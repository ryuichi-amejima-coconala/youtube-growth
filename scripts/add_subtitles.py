"""
字幕追加モジュール
Whisperで文字起こし → 字幕を動画に焼き込み
"""

import os
import subprocess
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class SubtitleSegment:
    """字幕セグメント"""
    start_time: float
    end_time: float
    text: str


def transcribe_audio_with_whisper(audio_path: str, model: str = "base") -> List[SubtitleSegment]:
    """Whisperで音声を文字起こし"""
    import whisper

    print(f"Whisperモデル '{model}' を読み込み中...")
    whisper_model = whisper.load_model(model)

    print("文字起こし中...")
    result = whisper_model.transcribe(
        audio_path,
        language="ja",
        word_timestamps=True
    )

    segments = []
    for segment in result["segments"]:
        segments.append(SubtitleSegment(
            start_time=segment["start"],
            end_time=segment["end"],
            text=segment["text"].strip()
        ))

    return segments


def format_time_srt(seconds: float) -> str:
    """SRT形式の時間フォーマット"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt_file(segments: List[SubtitleSegment], output_path: str) -> str:
    """SRTファイルを生成"""
    with open(output_path, 'w', encoding='utf-8') as f:
        for i, segment in enumerate(segments, 1):
            f.write(f"{i}\n")
            f.write(f"{format_time_srt(segment.start_time)} --> {format_time_srt(segment.end_time)}\n")
            f.write(f"{segment.text}\n")
            f.write("\n")

    return output_path


def format_time_ass(seconds: float) -> str:
    """ASS形式の時間フォーマット"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60

    return f"{hours}:{minutes:02d}:{secs:05.2f}"


def generate_ass_file(
    segments: List[SubtitleSegment],
    output_path: str,
    font_name: str = "Noto Sans JP",
    font_size: int = 48,
    primary_color: str = "&H00FFFFFF",  # 白
    outline_color: str = "&H00000000",  # 黒
    outline_width: int = 3
) -> str:
    """ASS字幕ファイルを生成（スタイル付き）"""

    header = f"""[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_name},{font_size},{primary_color},&H000000FF,{outline_color},&H80000000,-1,0,0,0,100,100,0,0,1,{outline_width},1,2,10,10,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(header)

        for segment in segments:
            start = format_time_ass(segment.start_time)
            end = format_time_ass(segment.end_time)
            # テキストの改行を\\Nに変換
            text = segment.text.replace('\n', '\\N')
            f.write(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")

    return output_path


def burn_subtitles(
    video_path: str,
    subtitle_path: str,
    output_path: str,
    subtitle_format: str = "ass"
) -> str:
    """字幕を動画に焼き込み"""

    if subtitle_format == "ass":
        # ASSファイルを使用
        filter_str = f"ass={subtitle_path}"
    else:
        # SRTファイルを使用
        filter_str = f"subtitles={subtitle_path}:force_style='Fontsize=24,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=2'"

    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-vf', filter_str,
        '-c:v', 'libx264',
        '-c:a', 'copy',
        '-preset', 'medium',
        '-crf', '23',
        output_path
    ]

    subprocess.run(cmd, check=True, capture_output=True)

    return output_path


def add_subtitles_to_video(
    video_path: str,
    audio_path: str,  # ナレーション音声（文字起こし用）
    output_path: str,
    temp_dir: str,
    whisper_model: str = "base"
) -> str:
    """動画に字幕を追加"""

    temp_path = Path(temp_dir)
    temp_path.mkdir(parents=True, exist_ok=True)

    # 1. 音声を文字起こし
    print("字幕を生成中...")
    segments = transcribe_audio_with_whisper(audio_path, whisper_model)

    # 2. ASS字幕ファイルを生成
    subtitle_path = temp_path / "subtitles.ass"
    generate_ass_file(segments, str(subtitle_path))

    # 3. 字幕を動画に焼き込み
    print("字幕を動画に焼き込み中...")
    burn_subtitles(video_path, str(subtitle_path), output_path)

    print(f"字幕付き動画を保存しました: {output_path}")

    return output_path


def add_subtitles_from_script(
    video_path: str,
    script_text: str,  # 台本のナレーション部分
    audio_path: str,
    output_path: str,
    temp_dir: str
) -> str:
    """台本テキストを元に字幕を追加（Whisperで同期）"""

    # Whisperで文字起こし
    segments = transcribe_audio_with_whisper(audio_path)

    # 台本のテキストで置き換え（Whisperのタイミングを使用）
    # TODO: より高度な同期アルゴリズムを実装

    temp_path = Path(temp_dir)
    subtitle_path = temp_path / "subtitles.ass"
    generate_ass_file(segments, str(subtitle_path))

    return burn_subtitles(video_path, str(subtitle_path), output_path)


if __name__ == "__main__":
    print("字幕追加モジュール")
    print("使用例:")
    print("  add_subtitles_to_video('video.mp4', 'audio.mp3', 'output.mp4', 'temp/')")
