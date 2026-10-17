
import os
from datetime import date, datetime

from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin, login_user,
    login_required, logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "local-development-key-change-before-deployment"
)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///expense_tracker.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


# Database models

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)


class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False
    )
    title = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    kind = db.Column(db.String(10), nullable=False)
    transaction_date = db.Column(db.Date, nullable=False)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Authentication pages

@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            error = "Please fill in all fields."
        elif len(password) < 8:
            error = "Password must contain at least 8 characters."
        elif User.query.filter_by(email=email).first():
            error = "An account with this email already exists."
        else:
            user = User(
                username=username,
                email=email,
                password=generate_password_hash(password)
            )
            db.session.add(user)
            db.session.commit()

            login_user(user)
            return redirect(url_for("dashboard"))

    return render_template("register.html", error=error)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    error = None

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("dashboard"))

        error = "Invalid email or password."

    return render_template("login.html", error=error)


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# Dashboard

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template(
        "dashboard.html", username=current_user.username
    )


# Transaction APIs

@app.route("/api/transactions", methods=["GET", "POST"])
@login_required
def transactions():
    if request.method == "POST":
        data = request.get_json(silent=True) or {}

        title = str(data.get("title", "")).strip()
        category = str(data.get("category", "")).strip()
        kind = data.get("kind")
        raw_amount = data.get("amount")
        raw_date = data.get("date")

        allowed_categories = {
            "Food", "Travel", "Shopping", "Bills",
            "Health", "Education", "Entertainment", "Salary", "Other"
        }

        if not title or len(title) > 120:
            return jsonify(error="Enter a valid transaction title."), 400

        if category not in allowed_categories:
            return jsonify(error="Choose a valid category."), 400

        if kind not in {"income", "expense"}:
            return jsonify(error="Choose income or expense."), 400

        try:
            amount = float(raw_amount)
            transaction_date = date.fromisoformat(raw_date)
        except (ValueError, TypeError):
            return jsonify(error="Enter a valid amount and date."), 400

        if not (0 < amount <= 1000000000):
            return jsonify(error="Amount must be greater than zero."), 400

        item = Transaction(
            user_id=current_user.id,
            title=title,
            amount=amount,
            category=category,
            kind=kind,
            transaction_date=transaction_date
        )

        db.session.add(item)
        db.session.commit()

        return jsonify(message="Transaction added successfully."), 201

    items = Transaction.query.filter_by(
        user_id=current_user.id
    ).order_by(
        Transaction.transaction_date.desc(),
        Transaction.id.desc()
    ).all()

    return jsonify([
        {
            "id": item.id,
            "title": item.title,
            "amount": item.amount,
            "category": item.category,
            "kind": item.kind,
            "date": item.transaction_date.isoformat()
        }
        for item in items
    ])


@app.route("/api/transactions/<int:transaction_id>", methods=["DELETE"])
@login_required
def delete_transaction(transaction_id):
    item = db.session.get(Transaction, transaction_id)

    if not item or item.user_id != current_user.id:
        return jsonify(error="Transaction not found."), 404

    db.session.delete(item)
    db.session.commit()

    return jsonify(message="Transaction deleted.")


@app.route("/api/summary")
@login_required
def summary():
    items = Transaction.query.filter_by(
        user_id=current_user.id
    ).all()

    today = date.today()
    monthly = [
        item for item in items
        if item.transaction_date.year == today.year
        and item.transaction_date.month == today.month
    ]

    income = sum(
        item.amount for item in items if item.kind == "income"
    )
    expenses = sum(
        item.amount for item in items if item.kind == "expense"
    )
    month_expenses = sum(
        item.amount for item in monthly if item.kind == "expense"
    )
    month_income = sum(
        item.amount for item in monthly if item.kind == "income"
    )

    categories = {}
    for item in monthly:
        if item.kind == "expense":
            categories[item.category] = (
                categories.get(item.category, 0) + item.amount
            )

    highest = max(categories, key=categories.get) if categories else None

    if not categories:
        insight = "Add an expense to see your spending insights."
    elif month_income > 0 and month_expenses > month_income:
        insight = "Your expenses exceed this month's income. Review your spending."
    elif highest:
        share = categories[highest] / month_expenses * 100
        insight = (
            f"{highest} is your top spending category this month "
            f"({share:.0f}% of expenses)."
        )
    else:
        insight = "No expenses recorded this month yet."

    return jsonify({
        "total_income": round(income, 2),
        "total_expenses": round(expenses, 2),
        "balance": round(income - expenses, 2),
        "month_income": round(month_income, 2),
        "month_expenses": round(month_expenses, 2),
        "categories": categories,
        "insight": insight
    })


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
