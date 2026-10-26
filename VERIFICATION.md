# SubtitleDesk 0.8.0 — kiểm chứng

Bản này dùng một cửa sổ với Library, Vocabulary, Settings và Appearance. Không còn tab Preview.
Settings cuộn được; chỉnh thông tin tập, chọn file phụ đề và xác nhận ghi đè hiện nội tuyến.
Hộp chọn tệp/thư mục Windows vẫn được giữ. Play/Delete nằm trên từng dòng; Delete không hỏi xác nhận.

## Đã kiểm tra trên mã nguồn

- 75 test offline: core, provider fixture, thư mục phim, phim lẻ, gói mùa, hai ngôn ngữ,
  tự tải bản trùng tên, an toàn ghi đè, thao tác từng dòng và nhiều lựa chọn.
- Phim lẻ nhận phụ đề đơn đúng bản; phụ đề tập và gói không rõ ràng bị từ chối.
- Việt và Anh lưu thành `.vi.srt` / `.en.srt`; phụ đề cũ không rõ ngôn ngữ giữ nguyên.
- Kéo thả khi bận bị chặn. Event từ lượt cũ/sai đường dẫn/sai chỉ số không sửa danh sách mới.
- Quét thư mục lập chỉ mục phụ đề một lần; bảng chỉ cập nhật dòng đổi, giữ lựa chọn/sắp xếp.
- Kho khóa lỗi không ngăn khởi động; dữ liệu gốc được giữ. Reset có bước xác nhận nội tuyến
  và lưu bản gốc trong thư mục dữ liệu riêng trước khi đặt lại.
- Export Anki và dọn phụ đề chạy nền; giao diện còn phản hồi, không xuất trùng khi nhấn lại;
  giữ file đổi sau scan, chỉ dọn sau khi ghi TXT thành công. Có tiến độ và hủy phần còn lại.
- Các trang dùng chung một Tk root; không tạo Toplevel riêng cho nội dung app.
- Bốn theme được kiểm tra bằng widget và ảnh render từ instance test đặt ngoài màn hình,
  không lấy focus. Có kiểm tra font, persistence, scroll/sort và nút từng dòng.

Test runner thu gom chu kỳ của nhiều Tk instance trên UI thread. Chạy bằng:

```powershell
.\.venv\Scripts\python.exe tests/run_tests.py
.\.venv\Scripts\python.exe build.py
```

## Giới hạn và bằng chứng đóng gói

- Không gọi tài khoản SubDL/OpenSubtitles thật trong lần sửa này.
- Lệnh mở player được mock trong hồi quy; adapter MPC-BE không đổi. Chưa kiểm tra lại player thật.
- Không kiểm tra extension trong hồ sơ trình duyệt thật hoặc trên máy Windows sạch khác.
- Gói build được kiểm tra riêng sau giải nén mới; kết quả và SHA256 lưu cục bộ trong test-artifacts.
  Mã nguồn/gói không bao gồm dữ liệu, khóa API, lịch sử hay phim của người dùng.
- Không tự đóng/restart app người dùng; tiến trình kiểm tra gói có thư mục và dữ liệu fixture riêng.
