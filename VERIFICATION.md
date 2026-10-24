# Kết quả kiểm tra — 22/10/2026

## Cập nhật 0.6.6 — 25/10/2026

- Theo yêu cầu mới, phím Delete và lệnh Delete trong menu chuyển ngay video
  đã chọn vào Thùng rác, không hỏi xác nhận. Phụ đề cạnh phim vẫn được giữ.
- Kiểm thử widget thật gọi lệnh Delete với hai video mẫu; cả hai đã được
  chuyển, video không chọn và phụ đề vẫn tồn tại. Hộp askyesno được chặn bằng
  lỗi trong phép thử để bảo đảm luồng không gọi xác nhận. Ba kiểm thử tương tác đạt.
- Giữ kiểm tra thư mục hợp lệ, tập do torrent quản lý và chặn lúc đang xử lý.

## Cập nhật 0.6.5 — 25/10/2026

- Movie files dùng nhấp đúp/Enter để mở phim; menu chuột phải có Open,
  Edit episode details và Delete. Bỏ hàng nút Edit/Open player dưới danh sách.
- Ctrl/Shift chọn nhiều tập, Ctrl+A chọn tất cả, Delete chuyển video đã chọn
  vào Thùng rác sau khi xác nhận; phụ đề cạnh phim được giữ lại. Shift+F10
  và phím Menu mở menu chuột phải. Giữ tập đang focus khi danh sách vẽ lại.
- Cho mở phim chưa có phụ đề; nếu có phụ đề đã lưu, dùng đúng đường dẫn,
  bao gồm tên có mã ngôn ngữ. Chặn phim đang tải hoặc không tồn tại.
- 69 kiểm thử hồi quy hiện có đạt trước khi kiểm tra tích hợp; 3 kiểm thử mới
  đạt, gồm hủy xóa, chặn lúc bận/torrent quản lý và chuyển hai video mẫu thật
  vào Thùng rác trong khi giữ phụ đề và video không chọn.
- Luồng GUI đang chạy: sự kiện nhấp đúp tại đúng hàng đã mở video mẫu trong
  MPC-BE thật; API /slave xác nhận tên video và track phụ đề ngoài. Nhấp đúp
  header/vùng trống không mở thêm player. Cửa sổ đang focus không thay đổi.
- Màu menu đã kiểm tra với cả bốn theme. Không thay đổi shared theme skill.
- Đường mở nền tùy chọn đã kiểm tra trên instance chạy mã nguồn riêng và
  không xuất hiện trong mẫu PID foreground. Gói EXE giải nén chạy ẩn đạt;
  với EXE cài trên máy đang được người dùng xem/tương tác, phép đo focus
  chưa phân biệt được thao tác chủ động và khởi động. Chưa coi hành vi hiện
  nền của EXE trong mọi cấu hình là đã xác nhận.
- Mở phim không có phụ đề đã kiểm tra qua GUI callback/đối số adapter;
  chưa thử riêng playback không phụ đề trên player thật. Không thử lại mọi
  tổ hợp phím bằng bàn phím vật lý hoặc trên máy Windows sạch.

## Cập nhật 0.6.4

- Giữ nguyên lệnh chuyển video vào Thùng rác: phụ đề cạnh phim vẫn ở lại.
- Sau khi xuất Anki TXT thành công cho thư mục phim, các file phụ đề SRT/VTT/
  ASS/SSA đã ghi nhận lúc quét được chuyển vào Thùng rác Windows. Phụ đề mới
  thêm hoặc bị sửa sau lúc quét được giữ lại.
- Luồng GUI thật đã kiểm tra xuất thành công, file đích có sẵn, phụ đề thay đổi
  sau lúc quét và giữ lại video. Hai phụ đề mẫu (tiếng Anh và tiếng Việt) được
  xác nhận trong Thùng rác; TXT Anki đã được tạo đúng định dạng.
- Toàn bộ 69 kiểm thử Python đạt. Sau nhiều cửa sổ GUI kiểm thử, đã xử lý việc
  Tkinter thu hồi widget trên luồng quét phụ đề; việc thu hồi nay diễn ra trên
  luồng giao diện trước khi bắt đầu quét nền.
