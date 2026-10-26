# Kiến trúc và tích hợp về sau

## Thành phần

- `core.py`: phân tích tên, chấm độ khớp kèm lý do, kiểm tra/đọc ZIP, xem trước, lưu.
- `providers.py`: Query/Result/Page/Capabilities, registry, tìm đồng thời tối đa 4 worker,
  timeout từ coordinator, hủy hợp tác, lỗi độc lập, khử trùng theo (nguồn, id).
  Mỗi nguồn tối đa 3 trang/lượt, mỗi trang tối đa 500 kết quả. Không khử các bản từ
  nguồn khác để vẫn giữ quyền chọn nguồn. Request treo không được giết cưỡng bức;
  worker daemon và semaphore giới hạn số worker đang gọi.
- `gui.py`: Tk, queue từ worker để chỉ cập nhật GUI trên main thread; không chặn cửa sổ khi tìm/tải.
- `sources.py`: SubDL v1 và OpenSubtitles REST API, chuẩn hóa kết quả/tập, bảo vệ credentials,
  từ chối redirect API khác host, allowlist miền tải. Không có khóa được nhúng.
- `batch.py`: quét video, nhận diện tập, chấm khớp nghiêm ngặt, chọn phụ đề trong gói mùa,
  lưu sidecar theo tên phim và mã ngôn ngữ bằng exclusive-create.
- `library_ui.py`: các thao tác tập phim cục bộ, tìm/tải phụ đề, cache gói mùa trong bộ nhớ,
  nhận kết quả qua queue có generation + đường dẫn phim, cập nhật dòng trên main thread.
- `simple_ui.py`: duyệt thư viện thư mục phim và hai nguồn phụ đề song song; Play/Delete mỗi dòng.
  Refresh quét lại thư mục đang chọn. Không có hàng chờ chờ video tải xong.
- `storage.py`: JSON cấu hình; Windows DPAPI cho thông tin xác thực.
- `players.py`: adapter MPC-BE, mở file và phụ đề bằng tham số CLI. Chưa có live IPC.
- `bridge.py`: framing Native Messaging, JSON nhỏ, xác thực trường, inbox của ứng dụng.
  Không nhận đường dẫn thực thi hay lệnh shell từ extension.
- `extensions/shared`: cùng mã JS/HTML; manifest khác nhau cho Chromium và Firefox.
- `scripts`: cài dạng portable và đăng ký/gỡ host từng trình duyệt theo tài khoản.

## Vì sao Native Messaging

URL protocol có ít đăng ký hơn nhưng cần xử lý URI/escaping/giới hạn độ dài,
và có thể bị bất kỳ website nào gọi hộp thoại mở ứng dụng. Native Messaging có
allowlist extension, khung JSON chuẩn, phản hồi thành công/lỗi và không cần server
HTTP/port nền. Cả hai đều cần một bước đăng ký Windows; chọn Native Messaging
để dùng một host cho nhiều trình duyệt với nguồn gọi được giới hạn.

## Thêm website khi người dùng cung cấp

Không cần hỏi lại website trước thời điểm đó. Không đăng ký nguồn mẫu.

1. Đọc tài liệu API, quy định, xác thực, phân trang và miền tải của website được đưa.
2. Tạo module adapter riêng trong `subtitledesk/`, bắt đầu từ `examples/provider_template.py`.
3. Khai báo Capabilities: id ổn định, tên, ngôn ngữ, search/download/pagination,
   credentials (username/password/api_key theo yêu cầu thật), min_interval, timeout,
   domains HTTPS chính xác (bao gồm CDN cần thiết).
4. `search(Query, cursor, Context) -> Page`: chuẩn hóa Result, không HTML trong metadata;
   `download(Result, Context) -> (filename, bytes)`.
5. Kiểm tra `context.check()` trước/sau I/O; dùng `fetch_bytes` để giới hạn kích thước,
   TLS và redirect đúng miền; đặt timeout cho mọi network call.
6. Truy xuất secret qua SecretStore, không đưa URL có token/lỗi chứa key vào log.
   Nếu CAPTCHA/đăng nhập tương tác: trả lỗi riêng và hướng dẫn người dùng xử lý;
   không vượt qua cơ chế chống bot.
7. Đăng ký tường minh trong `load_registry(secret_store)`. Không quét/import plugin
   tải từ internet tự động.
8. Viết fixture kiểm thử riêng trong tests, kiểm tra schema và retry/rate limit.
   Kiểm thử thực với nguồn sau khi người dùng cung cấp quyền truy cập cần thiết.

## Thêm player

Implement PlayerAdapter.command trả về list argv; đăng ký trong ADAPTERS.
Xác minh tham số từ tài liệu/mã nguồn chính thức trước khi thêm mpv/MPC-HC/VLC/PotPlayer.
Không dùng shell=True hoặc ghép lệnh từ tên phim. Nếu thêm live IPC, khai báo năng lực
riêng và chỉ bật khi player chạy với endpoint phù hợp. Không giả định mở CLI đồng nghĩa nạp nóng.

## Nguồn tham khảo kỹ thuật

- https://github.com/Aleksoid1978/MPC-BE/issues/549 (đường dẫn tuyệt đối cho /sub).
- https://github.com/Aleksoid1978/MPC-BE/blob/master/src/apps/mplayerc/AppSettings.cpp
- https://learn.microsoft.com/en-us/microsoft-edge/extensions/developer-guide/native-messaging
- https://developer.chrome.com/docs/extensions/develop/concepts/native-messaging
- https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Native_messaging
- https://subdl.com/api-doc
- https://blog.opensubtitles.com/opensubtitles/how-to-build-a-movie-subtitle-finder-cli-with-python-and-the-opensubtitles-api

## Các giới hạn có chủ ý

Hai website đã có adapter. Bản 0.8.0 được kiểm tra offline bằng nguồn giả lập; chưa kiểm tra API thật trong đợt này.
Chưa có RAR/7z, OCR, nạp nóng MPC-BE, auto-sync, hay adapter player khác.
Chưa phát hành lên store/ký extension/ký exe. Không sửa player và không đổi mặc định hệ thống.
Tất cả cấu hình ở `data` cạnh app; cần chạy ở thư mục người dùng có quyền ghi.
