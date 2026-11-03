"""Preview/repair the reported legacy corruption. Never runs during app startup.

python -m backend.repair_reported_data
python -m backend.repair_reported_data --restore-cancelled-order MA_DON_DA_HUY --apply
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime, timezone

from backend.database import connect, db_path
from backend.services.orders import restore_cancelled_stock


def repair_reported_data(apply: bool = False, cancelled_codes: list[str] | None = None,
                         product_repairs=None, price_repairs=None, rewind_codes=None) -> dict:
    path = db_path()
    if not path.is_file():
        raise ValueError(f"Không tìm thấy database: {path}")
    backup = None
    actions = []
    with connect() as conn:
        if apply:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = path.with_name(path.name + f".before-repair-{stamp}.bak")
            with sqlite3.connect(backup) as destination:
                conn.backup(destination)
        conn.execute("BEGIN IMMEDIATE")
        try:
            repairs = {"PP-006": (79000, 42), "PP-007": (89000, 24)}
            repairs.update(product_repairs or {})
            for sku, (price, stock) in repairs.items():
                if not isinstance(price, int) or not isinstance(stock, int) or price <= 0 or stock < 0:
                    raise ValueError('Giá phải dương, tồn kho phải không âm')
                row = conn.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone()
                if row and row["price_vnd"] == 0 and row["stock"] == 0:
                    actions.append({"sku": sku, "before": {"price_vnd": 0, "stock": 0}, "after": {"price_vnd": price, "stock": stock}})
                    conn.execute("UPDATE products SET price_vnd=?,stock=? WHERE id=?", (price, stock, row["id"]))
                    conn.execute("INSERT INTO inventory_events(product_id,delta,reason) VALUES(?,?,?)", (row["id"], stock, f"Khôi phục lỗi prompt: {sku}"))
                else:
                    actions.append({"sku": sku, "skipped": "Không tồn tại hoặc không còn đồng thời giá/tồn bằng 0"})
            for sku, price in (price_repairs or {}).items():
                if not isinstance(price, int) or price <= 0:
                    raise ValueError('Giá bán phải là số nguyên dương')
                row = conn.execute("SELECT * FROM products WHERE sku=?", (sku,)).fetchone()
                if not row:
                    raise ValueError('Không tìm thấy SKU cần đặt giá')
                if row['price_vnd'] == 0:
                    conn.execute('UPDATE products SET price_vnd=?,active=1 WHERE id=?', (price, row['id']))
                    actions.append({'sku': sku, 'after': {'price_vnd': price, 'active': 1}, 'stock_unchanged': True})
                else:
                    actions.append({'sku': sku, 'skipped': 'Giá đã khác 0; không ghi đè'})
            row = conn.execute("SELECT id FROM products WHERE sku='PP-010' AND price_vnd=0 AND active=1").fetchone()
            if row:
                actions.append({"sku": "PP-010", "after": {"active": 0}, "reason": "Chưa có giá bán"})
                conn.execute("UPDATE products SET active=0 WHERE id=?", (row["id"],))
            for code in dict.fromkeys(cancelled_codes or []):
                order = conn.execute("SELECT * FROM orders WHERE order_code=?", (code,)).fetchone()
                if not order or order["status"] != "cancelled":
                    raise ValueError(f"Đơn {code} không tồn tại hoặc chưa hủy")
                items = conn.execute("SELECT product_id,SUM(quantity) quantity FROM order_items WHERE order_id=? GROUP BY product_id", (order["id"],)).fetchall()
                for item in items:
                    deduction = conn.execute("SELECT COALESCE(SUM(delta),0) n FROM inventory_events WHERE product_id=? AND reason=?", (item["product_id"], f"Đơn {code}")).fetchone()["n"]
                    if not item["product_id"] or deduction != -item["quantity"]:
                        raise ValueError(f"Đơn {code}: không đủ bằng chứng xuất kho, cần đối soát thủ công")
                restored = restore_cancelled_stock(conn, order)
                actions.append({"order": code, "restore": restored} if restored else {"order": code, "skipped": "Đã hoàn đủ tồn kho"})
            for code in dict.fromkeys(rewind_codes or []):
                row = conn.execute('SELECT * FROM orders WHERE order_code=?', (code,)).fetchone()
                if not row:
                    raise ValueError('Không tìm thấy mã đơn cần chỉnh trạng thái')
                if row['status'] == 'confirmed':
                    actions.append({'order': code, 'skipped': 'Đã ở trạng thái xác nhận'})
                    continue
                if row['status'] != 'preparing' or row['tracking_code']:
                    raise ValueError('Chỉ chỉnh preparing về confirmed khi chưa có mã vận đơn; trạng thái khác cần đối soát riêng')
                conn.execute("UPDATE orders SET status='confirmed' WHERE id=? AND status='preparing'", (row['id'],))
                conn.execute('INSERT INTO operational_adjustments(event_type,subject_id,before_json,after_json,reason) VALUES(?,?,?,?,?)', ('order_status', str(row['id']), json.dumps({'status': row['status']}), json.dumps({'status': 'confirmed'}), 'Manual correction of test transition; no inventory change'))
                actions.append({'order': code, 'status': 'confirmed', 'inventory_unchanged': True})
            conn.execute("COMMIT" if apply else "ROLLBACK")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return {"applied": apply, "backup": str(backup) if backup else None, "actions": actions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Ghi sau khi sao lưu; mặc định chỉ xem trước")
    parser.add_argument("--restore-cancelled-order", action="append", default=[], metavar="CODE", help="Chỉ hoàn kho cho mã đơn đã đối soát, có thể lặp lại")
    parser.add_argument('--repair-product', action='append', default=[], metavar='SKU:PRICE:STOCK', help='Chỉ sửa khi giá và tồn đồng thời bằng 0')
    parser.add_argument('--price-product', action='append', default=[], metavar='SKU:PRICE', help='Đặt giá và bật bán khi giá hiện tại bằng 0; giữ nguyên tồn')
    parser.add_argument('--rewind-preparing-order', action='append', default=[], metavar='CODE', help='Chỉnh đơn test preparing về confirmed khi chưa có mã vận đơn')
    args = parser.parse_args()
    try:
        products = {}; prices = {}
        for entry in args.repair_product:
            sku, price, stock = entry.split(':'); products[sku] = (int(price), int(stock))
        for entry in args.price_product:
            sku, price = entry.split(':'); prices[sku] = int(price)
        print(json.dumps(repair_reported_data(args.apply, args.restore_cancelled_order, products, prices, args.rewind_preparing_order), ensure_ascii=False, indent=2))
    except ValueError as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
