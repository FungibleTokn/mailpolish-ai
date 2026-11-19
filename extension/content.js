(() => {
  const MODES = [["professional", "Professional"], ["shorten", "Shorten"], ["grammar", "Fix grammar"], ["diplomatic", "Diplomatic"]];
  const readText = editor => editor.innerText.trim();

  function replaceText(editor, text) {
    editor.focus();
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(editor);
    selection.removeAllRanges();
    selection.addRange(range);
    // Chrome's insertText command often preserves Gmail's undo and change tracking.
    if (!document.execCommand("insertText", false, text)) {
      throw new Error("Gmail did not accept the replacement. Use Copy instead.");
    }
  }

  function mount(editor) {
    if (editor.dataset.mailpolishMounted) return;
    editor.dataset.mailpolishMounted = "1";
    const toolbar = document.createElement("div");
    toolbar.className = "mp-toolbar";
    const status = document.createElement("span");
    status.className = "mp-status";
    status.textContent = "MailScribe";
    toolbar.append(status);

    const preview = document.createElement("div");
    preview.className = "mp-preview";
    preview.hidden = true;
    const controls = document.createElement("div");
    controls.className = "mp-preview-actions";
    controls.hidden = true;
    const accept = document.createElement("button");
    accept.textContent = "Replace draft";
    const copy = document.createElement("button");
    copy.textContent = "Copy";
    const cancel = document.createElement("button");
    cancel.textContent = "Dismiss";
    controls.append(accept, copy, cancel);
    let suggestion = "";
    let sourceText = "";

    for (const [mode, label] of MODES) {
      const button = document.createElement("button");
      button.textContent = label;
      button.type = "button";
      button.addEventListener("click", () => {
        const text = readText(editor);
        if (!text) { status.textContent = "Write a draft first"; return; }
        sourceText = text;
        status.textContent = "Rewriting…";
        button.disabled = true;
        chrome.runtime.sendMessage({ type: "MAILPOLISH_REWRITE", payload: { text, mode } }, response => {
          button.disabled = false;
          if (chrome.runtime.lastError) {
            status.textContent = "Connection error: " + chrome.runtime.lastError.message;
            return;
          }
          if (response?.error || typeof response?.rewritten !== "string") {
            status.textContent = "Error: " + (response?.error || "Invalid response");
            return;
          }
          suggestion = response.rewritten;
          preview.textContent = suggestion;
          preview.hidden = false;
          controls.hidden = false;
          status.textContent = "Review suggestion";
        });
      });
      toolbar.append(button);
    }

    accept.addEventListener("click", () => {
      if (readText(editor) !== sourceText) {
        status.textContent = "Draft changed since rewrite. Generate a new suggestion.";
        return;
      }
      try {
        replaceText(editor, suggestion);
        preview.hidden = true;
        controls.hidden = true;
        status.textContent = "Draft replaced — review before sending";
      } catch (error) { status.textContent = error.message; }
    });
    copy.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(suggestion); status.textContent = "Copied"; }
      catch { status.textContent = "Copy failed"; }
    });
    cancel.addEventListener("click", () => {
      preview.hidden = true;
      controls.hidden = true;
      status.textContent = "MailScribe";
    });

    editor.parentElement.insertBefore(toolbar, editor);
    toolbar.after(preview, controls);
  }

  function scan() {
    document.querySelectorAll('[role="textbox"][contenteditable="true"]').forEach(editor => {
      const label = (editor.getAttribute("aria-label") || "").toLowerCase();
      if (label.includes("message body") || editor.getAttribute("g_editable") === "true") mount(editor);
    });
  }
  new MutationObserver(scan).observe(document.documentElement, { childList: true, subtree: true });
  scan();
})();
