"""
画像・動画素材生成モジュール
Gemini (Imagen 3) / OpenAI (DALL-E 3) / Replicate (SDXL) を使用
"""

import os
import re
import time
import requests
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass
class VisualAsset:
    """生成された素材"""
    type: str  # "image" or "video"
    file_path: str
    prompt: str
    duration_seconds: Optional[float] = None


class GeminiImageGenerator:
    """Google Gemini (Imagen 3) を使用した画像生成"""

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY が設定されていません")

        from google import genai
        self.client = genai.Client(api_key=self.api_key)
        self.model_name = "imagen-3.0-generate-002"

    def generate(self, prompt: str, output_path: str, style: str = "cinematic") -> str:
        """画像を生成"""
        from google.genai import types

        # プロンプトを強化
        enhanced_prompt = self._enhance_prompt(prompt, style)

        result = self.client.models.generate_images(
            model=self.model_name,
            prompt=enhanced_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="16:9",  # YouTube向け
                safety_filter_level="BLOCK_MEDIUM_AND_ABOVE",
                person_generation="ALLOW_ADULT"
            )
        )

        # 画像を保存
        if result.generated_images and len(result.generated_images) > 0:
            image = result.generated_images[0]
            image.image.save(output_path)
            return output_path

        raise Exception("画像生成に失敗しました")

    def _enhance_prompt(self, prompt: str, style: str) -> str:
        """プロンプトを強化"""
        style_suffixes = {
            "cinematic": ", cinematic lighting, movie still, 8k, highly detailed, professional photography",
            "tech": ", modern technology, sleek design, blue accent lighting, futuristic, clean",
            "business": ", professional, corporate, clean background, modern office",
            "artistic": ", artistic, creative, vibrant colors, digital art"
        }
        suffix = style_suffixes.get(style, style_suffixes["cinematic"])
        return prompt + suffix


class ReplicateImageGenerator:
    """Replicate API (SDXL) を使用した画像生成"""

    def __init__(self):
        self.api_token = os.getenv("REPLICATE_API_TOKEN")
        if not self.api_token:
            raise ValueError("REPLICATE_API_TOKEN が設定されていません")

        import replicate
        self.client = replicate

    def generate(self, prompt: str, output_path: str, style: str = "cinematic") -> str:
        """画像を生成"""
        # プロンプトを英語化・強化
        enhanced_prompt = self._enhance_prompt(prompt, style)

        output = self.client.run(
            "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
            input={
                "prompt": enhanced_prompt,
                "negative_prompt": "low quality, blurry, distorted, deformed, ugly, bad anatomy",
                "width": 1920,
                "height": 1080,
                "num_outputs": 1
            }
        )

        # 画像をダウンロード
        if output and len(output) > 0:
            image_url = output[0]
            response = requests.get(image_url)
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return output_path

        raise Exception("画像生成に失敗しました")

    def _enhance_prompt(self, prompt: str, style: str) -> str:
        """プロンプトを強化"""
        style_suffixes = {
            "cinematic": ", cinematic lighting, movie still, 8k, highly detailed, professional photography",
            "tech": ", modern technology, sleek design, blue accent lighting, futuristic, clean",
            "business": ", professional, corporate, clean background, modern office",
            "artistic": ", artistic, creative, vibrant colors, digital art, trending on artstation"
        }
        suffix = style_suffixes.get(style, style_suffixes["cinematic"])
        return prompt + suffix


class OpenAIImageGenerator:
    """OpenAI DALL-E 3 を使用した画像生成"""

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY が設定されていません")

        from openai import OpenAI
        self.client = OpenAI(api_key=self.api_key)

    def generate(self, prompt: str, output_path: str, style: str = "vivid") -> str:
        """画像を生成"""
        response = self.client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1792x1024",
            quality="hd",
            style=style,  # "vivid" or "natural"
            n=1
        )

        image_url = response.data[0].url

        # 画像をダウンロード
        img_response = requests.get(image_url)
        with open(output_path, 'wb') as f:
            f.write(img_response.content)

        return output_path


class ReplicateVideoGenerator:
    """Replicate API を使用した動画生成"""

    def __init__(self):
        self.api_token = os.getenv("REPLICATE_API_TOKEN")
        if not self.api_token:
            raise ValueError("REPLICATE_API_TOKEN が設定されていません")

        import replicate
        self.client = replicate

    def generate_from_image(self, image_path: str, prompt: str, output_path: str) -> str:
        """画像から動画を生成"""
        # 画像をbase64エンコード
        import base64
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()

        # Stable Video Diffusion を使用
        output = self.client.run(
            "stability-ai/stable-video-diffusion:3f0457e4619daac51203dedb472816fd4af51f3149fa7a9e0b5ffcf1b8172438",
            input={
                "input_image": f"data:image/png;base64,{image_data}",
                "motion_bucket_id": 127,
                "fps": 24
            }
        )

        if output:
            # 動画をダウンロード
            response = requests.get(output)
            with open(output_path, 'wb') as f:
                f.write(response.content)
            return output_path

        raise Exception("動画生成に失敗しました")


