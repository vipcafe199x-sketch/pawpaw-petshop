# v1.2.1 — catalog công khai, ngày khuyến mãi và đối soát

## Khôi phục giá/tồn production: lệnh chạy thật, không tự chạy khi deploy

Release không tự sửa catalog production. Khôi phục phải thực hiện riêng theo các bước dưới trên máy chủ đang có Docker container `pawpaw`. Không chạy trên máy local với DATABASE_PATH mặc định rồi tưởng đã sửa production.

**SKU là khóa định danh.** Báo lỗi gần đây gán các tên khác nhau cho cùng SKU; repo gốc có PP-005 Đệm ngủ êm ái cho mèo, PP-006 Bóng dây thừng cho chó, PP-007 Đồ chơi cá nhồi bông. Các lệnh dưới dùng đúng ba SKU và giá/tồn được chủ shop yêu cầu. Chúng không đổi tên, slug, ảnh, mô tả, không tạo “Bánh thưởng dâu tây”. Nếu bước 1 cho thấy nhầm SKU/sản phẩm, dừng và đối soát tên/slug trước khi ghi; đừng đoán hoặc đổi tên sản phẩm khác thành bánh thưởng.

1. Đọc dữ liệu **trong production** (không sửa):

```bash
docker exec pawpaw python -m backend.repair_reported_data --catalog
```

2. Xem trước đúng ba SKU; kiểm tra `name`, `slug`, `before`, `after`. Chỉ sửa hàng đang đồng thời giá 0 và tồn 0:

```bash
docker exec pawpaw python -m backend.repair_reported_data --only-explicit-products --activate-repaired --repair-product PP-005:299000:11 --repair-product PP-006:79000:42 --repair-product PP-007:89000:24
```

3. Khi danh tính đã đúng, lệnh **ghi thật** (khác bước 2 ở `--apply`):

```bash
docker exec pawpaw python -m backend.repair_reported_data --only-explicit-products --activate-repaired --repair-product PP-005:299000:11 --repair-product PP-006:79000:42 --repair-product PP-007:89000:24 --apply
```

Công cụ tự tạo backup SQLite cạnh file database trước khi ghi. Kết quả phải có `applied: true`, đường dẫn `backup`, và ba `actions` có `after` gồm giá/tồn tương ứng + `active: 1`. Nhập kho được ghi nhật ký. Nếu `skipped`, không kết luận SKU đó đã sửa; kiểm tra lại bước 1. Chạy lại không ghi đè giá/tồn đã khác 0, không cộng tồn thêm. Cờ `--only-explicit-products` không sửa PP-010 hay SKU nào ngoài ba SKU chỉ định. Chạy trong thời gian bảo trì và kiểm tra lại ngay, vì đơn mua thật sau khôi phục có thể giảm tồn hợp lệ.

4. Xác minh dữ liệu sau ghi:

```bash
docker exec pawpaw python -m backend.repair_reported_data --catalog
```

| SKU | Giá mong đợi (₫) | Tồn ngay sau sửa | active |
|---|---:|---:|---:|
| PP-005 | 299000 | 11 | 1 |
| PP-006 | 79000 | 42 | 1 |
| PP-007 | 89000 | 24 | 1 |

Sau đó tìm từng SKU trong shop và admin. Không chỉ nhìn thông báo thành công. Không có sản phẩm tên “Bánh thưởng dâu tây” thì cần tạo sản phẩm mới với SKU riêng và thông tin thật; khôi phục ba SKU không tạo ra nó.

## Dọn ABC an toàn (chưa thực hiện)

ABC có SKU `PP-2FF7ED` theo báo lỗi. Sau khi chủ shop xác nhận đúng hàng test, vào Sản phẩm → tìm SKU → Sửa → bỏ Đang kinh doanh → Lưu. Đây là ẩn có thể bật lại, giữ nguyên đơn/nhật ký. Không DELETE, không tự ẩn trong migration/release. Khách test có thể ngừng tài khoản; đơn hủy giữ để đối soát hoàn kho. Xem thêm docs/admin-v1.2.0.md.

