from flask import Flask, render_template, request, redirect, session, url_for, jsonify
import json
import os
import requests
from datetime import datetime
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "your_secret_key_here"


# ---------------- CONFIG ----------------
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

PAYSTACK_SECRET_KEY = "sk_test_07157d2784524701ce709d7526e40311caaa38c6"   # Replace with your real secret key
PAYSTACK_PUBLIC_KEY = "pk_test_5dba95da4545041b0211cab413af0c955f71354f"   # Replace with your real public key

USERS_FILE = 'users.json'
PURCHASES_FILE = 'purchases.json'
PENDING_FILE = 'pending_payments.json'
# ---------------- UTILITIES ----------------
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _read_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return default


def _write_json(path, data):
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)


def load_users():
    data = _read_json(USERS_FILE, [])
    return data if isinstance(data, list) else []


def save_users(users):
    _write_json(USERS_FILE, users)


def load_purchases():
    data = _read_json(PURCHASES_FILE, [])
    return data if isinstance(data, list) else []


def save_purchases(purchases):
    _write_json(PURCHASES_FILE, purchases)


def now_str():
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def next_purchase_id(purchases):
    # Simple incremental ID for admin actions
    return (max([p.get('id', 0) for p in purchases]) + 1) if purchases else 1

def load_pending():
    return _read_json(PENDING_FILE, [])

def save_pending(pending):
    _write_json(PENDING_FILE, pending)

# ---------------- ROUTES ----------------
@app.route('/')
def home():
    return render_template('landing.html', current_year=datetime.now().year)


@app.route('/register', methods=['GET', 'POST'])
def register():
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
        else:
            error = 'Invalid email or password'

    return render_template('login.html', error=error)


@app.route('/dashboard')
def dashboard():
    if 'username' in session and 'email' in session:
        all_purchases = load_purchases()
        user_purchases = [p for p in all_purchases if p.get('email') == session['email']]
        users = load_users()
        user = next((u for u in users if u['email'] == session['email']), None)
        balance = user.get('wallet_balance', 0.0) if user else 0.0
        return render_template('dashboard.html', username=session['username'], purchases=user_purchases, balance=balance)
    return redirect(url_for('login'))


# -------- PURCHASE FLOW (Request -> Payment -> Admin Credit) --------
@app.route('/purchase', methods=['GET', 'POST'])
def purchase():
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

        # Extract price from string like "1 GB - 5.40 GHS"
        try:
            price_str = bundle.split('-')[1].strip().replace("GHS", "").strip()
            amount = float(price_str)
        except (IndexError, ValueError):
            return jsonify({"error": "Invalid bundle format."}), 400

        # SERVER-SIDE GUARD: block if insufficient balance (client checks too)
        if user.get('wallet_balance', 0.0) < amount:
            return jsonify({
                "error": "Insufficient wallet balance",
                "balance": float(user.get('wallet_balance', 0.0))
            }), 400

        purchases = load_purchases()
        pid = next_purchase_id(purchases)

        # Deduct now -> payment completed
        user['wallet_balance'] = round(float(user.get('wallet_balance', 0.0)) - amount, 2)

        # Create staged purchase record
        purchase_record = {
            "id": pid,
            "email": email,
            "provider": network,
            "bundle": bundle,
            "number": mobile,
            "amount": amount,
            "created_at": now_str(),
            "status": "payment_completed",  # stages: request_created -> payment_completed -> credited
            "stages": {
                "request_created": {"done": True,  "at": now_str()},
                "payment_completed": {"done": True,  "at": now_str()},
                "credited": {"done": False, "at": None}
            }
        }

        purchases.append(purchase_record)
        save_purchases(purchases)
        save_users(users)

        # If the frontend used fetch, send a JSON ok; if normal form, redirect from JS
        if request.headers.get('X-Requested-With') == 'fetch':
            return jsonify({"ok": True, "id": pid})
        return redirect(url_for('dashboard'))

    # GET
    return render_template('purchase.html', username=user['username'], balance=user.get('wallet_balance', 0.0))

@app.route('/faq')
def faq():
    return render_template('FAQ.html')
@app.route('/contact')
def contact():
    return render_template('contact.html')

# -------- ADMIN --------
@app.route('/admin', methods=['GET'])
def admin_panel():
    # TODO: Protect this route with proper auth/role check
    purchases = load_purchases()
    # newest first
    purchases_sorted = sorted(purchases, key=lambda p: p.get('id', 0), reverse=True)
    return render_template('admin.html', purchases=purchases_sorted)


@app.route('/admin/confirm/<int:pid>', methods=['POST'])
def admin_confirm(pid):
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
    # If fetch was used
    if request.headers.get('X-Requested-With') == 'fetch':
        return jsonify({"ok": True})
    return redirect(url_for('admin_panel'))


# -------- WALLET + PAYSTACK INTEGRATION --------
@app.route('/wallet')
def wallet():
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
    if 'email' not in session:
        return redirect(url_for('login'))

    amount = request.form.get("amount")
    provider = request.form.get("provider")
    number = request.form.get("number")
    email = session['email']

    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}", "Content-Type": "application/json"}
    data = {
        "email": email,
        "amount": int(float(amount) * 100),
        "callback_url": url_for("verify_payment", _external=True)
    }

    response = requests.post("https://api.paystack.co/transaction/initialize", headers=headers, json=data)
    res = response.json()

    if res.get("status"):
        reference = res["data"]["reference"]

        # Save this transaction as pending
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
    else:
        return f"Error initializing payment: {res.get('message', 'Unknown error')}"


@app.route("/verify_payment")
def verify_payment():
    reference = request.args.get("reference")
    if not reference:
        return "Missing payment reference."

    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    response = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers)
    res = response.json()

    if res.get("status") and res.get("data", {}).get("status") == "success":
        # Load pending payments
        pending = load_pending()
        payment = next((p for p in pending if p["reference"] == reference), None)

        if not payment:
            return "No matching pending payment found."

        users = load_users()
        user = next((u for u in users if u['email'] == payment['email']), None)
        if not user:
            return "User not found."

        # Credit wallet
        user["wallet_balance"] = round(float(user.get("wallet_balance", 0)) + payment["amount"], 2)
        user.setdefault("transactions", []).append({
            "amount": payment["amount"],
            "provider": payment["provider"],
            "number": payment["number"],
            "reference": reference,
            "status": "success",
            "at": now_str()
        })

        # Save updated user
        save_users(users)

        

        return redirect(url_for("wallet", email=user["email"]))
    else:
        return "Payment verification failed."

# -------- PROFILE --------
@app.route('/profile', methods=['GET', 'POST'])
def profile():
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

        user.update({"username": new_username, "email": new_email, "mobile": new_mobile, "gender": new_gender})
        if new_password:
            user['password'] = new_password

        session['email'] = new_email
        session['username'] = new_username

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
    if 'email' not in session:
        return redirect(url_for('login'))

    users = load_users()
    email = session['email']
    user = next((u for u in users if u['email'] == email), None)

    if user:
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
    session.clear()
    return redirect(url_for('login'))


# -------- LIGHTWEIGHT API (optional for frontend use) --------
@app.route('/api/wallet_balance')
def api_wallet_balance():
    if 'email' not in session:
        return jsonify({"balance": 0.0})
    users = load_users()
    user = next((u for u in users if u['email'] == session['email']), None)
    return jsonify({"balance": float(user.get('wallet_balance', 0.0)) if user else 0.0})


# ---------------- RUN ----------------
if __name__ == '__main__':
    app.run(debug=True)