---
name: diff-flow-match
description: This skill should be used when the user asks to "diff flows", "compare my clone to the source", "run a match-matrix", "verify flow parity", "check if my clone matches the original flow", "replay against the target", or "does my clone pass the flow spec". Takes a source-app flow JSON produced by record_flow.py, replays the same conceptual sequence against a target URL (e.g. the clone), and produces a match-matrix.md per-step comparison.
version: 0.1.0
---

# Diff flow match — source vs clone flow comparison

Complements `/manual-qa`. Where `/manual-qa` spec-builds and drives a clone from scratch, this skill takes a pre-recorded source-app flow and verifies that the clone executes the same conceptual sequence in the same order with the same kind of state change.

Use after recording a source-app flow with `scripts/record_flow.py --record` and building the clone. Run this before calling the clone done.

## Rule

**Same conceptual button sequence in same order produces the same kind of state change.**

"Conceptual" means the underlying action, not the label. Source says "Continue"; clone says "Next". Both advance to step 2. That's a PASS. Source advances to step 2; clone shows an error toast. That's a FAIL.

PARTIAL: the action is available but position differs or side-effects differ. Documentable, not a hard fail.

---

## Policy — read clone-config.json before starting

Before any stage runs, resolve the effective `clone-config.json` per `docs/clone-config.md`. The fields this skill reads:

- `target_parity` — minimum PASS fraction to declare "done" (default 1.0).
- `max_fix_iterations` — hard cap on the Stage 6 convergence loop (default 5).
- `partials_allowed` — PARTIAL rows tolerated at "done" (default 0).
- `blocked_requires_evidence` — whether BLOCKED rows without concrete env reason are demoted to FAIL (default true).
- `allow_plan_mode` — passed into any fixer subagent dispatched in Stage 6 (default false → subagent must NOT EnterPlanMode).
- `no_inventions` — if true (default), clone routes that don't map to a source route are auto-FAIL (run in Stage 5 before scoring).

Resolve once at skill start:

```bash
CLONE_CONFIG=$(
  for candidate in \
    "clones/${DOMAIN}/clone-config.json" \
    "${HOME}/.claude/clone-config.json" \
    "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/clone-config.default.json"; do
    [ -f "$candidate" ] && cat "$candidate" && break
  done
)
```

Do not ask the user about any of these values. The config is the contract. Only ask if the config is missing or unparseable.

---

## Pipeline — 6 stages

```
Record source flow  →  Translate semantics  →  Replay target  →  Diff per-step  →  Report  →  Converge (loop)
```

Stages 1–5 are unchanged from v0.1. Stage 6 is the new convergence loop that turns a one-shot report into a "fix until target_parity or hard-BLOCKED" process.

### Stage 1: Record source flow

If a source flow JSON doesn't exist yet:

```bash
python3 scripts/record_flow.py --record \
    --name {flow-name} \
    --start-url https://app.source.com/... \
    --cookies clones/{source-domain}/cookies.json \
    --description "One-line description of what this flow tests"
```

Output: `flows/{flow-name}.json` — the canonical spec.

Do not edit the spec manually unless correcting a mis-captured selector. The recorder captures what happened; manual edits should only add `note` fields or fix obviously wrong selectors.

### Stage 2: Translate to target semantics

The source spec uses the source app's accessible names. The clone uses its own labels. Build a label map JSON:

```json
{
  "Continue": "Next",
  "Generate Video": "Create",
  "Upload media": "Add files",
  "Describe your video...": "What do you want to create?"
}
```

Pass via `--label-map path/to/label-map.json` in Stage 3. Any step whose source `selector.name` matches a key gets the value substituted when resolving the locator on the target.

If labels match exactly (clone uses same copy), no label map needed.

A label map is a living file: update it as you discover mismatches during replay.

### Stage 3: Replay against target

```bash
python3 scripts/record_flow.py --playback \
    --spec flows/{flow-name}.json \
    --target-url https://localhost:3000 \
    --cookies clones/{clone-domain}/cookies.json \
    --out flows/reports/{flow-name}-clone-report.json
```

The playback produces a JSON report with per-step PASS/FAIL/SKIP and screenshot paths.

For the label-map translation: if the target uses different labels, edit the spec's `selector.name` values for the clone replay (keep the original spec untouched — duplicate it as `{flow-name}-clone.json`). Or use the label-map preprocessing step below before playback.

Label map preprocessing (optional helper):
```bash
python3 -c "
import json, sys
spec = json.load(open('flows/{flow-name}.json'))
lmap = json.load(open('flows/label-maps/{target}.json'))
for step in spec['steps']:
    sel = step.get('selector') or {}
    if sel.get('name') in lmap:
        sel['name'] = lmap[sel['name']]
json.dump(spec, open('flows/{flow-name}-clone.json','w'), indent=2)
print('Translated spec written')
"
```

