"""
OAuthの認証URLを発行する(1回目のステップ)。
code_verifierをsecrets/.oauth_pkce_state.jsonに保存しておくことで、
別プロセス(oauth_step2_exchange_code.py)からトークン交換時に再利用できるようにする。
"""
import json
import os

from google_auth_oauthlib.flow import Flow

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(REPO_ROOT, "secrets", ".oauth_pkce_state.json")

flow = Flow.from_client_secrets_file(
    os.path.join(REPO_ROOT, "secrets", "oauth_client_secret.json"),
    scopes=["https://www.googleapis.com/auth/drive"],
    redirect_uri="http://localhost",
)
auth_url, state = flow.authorization_url(access_type="offline", prompt="consent")

with open(STATE_PATH, "w", encoding="utf-8") as f:
    json.dump({"code_verifier": flow.code_verifier, "state": state}, f)
os.chmod(STATE_PATH, 0o600)

print(auth_url)
