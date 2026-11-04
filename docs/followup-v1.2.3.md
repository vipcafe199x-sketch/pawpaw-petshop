# v1.2.3 — Xóa sản phẩm và tự làm mới phiên biểu mẫu

## Xóa sản phẩm thật

Nút Xóa có ở bảng Sản phẩm/Kho hàng; dialog Sửa có nút Xóa sản phẩm. Mở xác nhận hiển thị đúng tên, SKU, giá và tồn hiện tại. Admin phải nhập chính xác SKU rồi bấm **Xóa vĩnh viễn**. Bấm Hủy, Escape hoặc nhập sai SKU không gửi lệnh xóa.

- Sản phẩm **chưa từng gắn với đơn hàng đang được lưu**: xóa vật lý dòng trong `products`, biến khỏi admin, shop, tìm kiếm và chi tiết công khai.
- Có `order_items` tham chiếu sản phẩm, kể cả đơn đã hủy: API trả 409, UI khóa xác nhận khi đã biết có đơn. Chỉ nên chuyển sang Nháp; không xóa/sửa đơn để vượt chặn.
- Tồn kho thay đổi sau khi mở xác nhận: API trả 409, yêu cầu mở lại để kiểm tra.
- API `DELETE /api/admin/products/{id}` yêu cầu quyền admin, CSRF hợp lệ, body có `confirm_sku` và `expected_stock`. Không có thao tác xóa bằng GET.

Trước khi xóa, sản phẩm và toàn bộ lịch sử kho liên quan được chụp vào `operational_adjustments` với `event_type=product_deleted`, ID sản phẩm, actor admin và thời gian. Các dòng `inventory_events` liên quan được chuyển vào bản chụp này rồi bỏ khỏi bảng kho hiện hành để giải phóng khóa ngoại. Việc lưu bản chụp, xóa nhật ký hiện hành và xóa sản phẩm diễn ra trong cùng `BEGIN IMMEDIATE`; lỗi ở bất kỳ bước nào rollback toàn bộ. Checkout và điều chỉnh kho cũng dùng giao dịch khóa ghi để tránh lọt đơn/ghi kho giữa bước kiểm tra và xóa.

Đây là xóa thật trong danh mục, không có nút Khôi phục trong UI. Bản chụp kiểm toán dùng để đối soát/khôi phục thủ công có kiểm soát, không tự chạy. File ảnh upload được giữ lại vì có thể đang được tham chiếu ở nơi khác. Không có job tự xóa theo tên, SKU hoặc thời gian; migration/deploy không dọn dữ liệu test.

### PP-TEST-001 và ABC

Release **không tự xóa** PP-TEST-001 hoặc ABC/PP-2FF7ED. Khi chủ shop quyết định dọn, tìm đúng SKU trong admin, mở Xóa, kiểm tra thông tin rồi nhập SKU để xác nhận. Nếu đã có đơn, ứng dụng chặn xóa và có thể dùng Nháp để ẩn.

## Tại sao lần lưu đầu có thể báo hết phiên?

Cookie CSRF sống 1 giờ, phiên đăng nhập 7 ngày. Trước đây mỗi GET `/api/csrf` luôn sinh token mới; mở tab khác có thể đổi cookie trong khi tab cũ còn giữ token cũ. Cookie hết hạn hoặc lệch token gây thông báo lỗi dù phiên đăng nhập vẫn còn.

Bản sửa:

1. GET `/api/csrf` dùng lại cookie có chữ ký hợp lệ, gia hạn cookie; chỉ tạo token mới khi cookie thiếu/không hợp lệ. Mở tab mới không chủ động vô hiệu token hợp lệ của tab khác.
2. API ghi dữ liệu vẫn kiểm tra Origin và CSRF trước khi thay đổi. Lỗi CSRF trả 403 với `detail.code=csrf_expired`, phân biệt lỗi quyền/Origin.
3. Client nhận đúng mã này sẽ lấy token mới rồi gửi lại **một lần**, cùng payload. Các yêu cầu cùng tab dùng chung một lần refresh đang chạy. Nếu chưa có token, lấy token trước khi gửi.
4. Upload ảnh dùng cùng cơ chế, gửi lại nguyên File/Blob, không chuyển file thành JSON. Nút lưu có khóa bận chống bấm lặp.
5. Không tự thử lại với 401, lỗi quyền, Origin, 409, 5xx hoặc lỗi mạng vì không thể chắc yêu cầu trước đã được áp dụng hay chưa. CSRF bị từ chối lần hai thì báo lỗi, không lặp vô hạn. Làm mới phiên thất bại giữ form và dữ liệu đang nhập để người dùng thử lại. Phiên đăng nhập hết hạn thật vẫn yêu cầu đăng nhập.

Token không được đưa vào log hoặc lưu trong repo. Không bỏ kiểm tra CSRF/Origin/quyền admin. Quyền xóa không mở cho khách hàng.

## Liên hệ và dữ liệu đã đạt

Không thêm hotline/email/địa chỉ mẫu. Khi chủ shop có dữ liệu thật, Cài đặt lưu vào `settings`, trang hỗ trợ đọc cùng nguồn. Giữ kiểm tra gửi liên hệ trống không xóa giá trị cũ. Không tạo WELCOME10/bánh thưởng, không thay đổi giá/tồn PP-005/006/007, không sửa coupon PAWPAW10, đơn hàng hoặc báo cáo trong deploy.

## Kiểm thử

36 test API/database + 25 test DOM. Toàn bộ suite v1.2.2 cùng các tình huống mới: tạo/sửa/xóa vật lý, kiểm toán nhật ký, SKU sai/Hủy/tồn cũ không xóa, chặn đơn thường và đơn hủy, auth/CSRF/Origin, rollback khi xóa lỗi, cookie CSRF ổn định, từ chối trước khi ghi, tự refresh và thử lại một lần với tạo/upload/xóa, cùng payload, chống bấm lưu lặp, giới hạn retry và giữ form khi refresh lỗi.

Dữ liệu test là database QA tạm. Không tự chạy tạo/sửa/xóa thử trên production; chưa xác minh trực tiếp thao tác/bố cục Safari/iPhone. Deploy sao lưu và kiểm tra catalog không đổi, kiểm tra health/build mới; không xuất nội dung database hoặc backup vào log GitHub.
