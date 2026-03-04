"""
ナレーション生成モジュール
ElevenLabs APIまたはVOICEVOXを使用してナレーション音声を生成
"""

import os
import re
import time
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class NarrationSegment:
    """ナレーションの区切り"""
    text: str
    output_file: str
    duration_seconds: Optional[float] = None


class ElevenLabsGenerator:
    """ElevenLabs APIを使用したナレーション生成"""

    def __init__(self):
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.voice_id = os.getenv("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM")  # デフォルト: Rachel

        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY が設定されていません")

    def generate(self, text: str, output_path: str) -> str:
        """テキストから音声を生成"""
        from elevenlabs import generate, save, set_api_key

        set_api_key(self.api_key)

        # テキストを整形
        text = self._preprocess_text(text)

        # 音声生成
        audio = generate(
            text=text,
            voice=self.voice_id,
            model="eleven_multilingual_v2"  # 日本語対応
        )

        # 保存
        save(audio, output_path)

        return output_path

    def _preprocess_text(self, text: str) -> str:
        """テキストを音声生成用に整形"""
        # Markdown記法を除去
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'`(.+?)`', r'\1', text)

        # 見出し記号を除去
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)

        # URLを除去
        text = re.sub(r'https?://\S+', '', text)

        # 箇条書き記号を整理
        text = re.sub(r'^[-•]\s+', '', text, flags=re.MULTILINE)

        # 複数の空行を1つに
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()


class VOICEVOXGenerator:
    """VOICEVOXを使用したナレーション生成（ローカル・無料）"""

    def __init__(self, speaker_id: int = 1):
        self.base_url = "http://localhost:50021"
        self.speaker_id = speaker_id

    def generate(self, text: str, output_path: str) -> str:
        """テキストから音声を生成"""
        import requests
        from pydub import AudioSegment

        # テキストを整形
        text = self._preprocess_text(text)

        # 音声クエリを作成
        query_response = requests.post(
            f"{self.base_url}/audio_query",
            params={"text": text, "speaker": self.speaker_id}
        )
        query_response.raise_for_status()
        query = query_response.json()

        # 音声を合成
        synthesis_response = requests.post(
            f"{self.base_url}/synthesis",
            params={"speaker": self.speaker_id},
            json=query
        )
        synthesis_response.raise_for_status()

        # WAVファイルとして保存
        wav_path = output_path.replace('.mp3', '.wav')
        with open(wav_path, 'wb') as f:
            f.write(synthesis_response.content)

        # MP3に変換
        audio = AudioSegment.from_wav(wav_path)
        audio.export(output_path, format='mp3')

        # WAVファイルを削除
        os.remove(wav_path)

        return output_path

    def _preprocess_text(self, text: str) -> str:
        """テキストを音声生成用に整形"""
        # ElevenLabsと同じ前処理
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'`(.+?)`', r'\1', text)
        text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'https?://\S+', '', text)
        text = re.sub(r'^[-•]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()


def split_text_into_segments(text: str, max_chars: int = 2000) -> List[str]:
    """テキストを適切な長さのセグメントに分割"""
    segments = []
    paragraphs = text.split('\n\n')

    current_segment = ""
    for para in paragraphs:
        if len(current_segment) + len(para) + 2 <= max_chars:
            current_segment += para + "\n\n"
        else:
            if current_segment:
                segments.append(current_segment.strip())
            current_segment = para + "\n\n"

    if current_segment:
        segments.append(current_segment.strip())

    return segments


def generate_narration(
    text: str,
    output_dir: str,
    use_elevenlabs: bool = True,
    prefix: str = "narration"
) -> List[NarrationSegment]:
    """ナレーションを生成"""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # テキストを分割
    segments_text = split_text_into_segments(text)

    # ジェネレーターを選択
    if use_elevenlabs:
        generator = ElevenLabsGenerator()
    else:
        generator = VOICEVOXGenerator()

    segments = []
    for i, segment_text in enumerate(segments_text):
        output_file = output_path / f"{prefix}_{i:03d}.mp3"

        print(f"セグメント {i+1}/{len(segments_text)} を生成中...")

        try:
            generator.generate(segment_text, str(output_file))

            segments.append(NarrationSegment(
                text=segment_text,
                output_file=str(output_file)
            ))

            # API制限を考慮して少し待機
            time.sleep(1)

        except Exception as e:
            print(f"エラー: セグメント {i+1} の生成に失敗: {e}")
            continue

    return segments


def concatenate_audio_files(audio_files: List[str], output_file: str) -> str:
    """複数の音声ファイルを結合"""
    from pydub import AudioSegment

    combined = AudioSegment.empty()

    for audio_file in audio_files:
        audio = AudioSegment.from_mp3(audio_file)
        # セグメント間に短い無音を追加
        silence = AudioSegment.silent(duration=500)  # 0.5秒
        combined += audio + silence

    combined.export(output_file, format='mp3')

    return output_file


if __name__ == "__main__":
    import sys

    # テスト用
    test_text = """
    こんにちは、今日はAIについてお話しします。

    AIは私たちの生活を大きく変えています。
    特にChatGPTの登場以降、その変化は加速しています。

    今日は、AIを活用して生産性を上げる方法を3つ紹介します。
    """

    output_dir = "./temp/narration_test"

    # ElevenLabsを使用する場合
    # segments = generate_narration(test_text, output_dir, use_elevenlabs=True)

    # VOICEVOXを使用する場合（ローカルでVOICEVOXが起動している必要あり）
    # segments = generate_narration(test_text, output_dir, use_elevenlabs=False)

    print("テスト完了")
