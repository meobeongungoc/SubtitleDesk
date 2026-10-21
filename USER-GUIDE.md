# SubtitleDesk 0.6.0

## Appearance

Open **Appearance** in the main toolbar to select Blue, Beige, Green or Purple.
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

Use **Library folder…** to set a persistent library root. This installation uses
`D:\MOVIE`, also configured as qBittorrent's default save directory. Existing
torrents keep their current locations; category-specific overrides in qBittorrent
may still use their own paths. Torrents added through this tool use the library root.

Use the selector beside **Movie files** to choose a movie/series folder. Nested
season folders are scanned together. **Refresh** discovers newly added
folders; the tool's own application directory is excluded. Videos directly in the
root appear under **Movies in library root**. Finish or cancel active subtitle work
before switching movies so queued subtitles are not discarded.

The duplicate content logo/title is removed. Rounded cards, shaded buttons, thin borders, monochrome icons and coordinated
four-theme palettes provide the visual styling. Appearance settings are in a
separate window; the toolbar wraps when space is limited. The application icon
remains in the Windows title bar/taskbar.

### Appearance

Choose one of four themes and any installed font in Appearance. The Transparency
slider ranges from 0 to 100 in steps of 5: zero means full opacity and 100 means
65% opacity. It affects the entire window and saves automatically.

Run `START.cmd`, or run `dist/SubtitleDesk/SubtitleDesk.exe` directly.
The portable package includes its Python runtime. Keep `_internal` next to the executable.

## Main window

The window shows three lists at the same time:

1. **Movie files** — choose a folder, including its subfolders, or import a torrent's files.
2. **SubDL** — subtitles for the selected video from SubDL.
3. **OpenSubtitles** — subtitles for the same video from OpenSubtitles.

Click **Find subtitles** to search the folder. Select a movie on the left to compare both sources.
Double-click a movie to correct its title, year, season or episode. Video files are never renamed.

The language menu lists **Vietnamese**, **English**, **Vietnamese + English**, then other languages.
The choice filters both source lists. With both selected, Vietnamese exact matches take priority.
Availability and language codes depend on the source. An empty source list means no accepted result
for that movie and language; it does not prove the subtitle is absent from the entire website.

## Automatic exact matches

An actual subtitle filename from the API qualifies when its base name equals the video base name,
ignoring case and the video/subtitle extension. OpenSubtitles sometimes supplies a filename without
the subtitle extension; that base name can also qualify. Release titles and similarity scores alone
do not qualify. Conflicting season/episode information is rejected.

Exact matches are highlighted. The app automatically downloads the preferred exact match without
asking for approval, validates its contents, then saves it beside the video using the video filename.
For example, `Show.S01E02.mkv` receives `Show.S01E02.srt`.

The file status and notification line show the source and outcome. Other versions remain available
for selection with **Download & apply**. Existing subtitles are skipped; automatic downloads
never overwrite them. A matching filename still does not guarantee perfectly synchronized timing.

ZIP season packs must contain an unambiguous subtitle for the episode. For ambiguous archives,
open **Preview** and select the file manually.

## Videos still downloading

The app can download a subtitle before its video finishes. It shows **Subtitle downloaded; waiting
for video** and saves a prepared copy in `data/pending`. When qBittorrent reports the video complete,
the app resolves its current location again and applies the subtitle.

Keep SubtitleDesk open for automatic application. Closing it retains the prepared queue in
`data/pending-subtitles.json`; reopening resumes it. It does not install a background service or
Windows startup task. A torrent removed from qBittorrent, a renamed file or a deselected video
requires you to check/import it again.

**Cancel** stops the current work and clears its active waiting queue. Already saved subtitles stay.
Choosing a different folder replaces the active list and queue.

## Torrents

Open **Torrents** to connect to qBittorrent, view downloads or search its installed plugins.
The local connection on this machine is `http://127.0.0.1:18080`.
Use **Import selected movie files** to bring a torrent's episode list into the main window.

You can add a selected search result, magnet/URL or `.torrent` file. The normal app asks for a save
folder and confirmation before adding a torrent. A new film does not require a new Python script.
Search plugin results are supplied by the source websites; displayed seed/peer totals may be stale.
Connected peer counts in Downloads are from qBittorrent.

Live-check scripts under `tests/live` are development checks, not components of the portable app.
They are not run by normal searches or downloads.

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

**Player & browser** contains the player executable, output preferences and optional browser setup.
MPC-BE opens a movie with `/sub`; it may restart playback. Hot subtitle injection is not implemented.
The main **Open in player** action requires a completed video and saved subtitle.

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
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe build.py
```

See `VERIFICATION.md` for evidence and remaining limits. The 2026-10-20 live check downloaded
20 English S01 subtitles from SubDL and 20 Vietnamese S01 subtitles from OpenSubtitles.
The Gravity Falls BluRay video download was still in progress at that check; playback/timing had
not yet been validated for that season.
# Appearance (0.4)

Use the Theme selector below the app header to choose Modern Neutral · Blue,
Warm Neutral · Beige, Green Accent, or Purple Accent. Changes apply immediately
to the main view, Settings, Torrents and subtitle preview, and are saved for the
next launch. The shared cat logo appears in the header and application icon.
Saved subtitles remain green; exact filename matches use the current accent.
Windows file pickers and system message boxes follow Windows appearance settings.
