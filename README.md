# illy-clone-framework

A Claude Code plugin for **structural** website cloning. Point it at a URL, answer a few detection questions, and get back a working local project that matches the source's information architecture, flows, and dynamics — with an entirely original visual layer as the legal firewall.

**Not a pixel-scraper.** Pixel-perfect clones of commercial SaaS land you in infringement. This framework does the work that actually matters — the 1:1 structural match on routes, flows, button sequences, and state changes — and leaves you to pick your own brand, colors, fonts, icons, and copy.

## What you get

- `/clone {url}` — discover → clone → fix → QA pipeline with auto-detection (React/Next/Vue/static, sitemap, auth pages, framework-specific quirks)
- `/qa` — automated pixel comparison vs. the live source, zone-level diff analysis, passing/failing page report
- `/manual-qa` — interactive behavior testing via Playwright MCP for SPA features that screenshots can't verify
- `/diff-flow-match` — record a source flow, replay it against your clone, produce a PASS/PARTIAL/FAIL matrix, and **converge to 100%** through a Stage 6 fix loop that dispatches scoped fixer subagents until every non-PASS is either resolved or a hard-BLOCKED with concrete env evidence
- `/import-browser-cookies` — decrypt your Chrome session cookies locally and load them into Playwright MCP for authenticated cloning
- `/convert`, `/analyze`, `/improve` — the rest of the pipeline: HTML → framework (Vite/Next.js), dependency/architecture report, learning loop

## The philosophy

| | |
|---|---|
| **Structural match** | Same routes, same flows, same button sequences, same state changes. This is the product value. |
| **Visual firewall** | Your own font, color palette, icons, copy, illustrations. This is the compliance. |
| **Convergence, not reporting** | `/diff-flow-match` doesn't stop at a report. It loops: drive → find deltas → dispatch fixer → rebuild → re-drive, until `target_parity` from `clone-config.json` is hit. |
| **Policy over prompts** | Whether to auto-commit, how many fix iterations, whether to allow subagent plan mode, whether inventions (extra routes in the clone) auto-FAIL — all declared in `clone-config.json`. The pipeline doesn't ask you these every time. |

Read `docs/patterns/modern-saas-editor.md` before cloning a timeline-centric creation tool (video editor, DAW, design tool). The IA skeleton for that entire category is already captured.

Read `docs/patterns/nextauth-subdomain-auth.md` before trying to import cookies for a NextAuth-backed app on a subdomain. The cookie-subdomain pitfall will eat an hour if you don't.

## Install as a Claude Code plugin

```bash
# Clone into your Claude plugins directory
cd ~/.claude/plugins
git clone https://github.com/{your-username}/illy-clone-framework.git
```

Claude Code auto-discovers the plugin via `.claude-plugin/plugin.json`.

Alternatively, reference it from a project by symlinking into `.claude/plugins/` in that project.

## Quick start

```bash
# In a new working directory where you want to keep your clones
mkdir -p clones/example.com

# Optional: override any policy for this clone only
cat > clones/example.com/clone-config.json <<'EOF'
{ "target_parity": 1.0, "auto_push_end": true }
EOF

# Then in Claude Code:
/clone https://example.com
```

The pipeline:

1. **Detects** the site's framework, crawls its sitemap, flags auth-required pages, and asks you which cloning mode (public, authenticated, or public-now-auth-later).
2. **Clones** via Playwright interception; writes `clones/example.com/static-clone/`.
3. **Fixes** common pitfalls auto-detected from `docs/learnings.md` (SPA script stripping, nested `<a>` tags, lazy-loaded images, URL rewriting).
4. **QAs** via `scripts/qa_compare.py` with a 30-threshold pixel diff and zone analysis. Runs a fix loop up to `max_fix_iterations` (default 5).
5. **Converts** to a React/Next.js project if the framework was detected as a SPA.
6. **Runs `/diff-flow-match`** with the Stage 6 convergence loop to hit `target_parity` on structural flows.
7. **Updates `docs/learnings.md`** with new patterns discovered.

## Configuration — `clone-config.json`

One file controls framework behavior. Defaults ship with the plugin at `.claude-plugin/clone-config.default.json`:

```json
{
  "target_parity": 1.0,
  "max_fix_iterations": 5,
  "auto_commit": true,
  "auto_push_end": false,
  "allow_plan_mode": false,
  "no_inventions": true,
  "partials_allowed": 0,
  "blocked_requires_evidence": true,
  "commit_author_email": "",
  "visual_firewall_enforced": true
}
```

Resolution (first found wins):
1. `clones/{domain}/clone-config.json` — per-clone override
2. `~/.claude/clone-config.json` — user-global override (gitignored)
3. `.claude-plugin/clone-config.default.json` — plugin default

See `docs/clone-config.md` for the full per-field semantics.

## The Stage 6 convergence loop

Where most QA tools stop at "here's the report," `/diff-flow-match` loops until it's actually done:

```
replay source flow  →  diff per-step  →  write match-matrix.md  →  Stage 6
                                                                      │
                         ┌────────────────────────────────────────────┘
                         ▼
      score >= target_parity  &&  every non-PASS has evidence  →  done
                         │
                         ▼  else
      collect FAIL + PARTIAL rows  →  build fix tickets
                         │
                         ▼
      dispatch fixer subagent (scope = clones/{domain}/{template}/ only)
                         │
                         ▼
      rebuild clone  →  replay  →  loop (cap: max_fix_iterations)
```

Iteration snapshots land in `clones/{domain}/matrix-history/iter-{n}.md` so the convergence is auditable.

## Your clones are your own

This repo ships the framework. Your actual cloned sites live in your own working directory (typically a private repo). Don't commit cookies, env files, or brand-specific screenshots here — the `.gitignore` blocks the common footguns, but be careful with `git add -A`.

## Contributing

See `CONTRIBUTING.md`.

## License

MIT. See `LICENSE`.
