# YouTube Growth - 完全自動化パイプライン

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

台本生成から動画作成・YouTube投稿まで、全て自動化するシステム。

## 特徴

- **台本自動生成** - Claude Code Skillで企画から台本まで自動作成
- **AI音声生成** - ElevenLabs / VOICEVOX でナレーション生成
- **AI画像生成** - DALL-E 3 / SDXL で各シーンの画像を生成
- **自動編集** - Ken Burnsエフェクト、BGM合成
- **自動字幕** - Whisperで文字起こし、スタイル付き字幕
- **自動投稿** - YouTube Data API で直接アップロード

## コスト目安

| 動画タイプ | 時間 | コスト |
|-----------|------|--------|
| Shorts | 60秒 | 約$0.20（30円） |
| 標準 | 10分 | 約$1.10（160円） |
| 長め | 20分 | 約$2.00（300円） |

※ VOICEVOX（無料）使用でさらに削減可能

## アーキテクチャ

```
┌─────────────────────────────────────────────────────────────────┐
│                    メインオーケストレーター                      │
│                    (main.py)                                    │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  1. 台本解析   │    │  2. 音声生成   │    │  3. 素材生成   │
│  parse_script │    │  generate_    │    │  generate_    │
│               │    │  narration    │    │  visuals      │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                    ┌───────────────┐
                    │  4. 動画合成   │
                    │  compose_     │
                    │  video        │
                    └───────────────┘
                              │
                              ▼
                    ┌───────────────┐
                    │  5. 字幕追加   │
                    │  add_         │
                    │  subtitles    │
                    └───────────────┘
                              │
                              ▼
                    ┌───────────────┐
                    │  6. YouTube   │
                    │  投稿          │
                    │  upload       │
                    └───────────────┘
```

## セットアップ

### 1. クローン

```bash
git clone https://github.com/ryuichi-amejima-coconala/youtube-growth.git
cd youtube-growth
```

### 2. システム要件

```bash
# FFmpegのインストール（必須）
brew install ffmpeg  # macOS
# sudo apt install ffmpeg  # Ubuntu
```

### 3. Python環境

```bash
pip install -r requirements.txt
```

### 4. 環境変数の設定

```bash
cp .env.example .env
# .envファイルを編集してAPIキーを設定
```

| 環境変数 | サービス | 取得先 |
|---------|---------|--------|
| `ELEVENLABS_API_KEY` | ナレーション | https://elevenlabs.io |
| `OPENAI_API_KEY` | 画像生成 | https://platform.openai.com |
| `REPLICATE_API_TOKEN` | 画像生成（代替） | https://replicate.com |

### 5. YouTube API認証（投稿する場合）

1. [Google Cloud Console](https://console.cloud.google.com) でプロジェクト作成
2. YouTube Data API v3 を有効化
3. OAuth 2.0 クライアントID作成（デスクトップアプリ）
4. `credentials.json` をダウンロードしてリポジトリ直下に配置

## 使い方

### 基本的な使い方

```bash
# 単一の台本から動画生成
python main.py scripts-example/01_chatgpt_7tips.md

# 複数の台本を一括処理
python main.py scripts-example/*.md
```

### YouTubeにアップロード

```bash
# 非公開でアップロード
python main.py script.md --upload

# 公開でアップロード
python main.py script.md --upload --privacy public
```

### 無料で試す（VOICEVOX使用）

```bash
# 1. VOICEVOXをダウンロード: https://voicevox.hiroshiba.jp
# 2. VOICEVOXを起動
# 3. 実行
python main.py script.md --voicevox
```

### オプション一覧

```bash
python main.py --help

# 主なオプション:
#   --output, -o     出力ディレクトリ（デフォルト: ./output）
#   --upload, -u     YouTubeにアップロード
#   --privacy, -p    公開設定（private/public/unlisted）
#   --voicevox       VOICEVOXを使用（ElevenLabsの代わり）
#   --replicate      Replicateを使用（OpenAIの代わり）
#   --images, -i     生成する画像数（デフォルト: 10）
#   --whisper-model  Whisperモデル（tiny/base/small/medium/large）
```

## Claude Code Skill

`SKILL.md` をClaude Codeのスキルとして登録すると、台本生成も自動化できます。

```bash
# スキルをインストール
cp SKILL.md ~/.claude/skills/youtube-growth/SKILL.md
```

スキルの機能:
1. **チャンネル戦略** - ニッチ分析、差別化戦略
2. **動画企画** - バイラルアイデア生成
3. **タイトル・サムネイル** - クリック率最適化
4. **台本作成** - 視聴維持率を高める構成
5. **SEO最適化** - 検索上位表示
6. **コミュニティ構築** - 視聴者エンゲージメント
7. **収益化** - マネタイズ戦略

## ディレクトリ構成

```
youtube-growth/
├── README.md
├── SKILL.md               # Claude Code用スキル
├── main.py                # メインオーケストレーター
├── requirements.txt       # Python依存関係
├── .env.example          # 環境変数テンプレート
├── scripts/
│   ├── parse_script.py    # 台本解析
│   ├── generate_narration.py  # 音声生成
│   ├── generate_visuals.py    # 画像/動画生成
│   ├── compose_video.py   # 動画合成
│   ├── add_subtitles.py   # 字幕追加
│   └── upload_youtube.py  # YouTube投稿
└── scripts-example/       # 台本サンプル
```

## 注意事項

- APIの利用料金に注意してください
- YouTube APIには1日の投稿上限があります
- 長い動画は処理時間がかかります
- 生成された動画は必ず確認してから公開してください

## License

MIT License
