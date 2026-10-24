"""Build inside this project only. No registry changes or browser installation."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"


def build_extensions(target):
    for browser in ("chromium", "firefox"):
        folder = target / browser
        folder.mkdir(parents=True, exist_ok=True)
        for source in (ROOT / "extensions" / "shared").iterdir():
            shutil.copy2(source, folder / source.name)
        manifest = json.loads((ROOT / "extensions" / f"{browser}.manifest.json").read_text("utf-8"))
        (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), "utf-8")


def main():
    for variable, folder in (("TCL_LIBRARY", "tcl8.6"), ("TK_LIBRARY", "tk8.6")):
        location = Path(sys.base_prefix) / "tcl" / folder
        if location.is_dir():
            os.environ.setdefault(variable, str(location))
    frozen = ROOT / "build" / "frozen"
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--distpath", str(frozen), "--onedir",
                    "--windowed", "--name", "SubtitleDesk", "--collect-all", "tkinterdnd2",
                    "--copy-metadata", "tkinterdnd2",
                    "--add-data", "subtitledesk/assets;subtitledesk/assets",
                    "--icon", "subtitledesk/assets/app.ico",
                    "main.py"], cwd=ROOT, check=True)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--distpath", str(frozen), "--onefile",
                    "--console", "--name", "SubtitleDeskHost", "native_host.py"],
                   cwd=ROOT, check=True)
    app = frozen / "SubtitleDesk"
    shutil.copy2(frozen / "SubtitleDeskHost.exe", app / "SubtitleDeskHost.exe")
    shutil.copytree(ROOT / "scripts", app / "scripts", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("setup_local_qbit.py", "__pycache__"))
    build_extensions(app / "extensions")
    for name in ("USER-GUIDE.md", "HUONG-DAN.md", "ARCHITECTURE.md", "THIRD-PARTY.md"):
        shutil.copy2(ROOT / name, app / name)
    if (ROOT / "VERIFICATION.md").exists():
        shutil.copy2(ROOT / "VERIFICATION.md", app / "VERIFICATION.md")
    licenses = app / "licenses"
    licenses.mkdir(exist_ok=True)
    shutil.copy2(Path(sys.base_prefix) / "LICENSE.txt", licenses / "Python-LICENSE.txt")
    from importlib.metadata import distribution
    trash_package = distribution("Send2Trash")
    trash_license_file = next(path for path in trash_package.files
                              if path.parts[-2:] == ("licenses", "LICENSE"))
    trash_license = Path(trash_package.locate_file(trash_license_file))
    shutil.copy2(trash_license, licenses / "Send2Trash-LICENSE.txt")
    DIST.mkdir(exist_ok=True)
    # Build portable packages only; installation is a separate manual operation.
    shutil.make_archive(str(DIST / "extension-chromium"), "zip", app / "extensions" / "chromium")
    shutil.make_archive(str(DIST / "extension-firefox"), "zip", app / "extensions" / "firefox")
    # Do not include any local settings/credentials in distribution archives.
    # No recursive deletion: reconstruct the archive from the explicit current app tree.
    import zipfile
    with zipfile.ZipFile(DIST / "SubtitleDesk-Windows-x64.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        for path in app.rglob("*"):
            relative = path.relative_to(app)
            if path.is_file() and relative.parts[0] != "data":
                archive.write(path, Path("SubtitleDesk") / relative)
    with zipfile.ZipFile(DIST / "SubtitleDesk-source.zip", "w", zipfile.ZIP_DEFLATED) as archive:
        root_files = ("main.py", "native_host.py", "build.py", "requirements.txt",
                      "requirements-build.txt", "START.cmd", "README.md", "USER-GUIDE.md",
                      "HUONG-DAN.md", "ARCHITECTURE.md", "THIRD-PARTY.md", "VERIFICATION.md")
        files = [ROOT / name for name in root_files if (ROOT / name).is_file()]
        for folder in ("subtitledesk", "scripts", "examples", "extensions"):
            files.extend(p for p in (ROOT / folder).rglob("*") if p.is_file()
                         and not p.is_symlink() and "__pycache__" not in p.parts
                         and p.name != "setup_local_qbit.py" and p.suffix.lower() in
                         (".py", ".ps1", ".cjs", ".js", ".json", ".html", ".css", ".md", ".txt", ".csv", ".png", ".ico"))
        # Local live probes and their reports may contain personal paths/download data.
        files.extend(p for p in (ROOT / "tests").iterdir() if p.is_file()
                     and p.suffix in (".py", ".cjs") and not p.is_symlink())
        for path in sorted(files):
            archive.write(path, Path("SubtitleDesk") / path.relative_to(ROOT))
    import hashlib
    checksums = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in DIST.glob("*.zip")}
    for name in ("SubtitleDesk.exe", "SubtitleDeskHost.exe"):
        checksums["SubtitleDesk/" + name] = hashlib.sha256((app / name).read_bytes()).hexdigest()
    (DIST / "SHA256.json").write_text(json.dumps(checksums, indent=2), "utf-8")
    print("Package:", DIST / "SubtitleDesk-Windows-x64.zip")


if __name__ == "__main__":
    main()