## Shop và khuyến mãi

API danh sách/tìm kiếm và chi tiết công khai chỉ trả `active=1 AND price_vnd>0`. Hết hàng nhưng có giá vẫn hiện đúng Hết hàng; nháp/không giá biến khỏi trang chủ, shop, yêu thích và đường dẫn chi tiết. Admin vẫn xem được để sửa.

Ngày ưu đãi được chuẩn hóa khi đọc từ `DD/MM/YYYY`, ngày ISO hoặc ISO timestamp thành `YYYY-MM-DD` cho date input; bảng dùng `DD/MM/YYYY`. GET/mở/Hủy không cập nhật database. Ngày không đọc được gây lỗi rõ ràng thay vì biến thành trống. PATCH không cho xóa ngày đã có trừ khi chọn “Xác nhận bỏ giới hạn ngày đã lưu”. Sửa trường khác giữ nguyên khoảng ngày, không reset lượt dùng.

## Liên hệ cửa hàng

Form nạp dữ liệu từ settings thật. SĐT/email/địa chỉ chưa có trong database được ghi Chưa cấu hình, không bắt buộc và không lấy số mẫu làm số thật. Server bỏ qua ô liên hệ trống, giữ dữ liệu cũ; trường có dữ liệu được lưu bình thường, email có kiểm tra. Tên cửa hàng vẫn bắt buộc.

## Báo cáo khớp theo công thức nào?

Cả tổng quan, biểu đồ, danh sách sản phẩm và CSV dùng cùng khoảng ngày Việt Nam, cùng tập đơn **không bị hủy**, gồm cả các đơn còn chờ/xử lý. Đây là doanh số theo đơn, không phải tiền đã thu.

- Bảng bán chạy: tất cả tên sản phẩm trong chi tiết đơn, không cắt top 8. Tiền hàng = đơn giá lịch sử × số lượng; chưa trừ coupon, chưa cộng phí giao hàng.
- Tổng doanh thu: tổng `orders.total_vnd` đã lưu, sau giảm giá và cộng phí giao hàng.
- Phần Đối soát hiển thị tiền hàng, giảm giá, ship và tổng. Nếu đơn cũ có `subtotal_vnd` khác tổng dòng hàng, hoặc `total_vnd` khác `subtotal − discount + ship`, hiện riêng chênh lệch và liên kết từng mã đơn cần kiểm tra. CSV cũng có các khoản đối soát. Không tạo dòng hàng hoặc đổi tiền lịch sử để che chênh lệch.

Công thức đầy đủ luôn đối chiếu được:

`tiền hàng chi tiết + lệch tạm tính lịch sử − giảm giá + ship + lệch tổng lịch sử = tổng doanh thu đã lưu`

Nếu dữ liệu hợp lệ, cả hai khoản lệch bằng 0. Con số 2/2 kết quả là hai dòng sản phẩm/tên sản phẩm, không phải hai đơn và không có nghĩa tiền hàng phải bằng tổng sau giảm/ship.

## Kiểm chứng

29 test API/database + 17 test DOM: toàn bộ suite v1.2.0 và thêm lọc công khai, date roundtrip/mở-Hủy, bảo vệ ngày khi PATCH, liên hệ trống, khôi phục bật bán có backup/idempotence, trên 8 sản phẩm bán chạy và các trường hợp coupon/ship/thiếu chi tiết đơn. Dữ liệu test ở SQLite tạm; không đặt đơn thử trên production. Chưa kiểm tra trực tiếp Safari/iPhone.

Job deploy chạy thêm `python -m backend.release_audit` chỉ đọc để ghi nhận trạng thái SKU, ngày WELCOME10, tổng hợp đối soát và kiểm tra API không lộ sản phẩm nháp/giá 0. Không tự khôi phục hoặc dọn dữ liệu.
