document.getElementById("send").addEventListener("click", () => {
  const status = document.getElementById("status");
  chrome.tabs.query({active: true, currentWindow: true}, (tabs) => {
    const tab = tabs[0];
    if (!tab?.url || !/^https?:\/\//i.test(tab.url)) {
      status.textContent = "Hãy mở một trang HTTP/HTTPS.";
      return;
    }
    chrome.runtime.sendNativeMessage("vn.subtitledesk.bridge", {
      action: "search",
      url: tab.url.slice(0,8192),
      title: (tab.title || "").slice(0,1024),
      selection: ""
    }, (response) => {
      const error = chrome.runtime.lastError;
      status.textContent = error || !response?.ok
        ? "Chưa gửi được. Kiểm tra đăng ký host, ID extension và đường dẫn ứng dụng."
        : "Đã gửi. Mở SubtitleDesk → Cài đặt & trình duyệt → Nhận yêu cầu.";
    });
  });
});
