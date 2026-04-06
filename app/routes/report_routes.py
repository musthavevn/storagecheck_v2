from flask import Blueprint, render_template, request, session
from ..auth import login_required, admin_or_manager
from ..services.reports import get_date_range, summary_totals
from ..db import get_db

report_bp = Blueprint("report", __name__)

@report_bp.get("/report/summary")
@admin_or_manager
def report_summary():
    period = request.args.get("period", "month")
    tu_ngay = request.args.get("tu_ngay", "")
    den_ngay = request.args.get("den_ngay", "")
    start, end = get_date_range(period, tu_ngay, den_ngay)

    totals = summary_totals(start, end, None)
    tong_chi_phi = float(totals["tong_vc"]) + float(totals["tong_hh"]) + float(totals["tong_khac"])
    loi_nhuan = float(totals["tong_ban"]) - float(totals["tong_von"]) - tong_chi_phi

    return render_template(
        "report_summary.html",
        period=period,
        start=start,
        end=end,
        totals=totals,
        tong_chi_phi=tong_chi_phi,
        loi_nhuan=loi_nhuan,
    )

@report_bp.get("/report/mine")
@login_required
def report_mine():
    period = request.args.get("period", "month")
    tu_ngay = request.args.get("tu_ngay", "")
    den_ngay = request.args.get("den_ngay", "")
    start, end = get_date_range(period, tu_ngay, den_ngay)

    totals = summary_totals(start, end, int(session["user_id"]))
    tong_chi_phi = float(totals["tong_vc"]) + float(totals["tong_hh"]) + float(totals["tong_khac"])
    tong_thu = float(totals["tong_ban"]) + tong_chi_phi

    return render_template(
        "report_staff.html",
        period=period,
        start=start,
        end=end,
        totals=totals,
        tong_chi_phi=tong_chi_phi,
        tong_thu=tong_thu,
    )

@report_bp.get("/report/price-history")
@admin_or_manager
def report_price_history():
    db = get_db()

    limit = int(request.args.get("limit", 200))
    if limit < 50:
        limit = 50
    if limit > 1000:
        limit = 1000

    rows = db.execute(
        """
        SELECT ph.changed_at,
               ph.product_id,
               ph.product_name,
               ph.old_cost,
               ph.new_cost,
               ph.old_sell_price,
               ph.new_sell_price,
               u.username
        FROM price_history ph
        LEFT JOIN users u ON u.id = ph.changed_by
        ORDER BY ph.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    return render_template("report_price_history.html", rows=rows, limit=limit)
def report_activity():
    db = get_db()

    limit = int(request.args.get("limit", 200))
    if limit < 50:
        limit = 50
    if limit > 1000:
        limit = 1000

    rows = db.execute(
        """
        SELECT a.created_at,
               a.action,
               a.entity_type,
               a.entity_id,
               a.detail,
               u.username
        FROM audit_logs a
        LEFT JOIN users u ON u.id = a.actor_user_id
        ORDER BY a.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    return render_template("report_activity.html", rows=rows, limit=limit)