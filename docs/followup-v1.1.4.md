# v1.1.4 — báo giá, đồng bộ trạng thái và bảo vệ dữ liệu

## Đã sửa

- Cart và checkout dùng `POST /api/orders/quote` để hiện giảm giá, phí ship và tổng cuối trước đặt hàng. Quote và tạo đơn cùng gọi `calculate_quote`; quote không trừ tồn, không tạo đơn và không dùng lượt coupon. Khi giá thay đổi sau xem lại, `expectedTotalVnd` chặn tạo đơn để khách xác nhận lại tổng mới. Mã không hợp lệ khóa nút đặt hàng và có nút Bỏ mã. Áp dụng mã không làm mất thông tin giao hàng đã nhập.
- Badge, ô chọn, cache và panel đơn hàng đồng bộ từ phản hồi API. Nếu PATCH bị từ chối, FE GET `/api/admin/orders/{id}` để lấy trạng thái máy chủ. API và HTML không cache; thêm xử lý `pageshow` để tránh giữ DOM cũ khi quay lại bằng browser history.
- Bỏ hẳn mọi nội dung thú cưng giả/placeholder trong cả template chính và template dự phòng. Chưa thêm CRUD hồ sơ thú cưng.
- Việc bỏ “Chọn tất cả” ở v1.1.3 là có chủ ý: checkout toàn bộ giỏ. Không có chọn từng dòng. Cả template chính/dự phòng đều bỏ checkbox và ghi rõ thanh toán toàn bộ giỏ hàng.
- Hoàn kho xử lý theo từng sản phẩm và số lượng còn thiếu. Đơn cũ đã hoàn một phần vẫn có thể bổ sung phần thiếu; chạy lại không cộng lặp. Khi lịch sử không khớp, dừng để đối soát.

## Deploy không tự sửa lại tồn kho

Code v1.1.3 có `INSERT OR IGNORE`, không có UPDATE đặt tồn về seed khi bản ghi cùng SKU/slug còn tồn tại. Chưa có quyền đọc database, volume và lịch sử thao tác trên production để kết luận nguyên nhân các biến động đã báo cáo. Không tự đặt lại tồn của các sản phẩm không được yêu cầu.

Bản này thêm:

1. Seed catalog/coupon chỉ thực hiện khi tạo database hoàn toàn mới. Database hiện hữu không được thêm lại các sản phẩm seed đã xóa hay đặt lại giá/tồn.
2. Trong production, thiếu file database sẽ dừng thay vì tự tạo, trừ khi có `ALLOW_DATABASE_INIT=1` cho lần cài đặt mới có chủ ý. Sau bootstrap đặt lại 0. Giữ nguyên `.env` và volume đang dùng.
3. Workflow build image rồi dừng container cũ, chạy `backend.deployment_guard` offline trên cùng volume. Guard yêu cầu file database hiện hữu nằm trong `/app/data`, tạo SQLite backup (bao gồm WAL qua API backup), gọi init và so sánh fingerprint toàn catalog trước/sau. Nếu sai đường dẫn hoặc catalog đổi, deploy dừng; container cũ được khởi động lại nếu còn tồn tại. Không in giá/tồn hoặc dữ liệu khách vào log.
4. Backup deploy nằm trong `/app/data/deploy-backups`. Nếu guard phát hiện init đã thay catalog, cần đối soát/khôi phục backup trước khi thử lại; không reset volume.

Guard ngăn lỗi gieo dữ liệu trên volume mới/đường dẫn sai; không chứng minh được nguyên nhân biến động tồn trong lịch sử. Cần đối chiếu backup trước deploy và `inventory_events` trên máy chủ cho các chênh lệch cũ. Nếu database thật đang nằm ngoài `/app/data`, chuyển mount/cấu hình cho đúng dữ liệu hiện hữu trước khi deploy; không tạo một database rỗng để vượt guard.

## Công cụ khôi phục có xem trước và sao lưu

