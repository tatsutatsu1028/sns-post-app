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


def clean_topic_tag(topic: str) -> str:
    """
    Threadsのトピック（1投稿に1つだけ付けられるタグ）として使える形に整える。
    先頭の # と、使えない文字（ピリオド・アンパサンド）を取り除き、50文字までにする。
    """
    topic = topic.strip().lstrip("#＃")
    for ch in (".", "&", "。", "＆"):
        topic = topic.replace(ch, "")
    return topic.strip()[:50]


def _wait_for_container(access_token: str, creation_id: str, timeout_seconds: int = 300) -> str | None:
    """
    動画のコンテナの処理が終わるまで待つ。終わったら None、失敗したらエラー文を返す。
    """
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        resp = requests.get(
            f"{THREADS_API_BASE}/{creation_id}",
            params={"access_token": access_token, "fields": "status,error_message"},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")
        if status == "FINISHED":
            return None
        if status in ("ERROR", "EXPIRED"):
            return f"動画の処理に失敗しました（{data.get('error_message') or status}）"
        time.sleep(5)
    return "動画の処理が時間内に終わりませんでした"


def post_to_threads(
    access_token: str,
    user_id: str,
    text: str,
    image_url: str | None = None,
    topic_tag: str = "",
    video_url: str | None = None,
) -> dict:
    """
    Threadsに投稿する。
    image_url を渡すと画像付き投稿、video_url を渡すと動画付き投稿（どちらも公開URLが必要）、
    どちらも渡さなければテキストのみの投稿になる。
    topic_tag を渡すと、その投稿にトピックを1つ付ける。

    戻り値: {"success": bool, "message": str, "post_id": str | None}
    """
    try:
        # Step 1: メディアコンテナを作成
        create_params = {
            "access_token": access_token,
            "text": text,
        }
        if video_url:
            create_params["media_type"] = "VIDEO"
            create_params["video_url"] = video_url
        elif image_url:
            create_params["media_type"] = "IMAGE"
            create_params["image_url"] = image_url
        else:
            create_params["media_type"] = "TEXT"
        topic_tag = clean_topic_tag(topic_tag)
        if topic_tag:
            create_params["topic_tag"] = topic_tag

        create_resp = requests.post(
            f"{THREADS_API_BASE}/{user_id}/threads",
            params=create_params,
            timeout=30,
        )
        create_resp.raise_for_status()
        creation_id = create_resp.json().get("id")

        if not creation_id:
            return {"success": False, "message": "コンテナ作成に失敗しました", "post_id": None}

        if video_url:
            # 動画はThreads側の処理が終わる（FINISHED）まで待つ
            error = _wait_for_container(access_token, creation_id)
            if error:
                return {"success": False, "message": f"Threads投稿エラー: {error}", "post_id": None}
        else:
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
