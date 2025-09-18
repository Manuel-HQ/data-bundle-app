#!/usr/bin/env python3
# -*- coding:utf-8 -*-
"""
app.py

Flask Web Application for a Data Bundle Sales Platform.

This application manages:
- User registration, login, and profile updates
- Wallet top-ups via Paystack (initialize + verify)
- Data bundle purchases that deduct from user wallet balances
- Admin purchase confirmation flow
- Persistence using SQLite with SQLAlchemy ORM

Author: Developer Arena
Notes:
- For production, set secrets as environment variables.
- Passwords are hashed using werkzeug.security (do NOT store plaintext).
"""

import os
from datetime import datetime
from typing import Optional

import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import (check_password_hash, generate_password_hash)
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message

# ----------------------
# App configuration
# ----------------------
app = Flask(__name__)

# Secret key (use environment variable in production)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")

# File upload configuration
UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "static/uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif"}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

# Database configuration: default to a local SQLite DB file
db_path = os.environ.get("DATABASE_URL", "sqlite:///data_bundle.db")
app.config["SQLALCHEMY_DATABASE_URI"] = db_path
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)



# Paystack credentials (set in environment for production)
PAYSTACK_SECRET_KEY = os.environ.get(
    "PAYSTACK_SECRET_KEY",
    "sk_test_07157d2784524701ce709d7526e40311caaa38c6",
)
PAYSTACK_PUBLIC_KEY = os.environ.get(
    "PAYSTACK_PUBLIC_KEY",
    "pk_test_5dba95da4545041b0211cab413af0c955f71354f",
)

# Flask-Mail Configuration
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "emmanuelzoryiku344@gmail.com"   # replace with your email
app.config["MAIL_PASSWORD"] = "fajl vldl isoy hkqp"   # replace with your password or app password
app.config["MAIL_DEFAULT_SENDER"] = ("Developers Arena Data Bunble App", "emmanuelzoryiku344@gmail.com")

mail = Mail(app)

# ----------------------
# Database models
# ----------------------


class User(db.Model):
    """
    Database model that represents an application user.

    Attributes:
        id: Primary key.
        username: Display name for the user.
        email: Unique email address used for login.
        mobile: Mobile phone number (string).
        gender: Gender string.
        password_hash: Hashed password (never store plaintext).
        wallet_balance: Float wallet balance in local currency units.
        profile_pic: Filename for uploaded profile picture (optional).
        purchases: Relationship to Purchase records.
        transactions: Relationship to Transaction records.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    mobile = db.Column(db.String(50), nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    password_hash = db.Column(db.String(200), nullable=False)
    wallet_balance = db.Column(db.Float, default=0.0)
    profile_pic = db.Column(db.String(300), nullable=True)

    purchases = db.relationship("Purchase", backref="user", lazy=True)
    transactions = db.relationship("Transaction", backref="user", lazy=True)

    def set_password(self, password: str) -> None:
        """Hash and set the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Return True if the provided password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<User {self.email}>"


class Purchase(db.Model):
    """
    Database model representing a bundle purchase.

    Attributes:
        id: Primary key.
        provider: Network/provider name (e.g., MTN).
        bundle: Bundle description (e.g., '1 GB - 5.40 GHS').
        number: Recipient phone number.
        amount: Amount charged for this purchase.
        created_at: Timestamp of creation (UTC).
        status: Status string (payment_completed, credited, etc.).
        user_id: Foreign key to the User who made the purchase.
    """

    __tablename__ = "purchases"

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(100), nullable=True)
    bundle = db.Column(db.String(200), nullable=False)
    number = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(50), default="payment_completed")
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    def created_at_str(self) -> str:
        """Return a formatted timestamp string for templates."""
        return self.created_at.strftime("%Y-%m-%d %H:%M:%S")


