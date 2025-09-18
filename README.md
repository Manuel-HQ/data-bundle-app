# 📱 Data Bundle Sales Platform

A Flask-based web application for selling mobile data bundles with wallet integration, user authentication, profile management, and an admin dashboard.  

## ✨ Features
- 🔑 User Registration & Login (session-based authentication)
- 👤 Profile Management (update info, upload profile picture)
- 💰 Wallet System (top up, check balance, use for purchases)
- 📦 Buy Data Bundles (MTN, Vodafone, AirtelTigo, etc.)
- 📜 Transaction History & Dashboard
- 📞 Contact Page with Email Support (Flask-Mail)
- 📊 Admin Panel (view/manage users, transactions)
- 🎨 Clean UI built with **Bootstrap 5** and **Bootstrap Icons**

---

## 🛠 Tech Stack
- **Backend:** Flask (Python 3.11/3.13 compatible)
- **Database:** SQLite with SQLAlchemy ORM
- **Frontend:** HTML, CSS, Bootstrap 5, Bootstrap Icons
- **Email:** Flask-Mail (SMTP with Gmail or other providers)
- **Deployment:** Render / Gunicorn (optional)

---

## 🚀 Installation & Setup

### 1️⃣ Clone the Repository
```bash
git clone https://github.com/Manuel-HQ/data-bundle-app
cd data-bundle-platform
2️⃣ Create Virtual Environment
bash
Copy code
python -m venv venv
Activate it:

Windows (PowerShell):

powershell
Copy code
venv\Scripts\Activate.ps1
Linux / Mac:

bash
Copy code
source venv/bin/activate
3️⃣ Install Dependencies
bash
Copy code
pip install -r requirements.txt
4️⃣ Configure Environment Variables
Create a .env file in the root folder and add:

env
Copy code
SECRET_KEY=your_secret_key_here
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=465
MAIL_USE_SSL=True
MAIL_USERNAME=your_email@gmail.com
MAIL_PASSWORD=your_app_password   # App Password if using Gmail
5️⃣ Run the Application
bash
Copy code
flask run
The app will be available at:
👉 http://127.0.0.1:5000/

📂 Project Structure
csharp
Copy code
data-bundle-platform/
│── app.py              # Main Flask app
│── requirements.txt    # Project dependencies
│── static/             # CSS, JS, images
│── templates/          # HTML templates
│── instance/           # Database (SQLite)
│── venv/               # Virtual environment
📨 Contact Page
Users can send messages via the contact form

Messages are delivered via Flask-Mail to the configured email

⚡ Deployment (Render)
Push code to GitHub

Create a new Render Web Service

Set environment variables in Render dashboard

Add gunicorn to requirements.txt

Use the following start command:

bash
Copy code
gunicorn app:app


👨‍💻 Author

Developed by Developer Arena
Community of Coders 💡