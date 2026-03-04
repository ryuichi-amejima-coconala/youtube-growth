"""
YouTube投稿モジュール
YouTube Data API v3を使用して動画をアップロード
"""

import os
import pickle
import json
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from dotenv import load_dotenv

load_dotenv()

# YouTube Data API v3のスコープ
SCOPES = ['https://www.googleapis.com/auth/youtube.upload',
          'https://www.googleapis.com/auth/youtube']


@dataclass
class VideoMetadata:
    """動画メタデータ"""
    title: str
    description: str
    tags: List[str]
    category_id: str = "28"  # Science & Technology
    privacy_status: str = "private"  # private, public, unlisted
    made_for_kids: bool = False
    language: str = "ja"
    thumbnail_path: Optional[str] = None


class YouTubeUploader:
    """YouTube動画アップローダー"""

    def __init__(self, credentials_path: str = None, token_path: str = None):
        self.credentials_path = credentials_path or os.getenv(
            "YOUTUBE_CREDENTIALS_PATH",
            str(Path.home() / ".claude/youtube-automation/credentials.json")
        )
        self.token_path = token_path or os.getenv(
            "YOUTUBE_TOKEN_PATH",
            str(Path.home() / ".claude/youtube-automation/token.pickle")
        )
        self.service = None

    def authenticate(self) -> bool:
        """YouTube APIの認証を行う"""
        creds = None

        # 保存されたトークンを確認
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                creds = pickle.load(token)

        # トークンがないか期限切れの場合
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(self.credentials_path):
                    print(f"エラー: 認証情報ファイルが見つかりません: {self.credentials_path}")
                    print("Google Cloud ConsoleからOAuth 2.0クライアントIDをダウンロードしてください")
                    return False

                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=8080)

            # トークンを保存
            with open(self.token_path, 'wb') as token:
                pickle.dump(creds, token)

        self.service = build('youtube', 'v3', credentials=creds)
        return True

    def upload_video(
        self,
        video_path: str,
        metadata: VideoMetadata,
        notify_subscribers: bool = False
    ) -> Optional[str]:
        """動画をアップロード"""

        if not self.service:
            if not self.authenticate():
                return None

        if not os.path.exists(video_path):
            print(f"エラー: 動画ファイルが見つかりません: {video_path}")
            return None

        # リクエストボディを作成
        body = {
            'snippet': {
                'title': metadata.title[:100],  # タイトルは100文字以内
                'description': metadata.description[:5000],  # 説明は5000文字以内
                'tags': metadata.tags[:500],  # タグは合計500文字以内
                'categoryId': metadata.category_id,
                'defaultLanguage': metadata.language,
                'defaultAudioLanguage': metadata.language
            },
            'status': {
                'privacyStatus': metadata.privacy_status,
                'selfDeclaredMadeForKids': metadata.made_for_kids,
                'notifySubscribers': notify_subscribers
            }
        }

        # メディアファイルを準備
        media = MediaFileUpload(
            video_path,
            mimetype='video/mp4',
            resumable=True,
            chunksize=1024*1024  # 1MB chunks
        )

        print(f"動画をアップロード中: {metadata.title}")

        try:
            # アップロードリクエストを実行
            request = self.service.videos().insert(
                part='snippet,status',
                body=body,
                media_body=media
            )

            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    print(f"アップロード進捗: {progress}%")

            video_id = response['id']
            print(f"アップロード完了! Video ID: {video_id}")
            print(f"URL: https://www.youtube.com/watch?v={video_id}")

            # サムネイルをアップロード
            if metadata.thumbnail_path and os.path.exists(metadata.thumbnail_path):
                self.upload_thumbnail(video_id, metadata.thumbnail_path)

            return video_id

        except Exception as e:
            print(f"アップロードエラー: {e}")
            return None

    def upload_thumbnail(self, video_id: str, thumbnail_path: str) -> bool:
        """サムネイルをアップロード"""

        if not self.service:
            return False

        try:
            media = MediaFileUpload(thumbnail_path, mimetype='image/jpeg')

            self.service.thumbnails().set(
                videoId=video_id,
                media_body=media
            ).execute()

            print(f"サムネイルをアップロードしました: {thumbnail_path}")
            return True

        except Exception as e:
            print(f"サムネイルアップロードエラー: {e}")
            return False

    def update_video_metadata(
        self,
        video_id: str,
        metadata: VideoMetadata
    ) -> bool:
        """動画のメタデータを更新"""

        if not self.service:
            if not self.authenticate():
                return False

        body = {
            'id': video_id,
            'snippet': {
                'title': metadata.title[:100],
                'description': metadata.description[:5000],
                'tags': metadata.tags[:500],
                'categoryId': metadata.category_id
            }
        }

        try:
            self.service.videos().update(
                part='snippet',
                body=body
            ).execute()

            print(f"メタデータを更新しました: {video_id}")
            return True

        except Exception as e:
            print(f"メタデータ更新エラー: {e}")
            return False

    def set_video_privacy(
        self,
        video_id: str,
        privacy_status: str = "public"
    ) -> bool:
        """動画の公開設定を変更"""

        if not self.service:
            if not self.authenticate():
                return False

        body = {
            'id': video_id,
            'status': {
                'privacyStatus': privacy_status
            }
        }

        try:
            self.service.videos().update(
                part='status',
                body=body
            ).execute()

            print(f"公開設定を変更しました: {video_id} -> {privacy_status}")
            return True

        except Exception as e:
            print(f"公開設定変更エラー: {e}")
            return False


def create_metadata_from_script(
    title: str,
    description: str,
    tags: List[str],
    thumbnail_path: str = None,
    privacy: str = "private"
) -> VideoMetadata:
    """台本データからメタデータを作成"""
    return VideoMetadata(
        title=title,
        description=description,
        tags=tags,
        privacy_status=privacy,
        thumbnail_path=thumbnail_path
    )


def upload_to_youtube(
    video_path: str,
    title: str,
    description: str,
    tags: List[str],
    thumbnail_path: str = None,
    privacy: str = "private"
) -> Optional[str]:
    """動画をYouTubeにアップロード（簡易関数）"""

    metadata = create_metadata_from_script(
        title=title,
        description=description,
        tags=tags,
        thumbnail_path=thumbnail_path,
        privacy=privacy
    )

    uploader = YouTubeUploader()
    return uploader.upload_video(video_path, metadata)


if __name__ == "__main__":
    print("YouTube投稿モジュール")
    print()
    print("使用前の準備:")
    print("1. Google Cloud Consoleでプロジェクトを作成")
    print("2. YouTube Data API v3を有効化")
    print("3. OAuth 2.0クライアントIDを作成（デスクトップアプリ）")
    print("4. credentials.jsonをダウンロード")
    print("5. ~/.claude/youtube-automation/credentials.json に配置")
    print()
    print("使用例:")
    print("  from upload_youtube import upload_to_youtube")
    print("  video_id = upload_to_youtube(")
    print("      'video.mp4',")
    print("      'タイトル',")
    print("      '説明文',")
    print("      ['タグ1', 'タグ2']")
    print("  )")
