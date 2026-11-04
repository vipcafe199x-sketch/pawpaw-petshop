"""Authoritative checkout quotes and transactional orders/inventory."""
from __future__ import annotations

import re
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

from fastapi import HTTPException
from backend.database import connect


def shipping_fee(subtotal: int, free_shipping_from: int) -> int:
    return 0 if subtotal >= free_shipping_from else 30000


def calculate_quote(conn, items, coupon_code=''):
    """Same catalog, coupon and shipping calculation for preview and order commit."""
    if not isinstance(items, list) or not items or len(items) > 40:
        raise HTTPException(422, 'Giỏ hàng đang trống hoặc có quá nhiều dòng')
    quantities = {}
    for item in items:
        if not isinstance(item, dict):
            raise HTTPException(422, 'Sản phẩm trong giỏ chưa hợp lệ')
        try:
            product_id, quantity = item['productId'], item['quantity']
            if isinstance(product_id, bool) or isinstance(quantity, bool) or int(product_id) != product_id or int(quantity) != quantity:
                raise ValueError()
            product_id, quantity = int(product_id), int(quantity)
        except (KeyError, TypeError, ValueError, OverflowError):
            raise HTTPException(422, 'Mã sản phẩm và số lượng phải là số nguyên')
        quantities[product_id] = quantities.get(product_id, 0) + quantity
        if quantity < 1 or quantities[product_id] > 25:
            raise HTTPException(422, 'Số lượng mỗi sản phẩm phải từ 1 đến 25')
    clean, subtotal = [], 0
    for product_id, quantity in quantities.items():
        row = conn.execute('SELECT id,name,price_vnd,stock FROM products WHERE id=? AND active=1', (product_id,)).fetchone()
        if not row:
            raise HTTPException(422, 'Một sản phẩm trong giỏ không còn bán')
        if row['price_vnd'] <= 0:
            raise HTTPException(422, f"Sản phẩm {row['name']} chưa có giá bán, vui lòng bỏ khỏi giỏ")
        if row['stock'] < quantity:
            raise HTTPException(409, f"Sản phẩm {row['name']} hiện không đủ tồn kho")
        subtotal += row['price_vnd'] * quantity
        clean.append((product_id, quantity, dict(row)))
    coupon_code = str(coupon_code).strip().upper()
    discount = 0
    if coupon_code:
        coupon = conn.execute('SELECT * FROM coupons WHERE code=? COLLATE NOCASE AND active=1', (coupon_code,)).fetchone()
        not_started = bool(coupon and coupon['starts_at'] and str(coupon['starts_at']) > datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date().isoformat())
        expired = bool(coupon and coupon['expires_at'] and str(coupon['expires_at']) < datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).date().isoformat())
        if not coupon or not_started or expired or (coupon['usage_limit'] and coupon['used_count'] >= coupon['usage_limit']) or subtotal < coupon['minimum_vnd']:
            raise HTTPException(422, 'Mã ưu đãi không hợp lệ hoặc chưa đủ điều kiện')
        discount = min(subtotal, subtotal * coupon['discount_value'] // 100 if coupon['discount_type'] == 'percent' else coupon['discount_value'])
    threshold = conn.execute("SELECT value FROM settings WHERE key='free_shipping_from_vnd'").fetchone()
    shipping = shipping_fee(subtotal, int(threshold['value']) if threshold else 299000)
    return clean, {'subtotal_vnd': subtotal, 'discount_vnd': discount, 'shipping_vnd': shipping,
                   'total_vnd': subtotal - discount + shipping, 'coupon_code': coupon_code,
                   'shipping_basis': 'subtotal_before_discount'}


def quote_order(body):
    with connect() as conn:
        conn.execute('BEGIN')
        _, quote = calculate_quote(conn, body.get('items'), body.get('coupon', ''))
        return quote


def restore_cancelled_stock(conn, order, actor_id=None):
    """Restore each line's remaining quantity, including partially repaired legacy orders."""
    reason = f"Hủy đơn {order['order_code']}"
    restored_items = []
    items = conn.execute('SELECT product_id,SUM(quantity) quantity FROM order_items WHERE order_id=? GROUP BY product_id', (order['id'],)).fetchall()
    for item in items:
        if item['product_id'] is None:
            raise HTTPException(409, 'Sản phẩm đã bị xóa; cần đối soát hoàn kho thủ công')
        restored = conn.execute('SELECT COALESCE(SUM(delta),0) n FROM inventory_events WHERE product_id=? AND reason=?', (item['product_id'], reason)).fetchone()['n']
        if restored < 0 or restored > item['quantity']:
            raise HTTPException(409, 'Lịch sử hoàn kho không khớp; cần đối soát thủ công')
        delta = item['quantity'] - restored
        if not delta:
            continue
        conn.execute('UPDATE products SET stock=stock+? WHERE id=?', (delta, item['product_id']))
        conn.execute('INSERT INTO inventory_events(product_id,delta,reason,actor_id) VALUES(?,?,?,?)', (item['product_id'], delta, reason, actor_id))
        restored_items.append({'product_id': item['product_id'], 'delta': delta})
    return restored_items


def place_order(body: dict[str, Any], user: dict[str, Any] | None) -> dict[str, Any]:
    customer = body.get('customer', {})
    if not isinstance(customer, dict) or any(not str(customer.get(k, '')).strip() for k in ('name', 'phone', 'address')):
        raise HTTPException(422, 'Vui lòng điền tên, số điện thoại và địa chỉ giao hàng')
    phone = re.sub(r'[\s.-]', '', str(customer['phone']))
    if not re.fullmatch(r'\+?\d{9,13}', phone):
        raise HTTPException(422, 'Số điện thoại chưa hợp lệ')
    code = 'PP' + secrets.token_hex(4).upper()
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        try:
            clean_items, quote = calculate_quote(conn, body.get('items'), body.get('coupon', ''))
            if 'expectedTotalVnd' in body and body['expectedTotalVnd'] != quote['total_vnd']:
                raise HTTPException(409, 'Giá hoặc ưu đãi đã thay đổi. Vui lòng xem lại tổng tiền trước khi đặt hàng.')
            payment = str(body.get('paymentMethod', 'cod'))
            if payment != 'cod':
                raise HTTPException(422, 'Thanh toán trực tuyến chưa được cấu hình; vui lòng chọn COD')
            cur = conn.execute('''INSERT INTO orders(order_code,user_id,customer_name,email,phone,address,subtotal_vnd,discount_vnd,shipping_vnd,total_vnd,coupon_code,payment_method)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''', (code, user['id'] if user else None, str(customer['name']).strip(), str(customer.get('email', '')).strip(), phone, str(customer['address']).strip(), quote['subtotal_vnd'], quote['discount_vnd'], quote['shipping_vnd'], quote['total_vnd'], quote['coupon_code'] or None, payment))
            order_id = cur.lastrowid
            for product_id, quantity, row in clean_items:
                conn.execute('INSERT INTO order_items(order_id,product_id,product_name,unit_price_vnd,quantity) VALUES(?,?,?,?,?)', (order_id, product_id, row['name'], row['price_vnd'], quantity))
                conn.execute('UPDATE products SET stock=stock-? WHERE id=?', (quantity, product_id))
                conn.execute('INSERT INTO inventory_events(product_id,delta,reason,actor_id) VALUES(?,?,?,?)', (product_id, -quantity, f'Đơn {code}', user['id'] if user else None))
            if quote['coupon_code']:
                conn.execute('UPDATE coupons SET used_count=used_count+1 WHERE code=? COLLATE NOCASE', (quote['coupon_code'],))
            conn.execute('COMMIT')
        except Exception:
            conn.execute('ROLLBACK')
            raise
    return {'id': order_id, 'order_code': code, **quote, 'status': 'pending'}
