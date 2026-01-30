from flask import Blueprint, request, jsonify
import os
import csv
import re
import uuid
from . import REPO_ROOT, ENCODING

auth_bp = Blueprint('auth', __name__)

USERS_CSV = os.path.join(REPO_ROOT, 'DATA', 'admins.csv')
_FIELD_TO_COLUMN = {'email': 'USER_MAIL', 'orgName': 'ORG_NAME', 'userName': 'USER_NAME'}

def is_valid_email(email: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))

def is_valid_password(password: str) -> bool:
    return isinstance(password, str) and len(password) >= 3

def is_valid_name(name: str) -> bool:
    return isinstance(name, str) and len(name.strip()) >= 2

def generate_id(prefix: str) -> str:
    return f'{prefix}_{uuid.uuid4().hex[:8]}'

_REGISTER_VALIDATORS = [
    ('email', is_valid_email, 'Invalid email format'),
    ('password', is_valid_password, 'Password must be at least 3 characters'),
    ('orgName', is_valid_name, 'Organization name must be at least 2 characters'),
    ('userName', is_valid_name, 'User name must be at least 2 characters'),
]

_UNIQUENESS_RULES = [
    ('email', 'Email is taken, try another'),
    ('orgName', 'Organization name is taken, try another'),
    ('userName', 'User name is taken, try another'),
]

def _validate_registration(data: dict) -> tuple[dict, str | None]:
    fields = {k: data.get(k, '').strip() if k != 'password' else data.get(k, '') for k in ['email', 'password', 'orgName', 'userName']}
    for field, validator, error_msg in _REGISTER_VALIDATORS:
        if not validator(fields[field]):
            return fields, error_msg
    return fields, None

def _check_field_exists(users: list[dict], field: str, value: str) -> bool:
    column = _FIELD_TO_COLUMN.get(field)
    return column and any(u[column].lower() == value.lower() for u in users)

def read_users() -> list[dict]:
    users = []
    try:
        if os.path.exists(USERS_CSV):
            with open(USERS_CSV, 'r', encoding=ENCODING) as f:
                users = list(csv.DictReader(f))
    except Exception as e:
        print(f'Error reading users: {e}')
    return users

def write_user(user: dict) -> bool:
    try:
        exists = os.path.exists(USERS_CSV)
        with open(USERS_CSV, 'a', newline='', encoding=ENCODING) as f:
            writer = csv.DictWriter(f, fieldnames=['ORG_ID', 'ORG_NAME', 'USER_ID', 'USER_NAME', 'USER_MAIL', 'USER_PASSWORD'])
            if not exists:
                writer.writeheader()
            writer.writerow(user)
        return True
    except Exception as e:
        print(f'Error writing user: {e}')
        return False

@auth_bp.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    email, password = data.get('email', '').strip(), data.get('password', '')
    if not email or not password:
        return jsonify(ok=False, error='Email and password required'), 400
    users = read_users()
    user = next((u for u in users if u['USER_MAIL'] == email and u['USER_PASSWORD'] == password), None)
    if user:
        return jsonify(ok=True, user=user)
    return jsonify(ok=False, error='Invalid credentials'), 401

@auth_bp.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    fields, error = _validate_registration(data)
    if error:
        return jsonify(ok=False, error=error), 400
    users = read_users()
    for field, error_msg in _UNIQUENESS_RULES:
        if _check_field_exists(users, field, fields[field]):
            return jsonify(ok=False, error=error_msg), 400
    user = {
        'ORG_ID': generate_id('ORG'), 'ORG_NAME': fields['orgName'],
        'USER_ID': generate_id('USER'), 'USER_NAME': fields['userName'],
        'USER_MAIL': fields['email'], 'USER_PASSWORD': fields['password']
    }
    if write_user(user):
        return jsonify(ok=True, user=user)
    return jsonify(ok=False, error='Failed to save user'), 500

@auth_bp.route('/api/check', methods=['POST'])
def api_check():
    data = request.get_json()
    field, value = data.get('field', ''), data.get('value', '').strip()
    if not value:
        return jsonify(ok=True, exists=False)
    return jsonify(ok=True, exists=_check_field_exists(read_users(), field, value))
