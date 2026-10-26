# SubtitleDesk 0.8.0

## Appearance

Open the **Appearance** tab to select Blue, Beige, Green or Purple.
The selected theme is preserved across updates and restarts. All three movie and
subtitle lists remain visible together. Drag the separators to adjust their widths.
Small windows and large fonts show fewer rows; scroll to see remaining items.
The theme surfaces are drawn by the app and are not native Fluent controls.

## Interface font

Open **Appearance**, then use **Font** to choose from installed Windows font families.
Type part of a name to filter the dropdown; select a font or enter its full name
and press Enter. Changes apply immediately and persist after restart. Theme changes
preserve the font. If a saved font was removed, the app falls back to Segoe UI or
the system default. Windows title bars and native file/message dialogs use their
own system fonts. Glyph coverage depends on the font; Windows may substitute
another font for unsupported characters. Vertical font aliases are omitted.

## Fixed movie library

Use **Library folder…** to set a persistent library root containing your local movies and series.
The app scans files already present in that folder and its subfolders.

Use the selector beside **Movie files** to choose a movie/series folder. Nested
season folders are scanned together. **Refresh** discovers newly added
folders and reloads the selected folder’s videos; the tool's own application directory is excluded. Videos directly in the
root appear under **Movies in library root**. Finish or cancel active subtitle work
before switching movies.

The duplicate content logo/title is removed. Rounded cards, shaded buttons, thin borders, monochrome icons and coordinated
four-theme palettes provide the visual styling. Appearance settings are in a
tab within the main window; the toolbar wraps when space is limited. The application icon
remains in the Windows title bar/taskbar.

### Appearance

Choose one of four themes and any installed font in Appearance. The Transparency
slider ranges from 0 to 100 in steps of 5: zero means full opacity and 100 means
65% opacity. It affects the entire window and saves automatically.

Run `START.cmd`, or run `dist/SubtitleDesk/SubtitleDesk.exe` directly.
For unattended diagnostics, `SubtitleDesk.exe --hidden` starts without displaying the window.
The portable package includes its Python runtime. Keep `_internal` next to the executable.

## Main window

The app uses one window with **Library**, **Vocabulary**, **Settings** and **Appearance** tabs.
There is no Preview tab. Episode editing and subtitle file selection stay inside the app.
Use **Settings → Player & browser → Import local subtitle / ZIP…** when you need to inspect
an archive; **Back to movie library** returns to the three lists. Routine errors and progress
appear inline. Windows file/folder pickers remain native dialogs. Replacing an existing
subtitle requires an explicit inline **Replace subtitle** action; deleting a video does not.


The window shows three lists at the same time:

1. **Movie files** — browse videos in your movie library, including nested season folders.
2. **SubDL** — subtitles for the selected video from SubDL.
3. **OpenSubtitles** — subtitles for the same video from OpenSubtitles.

**Play** and **Delete** appear on every movie row. Play opens that episode; Delete moves
only that video to the Windows Recycle Bin immediately without confirmation, keeping its subtitles.

Click **Find subtitles** to search the folder. Select a movie on the left to compare both sources.
Double-click a movie or press **Enter** to open it in the configured player. Saved subtitles are
loaded when available; videos without an external subtitle can also be opened. Double-clicking
empty space or a column heading does not open the previously selected video.

Use **Ctrl+click** or **Shift+click** to select several videos, or **Ctrl+A** to select all.
Right-click a selected video to keep the group selected and open its context menu:
**Open**, **Edit episode details…**, and **Delete**. Right-clicking an unselected video selects
that video. **Shift+F10** or the keyboard Menu key also opens the menu.

**Delete** in the menu or on the keyboard immediately moves selected videos to the Windows
Recycle Bin without a confirmation dialog. Sidecar subtitles stay in their folders. Finish active subtitle work before deleting videos. Use **Edit episode details…** to
correct the title, year, season or episode used for searching; video files are never renamed.

To remove videos from the library, select one or more rows in **Movie files** using Ctrl+click
or Shift+click, then right-click and choose **Delete**. Files move immediately without a
confirmation dialog. Only the video files move to the Windows Recycle Bin; matching subtitle files stay in their folders.
This action is available for videos on a local fixed drive inside the chosen movie library.
Finish active subtitle work first.

The language menu lists **Vietnamese**, **English**, **Vietnamese + English**, then other languages.
The choice filters both source lists. With both selected, an exact match can download for each language, with Vietnamese searched first.
Availability and language codes depend on the source. An empty source list means no accepted result
for that movie and language; it does not prove the subtitle is absent from the entire website.

## Automatic exact matches

An actual subtitle filename from the API qualifies when its base name equals the video base name,
ignoring case and the video/subtitle extension. OpenSubtitles sometimes supplies a filename without
the subtitle extension; that base name can also qualify. Release titles and similarity scores alone
do not qualify. Conflicting season/episode information is rejected.

