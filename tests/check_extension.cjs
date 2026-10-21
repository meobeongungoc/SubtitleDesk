// Test extension event handlers without installing into user browser profiles.
const fs = require("node:fs");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const path = require("node:path");
const root = path.join(__dirname, "..", "extensions", "shared");
let install, click, sent, menu, badge;
const chrome = {
  runtime: {
    onInstalled: { addListener(fn) { install = fn; } },
    sendNativeMessage(host, message, callback) {
      assert.equal(host, "vn.subtitledesk.bridge");
      sent = message; callback({ok: true});
    }
  },
  contextMenus: {
    removeAll(fn) { fn(); },
    create(value) { menu = value; },
    onClicked: { addListener(fn) { click = fn; } }
  },
  action: {setBadgeText(v) { badge = v.text; }, setTitle() {}}
};
vm.runInNewContext(fs.readFileSync(path.join(root, "background.js"), "utf8"), {chrome});
install();
assert.equal(menu.id, "subtitle-search");
click({menuItemId: "subtitle-search", selectionText: "Phim Việt"},
      {url: "https://example.org/film", title: "A film"});
assert.equal(sent.selection, "Phim Việt");
assert.equal(sent.url, "https://example.org/film");
assert.equal(badge, "OK");
chrome.runtime.lastError = {message: "host missing"};
click({menuItemId: "subtitle-search"}, {url: "https://example.org/", title: ""});
assert.equal(badge, "!");
delete chrome.runtime.lastError;
let sendClick;
const status = {textContent: ""};
const document = { getElementById(id) {
  return id === "status" ? status : {addEventListener(name, fn) { sendClick = fn; }};
}};
chrome.tabs = {query(options, fn) {fn([{url: "https://example.org/", title: "Film"}]);}};
vm.runInNewContext(fs.readFileSync(path.join(root, "popup.js"), "utf8"), {chrome, document});
sendClick();
assert.equal(sent.title, "Film");
assert.match(status.textContent, /Đã gửi/);
chrome.tabs.query = (options, fn) => fn([{url: "edge://settings"}]);
sendClick();
assert.match(status.textContent, /HTTP/);
for (const browser of ["chromium", "firefox"]) {
  const manifest = JSON.parse(fs.readFileSync(path.join(root, "..", browser + ".manifest.json"), "utf8"));
  assert.deepEqual(manifest.permissions, ["activeTab", "contextMenus", "nativeMessaging"]);
  assert.equal(manifest.host_permissions, undefined);
}
console.log("PASS: context menu, popup, Unicode payload, host failure, blocked scheme, minimal permissions.");
