"""
Google Drive 自動アップロード用スクリプト。
増田さん本人のOAuth認証(secrets/drive_oauth_token.jsonのリフレッシュトークン)で
指定フォルダに画像をアップロードし、「リンクを知っている全員が閲覧可」に共有設定した上で、
Metricool の media フィールドに渡せる公開URLを返す。

サービスアカウントには個人Driveへの書き込み容量(ストレージクォータ)が無いため、
本人のアカウント権限を借りるOAuth方式を採用している(oauth_step1/2で認証済み)。

使い方:
  from drive_upload import upload_file, load_config
  config = load_config()
  url = upload_file("assets/posts/post7/post7_final_slide1.jpg", config)
"""

import json
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/drive"]
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config(config_path=None):
    config_path = config_path or os.path.join(REPO_ROOT, "config", "drive_config.json")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_drive_service(config):
    token_path = os.path.join(REPO_ROOT, "secrets", "drive_oauth_token.json")
    with open(token_path, "r", encoding="utf-8") as f:
        token = json.load(f)

    creds = Credentials(
        token=None,
        refresh_token=token["refresh_token"],
        client_id=token["client_id"],
        client_secret=token["client_secret"],
        token_uri=token["token_uri"],
        scopes=token["scopes"],
    )
    creds.refresh(Request())
    return build("drive", "v3", credentials=creds)


def upload_file(local_path, config, service=None):
    """1ファイルをDriveの指定フォルダにアップロードし、{id, url} を返す。"""
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
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    return {"id": file_id, "url": url}


def upload_files(local_paths, config=None):
    """複数ファイルをまとめてアップロードし、{id, url} のリストを返す。"""
    config = config or load_config()
    service = get_drive_service(config)
    return [upload_file(p, config, service=service) for p in local_paths]


def delete_file(file_id, config=None, service=None):
    """Driveから1ファイルを完全に削除する(ゴミ箱もスキップ)。Metricoolへの取り込みが
    完了した後(投稿作成時のレスポンスでstatic.metricool.comのURLに変換されていることを
    確認した後)に呼び出すことを想定している。"""
    config = config or load_config()
    service = service or get_drive_service(config)
    service.files().delete(fileId=file_id).execute()


def delete_files(file_ids, config=None):
    """複数ファイルをまとめてDriveから削除する。"""
    config = config or load_config()
    service = get_drive_service(config)
    for file_id in file_ids:
        delete_file(file_id, config, service=service)


if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 2 and sys.argv[1] == "delete":
        delete_files(sys.argv[2:])
        print(f"{len(sys.argv) - 2}件のファイルをDriveから削除しました")
    else:
        cfg = load_config()
        results = upload_files(sys.argv[1:], cfg)
        for r in results:
            print(f"{r['id']}\t{r['url']}")
