---
name: manual-qa
description: This skill should be used when the user asks to "test the editor", "QA the clone interactively", "drive the SPA", "run functional QA", "check the cloned app works", "smoke-test the clone", or whenever a cloned interactive app (editor, dashboard, SPA) needs functional end-to-end verification beyond pixel comparison. Drives the app with Playwright, exercises every wired feature, captures console errors and network activity, and reports pass/fail per behavior with before/after screenshots. I run these tests myself and never ask the user to hand-test.
version: 0.1.0
---

# Manual (interactive) QA for cloned apps

Complements the `/qa` skill. Where `/qa` measures pixel similarity of static pages, this skill validates that interactive features of a cloned app actually work — clicks, uploads, state changes, persistence, API calls, error paths.

Trigger when any of these are true:
- The clone is a SPA or dashboard (not just marketing pages).
- The output is a framework template (React, Next.js, Vue) where behavior matters.
- A visual diff can't catch the bug (e.g. "button renders but doesn't do anything").
- The user asks "does it work?", "test it yourself", "check the flows", "make sure it's 99% matching".

## Rule: I test, not the user

The user does not hand-test. I drive the app via Playwright until I can report on every advertised behavior with evidence (screenshots + network logs + state snapshots). Only then do I report completion. If a flow is genuinely untestable from my environment (real OAuth, paid features, external device), I say so explicitly rather than imply it passes.

## Pipeline (six stages)

```
Spec -> Fixtures -> Drive -> Verify -> Report -> Fix-or-ship
```

### Stage 1: Write the behavior spec

Before driving anything, write `clones/{domain}/manual-qa-spec.md` listing every user-facing behavior to verify. Each behavior is one line: action + expected observable.

Good spec entries:
- "Click 'Upload media' opens the file picker."
- "Upload a 5s mp4 adds it to the library with duration '5.0s'."
- "Click '+ Clip' on a media item pushes it to the timeline at timelineStart=0."
- "Click 'Split' at playhead=2.5 produces two clips: [0-2.5] and [2.5-5]."
- "Click 'Transcribe audio' with no selection shows a 'Select a clip first' toast and makes zero network requests."
- "Click 'Transcribe audio' with a selection POSTs /api/ai/transcribe."
- "Reload preserves clips, texts, assets, and duration."

Bad spec entries (too vague):
- "Editor works."
- "Timeline is interactive."
- "Save button functions."

If you can't describe the observable, you can't verify it. Spec first.

### Stage 2: Prepare fixtures

Any flow that needs a file, auth token, or preset state gets a fixture saved under `scripts/test-fixtures/`. For video editors:

```bash
# 5 second test video with audio (reproducible, 546KB)
ffmpeg -y -f lavfi -i testsrc2=size=640x360:duration=5:rate=30 \
  -f lavfi -i sine=frequency=440:duration=5 \
  -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest \
  scripts/test-fixtures/test-5s.mp4
```

Fixtures must be checked in (not gitignored) so tests are reproducible across machines. Keep them small — a 5-second 360p clip is plenty for timeline testing.

### Stage 3: Drive the app with Playwright MCP

Use the Playwright MCP tool set: `browser_navigate`, `browser_snapshot`, `browser_click`, `browser_file_upload`, `browser_evaluate`, `browser_console_messages`, `browser_network_requests`, `browser_take_screenshot`.

Do NOT use Python headless Playwright for this — that's the `/qa` skill's domain. The MCP browser stays open across steps and lets you drive multi-step flows naturally.

A canonical drive loop for each spec entry:

1. `browser_snapshot` — get current accessibility tree, find the ref for the element to interact with.
2. `browser_click` / `browser_file_upload` / other action — perform the action.
3. `browser_wait_for { time: 1 }` if the action triggers async work (probe, network, animation).
4. `browser_evaluate` — read DOM/localStorage/IndexedDB state to verify expected outcome.
5. `browser_network_requests { filter: "/api/" }` — verify any expected/unexpected API call.
6. `browser_console_messages { level: "error" }` — confirm no unexpected errors.
7. `browser_take_screenshot` — save evidence with a named filename.

Tip: `browser_evaluate` rejects TypeScript annotations. Strip `as unknown as X` and interface generics — use plain JS in the evaluated function.

### Stage 4: Verify against the spec

For each spec entry, assign one of three outcomes:
- **PASS**: action performed, observable matched exactly, no unexpected console errors, expected network call made.
- **FAIL**: observable differed, or unexpected console error fired, or network call missed/duplicated.
- **BLOCKED**: can't test in the current environment (e.g. needs real OAuth, needs a paid account, needs a device feature).

Always include evidence. "Looks good" is not a verification result.

