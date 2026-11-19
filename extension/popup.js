const google = document.querySelector("#google-sign-in");
const form = document.querySelector("#sign-in");
const existingInvite = document.querySelector("#existing-invite");
const invite = document.querySelector("#invite");
const submit = form.querySelector("button");
const signOut = document.querySelector("#sign-out");
const status = document.querySelector("#status");

function showSession(signedIn) {
  existingInvite.hidden = signedIn;
  google.hidden = signedIn;
  signOut.hidden = !signedIn;
  status.textContent = signedIn ? "Signed in" : "";
}

google.addEventListener("click", async () => {
  status.textContent = "Continue in the Google sign-in window.";
  try {
    await chrome.runtime.sendMessage({ type: "MAILSCRIBE_GOOGLE_SIGN_IN" });
  } catch {
    status.textContent = "Couldn’t open Google sign-in. Try again.";
  }
});

form.addEventListener("submit", async event => {
  event.preventDefault();
  const inviteKey = invite.value.trim();
  submit.disabled = true;
  status.textContent = "Signing in…";
  try {
    const response = await fetch(MAILPOLISH_API_URL + "/session", {
      headers: { Authorization: "Bearer " + inviteKey }
    });
    if (response.status === 401) throw new Error("Invalid or revoked invite key.");
    if (!response.ok) throw new Error("MailScribe is temporarily unavailable.");
    await chrome.storage.session.set({ inviteKey });
    form.reset();
    showSession(true);
  } catch (error) {
    status.textContent = error.message;
  } finally {
    submit.disabled = false;
  }
});

signOut.addEventListener("click", async () => {
  await chrome.storage.session.remove(["inviteKey", "sessionToken", "signInError"]);
  showSession(false);
});

async function refreshSession() {
  const { inviteKey, sessionToken, signInError } = await chrome.storage.session.get(
    ["inviteKey", "sessionToken", "signInError"]
  );
  showSession(Boolean(inviteKey || sessionToken));
  if (signInError) status.textContent = signInError;
}

chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "session" && (changes.sessionToken || changes.signInError)) refreshSession();
});
refreshSession();
