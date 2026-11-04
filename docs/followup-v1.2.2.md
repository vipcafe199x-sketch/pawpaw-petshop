# v1.2.2 — Làm rõ nguồn dữ liệu và liên hệ cửa hàng

## 1. PP-005 và “Bánh thưởng dâu tây”

Trong seed đầu tiên, commit `0c1fcfc`, phần tử thứ năm là `dem-ngu-meo` / “Đệm ngủ êm ái cho mèo”; SKU sinh bằng chỉ số `PP-005`. PP-006 là Bóng dây thừng, PP-007 là Cá nhồi bông. Lịch sử thay đổi `backend/database.py` và `db/` không có seed “Bánh thưởng dâu tây”. Các lần khôi phục v1.2.1 chỉ chỉnh giá/tồn/bật bán, không thay tên/slug.

**Kết luận có bằng chứng:** trong dữ liệu gốc của repo, bánh thưởng không phải PP-005. Snapshot production đã đối chiếu ở v1.2.1 và kết quả người dùng kiểm tra không có sản phẩm mang tên này. **Chưa thể kết luận** một sản phẩm riêng đã từng được tạo rồi bị xóa, hoặc chưa từng tồn tại trên bất kỳ database nào. Repo không lưu đầy đủ audit xóa/SQL ngoài ứng dụng. Chưa kiểm tra được các backup production trong lượt này.

Không tự tạo hoặc đổi tên sản phẩm. Nếu chủ shop xác nhận đây là hàng riêng cần tạo lại:

1. Tìm tên, SKU và slug gần giống trong admin, đối chiếu backup bằng công cụ ở cuối tài liệu.
2. Chọn SKU mới, ví dụ `PP-STRAWBERRY-001`, slug `banh-thuong-dau-tay`. Kiểm tra cả hai chưa được dùng; tên không phải khóa chống trùng. Không tái dùng PP-005.
3. Đề xuất theo yêu cầu: tên Bánh thưởng dâu tây, giá 299.000₫, tồn ban đầu 11. Cần chủ shop xác nhận hàng thật, thương hiệu, khối lượng, loài phù hợp, ảnh và nguồn tồn trước khi lưu/bật bán.
4. Chỉ thực hiện tạo sau xác nhận. v1.2.2 không tạo sản phẩm này, không thay giá/tồn của PP-005/006/007.

## 2. WELCOME10 và form ngày

Seed repo chỉ có PAWPAW10. Lịch sử seed không có WELCOME10. Theo snapshot production v1.2.1 và lượt kiểm tra của người dùng, hiện chỉ có PAWPAW10. API sửa mã giữ code cố định; không có endpoint đổi mã hoặc xóa mã. Điều này không chứng minh không từng có thao tác SQL, database khác hoặc bản backup chứa WELCOME10.

Không đủ bằng chứng để khẳng định WELCOME10 đã bị xóa, đổi tên hay chưa từng tồn tại. Không tự tạo lại mã để “lấp chỗ trống”. Công cụ chỉ đọc bên dưới có thể tìm WELCOME10 trong backup và đếm tham chiếu coupon trong đơn cũ. Vẫn cần hiểu rằng snapshot không chứa mọi thời điểm.

Form sửa **nạp starts_at/expires_at thực từ database**. Ngày ISO/Vietnamese được chuẩn hóa cho date input; UI hiện thêm “Ngày lấy từ database: …”. PAWPAW10 chưa lưu giới hạn ngày thì hai ô trống và nhãn Không giới hạn là đúng. Thử nghiệm QA tạo mã riêng có ngày, mở/sửa/mở lại và mở–Hủy nhiều lần: ngày giữ đúng; gửi ô trống không xóa giới hạn nếu chưa xác nhận. Không tạo mã thử trên production.

## 3. Liên hệ thật lấy từ đâu?

Nguồn duy nhất: bảng `settings` trong database đang chạy, các khóa:

| Form | Khóa | Nguồn đọc |
|---|---|---|
| Số điện thoại | support_phone | GET /api/admin/settings |
| Email | support_email | GET /api/admin/settings |
| Địa chỉ | store_address | GET /api/admin/settings |
| Trang hỗ trợ công khai | Cùng ba khóa | GET /api/storefront/settings |

Snapshot đã kiểm tra chưa có ba khóa liên hệ; người dùng cũng thấy Chưa cấu hình. Các số/email/địa chỉ từng viết cứng trong giao diện cũ là nội dung mẫu, không phải bằng chứng thông tin thật của cửa hàng. Không lấy email quản trị làm email hỗ trợ hoặc sao chép thông tin mẫu vào database.

v1.2.2 bỏ liên hệ mẫu khỏi trang hỗ trợ và các hàm header/footer cũ, dùng dữ liệu settings thật. Nếu thiếu thì thông báo chưa cấu hình, không có nút gọi số mẫu. Admin ghi rõ nguồn dữ liệu, vẫn nạp giá trị đã lưu, cho để trống, gửi trống không xóa liên hệ cũ. Sau khi chủ shop nhập liên hệ thật và lưu, settings được cập nhật trong phiên hiện tại; khách tải trang sẽ đọc dữ liệu mới.

Chưa có thông tin được chủ shop xác nhận nên release không tự điền số/email/địa chỉ. Chủ shop có thể cung cấp ba giá trị hoặc tự lưu trong Cài đặt.

## 4. ABC — chưa xóa, chưa ẩn

Theo dữ liệu đã xác minh: ABC / `PP-2FF7ED`, giá 99.000₫, tồn 10, đang bán. Release không thay đổi dữ liệu này.

Sau khi chủ shop xác nhận dọn đúng SKU: Sản phẩm → tìm `PP-2FF7ED` → Sửa → bỏ Đang kinh doanh → Lưu. Đây là ẩn có thể bật lại, giữ đơn/nhật ký; không xóa vật lý. Kiểm tra shop không còn ABC và admin vẫn tra được hàng đã ẩn. Nếu cần xóa vĩnh viễn phải có xác nhận riêng và backup/đối soát liên kết đơn hàng.

## Công cụ bằng chứng chạy trực tiếp trên máy chủ

Chạy sau khi deploy v1.2.2, trong SSH/terminal riêng của chủ shop:

```bash
docker exec pawpaw python -m backend.catalog_evidence > /opt/pawpaw/catalog-evidence.json
```

Không cần dừng web. Công cụ mở SQLite với `mode=ro`, không seed, không sửa, không khôi phục. Kiểm tra database hiện tại và tối đa 100 file backup trong `deploy-backups/*.sqlite3` và `*.before-repair-*.bak`, báo số backup có/đã quét và cờ truncated. Không gửi kết quả lên mạng; không cấu hình workflow chạy công cụ này hay ghi dữ liệu production vào log GitHub. Giữ file kết quả trong máy chủ của chủ shop.

Kết quả có tên nguồn snapshot, danh tính PP-005, các tên bánh thưởng/dâu tây tìm được, code/ngày coupon, số tham chiếu tên sản phẩm/mã WELCOME10 trong đơn và cờ có/không liên hệ. Không xuất khách hàng, phiên đăng nhập, mật khẩu hoặc giá trị liên hệ. `unreadable` nghĩa là nguồn đó chưa kiểm tra được. Không tìm thấy trong backup không chứng minh chắc chắn chưa từng tồn tại. Nếu tìm thấy thì đối chiếu timestamp/nguồn trước khi quyết định khôi phục; công cụ không tự sửa.

## Kiểm thử và giới hạn

30 test API/database + 19 test DOM, gồm toàn bộ suite v1.2.1, form ngày có/không giới hạn, mở–Hủy không ghi, liên hệ lấy từ settings và không dùng mẫu, render admin/shop, checkout/hủy hoàn kho, giữ số liệu báo cáo, và công cụ snapshot không đổi database. Dữ liệu QA ở database tạm. Chưa kiểm tra thao tác/bố cục trực tiếp Safari/iPhone hoặc chạy công cụ backup trên production trong lượt này.
