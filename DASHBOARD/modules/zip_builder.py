from flask import Blueprint, request, jsonify, send_file
import os
import csv
import zipfile
import threading
from . import REPO_ROOT, ENCODING
from .auth import read_users

zip_bp = Blueprint('zip', __name__)
zip_lock = threading.Lock()

@zip_bp.route('/api/build-zip', methods=['POST'])
def api_build_zip():
    data = request.get_json()
    org_name = (data.get('org_name') or '').strip()
    if not org_name:
        return jsonify(ok=False, error='Organization name is required'), 400

    users = read_users()
    user = next((u for u in users if u['ORG_NAME'] == org_name), None)
    if not user:
        return jsonify(ok=False, error='Organization not found'), 404

    download_zip_dir = os.path.join(REPO_ROOT, 'DASHBOARD', 'dashboard-page', 'download-zip')
    org_id_csv = os.path.join(download_zip_dir, 'SecurityLayer', 'usbSecurity', 'A_org_id.csv')
    security_layer_dir = os.path.join(download_zip_dir, 'SecurityLayer')
    zip_dir = os.path.join(download_zip_dir, 'ZIP')
    output_zip = os.path.join(zip_dir, 'SecurityLayer_USB_Monitor.zip')

    if not zip_lock.acquire(timeout=5):
        return jsonify(ok=False, error='Another build is in progress'), 429

    try:
        with open(org_id_csv, 'w', newline='', encoding=ENCODING) as f:
            writer = csv.writer(f)
            writer.writerow(['ORG_ID'])
            writer.writerow([user['ORG_ID']])

        os.makedirs(zip_dir, exist_ok=True)
        exclude = {'__pycache__', '.pyc', '.build_manifest.json'}

        with zipfile.ZipFile(output_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(security_layer_dir):
                for fname in files:
                    fpath = os.path.join(root, fname)
                    if any(ex in fpath for ex in exclude):
                        continue
                    arcname = os.path.join('SecurityLayer', os.path.relpath(fpath, security_layer_dir))
                    zf.write(fpath, arcname)

        return send_file(output_zip, mimetype='application/zip', as_attachment=True, download_name='SecurityLayer_USB_Monitor.zip')
    except Exception as e:
        print(f'build_zip error: {e}')
        return jsonify(ok=False, error='Internal server error'), 500
    finally:
        zip_lock.release()
