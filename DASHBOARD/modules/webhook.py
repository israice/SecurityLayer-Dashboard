from flask import Blueprint, request
import os
import hmac
import hashlib
import subprocess
import threading
from . import config

webhook_bp = Blueprint('webhook', __name__)

def verify_github_signature(payload: bytes, signature: str | None) -> bool:
    if not signature:
        return False
    secret = os.environ['GITHUB_WEBHOOK_SECRET'].encode()
    expected = 'sha256=' + hmac.new(secret, payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)

def run_deploy() -> None:
    repo_path = config['WEBHOOK']['REPO_PATH']
    deploy_script = '/app/DASHBOARD/deploy.sh'
    print(f'Starting deploy from {repo_path}...')
    try:
        result = subprocess.run(['bash', deploy_script], cwd=repo_path, capture_output=True, text=True)
        print(f'Deploy stdout: {result.stdout}')
        if result.stderr:
            print(f'Deploy stderr: {result.stderr}')
        print(f'Deploy finished with code {result.returncode}')
    except Exception as e:
        print(f'Deploy error: {e}')

@webhook_bp.route('/webhook/github', methods=['POST'])
def github_webhook():
    signature = request.headers.get('X-Hub-Signature-256')
    if not verify_github_signature(request.data, signature):
        print('Webhook: Invalid signature')
        return 'Invalid signature', 401

    payload = request.json
    ref = payload['ref']
    allowed_branch = config['WEBHOOK']['ALLOWED_BRANCH']

    if ref != allowed_branch:
        print(f'Webhook: Ignored branch {ref}')
        return f'Ignored: {ref}', 200

    print(f'Webhook: Push to {ref} - starting deploy')
    threading.Thread(target=run_deploy, daemon=True).start()
    return 'Deploy started', 200
