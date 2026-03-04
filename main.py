#!/usr/bin/env python3
"""
YouTube動画自動生成パイプライン
台本 → ナレーション → 画像 → 動画合成 → 字幕 → YouTube投稿

使用方法:
    python main.py <台本ファイル.md> [オプション]

例:
    python main.py ~/scripts/01_chatgpt_7tips.md --output ./output
    python main.py ~/scripts/01_chatgpt_7tips.md --upload --privacy public
"""

import os
import sys
import json
import shutil
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional

# スクリプトディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

from parse_script import parse_script_file, get_narration_text, Script
from generate_narration import generate_narration, concatenate_audio_files
from generate_visuals import generate_visuals_for_script
from compose_video import compose_video
from add_subtitles import add_subtitles_to_video
from upload_youtube import upload_to_youtube, VideoMetadata, YouTubeUploader

from dotenv import load_dotenv

load_dotenv()


class VideoPipeline:
    """動画生成パイプライン"""

    def __init__(
        self,
        output_dir: str = "./output",
        temp_dir: str = "./temp",
        use_elevenlabs: bool = True,
        image_generator: str = "gemini",  # "gemini", "openai", "replicate"
        whisper_model: str = "base",
        num_images: int = 10
    ):
        self.output_dir = Path(output_dir)
        self.temp_dir = Path(temp_dir)
        self.use_elevenlabs = use_elevenlabs
        self.image_generator = image_generator
        self.whisper_model = whisper_model
        self.num_images = num_images

        # ディレクトリを作成
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def process_script(
        self,
        script_path: str,
        upload: bool = False,
        privacy: str = "private",
        cleanup: bool = True
    ) -> dict:
        """台本から動画を生成"""

        result = {
            "success": False,
            "script_path": script_path,
            "video_path": None,
            "video_id": None,
            "error": None
        }

        try:
            # 1. 台本を解析
            print("=" * 60)
            print("ステップ 1/6: 台本を解析中...")
            print("=" * 60)
            script = parse_script_file(script_path)
            print(f"タイトル: {script.title}")
            print(f"動画時間: {script.duration_minutes}分")

            # 一時ディレクトリを作成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            work_dir = self.temp_dir / f"work_{timestamp}"
            work_dir.mkdir(parents=True, exist_ok=True)

            # 2. ナレーションを生成
            print()
            print("=" * 60)
            print("ステップ 2/6: ナレーションを生成中...")
            print("=" * 60)
            narration_text = get_narration_text(script)
            narration_dir = work_dir / "narration"

            narration_segments = generate_narration(
                narration_text,
                str(narration_dir),
                use_elevenlabs=self.use_elevenlabs
            )

            if not narration_segments:
                raise Exception("ナレーション生成に失敗しました")

            # ナレーションを結合
            audio_files = [s.output_file for s in narration_segments]
            combined_audio = work_dir / "narration_combined.mp3"
            concatenate_audio_files(audio_files, str(combined_audio))
            print(f"ナレーション生成完了: {len(narration_segments)}セグメント")

            # 3. 画像を生成
            print()
            print("=" * 60)
            print("ステップ 3/6: 画像を生成中...")
            print("=" * 60)
            visuals_dir = work_dir / "visuals"

            visual_assets = generate_visuals_for_script(
                script.raw_content,
                str(visuals_dir),
                num_images=self.num_images,
                generator_type=self.image_generator
            )

            if not visual_assets:
                raise Exception("画像生成に失敗しました")

            visual_paths = [v.file_path for v in visual_assets]
            print(f"画像生成完了: {len(visual_assets)}枚")

            # 4. 動画を合成
            print()
            print("=" * 60)
            print("ステップ 4/6: 動画を合成中...")
            print("=" * 60)
            composed_video = work_dir / "composed.mp4"

            compose_video(
                audio_segments=audio_files,
                visual_assets=visual_paths,
                output_path=str(composed_video),
                temp_dir=str(work_dir / "compose_temp")
            )
            print("動画合成完了")

            # 5. 字幕を追加
            print()
            print("=" * 60)
            print("ステップ 5/6: 字幕を追加中...")
            print("=" * 60)
            final_video = self.output_dir / f"{Path(script_path).stem}_{timestamp}.mp4"

            add_subtitles_to_video(
                video_path=str(composed_video),
                audio_path=str(combined_audio),
                output_path=str(final_video),
                temp_dir=str(work_dir / "subtitle_temp"),
                whisper_model=self.whisper_model
            )

            result["video_path"] = str(final_video)
            print(f"動画生成完了: {final_video}")

            # 6. YouTubeにアップロード（オプション）
            if upload:
                print()
                print("=" * 60)
                print("ステップ 6/6: YouTubeにアップロード中...")
                print("=" * 60)

                # タイトルを選択（SEOタイトル案があれば最初のものを使用）
                title = script.seo_data.title_options[0] if script.seo_data.title_options else script.title

                video_id = upload_to_youtube(
                    video_path=str(final_video),
                    title=title,
                    description=script.seo_data.description or f"{script.title}\n\n#AI #Tips",
                    tags=script.seo_data.tags or ["AI", "Tips", "自動化"],
                    privacy=privacy
                )

                if video_id:
                    result["video_id"] = video_id
                    print(f"アップロード完了: https://www.youtube.com/watch?v={video_id}")
                else:
                    print("警告: アップロードに失敗しました")
            else:
                print()
                print("ステップ 6/6: スキップ（--upload オプションなし）")

            # 一時ファイルをクリーンアップ
            if cleanup:
                print()
                print("一時ファイルをクリーンアップ中...")
                shutil.rmtree(work_dir, ignore_errors=True)

            result["success"] = True

        except Exception as e:
            result["error"] = str(e)
            print(f"エラー: {e}")
            import traceback
            traceback.print_exc()

        return result

    def process_batch(
        self,
        script_paths: list,
        upload: bool = False,
        privacy: str = "private"
    ) -> list:
        """複数の台本を一括処理"""

        results = []
        total = len(script_paths)

        for i, script_path in enumerate(script_paths):
            print()
            print("#" * 70)
            print(f"# 動画 {i+1}/{total}: {Path(script_path).name}")
            print("#" * 70)

            result = self.process_script(script_path, upload, privacy)
            results.append(result)

            # 成功/失敗をサマリー
            if result["success"]:
                print(f"✅ 成功: {result['video_path']}")
            else:
                print(f"❌ 失敗: {result['error']}")

        # 最終サマリー
        print()
        print("=" * 70)
        print("処理完了サマリー")
        print("=" * 70)
        success_count = sum(1 for r in results if r["success"])
        print(f"成功: {success_count}/{total}")
        print(f"失敗: {total - success_count}/{total}")

        return results


