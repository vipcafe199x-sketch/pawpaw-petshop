# v1.2.5 — Gia cố và phạm vi kiểm tra bảo mật

## Những thay đổi cụ thể

### Tài liệu API

Production đặt `openapi_url=None`, không chỉ tắt Swagger UI. `/openapi.json`, `/docs`, `/redoc`, `/api/docs`, `/api/openapi.json` trả 404, không fallback thành trang SPA. Schema còn tại `/api/admin/openapi.json`, yêu cầu đăng nhập admin và `Cache-Control: no-store`. Local/development giữ schema để phát triển. Các đường nhạy cảm dạng `/.env`, `/.git/config` trả 404 rõ ràng; ứng dụng không đọc file theo đường dẫn URL.

Ẩn schema không thay thế kiểm tra quyền. Mọi API admin vẫn có dependency xác thực/phân quyền; API ghi vẫn kiểm CSRF và Origin trước khi ghi.

### Giới hạn đăng nhập

Trước đây bộ đếm chỉ theo IP và bị xóa khi bất kỳ tài khoản nào đăng nhập thành công. Nay dùng hai bộ đếm lỗi trong 15 phút: tối đa 8 lần thất bại cho cặp IP+tài khoản và 40 lần thất bại cộng dồn theo IP. Lần vượt giới hạn trả 429 cùng Retry-After. Thành công chỉ xóa lỗi của đúng cặp IP+tài khoản; không xóa lỗi của tài khoản khác hoặc lỗi cộng dồn IP. Cache giới hạn 4096 nhóm, dùng đồng hồ monotonic và khóa đồng bộ.

Giới hạn này nằm trong một process, mất khi restart, không đồng bộ giữa nhiều worker/instance và không chặn được toàn bộ tấn công phân tán. Image hiện chạy 1 worker. Khi mở rộng cần shared rate limiter/WAF. Phải cấu hình trusted proxy chính xác trước khi coi request.client.host là IP khách thật; không tin tùy ý X-Forwarded-For từ Internet. Người dùng sau cùng proxy/NAT có thể chia sẻ giới hạn IP. Không kiểm thử dò mật khẩu/khóa tài khoản thật trên production.

### Header phiên bản

Docker chạy Uvicorn với `--no-server-header`. Helper `deploy/nginx/harden_server_tokens.py` bổ sung snippet HTTP `server_tokens off;`. Helper không sửa vhost, proxy routes, TLS/certificates hoặc cài package; kiểm tra `nginx -t` trước/sau và reload graceful. Nếu cấu hình mới lỗi, khôi phục snippet trước và kiểm tra lại. Không ghi đè snippet không do helper quản lý hoặc symlink. Trường hợp cấu hình khác định nghĩa trùng/ghi đè directive cần xử lý riêng, không ép sửa toàn bộ nginx.conf.

Workflow chỉ gọi helper khi header công khai còn lộ phiên bản nginx, rồi kiểm tra lại bằng HTTPS. Cần quyền sudo không tương tác cho thao tác này. Header `Server: nginx` không có số phiên bản là kết quả mong đợi; không hứa xóa hẳn tên nginx.

Ẩn phiên bản không chứng minh đã vá. Không tự nâng cấp package Nginx/Ubuntu hoặc suy luận trạng thái CVE từ tên phiên bản. Chủ máy chủ cần kiểm tra bản vá theo kho Ubuntu và lên lịch nâng cấp/khởi động lại khi cần.

## Những kiểm tra đã chạy trên QA

46 test API/database + 27 test DOM, gồm suite kinh doanh trước đó và:

