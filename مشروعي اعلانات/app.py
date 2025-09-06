import os
import sqlite3
import hashlib
import hmac
import os
import sqlite3
import hashlib
import hmac
import time
import requests
from flask import Flask, request, jsonify, render_template, session, url_for
from datetime import datetime
from typing import Dict, Any, Optional

app = Flask(__name__)
app.secret_key = os.urandom(24) # Replace with a strong, unique secret key in production

# --- Configuration ---
TELEGRAM_BOT_TOKEN = "8216330677:AAHD1xOCs8OJd1PRZ9XZPIrFKsKIj1l8dHc"
TELEGRAM_ADMIN_CHAT_ID = "7645815913"
TELEGRAM_BOT_USERNAME = "SMARTLAB3Sbot"

DATABASE = 'smartcoinlabs.db'

# --- Database Functions ---
def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE NOT NULL,
            first_name TEXT,
            last_name TEXT,
            username TEXT,
            photo_url TEXT,
            auth_date INTEGER,
            hash TEXT,
            earnings REAL DEFAULT 0.0,
            ads_viewed INTEGER DEFAULT 0,
            referral_code TEXT UNIQUE,
            referrer_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            ton_wallet_address TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    conn.commit()
    conn.close()

# --- Telegram Bot Functions ---
def send_telegram_message(chat_id: str, message: str) -> Optional[Dict[str, Any]]:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML'
    }
    try:
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error sending Telegram message: {e}")
        return None

# --- Helper Functions ---
def generate_referral_code(telegram_id: int) -> str:
    # Simple referral code generation based on telegram_id
    return f"REF{telegram_id}"

# --- Routes ---
@app.route('/')
def index() -> str:
    return render_template('index.html', bot_username=TELEGRAM_BOT_USERNAME)

@app.route('/api/login', methods=['POST'])
def telegram_login() -> tuple[Dict[str, Any], int] | Dict[str, Any]:
    data: Dict[str, Any] = request.json
    if not data:
        return jsonify({"success": False, "message": "No data provided"}), 400

    # Telegram data validation (simplified for example, full validation is more complex)
    # For production, you must implement full Telegram data validation as per their docs:
    # https://core.telegram.org/widgets/login#checking-authorization
    check_string = ""
    for key in sorted(data.keys()):
        if key != 'hash' and key != 'referrer_id': # referrer_id is custom, hash is for validation
            check_string += f"{key}={data[key]}\n"
    check_string = check_string.strip()

    secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode('utf-8')).digest()
    h = hmac.new(secret_key, check_string.encode('utf-8'), hashlib.sha256)
    expected_hash = h.hexdigest()

    if expected_hash != data['hash']:
        return jsonify({"success": False, "message": "Invalid Telegram data hash"}), 403

    # Check auth_date freshness (e.g., within 24 hours)
    if time.time() - data['auth_date'] > 86400: # 24 hours
        return jsonify({"success": False, "message": "Telegram data is too old"}), 403

    telegram_id: int = int(data['id'])
    first_name: Optional[str] = str(data.get('first_name')) if data.get('first_name') else None
    last_name: Optional[str] = str(data.get('last_name')) if data.get('last_name') else None
    username: Optional[str] = str(data.get('username')) if data.get('username') else None
    photo_url: Optional[str] = str(data.get('photo_url')) if data.get('photo_url') else None
    auth_date: int = int(data.get('auth_date'))
    received_hash: str = str(data.get('hash'))
    referrer_id: Optional[int] = int(data.get('referrer_id')) if data.get('referrer_id') else None # Custom parameter for referral

    conn = get_db_connection()
    cursor = conn.cursor()

    user = cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()

    if user is None:
        # New user registration
        referral_code = generate_referral_code(telegram_id)
        cursor.execute(
            "INSERT INTO users (telegram_id, first_name, last_name, username, photo_url, auth_date, hash, referral_code, referrer_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (telegram_id, first_name, last_name, username, photo_url, auth_date, received_hash, referral_code, referrer_id)
        )
        conn.commit()
        user = cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)).fetchone()
        message = f"New user registered: {username or first_name} (ID: {telegram_id})"
        send_telegram_message(TELEGRAM_ADMIN_CHAT_ID, message)
    else:
        # Existing user login, update details if necessary
        cursor.execute(
            "UPDATE users SET first_name=?, last_name=?, username=?, photo_url=?, auth_date=?, hash=? WHERE telegram_id=?",
            (first_name, last_name, username, photo_url, auth_date, received_hash, telegram_id)
        )
        conn.commit()

    conn.close()

    session['user_id'] = user['id'] # Store user ID in session
    return jsonify({
        "success": True,
        "message": "Login successful",
        "user": {
            "id": user['id'],
            "telegram_id": user['telegram_id'],
            "first_name": user['first_name'],
            "username": user['username'],
            "earnings": user['earnings'],
            "adsViewed": user['ads_viewed'],
            "referralLink": url_for('index', ref=user['referral_code'], _external=True)
        }
    })

