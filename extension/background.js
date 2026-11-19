// Extension service worker: host-permissioned API requests avoid Gmail page CORS restrictions.
importScripts("api-config.js");
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message?.type === "MAILSCRIBE_GOOGLE_SIGN_IN" &&
      sender.url === chrome.runtime.getURL("popup.html")) {
    googleSignIn().catch(async error => {
      await chrome.storage.session.set({ signInError: error.message });
    });
    sendResponse({ started: true });
    return false;
  }
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
      const { sessionToken, inviteKey } = await chrome.storage.session.get(["sessionToken", "inviteKey"]);
      const token = sessionToken || inviteKey;
      if (!token) throw new Error("Open the MailScribe extension to sign in.");
      const response = await fetch(MAILPOLISH_API_URL + "/rewrite", {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: "Bearer " + token },
        body: JSON.stringify({ text, mode })
      });
      if (response.status === 401 && sessionToken) await chrome.storage.session.remove("sessionToken");
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "API error " + response.status);
      sendResponse({ rewritten: data.rewritten });
    } catch (error) {
      sendResponse({ error: error.message || "Rewrite failed" });
    }
  })();
  return true;
});

const hex = bytes => Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
let signingIn = false;

async function googleSignIn() {
  if (signingIn) return;
  signingIn = true;
  try {
    await chrome.storage.session.remove("signInError");
    const verifier = hex(crypto.getRandomValues(new Uint8Array(32)));
    const challenge = hex(new Uint8Array(await crypto.subtle.digest(
      "SHA-256", new TextEncoder().encode(verifier)
    )));
    const redirect = chrome.identity.getRedirectURL("google");
    const result = await chrome.identity.launchWebAuthFlow({
      url: MAILPOLISH_API_URL + "/auth/google/start?challenge=" + challenge,
      interactive: true
    });
    if (!result || !result.startsWith(redirect + "#")) throw new Error("Google sign-in was interrupted.");
    const params = new URLSearchParams(new URL(result).hash.slice(1));
    if (params.get("error") === "not_invited") throw new Error("This Google account hasn’t been invited.");
    const ticket = params.get("ticket");
    if (!ticket) throw new Error("Google sign-in didn’t finish. Try again.");
    const response = await fetch(MAILPOLISH_API_URL + "/auth/google/exchange", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ticket, verifier })
    });
    if (!response.ok) throw new Error("Google sign-in couldn’t be verified. Try again.");
    const { token } = await response.json();
    if (typeof token !== "string") throw new Error("Google sign-in returned no session.");
    await chrome.storage.session.remove(["inviteKey", "signInError"]);
    await chrome.storage.session.set({ sessionToken: token });
  } finally {
    signingIn = false;
  }
}
