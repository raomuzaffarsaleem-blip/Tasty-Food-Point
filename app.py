"""Tasty Food Point: Flask backend.

Run:   python app.py
Open:  http://localhost:5000          (customer site)
       http://localhost:5000/admin    (orders page, password protected)

Set these environment variables before going live:
    ADMIN_USER      default "admin"
    ADMIN_PASSWORD  default "changeme"  (CHANGE THIS)
"""
import json
import os
import re
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from datetime import datetime, timezone

from flask import Flask, Response, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MENU_PATH = os.path.join(BASE_DIR, "menu.json")
DB_PATH = os.environ.get("DB_PATH", os.path.join(BASE_DIR, "orders.db"))
ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme")

STATUSES = ("new", "preparing", "done", "cancelled")
MAX_LINES = 30
MAX_PIECES = 50
MAX_KG = 20
KG_STEP = 0.25

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"), static_url_path="/static")
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024  # orders are tiny; reject big bodies


# ---------- helpers ----------

def load_menu():
    """Read menu.json on every call so price edits apply without a restart."""
    with open(MENU_PATH, encoding="utf-8") as f:
        return json.load(f)


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                customer_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                order_type TEXT NOT NULL,
                address TEXT NOT NULL,
                notes TEXT NOT NULL,
                items_json TEXT NOT NULL,
                total INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'new'
            )"""
        )


_recent = defaultdict(lambda: deque(maxlen=10))


def too_many_orders(ip, limit=5, window=600):
    """Allow at most `limit` orders per IP in `window` seconds."""
    now = time.time()
    q = _recent[ip]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


def require_admin():
    auth = request.authorization
    ok = (
        auth is not None
        and auth.type == "basic"
        and secrets.compare_digest(auth.username or "", ADMIN_USER)
        and secrets.compare_digest(auth.password or "", ADMIN_PASSWORD)
    )
    if ok:
        return None
    return Response(
        "Login required.",
        401,
        {"WWW-Authenticate": 'Basic realm="Tasty Food Point orders"'},
    )


def clean_text(value, max_len):
    return re.sub(r"\s+", " ", str(value or "")).strip()[:max_len]


# ---------- public pages and API ----------

@app.get("/")
def home():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/menu")
def api_menu():
    return jsonify(load_menu())


@app.post("/api/orders")
def api_create_order():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify(error="Send the order as JSON."), 400

    if too_many_orders(request.remote_addr or "unknown"):
        return jsonify(error="Too many orders from this device. Please call us to order."), 429

    errors = {}

    name = clean_text(data.get("name"), 60)
    if len(name) < 2:
        errors["name"] = "Enter your name."

    phone_raw = clean_text(data.get("phone"), 20)
    digits = re.sub(r"\D", "", phone_raw)
    if not (10 <= len(digits) <= 13):
        errors["phone"] = "Enter a phone number we can call, for example 0300 1234567."

    order_type = data.get("order_type")
    if order_type not in ("delivery", "pickup"):
        errors["order_type"] = "Choose delivery or pickup."

    address = clean_text(data.get("address"), 200)
    if order_type == "delivery" and len(address) < 5:
        errors["address"] = "Enter the address for delivery."
    if order_type == "pickup":
        address = ""

    notes = clean_text(data.get("notes"), 300)

    menu = load_menu()
    by_id = {item["id"]: item for item in menu["items"]}
    lines = data.get("items")
    clean_lines = []
    total = 0

    if not isinstance(lines, list) or not lines:
        errors["items"] = "Add at least one item to your order."
    elif len(lines) > MAX_LINES:
        errors["items"] = "That is too many different items. Please call us to order."
    else:
        seen = set()
        for line in lines:
            item = by_id.get(line.get("id")) if isinstance(line, dict) else None
            if item is None or item["id"] in seen:
                errors["items"] = "Your cart has an item that is no longer on the menu. Refresh the page."
                break
            seen.add(item["id"])
            try:
                qty = float(line.get("qty"))
            except (TypeError, ValueError):
                errors["items"] = "One of the quantities is not valid."
                break

            if item["unit"] == "kg":
                valid = 0 < qty <= MAX_KG and abs(qty / KG_STEP - round(qty / KG_STEP)) < 1e-9
            else:
                valid = 0 < qty <= MAX_PIECES and qty == int(qty)
            if not valid:
                errors["items"] = f"The quantity for {item['name']} is not valid."
                break

            # Price always comes from menu.json, never from the browser.
            line_total = int(round(item["price"] * qty))
            total += line_total
            clean_lines.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "note": item.get("note", ""),
                    "unit": item["unit"],
                    "price": item["price"],
                    "qty": qty,
                    "line_total": line_total,
                }
            )

    if errors:
        return jsonify(error="Please fix the highlighted fields.", fields=errors), 400

    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO orders
               (created_at, customer_name, phone, order_type, address, notes, items_json, total)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (created_at, name, phone_raw, order_type, address, notes, json.dumps(clean_lines), total),
        )
        order_id = cur.lastrowid

    return jsonify(ok=True, order_id=order_id, total=total), 201


# ---------- admin ----------

@app.get("/admin")
def admin_page():
    denied = require_admin()
    if denied:
        return denied
    return send_from_directory(BASE_DIR, "admin.html")


@app.get("/api/admin/orders")
def admin_orders():
    denied = require_admin()
    if denied:
        return denied
    with db() as conn:
        rows = conn.execute("SELECT * FROM orders ORDER BY id DESC LIMIT 200").fetchall()
    orders = []
    for r in rows:
        o = dict(r)
        o["items"] = json.loads(o.pop("items_json"))
        orders.append(o)
    return jsonify(orders=orders)


@app.post("/api/admin/orders/<int:order_id>/status")
def admin_set_status(order_id):
    denied = require_admin()
    if denied:
        return denied
    data = request.get_json(silent=True) or {}
    status = data.get("status")
    if status not in STATUSES:
        return jsonify(error="Unknown status."), 400
    with db() as conn:
        cur = conn.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    if cur.rowcount == 0:
        return jsonify(error="Order not found."), 404
    return jsonify(ok=True)


init_db()

if __name__ == "__main__":
    if ADMIN_PASSWORD == "changeme":
        print("WARNING: set ADMIN_PASSWORD before putting this site online.")
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
