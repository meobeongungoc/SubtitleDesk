# SubtitleDesk 0.3.0

Giao diện mới có ba danh sách song song: Movie files, SubDL, OpenSubtitles.
Xem **USER-GUIDE.md** để dùng bản hiện tại. Hướng dẫn bên dưới mô tả bố cục 0.2.
Hàng chờ phụ đề hiện đã lưu qua lần đóng/mở app; cần mở app để tiếp tục áp dụng.

Ứng dụng Windows riêng để tìm và quản lý phụ đề cho phim lẻ, cả thư mục phim bộ,
và phim đang tải trong qBittorrent. Có adapter SubDL và OpenSubtitles; cần API key
của bạn để tìm/tải thật. Không có kết quả giả trong bản dùng thật.

## Chạy ngay

- Từ mã nguồn đã xây: nhấp đúp `START.cmd`.
- Từ gói `SubtitleDesk-Windows-x64.zip`: giải nén toàn bộ và chạy `SubtitleDesk.exe`.
  Giữ `_internal` cạnh file exe. Không cần cài Python.
- Có thể chạy `scripts\Install.ps1` để sao chép sang một thư mục riêng mới.
  Mặc định `D:\MOVIE\Tool\SubtitleDesk-Installed`; thư mục đã tồn tại sẽ bị từ chối.
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

## qBittorrent

Trên máy đã thiết lập: WebUI tại `http://127.0.0.1:18080`, tài khoản `subtitledesk`,
mật khẩu ngẫu nhiên nằm trong kho DPAPI của tool. Chỉ nghe trên loopback, vẫn yêu cầu
đăng nhập. Không mở cổng router. Bản sao INI trước thay đổi nằm trong
`data/backups` **của thư mục mã nguồn**; biên nhận tại `data/qbit-setup-receipt.json`.

- **Kết nối / mở qBittorrent** mở ứng dụng nếu cần rồi kết nối qua API.
- **Tự kết nối…** cho phép tool kết nối/mở qBit khi khởi động tool.
  Không đăng ký khởi động cùng Windows.
- **Đang tải / đã tải** cập nhật mỗi 5 giây, có tiến độ, tốc độ, dung lượng,
  ETA, seeds và peers dạng **đang kết nối / tổng qBittorrent biết**.
  Tổng không phải phép đếm chính xác toàn mạng. `?` nghĩa là chưa biết.
- **Peer chi tiết** lấy danh sách kết nối hiện tại một lần khi bấm.
- **Tìm torrent** dùng các plugin đang cài trong qBit. Seeds/leechers ở đây do website/plugin
  cung cấp, có thể cũ hoặc thiếu; không phải số peer tool đã trực tiếp kết nối.
- Chọn kết quả rồi **Tải torrent đã chọn…**, hoặc thêm magnet/URL/file `.torrent`.
  Chọn thư mục và xác nhận trước khi gửi. Tool không tự chọn torrent để tải.
- Chọn torrent trong **Đang tải / đã tải** → **Phụ đề cho bộ phim đã chọn**.
  Cần có metadata để đọc danh sách file; file bị bỏ chọn trong qBit không được nhập.
- Tìm, ghép và bấm tải phụ đề. Nếu tập chưa tải xong, tool giữ lựa chọn chờ và kiểm tra
  mỗi 10 giây khi tool đang mở. Đóng tool sẽ mất hàng chờ này; mở lại cần chọn lại.
- Trước khi lưu, tool đọc lại đường dẫn/progress. Torrent bị gỡ, file đổi tên hoặc bỏ chọn
  sẽ dừng lưu để bạn kiểm tra. Di chuyển thư mục qua qBit được cập nhật theo API.
- Tool không có lệnh xóa torrent, xóa dữ liệu, cài/sửa search plugin hoặc tắt qBit.

Gói portable trên máy khác không mang mật khẩu/cấu hình này. Bật WebUI trong qBittorrent,
giữ địa chỉ loopback và nhập URL/tài khoản/mật khẩu tương ứng trong tool.
Để gỡ kết nối: bỏ tự kết nối trong tool; nếu không ứng dụng nào khác dùng WebUI,
bạn có thể tắt WebUI trong cài đặt qBittorrent. Không khôi phục nguyên INI cũ sau khi đã
đổi các thiết lập khác vì có thể mất thay đổi mới.

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
