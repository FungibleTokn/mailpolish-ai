const form = document.querySelector("#sign-in");
const invite = document.querySelector("#invite");
const submit = form.querySelector("button");
const signOut = document.querySelector("#sign-out");
const status = document.querySelector("#status");

function showSession(signedIn) {
  form.hidden = signedIn;
  signOut.hidden = !signedIn;
  status.textContent = signedIn ? "Signed in" : "";
}

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
    if (!response.ok) throw new Error("MailPolish is temporarily unavailable.");
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
  await chrome.storage.session.remove("inviteKey");
  showSession(false);
});

chrome.storage.session.get("inviteKey").then(({ inviteKey }) => showSession(Boolean(inviteKey)));
