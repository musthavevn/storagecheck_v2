# app/routes/inventory_routes.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from ..auth import login_required, admin_or_manager
from ..db import get_db
from ..services.inventory import CartItem, create_sale_and_deduct_stock, get_on_hand

inventory_bp = Blueprint("inventory", __name__)


def _cart():
    return session.setdefault("cart", [])


def _audit(db, action, entity_type, entity_id=None, detail=""):
    actor = int(session.get("user_id") or 0) or None
    db.execute(
        "INSERT INTO audit_logs(actor_user_id,action,entity_type,entity_id,detail) VALUES (?,?,?,?,?)",
        (actor, action, entity_type, entity_id, detail or ""),
    )


@inventory_bp.get("/")
@login_required
def index():
    db = get_db()

    s = db.execute("SELECT * FROM settings WHERE id=1").fetchone()

    rows = db.execute(
        """
      SELECT
        p.id, p.sku, p.name, p.cost, p.sell_price, p.note,
        p.low_stock_enabled, p.low_stock_threshold, p.email_enabled,
        p.is_active,

        COALESCE(SUM(m.qty), 0) AS on_hand,

        COALESCE(SUM(CASE WHEN m.move_type='IN' THEN m.qty ELSE 0 END), 0) AS total_in,

        COALESCE(SUM(
          CASE
            WHEN m.move_type='OUT' AND date(m.created_at,'localtime') = date('now','localtime')
            THEN ABS(m.qty)
            ELSE 0
          END
        ), 0) AS out_today

      FROM products p
      LEFT JOIN stock_moves m ON m.product_id = p.id
      WHERE p.is_active = 1
      GROUP BY p.id
      ORDER BY p.id DESC
    """
    ).fetchall()

    return render_template("index.html", products=rows, cart=_cart(), s=s)


@inventory_bp.post("/product/add")
@admin_or_manager
def product_add():
    sku = (request.form.get("sku") or "").strip() or None
    name = (request.form.get("name") or "").strip()
    cost = float(request.form.get("cost", "0") or 0)
    sell_price = float(request.form.get("sell_price", "0") or 0)
    note = (request.form.get("note") or "").strip()

    low_stock_enabled = 1 if (request.form.get("low_stock_enabled") in ("1", "on", "true", "yes")) else 0
    low_stock_threshold = float(request.form.get("low_stock_threshold", "0") or 0)
    email_enabled = 1 if (request.form.get("email_enabled") in ("1", "on", "true", "yes")) else 0

    if not name:
        flash("Name required", "danger")
        return redirect(url_for("inventory.index"))

    if cost < 0 or sell_price < 0 or low_stock_threshold < 0:
        flash("Values must be >= 0", "danger")
        return redirect(url_for("inventory.index"))

    db = get_db()
    try:
        cur = db.execute(
            """INSERT INTO products(sku,name,cost,sell_price,note,low_stock_enabled,low_stock_threshold,email_enabled,is_active)
               VALUES (?,?,?,?,?,?,?,?,1)""",
            (sku, name, cost, sell_price, note, low_stock_enabled, low_stock_threshold, email_enabled),
        )
        pid = cur.lastrowid
        _audit(db, "PRODUCT_CREATE", "product", pid, f"name={name}; sku={sku}; cost={cost}; sell_price={sell_price}")
        db.commit()
        flash("Product created", "success")
    except Exception as e:
        db.rollback()
        flash(f"Create product failed: {e}", "danger")
    return redirect(url_for("inventory.index"))


@inventory_bp.post("/product/update")
@admin_or_manager
def product_update():
    db = get_db()
    product_id = int(request.form.get("product_id"))
    sku = (request.form.get("sku") or "").strip() or None
    name = (request.form.get("name") or "").strip()
    cost = float(request.form.get("cost", "0") or 0)
    sell_price = float(request.form.get("sell_price", "0") or 0)
    note = (request.form.get("note") or "").strip()
    low_stock_enabled = 1 if (request.form.get("low_stock_enabled") in ("1", "on", "true", "yes")) else 0
    low_stock_threshold = float(request.form.get("low_stock_threshold", "0") or 0)
    email_enabled = 1 if (request.form.get("email_enabled") in ("1", "on", "true", "yes")) else 0

    if not name:
        flash("Name required", "danger")
        return redirect(url_for("inventory.index"))

    try:
        db.execute(
            """UPDATE products
               SET sku=?, name=?, cost=?, sell_price=?, note=?,
                   low_stock_enabled=?, low_stock_threshold=?, email_enabled=?
               WHERE id=?""",
            (sku, name, cost, sell_price, note, low_stock_enabled, low_stock_threshold, email_enabled, product_id),
        )
        _audit(
            db,
            "PRODUCT_UPDATE",
            "product",
            product_id,
            f"sku={sku}; name={name}; cost={cost}; sell_price={sell_price}; low={low_stock_enabled}/{low_stock_threshold}; email={email_enabled}",
        )
        db.commit()
        flash("Product updated", "success")
    except Exception as e:
        db.rollback()
        flash(f"Update failed: {e}", "danger")

    return redirect(url_for("inventory.index"))


