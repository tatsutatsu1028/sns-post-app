"""
SNS投稿アプリ（保存機能なし・投稿専用）
Threads / Instagram に写真＋投稿文を投稿するだけのシンプルなアプリ。
写真（複数枚可）とメモから、Claudeが投稿文とハッシュタグを作る機能つき。
作った文章は投稿前に自分で確認・編集でき、自動では投稿しない。

secrets.toml に以下を設定して使う:

THREADS_ACCESS_TOKEN = "..."
THREADS_USER_ID = "..."
IG_ACCESS_TOKEN = "..."
IG_USER_ID = "..."
GITHUB_TOKEN = "..."
GITHUB_REPO = "your-name/sns-post-images"
GITHUB_BRANCH = "main"
ANTHROPIC_API_KEY = "..."
CLAUDE_TEXT_MODEL = "claude-haiku-5-5"   # 任意。省略時は Haiku
"""
import streamlit as st
from threads_poster import post_to_threads
from instagram_poster import post_to_instagram
from image_host import delete_image_from_github, upload_image_to_github
from caption_generator import DEFAULT_MODEL, MAX_IMAGES, USD_TO_JPY, generate_post

THREADS_MAX_CHARS = 500
INSTAGRAM_HASHTAG_LIMIT = 5

st.set_page_config(page_title="SNS投稿", page_icon="📸", layout="centered")

st.title("📸 SNS投稿")
st.caption("Threads / Instagram に投稿するだけ。保存はしません。")

# --- セッション状態の初期化 ---
for key in ("threads_text", "threads_topic", "instagram_text", "instagram_hashtags"):
    if key not in st.session_state:
        st.session_state[key] = ""


def parse_hashtags(text: str) -> list[str]:
    tags = []
    for word in text.replace("　", " ").split():
        word = word.lstrip("#＃")
        if word:
            tags.append(f"#{word}")
    return tags


def keep_first_hashtags():
    tags = parse_hashtags(st.session_state.instagram_hashtags)
    st.session_state.instagram_hashtags = " ".join(tags[:INSTAGRAM_HASHTAG_LIMIT])


# --- 写真とメモ ---
uploaded_images = st.file_uploader(
    "写真を選択（複数枚OK）",
    type=["jpg", "jpeg", "png"],
    accept_multiple_files=True,
)

if uploaded_images:
    cols = st.columns(min(len(uploaded_images), 4))
    for i, img in enumerate(uploaded_images):
        cols[i % len(cols)].image(img, use_container_width=True)

memo = st.text_area(
    "メモ（任意）",
    height=100,
    placeholder="例: 台北の夜市。屋台の胡椒餅が熱々でおいしかった",
)

# --- Claudeで投稿文を作る ---
already_generated = "gen_info" in st.session_state
button_label = "🔄 作り直す" if already_generated else "✨ 投稿文を作る"
if st.button(button_label, use_container_width=True):
    if not uploaded_images and not memo.strip():
        st.error("写真かメモのどちらかを入れてください")
    elif "ANTHROPIC_API_KEY" not in st.secrets:
        st.error("作れませんでした（ANTHROPIC_API_KEY が設定されていません）。自分で文章を書いて投稿できます。")
    else:
        if uploaded_images and len(uploaded_images) > MAX_IMAGES:
            st.warning(f"写真が多いので、先頭の{MAX_IMAGES}枚だけを使います")
        with st.spinner("Claudeが投稿文を作っています..."):
            result = generate_post(
                api_key=st.secrets["ANTHROPIC_API_KEY"],
                memo=memo,
                images=[img.getvalue() for img in uploaded_images or []],
                model=st.secrets.get("CLAUDE_TEXT_MODEL", DEFAULT_MODEL),
            )
        if result["success"]:
            # 下の編集欄（ウィジェット）より前なので、ここで値を入れられる
            st.session_state.threads_text = result["threads_text"]
            st.session_state.threads_topic = result["threads_topic"]
            st.session_state.instagram_text = result["instagram_text"]
            st.session_state.instagram_hashtags = " ".join(result["instagram_hashtags"])
            st.session_state.gen_info = result
            st.success("投稿文を作りました。下で確認・編集してから投稿してください。")
        else:
            st.error(result["message"])
            if result.get("detail"):
                st.caption(f"理由: {result['detail']}")

if "gen_info" in st.session_state:
    info = st.session_state.gen_info
    if info["cost_usd"] is not None:
        cost_text = f"約 ${info['cost_usd']:.4f}（約{info['cost_usd'] * USD_TO_JPY:.2f}円、1ドル={USD_TO_JPY}円で計算）"
    else:
        cost_text = "料金表にないモデルのため計算できません"
    st.caption(
        f"💰 前回の作成費用: {cost_text} ／ モデル: {info['model']} ／ "
        f"入力 {info['input_tokens']:,} トークン・出力 {info['output_tokens']:,} トークン"
    )

st.divider()

# --- 確認・編集（自分で書いてもOK） ---
st.subheader("📝 投稿文（確認・編集）")