class PendingPayment(db.Model):
    """
    Temporary storage for pending wallet top-up transactions (Paystack).

    Attributes:
        id: Primary key.
        email: Email of user initiating the top-up.
        amount: Amount to credit on success.
        provider: Provider chosen for top-up (for record).
        number: Mobile number attached to top-up.
        reference: Paystack transaction reference.
        created_at: Timestamp of initialization.
    """

    __tablename__ = "pending_payments"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    provider = db.Column(db.String(100), nullable=True)
    number = db.Column(db.String(50), nullable=True)
    reference = db.Column(db.String(200), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Transaction(db.Model):
    """
    Record of a completed wallet transaction (top-up).

    Attributes:
        id: Primary key.
        amount: Amount credited.
        provider: Provider used (for reference).
        number: Phone number recorded.
        reference: External reference (Paystack).
        status: Status string (e.g., success).
        at: Timestamp of completion.
        user_id: ForeignKey to User.
    """

    __tablename__ = "transactions"

    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    provider = db.Column(db.String(100), nullable=True)
    number = db.Column(db.String(50), nullable=True)
    reference = db.Column(db.String(200), nullable=True)
    status = db.Column(db.String(50), nullable=True)
    at = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    def at_str(self) -> str:
        """Return a formatted timestamp string for templates."""
        return self.at.strftime("%Y-%m-%d %H:%M:%S")


# Create tables if they don't exist
with app.app_context():
    db.create_all()


# ----------------------
# Helper utilities
# ----------------------
def allowed_file(filename: str) -> bool:
    """
    Determine whether the uploaded filename has an allowed extension.

    Args:
        filename: Uploaded filename.

    Returns:
        True if extension is allowed, otherwise False.
    """
    if not filename:
        return False
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def now_str() -> str:
    """
    Return the current UTC time as a formatted string.

    Returns:
        formatted timestamp string.
    """
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")


def current_user() -> Optional[User]:
    """
    Return the currently logged-in user (or None).

    Uses session['email'] to look up the user in the DB.
    """
    email = session.get("email")
    if not email:
        return None
    return User.query.filter_by(email=email).first()


# ----------------------
# Routes (public)
# ----------------------
@app.route("/")
def home():
    """
    Landing page.

    Renders the landing page template with the current year.
    """
    return render_template("landing.html", current_year=datetime.utcnow().year)


@app.route("/register", methods=("GET", "POST"))
def register():
    """
    Handle user registration.

    Validates form input, prevents duplicate emails, hashes the password,
    and creates a new User record.
    """
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        mobile = request.form.get("mobile", "").strip()
        gender = request.form.get("gender", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Validate passwords match
        if password != confirm_password:
            return render_template("register.html", error="Passwords do not match")

        # Prevent duplicate emails
        if User.query.filter_by(email=email).first():
            return render_template("register.html", error="Email already registered")

        # Create user with hashed password
        user = User(username=username, email=email, mobile=mobile, gender=gender)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()

        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=("GET", "POST"))
def login():
    """
    Authenticate user and create a session.

    Passwords are validated against a secure hash.
    """
    error = None
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            # Store minimal info in session
            session["email"] = user.email
            session["username"] = user.username
            return redirect(url_for("dashboard"))

        error = "Invalid email or password"

    return render_template("login.html", error=error)


@app.route("/dashboard")
def dashboard():
    """
    User dashboard showing purchases and wallet balance.

    Redirects to login for anonymous users.
    """
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    purchases = Purchase.query.filter_by(user_id=user.id).order_by(
        Purchase.created_at.desc()
    ).all()
    return render_template(
        "dashboard.html", username=user.username, purchases=purchases, balance=user.wallet_balance
    )


@app.route("/purchase", methods=("GET", "POST"))
def purchase():
    """
    Handle bundle purchase requests.

    - Validates bundle price
    - Ensures sufficient wallet balance
    - Creates a Purchase record and deducts the user's wallet
    """
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        network = request.form.get("network", "").strip()
        bundle = request.form.get("bundle", "").strip()
        mobile = request.form.get("mobile", "").strip()

        # Parse price from bundle string like "1 GB - 5.40 GHS"
        try:
            price_part = bundle.split("-", 1)[1]  # everything after the first dash
            price_str = price_part.replace("GHS", "").strip()
            amount = float(price_str)
        except (IndexError, ValueError):
            return jsonify({"error": "Invalid bundle format."}), 400

        if user.wallet_balance < amount:
            return jsonify({"error": "Insufficient wallet balance", "balance": float(user.wallet_balance)}), 400

        # Deduct wallet and create purchase
        user.wallet_balance = round(user.wallet_balance - amount, 2)
        purchase = Purchase(
            provider=network,
            bundle=bundle,
            number=mobile,
            amount=amount,
            created_at=datetime.utcnow(),
            status="payment_completed",
            user_id=user.id,
        )
        db.session.add(purchase)
        db.session.commit()

        # AJAX/fetch support
        if request.headers.get("X-Requested-With") == "fetch":
            return jsonify({"ok": True, "id": purchase.id})

        return redirect(url_for("dashboard"))

    # GET
    return render_template("purchase.html", username=user.username, balance=user.wallet_balance)


@app.route("/faq")
def faq():
    """Render FAQ page."""
    return render_template("FAQ.html")


@app.route("/landing")
def landing():
    """Render landing page (alternate route)."""
    return render_template("landing.html")



# ---------------- Contact Route ---------------- #
@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message_body = request.form.get("message")

        # Build the email message
        msg = Message(
            subject=f"New Contact Message from {name}",
            recipients=["your_email@gmail.com"],  # replace with where you want to receive messages
            body=f"From: {name} <{email}>\n\nMessage:\n{message_body}"
        )
        try:
            mail.send(msg)
            flash("✅ Your message has been sent successfully!", "success")
        except Exception as e:
            flash("❌ Failed to send your message. Please try again later.", "danger")
            print("Mail error:", e)

        return redirect(url_for("contact"))

    return render_template("contact.html")


# ----------------------
# Admin routes
# ----------------------
@app.route("/admin")
def admin_panel():
    """
    Admin panel that lists all purchases.

    NOTE: This route has no authentication. In production add admin auth!
    """
    purchases = Purchase.query.order_by(Purchase.id.desc()).all()
    return render_template("admin.html", purchases=purchases)


@app.route("/admin/confirm/<int:pid>", methods=("POST",))
def admin_confirm(pid: int):
    """
    Admin endpoint to mark a purchase as 'credited'.

    Accepts POST only. Returns JSON for AJAX or redirect for browser.
    """
    purchase = Purchase.query.get(pid)
    if not purchase:
        return jsonify({"error": "Purchase not found"}), 404

    purchase.status = "credited"
    db.session.commit()

    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"ok": True})
    return redirect(url_for("admin_panel"))


