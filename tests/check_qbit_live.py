"""Read-only API smoke check; may launch qBittorrent, never adds a torrent."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from subtitledesk.storage import SecretStore, load_settings
from subtitledesk.qbittorrent import QbitClient

settings = load_settings(ROOT / "data")
client = QbitClient(settings["qbit_url"], settings["qbit_username"],
                    SecretStore(ROOT / "data").get("qbittorrent", "password"), settings["qbit_exe"])
version = client.connect(launch=True)
plugins = client.plugins()
torrents = client.torrents()
files_checked = 0
for torrent in torrents[:3]:
    files = client.files(torrent["hash"])
    assert all("name" in file and "progress" in file for file in files)
    files_checked += len(files)
    peers = client.peers(torrent["hash"])
    assert isinstance(peers.get("peers", {}), dict)
report = {"passed": True, "version": version, "authenticated": True,
          "torrent_count": len(torrents), "files_checked": files_checked,
          "plugins": [{"name": p["name"], "enabled": p.get("enabled")} for p in plugins],
          "torrent_added": False}
(ROOT / "test-artifacts").mkdir(exist_ok=True)
(ROOT / "test-artifacts" / "qbit-live-result.json").write_text(json.dumps(report, indent=2), "utf-8")
print(json.dumps(report))
