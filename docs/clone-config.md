# clone-config.json — framework-wide policy

One file tells every skill in the IllyCloneFramework pipeline how to behave when a choice is about policy, not judgment. If a clone is about to pause and ask "should I commit?" or "PARTIAL acceptable?" — check this file first. Only ask the human if the config doesn't cover it.

## Resolution order

First found wins:

1. `clones/{domain}/clone-config.json` — per-clone override. Use when a specific target needs looser or tighter policy (e.g. a clone where you want `partials_allowed: 2` because some flows are genuinely environment-blocked).
2. `~/.claude/clone-config.json` — user-global override. Gitignored by convention. Use for personal defaults that cross projects.
3. `${CLAUDE_PLUGIN_ROOT}/.claude-plugin/clone-config.default.json` — shipped with the plugin. Always exists.

## Reading the config from a skill

Skills should prescribe this inline so they stay portable (no shared helper module):

```bash
# Resolve effective config for the current clone. Put in CLONE_CONFIG.
CLONE_CONFIG=$(
  for candidate in \
    "clones/${DOMAIN}/clone-config.json" \
    "${HOME}/.claude/clone-config.json" \
    "${CLAUDE_PLUGIN_ROOT}/.claude-plugin/clone-config.default.json"; do
    [ -f "$candidate" ] && cat "$candidate" && break
  done
)

# Read a single field
TARGET_PARITY=$(echo "$CLONE_CONFIG" | jq -r '.target_parity')
AUTO_COMMIT=$(echo "$CLONE_CONFIG" | jq -r '.auto_commit')
ALLOW_PLAN_MODE=$(echo "$CLONE_CONFIG" | jq -r '.allow_plan_mode')
```

Skills that invoke subagents should forward the relevant fields verbatim in the subagent's prompt ("clone-config says allow_plan_mode=false; do not EnterPlanMode; do not ask for approval").

## Schema

| Field | Type | Default | Meaning |
|---|---|---|---|
| `target_parity` | number | 1.0 | Fraction of flow-match rows that must be PASS before `/diff-flow-match` exits. `1.0` = 100%. |
| `max_fix_iterations` | int | 5 | Hard cap on the Stage 6 convergence loop in `/diff-flow-match`. Prevents runaway. |
| `auto_commit` | bool | true | After each phase produces artifacts, commit to git without asking. Uses `commit_author_email`. |
| `auto_push_end` | bool | false | Push to remote at the very end of the pipeline. Default off — pushing is a conscious act. |
| `allow_plan_mode` | bool | false | If false, subagents dispatched by skills must NOT call EnterPlanMode. They execute directly. Prevents the "subagent froze in its own plan mode" failure. |
| `no_inventions` | bool | true | Clone must not have routes, screens, or flows that the source doesn't have. Extras are auto-FAIL in the match matrix. Rationale: structural parity is the contract; inventions drift from the source and hide regressions. |
| `partials_allowed` | int | 0 | How many PARTIAL rows the pipeline tolerates at "done". 0 means every PARTIAL becomes a Stage 6 fix ticket. |
| `blocked_requires_evidence` | bool | true | BLOCKED rows must cite a concrete environmental reason (e.g. "requires live Stripe session"). A BLOCKED row without evidence is treated as FAIL. |
| `commit_author_email` | string | — | Email used for automated commits. |
| `visual_firewall_enforced` | bool | true | After each fix iteration, grep clone output for source-specific strings/hex colors/font names from `visual-decisions.md`. Violations are reported. |

## Override example

`clones/example.com/clone-config.json`:

```json
{
  "partials_allowed": 1,
  "auto_push_end": true
}
```

Merged with defaults this means: tolerate 1 PARTIAL row at "done", auto-push at pipeline end. All other fields inherit from the default.

## When to change defaults

- **target_parity < 1.0**: rarely. Only if a site has genuinely unreachable flows (e.g. paywalled admin area) that can't be stubbed. Prefer using BLOCKED-with-evidence instead.
- **auto_commit false**: if you're actively exploring and don't want commit noise.
- **allow_plan_mode true**: if you want subagents to pause for plan approval on each step. Slower but more cautious.
- **no_inventions false**: if the clone is intentionally a superset of the source (e.g. adding an analytics dashboard on top). Rare.

## Which skills read this file

- `/clone` — `auto_commit`, `allow_plan_mode`
- `/diff-flow-match` — `target_parity`, `max_fix_iterations`, `partials_allowed`, `blocked_requires_evidence`, `allow_plan_mode`, `no_inventions`
- `/qa` — `max_fix_iterations` (replaces the old hardcoded "2 rounds")
- `/convert` — `auto_commit`
- Any skill that dispatches a subagent — `allow_plan_mode` (forwarded in subagent prompt)

Each skill's SKILL.md documents inline which fields it reads and how it acts on them.
