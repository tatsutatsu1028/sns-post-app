"""
SNS投稿アプリ（保存機能なし・投稿専用）
Threads / Instagram に写真または動画＋投稿文を投稿するだけのシンプルなアプリ。
写真・動画（複数可）とメモから、Claudeが投稿文とハッシュタグを作る機能つき。
作った文章は投稿前に自分で確認・編集でき、自動では投稿しない。

secrets.toml に以下を設定して使う:

THREADS_ACCESS_TOKEN = "..."
THREADS_USER_ID = "..."
IG_ACCESS_TOKEN = "..."
IG_USER_ID = "..."
GITHUB_TOKEN = "..."
GITHUB_REPO = "your-name/sns-post-images"
GITHUB_BRANCH = "main"
GITHUB_PAGES_URL = "https://your-name.github.io/sns-post-images"  # 任意。動画投稿用
ANTHROPIC_API_KEY = "..."
CLAUDE_TEXT_MODEL = "claude-haiku-5-5"   # 任意。省略時は Haiku
"""
import streamlit as st
from threads_poster import post_to_threads
from instagram_poster import post_to_instagram
from image_host import delete_image_from_github, upload_image_to_github, wait_until_public
from caption_generator import DEFAULT_MODEL, MAX_IMAGES, MAX_VIDEOS, USD_TO_JPY, generate_post
from video_tools import get_video_duration

THREADS_MAX_CHARS = 500
INSTAGRAM_HASHTAG_LIMIT = 5
VIDEO_EXTENSIONS = ("mp4", "mov")
# GitHubに置けるファイルは1つ100MBまでなので、少し余裕を持たせる
VIDEO_MAX_MB = 95
# Instagramのリールは3秒以上が必要
VIDEO_MIN_SECONDS = 3

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


def is_video(file) -> bool:
    return (file.type or "").startswith("video/") or file.name.lower().endswith(VIDEO_EXTENSIONS)


def file_extension(file) -> str:
    ext = file.name.rsplit(".", 1)[-1].lower() if "." in file.name else ""
    if is_video(file):
        return ext if ext in VIDEO_EXTENSIONS else "mp4"
    return "png" if ext == "png" else "jpg"


def keep_first_hashtags():
    tags = parse_hashtags(st.session_state.instagram_hashtags)
    st.session_state.instagram_hashtags = " ".join(tags[:INSTAGRAM_HASHTAG_LIMIT])


# --- 写真・動画とメモ ---
uploaded_files = st.file_uploader(
    "写真・動画を選択（複数OK）",
    type=["jpg", "jpeg", "png", *VIDEO_EXTENSIONS],
    accept_multiple_files=True,
) or []
uploaded_images = [f for f in uploaded_files if not is_video(f)]
uploaded_videos = [f for f in uploaded_files if is_video(f)]

if uploaded_images:
    cols = st.columns(min(len(uploaded_images), 4))
    for i, img in enumerate(uploaded_images):
        cols[i % len(cols)].image(img, use_container_width=True)
for video in uploaded_videos:
    st.video(video)

memo = st.text_area(
    "メモ（任意）",
    height=100,
    placeholder="例: 台北の夜市。屋台の胡椒餅が熱々でおいしかった",
)