- 13 đường đọc admin (gồm schema riêng): chưa đăng nhập nhận 401, khách thường nhận 403.
- 11 đường ghi admin, gồm sửa/xóa sản phẩm và upload: khách/anonymous không được gọi.
- 19 đường POST/PATCH/DELETE từ auth, giỏ/đơn, booking/returns tới admin: thiếu CSRF hoặc Origin khác bị từ chối trước khi thay đổi các bảng được kiểm tra.
- Khách A/B chỉ thấy đơn của mình trong `/api/account/orders`; khách không xem chi tiết qua API admin. Tra cứu/đổi trả với sai mã hoặc SĐT bị từ chối.
- Giá từng sản phẩm, giảm giá, ship và user_id gửi giả từ trình duyệt không ghi đè phép tính/quyền sở hữu server. Tổng xem lại sai bị 409 và không trừ kho.
- Một process production QA riêng xác nhận schema công khai 404, schema admin 401/200, cookie Secure/HttpOnly/SameSite=Lax và header HSTS/frame protection.
- Rate limit: 8 lần sai, đăng nhập tài khoản khác không reset giới hạn mục tiêu, Retry-After, hết cửa sổ và cache có giới hạn.
- SQLite backup QA được phục hồi vào file khác, integrity_check và giá trị đơn/tồn khớp. Không khôi phục đè production hoặc xuất backup lên log.
- Snippet Nginx: tạo hợp lệ, chạy lại không đổi, rollback khi syntax test lỗi, không ghi đè file không quản lý. Kiểm tra header thật nằm trong job deploy.

## Các giới hạn chưa giải quyết/không được đánh đồng

1. **MFA admin chưa được tích hợp/bật.** Cần thiết kế đăng ký thiết bị và khôi phục trước khi bật để tránh khóa chủ shop khỏi hệ thống.
2. **Tra cứu khách vãng lai dùng code+phone.** Ai có cả hai thông tin có thể tra cứu, không phải cơ chế ownership theo tài khoản và chưa có OTP. Cần cân nhắc OTP, giới hạn tra cứu và giảm dữ liệu trả về trước khi bán thật. Không đổi âm thầm luồng tra cứu đang chạy trong bản này.
3. **Audit chưa đầy đủ mọi thay đổi admin.** Xóa sản phẩm, sửa vận hành thủ công và nhật ký kho có dấu vết; chưa có hệ thống cảnh báo/SIEM hoặc audit đồng nhất cho mọi trường thay đổi.
4. **Backup production:** deploy sao lưu và kiểm tra catalog; phục hồi thực tế của backup production, lịch backup định kỳ, retention, mã hóa và bản sao ngoài máy chủ chưa được xác minh. Test khôi phục chỉ là QA.
5. **Hạ tầng:** chưa audit SSH, firewall, Docker socket, hệ điều hành, trạng thái cập nhật package, trusted proxy và lịch tự gia hạn chứng chỉ. HTTPS health check không tương đương chứng minh auto-renew đang hoạt động. Chủ máy chủ có thể kiểm tra `systemctl status certbot.timer` và thử gia hạn có kiểm soát.
6. Chưa có kiểm thử xâm nhập toàn diện, tải cao hoặc tấn công phân tán. Một số chuỗi XSS/SQL thử nghiệm hay 401/403 không đại diện toàn bộ web. Không tuyên bố web “khó hack” hay không còn lỗ hổng.

## PAWPAW10

Mức đúng đã chốt là 10% và đã sửa qua admin ở v1.2.4. Khi đó kiểm tra trên web thật giỏ/checkout: 320.000₫ − 32.000₫, ship 0₫ = 288.000₫. Báo cáo 30% mô tả trạng thái trước lúc sửa. Bản security này không reseed hoặc đổi cấu hình coupon; test QA 10%/cấu hình động tiếp tục nằm trong suite. Cấu hình hiện tại cần đọc trên web tại thời điểm kiểm tra; không lấy mô tả cũ thay cho dữ liệu server.

## Tham chiếu chính thức

- https://fastapi.tiangolo.com/how-to/conditional-openapi/
- https://nginx.org/en/docs/http/ngx_http_core_module.html#server_tokens