def extract_visual_prompts_from_script(script_content: str) -> List[str]:
    """台本から画像生成用のプロンプトを抽出"""
    prompts = []

    # セクションタイトルからプロンプトを生成
    sections = re.findall(r'^##\s+(.+)$', script_content, re.MULTILINE)

    for section in sections:
        # SEO関連のセクションはスキップ
        if any(skip in section for skip in ['SEO', 'メタデータ', 'タイトル', 'タグ']):
            continue

        # タイムスタンプを除去
        clean_title = re.sub(r'[\d:]+[-–][\d:]+', '', section).strip()

        if clean_title:
            # 日本語のタイトルを画像プロンプトに変換
            prompt = generate_image_prompt(clean_title)
            prompts.append(prompt)

    return prompts


def generate_image_prompt(section_title: str) -> str:
    """セクションタイトルから画像プロンプトを生成"""
    # キーワードマッピング
    keyword_to_visual = {
        "オープニング": "Professional presenter in modern studio, welcoming gesture, bright lighting",
        "問題提起": "Person looking frustrated at computer, office setting, dramatic lighting",
        "メインコンテンツ": "Modern workspace with multiple screens showing data, tech aesthetic",
        "クロージング": "Happy person giving thumbs up, success celebration, warm lighting",
        "AI": "Futuristic AI interface, holographic display, blue glow, technology",
        "ChatGPT": "Chat interface on screen, AI assistant, modern UI, clean design",
        "プログラミング": "Code on multiple monitors, developer workspace, dark theme with syntax highlighting",
        "効率化": "Organized desk, productivity tools, clean workspace, time management",
        "収益": "Growth chart, money symbols, business success, green colors",
        "比較": "Side by side comparison, split screen, versus concept",
    }

    # タイトル内のキーワードをチェック
    for keyword, visual in keyword_to_visual.items():
        if keyword in section_title:
            return visual

    # デフォルト: 一般的なテック/ビジネス画像
    return f"Modern technology concept representing '{section_title}', professional, clean design, blue accent"


def generate_visuals_for_script(
    script_content: str,
    output_dir: str,
    num_images: int = 10,
    generator_type: str = "gemini"  # "gemini", "openai", "replicate"
) -> List[VisualAsset]:
    """台本に基づいて画像を生成"""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # プロンプトを抽出
    prompts = extract_visual_prompts_from_script(script_content)

    # 必要な数だけ選択（または繰り返し）
    while len(prompts) < num_images:
        prompts.extend(prompts)
    prompts = prompts[:num_images]

    # ジェネレーターを選択
    if generator_type == "gemini":
        generator = GeminiImageGenerator()
    elif generator_type == "openai":
        generator = OpenAIImageGenerator()
    else:
        generator = ReplicateImageGenerator()

    assets = []
    for i, prompt in enumerate(prompts):
        output_file = output_path / f"visual_{i:03d}.png"

        print(f"画像 {i+1}/{len(prompts)} を生成中...")
        print(f"  プロンプト: {prompt[:50]}...")

        try:
            generator.generate(prompt, str(output_file))

            assets.append(VisualAsset(
                type="image",
                file_path=str(output_file),
                prompt=prompt
            ))

            # API制限を考慮
            time.sleep(2)

        except Exception as e:
            print(f"エラー: 画像 {i+1} の生成に失敗: {e}")
            continue

    return assets


def add_ken_burns_effect(image_path: str, output_path: str, duration: float = 5.0) -> str:
    """Ken Burnsエフェクト（ズーム・パン）を追加して動画化"""
    import subprocess

    # FFmpegでKen Burnsエフェクトを適用
    # ゆっくりズームイン
    cmd = [
        'ffmpeg', '-y',
        '-loop', '1',
        '-i', image_path,
        '-vf', f"scale=8000:-1,zoompan=z='min(zoom+0.0015,1.5)':d={int(duration*30)}:s=1920x1080",
        '-c:v', 'libx264',
        '-t', str(duration),
        '-pix_fmt', 'yuv420p',
        output_path
    ]

    subprocess.run(cmd, check=True, capture_output=True)

    return output_path


if __name__ == "__main__":
    # テスト
    test_content = """
    ## オープニング 0:00-0:30
    今日はAIについて解説します。

    ## メインコンテンツ 0:30-8:00
    AIの活用方法を紹介します。

    ## クロージング 8:00-10:00
    まとめです。
    """

    prompts = extract_visual_prompts_from_script(test_content)
    print("抽出されたプロンプト:")
    for p in prompts:
        print(f"  - {p}")
