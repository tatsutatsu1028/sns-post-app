"""
写真とキーワードから、Threads用・Instagram用の投稿文を自動生成する。
Anthropic Claude APIを使用。

必要な secrets:
  ANTHROPIC_API_KEY
"""
import base64
import json
import requests

CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
CLAUDE_MODEL = "claude-sonnet-4-5"


def _image_to_base64(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media_type,
            "data": b64,
        },
    }


def generate_captions(
    api_key: str,
    keywords: str,
    image_bytes: bytes | None = None,
    media_type: str = "image/jpeg",
) -> dict:
    """
    キーワード（と任意で写真）から、Threads用・Instagram用（ハッシュタグ付き）の
    投稿文を生成する。

    戻り値: {"success": bool, "message": str, "threads_caption": str, "instagram_caption": str}
    """
    try:
        content = []
        if image_bytes:
            content.append(_image_to_base64(image_bytes, media_type))

        prompt = f"""あなたはSNS投稿文の作成が得意なアシスタントです。
以下のキーワードと（あれば）添付された写真をもとに、SNS投稿用のキャプションを2種類作成してください。

キーワード: {keywords}

【出力条件】
1. Threads用のキャプション（ハッシュタグなし、カジュアルで短め、絵文字を適度に使う）
2. Instagram用のキャプション（本文＋最後にハッシュタグを6〜10個、日本語ハッシュタグ中心）

必ず以下のJSON形式のみで出力してください。他の説明文は一切含めないでください。
{{"threads": "ここにThreads用キャプション", "instagram": "ここにInstagram用キャプション（ハッシュタグ込み）"}}
"""
        content.append({"type": "text", "text": prompt})

        resp = requests.post(
            CLAUDE_API_URL,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": CLAUDE_MODEL,
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": content}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

        text = "".join(
            block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
        ).strip()

        # ```json ... ``` のようなコードブロックで返ってくることがあるので除去
        text = text.replace("```json", "").replace("```", "").strip()

        parsed = json.loads(text)

        return {
            "success": True,
            "message": "投稿文を生成しました",
            "threads_caption": parsed.get("threads", ""),
            "instagram_caption": parsed.get("instagram", ""),
        }

    except requests.exceptions.HTTPError as e:
        detail = ""
        try:
            detail = e.response.json().get("error", {}).get("message", "")
        except Exception:
            pass
        return {
            "success": False,
            "message": f"生成エラー: {detail or str(e)}",
            "threads_caption": "",
            "instagram_caption": "",
        }
    except json.JSONDecodeError:
        return {
            "success": False,
            "message": "生成結果の解析に失敗しました。もう一度試してください。",
            "threads_caption": "",
            "instagram_caption": "",
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"生成エラー: {str(e)}",
            "threads_caption": "",
            "instagram_caption": "",
        }
