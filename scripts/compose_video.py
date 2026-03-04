"""
動画合成モジュール
ナレーション + 画像/動画素材 → 完成動画
"""

import os
import subprocess
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class VideoSegment:
    """動画セグメント"""
    visual_path: str  # 画像または動画
    audio_path: str   # ナレーション音声
    duration: float   # 秒


def get_audio_duration(audio_path: str) -> float:
    """音声ファイルの長さを取得"""
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
         '-of', 'default=noprint_wrappers=1:nokey=1', audio_path],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())


def create_video_from_image(
    image_path: str,
    duration: float,
    output_path: str,
    effect: str = "zoom_in"
) -> str:
    """画像から動画を作成（Ken Burnsエフェクト付き）"""

    effects = {
        "zoom_in": "scale=8000:-1,zoompan=z='min(zoom+0.001,1.3)':d={frames}:s=1920x1080:fps=30",
        "zoom_out": "scale=8000:-1,zoompan=z='if(lte(zoom,1.0),1.3,max(1.001,zoom-0.001))':d={frames}:s=1920x1080:fps=30",
        "pan_left": "scale=2880:-1,zoompan=z='1':x='iw/2-(iw/zoom/2)+((iw/zoom)/{frames})*on':y='ih/2-(ih/zoom/2)':d={frames}:s=1920x1080:fps=30",
        "pan_right": "scale=2880:-1,zoompan=z='1':x='iw/2-(iw/zoom/2)-((iw/zoom)/{frames})*on':y='ih/2-(ih/zoom/2)':d={frames}:s=1920x1080:fps=30",
        "static": "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2"
    }

    frames = int(duration * 30)
    filter_str = effects.get(effect, effects["zoom_in"]).format(frames=frames)

    cmd = [
        'ffmpeg', '-y',
        '-loop', '1',
        '-i', image_path,
        '-vf', filter_str,
        '-c:v', 'libx264',
        '-t', str(duration),
        '-pix_fmt', 'yuv420p',
        '-r', '30',
        output_path
    ]

    subprocess.run(cmd, check=True, capture_output=True)

    return output_path


def add_audio_to_video(video_path: str, audio_path: str, output_path: str) -> str:
    """動画に音声を追加"""
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-i', audio_path,
        '-c:v', 'copy',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-shortest',
        output_path
    ]

    subprocess.run(cmd, check=True, capture_output=True)

    return output_path


def concatenate_videos(video_paths: List[str], output_path: str) -> str:
    """複数の動画を結合"""
    # 一時ファイルリストを作成
    list_file = Path(output_path).parent / "concat_list.txt"

    with open(list_file, 'w') as f:
        for video_path in video_paths:
            f.write(f"file '{video_path}'\n")

    cmd = [
        'ffmpeg', '-y',
        '-f', 'concat',
        '-safe', '0',
        '-i', str(list_file),
        '-c', 'copy',
        output_path
    ]

    subprocess.run(cmd, check=True, capture_output=True)

    # 一時ファイルを削除
    list_file.unlink()

    return output_path


def add_background_music(
    video_path: str,
    music_path: str,
    output_path: str,
    music_volume: float = 0.15
) -> str:
    """BGMを追加"""
    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-i', music_path,
        '-filter_complex',
        f'[1:a]volume={music_volume}[music];[0:a][music]amix=inputs=2:duration=first[a]',
        '-map', '0:v',
        '-map', '[a]',
        '-c:v', 'copy',
        '-c:a', 'aac',
        output_path
    ]

    subprocess.run(cmd, check=True, capture_output=True)

    return output_path


def compose_video(
    audio_segments: List[str],  # ナレーション音声ファイルのリスト
    visual_assets: List[str],   # 画像/動画ファイルのリスト
    output_path: str,
    temp_dir: str,
    bgm_path: str = None
) -> str:
    """動画を合成"""

    temp_path = Path(temp_dir)
    temp_path.mkdir(parents=True, exist_ok=True)

    segment_videos = []

    # 各セグメントを処理
    for i, audio_path in enumerate(audio_segments):
        # 対応する画像を取得（ループ）
        visual_index = i % len(visual_assets)
        visual_path = visual_assets[visual_index]

        # 音声の長さを取得
        duration = get_audio_duration(audio_path)

        # エフェクトをローテーション
        effects = ["zoom_in", "zoom_out", "pan_left", "pan_right"]
        effect = effects[i % len(effects)]

        print(f"セグメント {i+1}/{len(audio_segments)} を合成中...")

        # 画像から動画を作成
        video_only = temp_path / f"segment_{i:03d}_video.mp4"
        create_video_from_image(visual_path, duration, str(video_only), effect)

        # 音声を追加
        video_with_audio = temp_path / f"segment_{i:03d}_final.mp4"
        add_audio_to_video(str(video_only), audio_path, str(video_with_audio))

        segment_videos.append(str(video_with_audio))

    # 全セグメントを結合
    print("セグメントを結合中...")
    combined_video = temp_path / "combined.mp4"
    concatenate_videos(segment_videos, str(combined_video))

    # BGMを追加（オプション）
    if bgm_path and Path(bgm_path).exists():
        print("BGMを追加中...")
        add_background_music(str(combined_video), bgm_path, output_path)
    else:
        # BGMなしの場合はそのままコピー
        import shutil
        shutil.copy(str(combined_video), output_path)

    print(f"動画を保存しました: {output_path}")

    return output_path


def add_intro_outro(
    main_video: str,
    intro_video: str,
    outro_video: str,
    output_path: str
) -> str:
    """イントロとアウトロを追加"""
    videos = []

    if intro_video and Path(intro_video).exists():
        videos.append(intro_video)

    videos.append(main_video)

    if outro_video and Path(outro_video).exists():
        videos.append(outro_video)

    if len(videos) == 1:
        import shutil
        shutil.copy(main_video, output_path)
        return output_path

    return concatenate_videos(videos, output_path)


if __name__ == "__main__":
    print("動画合成モジュール")
    print("使用例:")
    print("  compose_video(audio_segments, visual_assets, 'output.mp4', 'temp/')")