def main():
    parser = argparse.ArgumentParser(
        description="YouTube動画自動生成パイプライン",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
    # 単一の台本から動画を生成
    python main.py script.md

    # 複数の台本を一括処理
    python main.py scripts/*.md

    # YouTubeにアップロード（非公開）
    python main.py script.md --upload

    # YouTubeに公開
    python main.py script.md --upload --privacy public

    # VOICEVOXを使用（ElevenLabsの代わり）
    python main.py script.md --voicevox

    # 画像生成エンジンを選択
    python main.py script.md --image-gen gemini     # デフォルト
    python main.py script.md --image-gen openai     # DALL-E 3
    python main.py script.md --image-gen replicate  # SDXL

環境変数:
    GEMINI_API_KEY        - Google Gemini APIキー（画像生成デフォルト）
    ELEVENLABS_API_KEY    - ElevenLabs APIキー
    OPENAI_API_KEY        - OpenAI APIキー（DALL-E使用時）
    REPLICATE_API_TOKEN   - Replicate APIトークン（SDXL使用時）
        """
    )

    parser.add_argument(
        "scripts",
        nargs="+",
        help="台本ファイル（Markdown）"
    )
    parser.add_argument(
        "--output", "-o",
        default="./output",
        help="出力ディレクトリ（デフォルト: ./output）"
    )
    parser.add_argument(
        "--temp", "-t",
        default="./temp",
        help="一時ディレクトリ（デフォルト: ./temp）"
    )
    parser.add_argument(
        "--upload", "-u",
        action="store_true",
        help="YouTubeにアップロード"
    )
    parser.add_argument(
        "--privacy", "-p",
        choices=["private", "public", "unlisted"],
        default="private",
        help="公開設定（デフォルト: private）"
    )
    parser.add_argument(
        "--voicevox",
        action="store_true",
        help="VOICEVOXを使用（ElevenLabsの代わり）"
    )
    parser.add_argument(
        "--image-gen",
        choices=["gemini", "openai", "replicate"],
        default="gemini",
        help="画像生成エンジン（デフォルト: gemini）"
    )
    parser.add_argument(
        "--images", "-i",
        type=int,
        default=10,
        help="生成する画像数（デフォルト: 10）"
    )
    parser.add_argument(
        "--whisper-model", "-w",
        choices=["tiny", "base", "small", "medium", "large"],
        default="base",
        help="Whisperモデル（デフォルト: base）"
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="一時ファイルを削除しない"
    )

    args = parser.parse_args()

    # パイプラインを初期化
    pipeline = VideoPipeline(
        output_dir=args.output,
        temp_dir=args.temp,
        use_elevenlabs=not args.voicevox,
        image_generator=args.image_gen,
        whisper_model=args.whisper_model,
        num_images=args.images
    )

    # 台本を処理
    if len(args.scripts) == 1:
        result = pipeline.process_script(
            args.scripts[0],
            upload=args.upload,
            privacy=args.privacy,
            cleanup=not args.no_cleanup
        )
        sys.exit(0 if result["success"] else 1)
    else:
        results = pipeline.process_batch(
            args.scripts,
            upload=args.upload,
            privacy=args.privacy
        )
        success_count = sum(1 for r in results if r["success"])
        sys.exit(0 if success_count == len(results) else 1)


if __name__ == "__main__":
    main()