### Stage 5: Generate the report

Write `clones/{domain}/manual-qa-report.md` with this structure:

```markdown
# Manual QA report — {domain} — {timestamp}

**Score:** {pass}/{total} passing ({percent}%).

## Summary
- Passing: {pass}
- Failing: {fail}
- Blocked: {blocked}

## Results
| # | Behavior | Result | Evidence |
|---|----------|--------|----------|
| 1 | Upload adds media to library | PASS | clone-02-upload.png, localStorage state |
| 2 | Split at playhead produces two clips | PASS | clone-03-split.png, clips=[{0-2.5},{2.5-5}] |
| 3 | Reload preserves state | PASS | clone-05-reload.png, IDB rehydration confirmed |
| 4 | Audio unmute plays sound | BLOCKED | Headless Chrome disables audio output |

## Failures
(full detail for each FAIL: spec, observed, expected, screenshot, relevant console/network lines)

## Blocked
(one line each: what couldn't be tested and why)

## Fix priority
(if any failures: list in priority order for follow-up)
```

### Stage 6: Fix or ship

If any spec entry is FAIL: loop back to the code, apply fixes, re-drive the failing entries only. Do not declare done until:
- All critical (user-facing path) entries PASS.
- All BLOCKED entries are documented with a reason the user can accept.
- The report is written and saved.

## Common observable patterns

For a video editor clone (typical target), these are the observable categories worth explicit spec entries:

### Persistence
- Project index in `localStorage['{app}:project-index']` contains the active project (substitute your clone's namespace — common convention: the app's short name as the key prefix).
- Full project state in `localStorage['{app}:project:{id}']` round-trips across reload.
- Asset blobs in IndexedDB (database named after your app, store `assets`) contain the File for each asset.
- After reload, `asset.url` is rehydrated from IDB (new `blob:` URL, not the stale one).

### Timeline state
- Adding a clip increases `state.clips.length` by 1 and sets `selectedClipId`.
- Split at playhead inside clip C yields two clips whose `timelineStart` values partition C's range.
- Deleting selected clip sets `selectedClipId` to `null`.
- Reordering clips on the same track recomputes `timelineStart` in order.

### Preview playback
- Clicking Play sets `isPlaying=true` and calls `video.play()`.
- If video has audio, the fallback path sets `video.muted=true` when the first play is rejected.
- Playhead advances at real-time rate (cap 0.1s per frame so background-tab resume doesn't jump).
- When a video is active, playhead reads from `video.currentTime` — this is drift-free.
- Reaching duration sets `isPlaying=false` and stops the rAF loop.

### API hooks
- Each AI button POSTs to `/api/ai/{feature}`; response `status==="backend-todo"` confirms the stub is wired.
- Export POSTs `/api/render` with the full project payload.
- A guard ("Select a clip first") fires toast + makes zero network requests when no clip is selected.

### Toasts
- Toasts render in a `fixed bottom-4 right-4` container.
- Each toast auto-dismisses after ~3.5s — capture with `browser_evaluate` inside that window, or use `browser_take_screenshot` immediately after the triggering action.

## Known environmental quirks

- **Headless Chrome video playback**: often runs at non-realtime rate or fast-forwards. Don't fail a test because `currentTime` reached end faster than wall-clock; the logic is correct.
- **Audio autoplay**: blocked unless muted. Our fallback mutes on rejection — test that `video.muted` becomes `true` after Play.
- **Blob URL lifetime**: blob URLs don't survive reload. IndexedDB asset persistence is the fix; test both paths (first-load-after-import AND after-reload).
- **localStorage quota**: ~5-10MB per origin. Projects with many text overlays are fine. Don't store asset bytes in localStorage — use IDB.
- **Playwright's `browser_evaluate`**: serializer rejects TS annotations. Strip `as X`, generic types, and interface decls from the evaluated function body.

## Integration with the pipeline

When `/clone` produces a framework template that's an interactive app (editor, dashboard, admin):

1. `/qa` runs first for visual fidelity of the rendered shell.
2. `/manual-qa` runs second for interactive behavior.
3. Only if BOTH pass should the clone be declared complete.

Visual at 99% + functional PASS on every advertised feature = the bar.
Either one below target = more work before declaring done.

## Reference files

- `${CLAUDE_PLUGIN_ROOT}/skills/qa/SKILL.md` — sibling skill for pixel similarity.
- `${CLAUDE_PLUGIN_ROOT}/skills/manual-qa/references/playwright-recipes.md` — copy-paste evaluate functions for common checks.
- `${CLAUDE_PLUGIN_ROOT}/scripts/test-fixtures/` — reusable test media and data.
