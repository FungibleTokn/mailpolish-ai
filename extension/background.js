// Extension service worker: host-permissioned API requests avoid Gmail page CORS restrictions.
importScripts("config.js");
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type !== "MAILPOLISH_REWRITE") return false;
  if (!sender.url?.startsWith("https://mail.google.com/")) {
    sendResponse({ error: "Unauthorized sender" });
    return false;
  }
  const { text, mode } = message.payload || {};
  if (typeof text !== "string" || !text.trim() || text.length > 12000 ||
      !["professional", "shorten", "grammar", "diplomatic"].includes(mode)) {
    sendResponse({ error: "Invalid rewrite request" });
    return false;
  }
  (async () => {
    try {
      const response = await fetch(MAILPOLISH_CONFIG.apiUrl + "/rewrite", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Dev-Token": MAILPOLISH_CONFIG.apiToken },
        body: JSON.stringify({ text, mode })
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "API error " + response.status);
      sendResponse({ rewritten: data.rewritten });
    } catch (error) {
      sendResponse({ error: error.message || "Rewrite failed" });
    }
  })();
  return true;
});
