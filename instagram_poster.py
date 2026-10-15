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
IG_GRAPH_BASE = "https://graph.instagram.com/v21.0"


def _api_base(access_token: str) -> str:
    """
    トークンの種類に合わせて接続先を選ぶ。
    「Instagramログイン」で発行したトークン（IGで始まる）は graph.instagram.com、
    「Facebookログイン」で発行したトークン（EAAで始まる）は graph.facebook.com でしか使えない。
    違う方に送ると「Cannot parse access token」エラーになる。
    """
    return IG_GRAPH_BASE if access_token.startswith("IG") else FB_GRAPH_BASE


def post_to_instagram(access_token: str, ig_user_id: str, caption: str, image_url: str) -> dict:
    """
    Instagramに画像投稿する。
    Instagram APIは画像の直接アップロード不可のため、公開URL（image_url）が必須。

    戻り値: {"success": bool, "message": str, "post_id": str | None}
    """
    if not image_url:
        return {"success": False, "message": "Instagram投稿には画像の公開URLが必要です", "post_id": None}

    # Secretsに貼り付けた時に紛れ込みやすい空白・改行・引用符を取り除く
    access_token = access_token.strip().strip('"').strip("'").strip()
    ig_user_id = str(ig_user_id).strip()
    api_base = _api_base(access_token)

    try:
        # Step 1: メディアコンテナを作成
        create_resp = requests.post(
            f"{api_base}/{ig_user_id}/media",
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
                f"{api_base}/{creation_id}",
                params={"access_token": access_token, "fields": "status_code"},
                timeout=30,
            )
            status = status_resp.json().get("status_code")
            if status == "FINISHED":
                break
            time.sleep(2)

        # Step 2: 公開する
        publish_resp = requests.post(
            f"{api_base}/{ig_user_id}/media_publish",
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
