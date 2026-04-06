from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..auth import login_user, logout_user

auth_bp = Blueprint("auth", __name__)

@auth_bp.get("/login")
@auth_bp.post("/login")
def login():
    next_url = request.args.get("next") or request.form.get("next") or ""
    if request.method == "POST":
        ok, _ = login_user(
            (request.form.get("username", "") or "").strip(),
            request.form.get("password", "") or "",
        )
        if ok:
            return redirect(next_url or url_for("inventory.index"))
        flash("Sai tài khoản hoặc mật khẩu / Invalid credentials", "danger")

    return render_template("login.html", next=next_url)

@auth_bp.get("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))