# Replay patterns — edge case recipes

Common situations where naive step-by-step replay breaks, and how to handle each.

---

## 1. Auth-required flows

**Problem:** playback navigates to a protected URL and lands on the login page instead of the expected state. Every subsequent step fails because the DOM is wrong.

**Symptoms in report:** Step 0 (navigate) may PASS (it did navigate), but step 1 (click some app element) FAILs with "selector not found" because the login page doesn't have that element.

**Recipe:**

1. Pass `--cookies` with a valid session cookie JSON from `import_browser_cookies.py`.
2. Before running playback, verify the cookie is still valid:
   ```bash
   python3 -c "
   import json, time
   cookies = json.load(open('clones/target.com/cookies.json'))
   now = time.time()
   session = [c for c in cookies if 'session' in c['name'].lower()]
   for c in session:
       exp = c.get('expires', -1)
       if exp > 0 and exp < now:
           print('EXPIRED:', c['name'], c['domain'])
       else:
           print('OK:', c['name'], c['domain'])
   "
   ```
3. If expired: re-run `import_browser_cookies.py` after the user refreshes their session in Chrome.
4. If the target requires an initial page load + redirect before the cookie is recognized: add a `wait-for` step with `timeout_ms: 3000` after the navigate step in the spec.

**Spec pattern:**
```json
{ "type": "navigate", "url": "https://app.target.com/projects" },
{ "type": "wait-for", "timeout_ms": 3000, "note": "Wait for auth redirect to settle" },
{ "type": "screenshot", "note": "Verify we land on projects, not login" }
```

---

## 2. Modal-triggering actions

**Problem:** a click opens a modal dialog. The next step tries to interact with something in the modal. If the modal uses a portal (renders outside the DOM parent), `page.locator` may not find it.

**Symptoms:** step after the click FAILs with "selector not found" even though the modal is visually present.

**Recipe:**

1. After the click step, add a `wait-for` step targeting an element inside the modal:
   ```json
   { "type": "click", "selector": { "role": "button", "name": "Export" } },
   { "type": "wait-for", "selector": { "role": "dialog" }, "timeout_ms": 5000 },
   { "type": "screenshot", "note": "Modal should be open" }
   ```
2. Use `role: "dialog"` or `role: "alertdialog"` as the wait-for selector — portals still get proper ARIA roles.
3. If the modal has a close button, always add a step to close it at the end of the sub-flow. Otherwise the next step navigates away with the modal open, causing a `beforeunload` confirmation.

**Handling beforeunload prompts:**
```json
{ "type": "press", "value": "Enter", "note": "Confirm beforeunload dialog if triggered" }
```
Add this step after any navigation away from a page that registers a `beforeunload` handler (common on creation tool landing pages mid-flow).

---

## 3. Async-result flows (AI generation, file upload processing)

**Problem:** a click triggers a server-side job (AI generation, transcription, export). The result appears after a variable delay (2-30s). The next step expects the result to be present, but the poll hasn't resolved yet.

**Symptoms:** step after the trigger click FAILs immediately because the result element doesn't exist yet.

**Recipe:**

1. After the trigger step, add a `wait-for` step with a generous timeout targeting the result element (a progress bar disappearing, a result card appearing, a "Done" status badge):
   ```json
   { "type": "click", "selector": { "role": "button", "name": "Generate" } },
   { "type": "wait-for", "selector": { "role": "status", "name": "Done" }, "timeout_ms": 60000, "note": "Wait for generation to complete" },
   { "type": "screenshot", "note": "Capture generated result" }
   ```
2. For uploads specifically: wait for the thumbnail to appear in the media grid.
   ```json
   { "type": "upload", "selector": { "role": "textbox" }, "files": ["scripts/test-fixtures/test-5s.mp4"] },
   { "type": "wait-for", "timeout_ms": 10000, "note": "Wait for upload processing" }
   ```
3. If the result is polled via WebSocket or SSE and the step is FAIL in playback but PASS in manual observation: check `browser_network_requests` for the WebSocket connection — the clone may not have the WS endpoint stubbed.

---

## 4. Multi-step wizards

