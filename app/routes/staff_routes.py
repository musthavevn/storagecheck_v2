from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..auth import admin_or_manager, admin_only, hash_password
from ..db import get_db

staff_bp = Blueprint("staff", __name__)

@staff_bp.get("/staff")
@staff_bp.post("/staff")
@admin_or_manager
def staff_page():
    db = get_db()
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        pw = request.form.get("password") or ""
        role = request.form.get("role") or "staff"
        if not username or not pw:
            flash("Missing username/password", "danger")
            return redirect(url_for("staff.staff_page"))
        try:
            db.execute(
                "INSERT INTO users(username,password_hash,role) VALUES (?,?,?)",
                (username, hash_password(pw), role),
            )
            db.commit()
            flash("Created user", "success")
        except Exception as e:
            db.rollback()
            flash(f"Create failed: {e}", "danger")
        return redirect(url_for("staff.staff_page"))

    users = db.execute(
        "SELECT id,username,role,created_at FROM users ORDER BY id DESC"
    ).fetchall()
    return render_template("staff.html", users=users)

@staff_bp.post("/staff/<int:user_id>/role")
@admin_or_manager
def staff_set_role(user_id: int):
    role = request.form.get("role") or "staff"
    db = get_db()
    db.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    db.commit()
    flash("Updated role", "success")
    return redirect(url_for("staff.staff_page"))

@staff_bp.post("/staff/<int:user_id>/reset-pass")
@admin_or_manager
def staff_reset_pass(user_id: int):
    pw = request.form.get("password") or ""
    if not pw:
        flash("Password required", "danger")
        return redirect(url_for("staff.staff_page"))
    db = get_db()
    db.execute(
        "UPDATE users SET password_hash=? WHERE id=?",
        (hash_password(pw), user_id),
    )
    db.commit()
    flash("Reset password OK", "success")
    return redirect(url_for("staff.staff_page"))

@staff_bp.get("/staff/<int:user_id>/delete")
@admin_only
def staff_delete(user_id: int):
    db = get_db()
    db.execute("DELETE FROM users WHERE id=? AND username<>'admin'", (user_id,))
    db.commit()
    flash("Deleted (except admin)", "success")
    return redirect(url_for("staff.staff_page"))