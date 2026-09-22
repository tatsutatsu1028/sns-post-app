"""
Instagram Graph API 投稿処理
プロフェッショナルアカウント（ビジネス/クリエイター）＋Facebookページ連携が必要。

必要な secrets:
  IG_ACCESS_TOKEN
  IG_USER_ID   (Instagram Business Account ID。Page ID ではない点に注意)
"""
import requests
import time

FB_GRAPH_BASE = "https://graph.facebook.com/v21.0"


def post_to_instagram(access_token: str, ig_user_id: str, caption: str, image_url: str) -> dict:
    """
    Instagramに画像投稿する。
    Instagram APIは画像の直接アップロード不可のため、公開URL（image_url）が必須。

    戻り値: {"success": bool, "message": str, "post_id": str | None}
    """
    if not image_url:
        return {"success": False, "message": "Instagram投稿には画像の公開URLが必要です", "post_id": None}

    try:
        # Step 1: メディアコンテナを作成
        create_resp = requests.post(
            f"{FB_GRAPH_BASE}/{ig_user_id}/media",
            params={
                "access_token": access_token,
                "image_url": image_url,
                "caption": caption,
            },
            timeout=30,
        )
        create_resp.raise_for_status()
        creation_id = create_resp.json().get("id")

        if not creation_id:
            return {"success": False, "message": "コンテナ作成に失敗しました", "post_id": None}

        # コンテナのステータスがFINISHEDになるまで待つ
        for _ in range(10):
            status_resp = requests.get(
                f"{FB_GRAPH_BASE}/{creation_id}",
                params={"access_token": access_token, "fields": "status_code"},
                timeout=30,
            )
            status = status_resp.json().get("status_code")
            if status == "FINISHED":
                break
            time.sleep(2)

        # Step 2: 公開する
        publish_resp = requests.post(
            f"{FB_GRAPH_BASE}/{ig_user_id}/media_publish",
            params={"access_token": access_token, "creation_id": creation_id},
            timeout=30,
        )
        publish_resp.raise_for_status()
        post_id = publish_resp.json().get("id")

        return {"success": True, "message": "Instagramに投稿しました", "post_id": post_id}

    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("error", {}).get("message", "")
        except Exception:
            pass
        return {"success": False, "message": f"Instagram投稿エラー: {detail or str(e)}", "post_id": None}
    except Exception as e:
        return {"success": False, "message": f"Instagram投稿エラー: {str(e)}", "post_id": None}