Không tự chạy trên production khi deploy. Các lệnh dưới là mẫu: thay SKU, PRICE, STOCK và ORDER_CODE bằng giá trị đã đối soát. Chạy lúc tạm dừng nhận đơn/chỉnh kho.

```bash
docker exec pawpaw python -m backend.repair_reported_data \
  --repair-product SKU:PRICE:STOCK \
  --price-product SKU:PRICE \
  --restore-cancelled-order ORDER_CODE
```

- Default vẫn xem trước hai sản phẩm cấu hình sẵn trong module; không ghi nếu thiếu `--apply`.
- `--repair-product` mở rộng được cho sản phẩm khác và khớp bằng SKU duy nhất, không phụ thuộc tên/slug bị đổi. Chỉ sửa khi đồng thời giá và tồn bằng 0. Nếu đã khác 0, bỏ qua để tránh ghi đè. Ghi inventory event cho lượng khôi phục.
- `--price-product` chỉ đặt giá khi giá đang 0, bật lại active và giữ nguyên tồn. Dùng giá bán đã xác minh; giá seed chỉ là dữ liệu mẫu, không tự coi là giá thực tế.
- `--restore-cancelled-order` chỉ chấp nhận đơn đã hủy và có ledger xuất kho khớp order_items. Tính phần hoàn còn thiếu cho từng sản phẩm. Nếu đã hoàn thủ công không theo ledger này, không chạy trước khi đối soát vì có nguy cơ cộng dư.
- Thêm `--apply` vào lệnh đã xem trước để ghi. Công cụ tạo file `.before-repair-*.bak` cùng thư mục trước giao dịch. Nếu một thao tác lỗi, cả giao dịch rollback.
- Không sửa tổng tiền hay viết lại lịch sử đơn đã chốt. Không reset tồn các sản phẩm khác về số liệu seed hoặc về số lượng được phỏng đoán.

### Sửa trạng thái test preparing về confirmed

Quy trình API vẫn chỉ cho chuyển tiếp. Công cụ chỉnh database riêng có backup, ghi `operational_adjustments` và không thay tồn kho:

```bash
docker exec pawpaw python -m backend.repair_reported_data --rewind-preparing-order ORDER_CODE
# Sau khi đối soát output:
docker exec pawpaw python -m backend.repair_reported_data --rewind-preparing-order ORDER_CODE --apply
```

Chỉ cho phép khi trạng thái hiện tại là `preparing` và chưa có mã vận đơn; nếu đã `confirmed` thì bỏ qua. Không áp dụng cho đơn đang giao/đã giao/đã hủy. Bên trong giao dịch tương đương điều kiện SQL:

```sql
UPDATE orders SET status='confirmed'
WHERE order_code=:order_code AND status='preparing' AND tracking_code='';
```

Ưu tiên công cụ vì nó có kiểm tra, backup và audit; không chạy SQL thiếu điều kiện WHERE hay bỏ bước đối soát.

## Kiểm tra

- 16 test API: quote/final COD khớp, coupon sai, quote không trừ kho/lượt coupon, tổng thay đổi phải xác nhận lại; hoàn kho hai mặt hàng, hủy lặp, legacy hoàn một phần; sửa SKU bị đổi tên; giá-only không đổi tồn; init/deploy guard không đổi catalog; missing production DB không được tạo; GET trạng thái sau từ chối và sửa test có audit; các ca auth, catalog, booking, COD cũ.
- 7 test FE với DOM giả lập: modal sửa sản phẩm, chặn giá 0, pricing, breadcrumb/ẩn thú cưng, badge cập nhật sau success, readback sau reject, hiển thị quote và khóa submit khi mã lỗi/giữ thông tin form.
- Chưa kiểm tra lại trực tiếp trên Safari/iPhone hoặc thao tác ghi dữ liệu production. Dùng dữ liệu QA tách biệt, không ghi dữ liệu khách thật vào repo.
