"""
SNS投稿アプリ（保存機能なし・投稿専用）
Threads / Instagram に写真＋キャプションを投稿するだけのシンプルなアプリ。
キーワード（＋写真）からAIがキャプションを自動生成する機能つき。

secrets.toml に以下を設定して使う:

THREADS_ACCESS_TOKEN = "..."
THREADS_USER_ID = "..."
IG_ACCESS_TOKEN = "..."
IG_USER_ID = "..."
GITHUB_TOKEN = "..."
GITHUB_REPO = "your-name/sns-post-images"
GITHUB_BRANCH = "main"
ANTHROPIC_API_KEY = "..."
"""
import streamlit as st
from threads_poster import post_to_threads
from instagram_poster import post_to_instagram
from image_host import upload_image_to_github
from caption_generator import generate_captions

st.set_page_config(page_title="SNS投稿", page_icon="📸", layout="centered")

st.title("📸 SNS投稿")
st.caption("Threads / Instagram に投稿するだけ。保存はしません。")

# --- セッション状態の初期化 ---
if "caption" not in st.session_state:
    st.session_state.caption = ""

# --- 写真アップロード ---
uploaded_image = st.file_uploader("写真を選択", type=["jpg", "jpeg", "png"])

if uploaded_image:
    st.image(uploaded_image, use_container_width=True)

st.divider()

# --- キャプション自動生成 ---
st.subheader("✨ キャプション自動生成（任意）")
keywords = st.text_input(
    "キーワードを入力",
    placeholder="例: マレーシア、ツインタワー、夜景",
)

gen_col1, gen_col2 = st.columns(2)
with gen_col1:
    target_platform = st.radio(
        "生成対象",
        ["両方", "Threadsのみ", "Instagramのみ"],
        horizontal=True,
        label_visibility="collapsed",
    )

if st.button("投稿文を生成する", use_container_width=True):
    if not keywords:
        st.error("キーワードを入力してください")
    elif "ANTHROPIC_API_KEY" not in st.secrets:
        st.error("ANTHROPIC_API_KEY が設定されていません")
    else:
        with st.spinner("生成中..."):
            image_bytes = uploaded_image.getvalue() if uploaded_image else None
            media_type = uploaded_image.type if uploaded_image else "image/jpeg"
            result = generate_captions(
                api_key=st.secrets["ANTHROPIC_API_KEY"],
                keywords=keywords,
                image_bytes=image_bytes,
                media_type=media_type,
            )
            if result["success"]:
                st.session_state.generated_threads = result["threads_caption"]
                st.session_state.generated_instagram = result["instagram_caption"]
                st.success(result["message"])
            else:
                st.error(result["message"])

# 生成結果があれば選んで反映できるようにする
if st.session_state.get("generated_threads") or st.session_state.get("generated_instagram"):
    st.write("生成結果（クリックでキャプション欄に反映）")
    gcol1, gcol2 = st.columns(2)
    with gcol1:
        st.text_area("Threads用（生成結果）", st.session_state.get("generated_threads", ""), height=120, key="gen_threads_display")
        if st.button("これをThreads用に使う", use_container_width=True):
            st.session_state.caption = st.session_state.get("generated_threads", "")
    with gcol2:
        st.text_area("Instagram用（生成結果）", st.session_state.get("generated_instagram", ""), height=120, key="gen_ig_display")
        if st.button("これをInstagram用に使う", use_container_width=True):
            st.session_state.caption = st.session_state.get("generated_instagram", "")

st.divider()

# --- 入力 ---
caption = st.text_area("キャプション", height=150, placeholder="投稿文を入力...", key="caption")

st.divider()
col1, col2 = st.columns(2)
with col1:
    post_to_threads_checked = st.checkbox("Threadsに投稿", value=True)
with col2:
    post_to_instagram_checked = st.checkbox("Instagramに投稿", value=True)

st.divider()

# --- 投稿処理 ---
if st.button("投稿する", type="primary", use_container_width=True):
    if not caption and not uploaded_image:
        st.error("キャプションか写真のどちらかを入力してください")
        st.stop()

    if not post_to_threads_checked and not post_to_instagram_checked:
        st.error("投稿先を1つ以上選んでください")
        st.stop()

    if post_to_instagram_checked and not uploaded_image:
        st.error("Instagram投稿には写真が必須です")
        st.stop()

    image_url = None

    # 画像がある場合は先にGitHubへアップロードしてURL化
    if uploaded_image:
        with st.spinner("画像を準備中..."):
            image_bytes = uploaded_image.getvalue()
            upload_result = upload_image_to_github(
                github_token=st.secrets["GITHUB_TOKEN"],
                repo=st.secrets["GITHUB_REPO"],
                image_bytes=image_bytes,
                branch=st.secrets.get("GITHUB_BRANCH", "main"),
            )
            if not upload_result["success"]:
                st.error(upload_result["message"])
                st.stop()
            image_url = upload_result["url"]

    # Threads投稿
    if post_to_threads_checked:
        with st.spinner("Threadsに投稿中..."):
            result = post_to_threads(
                access_token=st.secrets["THREADS_ACCESS_TOKEN"],
                user_id=st.secrets["THREADS_USER_ID"],
                text=caption,
                image_url=image_url,
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
                caption=caption,
                image_url=image_url,
            )
            if result["success"]:
                st.success(result["message"])
            else:
                st.error(result["message"])