@app.route('/api/view_ad', methods=['POST'])
def view_ad() -> tuple[Dict[str, Any], int] | Dict[str, Any]:
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    user_id: int = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    user = cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"success": False, "message": "User not found"}), 404

    new_ads_viewed: int = user['ads_viewed'] + 1
    new_earnings: float = user['earnings'] + 0.0001

    # Check for 50 ad milestone bonus
    if new_ads_viewed % 50 == 0:
        new_earnings += 0.1 # Bonus for every 50 ads

    # Handle referral commission
    if user['referrer_id']:
        referrer = cursor.execute("SELECT * FROM users WHERE id = ?", (user['referrer_id'],)).fetchone()
        if referrer:
            commission: float = 0.0001 * 0.10 # 10% of 0.0001
            cursor.execute("UPDATE users SET earnings = earnings + ? WHERE id = ?", (commission, referrer['id']))
            conn.commit()

    cursor.execute(
        "UPDATE users SET ads_viewed = ?, earnings = ? WHERE id = ?",
        (new_ads_viewed, new_earnings, user_id)
    )
    conn.commit()

    updated_user = cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Ad viewed successfully",
        "user": {
            "id": updated_user['id'],
            "telegram_id": updated_user['telegram_id'],
            "first_name": updated_user['first_name'],
            "username": updated_user['username'],
            "earnings": updated_user['earnings'],
            "adsViewed": updated_user['ads_viewed'],
            "referralLink": url_for('index', ref=updated_user['referral_code'], _external=True)
        }
    })

@app.route('/api/withdraw', methods=['POST'])
def withdraw() -> tuple[Dict[str, Any], int] | Dict[str, Any]:
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    user_id: int = session['user_id']
    data: Dict[str, Any] = request.json
    ton_wallet_address: Optional[str] = data.get('tonWalletAddress')

    if not ton_wallet_address:
        return jsonify({"success": False, "message": "TON wallet address is required"}), 400

    # Basic TON wallet address validation (can be enhanced)
    if not ton_wallet_address.startswith('UQ') and not ton_wallet_address.startswith('EQ'):
        return jsonify({"success": False, "message": "Invalid TON wallet address format"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    user = cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"success": False, "message": "User not found"}), 404

    if user['ads_viewed'] < 50:
        conn.close()
        return jsonify({"success": False, "message": "You must view at least 50 ads before withdrawing"}), 400

    withdrawal_amount: float = user['earnings'] # Withdraw all available earnings

    if withdrawal_amount <= 0:
        conn.close()
        return jsonify({"success": False, "message": "No earnings to withdraw"}), 400

    # Deduct earnings and record withdrawal
    cursor.execute("UPDATE users SET earnings = 0.0 WHERE id = ?", (user_id,))
    cursor.execute(
        "INSERT INTO withdrawals (user_id, amount, ton_wallet_address) VALUES (?, ?, ?)",
        (user_id, withdrawal_amount, ton_wallet_address)
    )
    conn.commit()

    # Send admin notification via Telegram bot
    message = (
        f"<b>New Withdrawal Request!</b>\n"
        f"User: {user['first_name'] or user['username']} (ID: {user['telegram_id']})\n"
        f"Amount: {withdrawal_amount:.4f}\n"
        f"TON Wallet: <code>{ton_wallet_address}</code>\n"
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    send_telegram_message(TELEGRAM_ADMIN_CHAT_ID, message)

    updated_user = cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    return jsonify({
        "success": True,
        "message": "Withdrawal request submitted successfully",
        "user": {
            "id": updated_user['id'],
            "telegram_id": updated_user['telegram_id'],
            "first_name": updated_user['first_name'],
            "username": updated_user['username'],
            "earnings": updated_user['earnings'],
            "adsViewed": updated_user['ads_viewed'],
            "referralLink": url_for('index', ref=updated_user['referral_code'], _external=True)
        }
    })

@app.after_request
def add_security_headers(response):
    response.headers['Content-Security-Policy'] = "frame-ancestors 'self' https://oauth.telegram.org http://127.0.0.1:5000;"
    return response

if __name__ == '__main__':
    init_db()
    app.run(debug=True)