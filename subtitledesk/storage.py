import base64
import binascii
import ctypes
import json
import os
from pathlib import Path
from ctypes import wintypes


DEFAULTS = {
    "theme": "blue",
    "library_root": "", "library_selection": "",
    "vocabulary_input_dir": "", "vocabulary_export_dir": "",
    "glass_strength": 10,
    "font_family": "Segoe UI",
    "languages": "vi,en", "player_kind": "MPC-BE",
    "player_path": r"D:\Program\MPC-BE\mpc-be64.exe", "output_dir": "",
    "save_beside": True, "geometry": "1080x780", "disabled_sources": [],
}


def dialog_directory(*locations):
    """Use the last confirmed folder, or its nearest surviving parent."""
    for location in locations:
        if not location:
            continue
        try:
            path = Path(location).expanduser()
            for candidate in (path, *path.parents):
                if candidate.is_dir():
                    return str(candidate)
        except (OSError, ValueError, RuntimeError):
            continue
    return None


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def load_settings(root: Path):
    path = root / "settings.json"
    if not path.exists():
        return DEFAULTS.copy()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError()
        settings = DEFAULTS.copy()
        for key, default in DEFAULTS.items():
            if key in value and isinstance(value[key], type(default)):
                settings[key] = value[key]
        return settings
    except (ValueError, OSError) as exc:
        raise ValueError("Could not read settings.json. The original file was preserved.") from exc


class Blob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_ubyte))]


def protect(data: bytes, decrypt=False) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Protected credential storage requires Windows DPAPI.")
    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    target = Blob()
    crypt = ctypes.WinDLL("crypt32", use_last_error=True)
    function = crypt.CryptUnprotectData if decrypt else crypt.CryptProtectData
    function.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p,
                         ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    function.restype = wintypes.BOOL
    if not function(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(target.pbData, target.cbData)
    finally:
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.LocalFree.argtypes = [ctypes.c_void_p]
        kernel.LocalFree(ctypes.cast(target.pbData, ctypes.c_void_p))


class CredentialError(ValueError):
    """Safe credential failure; the original storage is never replaced implicitly."""


class SecretStore:
    def __init__(self, root: Path):
        self.path = root / "secrets.json"

    def _load(self):
        try:
            values = json.loads(self.path.read_text("utf-8")) if self.path.exists() else {}
            if not isinstance(values, dict) or any(not isinstance(k, str) or not isinstance(v, str)
                                                    for k, v in values.items()):
                raise ValueError()
            return values
        except (OSError, ValueError):
            raise CredentialError("Credential storage cannot be read. Its original file has been preserved. Restore it or choose Reset credentials in Settings.") from None

    def set(self, provider: str, field: str, value: str):
        values = self._load()
        key = f"{provider}:{field}"
        if value:
            values[key] = base64.b64encode(protect(value.encode("utf-8"))).decode("ascii")
        else:
            values.pop(key, None)
        write_json(self.path, values)

    def get(self, provider: str, field: str) -> str:
        encoded = self._load().get(f"{provider}:{field}")
        try:
            return protect(base64.b64decode(encoded, validate=True), decrypt=True).decode("utf-8") if encoded else ""
        except (OSError, ValueError, binascii.Error):
            raise CredentialError("This saved credential cannot be decrypted on this Windows profile. Enter and save it again in Settings.") from None

    def reset(self):
        """An explicit user action archives the old store before creating an empty one."""
        import uuid
        backup = self.path.with_name('secrets-unreadable-' + uuid.uuid4().hex + '.json')
        if self.path.exists():
            self.path.rename(backup)
        return backup