@inventory_bp.post("/product/deactivate/<int:product_id>")
@admin_or_manager
def product_deactivate(product_id: int):
    db = get_db()
    try:
        db.execute("UPDATE products SET is_active=0 WHERE id=?", (product_id,))
        _audit(db, "PRODUCT_DEACTIVATE", "product", product_id, "is_active=0")
        db.commit()
        flash("Product deleted (soft)", "warning")
    except Exception as e:
        db.rollback()
        flash(f"Delete failed: {e}", "danger")
    return redirect(url_for("inventory.index"))


@inventory_bp.post("/stock/in")
@admin_or_manager
def stock_in():
    product_id = int(request.form.get("product_id"))
    qty = float(request.form.get("qty", "0") or 0)
    unit_cost = float(request.form.get("unit_cost", "0") or 0)
    note = (request.form.get("note") or "").strip()
    update_cost = 1 if (request.form.get("update_cost") in ("1", "on", "true", "yes")) else 0

    if qty <= 0:
        flash("Invalid qty", "danger")
        return redirect(url_for("inventory.index"))

    if unit_cost < 0:
        flash("Invalid unit cost", "danger")
        return redirect(url_for("inventory.index"))

    db = get_db()
    p = db.execute("SELECT * FROM products WHERE id=? AND is_active=1", (product_id,)).fetchone()
    if not p:
        flash("Product not found", "danger")
        return redirect(url_for("inventory.index"))

    try:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            """INSERT INTO stock_moves(product_id,move_type,qty,unit_cost,ref_type,note,created_by)
               VALUES (?,?,?,?,?,?,?)""",
            (product_id, "IN", abs(qty), unit_cost, "MANUAL_IN", note, int(session["user_id"])),
        )
        if update_cost:
            db.execute("UPDATE products SET cost=? WHERE id=?", (unit_cost, product_id))

        _audit(db, "STOCK_IN", "product", product_id, f"qty={qty}; unit_cost={unit_cost}; update_cost={update_cost}; note={note}")
        db.commit()
        flash("Stock IN OK", "success")
    except Exception as e:
        try:
            db.rollback()
        except:
            pass
        flash(f"Stock IN failed: {e}", "danger")

    return redirect(url_for("inventory.index"))


@inventory_bp.post("/cart/add")
@login_required
def cart_add():
    product_id = int(request.form.get("product_id"))
    qty = float(request.form.get("qty", "0") or 0)

    unit_price_raw = (request.form.get("unit_price") or "").strip()
    unit_price = float(unit_price_raw or 0)

    db = get_db()
    p = db.execute("SELECT * FROM products WHERE id=? AND is_active=1", (product_id,)).fetchone()
    if not p:
        flash("Product not found", "danger")
        return redirect(url_for("inventory.index"))
    if qty <= 0:
        flash("Invalid qty", "danger")
        return redirect(url_for("inventory.index"))

    if unit_price <= 0:
        unit_price = float(p["sell_price"] or 0)

    if unit_price <= 0:
        flash("Unit price required (or set a default sell price for this product)", "danger")
        return redirect(url_for("inventory.index"))

    on_hand = get_on_hand(product_id)
    cart = _cart()

    for c in cart:
        if c["product_id"] == product_id:
            new_qty = float(c["qty"]) + qty
            if on_hand < new_qty:
                flash(f"Not enough stock. On hand={on_hand}", "danger")
                return redirect(url_for("inventory.index"))
            c["qty"] = new_qty
            if unit_price_raw:
                c["unit_price"] = unit_price
            session.modified = True
            flash("Added to cart", "success")
            return redirect(url_for("inventory.index"))

    if on_hand < qty:
        flash(f"Not enough stock. On hand={on_hand}", "danger")
        return redirect(url_for("inventory.index"))

    cart.append(
        {
            "product_id": product_id,
            "name": p["name"],
            "qty": qty,
            "unit_cost": float(p["cost"] or 0),
            "unit_price": unit_price,
        }
    )
    session.modified = True
    flash("Added to cart", "success")
    return redirect(url_for("inventory.index"))


