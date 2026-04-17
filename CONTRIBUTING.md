# Contributing to illy-clone-framework

Thanks for the interest. This is primarily a personal R&D framework that happens to be open source — contributions are welcome but the scope is opinionated.

## What's in scope

- **New skills** for the cloning pipeline (e.g. auth-detection skills, specialized framework detectors, publisher-platform integrations).
- **New patterns** in `docs/patterns/` for site categories the framework hasn't covered yet (e.g. marketplace, e-commerce, social, dashboard). A pattern doc earns its place when it cuts the first-15-minutes discovery time on a new clone target.
- **Scripts** under `scripts/` that generalize across clones (not bespoke to one target).
- **Bug fixes** in existing skills, especially around the convergence loop, cookie decryption, and the QA pixel-diff heuristics.
- **`docs/learnings.md` patterns** discovered during real clones — with a concrete "Applies to" scope so future clones auto-inherit the fix.

## What's out of scope

- Per-site clone output (those belong in your own private repo, not this one).
- Brand-specific visual assets, themes, or design systems.
- Features that require a specific commercial service (Stripe, Auth0, etc.) without a documented local-dev fallback.

## Running the plugin locally

```bash
# Symlink into a test project's plugin dir
mkdir -p ~/testclone/.claude/plugins
ln -s "$(pwd)" ~/testclone/.claude/plugins/illy-clone-framework
cd ~/testclone
claude  # Claude Code picks up the plugin
```

## Testing changes

1. Make the change to a skill or script.
2. Run a real clone end-to-end against a known target (a small static site is fastest). Confirm the full pipeline completes.
3. For changes to `/diff-flow-match` Stage 6: verify the convergence loop on a contrived failing clone — force a FAIL row, confirm Stage 6 dispatches a fixer, confirm rebuild + replay fixes it.
4. Update `docs/learnings.md` if you discovered a new pattern while testing.

## Policy on "no inventions"

The `no_inventions` rule in `clone-config.json` means the clone must not add routes/screens/flows that the source doesn't have. If a skill change makes this harder to enforce, call it out in the PR.

## Submitting

1. Open an issue first for anything non-trivial. One-line bug fixes can go straight to PR.
2. Keep PRs scoped — one skill change, one pattern addition, or one bug fix per PR.
3. Update the README and relevant SKILL.md files if behavior changed.
4. No line-noise commits — follow the existing commit-message style (`feat(skill-name): ...`, `fix(script): ...`, `docs: ...`).

## License

By contributing you agree your contribution is released under the MIT license (see `LICENSE`).
