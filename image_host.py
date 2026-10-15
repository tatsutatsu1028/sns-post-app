"""
Instagram APIは画像の直接アップロードができず、公開URLが必須。
このアプリでは保存機能を持たない方針なので、GitHubの公開リポジトリを
「一時的な画像置き場」として使い、投稿に使うraw URLを発行する。
投稿が終わったら delete_image_from_github で削除する。

Threadsは image_url を渡さずテキストのみ、または image_url ありで
投稿できるので、Threadsも画像付き投稿する場合は同じURLを使い回せる。

動画は raw URL だと種類（Content-Type）が application/octet-stream になり、
Meta側で読み込めないことがある。GitHub Pages を有効にして GITHUB_PAGES_URL を
設定すると、動画は Pages のURL（video/mp4 として配信される）を使う。

必要な secrets:
  GITHUB_TOKEN        (repoスコープのPersonal Access Token)
  GITHUB_REPO         (例: "your-name/sns-post-images")
  GITHUB_BRANCH       (例: "main"。省略時は "main")
任意の secrets:
  GITHUB_PAGES_URL    (例: "https://your-name.github.io/sns-post-images")
"""
import base64
import time
import requests

GITHUB_API_BASE = "https://api.github.com"


def upload_image_to_github(
    github_token: str,
    repo: str,
    image_bytes: bytes,
    filename_prefix: str = "post",
    branch: str = "main",
    extension: str = "jpg",
    pages_base_url: str | None = None,
) -> dict:
    """
    画像（または動画）をGitHubリポジトリにアップロードし、公開URLを返す。
    pages_base_url を渡すと GitHub Pages のURL、渡さなければ raw URL を返す。

    戻り値: {"success": bool, "message": str, "url": str | None, "path": str | None, "sha": str | None}
    """
    try:
        timestamp = int(time.time())
        path = f"images/{filename_prefix}_{timestamp}.{extension}"

        content_b64 = base64.b64encode(image_bytes).decode("utf-8")

        resp = requests.put(
            f"{GITHUB_API_BASE}/repos/{repo}/contents/{path}",
            headers={
                "Authorization": f"Bearer {github_token}",
                "Accept": "application/vnd.github+json",
            },
            json={
                "message": f"add post image {timestamp}",
                "content": content_b64,
                "branch": branch,
            },
            timeout=30,
        )
        resp.raise_for_status()
        sha = resp.json().get("content", {}).get("sha")

        if pages_base_url:
            url = f"{pages_base_url.rstrip('/')}/{path}"
        else:
            url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
        return {"success": True, "message": "アップロードしました", "url": url, "path": path, "sha": sha}

    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("message", "")
        except Exception:
            pass
        return {"success": False, "message": f"画像アップロードエラー: {detail or str(e)}", "url": None, "path": None, "sha": None}
    except Exception as e:
        return {"success": False, "message": f"画像アップロードエラー: {str(e)}", "url": None, "path": None, "sha": None}


def wait_until_public(url: str, timeout_seconds: int = 300, interval_seconds: int = 10) -> bool:
    """
    アップロードしたファイルがURLで見られるようになるまで待つ。
    GitHub Pages は反映に1〜数分かかるため。見られるようになったら True。
    """
    deadline = time.time() + timeout_seconds
    while True:
        try:
            if requests.head(url, timeout=15, allow_redirects=True).status_code == 200:
                return True
        except requests.exceptions.RequestException:
            pass
        if time.time() >= deadline:
            return False
        time.sleep(interval_seconds)


def delete_image_from_github(
    github_token: str,
    repo: str,
    path: str,
    sha: str | None = None,
    branch: str = "main",
) -> dict:
    """
    投稿が終わった画像をGitHubリポジトリから削除する。
    sha が分からない時は、ファイル情報を取得してから削除する。

    戻り値: {"success": bool, "message": str}
    """
    headers = {
        "Authorization": f"Bearer {github_token}",
        "Accept": "application/vnd.github+json",
    }
    url = f"{GITHUB_API_BASE}/repos/{repo}/contents/{path}"
    try:
        if not sha:
            info_resp = requests.get(url, headers=headers, params={"ref": branch}, timeout=30)
            info_resp.raise_for_status()
            sha = info_resp.json().get("sha")

        resp = requests.delete(
            url,
            headers=headers,
            json={"message": f"delete posted image {path}", "sha": sha, "branch": branch},
            timeout=30,
        )
        resp.raise_for_status()
        return {"success": True, "message": "投稿に使ったファイルを削除しました"}

    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("message", "")
        except Exception:
            pass
        return {"success": False, "message": f"画像の削除エラー: {detail or str(e)}"}
    except Exception as e:
        return {"success": False, "message": f"画像の削除エラー: {str(e)}"}
