from datetime import date, datetime, timedelta
from typing import Optional
from ..db import get_db

def get_date_range(period: str, tu_ngay: str = "", den_ngay: str = ""):
    today = date.today()
    if period == "today":
        start = end = today
    elif period == "month":
        start, end = today.replace(day=1), today
    elif period == "6months":
        start, end = today - timedelta(days=183), today
    elif period == "12months":
        start, end = today - timedelta(days=365), today
    elif period == "year":
        start, end = date(today.year, 1, 1), today
    elif period == "custom" and tu_ngay and den_ngay:
        start = datetime.strptime(tu_ngay, "%Y-%m-%d").date()
        end = datetime.strptime(den_ngay, "%Y-%m-%d").date()
    else:
        start, end = today.replace(day=1), today
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

def summary_totals(start: str, end: str, created_by: Optional[int] = None):
    db = get_db()
    if created_by is not None:
        q = """
        SELECT
          COUNT(DISTINCT s.id) AS so_phieu,
          COALESCE(SUM(i.qty*i.unit_price),0) AS tong_ban,
          COALESCE(SUM(i.qty*i.unit_cost),0) AS tong_von,
          COALESCE(SUM(s.shipping_cost),0) AS tong_vc,
          COALESCE(SUM(s.commission),0) AS tong_hh,
          COALESCE(SUM(s.other_cost),0) AS tong_khac
        FROM sales s
        JOIN sale_items i ON i.sale_id=s.id
        WHERE date(s.created_at) BETWEEN ? AND ? AND s.created_by=?
        """
        row = db.execute(q, (start, end, created_by)).fetchone()
    else:
        q = """
        SELECT
          COUNT(DISTINCT s.id) AS so_phieu,
          COALESCE(SUM(i.qty*i.unit_price),0) AS tong_ban,
          COALESCE(SUM(i.qty*i.unit_cost),0) AS tong_von,
          COALESCE(SUM(s.shipping_cost),0) AS tong_vc,
          COALESCE(SUM(s.commission),0) AS tong_hh,
          COALESCE(SUM(s.other_cost),0) AS tong_khac
        FROM sales s
        JOIN sale_items i ON i.sale_id=s.id
        WHERE date(s.created_at) BETWEEN ? AND ?
        """
        row = db.execute(q, (start, end)).fetchone()
    return row