### Stage 4: Diff per-step

Load both reports (source playback report + clone playback report) and compare step by step.

For each step:
- **PASS**: both reports show PASS for the step index. Observable (state change, navigation, value) matches.
- **FAIL**: source PASS but clone FAIL. The flow diverges here; the clone is broken at this step.
- **PARTIAL**: both pass but evidence differs — different final URL, different toast message, different side-effect observable. Note it; do not auto-fail.
- **SKIP**: step was skipped in source or clone. Investigate why before declaring.

When source doesn't have a recorded playback report (you only have the flow JSON, not an automated source replay): use screenshot evidence from the original recording session or the editor-observations reference doc as the source ground truth.

### Stage 4.5: No-inventions route audit

Run this before scoring in Stage 5 iff `no_inventions` is true in clone-config.

1. Extract the source's **surface inventory** — the route table at the top of `flows-audit.md` mapping each source URL to its clone-equivalent target URL.
2. List the clone's actual routes. For Next.js App Router: parse the output of `npm run build` for the `Route (app)` block. For Vite + React Router: parse the router config. For static: list `index.html` files.
3. For each clone route, confirm it maps to a source route (or is a documented redirect shim, e.g. `/projects` → `/app`).
4. Any clone route without a source mapping is an **invention** — add an auto-FAIL row to the matrix with the fix ticket "remove or justify this route."

Rationale: inventions drift the clone from the source and hide regressions. Common example: a `/welcome` onboarding route in the clone that doesn't exist in the source. A subagent might charitably map it to "post-login first step," but if the source goes directly from login to the dashboard, the extra step is a structural divergence. Enforcing this audit catches inventions on iteration 0.

### Stage 5: Report — match-matrix.md

Write `clones/{domain}/match-matrix.md`:

```markdown
# Flow match matrix — {flow-name} — {timestamp}

**Score:** {pass}/{total} steps match ({percent}%).

**Source:** {source-start-url}
**Target:** {target-url}
**Spec:** flows/{flow-name}.json

## Match matrix

| # | Step type | Source action | Target action | Source screenshot | Target screenshot | Result |
|---|-----------|---------------|---------------|-------------------|-------------------|--------|
| 0 | navigate  | /projects     | /             | —                 | step-000-nav.png  | PASS   |
| 1 | click     | "Continue"    | "Next"        | src-001.png       | step-001-click.png| PASS   |
| 2 | fill      | Email textbox | Email textbox | src-002.png       | step-002-fill.png | PASS   |
| 3 | click     | "Generate Video"| "Create"    | src-003.png       | step-003-click.png| PARTIAL|

## PARTIAL details

| # | Why PARTIAL | Impact |
|---|-------------|--------|
| 3 | Modal appears after "Create" in clone but not in source — extra confirmation step | Low — user still reaches same end state |

## Failures

(Full detail per FAIL: step, source observable, target observable, screenshot comparison, fix suggestion)

## Next steps

- Fix: [step index] — [what to fix]
- Rerun: `python3 scripts/record_flow.py --playback --spec flows/{flow-name}-clone.json ...`
```

---

### Stage 6: Convergence loop

Turn the one-shot report into a fix-until-done process. Runs after Stage 5 writes the initial `match-matrix.md`. Respects the clone-config fields loaded at skill start.

**Exit conditions (checked at the top of each iteration):**

- `score >= target_parity` AND `partials_count <= partials_allowed` AND every remaining non-PASS is a BLOCKED row that passes `blocked_requires_evidence` → **done**. Stop the loop, leave the matrix at its current state.
- `iteration >= max_fix_iterations` → **not-converged**. Stop. The final matrix is the handoff to a human. Write a `NOT-CONVERGED` banner at the top of `match-matrix.md` listing the still-FAILing rows.
- Every non-PASS row is already a validated BLOCKED → same as "done" above.

**Per-iteration steps (else):**

1. **Collect tickets.** Walk the matrix; every FAIL and PARTIAL row becomes a ticket:
   - `flow_number`, `flow_name`
   - `source_observable` — from reference screenshots or source-flow JSON
   - `target_observable` — from this iteration's playback report
   - `probable_files` — grep the clone's source for route-matching filenames (e.g. FAIL on Flow 14 → grep for `Upgrade`, `upgrade`, `pricing`, `plan` under `clones/{domain}/{template}/src/`)
   - `fix_hint` — the rebuild note from `flows-audit.md` for that flow
