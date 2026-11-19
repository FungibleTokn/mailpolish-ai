// Extension service worker: host-permissioned API requests avoid Gmail page CORS restrictions.
importScripts("api-config.js");
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
      const { inviteKey } = await chrome.storage.session.get("inviteKey");
      if (!inviteKey) throw new Error("Open the MailScribe extension to sign in.");
      const response = await fetch(MAILPOLISH_API_URL + "/rewrite", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + inviteKey },
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
