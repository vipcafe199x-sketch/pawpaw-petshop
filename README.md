# PawPaw Pet Shop · Full-stack MVP

Vietnamese pet shop based on the attached storefront and admin screen designs.

## FE · BE · Database

```text
frontend/                 HTML/CSS/JS: shop, account, booking, support, admin UI
backend/main.py           FastAPI routes and authentication/authorization
backend/services/         Domain/application services (transactional checkout)
backend/database.py       SQLite connection, seed data, database bootstrap
backend/security.py       Password/session/CSRF helpers
db/migrations/            Versioned SQL schema
contracts/openapi.yaml    API contract
docs/                     Audit, backend design, data model, AWS handoff
deploy/aws/               Lightsail run/backup instructions
```

## Local run

Requires Python 3.12+ and the packages in `requirements.txt`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`. Configure `ADMIN_EMAIL` and `ADMIN_PASSWORD` in the deployment environment before starting the application. API docs: `/api/docs` in development.

## Tests

```bash
python -m unittest discover -s tests -v
```

## AWS

See [deploy/aws/deploy-lightsail.md](deploy/aws/deploy-lightsail.md). Single Lightsail VM + FastAPI + SQLite volume + Caddy is the low-cost pilot architecture. Real payment providers, shipping, email and domain credentials are intentionally not guessed. This workspace did not have AWS CLI or account credentials, so resources were not created.

## Fix 11 lỗi nghiệp vụ (04/11/2026)

Xem [bàn giao và khôi phục dữ liệu](docs/fix-11-issues.md). Miễn phí vận chuyển tính theo tạm tính **trước giảm giá**; hủy đơn hoàn kho trong cùng giao dịch và không cộng lặp.

Chạy kiểm tra FE (Node.js 20+; dependency chỉ dùng để test, không cần cho server Python):

```bash
npm ci --ignore-scripts
npm test
```

Công cụ dữ liệu mặc định chỉ xem trước, không chạy khi khởi động app:

```bash
python -m backend.repair_reported_data
```

## v1.1.4 follow-up

Xem [hướng dẫn kiểm tra, bảo vệ database và sửa dữ liệu cũ](docs/followup-v1.1.4.md). Báo giá coupon trước đặt hàng dùng `/api/orders/quote` và cùng phép tính với tạo đơn. Deploy hiện yêu cầu database đang tồn tại trong volume, sao lưu rồi kiểm tra khởi tạo không đổi catalog.

## v1.2.0 quản trị

Xem [phạm vi, cách sử dụng, kiểm thử và dọn dữ liệu test an toàn](docs/admin-v1.2.0.md). Có form sản phẩm đầy đủ và upload ảnh persistent, điều chỉnh kho có lý do, quản lý mã giảm giá, chi tiết khách hàng, báo cáo theo ngày và tìm kiếm chung. Các tab chưa triển khai đã được ẩn.

## v1.2.1 follow-up

[Hướng dẫn khôi phục production từng bước, dọn ABC an toàn và cách đối soát doanh thu](docs/followup-v1.2.1.md). Shop ẩn nháp/không giá; ngày ưu đãi và liên hệ được bảo vệ khỏi ô trống; báo cáo có phần đối soát và toàn bộ sản phẩm bán chạy.

## v1.2.2 nguồn dữ liệu

[Làm rõ PP-005, sản phẩm bánh thưởng, WELCOME10, liên hệ thật và ABC](docs/followup-v1.2.2.md). Trang hỗ trợ dùng settings, bỏ liên hệ mẫu. Công cụ `python -m backend.catalog_evidence` chạy chỉ đọc tại máy chủ của chủ shop để đối chiếu backup; không tự tạo/xóa/khôi phục dữ liệu.

## v1.2.3 quản lý sản phẩm

[Xóa sản phẩm có xác nhận, chặn liên kết đơn hàng và tự làm mới phiên biểu mẫu](docs/followup-v1.2.3.md). Chưa tự dọn PP-TEST-001/ABC; thử nghiệm tạo/sửa/xóa chỉ chạy trên QA.

## v1.2.4 giỏ hàng và bộ lọc

[Đối chiếu PAWPAW10 10%, điều kiện lấy từ báo giá server và đếm đúng sản phẩm sau lọc](docs/followup-v1.2.4.md).
