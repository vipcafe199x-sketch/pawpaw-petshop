# Bàn giao bản sửa 11 lỗi — 04/11/2026

Mã được sửa trên nền `main` có bản v1.1.2, giữ các sửa responsive/bộ lọc trước đó. Không thay database bằng dữ liệu seed; không tự chạy sửa dữ liệu khi app khởi động. Không thay đổi schema hoặc workflow deploy. `.env` hiện hữu được giữ; mẫu `.env.example` không còn thông tin đăng nhập dùng chung. Cần cấu hình `ADMIN_EMAIL` và `ADMIN_PASSWORD` khi chạy mới.

## Các thay đổi

| # | Lỗi | Bản sửa |
| --- | --- | --- |
| 1 | Sửa sản phẩm ghi 0 khi đóng prompt | Thay bằng dialog có tên/giá/tồn/đang kinh doanh hiện tại ở cả sản phẩm và kho. Hủy, Esc và mở dialog không gửi PATCH. Chỉ nút Lưu gửi dữ liệu. FE và API từ chối giá rỗng/null/0/âm/thập phân, tồn kho rỗng/null/âm/thập phân. Tồn 0 vẫn hợp lệ khi nhập rõ ràng. |
| 2 | Hai cách tính miễn phí ship | Ngưỡng lấy từ settings; điều kiện là tạm tính hàng hóa **trước coupon** ≥ ngưỡng. Cart và checkout dùng chung `shippingFee`, đặt đơn dùng `shipping_fee` với cùng quy tắc. Có chú thích trên giao diện. 330.000 − 33.000 + 0 = **297.000₫**. |
| 3 | Breadcrumb shop | `Trang chủ › Cửa hàng`. |
| 4 | Sản phẩm chưa có giá vẫn mua được | Ghi “Chưa có giá bán”, khóa nút, chặn addToCart và chặn checkout phía API. Công cụ sửa dữ liệu có thể ẩn mặt hàng chưa có giá; không đoán giá bán thật. Có thể đặt giá dương và bật lại bằng dialog. |
| 5 | Ngày ISO trong admin | Dùng `Intl.DateTimeFormat('vi-VN')`, múi giờ `Asia/Ho_Chi_Minh` (UTC+7) cho bảng/chi tiết đơn và đơn tài khoản. |
| 6 | Doanh thu tính đơn hủy | Dashboard và báo cáo/bán chạy loại đơn `cancelled`; số lượng tổng đơn dashboard vẫn gồm tất cả trạng thái. |
| 7 | Hủy không hoàn tồn | Chuyển sang canceled và cộng tồn + ghi inventory_events trong một `BEGIN IMMEDIATE`/COMMIT. Yêu cầu hủy lặp không cộng thêm. Giao dịch lỗi rollback cả trạng thái và tồn. |
| 8 | Ký hiệu tiền | Formatter chung trả Unicode U+20AB `₫`, khoảng trắng không ngắt dòng, dùng cùng formatter cho dịch vụ và tóm tắt đặt lịch. |
| 9 | Placeholder thú cưng | Ẩn mục điều hướng và khối “Thú cưng của tôi”; không giả lập hồ sơ. |
| 10 | Chọn tất cả bị vô hiệu | Bỏ checkbox; hiển thị số dòng sản phẩm. Checkout áp dụng toàn bộ giỏ như trước. |
| 11 | Trạng thái đơn bị cũ | Sau PATCH thành công cập nhật badge, select, cache đơn và panel đang mở từ phản hồi server; lỗi trả select về trạng thái trước. Không cần refresh trang. |

Cart/checkout cũng làm mới giá từ catalog thay vì giữ giá cũ trong localStorage. API luôn là nơi xác thực giá/tồn cuối cùng. Không có tích hợp thanh toán online mới; COD giữ nguyên.

## Dữ liệu đã hỏng cần một lần sửa riêng

Triển khai code **không tự khôi phục dữ liệu đã bị ghi sai**. Không xóa volume, không tạo lại database, không ghi đè bằng database trong bản ZIP. ZIP không chứa `.env`, database, session hay thông tin đăng nhập production.

`backend/repair_reported_data.py`:

- Chỉ khôi phục hai sản phẩm mẫu có SKU/slug nằm trong danh sách cho phép khi đồng thời giá và tồn bằng 0. Cấu hình khôi phục nằm trong module, trùng với các giá trị catalog seed công khai của repo; không đọc hoặc công bố dữ liệu production.
- Không ghi đè nếu giá/tồn đã được sửa hoặc SKU/slug không khớp.
- Ẩn sản phẩm chưa có giá được cấu hình trong module, không tự đoán giá mới.
- Hoàn kho đơn cũ chỉ khi chỉ định chính xác mã đơn đã hủy và ledger chứng minh đã xuất đúng số lượng. Không chạy trên toàn bộ đơn hủy tự động. Có sự kiện `Hủy đơn CODE` thì bỏ qua để tránh cộng lặp.
- Tự tạo bản sao SQLite `.before-repair-*.bak` cùng thư mục trước khi ghi. Nếu không đủ bằng chứng hoặc mã đơn sai, toàn bộ thay đổi trong lần chạy bị rollback.

Chạy lúc tạm dừng nhận đơn/chỉnh kho. Trước khi áp dụng, đối soát mã đơn và bảo đảm chưa hoàn kho thủ công bằng thao tác khác: ledger cũ không ghi nhận được mọi lần ghi đè tồn kho bằng prompt. Nếu đã hoàn thủ công, không truyền mã đơn đó.

### Trong Docker đang chạy bản code mới

Xem trước sửa dữ liệu sản phẩm:

```bash
docker exec pawpaw python -m backend.repair_reported_data
```

Xem trước cả hoàn kho đơn đã đối soát (chỉ khi đơn thực sự đã hủy). Thay `MA_DON_DA_HUY` bằng mã đơn đã đối soát, không chạy nguyên placeholder:

```bash
docker exec pawpaw python -m backend.repair_reported_data --restore-cancelled-order MA_DON_DA_HUY
```

Sau khi đối soát output, thêm `--apply`:

```bash
docker exec pawpaw python -m backend.repair_reported_data --restore-cancelled-order MA_DON_DA_HUY --apply
```

Với đơn hủy khác đã đối soát, lặp lại `--restore-cancelled-order MA_DON`. Công cụ cộng đúng quantity trong order_items; không đặt tồn về số cố định theo phỏng đoán. Không sửa tổng tiền/lịch sử của đơn đã chốt.

Nếu chạy ngoài Docker, đặt `DATABASE_PATH` trỏ đúng database hiện hữu rồi dùng các lệnh `python -m backend.repair_reported_data ...` tương tự. Backend trong Docker đã được COPY nên module có trong image build mới.

## Triển khai và kiểm tra

1. Giữ nguyên `.env` và volume dữ liệu; build image bằng Dockerfile hiện có hoặc cập nhật source và khởi động lại Uvicorn theo cách đang dùng.
2. Xem trước và áp dụng sửa dữ liệu như trên. Không lấy database QA để thay production.
3. Tải lại website để nhận CSS/JS `fix-11-5`, kiểm tra nút sửa ở cả `/admin/products` và `/admin/inventory`.
4. Kiểm tra COD + PAWPAW10, đổi trạng thái và hoàn kho trên dữ liệu thử được phép dùng.

Chạy lại bộ kiểm tra:

```bash
python -m unittest discover -s tests -v
npm ci --ignore-scripts
npm test
```

- 11 test API đạt: gồm các luồng cũ auth/quyền, COD/tra cứu/tồn, booking trùng, health/catalog; các ca mới sửa sản phẩm, giá 0, ship đúng ngưỡng/trước coupon, hủy lặp, doanh thu, rollback và công cụ sửa dữ liệu.
- 5 test FE với DOM giả lập đạt: dialog hủy/rỗng/lưu rõ ràng, khóa giá 0, chính sách ship/tiền tệ, breadcrumb/ẩn pets, cập nhật trạng thái trực tiếp và giờ Việt Nam.
- Bộ kiểm tra render 19 màn/bộ lọc/FAQ/chi tiết đơn trước đó đạt; JavaScript syntax và CSS parse đạt.
- Chưa xác nhận lại bằng Safari/iPhone. Phiên trình duyệt kiểm thử không kết nối được server local trong môi trường làm việc này. Các test FE ở trên là DOM giả lập, không được coi là bằng chứng pixel/UI trên thiết bị thật.

Không tạo tag/release hoặc deploy production cho bản bàn giao này.
