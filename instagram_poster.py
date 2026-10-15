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


def _token_hint(access_token: str, api_base: str) -> str:
    """
    トークンの問題を調べるためのヒント。トークン本体は出さず、
    先頭4文字・長さ・接続先・おかしな文字が混ざっていないかだけを表示する。
    """
    host = api_base.split("/")[2]
    hint = f"接続先: {host} ／ トークン: 「{access_token[:4]}…」で始まる{len(access_token)}文字"
    if access_token.startswith("your-"):
        hint += " ／ ⚠️ Secretsの値がひな形のままです"
    elif any(c.isspace() for c in access_token) or not access_token.isascii():
        hint += " ／ ⚠️ トークンの途中に空白・改行・全角文字が混ざっています"
    return hint


def post_to_instagram(
    access_token: str,
    ig_user_id: str,
    caption: str,
    image_url: str | None = None,
    video_url: str | None = None,
) -> dict:
    """
    Instagramに画像、または動画（リール）を投稿する。
    Instagram APIはファイルの直接アップロード不可のため、公開URL（image_url か video_url）が必須。

    戻り値: {"success": bool, "message": str, "post_id": str | None}
    """
    if not image_url and not video_url:
        return {"success": False, "message": "Instagram投稿には写真か動画の公開URLが必要です", "post_id": None}

    # Secretsに貼り付けた時に紛れ込みやすい空白・改行・引用符を取り除く
    access_token = access_token.strip().strip('"').strip("'").strip()
    ig_user_id = str(ig_user_id).strip()
    api_base = _api_base(access_token)

    try:
        # Step 1: メディアコンテナを作成
        create_params = {"access_token": access_token, "caption": caption}
        if video_url:
            create_params["media_type"] = "REELS"
            create_params["video_url"] = video_url
            create_params["share_to_feed"] = "true"
        else:
            create_params["image_url"] = image_url
        create_resp = requests.post(
            f"{api_base}/{ig_user_id}/media",
            params=create_params,
            timeout=30,
        )
        create_resp.raise_for_status()
        creation_id = create_resp.json().get("id")

        if not creation_id:
            return {"success": False, "message": "コンテナ作成に失敗しました", "post_id": None}

        # コンテナのステータスがFINISHEDになるまで待つ（動画は処理に時間がかかる）
        wait_times = [5] * 60 if video_url else [2] * 10
        for wait in wait_times:
            status_resp = requests.get(
                f"{api_base}/{creation_id}",
                params={"access_token": access_token, "fields": "status_code,status"},
                timeout=30,
            )
            status_data = status_resp.json()
            status = status_data.get("status_code")
            if status == "FINISHED":
                break
            if status in ("ERROR", "EXPIRED"):
                detail = status_data.get("status") or status
                return {"success": False, "message": f"Instagram投稿エラー: 動画の処理に失敗しました（{detail}）", "post_id": None}
            time.sleep(wait)
        else:
            if video_url:
                return {"success": False, "message": "Instagram投稿エラー: 動画の処理が時間内に終わりませんでした", "post_id": None}

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
        message = f"Instagram投稿エラー: {detail or str(e)}"
        if "access token" in detail.lower():
            message += f"（{_token_hint(access_token, api_base)}）"
        return {"success": False, "message": message, "post_id": None}
    except Exception as e:
        return {"success": False, "message": f"Instagram投稿エラー: {str(e)}", "post_id": None}