st.markdown("**Threads**")
threads_text = st.text_area(
    "Threads用の文章",
    height=150,
    max_chars=THREADS_MAX_CHARS,
    placeholder="Threadsに投稿する文章を入力...",
    key="threads_text",
)
threads_topic = st.text_input(
    "Threadsのトピック（1つだけ・任意）",
    placeholder="例: 台湾旅行",
    help="Threadsは1投稿につきトピック（タグ）を1つだけ付けられます。#は不要です。",
    key="threads_topic",
)

st.markdown("**Instagram**")
instagram_text = st.text_area(
    "Instagram用の文章",
    height=200,
    placeholder="Instagramに投稿する文章を入力...",
    key="instagram_text",
)
instagram_hashtags = st.text_area(
    "Instagram用のハッシュタグ（スペース区切り）",
    height=80,
    placeholder="#旅行 #台湾旅行 ...",
    key="instagram_hashtags",
)
hashtag_list = parse_hashtags(instagram_hashtags)
if len(hashtag_list) > INSTAGRAM_HASHTAG_LIMIT:
    st.warning(
        f"ハッシュタグが{len(hashtag_list)}個あります。Instagramは1投稿あたりのハッシュタグが"
        f"{INSTAGRAM_HASHTAG_LIMIT}個までになったため、多すぎると反映されなかったり投稿に失敗したりする可能性があります。"
    )
    st.button(
        f"先頭の{INSTAGRAM_HASHTAG_LIMIT}個だけ残す",
        on_click=keep_first_hashtags,
    )

instagram_caption = instagram_text.strip()
if hashtag_list:
    instagram_caption = f"{instagram_caption}\n\n{' '.join(hashtag_list)}".strip()

st.divider()

# --- 投稿する写真 ---
post_image = None
if uploaded_images:
    if len(uploaded_images) == 1:
        post_image = uploaded_images[0]
    else:
        image_index = st.selectbox(
            "投稿に使う写真（1枚）",
            range(len(uploaded_images)),
            format_func=lambda i: f"{i + 1}枚目: {uploaded_images[i].name}",
        )
        post_image = uploaded_images[image_index]
        st.image(post_image, width=200)

col1, col2 = st.columns(2)
with col1:
    post_to_threads_checked = st.checkbox("Threadsに投稿", value=True)
with col2:
    post_to_instagram_checked = st.checkbox("Instagramに投稿", value=True)

st.divider()

# --- 投稿処理（ボタンを押した時だけ投稿する） ---
if st.button("投稿する", type="primary", use_container_width=True):
    if not post_to_threads_checked and not post_to_instagram_checked:
        st.error("投稿先を1つ以上選んでください")
        st.stop()

    if post_to_threads_checked and not threads_text.strip() and not post_image:
        st.error("Threads用の文章か写真のどちらかを入力してください")
        st.stop()

    if post_to_instagram_checked and not post_image:
        st.error("Instagram投稿には写真が必須です")
        st.stop()

    image_url = None
    uploaded = None

    # 画像がある場合は先にGitHubへアップロードしてURL化
    if post_image:
        with st.spinner("画像を準備中..."):
            upload_result = upload_image_to_github(
                github_token=st.secrets["GITHUB_TOKEN"],
                repo=st.secrets["GITHUB_REPO"],
                image_bytes=post_image.getvalue(),
                branch=st.secrets.get("GITHUB_BRANCH", "main"),
            )
            if not upload_result["success"]:
                st.error(upload_result["message"])
                st.stop()
            image_url = upload_result["url"]
            uploaded = upload_result

    try:
        # Threads投稿
        if post_to_threads_checked:
            with st.spinner("Threadsに投稿中..."):
                result = post_to_threads(
                    access_token=st.secrets["THREADS_ACCESS_TOKEN"],
                    user_id=st.secrets["THREADS_USER_ID"],
                    text=threads_text.strip(),
                    image_url=image_url,
                    topic_tag=threads_topic,
                )
                if result["success"]:
                    st.success(result["message"])
                else:
                    st.error(result["message"])

        # Instagram投稿
        if post_to_instagram_checked:
            with st.spinner("Instagramに投稿中..."):
                result = post_to_instagram(
                    access_token=st.secrets["IG_ACCESS_TOKEN"],
                    ig_user_id=st.secrets["IG_USER_ID"],
                    caption=instagram_caption,
                    image_url=image_url,
                )
                if result["success"]:
                    st.success(result["message"])
                else:
                    st.error(result["message"])
    finally:
        # 保存しない方針なので、投稿が終わったら（失敗した時も）画像を削除する。
        # 投稿は公開した時点でThreads/Instagram側に取り込まれているので、消しても投稿は残る。
        if uploaded:
            with st.spinner("投稿に使った画像を削除中..."):
                delete_result = delete_image_from_github(
                    github_token=st.secrets["GITHUB_TOKEN"],
                    repo=st.secrets["GITHUB_REPO"],
                    path=uploaded["path"],
                    sha=uploaded.get("sha"),
                    branch=st.secrets.get("GITHUB_BRANCH", "main"),
                )
            if delete_result["success"]:
                st.caption(f"🗑️ {delete_result['message']}")
            else:
                st.warning(f"{delete_result['message']}（GitHubのリポジトリから手動で消してください: {uploaded['path']}）")
