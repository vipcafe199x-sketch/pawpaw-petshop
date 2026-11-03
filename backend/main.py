"""PawPaw Pet Shop modular-monolith API and static web application."""
from __future__ import annotations

import os
import re
import secrets
from collections import defaultdict, deque
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.database import connect, init_db
from backend.security import csrf_matches, hash_password, new_csrf, new_session, session_digest, verify_password
from backend.services.orders import place_order, restore_cancelled_stock

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "frontend" / "static"
APP_ENV = os.getenv("APP_ENV", "development")
COOKIE_SECURE = APP_ENV == "production"
app = FastAPI(title="PawPaw Pet Shop API", version="1.0.0", docs_url="/api/docs" if APP_ENV != "production" else None, redoc_url=None)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

LOGIN_ATTEMPTS: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; font-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    if APP_ENV == "production":
        response.headers["Strict-Transport-Security"] = "max-age=15552000; includeSubDomains"
    return response


@app.on_event("startup")
def startup() -> None:
    if APP_ENV == "production":
        if len(os.getenv("APP_SECRET", "")) < 40:
            raise RuntimeError("APP_SECRET must be a random value at least 40 characters long in production")
        if len(os.getenv("ADMIN_PASSWORD", "")) < 14:
            raise RuntimeError("Set a strong ADMIN_PASSWORD before starting in production")
        if os.getenv("ADMIN_PASSWORD", "").lower().startswith("changeme") or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", os.getenv("ADMIN_EMAIL", "")) or os.getenv("ADMIN_EMAIL", "").lower().endswith(".local"):
            raise RuntimeError("Replace the local demo admin account before starting in production")
    init_db()


def rowdict(row: Any) -> dict[str, Any] | None:
    return dict(row) if row else None


def require_same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin:
        expected = os.getenv("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
        if origin.rstrip("/") != expected:
            raise HTTPException(403, "Origin không hợp lệ")


def require_csrf(request: Request) -> None:
    require_same_origin(request)
    cookie = request.cookies.get("pawpaw_csrf")
    header = request.headers.get("x-csrf-token")
    if not csrf_matches(cookie, header):
        raise HTTPException(403, "Phiên biểu mẫu hết hạn. Tải lại trang rồi thử lại.")


def current_user(request: Request) -> dict[str, Any] | None:
    raw = request.cookies.get("pawpaw_session")
    if not raw:
        return None
    with connect() as conn:
        row = conn.execute(
            """SELECT u.id,u.email,u.full_name,u.phone,u.role FROM sessions s
               JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>?""",
            (session_digest(raw), datetime.now(timezone.utc).isoformat()),
        ).fetchone()
    return rowdict(row)


def signed_in(request: Request) -> dict[str, Any]:
    user = current_user(request)
    if not user:
        raise HTTPException(401, "Đăng nhập để tiếp tục")
    return user


def admin_user(request: Request) -> dict[str, Any]:
    user = signed_in(request)
    if user["role"] != "admin":
        raise HTTPException(403, "Bạn không có quyền truy cập khu vực quản trị")
    return user


def issue_session(response: Response, user_id: int) -> None:
    raw, digest, expiry = new_session()
    with connect() as conn:
        conn.execute("INSERT INTO sessions(token_hash,user_id,expires_at) VALUES(?,?,?)", (digest, user_id, expiry))
    response.set_cookie("pawpaw_session", raw, httponly=True, secure=COOKIE_SECURE, samesite="lax", max_age=7 * 86400, path="/")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "pawpaw"}


@app.get("/api/csrf")
def csrf(response: Response) -> dict[str, str]:
    token = new_csrf()
    response.set_cookie("pawpaw_csrf", token, httponly=False, secure=COOKIE_SECURE, samesite="strict", max_age=3600, path="/")
    return {"csrfToken": token}


@app.get("/api/products")
def products(q: str = "", category: str = "", species: str = "", sort: str = "popular", limit: int = 60) -> list[dict[str, Any]]:
    limit = max(1, min(limit, 100))
    sql = "SELECT * FROM products WHERE active=1"
    params: list[Any] = []
    if q.strip():
        sql += " AND (name LIKE ? OR description LIKE ? OR sku LIKE ?)"
        term = f"%{q.strip()}%"
        params.extend([term, term, term])
    if category:
        sql += " AND category=?"
        params.append(category)
    if species:
        sql += " AND species=?"
        params.append(species)
    order = {"price-asc": "price_vnd ASC", "price-desc": "price_vnd DESC", "newest": "id DESC", "popular": "featured DESC, id ASC"}.get(sort, "featured DESC, id ASC")
    sql += f" ORDER BY {order} LIMIT ?"
    params.append(limit)
    with connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


