# SubtitleDesk 0.7.0

Ứng dụng duyệt thư mục phim trên Windows và tìm/tải phụ đề từ SubDL, OpenSubtitles.
Giao diện gồm Movie files, SubDL và OpenSubtitles. Bấm **Library folder…** để chọn
thư viện, dùng danh sách cạnh **Movie files** để chuyển phim/bộ phim, bấm **Refresh**
để cập nhật video mới. Thư mục mùa bên trong được quét cùng nhau.

Mỗi dòng tập có **Play** và **Delete**. Play mở đúng tập; Delete chuyển riêng video
đó vào Recycle Bin ngay, không xác nhận và giữ nguyên phụ đề. Menu chuột phải/phím
Delete có thể xóa nhiều video đã chọn. Hoàn tất hoặc hủy tìm/tải phụ đề trước khi đổi thư mục hay xóa.

Bấm **Find subtitles** để tìm cả thư mục. Bản phụ đề trùng chính xác tên video được
tải tự động; các bản khác chọn ở danh sách nguồn rồi bấm **Download & apply**.
Video đã có phụ đề được bỏ qua. Cần API key của bạn trong Settings để tìm/tải thật.
Cache tải chờ từ bản cũ được giữ nguyên, không tự tiếp tục áp dụng.

Xem **USER-GUIDE.md** để dùng bản hiện tại. Các phần phía dưới mô tả thêm công cụ nhập
phụ đề, nguồn và kết nối trình duyệt.

## Chạy ngay

- Từ mã nguồn đã xây: nhấp đúp `START.cmd`.
- Từ gói `SubtitleDesk-Windows-x64.zip`: giải nén toàn bộ và chạy `SubtitleDesk.exe`.
  Giữ `_internal` cạnh file exe. Không cần cài Python.
- Có thể chạy `scripts\Install.ps1` để sao chép sang một thư mục riêng mới.
  Mặc định `%LOCALAPPDATA%\Programs\SubtitleDesk`; thư mục đã tồn tại sẽ bị từ chối.
  Đây là cài dạng portable, không sửa player, PATH hay liên kết file mặc định.

## Dùng với phụ đề có sẵn

1. Chọn/kéo thả file phim. Kiểm tra lại tên, năm, mùa/tập và bản phát hành.
2. Bấm **Nhập phụ đề / ZIP** hoặc thả một tệp vào cửa sổ.
3. Nếu ZIP có nhiều phụ đề, chọn đúng tệp ở danh sách trên phần xem trước.
4. UTF-8 và UTF-16 có BOM được nhận tự động. Nếu gặp bảng mã cũ, chọn cp1258
   hoặc cp1252 và kiểm tra tiếng Việt. Bảng mã chỉ dùng xem trước; khi lưu giữ nguyên byte.
5. **Lưu phụ đề** chọn đường dẫn và xác nhận nếu tệp tồn tại.
6. **Lưu & mở phim bằng player** gọi MPC-BE với file phim và đường dẫn `/sub` tuyệt đối.
   Nếu player đang phát, thao tác có thể mở lại phim; chưa có chức năng nạp nóng.

Trong **Cài đặt & trình duyệt**, sửa đường dẫn MPC-BE, thư mục lưu và ưu tiên ngôn ngữ.
Mặc định `vi,en`. Không tự gán ngôn ngữ phụ đề dựa trên ưu tiên.
Cấu hình tự lưu khi đóng, hoặc bấm Lưu thiết lập.

Hỗ trợ SRT, ASS, SSA, VTT và ZIP. Chưa hỗ trợ RAR/7z, ZIP có mật khẩu,
phụ đề ảnh PGS/VobSub hay OCR. ZIP chỉ được đọc trong bộ nhớ, không chạy file bên trong.
Giới hạn: tải/nhập 32 MB; mỗi phụ đề 8 MB; tổng giải nén 64 MB; 200 mục ZIP.
Xem trước chỉ hiển thị tối đa 60.000 ký tự; lưu vẫn giữ nguyên toàn bộ tệp.

## Cấu hình SubDL / OpenSubtitles

Vào **Nguồn phụ đề**, bật nguồn cần dùng, nhập từng trường rồi bấm **Lưu khóa**.
Ô nhập sẽ trống lại sau khi lưu; nhãn **Đã lưu** xác nhận khóa đang có.
Lưu giá trị rỗng sẽ xóa khóa của trường đó.

- SubDL: lấy API key từ tài khoản tại https://subdl.com/panel.
- OpenSubtitles: API key tại https://www.opensubtitles.com/consumers.
  Username/password tùy chọn để tải theo tài khoản; nếu dùng cần nhập cả hai.
- Khóa được mã hóa bằng Windows DPAPI trong `data/secrets.json`; không nằm trong gói ZIP.
- Chưa có API key thì nguồn báo thiếu khóa. Hạn mức tìm/tải phụ thuộc tài khoản.
- SubDL dùng API v1, tối đa 30 kết quả/lượt; OpenSubtitles lấy tối đa 3 trang/lượt.
  Hai adapter hiện khai báo ưu tiên hỗ trợ vi/en. Không đăng nhập qua cookie trình duyệt.

## Phim bộ / cả thư mục

1. Tab **Phim bộ / Thư mục** → **Chọn thư mục phim bộ…**; có thể quét thư mục con.
2. Kiểm tra tên bộ, mùa, tập. Nhận `S01E02`, `1x02`, `Tập 02`/`Ep02`;
   kiểu chỉ có số tập cần nhập mùa hoặc đặt trong thư mục `Season 1`.
   Sửa tên/mùa chung bằng **Áp dụng tên / mùa**, hoặc nhấp đúp từng dòng.
   File chứa nhiều tập cần xử lý thủ công.