- Bản ZIP đã giải nén và khởi động ẩn thành công; phép thử không đổi cửa sổ
  đang được focus. Gói không chứa thư mục dữ liệu cá nhân.

## Cập nhật 0.6.3

- Chọn nhiều tập bằng Ctrl/Shift+click, giữ lựa chọn khi danh sách được vẽ lại;
  chuột phải mở lệnh chuyển các video được chọn vào Thùng rác Windows.
- Thử luồng GUI thật bằng hai file video mẫu: cả hai biến mất khỏi thư mục,
  xuất hiện trong Thùng rác và phụ đề cạnh phim vẫn ở nguyên vị trí.
- Đã kiểm tra hủy ở hộp xác nhận, giữ nhiều lựa chọn khi chuột phải, chặn
  tập nhập từ torrent đang được qBittorrent quản lý. 68 kiểm thử hiện có đạt.
- Bản ZIP đóng gói đã chạy được sau khi giải nén; có các thành phần Windows
  cần cho thao tác Thùng rác và giấy phép Send2Trash, không chứa `data/`.
- Chưa thử thao tác xóa trên video thật dung lượng lớn hoặc từ bản `.exe` đã
  giải nén; phép thử xóa trực tiếp dùng GUI chạy từ mã nguồn. qBittorrent vẫn
  có thể tải lại video nếu một thư mục được quét còn thuộc torrent đang hoạt động.

## Cập nhật 0.3

- 50 kiểm thử Python đạt, gồm ba danh sách song song, đúng thứ tự ngôn ngữ,
  phân biệt tên file chính xác với bản gần giống, tự tải không hỏi xác nhận,
  báo nguồn/kết quả trong UI, khôi phục phụ đề đã tải và áp dụng không tải lại.
- API thật: SubDL tải đủ 20 phụ đề tiếng Anh từ gói BluRay S01; OpenSubtitles
  tải đủ 20 phụ đề tiếng Việt cùng bản TAXES, còn 80 lượt tải do API báo.
- qBittorrent tìm bằng plugin và đã tải bản Gravity Falls S01 1080p BluRay
  x264-TAXES, metadata 20 tập, 23.844.429.630 byte, dưới 25 GB.
  Phim đang tải; chưa khẳng định phát được hoặc khớp timing thực tế cả mùa.
- 20 phụ đề tiếng Việt đã được chuẩn bị cho hàng chờ chung của app;
  tự áp dụng khi từng video hoàn thành. Bộ SubDL tiếng Anh giữ riêng để đối chiếu.
- Các script riêng cho lần thử nằm trong `tests/live`, không nằm trong gói app.
- SubDL có thể trả URL gắn API key; adapter đã bỏ query đó khỏi metadata/báo cáo
  và chuyển key sang header tải. Không đóng gói data/credentials.

Các mục dưới đây là biên bản kiểm tra của các bản trước.

## Đã triển khai và kiểm tra

- 47 kiểm thử Python: phân tích tên phim (kể cả tiêu đề bắt đầu bằng năm), mùa/tập,
  điểm khớp, UTF-8/UTF-16, cấu trúc phụ đề, ZIP, chống path traversal/symlink/ZIP quá lớn,
  chống ghi đè, bảo vệ đích hardlink, cấu hình hỏng được giữ nguyên, Windows DPAPI.
- Tìm kiếm bằng nguồn giả lập chỉ trong tests: nguồn tốt/hỏng cùng lượt, dedup,
  timeout ngoài provider, hủy, phân trang, giới hạn URL/miền, giới hạn tốc độ tải.
- Kiểm thử widget của ứng dụng: nhập phim/phụ đề, nội dung xem trước, lưu, từ chối
  ghi đè, nhận thông tin trình duyệt qua inbox, lưu cấu hình. TkDnD được khởi tạo.
- Phim bộ: nhận tên tập/Season folder, không tự ghép file nhiều tập, bỏ qua sub có sẵn,
  chọn đúng tập trong ZIP mùa, từ chối ZIP mơ hồ, giữ nguyên video và lưu đúng tên.