@app.get("/api/products/{slug}")
def product_detail(slug: str) -> dict[str, Any]:
    with connect() as conn:
        row = conn.execute("SELECT * FROM products WHERE slug=? AND active=1", (slug,)).fetchone()
    if not row:
        raise HTTPException(404, "Không tìm thấy sản phẩm")
    return dict(row)


@app.get("/api/storefront/settings")
def storefront_settings() -> dict[str, str]:
    public_keys = {"store_name", "free_shipping_from_vnd", "support_phone", "support_email", "store_address"}
    with connect() as conn:
        return {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM settings").fetchall() if r["key"] in public_keys}


@app.post("/api/auth/register")
async def register(request: Request, response: Response) -> dict[str, Any]:
    require_csrf(request)
    body = await request.json()
    email = str(body.get("email", "")).strip().lower()
    name = str(body.get("fullName", "")).strip()
    phone = str(body.get("phone", "")).strip()
    password = str(body.get("password", ""))
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email) or len(name) < 2 or len(password) < 10:
        raise HTTPException(422, "Nhập email hợp lệ, họ tên và mật khẩu tối thiểu 10 ký tự")
    try:
        with connect() as conn:
            cur = conn.execute("INSERT INTO users(email,full_name,phone,password_hash) VALUES(?,?,?,?)", (email, name, phone, hash_password(password)))
            user_id = cur.lastrowid
        issue_session(response, int(user_id))
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise HTTPException(409, "Email này đã được đăng ký")
        raise
    return {"id": user_id, "email": email, "full_name": name, "phone": phone, "role": "customer"}


@app.post("/api/auth/login")
async def login(request: Request, response: Response) -> dict[str, Any]:
    require_csrf(request)
    body = await request.json()
    email = str(body.get("email", "")).strip().lower()
    password = str(body.get("password", ""))
    ip = request.client.host if request.client else "unknown"
    now = datetime.now().timestamp()
    attempts = LOGIN_ATTEMPTS[ip]
    while attempts and now - attempts[0] > 900:
        attempts.popleft()
    if len(attempts) >= 8:
        raise HTTPException(429, "Thử đăng nhập quá nhiều lần. Vui lòng đợi 15 phút.")
    with connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        attempts.append(now)
        raise HTTPException(401, "Email hoặc mật khẩu chưa chính xác")
    attempts.clear()
    issue_session(response, row["id"])
    return {"id": row["id"], "email": row["email"], "full_name": row["full_name"], "phone": row["phone"], "role": row["role"]}


@app.get("/api/auth/me")
def me(request: Request) -> dict[str, Any] | None:
    return current_user(request)


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict[str, bool]:
    require_csrf(request)
    raw = request.cookies.get("pawpaw_session")
    if raw:
        with connect() as conn:
            conn.execute("DELETE FROM sessions WHERE token_hash=?", (session_digest(raw),))
    response.delete_cookie("pawpaw_session", path="/")
    return {"ok": True}


@app.post("/api/orders")
async def create_order(request: Request) -> dict[str, Any]:
    require_csrf(request)
    return place_order(await request.json(), current_user(request))


def order_view(conn: Any, row: Any) -> dict[str, Any]:
    result = dict(row)
    result["items"] = [dict(i) for i in conn.execute("SELECT product_name,unit_price_vnd,quantity FROM order_items WHERE order_id=?", (row["id"],)).fetchall()]
    return result


@app.post("/api/orders/lookup")
async def lookup_order(request: Request) -> dict[str, Any]:
    require_csrf(request)
    body = await request.json()
    code = str(body.get("code", ""))
    phone = str(body.get("phone", ""))
    with connect() as conn:
        row = conn.execute("SELECT * FROM orders WHERE order_code=? AND phone=?", (code.strip().upper(), re.sub(r"[\s.-]", "", phone))).fetchone()
        if not row:
            raise HTTPException(404, "Không tìm thấy đơn hàng với mã và số điện thoại này")
        return order_view(conn, row)


