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


def repair_reported_data(apply: bool = False, cancelled_codes: list[str] | None = None) -> dict:
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
            for sku, slug, price, stock in [
                ("PP-006", "bong-day-thung", 79000, 42),
                ("PP-007", "do-choi-ca-nhoi-bong", 89000, 24),
            ]:
                row = conn.execute("SELECT * FROM products WHERE sku=? AND slug=?", (sku, slug)).fetchone()
                if row and row["price_vnd"] == 0 and row["stock"] == 0:
                    actions.append({"sku": sku, "before": {"price_vnd": 0, "stock": 0}, "after": {"price_vnd": price, "stock": stock}})
                    conn.execute("UPDATE products SET price_vnd=?,stock=? WHERE id=?", (price, stock, row["id"]))
                    conn.execute("INSERT INTO inventory_events(product_id,delta,reason) VALUES(?,?,?)", (row["id"], stock, f"Khôi phục lỗi prompt: {sku}"))
            row = conn.execute("SELECT id FROM products WHERE sku='PP-010' AND price_vnd=0 AND active=1").fetchone()
            if row:
                actions.append({"sku": "PP-010", "after": {"active": 0}, "reason": "Chưa có giá bán"})
                conn.execute("UPDATE products SET active=0 WHERE id=?", (row["id"],))
            for code in dict.fromkeys(cancelled_codes or []):
                order = conn.execute("SELECT * FROM orders WHERE order_code=?", (code,)).fetchone()
                if not order or order["status"] != "cancelled":
                    raise ValueError(f"Đơn {code} không tồn tại hoặc chưa hủy")
                if conn.execute("SELECT 1 FROM inventory_events WHERE reason=?", (f"Hủy đơn {code}",)).fetchone():
                    actions.append({"order": code, "skipped": "Đã có sự kiện hoàn kho"})
                    continue
                items = conn.execute("SELECT product_id,SUM(quantity) quantity FROM order_items WHERE order_id=? GROUP BY product_id", (order["id"],)).fetchall()
                for item in items:
                    deduction = conn.execute("SELECT COALESCE(SUM(delta),0) n FROM inventory_events WHERE product_id=? AND reason=?", (item["product_id"], f"Đơn {code}")).fetchone()["n"]
                    if not item["product_id"] or deduction != -item["quantity"]:
                        raise ValueError(f"Đơn {code}: không đủ bằng chứng xuất kho, cần đối soát thủ công")
                actions.append({"order": code, "restore": [dict(item) for item in items]})
                restore_cancelled_stock(conn, order)
            conn.execute("COMMIT" if apply else "ROLLBACK")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return {"applied": apply, "backup": str(backup) if backup else None, "actions": actions}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Ghi sau khi sao lưu; mặc định chỉ xem trước")
    parser.add_argument("--restore-cancelled-order", action="append", default=[], metavar="CODE", help="Chỉ hoàn kho cho mã đơn đã đối soát, có thể lặp lại")
    args = parser.parse_args()
    try:
        print(json.dumps(repair_reported_data(args.apply, args.restore_cancelled_order), ensure_ascii=False, indent=2))
    except ValueError as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
