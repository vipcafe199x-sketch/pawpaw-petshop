"""SQLite persistence for the PawPaw single-node MVP."""
from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from backend.security import hash_password


DEFAULT_PRODUCTS = [
    ("hat-dinh-duong-puppycare", "Hạt dinh dưỡng PuppyCare", "Thức ăn", "Chó", 320000, 360000, 54, "🥣", "Công thức cân bằng cho chó con, giàu đạm và omega 3."),
    ("thuc-an-meo-catlove", "Thức ăn cho mèo CatLove", "Thức ăn", "Mèo", 280000, 0, 49, "🐟", "Hạt giòn thơm, bổ sung taurine cho mắt sáng và lông mượt."),
    ("pate-royaldog", "Pate cho chó RoyalDog", "Thức ăn", "Chó", 65000, 0, 30, "🥫", "Pate mềm ẩm, dễ ăn, phù hợp cho bữa ăn hằng ngày."),
    ("pate-catmenu", "Pate cho mèo CatMenu", "Thức ăn", "Mèo", 69000, 0, 42, "🍲", "Pate vị cá ngừ dành cho mèo kén ăn."),
    ("dem-ngu-meo", "Đệm ngủ êm ái cho mèo", "Phụ kiện", "Mèo", 299000, 0, 11, "🛏️", "Đệm lông mềm, có thể tháo vỏ để giặt."),
    ("bong-day-thung", "Bóng dây thừng cho chó", "Đồ chơi", "Chó", 79000, 0, 42, "🧶", "Đồ chơi nhẹ, hỗ trợ vận động và làm sạch răng."),
    ("do-choi-ca-nhoi-bong", "Đồ chơi cá nhồi bông", "Đồ chơi", "Mèo", 89000, 0, 24, "🐠", "Cá nhồi bông mềm cho giờ chơi trong nhà."),
    ("nha-ngu-meo", "Nhà ngủ cho mèo cao cấp", "Phụ kiện", "Mèo", 459000, 0, 11, "🏠", "Nhà ngủ ấm áp, thiết kế gọn cho góc nhỏ."),
    ("dau-goi-pawpaw", "Sữa tắm dưỡng lông PawPaw", "Chăm sóc", "Chó", 149000, 0, 22, "🧴", "Làm sạch dịu nhẹ, giữ lông mềm thơm."),
    ("day-dat-meo", "Dây dắt yếm cho mèo", "Phụ kiện", "Mèo", 129000, 0, 18, "🦮", "Yếm điều chỉnh được, có phản quang."),
]


class ClosingConnection(sqlite3.Connection):
    """A connection context also releases the file handle on exit."""
    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "migrations" / "001_initial.sql"


def db_path() -> Path:
    return Path(os.getenv("DATABASE_PATH", "./data/pawpaw.sqlite3")).resolve()


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=15, isolation_level=None, factory=ClosingConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 15000")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        for idx, row in enumerate(DEFAULT_PRODUCTS):
            slug, name, category, species, price, compare, stock, emoji, desc = row
            conn.execute(
                """INSERT OR IGNORE INTO products
                (slug,name,category,species,price_vnd,compare_price_vnd,stock,sku,emoji,description,featured)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (slug, name, category, species, price, compare, stock, f"PP-{idx+1:03}", emoji, desc, 1 if idx < 5 else 0),
            )
        conn.execute("INSERT OR IGNORE INTO coupons(code,discount_type,discount_value,minimum_vnd,usage_limit) VALUES('PAWPAW10','percent',10,150000,500)")
        conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('store_name','PawPaw Pet Shop')")
        conn.execute("INSERT OR IGNORE INTO settings(key,value) VALUES('free_shipping_from_vnd','299000')")
        admin_email = os.getenv("ADMIN_EMAIL", "admin@pawpaw.local").strip().lower()
        admin_password = os.getenv("ADMIN_PASSWORD", "ChangeMe-OnlyForLocal")
        existing = conn.execute("SELECT id FROM users WHERE email=?", (admin_email,)).fetchone()
        if not existing:
            conn.execute(
                "INSERT INTO users(email,full_name,password_hash,role) VALUES(?,?,?,'admin')",
                (admin_email, "Quản trị PawPaw", hash_password(admin_password)),
            )