# ----------------------
# Wallet & Paystack integration
# ----------------------
@app.route("/wallet")
def wallet():
    """
    Show wallet page with current balance and Paystack public key.

    Accepts optional 'email' query param for admin-like views.
    """
    email = request.args.get("email") or session.get("email")
    if not email:
        return redirect(url_for("login"))

    user = User.query.filter_by(email=email).first()
    if not user:
        return redirect(url_for("logout"))

    return render_template("wallet.html", user=user, paystack_public_key=PAYSTACK_PUBLIC_KEY)


@app.route("/initiate_payment", methods=("POST",))
def initiate_payment():
    """
    Initialize a Paystack transaction for a wallet top-up.

    Stores a PendingPayment record and redirects the user to Paystack's
    authorization URL. Expects 'amount', 'provider', and 'number' in the form.
    """
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    amount = request.form.get("amount")
    provider = request.form.get("provider")
    number = request.form.get("number")

    # Build Paystack initialize request
    try:
        amount_kobo = int(float(amount) * 100)
    except (TypeError, ValueError):
        return "Invalid amount", 400

    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}", "Content-Type": "application/json"}
    data = {"email": user.email, "amount": amount_kobo, "callback_url": url_for("verify_payment", _external=True)}

    response = requests.post("https://api.paystack.co/transaction/initialize", headers=headers, json=data)
    try:
        res = response.json()
    except ValueError:
        return "Invalid response from Paystack", 502

    if res.get("status"):
        reference = res["data"]["reference"]
        authorization_url = res["data"]["authorization_url"]

        # Create pending payment record
        pending = PendingPayment(
            email=user.email,
            amount=float(amount),
            provider=provider,
            number=number,
            reference=reference,
            created_at=datetime.utcnow(),
        )
        db.session.add(pending)
        db.session.commit()

        # Redirect user to Paystack's payment page
        return redirect(authorization_url)

    # Error initializing payment
    return f"Error initializing payment: {res.get('message', 'Unknown error')}", 500


