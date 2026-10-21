/* No content script, host permissions, history access or automatic collection. */
const HOST = "vn.subtitledesk.bridge";
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.removeAll(() => {
    chrome.contextMenus.create({
      id: "subtitle-search",
      title: "Tìm phụ đề bằng SubtitleDesk",
      contexts: ["page", "selection", "link"],
      documentUrlPatterns: ["http://*/*", "https://*/*"]
    });
  });
});
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== "subtitle-search") return;
  const message = {
    action: "search",
    url: (info.linkUrl || tab.url || "").slice(0, 8192),
    title: (tab.title || "").slice(0, 1024),
    selection: (info.selectionText || "").slice(0, 2048)
  };
  chrome.runtime.sendNativeMessage(HOST, message, (response) => {
    const error = chrome.runtime.lastError;
    const action = chrome.action || chrome.browserAction;
    action.setBadgeText({text: error || !response?.ok ? "!" : "OK"});
    action.setTitle({title: error || !response?.ok
      ? "Chưa gửi được — mở extension để xem hướng dẫn"
      : "Đã gửi sang SubtitleDesk"});
  });
});
