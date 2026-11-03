"""Order application service: validates catalog state and commits all checkout writes atomically."""
from __future__ import annotations

import re
import secrets
from datetime import date
from typing import Any

from fastapi import HTTPException

from backend.database import connect


def shipping_fee(subtotal: int, free_shipping_from: int) -> int:
    """Free shipping uses merchandise subtotal BEFORE any coupon discount."""
    return 0 if subtotal >= free_shipping_from else 30000


def restore_cancelled_stock(conn, order, actor_id=None) -> None:
    """Caller holds BEGIN IMMEDIATE; the event ledger makes restoration repeat-safe."""
    reason = f"Hủy đơn {order['order_code']}"
    if conn.execute("SELECT 1 FROM inventory_events WHERE reason=?", (reason,)).fetchone():
        return
    items = conn.execute("SELECT product_id,SUM(quantity) quantity FROM order_items WHERE order_id=? AND product_id IS NOT NULL GROUP BY product_id", (order["id"],)).fetchall()
    for item in items:
        conn.execute("UPDATE products SET stock=stock+? WHERE id=?", (item["quantity"], item["product_id"]))
        conn.execute("INSERT INTO inventory_events(product_id,delta,reason,actor_id) VALUES(?,?,?,?)", (item["product_id"], item["quantity"], reason, actor_id))


def place_order(body: dict[str, Any], user: dict[str, Any] | None) -> dict[str, Any]:
    items = body.get("items", [])
    customer = body.get("customer", {})
    if not isinstance(items, list) or not items or len(items) > 40:
        raise HTTPException(422, "Giỏ hàng đang trống hoặc có quá nhiều dòng")
    if any(not str(customer.get(k, "")).strip() for k in ("name", "phone", "address")):
        raise HTTPException(422, "Vui lòng điền tên, số điện thoại và địa chỉ giao hàng")
    phone = re.sub(r"[\s.-]", "", str(customer["phone"]))
    if not re.fullmatch(r"\+?\d{9,13}", phone):
        raise HTTPException(422, "Số điện thoại chưa hợp lệ")
    code = "PP" + secrets.token_hex(4).upper()
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            clean_items: list[tuple[int, int, dict[str, Any]]] = []
            subtotal = 0
            for item in items:
                product_id = int(item.get("productId", 0))
                quantity = int(item.get("quantity", 0))
                if quantity < 1 or quantity > 25:
                    raise HTTPException(422, "Số lượng mỗi sản phẩm phải từ 1 đến 25")
                row = conn.execute("SELECT id,name,price_vnd,stock FROM products WHERE id=? AND active=1", (product_id,)).fetchone()
                if not row:
                    raise HTTPException(422, "Một sản phẩm trong giỏ không còn bán")
                if row["price_vnd"] <= 0:
                    raise HTTPException(422, f"Sản phẩm {row['name']} chưa có giá bán, vui lòng bỏ khỏi giỏ")
                if row["stock"] < quantity:
                    raise HTTPException(409, f"Sản phẩm {row['name']} hiện không đủ tồn kho")
                subtotal += row["price_vnd"] * quantity
                clean_items.append((product_id, quantity, dict(row)))
            coupon_code = str(body.get("coupon", "")).strip().upper()
            discount = 0
            if coupon_code:
                coupon = conn.execute("SELECT * FROM coupons WHERE code=? COLLATE NOCASE AND active=1", (coupon_code,)).fetchone()
                expired = bool(coupon and coupon["expires_at"] and str(coupon["expires_at"]) < date.today().isoformat())
                if not coupon or expired or (coupon["usage_limit"] and coupon["used_count"] >= coupon["usage_limit"]) or subtotal < coupon["minimum_vnd"]:
                    raise HTTPException(422, "Mã ưu đãi không hợp lệ hoặc chưa đủ điều kiện")
                discount = min(subtotal, subtotal * coupon["discount_value"] // 100 if coupon["discount_type"] == "percent" else coupon["discount_value"])
            threshold_row = conn.execute("SELECT value FROM settings WHERE key='free_shipping_from_vnd'").fetchone()
            free_shipping_from = int(threshold_row["value"]) if threshold_row else 299000
            shipping = shipping_fee(subtotal, free_shipping_from)
            total = subtotal - discount + shipping
            payment = str(body.get("paymentMethod", "cod"))
            if payment != "cod":
                raise HTTPException(422, "Thanh toán trực tuyến chưa được cấu hình; vui lòng chọn COD")
            cur = conn.execute(
                """INSERT INTO orders(order_code,user_id,customer_name,email,phone,address,subtotal_vnd,discount_vnd,shipping_vnd,total_vnd,coupon_code,payment_method)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                (code, user["id"] if user else None, str(customer["name"]).strip(), str(customer.get("email", "")).strip(), phone, str(customer["address"]).strip(), subtotal, discount, shipping, total, coupon_code or None, payment),
            )
            order_id = cur.lastrowid
            for product_id, quantity, row in clean_items:
                conn.execute("INSERT INTO order_items(order_id,product_id,product_name,unit_price_vnd,quantity) VALUES(?,?,?,?,?)", (order_id, product_id, row["name"], row["price_vnd"], quantity))
                conn.execute("UPDATE products SET stock=stock-? WHERE id=?", (quantity, product_id))
                conn.execute("INSERT INTO inventory_events(product_id,delta,reason,actor_id) VALUES(?,?,?,?)", (product_id, -quantity, f"Đơn {code}", user["id"] if user else None))
            if coupon_code:
                conn.execute("UPDATE coupons SET used_count=used_count+1 WHERE code=? COLLATE NOCASE", (coupon_code,))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return {"id": order_id, "order_code": code, "subtotal_vnd": subtotal, "discount_vnd": discount, "shipping_vnd": shipping, "total_vnd": total, "status": "pending"}
