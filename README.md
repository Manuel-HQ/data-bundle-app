Flask Data Bundle Platform 💻📱

A simple Flask-based web application for selling data bundles with wallet integration.
Users can register, log in, top up their wallet, and purchase bundles.
Built with Flask, Bootstrap, and JSON file storage for persistence.

🚀 Features

🔐 User registration & login

👛 Wallet system (top-up & spend)

📱 Buy data bundles with confirmation modal

🗂 Persistent storage with JSON files

📊 User dashboard with recent transactions

🎨 Clean Bootstrap styling with icons

📂 Project Structure
project/
│── app.py                # Main Flask app
│── requirements.txt       # Dependencies
│── runtime.txt            # Python version for Render
│── static/                # CSS, JS, Images
│── templates/             # HTML files (Bootstrap styled)
│── data/                  # JSON files for users, wallets, transactions
│── README.md              # Project documentation

⚙️ Installation (Local Setup)

Clone this repository:

git clone https://github.com/your-username/your-repo.git
cd your-repo


Create and activate a virtual environment:

python -m venv venv
source venv/bin/activate   # On Mac/Linux
venv\Scripts\activate      # On Windows


Install dependencies:

pip install -r requirements.txt


Run the Flask app:

python app.py


Open in browser:

http://127.0.0.1:5000

🌐 Deployment on Render

Push your project to GitHub.

Go to Render
.

Create a new Web Service and connect your repo.

Set:

Build Command:

pip install -r requirements.txt


Start Command:

gunicorn app:app


Environment:
Python runtime.txt → python-3.11.9

Deploy 🎉

📦 Requirements

Python 3.11.9

Flask

Gunicorn (for Render)

Bootstrap (CDN included in templates)

Install all with:

pip install -r requirements.txt

✨ Future Improvements

📧 Email confirmation for transactions

🏦 Integration with real payment APIs

📊 Admin dashboard for sales overview

🌙 Dark mode toggle

👨‍💻 Author

Developed by Emmanuel (Manuel-HQ) 🚀
Community of Coders 💡
