"""
Flask Web Application for Data Bundle Sales Platform
====================================================

This application manages:
- User registration, login, and profiles
- Wallet top-up using Paystack integration
- Data bundle purchases with wallet deductions
- Admin purchase confirmation
- JSON-based persistent storage for users and purchases

Author: Emmanuel
"""

from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import json
import os
import requests
from datetime import datetime
from werkzeug.utils import secure_filename

# ---------------- APP CONFIGURATION ----------------
app = Flask(__name__)
app.secret_key = "MYSPECIALDATAAPPSECREATKEY"  # Replace with environment variable in production

UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Paystack credentials (should be stored securely in environment variables)
PAYSTACK_SECRET_KEY = "sk_test_07157d2784524701ce709d7526e40311caaa38c6"
PAYSTACK_PUBLIC_KEY = "pk_test_5dba95da4545041b0211cab413af0c955f71354f"

# JSON data storage files
USERS_FILE = 'users.json'
PURCHASES_FILE = 'purchases.json'
PENDING_FILE = 'pending_payments.json'


# ---------------- HELPER FUNCTIONS ----------------
def allowed_file(filename):
    """Check if uploaded file has a valid extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _read_json(path, default):
    """Read JSON data from a file safely, returning default if file does not exist or is invalid."""
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return default


def _write_json(path, data):
    """Write JSON data to a file with indentation for readability."""
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)


def load_users():
    """Load all users from the JSON file."""
    data = _read_json(USERS_FILE, [])
    return data if isinstance(data, list) else []


def save_users(users):
    """Save the list of users to the JSON file."""
    _write_json(USERS_FILE, users)


def load_purchases():
    """Load all purchases from the JSON file."""
    data = _read_json(PURCHASES_FILE, [])
    return data if isinstance(data, list) else []


def save_purchases(purchases):
    """Save the list of purchases to the JSON file."""
    _write_json(PURCHASES_FILE, purchases)


def load_pending():
    """Load pending wallet top-up payments from JSON file."""
    return _read_json(PENDING_FILE, [])


def save_pending(pending):
    """Save pending wallet top-up payments to JSON file."""
    _write_json(PENDING_FILE, pending)


def now_str():
    """Return the current datetime as a formatted string."""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def next_purchase_id(purchases):
    """Generate the next purchase ID by incrementing the maximum existing ID."""
    return (max([p.get('id', 0) for p in purchases]) + 1) if purchases else 1


# ---------------- ROUTES ----------------
@app.route('/')
def home():
    """Landing page route."""
    return render_template('landing.html', current_year=datetime.now().year)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Handle user registration with validation and persistence."""
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        mobile = request.form['mobile']
        gender = request.form['gender']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            return render_template('register.html', error="Passwords do not match")

        users = load_users()
        for user in users:
            if user.get('email') == email:
                return render_template('register.html', error="Email already registered")

        # Add new user with empty wallet and no transactions
        users.append({
            "username": username,
            "email": email,
            "mobile": mobile,
            "gender": gender,
            "password": password,
            "wallet_balance": 0.0,
            "transactions": []
        })

        save_users(users)
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Authenticate users and create a session."""
    error = None
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        users = load_users()
        user = next((u for u in users if u['email'] == email), None)

        if user and user['password'] == password:
            session['email'] = user['email']
            session['username'] = user['username']
            return redirect(url_for('dashboard'))
        error = 'Invalid email or password'

    return render_template('login.html', error=error)


@app.route('/dashboard')
def dashboard():
    """Display user dashboard with purchase history and wallet balance."""
    if 'username' in session and 'email' in session:
        all_purchases = load_purchases()
        user_purchases = [p for p in all_purchases if p.get('email') == session['email']]
        users = load_users()
        user = next((u for u in users if u['email'] == session['email']), None)
        balance = user.get('wallet_balance', 0.0) if user else 0.0
        return render_template('dashboard.html',
                               username=session['username'],
                               purchases=user_purchases,
                               balance=balance)
    return redirect(url_for('login'))


@app.route('/purchase', methods=['GET', 'POST'])
def purchase():
    """Handle purchase requests, deduct from wallet, and record transactions."""
    if 'email' not in session:
        return redirect(url_for('login'))

    users = load_users()
    user = next((u for u in users if u['email'] == session['email']), None)
    if not user:
        return redirect(url_for('logout'))

    if request.method == 'POST':
        network = request.form['network']
        bundle = request.form['bundle']
        mobile = request.form['mobile']
        email = session['email']

        # Extract price from format like "1 GB - 5.40 GHS"
        try:
            price_str = bundle.split('-')[1].strip().replace("GHS", "").strip()
            amount = float(price_str)
        except (IndexError, ValueError):
            return jsonify({"error": "Invalid bundle format."}), 400

        # Prevent purchase if wallet balance is insufficient
        if user.get('wallet_balance', 0.0) < amount:
            return jsonify({
                "error": "Insufficient wallet balance",
                "balance": float(user.get('wallet_balance', 0.0))
            }), 400

        purchases = load_purchases()
        pid = next_purchase_id(purchases)

        # Deduct from wallet immediately (payment considered completed)
        user['wallet_balance'] = round(float(user.get('wallet_balance', 0.0)) - amount, 2)

        # Create a new purchase record with staged status tracking
        purchase_record = {
            "id": pid,
            "email": email,
            "provider": network,
            "bundle": bundle,
            "number": mobile,
            "amount": amount,
            "created_at": now_str(),
            "status": "payment_completed",
            "stages": {
                "request_created": {"done": True, "at": now_str()},
                "payment_completed": {"done": True, "at": now_str()},
                "credited": {"done": False, "at": None}
            }
        }

        purchases.append(purchase_record)
        save_purchases(purchases)
        save_users(users)

        # If request came from fetch (AJAX), return JSON
        if request.headers.get('X-Requested-With') == 'fetch':
            return jsonify({"ok": True, "id": pid})
        return redirect(url_for('dashboard'))

    # GET: Show purchase page
    return render_template('purchase.html',
                           username=user['username'],
                           balance=user.get('wallet_balance', 0.0))


@app.route('/faq')
def faq():
    """FAQ page route."""
    return render_template('FAQ.html')


@app.route('/landing')
def landing():
    """Landing page route."""
    return render_template('landing.html')


@app.route('/contact')
def contact():
    """Contact page route."""
    return render_template('contact.html')


# ---------------- ADMIN ----------------
@app.route('/admin', methods=['GET'])
def admin_panel():
    """
    Admin panel to view all purchases.
    NOTE: Authentication/authorization should be enforced for security.
    """
    purchases = load_purchases()
    purchases_sorted = sorted(purchases, key=lambda p: p.get('id', 0), reverse=True)
    return render_template('admin.html', purchases=purchases_sorted)


@app.route('/admin/confirm/<int:pid>', methods=['POST'])
def admin_confirm(pid):
    """Admin route to confirm and mark a purchase as credited."""
    purchases = load_purchases()
    found = False
    for p in purchases:
        if p.get('id') == pid:
            p['status'] = 'credited'
            p.setdefault('stages', {})
            p['stages'].setdefault('credited', {"done": False, "at": None})
            p['stages']['credited']['done'] = True
            p['stages']['credited']['at'] = now_str()
            found = True
            break

    if not found:
        return jsonify({"error": "Purchase not found"}), 404

    save_purchases(purchases)

    if request.headers.get('X-Requested-With') == 'fetch':
        return jsonify({"ok": True})
    return redirect(url_for('admin_panel'))


# ---------------- WALLET & PAYSTACK ----------------
@app.route('/wallet')
def wallet():
    """Wallet page showing balance and Paystack top-up option."""
    email = request.args.get("email") or session.get("email")
    if not email:
        return redirect(url_for("login"))

    users = load_users()
    user = next((u for u in users if u['email'] == email), None)

    if not user:
        return redirect(url_for('logout'))

    return render_template('wallet.html', user=user, paystack_public_key=PAYSTACK_PUBLIC_KEY)


@app.route('/initiate_payment', methods=['POST'])
def initiate_payment():
    """Initialize a Paystack transaction for wallet top-up."""
    if 'email' not in session:
        return redirect(url_for('login'))

    amount = request.form.get("amount")
    provider = request.form.get("provider")
    number = request.form.get("number")
    email = session['email']

    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}", "Content-Type": "application/json"}
    data = {
        "email": email,
        "amount": int(float(amount) * 100),  # Paystack expects amount in kobo/pesewas
        "callback_url": url_for("verify_payment", _external=True)
    }

    response = requests.post("https://api.paystack.co/transaction/initialize",
                             headers=headers, json=data)
    res = response.json()

    if res.get("status"):
        reference = res["data"]["reference"]

        # Save transaction as pending
        pending = load_pending()
        pending.append({
            "email": email,
            "amount": float(amount),
            "provider": provider,
            "number": number,
            "reference": reference,
            "created_at": now_str()
        })
        save_pending(pending)

        return redirect(res["data"]["authorization_url"])

    return f"Error initializing payment: {res.get('message', 'Unknown error')}"


@app.route("/verify_payment")
def verify_payment():
    """Verify a Paystack payment and credit the user’s wallet."""
    reference = request.args.get("reference")
    if not reference:
        return "Missing payment reference."

    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    response = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers)
    res = response.json()

    if res.get("status") and res.get("data", {}).get("status") == "success":
        pending = load_pending()
        payment = next((p for p in pending if p["reference"] == reference), None)

        if not payment:
            return "No matching pending payment found."

        users = load_users()
        user = next((u for u in users if u['email'] == payment['email']), None)
        if not user:
            return "User not found."

        # Credit wallet balance
        user["wallet_balance"] = round(float(user.get("wallet_balance", 0)) + payment["amount"], 2)
        user.setdefault("transactions", []).append({
            "amount": payment["amount"],
            "provider": payment["provider"],
            "number": payment["number"],
            "reference": reference,
            "status": "success",
            "at": now_str()
        })

        save_users(users)
        return redirect(url_for("wallet", email=user["email"]))

    return "Payment verification failed."


# ---------------- PROFILE ----------------
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    """View and update user profile details."""
    if 'email' not in session:
        return redirect(url_for('login'))

    users = load_users()
    user = next((u for u in users if u['email'] == session['email']), None)
    if not user:
        return redirect(url_for('logout'))

    if request.method == 'POST':
        new_username = request.form['username']
        new_email = request.form['email']
        new_mobile = request.form['mobile']
        new_gender = request.form['gender']
        new_password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        if new_password and new_password != confirm_password:
            return render_template('profile.html', user=user, error="Passwords do not match")

        if new_email != user['email'] and any(u['email'] == new_email for u in users):
            return render_template('profile.html', user=user, error="This email is already in use")

        # Update user details
        user.update({"username": new_username, "email": new_email,
                     "mobile": new_mobile, "gender": new_gender})
        if new_password:
            user['password'] = new_password

        # Update session
        session['email'] = new_email
        session['username'] = new_username

        # Handle profile picture upload
        if 'profile_pic' in request.files:
            file = request.files['profile_pic']
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                user['profile_pic'] = filename

        save_users(users)
        return render_template('profile.html', user=user, message="Profile updated successfully")

    return render_template('profile.html', user=user)


@app.route('/delete_account', methods=['POST'])
def delete_account():
    """Delete user account and remove associated profile picture."""
    if 'email' not in session:
        return redirect(url_for('login'))

    users = load_users()
    email = session['email']
    user = next((u for u in users if u['email'] == email), None)

    if user:
        # Remove profile picture if exists
        if 'profile_pic' in user:
            pic_path = os.path.join(app.config['UPLOAD_FOLDER'], user['profile_pic'])
            if os.path.exists(pic_path):
                os.remove(pic_path)

        updated_users = [u for u in users if u['email'] != email]
        save_users(updated_users)
        session.clear()
        return redirect(url_for('login'))

    return "User not found", 404


@app.route('/logout')
def logout():
    """Log out the user and clear the session."""
    session.clear()
    return redirect(url_for('landing'))


# ---------------- API ENDPOINTS ----------------
@app.route('/api/wallet_balance')
def api_wallet_balance():
    """Return current wallet balance of logged-in user as JSON."""
    if 'email' not in session:
        return jsonify({"balance": 0.0})

    users = load_users()
    user = next((u for u in users if u['email'] == session['email']), None)
    return jsonify({"balance": float(user.get('wallet_balance', 0.0)) if user else 0.0})


# ---------------- RUN APP ----------------
if __name__ == '__main__':
    app.run(debug=True)
