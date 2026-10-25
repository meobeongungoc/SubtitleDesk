<div align="center">
  <img src="subtitledesk/assets/logo.png" alt="SubtitleDesk cat logo" width="112" />
  <h1>SubtitleDesk</h1>
  <p><strong>Find subtitles for a whole folder of movies and TV episodes.</strong></p>
  <p>Search two subtitle services, choose a match, and open your video with subtitles in MPC-BE.</p>
</div>

---

SubtitleDesk is a Windows app that brings your video files and subtitle search together. It scans a movie or series folder, shows results from **SubDL** and **OpenSubtitles** side by side, and helps you get subtitles next to the videos they belong to.

## Find and apply subtitles

Choose a movie folder and search its episodes together. SubtitleDesk highlights exact filename matches and can download and apply them automatically. You can also compare other results, choose a different version, and filter by Vietnamese, English, both, or another available language.

Subtitles are saved with the same base name as the video, so supported players can find them easily. Existing subtitle files are kept safe from being overwritten.

## More than subtitle search

- **qBittorrent:** view downloads, search installed torrent plugins, and bring episode files into SubtitleDesk, even while a download is in progress. qBittorrent starts when you open Torrents and exits after observed downloads finish while SubtitleDesk is running.
- **Anki vocabulary export:** collect advanced English words from a folder of subtitles and export them for Anki. After a successful export, the scanned subtitle files move to the Windows Recycle Bin.
- **MPC-BE:** open a completed video with its selected subtitle.
- **Browser connection:** optionally send a page title, URL, or text you select from Edge, Chrome, or Firefox to the app.
- **Personalize the app:** choose one of four themes and a font installed on Windows.
- **Manage episodes:** every movie row has **Play** and **Delete** buttons. Play opens that episode; Delete immediately moves only that video to the Windows Recycle Bin without confirmation and keeps its subtitles. You can also double-click to play, select several videos with Ctrl/Shift, and use the right-click menu or Delete key to move videos immediately to the Windows Recycle Bin without a confirmation dialog. Sidecar subtitles stay in place.

## Get started

SubtitleDesk is a portable Windows application. Download the [latest Windows release](https://github.com/meobeongungoc/SubtitleDesk/releases/latest), extract the package, and run `SubtitleDesk.exe`. Add your SubDL and OpenSubtitles API keys in Settings to search and download subtitles. Browser integration is optional.

- [Setup and usage guide](USER-GUIDE.md)
- [Verification notes and known limitations](VERIFICATION.md)

## Current limitations

MPC-BE is the currently supported player. Subtitle matching does not guarantee synchronized timing. SubtitleDesk does not extract embedded subtitles from video files and does not support OCR or RAR/7z archives.
