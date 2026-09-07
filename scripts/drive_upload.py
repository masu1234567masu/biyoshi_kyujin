"""
Google Drive 自動アップロード用スクリプト。
サービスアカウント認証で指定フォルダに画像をアップロードし、
「リンクを知っている全員が閲覧可」に共有設定した上で、
Metricool の media フィールドに渡せる公開URLを返す。

使い方:
  from drive_upload import upload_file, load_config
  config = load_config()
  url = upload_file("assets/posts/post7/post7_final_slide1.jpg", config)
"""

import json
import os

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config(config_path=None):
    config_path = config_path or os.path.join(REPO_ROOT, "config", "drive_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_drive_service(config):
    key_path = os.path.join(REPO_ROOT, config["service_account_key_path"])
    creds = service_account.Credentials.from_service_account_file(key_path, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def upload_file(local_path, config, service=None):
    """1ファイルをDriveの指定フォルダにアップロードし、公開閲覧URLを返す。"""
    service = service or get_drive_service(config)

    file_metadata = {
        "name": os.path.basename(local_path),
        "parents": [config["upload_folder_id"]],
    }
    media = MediaFileUpload(local_path, resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields="id").execute()
    file_id = file["id"]

    # リンクを知っている全員が閲覧可能に設定(Metricoolが取得できるようにするため)
    service.permissions().create(
        fileId=file_id,
        body={"type": "anyone", "role": "reader"},
        fields="id",
    ).execute()

    # Metricool 等の外部サービスが直接ダウンロードできる形式のURL
    return f"https://drive.google.com/uc?export=download&id={file_id}"


def upload_files(local_paths, config=None):
    """複数ファイルをまとめてアップロードし、URLのリストを返す。"""
    config = config or load_config()
    service = get_drive_service(config)
    return [upload_file(p, config, service=service) for p in local_paths]


if __name__ == "__main__":
    import sys

    cfg = load_config()
    urls = upload_files(sys.argv[1:], cfg)
    for u in urls:
        print(u)
