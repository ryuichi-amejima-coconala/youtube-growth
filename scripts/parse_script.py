"""
台本解析モジュール
Markdownの台本ファイルを解析し、構造化されたデータに変換
"""

import re
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


@dataclass
class Section:
    """台本のセクション"""
    title: str
    content: str
    timestamp_start: Optional[str] = None
    timestamp_end: Optional[str] = None
    subsections: List['Section'] = field(default_factory=list)


@dataclass
class SEOData:
    """SEO関連データ"""
    title_options: List[str] = field(default_factory=list)
    description: str = ""
    tags: List[str] = field(default_factory=list)
    thumbnail_ideas: List[str] = field(default_factory=list)


@dataclass
class Script:
    """解析された台本"""
    title: str
    duration_minutes: int
    target_audience: str
    sections: List[Section]
    seo_data: SEOData
    raw_content: str


def parse_timestamp(text: str) -> tuple:
    """タイムスタンプを解析（例: 0:00-1:30）"""
    match = re.search(r'(\d+:\d+)-(\d+:\d+)', text)
    if match:
        return match.group(1), match.group(2)
    return None, None


def extract_duration(content: str) -> int:
    """動画時間を抽出（分単位）"""
    # "動画時間: 12分" のようなパターンを探す
    match = re.search(r'動画時間[：:]\s*(\d+)', content)
    if match:
        return int(match.group(1))

    # "60秒" パターン（ショート動画）
    match = re.search(r'(\d+)秒', content)
    if match:
        return 1  # 60秒以下は1分として扱う

    return 10  # デフォルト


def extract_target(content: str) -> str:
    """ターゲット視聴者を抽出"""
    match = re.search(r'ターゲット[：:]\s*(.+?)(?:\n|$)', content)
    if match:
        return match.group(1).strip()
    return "一般視聴者"


def parse_sections(content: str) -> List[Section]:
    """セクションを解析"""
    sections = []

    # ## で始まるセクションを分割
    h2_pattern = r'^## (.+?)$'
    h3_pattern = r'^### (.+?)$'

    lines = content.split('\n')
    current_section = None
    current_subsection = None
    current_content = []

    for line in lines:
        h2_match = re.match(h2_pattern, line)
        h3_match = re.match(h3_pattern, line)

        if h2_match:
            # 前のセクションを保存
            if current_subsection:
                current_subsection.content = '\n'.join(current_content)
                current_content = []
            if current_section:
                if current_subsection:
                    current_section.subsections.append(current_subsection)
                    current_subsection = None
                sections.append(current_section)

            # 新しいセクション開始
            title = h2_match.group(1)
            start, end = parse_timestamp(title)
            current_section = Section(
                title=re.sub(r'[\d:]+[-–][\d:]+', '', title).strip(),
                content="",
                timestamp_start=start,
                timestamp_end=end
            )
            current_content = []

        elif h3_match and current_section:
            # 前のサブセクションを保存
            if current_subsection:
                current_subsection.content = '\n'.join(current_content)
                current_section.subsections.append(current_subsection)

            # 新しいサブセクション開始
            title = h3_match.group(1)
            start, end = parse_timestamp(title)
            current_subsection = Section(
                title=re.sub(r'[\d:]+[-–][\d:]+', '', title).strip(),
                content="",
                timestamp_start=start,
                timestamp_end=end
            )
            current_content = []

        else:
            current_content.append(line)

    # 最後のセクションを保存
    if current_subsection:
        current_subsection.content = '\n'.join(current_content)
        if current_section:
            current_section.subsections.append(current_subsection)
    if current_section:
        if not current_section.subsections:
            current_section.content = '\n'.join(current_content)
        sections.append(current_section)

    return sections


def extract_seo_data(content: str) -> SEOData:
    """SEOデータを抽出"""
    seo = SEOData()

    # タイトル案を抽出
    title_section = re.search(r'\*\*タイトル案\*\*[：:]?\s*\n((?:[-•]\s*.+\n?)+)', content)
    if title_section:
        titles = re.findall(r'[-•]\s*(.+)', title_section.group(1))
        seo.title_options = [t.strip() for t in titles]

    # 説明文を抽出
    desc_match = re.search(r'\*\*説明文[^*]*\*\*[：:]?\s*\n(.+?)(?:\n\n|\*\*)', content, re.DOTALL)
    if desc_match:
        seo.description = desc_match.group(1).strip()

    # タグを抽出
    tags_match = re.search(r'\*\*タグ\*\*[：:]?\s*\n?(.+?)(?:\n\n|\*\*|$)', content)
    if tags_match:
        tags_text = tags_match.group(1)
        seo.tags = [t.strip() for t in re.split(r'[,、]', tags_text) if t.strip()]

    # サムネイル案を抽出
    thumb_section = re.search(r'\*\*サムネイル案\*\*[：:]?\s*\n((?:[-•]\s*.+\n?)+)', content)
    if thumb_section:
        thumbs = re.findall(r'[-•]\s*(.+)', thumb_section.group(1))
        seo.thumbnail_ideas = [t.strip() for t in thumbs]

    return seo


def extract_narration_text(sections: List[Section]) -> str:
    """ナレーション用のテキストを抽出"""
    narration_parts = []

    for section in sections:
        # SEOセクションはスキップ
        if 'SEO' in section.title or 'メタデータ' in section.title:
            continue

        # コンテンツからナレーション部分を抽出
        content = section.content
        for subsection in section.subsections:
            content += "\n" + subsection.content

        # コードブロックを除去
        content = re.sub(r'```[\s\S]*?```', '', content)

        # 表を除去
        content = re.sub(r'\|.+\|', '', content)

        # Markdown記法を除去
        content = re.sub(r'\*\*(.+?)\*\*', r'\1', content)
        content = re.sub(r'\*(.+?)\*', r'\1', content)
        content = re.sub(r'`(.+?)`', r'\1', content)

        # 見出しを除去
        content = re.sub(r'^#+\s+', '', content, flags=re.MULTILINE)

        # 空行を整理
        content = re.sub(r'\n{3,}', '\n\n', content)

        if content.strip():
            narration_parts.append(content.strip())

    return '\n\n'.join(narration_parts)


def parse_script_file(file_path: str) -> Script:
    """台本ファイルを解析"""
    path = Path(file_path)

    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # タイトルを抽出（最初の # で始まる行）
    title_match = re.search(r'^# (.+)$', content, re.MULTILINE)
    title = title_match.group(1) if title_match else path.stem

    # 各要素を解析
    duration = extract_duration(content)
    target = extract_target(content)
    sections = parse_sections(content)
    seo_data = extract_seo_data(content)

    return Script(
        title=title,
        duration_minutes=duration,
        target_audience=target,
        sections=sections,
        seo_data=seo_data,
        raw_content=content
    )


def get_narration_text(script: Script) -> str:
    """台本からナレーションテキストを取得"""
    return extract_narration_text(script.sections)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python parse_script.py <script_file>")
        sys.exit(1)

    script = parse_script_file(sys.argv[1])

    print(f"タイトル: {script.title}")
    print(f"動画時間: {script.duration_minutes}分")
    print(f"ターゲット: {script.target_audience}")
    print(f"セクション数: {len(script.sections)}")
    print(f"\nSEOタイトル案:")
    for title in script.seo_data.title_options:
        print(f"  - {title}")
    print(f"\nナレーションテキスト（最初の500文字）:")
    narration = get_narration_text(script)
    print(narration[:500] + "..." if len(narration) > 500 else narration)