Exact matches are highlighted. The app automatically downloads the preferred exact match without
asking for approval, validates its contents, then saves it beside the video using the video filename.
For example, `Show.S01E02.mkv` receives `Show.S01E02.vi.srt` and/or `Show.S01E02.en.srt`.
The video base name is preserved; language suffixes let both tracks coexist. Existing untagged
subtitles are kept and their language is not guessed.

The file status and notification line show the source and outcome. Other versions remain available
for selection with **Download & apply**. Existing tracks of the requested language are skipped; automatic downloads
never overwrite them. A matching filename still does not guarantee perfectly synchronized timing.

ZIP season packs must contain an unambiguous subtitle for the episode. For ambiguous archives,
use **Settings → Player & browser → Import local subtitle / ZIP…** and select the file manually.

## Vocabulary export and subtitle cleanup

Open the **Vocabulary** tab, choose a movie or series folder, and click **Scan subtitles**. The scan
includes subfolders and previews C1/C2 English vocabulary before export. Click **Export Anki
TXT…** and choose a new `.txt` filename. After the Anki file is saved successfully, SubtitleDesk
automatically moves the SRT, VTT, ASS and SSA files found during that scan to the Windows Recycle
Bin, including subtitles in other languages. Videos and unrelated files remain in place. Files
added or changed after the scan are kept; scan again if you want to include them. If export is
cancelled before choosing an output or fails to save, no subtitles are moved. Saving and cleanup run
in the background. **Cancel** during cleanup keeps the remaining subtitle files; the completed
Anki TXT is retained. The status line reports how many were moved or kept, with details inline.

## Local file workflow

Searches and downloads use the video files currently present in your chosen library.
Subtitles are validated and saved directly beside each video. If a video is moved or removed,
refresh the library and search again. **Cancel** stops current work; subtitles already saved remain.

Old prepared-download cache files from earlier versions are left untouched and are not resumed.

## Settings and credentials

Open **Settings → Sources**. Get a key from the source's own account:

- SubDL: `https://subdl.com/panel`
- OpenSubtitles: `https://www.opensubtitles.com/consumers`

Enter each API key and click **Save**. The entry clears after saving; **Saved** confirms storage.
OpenSubtitles username/password are optional. Enter both or neither. Downloads without a login
use the account/anonymous allowance reported by the service.

Secrets are protected with Windows DPAPI in `data/secrets.json`. Download links returned by SubDL
are normalized to remove credential query strings; the key is sent only in the download header.
Portable/source archives exclude local settings, keys, pending subtitles and movie files.
Unreadable credentials disable the affected source while local tools remain usable. A credential
that cannot be decrypted can be entered again. If the storage file itself is malformed, the explicit
**Archive unreadable credential storage & reset…** action preserves a private backup before resetting.
Do not publish those backup files.

**Player & browser** contains the player executable, output preferences and optional browser setup.
MPC-BE opens a movie with `/sub`; it may restart playback. Hot subtitle injection is not implemented.
The row **Play** action can open a video with or without an external subtitle.

## Browser connection

Edge and Chrome use `extensions/chromium`. Firefox uses `extensions/firefox`.
Load the unpacked extension, then register the native host from the final app directory:

```powershell
powershell -NoProfile -File .\scripts\Register-Browser.ps1 -Browser Edge -ExtensionId YOUR_EXTENSION_ID
```

Replace `Edge` with `Chrome` when appropriate. Firefox uses `-Browser Firefox` without an extension ID.
Firefox's unsigned development package is temporary unless signed through Mozilla.
The extension sends only a URL, title or text you explicitly select. The app works without it.

## Formats, removal and development

Supported: SRT, ASS, SSA, VTT and ZIP. RAR/7z, image subtitles and OCR are not supported.
Limits: 32 MB download, 8 MB per subtitle, 64 MB expanded ZIP and 200 archive entries.

To unregister a browser connection, run `scripts/Unregister-Browser.ps1 -Browser Edge` (or the browser
you registered), then remove the extension in that browser. Keep any needed subtitles/settings,
close the app and remove its dedicated folder to uninstall the portable application.

Build and checks:

```powershell
.\.venv\Scripts\python.exe tests/run_tests.py
.\.venv\Scripts\python.exe build.py
```

See `VERIFICATION.md` for checks and remaining limits of the current version.

## Updating without interrupting an open app

Builds create portable archives and leave `dist/SubtitleDesk` unchanged by default.
Close SubtitleDesk yourself when ready to update, extract the new archive into a
separate folder, and keep your existing `data` folder if you want to retain your
settings and protected credentials on the same Windows account. Do not replace
files while the application is running. Developer builds use `python build.py` to
create archives only; the build never installs files into an open app or stops processes.
