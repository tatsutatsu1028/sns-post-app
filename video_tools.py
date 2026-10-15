"""
動画の長さを調べたり、Claudeに送るための静止画（場面）を切り出したりする。
Claudeは動画をそのまま見られないため、動画から数枚の場面を切り出して送る。

保存機能なしの方針なので、動画はメモリ上で読むだけで、ファイルには書き出さない。
"""
import io

import av

FRAMES_PER_VIDEO = 4


def get_video_duration(video_bytes: bytes) -> float | None:
    """動画の長さ（秒）を返す。読めない時は None。"""
    try:
        with av.open(io.BytesIO(video_bytes)) as container:
            if container.duration:
                return container.duration / av.time_base
            stream = container.streams.video[0]
            if stream.duration and stream.time_base:
                return float(stream.duration * stream.time_base)
    except Exception:
        pass
    return None


def extract_frames(video_bytes: bytes, count: int = FRAMES_PER_VIDEO) -> list[bytes]:
    """
    動画の最初から最後まで、均等な間隔で count 枚の場面をJPEGで切り出す。
    スマホで縦向きに撮った動画も、正しい向きに直す。
    """
    duration = get_video_duration(video_bytes) or 0
    frames = []
    with av.open(io.BytesIO(video_bytes)) as container:
        stream = container.streams.video[0]
        for i in range(count):
            # 最初と最後の黒い画面を避けるため、少し内側の位置を使う
            seconds = duration * (i + 0.5) / count
            container.seek(int(seconds * av.time_base), any_frame=False)
            frame = next(container.decode(stream), None)
            if frame is None:
                continue
            image = frame.to_image()
            if frame.rotation:
                image = image.rotate(frame.rotation, expand=True)
            out = io.BytesIO()
            image.convert("RGB").save(out, format="JPEG", quality=85)
            frames.append(out.getvalue())
    return frames
