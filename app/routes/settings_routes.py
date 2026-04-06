import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from werkzeug.utils import secure_filename

from ..auth import admin_or_manager, login_required
from ..db import get_db

settings_bp = Blueprint("settings", __name__)

def _audit(db, action, entity_type, entity_id=None, detail=""):
    actor = int(session.get("user_id") or 0) or None
    db.execute(
        "INSERT INTO audit_logs(actor_user_id,action,entity_type,entity_id,detail) VALUES (?,?,?,?,?)",
        (actor, action, entity_type, entity_id, detail or ""),
    )

@settings_bp.get("/settings")
@login_required
@admin_or_manager
def settings():
    db = get_db()
    s = db.execute("SELECT * FROM settings WHERE id=1").fetchone()
    return render_template("settings.html", s=s)

@settings_bp.post("/settings/save")
@login_required
@admin_or_manager
def settings_save():
    db = get_db()
    s = db.execute("SELECT * FROM settings WHERE id=1").fetchone()
    if not s:
        flash("Settings not found", "danger")
        return redirect(url_for("settings.settings"))

    theme_primary = (request.form.get("theme_primary") or "#0d6efd").strip()
    theme_section_bg = (request.form.get("theme_section_bg") or "#f8f9fa").strip()
    theme_section_border = (request.form.get("theme_section_border") or "#e9ecef").strip()

    try:
        db.execute(
            """UPDATE settings
               SET theme_primary=?,
                   theme_section_bg=?,
                   theme_section_border=?
               WHERE id=1""",
            (theme_primary, theme_section_bg, theme_section_border),
        )
        _audit(
            db,
            action="SETTINGS_UPDATE",
            entity_type="setting",
            entity_id=1,
            detail=f"theme_primary={theme_primary}; theme_section_bg={theme_section_bg}; theme_section_border={theme_section_border}",
        )
        db.commit()
        flash("Settings saved", "success")
    except Exception as e:
        db.rollback()
        flash(f"Save settings failed: {e}", "danger")

    return redirect(url_for("settings.settings"))

@settings_bp.post("/settings/banner/upload")
@login_required
@admin_or_manager
def banner_upload():
    db = get_db()
    f = request.files.get("banner_file")
    if not f or not f.filename:
        flash("No file selected", "danger")
        return redirect(url_for("settings.settings"))

    filename = secure_filename(f.filename)
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        flash("Only .jpg/.jpeg/.png/.webp are allowed", "danger")
        return redirect(url_for("settings.settings"))

    upload_dir = os.path.join(current_app.instance_path, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    # Stable name -> always overwrite old banner
    save_name = "banner" + ext
    save_path = os.path.join(upload_dir, save_name)

    try:
        f.save(save_path)
        rel_path = f"uploads/{save_name}"

        # Clear base64 to avoid big DB + request limit issues
        db.execute("UPDATE settings SET banner_path=?, banner_b64='' WHERE id=1", (rel_path,))
        _audit(db, "BANNER_UPLOAD", "setting", 1, f"path={rel_path}; size_bytes={os.path.getsize(save_path)}")
        db.commit()

        flash("Banner uploaded", "success")
    except Exception as e:
        db.rollback()
        flash(f"Upload failed: {e}", "danger")

    return redirect(url_for("settings.settings"))

@settings_bp.post("/settings/banner/remove")
@login_required
@admin_or_manager
def banner_remove():
    db = get_db()
    s = db.execute("SELECT * FROM settings WHERE id=1").fetchone()
    if not s:
        flash("Settings not found", "danger")
        return redirect(url_for("settings.settings"))

    # Try delete file if exists
    try:
        banner_path = (s["banner_path"] or "").strip()
        if banner_path:
            abs_path = os.path.join(current_app.instance_path, banner_path)
            if os.path.exists(abs_path):
                os.remove(abs_path)
    except Exception:
        pass

    try:
        db.execute("UPDATE settings SET banner_b64='', banner_path='' WHERE id=1")
        _audit(db, "BANNER_REMOVE", "setting", 1, "cleared banner_b64 and banner_path")
        db.commit()
        flash("Banner removed", "warning")
    except Exception as e:
        db.rollback()
        flash(f"Remove banner failed: {e}", "danger")

    return redirect(url_for("settings.settings"))