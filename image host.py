"""
Instagram APIは画像の直接アップロードができず、公開URLが必須。
このアプリでは保存機能を持たない方針なので、GitHubの公開リポジトリを
「一時的な画像置き場」として使い、投稿に使うraw URLを発行する。

Threadsは image_url を渡さずテキストのみ、または image_url ありで
投稿できるので、Threadsも画像付き投稿する場合は同じURLを使い回せる。

必要な secrets:
  GITHUB_TOKEN        (repoスコープのPersonal Access Token)
  GITHUB_REPO         (例: "your-name/sns-post-images")
  GITHUB_BRANCH       (例: "main"。省略時は "main")
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
) -> dict:
    """
    画像をGitHubリポジトリにアップロードし、raw URLを返す。

    戻り値: {"success": bool, "message": str, "url": str | None, "path": str | None}
    """
    try:
        timestamp = int(time.time())
        path = f"images/{filename_prefix}_{timestamp}.jpg"

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

        raw_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
        return {"success": True, "message": "画像をアップロードしました", "url": raw_url, "path": path}

    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("message", "")
        except Exception:
            pass
        return {"success": False, "message": f"画像アップロードエラー: {detail or str(e)}", "url": None, "path": None}
    except Exception as e:
        return {"success": False, "message": f"画像アップロードエラー: {str(e)}", "url": None, "path": None}
