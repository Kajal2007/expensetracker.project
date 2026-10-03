import os
import sqlite3
from datetime import date

from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__)

# Database file sits next to app.py, so the app works from any folder
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, "expense_tracker.db")

CATEGORIES = ["Food", "Transport", "Shopping", "Bills", "Education", "Other"]


# ---------- Database helpers ----------

def get_db_connection():
    """Open a connection. Row factory lets us use row['title'] in templates."""
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    """Create the expenses table if it does not exist yet."""
    connection = get_db_connection()
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            date TEXT NOT NULL,
            note TEXT
        )
        """
    )
    connection.commit()
    connection.close()


# ---------- Calculation helpers (done in Python) ----------

def calculate_total(expenses):
    """Add up the amount of every expense in the list."""
    total = 0
    for expense in expenses:
        total += expense["amount"]
    return total


def calculate_month_total(expenses):
    """Add up expenses whose date starts with the current 'YYYY-MM'."""
    current_month = date.today().strftime("%Y-%m")
    total = 0
    for expense in expenses:
        if expense["date"].startswith(current_month):
            total += expense["amount"]
    return total


def calculate_category_totals(expenses):
    """Return a dictionary like {'Food': 120.5, 'Bills': 300.0, ...}."""
    totals = {category: 0 for category in CATEGORIES}
    for expense in expenses:
        totals[expense["category"]] += expense["amount"]
    return totals


def read_form():
    """Read and clean the form fields. Returns (data, error_message)."""
    title = request.form.get("title", "").strip()
    category = request.form.get("category", "")
    expense_date = request.form.get("date", "")
    note = request.form.get("note", "").strip()

    try:
        amount = float(request.form.get("amount", ""))
    except ValueError:
        return None, "Amount must be a number."

    if not title or not expense_date:
        return None, "Title and date are required."
    if amount <= 0:
        return None, "Amount must be greater than zero."
    if category not in CATEGORIES:
        return None, "Please choose a valid category."

    return (title, amount, category, expense_date, note), None


# ---------- Routes ----------

@app.route("/")
def index():
    """Dashboard: totals and category-wise summary."""
    connection = get_db_connection()
    expenses = connection.execute("SELECT * FROM expenses").fetchall()
    connection.close()

    return render_template(
        "index.html",
        total_records=len(expenses),
        total_expenses=calculate_total(expenses),
        month_total=calculate_month_total(expenses),
        category_totals=calculate_category_totals(expenses),
    )


@app.route("/add", methods=["GET", "POST"])
def add_expense():
    """Show the form (GET) or save a new expense (POST)."""
    if request.method == "POST":
        data, error = read_form()
        if error:
            return render_template(
                "add_expense.html", categories=CATEGORIES,
                today=date.today().isoformat(), error=error, form=request.form,
            )

        connection = get_db_connection()
        connection.execute(
            "INSERT INTO expenses (title, amount, category, date, note) "
            "VALUES (?, ?, ?, ?, ?)",
            data,
        )
        connection.commit()
        connection.close()
        return redirect(url_for("expenses_list"))

    return render_template(
        "add_expense.html", categories=CATEGORIES,
        today=date.today().isoformat(), error=None, form={},
    )


@app.route("/expenses")
def expenses_list():
    """List expenses, with optional search / category / date filters."""
    search = request.args.get("search", "").strip()
    category = request.args.get("category", "")
    filter_date = request.args.get("date", "")

    query = "SELECT * FROM expenses WHERE 1=1"
    params = []

    if search:
        query += " AND title LIKE ?"
        params.append("%" + search + "%")
    if category:
        query += " AND category = ?"
        params.append(category)
    if filter_date:
        query += " AND date = ?"
        params.append(filter_date)

    query += " ORDER BY date DESC, id DESC"

    connection = get_db_connection()
    expenses = connection.execute(query, params).fetchall()
    connection.close()

    return render_template(
        "expenses.html",
        expenses=expenses,
        categories=CATEGORIES,
        search=search,
        selected_category=category,
        filter_date=filter_date,
        shown_total=calculate_total(expenses),
    )


@app.route("/edit/<int:expense_id>", methods=["GET", "POST"])
def edit_expense(expense_id):
    """Show the edit form (GET) or save the changes (POST)."""
    connection = get_db_connection()
    expense = connection.execute(
        "SELECT * FROM expenses WHERE id = ?", (expense_id,)
    ).fetchone()

    if expense is None:
        connection.close()
        return "Expense not found", 404

    if request.method == "POST":
        data, error = read_form()
        if error:
            connection.close()
            return render_template(
                "edit_expense.html", expense=expense,
                categories=CATEGORIES, error=error,
            )

        connection.execute(
            "UPDATE expenses SET title = ?, amount = ?, category = ?, "
            "date = ?, note = ? WHERE id = ?",
            data + (expense_id,),
        )
        connection.commit()
        connection.close()
        return redirect(url_for("expenses_list"))

    connection.close()
    return render_template(
        "edit_expense.html", expense=expense, categories=CATEGORIES, error=None
    )


@app.route("/delete/<int:expense_id>", methods=["POST"])
def delete_expense(expense_id):
    """Delete one expense. POST only, so a link click can't delete by accident."""
    connection = get_db_connection()
    connection.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
    connection.commit()
    connection.close()
    return redirect(url_for("expenses_list"))


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
