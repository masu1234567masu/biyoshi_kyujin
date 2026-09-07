"""
OAuthの認証コードをトークンに交換する(2回目のステップ)。
使い方: python3 oauth_step2_exchange_code.py "http://localhost/?state=...&code=...&scope=..."
交換できたリフレッシュトークン等を secrets/drive_oauth_token.json に保存する。
"""
import json
import os
import sys

from google_auth_oauthlib.flow import Flow

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(REPO_ROOT, "secrets", ".oauth_pkce_state.json")
TOKEN_PATH = os.path.join(REPO_ROOT, "secrets", "drive_oauth_token.json")

redirect_response = sys.argv[1]

with open(STATE_PATH, "r", encoding="utf-8") as f:
    pkce_state = json.load(f)

flow = Flow.from_client_secrets_file(
    os.path.join(REPO_ROOT, "secrets", "oauth_client_secret.json"),
    scopes=["https://www.googleapis.com/auth/drive"],
    redirect_uri="http://localhost",
)
flow.code_verifier = pkce_state["code_verifier"]
flow.fetch_token(authorization_response=redirect_response)

creds = flow.credentials
with open(TOKEN_PATH, "w", encoding="utf-8") as f:
    json.dump(
        {
            "refresh_token": creds.refresh_token,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "token_uri": creds.token_uri,
            "scopes": list(creds.scopes),
        },
        f,
        indent=2,
    )
os.chmod(TOKEN_PATH, 0o600)
os.remove(STATE_PATH)

print("認証成功。リフレッシュトークンを保存しました:", TOKEN_PATH)