# --- Claudeで投稿文を作る ---
already_generated = "gen_info" in st.session_state
button_label = "🔄 作り直す" if already_generated else "✨ 投稿文を作る"
if st.button(button_label, use_container_width=True):
    if not uploaded_files and not memo.strip():
        st.error("写真・動画かメモのどれかを入れてください")
    elif "ANTHROPIC_API_KEY" not in st.secrets:
        st.error("作れませんでした（ANTHROPIC_API_KEY が設定されていません）。自分で文章を書いて投稿できます。")
    else:
        if uploaded_images and len(uploaded_images) > MAX_IMAGES:
            st.warning(f"写真が多いので、先頭の{MAX_IMAGES}枚だけを使います")
        if len(uploaded_videos) > MAX_VIDEOS:
            st.warning(f"動画が多いので、先頭の{MAX_VIDEOS}本だけを使います")
        with st.spinner("Claudeが投稿文を作っています..."):
            result = generate_post(
                api_key=st.secrets["ANTHROPIC_API_KEY"],
                memo=memo,
                images=[img.getvalue() for img in uploaded_images],
                videos=[video.getvalue() for video in uploaded_videos],
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

# --- 投稿する写真・動画（1つ） ---
post_media = None
if uploaded_files:
    if len(uploaded_files) == 1:
        post_media = uploaded_files[0]
    else:
        media_index = st.selectbox(
            "投稿に使う写真・動画（1つ）",
            range(len(uploaded_files)),
            format_func=lambda i: f"{i + 1}つ目（{'動画' if is_video(uploaded_files[i]) else '写真'}）: {uploaded_files[i].name}",
        )
        post_media = uploaded_files[media_index]
        if not is_video(post_media):
            st.image(post_media, width=200)
post_is_video = post_media is not None and is_video(post_media)
if post_is_video:
    st.caption("動画はInstagramではリールとして投稿されます。投稿には数分かかることがあります。")

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

    if post_to_threads_checked and not threads_text.strip() and not post_media:
        st.error("Threads用の文章か写真・動画のどれかを入力してください")
        st.stop()

    if post_to_instagram_checked and not post_media:
        st.error("Instagram投稿には写真か動画が必須です")
        st.stop()

    if post_is_video:
        size_mb = post_media.size / 1024 / 1024
        if size_mb > VIDEO_MAX_MB:
            st.error(f"動画が大きすぎます（{size_mb:.0f}MB）。{VIDEO_MAX_MB}MB以下にしてください")
            st.stop()
        duration = get_video_duration(post_media.getvalue())
        if duration is not None and duration < VIDEO_MIN_SECONDS:
            st.error(f"動画が短すぎます（{duration:.1f}秒）。{VIDEO_MIN_SECONDS}秒以上にしてください")
            st.stop()

    media_url = None
    uploaded = None

    # 写真・動画がある場合は先にGitHubへアップロードしてURL化
    if post_media:
        with st.spinner("動画を準備中..." if post_is_video else "画像を準備中..."):
            upload_result = upload_image_to_github(
                github_token=st.secrets["GITHUB_TOKEN"],
                repo=st.secrets["GITHUB_REPO"],
                image_bytes=post_media.getvalue(),
                branch=st.secrets.get("GITHUB_BRANCH", "main"),
                extension=file_extension(post_media),
                # 動画は raw URL だとMetaが読めないことがあるので、設定があれば GitHub Pages のURLを使う
                pages_base_url=st.secrets.get("GITHUB_PAGES_URL") if post_is_video else None,
            )
            if not upload_result["success"]:
                st.error(upload_result["message"])
                st.stop()
            media_url = upload_result["url"]
            uploaded = upload_result

    try:
        if post_is_video and st.secrets.get("GITHUB_PAGES_URL"):
            with st.spinner("動画がGitHub Pagesで公開されるのを待っています（1〜3分）..."):
                if not wait_until_public(media_url):
                    st.error("動画がGitHub Pagesで公開されませんでした。GITHUB_PAGES_URL とPagesの設定を確認してください")
                    st.stop()

        image_url = None if post_is_video else media_url
        video_url = media_url if post_is_video else None

        # Threads投稿
        if post_to_threads_checked:
            with st.spinner("Threadsに投稿中..."):
                result = post_to_threads(
                    access_token=st.secrets["THREADS_ACCESS_TOKEN"],
                    user_id=st.secrets["THREADS_USER_ID"],
                    text=threads_text.strip(),
                    image_url=image_url,
                    video_url=video_url,
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
                    video_url=video_url,
                )
                if result["success"]:
                    st.success(result["message"])
                else:
                    st.error(result["message"])
                    if post_is_video and not st.secrets.get("GITHUB_PAGES_URL"):
                        st.info("動画が読み込めない場合は、GitHub Pagesを有効にして GITHUB_PAGES_URL を設定すると直ることがあります")
    finally:
        # 保存しない方針なので、投稿が終わったら（失敗した時も）写真・動画を削除する。
        # 投稿は公開した時点でThreads/Instagram側に取り込まれているので、消しても投稿は残る。
        if uploaded:
            with st.spinner("投稿に使ったファイルを削除中..."):
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