@app.route("/verify_payment")
def verify_payment():
    """
    Paystack callback / verification URL.

    Verifies the transaction reference, credits the user's wallet on success,
    creates a Transaction record, and removes the PendingPayment record.
    """
    reference = request.args.get("reference")
    if not reference:
        return "Missing payment reference.", 400

    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    response = requests.get(f"https://api.paystack.co/transaction/verify/{reference}", headers=headers)
    try:
        res = response.json()
    except ValueError:
        return "Invalid response from Paystack", 502

    # Check success status from Paystack
    if res.get("status") and res.get("data", {}).get("status") == "success":
        pending = PendingPayment.query.filter_by(reference=reference).first()
        if not pending:
            return "No matching pending payment found.", 404

        user = User.query.filter_by(email=pending.email).first()
        if not user:
            return "User not found.", 404

        # Credit wallet and record a transaction
        user.wallet_balance = round(user.wallet_balance + pending.amount, 2)
        transaction = Transaction(
            amount=pending.amount,
            provider=pending.provider,
            number=pending.number,
            reference=reference,
            status="success",
            at=datetime.utcnow(),
            user_id=user.id,
        )

        db.session.add(transaction)
        db.session.delete(pending)  # remove pending record now that transaction is complete
        db.session.commit()

        return redirect(url_for("wallet", email=user.email))

    return "Payment verification failed.", 400


# ----------------------
# Profile routes
# ----------------------
@app.route("/profile", methods=("GET", "POST"))
def profile():
    """
    View and update the currently logged-in user's profile.

    Supports username, email, mobile, gender, password, and profile picture upload.
    """
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    if request.method == "POST":
        new_username = request.form.get("username", "").strip()
        new_email = request.form.get("email", "").strip().lower()
        new_mobile = request.form.get("mobile", "").strip()
        new_gender = request.form.get("gender", "").strip()
        new_password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        # Password update validations
        if new_password and new_password != confirm_password:
            return render_template("profile.html", user=user, error="Passwords do not match")

        # Prevent email conflicts
        if new_email != user.email and User.query.filter_by(email=new_email).first():
            return render_template("profile.html", user=user, error="This email is already in use")

        # Apply updates
        user.username = new_username or user.username
        user.email = new_email or user.email
        user.mobile = new_mobile or user.mobile
        user.gender = new_gender or user.gender
        if new_password:
            user.set_password(new_password)

        # Update session to reflect email/username changes
        session["email"] = user.email
        session["username"] = user.username

        # Handle profile picture upload
        if "profile_pic" in request.files:
            file = request.files["profile_pic"]
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
                file.save(filepath)

                # Delete old pic file if present and different
                if user.profile_pic and user.profile_pic != filename:
                    old_path = os.path.join(app.config["UPLOAD_FOLDER"], user.profile_pic)
                    try:
                        if os.path.exists(old_path):
                            os.remove(old_path)
                    except Exception:
                        # Do not crash on file deletion errors; log in production
                        pass

                user.profile_pic = filename

        db.session.commit()
        return render_template("profile.html", user=user, message="Profile updated successfully")

    # GET
    return render_template("profile.html", user=user)

@app.route("/delete_purchase/<int:purchase_id>", methods=("POST", "GET"))
def delete_purchase(purchase_id):
    """
    Delete a purchase record by its ID.

    Args:
        purchase_id (int): The ID of the purchase to delete.

    Returns:
        Redirect: Back to the admin panel after deletion.
    """
    purchase = Purchase.query.get(purchase_id)
    if not purchase:
        return jsonify({"error": "Purchase not found"}), 404

    db.session.delete(purchase)
    db.session.commit()

    return redirect(url_for("admin_panel"))


