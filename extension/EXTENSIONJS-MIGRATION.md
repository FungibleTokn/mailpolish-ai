# MailScribe: Extension.js cross-browser proof of concept

This branch experiments with [Extension.js](https://extension.js.org/) without changing the existing Railway backend or merging changes into `main`.

## Requirements

- Node.js **22.12+** (Extension.js 4.x).
- Existing MailScribe beta invite key and Railway backend.
- macOS and Xcode for Safari builds.

## Build

```sh
cd extension
npm install
npm run build:chrome
npm run build:edge
npm run build:firefox
```

Output is generated in `extension/dist/<browser>`. Use `npm run package:chrome` to produce a distributable Chrome ZIP. Do not commit `dist/` or `node_modules/`.

## Critical compatibility checks

1. Verify the build includes `api-config.js`, and that `background.js` can load it through `importScripts`. If bundling inlines or renames scripts, refactor to explicit ES imports and set a compatible service-worker format before merging.
2. Verify `popup.html` loads `api-config.js` and `popup.js` in order.
3. Verify `styles.css` loads in Gmail and the toolbar appears exactly once per compose editor.
4. Verify `chrome.storage.session` works for the beta invite-key sign-in flow in each target browser.
5. Test `/session` authentication and `/rewrite` against the existing Railway API with **dummy emails only**.
6. Confirm a rewritten draft is only replaced after explicit approval and that no message is sent.
7. Inspect browser-specific manifest permissions and packaged artifacts; validate Firefox messaging, CSP and background lifecycle.
8. Run backend tests and Chrome regression tests before merging.

## Deployment

The FastAPI backend is unchanged. The browser extension's beta access model and API URL remain as they are. **Do not put OpenAI keys, Railway environment secrets or plaintext tester invite keys in the extension.**

## Status

Build scripts are added for evaluation, but browser builds and Gmail end-to-end behavior have **not yet been validated**. Do not publish these artifacts or merge this branch until the checks above pass.
