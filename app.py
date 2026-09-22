"""
SNS投稿アプリ（保存機能なし・投稿専用）
Threads / Instagram に写真＋キャプションを投稿するだけのシンプルなアプリ。

secrets.toml に以下を設定して使う:

THREADS_ACCESS_TOKEN = "..."
THREADS_USER_ID = "..."
IG_ACCESS_TOKEN = "..."
IG_USER_ID = "..."
GITHUB_TOKEN = "..."
GITHUB_REPO = "your-name/sns-post-images"
GITHUB_BRANCH = "main"
"""
import streamlit as st
from threads_poster import post_to_threads
from instagram_poster import post_to_instagram
from image_host import upload_image_to_github

st.set_page_config(page_title="SNS投稿", page_icon="📸", layout="centered")

st.title("📸 SNS投稿")
st.caption("Threads / Instagram に投稿するだけ。保存はしません。")

# --- 入力 ---
uploaded_image = st.file_uploader("写真を選択", type=["jpg", "jpeg", "png"])

if uploaded_image:
    st.image(uploaded_image, use_container_width=True)

caption = st.text_area("キャプション", height=150, placeholder="投稿文を入力...")

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
