from dataclasses import dataclass
from datetime import datetime
import uuid
from ..db import get_db

@dataclass
class CartItem:
    product_id: int
    name: str
    qty: float
    unit_cost: float
    unit_price: float

def get_on_hand(product_id:int)->float:
    db = get_db()
    r = db.execute(
        "SELECT COALESCE(SUM(qty),0) AS on_hand FROM stock_moves WHERE product_id=?",
        (product_id,),
    ).fetchone()
    return float(r["on_hand"] or 0)

def new_sale_code()->str:
    return datetime.now().strftime("%Y%m%d")+"-"+uuid.uuid4().hex[:8].upper()

def create_sale_and_deduct_stock(*, items:list[CartItem], customer_note:str,
                                 shipping_cost:float, commission:float, other_cost:float,
                                 other_cost_note:str, created_by:int)->tuple[int,str]:
    if not items:
        raise ValueError("Empty cart")

    for it in items:
        if it.qty <= 0:
            raise ValueError("Invalid qty")
        if get_on_hand(it.product_id) < it.qty:
            raise ValueError(f"Not enough stock for {it.name}")

    db = get_db()
    code = new_sale_code()

    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            """INSERT INTO sales(code,customer_note,shipping_cost,commission,other_cost,other_cost_note,created_by)
               VALUES (?,?,?,?,?,?,?)""",
            (code, customer_note, shipping_cost, commission, other_cost, other_cost_note, created_by),
        )
        sale_id = db.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]

        for it in items:
            db.execute(
                """INSERT INTO sale_items(sale_id,product_id,product_name,qty,unit_cost,unit_price)
                   VALUES (?,?,?,?,?,?)""",
                (sale_id, it.product_id, it.name, it.qty, it.unit_cost, it.unit_price),
            )
            db.execute(
                """INSERT INTO stock_moves(product_id,move_type,qty,unit_cost,unit_price,ref_type,ref_id,note,created_by)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (it.product_id, "OUT", -abs(it.qty), it.unit_cost, it.unit_price, "SALE", sale_id, customer_note or "", created_by),
            )

        db.commit()
        return int(sale_id), code
    except:
        try: db.rollback()
        except: pass
        raise