@app.route("/credit_purchase/<int:purchase_id>", methods=("POST", "GET"))
def credit_purchase(purchase_id):
    """
    Mark a purchase as credited.

    Args:
        purchase_id (int): The ID of the purchase to credit.

    Returns:
        Redirect: Back to the admin panel after update.
    """
    purchase = Purchase.query.get(purchase_id)
    if not purchase:
        return jsonify({"error": "Purchase not found"}), 404

    purchase.status = "credited"
    db.session.commit()

    return redirect(url_for("admin_panel"))

@app.route("/confirm_purchase/<int:purchase_id>", methods=("POST", "GET"))
def confirm_purchase(purchase_id):
    """
    Confirm a purchase by updating its status to 'confirmed'.

    Args:
        purchase_id (int): The ID of the purchase to confirm.

    Returns:
        Redirect: Back to the admin panel after confirmation.
    """
    purchase = Purchase.query.get(purchase_id)
    if not purchase:
        return jsonify({"error": "Purchase not found"}), 404

    purchase.status = "confirmed"
    db.session.commit()

    return redirect(url_for("admin_panel"))

@app.route("/delete_account", methods=("POST",))
def delete_account():
    """
    Delete the currently logged-in user's account and associated profile picture.

    Clears session on completion.
    """
    user = current_user()
    if not user:
        return redirect(url_for("login"))

    # Remove profile picture file if exists
    if user.profile_pic:
        pic_path = os.path.join(app.config["UPLOAD_FOLDER"], user.profile_pic)
        if os.path.exists(pic_path):
            try:
                os.remove(pic_path)
            except Exception:
                # In production, log this error
                pass

    # Delete user and commit
    db.session.delete(user)
    db.session.commit()
    session.clear()
    return redirect(url_for("login"))


@app.route("/logout")
def logout():
    """Clear session and return to landing page."""
    session.clear()
    return redirect(url_for("landing"))


# ----------------------
# API endpoints
# ----------------------
@app.route("/api/wallet_balance")
def api_wallet_balance():
    """
    Return the wallet balance for the currently logged-in user as JSON.

    If no user is logged in, returns 0.0.
    """
    user = current_user()
    return jsonify({"balance": float(user.wallet_balance) if user else 0.0})


# ----------------------
# Utility: import JSON data (optional)
# ----------------------
def import_json_to_db(users_json_path: str, purchases_json_path: str) -> None:
    """
    Optional helper to migrate existing JSON files into the database.

    This function is not run automatically. Call it manually if needed.

    Args:
        users_json_path: Path to existing users.json (list of user dicts).
        purchases_json_path: Path to existing purchases.json (list of purchase dicts).
    """
    import json

    if os.path.exists(users_json_path):
        with open(users_json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            for u in data:
                # Skip if user already exists
                if User.query.filter_by(email=u.get("email")).first():
                    continue
                user = User(
                    username=u.get("username", "user"),
                    email=u.get("email"),
                    mobile=u.get("mobile"),
                    gender=u.get("gender"),
                    wallet_balance=float(u.get("wallet_balance", 0.0)),
                )
                # If JSON stored plaintext password (not ideal), set a hash
                pwd = u.get("password", "change_me")
                user.set_password(pwd)
                db.session.add(user)
            db.session.commit()

    if os.path.exists(purchases_json_path):
        with open(purchases_json_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            for p in data:
                # Find user by email
                user = User.query.filter_by(email=p.get("email")).first()
                if not user:
                    continue
                # Create purchase
                purchase = Purchase(
                    provider=p.get("provider"),
                    bundle=p.get("bundle"),
                    number=p.get("number"),
                    amount=float(p.get("amount", 0.0)),
                    created_at=datetime.strptime(p.get("created_at"), "%Y-%m-%d %H:%M:%S")
                    if p.get("created_at")
                    else datetime.utcnow(),
                    status=p.get("status", "payment_completed"),
                    user_id=user.id,
                )
                db.session.add(purchase)
            db.session.commit()


# ----------------------
# Run app (development)
# ----------------------
if __name__ == "__main__":
    # For local development only. Use a WSGI server for production.
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