@app.get("/api/account/orders")
def account_orders(user: dict[str, Any] = Depends(signed_in)) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC", (user["id"],)).fetchall()
        return [order_view(conn, r) for r in rows]


@app.post("/api/bookings")
async def create_booking(request: Request) -> dict[str, Any]:
    require_csrf(request)
    body = await request.json()
    required = ["serviceType", "petName", "petSpecies", "ownerName", "phone", "serviceDate", "timeSlot"]
    if any(not str(body.get(k, "")).strip() for k in required):
        raise HTTPException(422, "Vui lòng điền các thông tin bắt buộc")
    service_type = str(body["serviceType"])
    if service_type not in {"grooming", "vet"}:
        raise HTTPException(422, "Dịch vụ không hợp lệ")
    try:
        appointment_day = date.fromisoformat(str(body["serviceDate"]))
    except ValueError:
        raise HTTPException(422, "Ngày hẹn chưa hợp lệ")
    if appointment_day < date.today():
        raise HTTPException(422, "Ngày hẹn cần từ hôm nay trở đi")
    booking_phone = re.sub(r"[\s.-]", "", str(body["phone"]))
    if not re.fullmatch(r"\+?\d{9,13}", booking_phone):
        raise HTTPException(422, "Số điện thoại chưa hợp lệ")
    price = 149000 if service_type == "grooming" else 99000
    user = current_user(request)
    staff = "Chuyên viên PawPaw"
    try:
        with connect() as conn:
            cur = conn.execute(
                """INSERT INTO appointments(user_id,service_type,pet_name,pet_species,owner_name,phone,service_date,time_slot,staff_name,note,price_vnd)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (user["id"] if user else None, service_type, body["petName"].strip(), body["petSpecies"], body["ownerName"].strip(), booking_phone, body["serviceDate"], body["timeSlot"], staff, str(body.get("note", "")).strip(), price),
            )
    except Exception as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise HTTPException(409, "Khung giờ này vừa được đặt. Hãy chọn giờ khác.")
        raise
    return {"id": cur.lastrowid, "status": "requested", "price_vnd": price}


@app.post("/api/returns")
async def request_return(request: Request) -> dict[str, Any]:
    require_csrf(request)
    body = await request.json()
    reason = str(body.get("reason", "")).strip()
    with connect() as conn:
        order = conn.execute("SELECT id,created_at FROM orders WHERE order_code=? AND phone=?", (str(body.get("orderCode", "")).strip().upper(), re.sub(r"[\s.-]", "", str(body.get("phone", ""))))).fetchone()
        if not order:
            raise HTTPException(404, "Không tìm thấy đơn hàng")
        if not reason:
            raise HTTPException(422, "Vui lòng chọn lý do đổi trả")
        cur = conn.execute("INSERT INTO returns(order_id,reason,details) VALUES(?,?,?)", (order["id"], reason, str(body.get("details", "")).strip()))
        return {"id": cur.lastrowid, "status": "requested"}


@app.get("/api/faqs")
def faqs() -> list[dict[str, str]]:
    return [
        {"q": "Làm sao để đặt hàng trên PawPaw?", "a": "Chọn sản phẩm, thêm vào giỏ và hoàn tất thông tin giao hàng. PawPaw hiện hỗ trợ thanh toán khi nhận hàng."},
        {"q": "PawPaw giao hàng trong bao lâu?", "a": "Đơn nội thành thường đến trong 1–2 ngày làm việc. Nhân viên sẽ xác nhận thời gian dự kiến qua điện thoại."},
        {"q": "Tôi có thể đổi trả sản phẩm không?", "a": "Bạn có thể gửi yêu cầu trong 7 ngày từ khi nhận hàng nếu sản phẩm còn nguyên trạng. Đơn thức ăn đã mở có thể không đủ điều kiện đổi trả."},
        {"q": "Làm sao đặt lịch grooming hoặc khám thú y?", "a": "Mở mục Dịch vụ, chọn loại dịch vụ, thú cưng và khung giờ. PawPaw sẽ gọi xác nhận lịch."},
    ]


@app.get("/api/admin/dashboard")
def admin_dashboard(admin: dict[str, Any] = Depends(admin_user)) -> dict[str, Any]:
    with connect() as conn:
        totals = conn.execute("""SELECT COUNT(*) order_count, COALESCE(SUM(CASE WHEN status!='cancelled' THEN total_vnd ELSE 0 END),0) revenue,
                                 COALESCE(SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END),0) pending_count FROM orders""").fetchone()
        customers = conn.execute("SELECT COUNT(*) c FROM users WHERE role='customer'").fetchone()["c"]
        low = conn.execute("SELECT id,name,stock,emoji FROM products WHERE active=1 AND stock<=12 ORDER BY stock ASC LIMIT 5").fetchall()
        latest = conn.execute("SELECT * FROM orders ORDER BY created_at DESC LIMIT 5").fetchall()
        categories = conn.execute("SELECT category,COUNT(*) count FROM products WHERE active=1 GROUP BY category ORDER BY count DESC").fetchall()
    return {"revenue_vnd": totals["revenue"], "order_count": totals["order_count"], "pending_count": totals["pending_count"], "customer_count": customers, "low_stock": [dict(x) for x in low], "latest_orders": [dict(x) for x in latest], "categories": [dict(x) for x in categories]}


@app.get("/api/admin/orders")
def admin_orders(q: str = "", status: str = "", admin: dict[str, Any] = Depends(admin_user)) -> list[dict[str, Any]]:
    with connect() as conn:
        sql = "SELECT * FROM orders WHERE 1=1"
        params: list[Any] = []
        if q:
            sql += " AND (order_code LIKE ? OR customer_name LIKE ? OR phone LIKE ?)"
            params += [f"%{q}%"] * 3
        if status:
            sql += " AND status=?"
            params.append(status)
        rows = conn.execute(sql + " ORDER BY created_at DESC LIMIT 200", params).fetchall()
        return [order_view(conn, r) for r in rows]


@app.patch("/api/admin/orders/{order_id}")
async def update_order(order_id: int, request: Request, admin: dict[str, Any] = Depends(admin_user)) -> dict[str, Any]:
    require_csrf(request)
    body = await request.json()
    status = str(body.get("status", ""))
    allowed = {"pending", "confirmed", "preparing", "shipping", "delivered", "cancelled"}
    if status not in allowed:
        raise HTTPException(422, "Trạng thái đơn không hợp lệ")
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            if not row:
                raise HTTPException(404, "Không tìm thấy đơn")
            transitions = {"pending": {"confirmed", "cancelled"}, "confirmed": {"preparing", "cancelled"}, "preparing": {"shipping", "cancelled"}, "shipping": {"delivered"}, "delivered": set(), "cancelled": set()}
            if status != row["status"] and status not in transitions[row["status"]]:
                raise HTTPException(409, "Không thể chuyển đơn sang trạng thái này")
            if status == "cancelled" and row["status"] != "cancelled":
                restore_cancelled_stock(conn, row, admin["id"])
            conn.execute("UPDATE orders SET status=?,tracking_code=COALESCE(NULLIF(?,''),tracking_code) WHERE id=?", (status, str(body.get("trackingCode", "")), order_id))
            updated = order_view(conn, conn.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone())
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
    return updated


@app.get("/api/admin/products")
def admin_products(admin: dict[str, Any] = Depends(admin_user)) -> list[dict[str, Any]]:
    with connect() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM products ORDER BY id DESC").fetchall()]


def product_integer(value: Any, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, str)) or not re.fullmatch(r"[0-9]+", str(value).strip()):
        raise HTTPException(422, "Giá và tồn kho cần là số nguyên, không được để trống")
    number = int(value)
    if number < minimum or number > 2_147_483_647:
        raise HTTPException(422, "Giá bán phải lớn hơn 0; tồn kho và giá so sánh không được âm")
    return number


@app.post("/api/admin/products")
async def create_product(request: Request, admin: dict[str, Any] = Depends(admin_user)) -> dict[str, Any]:
    require_csrf(request)
    body = await request.json()
    name = str(body.get("name", "")).strip()
    slug = re.sub(r"[^a-z0-9]+", "-", str(body.get("slug", name)).lower()).strip("-")
    price = product_integer(body.get("price_vnd"), minimum=1)
    stock = product_integer(body.get("stock", 0))
    compare = product_integer(body.get("compare_price_vnd", 0))
    if len(name) < 3 or not slug:
        raise HTTPException(422, "Thông tin sản phẩm chưa hợp lệ")
    sku = str(body.get("sku", "")).strip() or "PP-" + secrets.token_hex(3).upper()
    with connect() as conn:
        try:
            cur = conn.execute("INSERT INTO products(slug,name,category,species,price_vnd,compare_price_vnd,stock,sku,emoji,description,featured) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (slug,name,str(body.get("category","Phụ kiện")),str(body.get("species","Chó")),price,compare,stock,sku,str(body.get("emoji","🐾")),str(body.get("description","")),int(bool(body.get("featured")))))
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc): raise HTTPException(409, "Slug hoặc SKU đã tồn tại")
            raise
        return dict(conn.execute("SELECT * FROM products WHERE id=?", (cur.lastrowid,)).fetchone())


@app.patch("/api/admin/products/{product_id}")
async def update_product(product_id: int, request: Request, admin: dict[str, Any] = Depends(admin_user)) -> dict[str, Any]:
    require_csrf(request)
    body = await request.json()
    fields = {"name": "name", "category": "category", "species": "species", "price_vnd": "price_vnd", "compare_price_vnd": "compare_price_vnd", "stock": "stock", "description": "description", "active": "active", "featured": "featured", "emoji": "emoji"}
    for key in ("price_vnd", "compare_price_vnd", "stock"):
        if key in body:
            body[key] = product_integer(body[key], minimum=1 if key == "price_vnd" else 0)
    updates = [(db, body[key]) for key, db in fields.items() if key in body]
    if not updates:
        raise HTTPException(422, "Không có nội dung cần cập nhật")
    with connect() as conn:
        if not conn.execute("SELECT id FROM products WHERE id=?", (product_id,)).fetchone(): raise HTTPException(404, "Không tìm thấy sản phẩm")
        conn.execute("UPDATE products SET " + ",".join(f"{name}=?" for name,_ in updates) + " WHERE id=?", [v for _,v in updates] + [product_id])
        return dict(conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone())


@app.post("/api/admin/inventory")
async def inventory_adjust(request: Request, admin: dict[str, Any] = Depends(admin_user)) -> dict[str, Any]:
    require_csrf(request)
    body = await request.json()
    try: product_id, delta = int(body.get("productId")), int(body.get("delta"))
    except (TypeError, ValueError): raise HTTPException(422, "Sản phẩm và số lượng không hợp lệ")
    if delta == 0 or abs(delta) > 10000: raise HTTPException(422, "Điều chỉnh phải khác 0 và không quá 10.000")
    with connect() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            row = conn.execute("SELECT stock FROM products WHERE id=?", (product_id,)).fetchone()
            if not row: raise HTTPException(404, "Không tìm thấy sản phẩm")
            if row["stock"] + delta < 0: raise HTTPException(409, "Tồn kho không thể âm")
            conn.execute("UPDATE products SET stock=stock+? WHERE id=?", (delta, product_id))
            cur = conn.execute("INSERT INTO inventory_events(product_id,delta,reason,actor_id) VALUES(?,?,?,?)", (product_id,delta,str(body.get("reason","Điều chỉnh thủ công"))[:160],admin["id"]))
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK"); raise
    return {"ok": True, "event_id": cur.lastrowid, "stock": row["stock"] + delta}


@app.get("/api/admin/customers")
def admin_customers(q: str = "", admin: dict[str, Any] = Depends(admin_user)) -> list[dict[str, Any]]:
    with connect() as conn:
        sql = """SELECT u.id,u.full_name,u.email,u.phone,u.created_at,COUNT(o.id) order_count,COALESCE(SUM(o.total_vnd),0) spent_vnd
                 FROM users u LEFT JOIN orders o ON o.user_id=u.id WHERE u.role='customer'"""
        params: list[Any] = []
        if q:
            sql += " AND (u.full_name LIKE ? OR u.email LIKE ? OR u.phone LIKE ?)"; params = [f"%{q}%"]*3
        return [dict(r) for r in conn.execute(sql + " GROUP BY u.id ORDER BY spent_vnd DESC LIMIT 200", params).fetchall()]


@app.get("/api/admin/promotions")
def admin_promotions(admin: dict[str, Any] = Depends(admin_user)) -> list[dict[str, Any]]:
    with connect() as conn: return [dict(r) for r in conn.execute("SELECT * FROM coupons ORDER BY code").fetchall()]


@app.post("/api/admin/promotions")
async def create_promotion(request: Request, admin: dict[str, Any] = Depends(admin_user)) -> dict[str, Any]:
    require_csrf(request); body = await request.json()
    code = re.sub(r"[^A-Z0-9]", "", str(body.get("code", "")).upper())
    typ = str(body.get("discount_type", "percent")); value = int(body.get("discount_value", 0))
    if len(code) < 4 or typ not in {"percent","fixed"} or value <= 0 or (typ == "percent" and value > 80): raise HTTPException(422, "Mã ưu đãi chưa hợp lệ")
    with connect() as conn:
        try: conn.execute("INSERT INTO coupons(code,discount_type,discount_value,minimum_vnd,usage_limit) VALUES(?,?,?,?,?)", (code,typ,value,int(body.get("minimum_vnd",0)),int(body.get("usage_limit",0))))
        except Exception as exc:
            if "UNIQUE constraint failed" in str(exc): raise HTTPException(409, "Mã ưu đãi đã tồn tại")
            raise
        return dict(conn.execute("SELECT * FROM coupons WHERE code=?", (code,)).fetchone())


@app.get("/api/admin/appointments")
def admin_appointments(admin: dict[str, Any] = Depends(admin_user)) -> list[dict[str, Any]]:
    with connect() as conn: return [dict(r) for r in conn.execute("SELECT * FROM appointments ORDER BY service_date DESC,time_slot LIMIT 200").fetchall()]


@app.patch("/api/admin/appointments/{appointment_id}")
async def update_appointment(appointment_id: int, request: Request, admin: dict[str, Any] = Depends(admin_user)) -> dict[str, Any]:
    require_csrf(request); body = await request.json(); status = str(body.get("status",""))
    if status not in {"requested","confirmed","completed","cancelled"}: raise HTTPException(422, "Trạng thái lịch hẹn không hợp lệ")
    with connect() as conn:
        cur = conn.execute("UPDATE appointments SET status=? WHERE id=?", (status,appointment_id))
        if not cur.rowcount: raise HTTPException(404,"Không tìm thấy lịch hẹn")
        return dict(conn.execute("SELECT * FROM appointments WHERE id=?", (appointment_id,)).fetchone())


@app.get("/api/admin/reports")
def admin_reports(admin: dict[str, Any] = Depends(admin_user)) -> dict[str, Any]:
    with connect() as conn:
        month = conn.execute("SELECT substr(created_at,1,7) month,COUNT(*) orders,COALESCE(SUM(total_vnd),0) revenue FROM orders WHERE status!='cancelled' GROUP BY month ORDER BY month DESC LIMIT 12").fetchall()
        best = conn.execute("SELECT i.product_name,SUM(i.quantity) units,SUM(i.unit_price_vnd*i.quantity) revenue FROM order_items i JOIN orders o ON o.id=i.order_id WHERE o.status!='cancelled' GROUP BY i.product_name ORDER BY units DESC LIMIT 8").fetchall()
        returns_count = conn.execute("SELECT COUNT(*) c FROM returns").fetchone()["c"]
    return {"months": [dict(r) for r in reversed(month)], "best_sellers": [dict(r) for r in best], "returns_count": returns_count}


@app.get("/api/admin/settings")
def admin_settings(admin: dict[str, Any] = Depends(admin_user)) -> dict[str, str]:
    with connect() as conn: return {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM settings").fetchall()}


@app.patch("/api/admin/settings")
async def update_settings(request: Request, admin: dict[str, Any] = Depends(admin_user)) -> dict[str, str]:
    require_csrf(request); body = await request.json()
    allowed = {"store_name","free_shipping_from_vnd","support_phone","support_email","store_address"}
    with connect() as conn:
        for k,v in body.items():
            if k in allowed: conn.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k,str(v)[:200]))
        return {r["key"]: r["value"] for r in conn.execute("SELECT key,value FROM settings").fetchall()}


@app.get("/{path:path}", include_in_schema=False)
def web(path: str) -> FileResponse:
    # Client-side route map handles storefront and admin pages; unknown URLs land on the branded 404 view.
    if path.startswith("api/"):
        raise HTTPException(404, "API route not found")
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})