**Problem:** a funnel flow (prompt → customize → confirm) has 2-3 steps at different URLs or modal states. Each step's elements only exist during that step. Recording captures them correctly, but playback fails if a step transition is slow (animate-in) or if the URL doesn't change (pure state machine wizard).

**Symptoms:** step N passes (click Continue), step N+1 fails immediately (elements from step N+1 not yet rendered).

**Recipe:**

1. After each advancing CTA click, add a `wait-for` that targets a unique element on the NEXT step:
   ```json
   { "type": "click", "selector": { "role": "button", "name": "Continue" } },
   { "type": "wait-for", "selector": { "role": "heading", "name": "Choose your style" }, "timeout_ms": 5000 },
   { "type": "screenshot", "note": "Step 2 loaded" }
   ```
2. For URL-changing wizards: after navigate, use `wait-for` with `timeout_ms: 3000` and no selector (pure time delay) if the URL change is slow to settle.
3. For `Back` button flows: always record the Back navigation as a step. It's easy to miss and often the only way to test the Back path.

**Progress bar verification:**
If the wizard has a progress bar, add a `browser_evaluate` assertion after each step (not supported directly in record_flow.py, but add as a note in the spec for manual-qa follow-up):
```json
{ "type": "screenshot", "note": "Progress bar should show step 2 of 3 here" }
```

---

## 5. Hover-only UI elements

**Problem:** some actions only appear on hover (three-dot menu on project cards, inline edit buttons). The recorder captures the click, but the element isn't visible without a preceding hover.

**Symptoms:** playback FAIL on the click step because the element has `display:none` or `visibility:hidden` until hovered.

**Recipe:**

There is no `hover` step type in `record_flow.py` by default. Two options:

**Option A: Use CSS selector targeting the hidden element directly** (bypasses visibility check):
```json
{
  "type": "click",
  "selector": { "css": ".project-card:first-child [data-testid='card-menu']" },
  "note": "Three-dot menu — may need hover first"
}
```

**Option B: Add a hover step** before the click. In the spec JSON, add:
```json
{ "type": "wait-for", "timeout_ms": 500, "note": "Hover over card to reveal menu" },
{ "type": "click", "selector": { "css": ".project-card:first-child" }, "note": "Hover target" }
```
Then the three-dot click follows. In playback, Playwright moves the mouse to the element on `click`, which triggers the CSS `:hover` state.

**Playwright behavior:** `loc.click()` moves the mouse to the element center before clicking. This IS enough to trigger CSS `:hover` on the element itself. It is NOT enough to trigger `:hover` on an ancestor (e.g. card hover reveals child button). For ancestor-triggered hover: click the ancestor first (which moves mouse to it), then immediately click the child.

---

## 6. Iframe-embedded content

**Problem:** part of the page is inside an `<iframe>` (e.g. embedded video player, payment widget). Playwright's default locator scope doesn't cross frame boundaries.

**Symptoms:** selector not found even though element is clearly visible.

**Recipe:**

Record-time: the recorder's injected JS runs in the main frame only. Interactions inside iframes are not captured automatically. After recording, manually add iframe-aware steps:

```json
{
  "type": "click",
  "selector": { "css": "iframe[name='player']" },
  "note": "Focus the iframe first"
},
{
  "type": "press",
  "value": "Space",
  "note": "Space to play/pause inside player iframe — keyboard event crosses frame"
}
```

For content inside iframes that requires direct interaction (form inputs in payment widget): this is generally not automatable via record_flow.py. Mark as BLOCKED in the match matrix and test manually.

---

## 7. Clipboard / download verification

**Problem:** a step triggers a download or writes to clipboard. Playwright can intercept downloads but `record_flow.py` doesn't capture them as steps.

**Recipe:**

Add a `screenshot` step immediately after the trigger click to capture the download toast or browser download bar (evidence that download was initiated). The download file itself is not verified — out of scope for flow matching.

For clipboard: use `browser_evaluate` in `/manual-qa` instead:
```js
navigator.clipboard.readText().then(t => console.log('clipboard:', t))
```

Note in match matrix: "clipboard content not diffed — screenshot evidence only".