@inventory_bp.get("/cart/remove/<int:i>")
@login_required
def cart_remove(i: int):
    cart = _cart()
    if 0 <= i < len(cart):
        cart.pop(i)
        session.modified = True
    return redirect(url_for("inventory.index"))


@inventory_bp.get("/cart/clear")
@login_required
def cart_clear():
    session["cart"] = []
    return redirect(url_for("inventory.index"))


@inventory_bp.post("/sale/preview")
@login_required
def sale_preview():
    cart = _cart()
    if not cart:
        return redirect(url_for("inventory.index"))

    customer_note = (request.form.get("customer_note", "Retail") or "Retail").strip()
    shipping_cost = float(request.form.get("shipping_cost", "0") or 0)
    commission = float(request.form.get("commission", "0") or 0)
    other_cost = float(request.form.get("other_cost", "0") or 0)
    other_cost_note = (request.form.get("other_cost_note") or "").strip()

    total_sales = sum(float(x["qty"]) * float(x["unit_price"]) for x in cart)
    total_cost = sum(float(x["qty"]) * float(x["unit_cost"]) for x in cart)
    profit = total_sales - total_cost - shipping_cost - commission - other_cost

    return render_template(
        "sale_preview.html",
        cart=cart,
        customer_note=customer_note,
        shipping_cost=shipping_cost,
        commission=commission,
        other_cost=other_cost,
        other_cost_note=other_cost_note,
        total_sales=total_sales,
        total_cost=total_cost,
        profit=profit,
    )


@inventory_bp.post("/sale/checkout")
@login_required
def sale_checkout():
    db = get_db()  # FIX: ensure db exists for _audit()

    cart = _cart()
    if not cart:
        return redirect(url_for("inventory.index"))

    customer_note = (request.form.get("customer_note", "Retail") or "Retail").strip()
    shipping_cost = float(request.form.get("shipping_cost", "0") or 0)
    commission = float(request.form.get("commission", "0") or 0)
    other_cost = float(request.form.get("other_cost", "0") or 0)
    other_cost_note = (request.form.get("other_cost_note") or "").strip()

    items = [
        CartItem(
            product_id=int(x["product_id"]),
            name=x["name"],
            qty=float(x["qty"]),
            unit_cost=float(x["unit_cost"]),
            unit_price=float(x["unit_price"]),
        )
        for x in cart
    ]

    try:
        sale_id, code = create_sale_and_deduct_stock(
            items=items,
            customer_note=customer_note,
            shipping_cost=shipping_cost,
            commission=commission,
            other_cost=other_cost,
            other_cost_note=other_cost_note,
            created_by=int(session["user_id"]),
        )
        _audit(db, "SALE_CHECKOUT", "sale", sale_id, f"code={code}; items={len(items)}")
        db.commit()
        session["cart"] = []
        flash(f"SALE OK: {code}", "success")
        return redirect(url_for("inventory.sale_receipt", sale_id=sale_id))
    except Exception as e:
        try:
            db.rollback()
        except:
            pass
        flash(f"Checkout failed: {e}", "danger")
        return redirect(url_for("inventory.index"))


@inventory_bp.get("/sale/<int:sale_id>/receipt")
@login_required
def sale_receipt(sale_id: int):
    db = get_db()
    sale = db.execute("SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()
    if not sale:
        flash("Sale not found", "danger")
        return redirect(url_for("inventory.index"))

    items = db.execute(
        "SELECT * FROM sale_items WHERE sale_id=? ORDER BY id", (sale_id,)
    ).fetchall()

    total_sales = sum(float(x["qty"]) * float(x["unit_price"]) for x in items)
    total_cost = sum(float(x["qty"]) * float(x["unit_cost"]) for x in items)
    profit = (
        total_sales
        - total_cost
        - float(sale["shipping_cost"])
        - float(sale["commission"])
        - float(sale["other_cost"])
    )

    return render_template(
        "sale_receipt.html",
        sale=sale,
        items=items,
        total_sales=total_sales,
        total_cost=total_cost,
        profit=profit,
    )