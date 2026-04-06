from functools import wraps
from flask import session, redirect, url_for, flash, request
from werkzeug.security import generate_password_hash, check_password_hash
from .db import get_db

def hash_password(pw: str) -> str:
    # Force PBKDF2 so it works even when hashlib.scrypt is unavailable
    return generate_password_hash(pw, method="pbkdf2:sha256")

def verify_password(pw_hash: str, pw: str) -> bool:
    return check_password_hash(pw_hash, pw)

def login_user(username: str, password: str):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    if not user:
        return False, None
    if not verify_password(user["password_hash"], password):
        return False, None
    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    session.setdefault("cart", [])
    return True, user

def logout_user():
    session.clear()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("auth.login", next=request.path))
        return fn(*args, **kwargs)
    return wrapper

def role_required(*roles):
    def deco(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not session.get("user_id"):
                return redirect(url_for("auth.login"))
            if session.get("role") not in roles:
                flash("Permission denied", "danger")
                return redirect(url_for("inventory.index"))
            return fn(*args, **kwargs)
        return wrapper
    return deco

# --- role helpers (aliases) ---
admin_only = role_required("admin")
admin_or_manager = role_required("admin", "manager")
staff_only = role_required("staff")