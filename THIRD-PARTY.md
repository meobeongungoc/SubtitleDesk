# Thành phần bên thứ ba

- Python 3.13 / Tkinter: Python Software Foundation License; Tcl/Tk theo giấy phép kèm runtime.
  https://www.python.org/psf/license/
- tkinterdnd2 0.6.4 và TkDnD: xem LICENSE trong gói phân phối.
  https://github.com/Eliav2/tkinterdnd2
- PyInstaller 6.22.3: GPL kèm ngoại lệ cho phép phân phối bundle.
  https://pyinstaller.org/en/stable/license.html
- Send2Trash 2.1.0: BSD 3-Clause License.
  https://github.com/arsenetar/send2trash
- pywin32 311: Python Software Foundation License.
  https://github.com/mhammond/pywin32

Phần mềm chưa ký số. Không phân phối MPC-BE hay các player khác.
Build chỉ đưa Python runtime và các dependency cần thiết vào `_internal`.

Dữ liệu từ vựng offline:

- Octanove Vocabulary Profile C1/C2 v1.0, Octanove Labs: CC BY-SA 4.0.
  https://github.com/openlanguageprofiles/olp-en-cefrj
  https://creativecommons.org/licenses/by-sa/4.0/
- CEFR-J Wordlist v1.5, Yukio Tono, Tokyo University of Foreign Studies,
  Tono Laboratory: được sử dụng miễn phí với điều kiện trích dẫn nguồn.
  Dùng để loại các từ A1–B2 trùng với danh sách nâng cao.
- CSV gốc, revision, checksum và ghi công nằm trong `subtitledesk/assets/vocabulary/`.
  Không có thêm thư viện NLP hoặc mô hình AI đi kèm.