- Luồng GUI dùng provider fixture: tìm/ghép hai tập, tải một ZIP một lần, lưu cả hai;
  gọi mở tập kèm sub; thử lại không ghi đè. Mô phỏng chờ qBit tải xong rồi lưu,
  và từ chối khi file trong torrent đổi tên.
- Adapter SubDL/OpenSubtitles kiểm tra bằng response fixture: schema, phân trang,
  metadata mùa/tập, gói mùa, thiếu key, không chuyển credentials sang link tải.
- qBit HTTP server giả lập: SID login, list, search, seeds/leechers, hủy và xóa job
  của tool, thêm đúng một URL, từ chối redirect/host khác/path traversal.
- qBittorrent thật **5.1.0**: bật WebUI loopback, đăng nhập thành công, đọc danh sách
  9 plugin bật. Danh sách torrent đang trống; không thêm torrent trong phép thử.
  Chứng cứ: `test-artifacts/qbit-live-result.json`. Không sửa thư mục player hay plugin.
- Kiểm tra mã JS bằng API giả lập: menu chuột phải, popup, Unicode, lỗi host,
  từ chối scheme không hỗ trợ và quyền manifest tối thiểu.
- Cú pháp PowerShell của script cài/gỡ/đăng ký.
- Bản `.exe` khởi động; host `.exe` nhận thông điệp Native Messaging thật qua stdin,
  phản hồi đúng và GUI nhận được yêu cầu. Thông điệp quá lớn bị từ chối.
  Không sửa profile trình duyệt/registry trong phép thử này.
- MPC-BE **1.9.1.0** thật: mở AVI tự tạo với `/sub` đường dẫn tuyệt đối;
  `/slave` API trả `explicit-external-subtitle.srt|0` — track phụ đề ngoài được chọn.
  Chỉ mở/đóng tiến trình MPC-BE của phép thử.
  Chứng cứ: `test-artifacts/mpc-live-result.json`, `package-result.json`.

## Đã viết nhưng chưa kiểm tra đầu-cuối trên máy

- Extension chưa cài trong Edge/Chrome/Firefox; registry Native Messaging chưa đăng ký.
  Mã JS và đường truyền native đã kiểm tra riêng; chưa khẳng định thao tác thật từ trình duyệt.
- Script đăng ký/gỡ host đã kiểm tra cú pháp, chưa chạy ghi registry.
- TkDnD đã khởi tạo nhưng chưa thử kéo thả vật lý từ Explorer.
- Chưa kiểm tra bằng mắt việc render phụ đề trong player; API xác nhận nạp/chọn track.
- Chưa thử ứng dụng trên một máy Windows khác.

## Cần thông tin truy cập để kiểm tra thực tế

- SubDL và OpenSubtitles đã có adapter trong registry sản phẩm.
- Chưa có API key của người dùng: chưa xác nhận tìm/tải/đăng nhập/quota thật trên hai nguồn.
- Chưa thử tải torrent thật hoặc tìm qua plugin website thật; không biết trước plugin nào
  đang bị website chặn. Seed/peer và tiến độ có dữ liệu đã kiểm tra bằng API fixture,
  chưa đối chiếu torrent đang tải thật vì danh sách qBit đang trống.

## Ngoài phạm vi bản đầu

mpv/MPC-HC/VLC/PotPlayer có thể thêm qua interface, hiện chỉ MPC-BE có adapter.
Chưa có nạp nóng MPC-BE, tự đồng bộ timing, RAR/7z, OCR, ký số exe hoặc ký extension.
Firefox đang có gói phát triển tải tạm thời; cài bền vững cần Mozilla ký.

## Chạy lại

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node tests\check_extension.cjs
.\.venv\Scripts\python.exe build.py
.\.venv\Scripts\python.exe tests\check_package.py
.\.venv\Scripts\python.exe tests\check_qbit_live.py
.\.venv\Scripts\python.exe tests\check_mpc_live.py
```

Phép thử MPC-BE có mở player với video mẫu riêng. Không chạy nó nếu đang muốn
giữ player hoàn toàn không phát thêm nội dung.
