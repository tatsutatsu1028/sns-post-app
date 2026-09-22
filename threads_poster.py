"""
Threads API 投稿処理
自分のアカウントへの投稿のみなので審査不要。無料。

必要な secrets:
  THREADS_ACCESS_TOKEN
  THREADS_USER_ID
"""
import requests
import time

THREADS_API_BASE = "https://graph.threads.net/v1.0"


def post_to_threads(access_token: str, user_id: str, text: str, image_url: str | None = None) -> dict:
    """
    Threadsに投稿する。
    image_url を渡すと画像付き投稿（公開URLが必要）、
    渡さなければテキストのみの投稿になる。

    戻り値: {"success": bool, "message": str, "post_id": str | None}
    """
    try:
        # Step 1: メディアコンテナを作成
        create_params = {
            "access_token": access_token,
            "text": text,
        }
        if image_url:
            create_params["media_type"] = "IMAGE"
            create_params["image_url"] = image_url
        else:
            create_params["media_type"] = "TEXT"

        create_resp = requests.post(
            f"{THREADS_API_BASE}/{user_id}/threads",
            params=create_params,
            timeout=30,
        )
        create_resp.raise_for_status()
        creation_id = create_resp.json().get("id")

        if not creation_id:
            return {"success": False, "message": "コンテナ作成に失敗しました", "post_id": None}

        # 画像処理の反映待ち（公式推奨: 数秒待つ）
        time.sleep(3)

        # Step 2: 公開する
        publish_resp = requests.post(
            f"{THREADS_API_BASE}/{user_id}/threads_publish",
            params={"access_token": access_token, "creation_id": creation_id},
            timeout=30,
        )
        publish_resp.raise_for_status()
        post_id = publish_resp.json().get("id")

        return {"success": True, "message": "Threadsに投稿しました", "post_id": post_id}

    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("error", {}).get("message", "")
        except Exception:
            pass
        return {"success": False, "message": f"Threads投稿エラー: {detail or str(e)}", "post_id": None}
    except Exception as e:
        return {"success": False, "message": f"Threads投稿エラー: {str(e)}", "post_id": None}