3. **Tìm & ghép cả danh sách**: các nguồn tìm đồng thời cho từng tập.
   Chỉ ghép đúng ngôn ngữ, mùa/tập hoặc gói cả mùa; điểm dựa trên tên/bản phát hành.
   Khi có nhiều bản gần điểm nhau, dùng **Chọn bản khác…**.
4. Kiểm tra các dòng đã ghép → **Tải các tập đã ghép**.
   Tool xác nhận tên tập trong ZIP; nhiều file cùng tập hoặc không rõ tập sẽ báo cần chọn thủ công.
5. `Show.S01E02.mkv` được lưu cạnh `Show.S01E02.srt` (hoặc ASS/SSA/VTT).
   Không đổi tên video. Tập đã có phụ đề cùng tên, kể cả `Show.S01E02.vi.srt`, bị bỏ qua.
6. Chọn dòng → **Mở tập đã chọn kèm phụ đề** để mở bằng MPC-BE.
   Đây là mở phim với `/sub`, có thể phát lại từ đầu, chưa phải nạp nóng.

Không bảo đảm đồng bộ timing chỉ dựa vào tên và điểm khớp. Nếu ZIP cần chọn tay,
dùng tab **Phim & phụ đề** để nhập ZIP, xem trước và chọn file chính xác.
Gói cả mùa được tái sử dụng từ bộ nhớ cho các tập liên tiếp dùng cùng kết quả.
Hàng đợi ghép tập không lưu qua lần đóng ứng dụng.

## Kết nối Edge / Chrome (tùy chọn)

Phải thực hiện từ thư mục đã giải nén cuối cùng; sau đăng ký không di chuyển thư mục.

1. Mở `edge://extensions` hoặc `chrome://extensions`, bật Developer mode.
2. Chọn **Load unpacked**, trỏ vào `extensions\chromium` cạnh exe.
3. Sao chép ID extension (32 chữ cái a–p).
4. Mở PowerShell tại thư mục ứng dụng, chạy một trong các lệnh sau với ID thực:

```powershell
powershell -NoProfile -File .\scripts\Register-Browser.ps1 -Browser Edge -ExtensionId ID_THUC_TE
powershell -NoProfile -File .\scripts\Register-Browser.ps1 -Browser Chrome -ExtensionId ID_THUC_TE
```

Chỉ chạy lệnh của trình duyệt bạn muốn dùng. Script ghi duy nhất host
`vn.subtitledesk.bridge` trong NativeMessagingHosts của trình duyệt đó, ở HKCU
(tài khoản Windows hiện tại). Không yêu cầu quyền Administrator.
Nếu chính sách PowerShell chặn script, xem xét nội dung trước; không đổi chính sách hệ thống.
Có thể chạy với `powershell -NoProfile -ExecutionPolicy Bypass -File ...` cho riêng tiến trình
sau khi bạn đồng ý với nội dung script.

5. Mở trang phim. Bấm extension → **Tìm phụ đề cho trang này**, hoặc chọn văn bản
   và dùng menu chuột phải **Tìm phụ đề bằng SubtitleDesk**.
6. Trong SubtitleDesk: **Cài đặt & trình duyệt → Nhận yêu cầu trình duyệt tiếp theo**.
   Kiểm tra tên phim, rồi tìm. Nguồn chưa có API key sẽ báo thiếu khóa.

Edge và Chrome có thể cấp ID khác nhau. Đăng ký từng trình duyệt bằng đúng ID.
Không có quyền đọc lịch sử, cookie, tự quét tab hay đọc nội dung trang.
`activeTab` chỉ phục vụ thao tác bạn chủ động thực hiện; extension gửi URL, tiêu đề
và đoạn được chọn sang ứng dụng trên máy. Không gửi tới dịch vụ bên ngoài.
URL có thể chứa thông tin riêng tư: yêu cầu chưa nhận được giữ trong `data\inbox`;
sau khi nhận sẽ xóa khỏi hàng đợi. Không ghi URL vào nhật ký hay cấu hình.

## Firefox

1. Mở `about:debugging#/runtime/this-firefox`, chọn **Load Temporary Add-on**,
   chọn `extensions\firefox\manifest.json`.
2. Chạy `powershell -NoProfile -File .\scripts\Register-Browser.ps1 -Browser Firefox`.
3. Cách gửi/nhận giống ở trên.

ID cố định: `subtitledesk@local.invalid`. Bản chưa ký chỉ tải tạm thời trong Firefox
thông thường; khởi động lại Firefox cần tải lại. Muốn cài bền vững phải ký qua Mozilla.
Không tự vô hiệu hóa kiểm tra chữ ký.

## Gỡ kết nối / gỡ ứng dụng

- Chạy `scripts\Unregister-Browser.ps1 -Browser Edge` (hoặc Chrome/Firefox) từ đúng
  thư mục đã đăng ký. Script chỉ gỡ host thuộc bản cài đó; không xóa cấu hình.
- Gỡ extension bằng trang quản lý extension của trình duyệt.
- Đóng SubtitleDesk. Có thể xóa thư mục ứng dụng sau khi giữ các phụ đề, mã nguồn
  và cấu hình bạn cần. Tool không tự xóa dữ liệu hay đăng ký tự khởi động.
- Khóa/API key được lưu bằng Windows DPAPI trong `data\secrets.json`, gắn với
  tài khoản Windows. Sao chép file sang tài khoản khác không đảm bảo giải mã được.
- Các ô nhập khóa nằm ở tab **Nguồn phụ đề**.

## Build và kiểm tra

Từ thư mục mã nguồn:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe build.py
```

Xem `ARCHITECTURE.md` để thêm website/player. Xem `VERIFICATION.md` cạnh mã nguồn
để phân biệt phần đã kiểm tra với phần cần thử trong trình duyệt/player thật.
