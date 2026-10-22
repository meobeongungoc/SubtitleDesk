"""One-time local setup, only when explicitly requested by the user.
Refuses running qBittorrent or an existing WebUI password. No secret output.
"""
import base64
import hashlib
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from subtitledesk.storage import SecretStore, load_settings, write_json


def main():
    processes = subprocess.run(["tasklist", "/FI", "IMAGENAME eq qbittorrent.exe", "/FO", "CSV", "/NH"],
                               capture_output=True, text=True, check=True)
    if '"qbittorrent.exe"' in processes.stdout.lower():
        raise RuntimeError("qBittorrent đang chạy; không sửa cấu hình khi ứng dụng đang chạy.")
    config = Path(os.environ["APPDATA"]) / "qBittorrent" / "qBittorrent.ini"
    original = config.read_bytes()
    text = original.decode("utf-8-sig")
    if any(line.startswith(("WebUI\\Password_PBKDF2=", "WebUI\\Password_ha1=")) for line in text.splitlines()):
        raise RuntimeError("Đã có mật khẩu WebUI. Giữ nguyên; nhập mật khẩu hiện tại trong SubtitleDesk.")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 18080))
    password = secrets.token_urlsafe(32)
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha512", password.encode(), salt, 100000, 64)
    encoded = base64.b64encode(salt).decode() + ":" + base64.b64encode(digest).decode()
    updates = {
        "WebUI\\Enabled": "true", "WebUI\\Address": "127.0.0.1", "WebUI\\Port": "18080",
        "WebUI\\Username": "subtitledesk", "WebUI\\Password_PBKDF2": f'"@ByteArray({encoded})"',
        "WebUI\\LocalHostAuth": "true", "WebUI\\AuthSubnetWhitelistEnabled": "false",
        "WebUI\\HTTPS\\Enabled": "false", "WebUI\\UseUPnP": "false",
    }
    lines, output, section, added = text.splitlines(), [], "", False
    for line in lines:
        if line.startswith("["):
            if section == "[Preferences]":
                output.extend(f"{key}={value}" for key, value in updates.items())
                added = True
            section = line.strip()
        key = line.split("=", 1)[0]
        if section == "[Preferences]" and key in updates:
            continue
        output.append(line)
    if not added:
        if section != "[Preferences]":
            output += ["", "[Preferences]"]
        output.extend(f"{key}={value}" for key, value in updates.items())
    backups = ROOT / "data" / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = backups / f"qBittorrent-before-webui-{stamp}.ini"
    with backup.open("xb") as stream:
        stream.write(original)
    # Write credentials before config; abort without touching qBit if DPAPI fails.
    SecretStore(ROOT / "data").set("qbittorrent", "password", password)
    for data_root in (ROOT / "data", ROOT / "dist" / "SubtitleDesk" / "data"):
        SecretStore(data_root).set("qbittorrent", "password", password)
        settings = load_settings(data_root)
        settings.update(qbit_url="http://127.0.0.1:18080", qbit_username="subtitledesk",
                        qbit_exe=r"D:\Program\qBittorrent\qbittorrent.exe")
        write_json(data_root / "settings.json", settings)
    temporary = config.with_suffix(".subtitledesk.tmp")
    temporary.write_text("\n".join(output) + "\n", encoding="utf-8")
    os.replace(temporary, config)
    write_json(ROOT / "data" / "qbit-setup-receipt.json",
               {"config": str(config), "backup": str(backup), "url": "http://127.0.0.1:18080",
                "changed_keys": list(updates), "password_storage": "Windows DPAPI in SubtitleDesk data"})
    print("Configured loopback WebUI on port 18080. Backup retained; password stored with DPAPI.")


if __name__ == "__main__":
    main()
