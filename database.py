import sqlite3
import uuid

from expenses import Expense

DB_PATH = "budget.db"


def load_connection(db_path: str = DB_PATH) -> sqlite3.Connection | None:
    try:
        conn = sqlite3.connect(db_path)
        return conn
    except sqlite3.OperationalError as e:
        print("Failed to open database: ", e)
        return None


def create_tables(conn: sqlite3.Connection) -> None:
    create_table_statements = [
        """CREATE TABLE IF NOT EXISTS expenses (
        id TEXT PRIMARY KEY,
        amount REAL NOT NULL,
        category TEXT NOT NULL,
        label TEXT
      );""",
    ]

    try:
        cursor = conn.cursor()

        for statement in create_table_statements:
            cursor.execute(statement)

        conn.commit()
        print("Tables created successfully")
    except sqlite3.OperationalError as e:
        print("Failed to create tables: ", e)


def add_expense(conn: sqlite3.Connection, expense: Expense) -> None:
    sql = """INSERT INTO expenses(id, amount, category, label) VALUES (?, ?, ?, ?)"""
    try:
        cursor = conn.cursor()

        expense_id = str(uuid.uuid4())

        cursor.execute(
            sql, (expense_id, expense.amount, expense.category, expense.label)
        )
        conn.commit()

        print("Expense added successfully")
    except sqlite3.OperationalError as e:
        print("Failed to add expense:", e)


def get_all_expenses(conn: sqlite3.Connection) -> list[Expense]:
    conn.row_factory = sqlite3.Row
    sql = """SELECT amount, label, category FROM expenses"""
    try:
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()

        return [Expense.from_dict(dict(row)) for row in rows]
    except sqlite3.OperationalError as e:
        print("Failed to fetch expenses:", e)
        return []
