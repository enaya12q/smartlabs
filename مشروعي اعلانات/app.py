import os
import sqlite3
import hashlib
import hmac
import time
import requests
from flask import Flask, request, jsonify, render_template, session, url_for, redirect
from datetime import datetime
from typing import Dict, Any, Optional
from functools import wraps # Import wraps for decorator
import asyncio # Import asyncio for running async functions in a sync context
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN_HERE")
TELEGRAM_ADMIN_CHAT_ID = os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "YOUR_TELEGRAM_ADMIN_CHAT_ID_HERE")
TELEGRAM_ADMIN_ID = int(os.environ.get("TELEGRAM_ADMIN_ID", "YOUR_ADMIN_TELEGRAM_ID_HERE")) # Admin's Telegram ID
TELEGRAM_BOT_USERNAME = "SMARTLAB3Sbot" # This can remain hardcoded or also be an env var

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

app = Flask(__name__)
app.secret_key = os.urandom(24) # Replace with a strong, unique secret key in production

# Initialize the database when the app starts
with app.app_context():
    init_db()

# --- Telegram Bot Functions ---
async def send_telegram_message(chat_id: str, message: str) -> Optional[Dict[str, Any]]:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': message,
        'parse_mode': 'HTML'
    }
    try:
        # Using requests.post is synchronous, for a fully async app, aiohttp would be preferred.
        # However, for simplicity and to avoid adding new dependencies, we'll keep requests for now.
        # In an async context, this will block the event loop.
        response = await asyncio.to_thread(requests.post, url, json=payload)
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

@app.route('/test')
def test_route() -> str:
    return "Test route is working!"

@app.route('/about')
def about() -> str:
    return render_template('about.html')

@app.route('/whitepaper')
def whitepaper() -> str:
    return render_template('whitepaper.html')

@app.route('/privacy-policy')
def privacy_policy() -> str:
    return render_template('privacy_policy.html')

@app.route('/dashboard')
def dashboard() -> str:
    if 'user_id' not in session:
        return redirect(url_for('index')) # Redirect to home if not logged in
    return render_template('dashboard.html')

@app.route('/admin')
@admin_required
def admin_panel() -> str:
    return render_template('admin.html')

# --- Admin Decorator ---
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('index'))
        
        conn = get_db_connection()
        user = conn.execute("SELECT telegram_id FROM users WHERE id = ?", (session['user_id'],)).fetchone()
        conn.close()

        if user and user['telegram_id'] == TELEGRAM_ADMIN_ID:
            return f(*args, **kwargs)
        else:
            return jsonify({"success": False, "message": "Admin access required"}), 403
    return decorated_function

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
        admin_message = f"New user registered: {username or first_name} (ID: {telegram_id})"
        asyncio.run(send_telegram_message(TELEGRAM_ADMIN_CHAT_ID, admin_message))

        welcome_message = (
            "👋 Welcome to Smart Coin Labs!\n"
            "📺 Watch ads and earn TON easily.\n"
            "💎 Earn $0.50 TON for every 50 ads watched!\n"
            "Click /start to begin now."
        )
        asyncio.run(send_telegram_message(str(telegram_id), welcome_message))
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

