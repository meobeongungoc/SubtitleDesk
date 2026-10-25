# SubtitleDesk 0.7.0 — kiểm chứng

Bản này dùng thư mục video cục bộ: duyệt thư viện, tìm/tải phụ đề, Play và Delete theo từng tập.
Các phép thử dùng thư mục tạm và provider fixture; không sửa phim thật hay khóa API.

## Phạm vi kiểm tra

- Khởi tạo với cấu hình cũ: giữ theme/ngôn ngữ/thư mục phim; không mở kết nối tải video.
- Cache và file hàng chờ cũ giữ nguyên byte, không tự khôi phục hoặc áp dụng vào phim.
- Duyệt thư viện, đổi phim khi không bận, quét lại danh sách hiện tại khi Refresh;
  thư mục không còn video sẽ xóa danh sách cũ khỏi giao diện.
- Tìm phụ đề, tự tải bản trùng tên chính xác, chọn bản khác và gói cả mùa;
  lưu cạnh video, tái sử dụng gói trong bộ nhớ, không ghi đè phụ đề có sẵn.
- Play/Delete theo đúng dòng, thao tác nhiều lựa chọn, cuộn/sắp xếp và bốn theme;
  Delete chuyển video mẫu thật vào Recycle Bin không hỏi xác nhận, giữ phụ đề.
- Gói portable: kiểm tra sau khi build bằng giải nén mới, chạy executable,
  Native Messaging và loại trừ cấu hình/khóa/media của người dùng.

## Giới hạn

- Provider trực tuyến được kiểm tra bằng fixture trong lần sửa này; không lặp lại tải thật
  qua tài khoản SubDL/OpenSubtitles. Khả năng đồng bộ timing cần kiểm tra theo từng video.
- Play theo dòng được kiểm tra định tuyến bằng mock. Kiểm tra MPC-BE thật trước đó đã xác nhận
  mở video mẫu và nạp phụ đề qua `/slave`; lần sửa này không thay adapter player.
- Chưa kiểm tra trên một máy Windows sạch khác hoặc thao tác extension thật trong trình duyệt.
- Cache/runtime và credentials không nằm trong gói phát hành; giữ `data` để bảo toàn thiết lập.

## Chạy lại

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe build.py
.\.venv\Scripts\python.exe tests\check_package.py
```

Kết quả chính xác của lần kiểm tra và bản build nằm trong `test-artifacts` tại máy phát triển.