2. **Snapshot the iteration.** Copy the current `match-matrix.md` to `clones/{domain}/matrix-history/iter-{n}.md` so convergence is auditable.
3. **Dispatch one fixer subagent** (Agent tool, `general-purpose`). Prompt template:

   ```
   DIRECT EXECUTION MODE — do NOT call EnterPlanMode. Do NOT ask for approval.
   [per clone-config allow_plan_mode={value}]

   You are the fixer subagent in Stage 6 of /diff-flow-match.

   Scope (the ONLY files you may edit): {clones/{domain}/{template}/**}
   Do NOT create new routes/screens/flows. `no_inventions={value}` means any
   route you add that isn't already in the source flow audit will FAIL on the
   next iteration.

   Fix tickets (resolve all):
   [list of tickets from step 1]

   For each ticket:
   - Read the probable file(s).
   - Make the minimum change to match the source observable.
   - If the fix requires touching a file outside scope, STOP and report the
     ticket as BLOCKED with the reason; do not overreach.

   When all tickets are addressed:
   - Run the clone's build command ({build_cmd from clone-config or package.json})
   - Report which tickets are resolved and which became BLOCKED.
   ```

4. **Wait for fixer completion.** Check fixer's report; record resolved/blocked.
5. **Rebuild the clone** if the fixer's build step failed or was skipped.
6. **Re-run Stages 3–5** (replay + diff + report). This overwrites `match-matrix.md` with iteration `{n+1}`'s results.
7. **Loop back to top of Stage 6.** Increment iteration counter.

**Dry-run / already-done fast path:** if Stage 5 already wrote a matrix with score == target_parity on iteration 0, Stage 6 exits immediately. No fixer dispatched, no wasted tool calls.

**Auditability:** after convergence (or non-convergence), `clones/{domain}/matrix-history/` contains one file per iteration. Reading them in order reproduces the fix sequence. Useful for retros and for `docs/learnings.md` updates.

---

## Semantic-selector translation

Source apps and clone apps use different copy. The selector translation layer prevents false FAILs from label differences.

### Priority of translation

1. `role + name` is translated via label map.
2. If no match in label map: try `role` only (first matching element of that role).
3. If still no match: fall back to `text`, `id`, `data_attr`, `css` in that order.
4. If nothing resolves: FAIL the step with error "selector not found — add to label map".

### Label map format

```json
{
  "source label": "target label",
  "Continue": "Next",
  "Upload media": "Add files",
  "Generate Video": "Create",
  "Describe your video...": "What do you want to make?"
}
```

Store at `flows/label-maps/{target-domain}.json`. One file per target. Reuse across flows for the same target.

### When labels differ but roles differ too

If source uses `role=button name="Continue"` and clone uses a different role (e.g. a `link` styled as button): add both `role` and `name` to the label map as a structured override:

```json
{
  "__override:Continue": { "role": "link", "name": "Next" }
}
```

The preprocessing step checks for `__override:` prefix keys and applies the full selector replacement.

---

## When to use PARTIAL

PARTIAL = same action available, conceptually same outcome, but some observable differs.

Use PARTIAL when:
- Button position changed (was in toolbar, now in sidebar). User can still find it.
- Different toast message text (same action, different copy).
- Extra confirmation step in clone (modal before final action). End state still reached.
- Slightly different URL after navigation (path differs, same page content).

Do NOT use PARTIAL when:
- Step is missing entirely in clone (no button, no action). That is FAIL.
- Clone navigates to wrong page. That is FAIL.
- State change is wrong (clip not added to timeline, form not submitted). That is FAIL.

Document every PARTIAL with "Impact" field — let the user decide if it's acceptable.

---

## Integration with /manual-qa

These two skills are complementary, not redundant.

| `/manual-qa` | `/diff-flow-match` |
|---|---|
| No pre-recorded spec needed | Requires a source flow JSON |
| You write the spec based on expected behavior | Spec is captured from live source app |
| Good for first-pass QA of a clone | Good for regression: "does this still match source?" |
| Reports PASS/FAIL per behavior description | Reports PASS/FAIL per step in the original source flow |
| Drives clone only | Drives source + clone, diffs them |

Typical use order:
1. Run `/manual-qa` during active development — fast feedback, spec-driven.
2. Run `/diff-flow-match` before declaring the clone done — confirm the full source flow still plays correctly against the clone.

Both must pass before calling the clone complete.

---

## Reference files

- `scripts/record_flow.py` — flow recorder and player. Source of the spec JSON.
- `skills/diff-flow-match/references/replay-patterns.md` — edge case recipes (auth-required flows, modals, async, wizards).
- `skills/manual-qa/SKILL.md` — sibling skill for spec-free interactive QA.
- `docs/patterns/modern-saas-editor.md` — IA skeleton; use to anticipate which flows exist before recording.