@app.route('/api/user_data', methods=['GET'])
def get_user_data() -> tuple[Dict[str, Any], int] | Dict[str, Any]:
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "Not authenticated"}), 401

    user_id: int = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()

    if not user:
        return jsonify({"success": False, "message": "User not found"}), 404

    return jsonify({
        "success": True,
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

# --- Telegram Bot Webhook ---
application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_user:
        print("No effective user in update.")
        return

    user_telegram_id = update.effective_user.id
    user_first_name = update.effective_user.first_name
    user_username = update.effective_user.username

    conn = get_db_connection()
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (user_telegram_id,)).fetchone()

    if user is None:
        # This scenario should ideally be handled by the web login, but as a fallback
        # or for direct bot interaction, we can register them here.
        referral_code = generate_referral_code(user_telegram_id)
        cursor.execute(
            "INSERT INTO users (telegram_id, first_name, username, referral_code) VALUES (?, ?, ?, ?)",
            (user_telegram_id, user_first_name, user_username, referral_code)
        )
        conn.commit()
        admin_message = f"New user registered via bot: {user_username or user_first_name} (ID: {user_telegram_id})"
        await send_telegram_message(TELEGRAM_ADMIN_CHAT_ID, admin_message)

    welcome_message = (
        "👋 Welcome to Smart Coin Labs!\n"
        "📺 Watch ads and earn TON easily.\n"
        "💎 Earn $0.50 TON for every 50 ads watched!\n"
        "Click /start to begin now."
    )
    # Use context.bot.send_message for async operations
    await context.bot.send_message(chat_id=user_telegram_id, text=welcome_message)
    conn.close()

application.add_handler(CommandHandler("start", start_command))

@app.route('/telegram-webhook', methods=['POST'])
async def telegram_webhook() -> tuple[Dict[str, Any], int]:
    await application.update_queue.put(Update.de_json(request.get_json(force=True), application.bot))
    return jsonify({"status": "ok"}), 200

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
        new_earnings += 0.50 # Bonus for every 50 ads: $0.50 TON

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
        f"Amount: {withdrawal_amount:.4f} TON\n"
        f"TON Wallet: <code>{ton_wallet_address}</code>\n"
        f"⏳ Status: Pending\n"
        f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    asyncio.run(send_telegram_message(TELEGRAM_ADMIN_CHAT_ID, message))

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

@app.route('/api/logout', methods=['POST'])
def logout() -> tuple[Dict[str, Any], int]:
    session.pop('user_id', None)
    return jsonify({"success": True, "message": "Logged out successfully"}), 200

@app.route('/api/admin/users', methods=['GET'])
@admin_required
def admin_get_users() -> tuple[Dict[str, Any], int]:
    conn = get_db_connection()
    cursor = conn.cursor()
    search_term = request.args.get('search', '')

    if search_term:
        users = cursor.execute(
            "SELECT * FROM users WHERE username LIKE ? OR telegram_id LIKE ?",
            (f"%{search_term}%", f"%{search_term}%")
        ).fetchall()
    else:
        users = cursor.execute("SELECT * FROM users").fetchall()
    
    conn.close()
    return jsonify({"success": True, "users": [dict(user) for user in users]}), 200

@app.route('/api/admin/withdrawals', methods=['GET'])
@admin_required
def admin_get_withdrawals() -> tuple[Dict[str, Any], int]:
    conn = get_db_connection()
    cursor = conn.cursor()
    search_term = request.args.get('search', '')

    if search_term:
        # Join with users table to get username for search
        withdrawals = cursor.execute(
            """
            SELECT w.*, u.username, u.first_name
            FROM withdrawals w
            JOIN users u ON w.user_id = u.id
            WHERE u.username LIKE ? OR w.ton_wallet_address LIKE ?
            """,
            (f"%{search_term}%", f"%{search_term}%")
        ).fetchall()
    else:
        withdrawals = cursor.execute(
            """
            SELECT w.*, u.username, u.first_name
            FROM withdrawals w
            JOIN users u ON w.user_id = u.id
            """
        ).fetchall()
    
    conn.close()
    return jsonify({"success": True, "withdrawals": [dict(w) for w in withdrawals]}), 200

@app.route('/api/admin/withdrawals/<int:withdrawal_id>/<status>', methods=['POST'])
@admin_required
def admin_update_withdrawal_status(withdrawal_id: int, status: str) -> tuple[Dict[str, Any], int]:
    if status not in ['completed', 'rejected']:
        return jsonify({"success": False, "message": "Invalid status"}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE withdrawals SET status = ? WHERE id = ?",
        (status, withdrawal_id)
    )
    conn.commit()
    conn.close()

    # Optionally, notify the user via Telegram about the withdrawal status change
    # For this, you'd need to fetch user_id from the withdrawal and then their telegram_id
    # This is a future enhancement.

    return jsonify({"success": True, "message": f"Withdrawal {withdrawal_id} marked as {status}"}), 200

@app.after_request
def add_security_headers(response):
    response.headers['Content-Security-Policy'] = "frame-ancestors 'self' https://oauth.telegram.org http://127.0.0.1:5000;"
    return response

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000, debug=True)