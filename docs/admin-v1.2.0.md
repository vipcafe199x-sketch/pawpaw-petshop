# Quản trị v1.2.0

## Phạm vi đã sửa

| Mục phản hồi | Hành vi mới |
|---|---|
| 1, 3 | Thêm/sửa sản phẩm bằng dialog có SKU, tên, danh mục, loài, thương hiệu, mô tả, thông số, giá bán, giá gốc, tồn kho, nổi bật và ảnh thật. SKU/slug cố định khi sửa. |
| 2, 9 | Nút bổ sung/điều chỉnh và nút + mở dialog chọn sản phẩm, số lượng có dấu và lý do. Không nhận rỗng, 0, quá ±10.000 hoặc làm tồn âm. Ghi nhật ký nhập/xuất. |
| 4 | Đã hủy/đã giao khóa dropdown. API cũng khóa; không thể hồi sinh đơn. |
| 5 | Tạo/sửa/tắt mã giảm giá: phần trăm hoặc số tiền, đơn tối thiểu, lượt dùng, ngày bắt đầu/kết thúc, trạng thái. Lượt đã dùng không bị reset khi sửa. |
| 6, 7, 18 | Ẩn tab cài đặt chưa có backend, tab chiến dịch/chương trình, dịch vụ/nhân viên và tab báo cáo giả; bỏ Thiết lập nhanh tĩnh. Kho có lịch sử điều chỉnh thật thay các tab phiếu giả. |
| 8, 17 | Dòng khách mở chi tiết, sửa liên hệ, xem lịch sử đơn. 0 chi tiêu là Thành viên mới; sau đó Bạc <3 triệu, Vàng <10 triệu, Kim cương ≥10 triệu. Có ngừng/kích hoạt lại tài khoản, giữ đơn hàng. |
| 10, 16 | Ngưỡng tồn thấp mặc định ≤5, chỉnh được ở Cài đặt; phân biệt nháp/chưa giá, hết hàng, sắp hết, đang bán. |
| 11, 15, 19 | Dashboard và Báo cáo dùng cùng dữ liệu: đơn hợp lệ trừ đơn hủy; hiện riêng tổng đơn và đơn hủy. Chọn hôm nay/tuần/tháng/tùy chọn, nhóm ngày/tuần/tháng. Biểu đồ cột hiện cả khi chỉ một kỳ. CSV xuất tổng hợp và sản phẩm bán chạy, không phải CSV đơn hàng. |
| 12 | Lịch chỉ chờ → xác nhận → hoàn thành/hủy; chờ cũng có thể hủy. Đánh dấu ngày có lịch, chọn tháng/ngày. |
| 13, 14 | Tìm kiếm chung Enter tìm sản phẩm/SKU/thương hiệu, đơn, khách. Footer bảng đếm đúng số dòng lọc. |

Doanh thu tổng quan = tổng tiền sau giảm và phí ship của tất cả đơn chưa hủy (không đồng nghĩa tiền đã thu). Doanh thu từng sản phẩm trong báo cáo = đơn giá × số lượng trước phân bổ mã giảm/ship; không cộng ngang để đối chiếu tổng tiền đơn. Ngày báo cáo, ngày áp dụng coupon dùng Asia/Ho_Chi_Minh. Các mốc ngày bao gồm cả ngày bắt đầu và kết thúc.

## Ảnh và dữ liệu khi deploy

Ảnh JPEG/PNG/WebP tối đa 5 MB, 20 megapixel được kiểm tra, chuyển thành WebP tối đa 2000×2000, tên ngẫu nhiên. Lưu tại thư mục `uploads` cùng cấp file `DATABASE_PATH`, thuộc volume dữ liệu hiện có. Không lưu trong filesystem tạm của image Docker. Khi backup toàn bộ cửa hàng cần sao lưu cả database và thư mục ảnh. Bỏ ảnh khỏi sản phẩm không tự xóa file vật lý.

Migration chỉ bổ sung cột mới và ngưỡng mặc định bằng INSERT OR IGNORE. Không reseed, không chỉnh giá/tồn hiện có. Deployment guard sao lưu SQLite trước migration và so sánh toàn bộ cột catalog đã tồn tại trước migration. Form sửa có kiểm tra tồn kho gốc: nếu đơn hàng/nhân viên khác vừa đổi kho, từ chối lưu form cũ để tránh ghi đè.

## Dọn dữ liệu test an toàn (chưa thực hiện trên production)

1. Sao lưu database và ảnh, ghi lại ID/SKU/mã đơn cụ thể và quan hệ đơn hàng trước khi dọn; xác nhận danh sách với chủ shop.
2. Sản phẩm test: mở Sản phẩm → Sửa → bỏ Đang kinh doanh. Sản phẩm biến khỏi shop, lịch sử đơn và nhật ký kho được giữ.
3. Khách test: mở Khách hàng → Chi tiết → bỏ Tài khoản hoạt động. Phiên đăng nhập bị thu hồi; không xóa lịch sử. Dùng “Xem cả tài khoản ngừng hoạt động” để mở và bật lại nếu cần.
4. Đơn test đã hủy: giữ nguyên để đối soát việc hoàn kho; doanh thu/đơn hợp lệ đã loại trừ. Không tự DELETE đơn hoặc order_items vì có liên kết nhật ký kho/đổi trả/coupon. Xóa vĩnh viễn chỉ sau khi chủ shop xác nhận từng ID và có kế hoạch xử lý quan hệ, backup/khôi phục rõ ràng.

Không có script tự dọn dữ liệu production hoặc tự chạy công cụ sửa tồn kho trong release này.

## Kiểm chứng

Chạy `python -m unittest discover -s tests -v` (24 API/DB tests) và `npm ci && npm test` (13 DOM tests). Dữ liệu test nằm trong SQLite tạm, không dùng production. Bao gồm checkout COD, đăng ký/đăng nhập, báo giá, hủy hoàn kho đúng một lần/rollback, migration không đổi catalog, metadata/upload, điều chỉnh kho, coupon, trạng thái cuối, lịch chuyển tiếp, khách hàng và báo cáo ngày Việt Nam. DOM tests mở mọi màn admin, bấm tạo/sửa/hủy form, tìm kiếm/đếm dòng, biểu đồ/CSV/lịch và đồng bộ trạng thái.

Giới hạn: test DOM không thay thế kiểm tra layout hoặc thao tác trực tiếp trên Safari/iPhone. Production yêu cầu đăng nhập admin riêng; chưa tự tạo/sửa dữ liệu thử trên production.
