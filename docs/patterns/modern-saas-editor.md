# Modern SaaS Editor — IA + Component Template

Generic skeleton for timeline-centric media creation apps: video editors, audio editors, image editors, DAWs, podcast tools. When the next clone target is a Descript, CapCut, Runway, Suno, or any creation SaaS, run through this doc in the first 15 minutes. Deviate only where the target demonstrably differs.

> STRUCTURE only. Every clone's visual layer (colors, fonts, icons, copy, illustrations) must be original. The skeleton is the value; the visual expression is the legal firewall.
>
> Your clone picks its own visual tokens (background color, font, accent gradient, icon set, spacing scale) in a `visual-decisions.md` file inside your clone directory. Where this doc mentions specific tokens in examples, replace them with yours.

---

## 1. Top-level surfaces

Most creation SaaS products have 5-8 distinct URL surfaces. Map these in the first discovery pass.

| Surface | Purpose | Present when | Missing when |
|---|---|---|---|
| **Project list** | Grid of user's past projects; entry point for new creation. | Always. Core loop. | Never — even a single-project tool usually has a "home" landing. |
| **Tool landings** | Feature-specific entry pages (AI generation modes, import flows). One per major product axis. | Target has distinct creation workflows (generate, import, edit from existing). | Simple one-mode tools (record only, import only). |
| **Editor** | The 4-zone workspace (see section 2). Full-screen or near-full. | Target is a creation tool where the user actively assembles output. | Mostly-automated tools where output is generated server-side with no editing step. |
| **Library / Brand kit** | Reusable assets: logos, fonts, avatars, saved templates. Often gated to Pro/Team plan. | Target markets to teams or brands. | Solo tools, MVP, or early-stage. |
| **Profile / Settings** | Account info, auth method, language, subscription status, danger zone. | Always. | Never. |
| **Billing / Subscription** | Upgrade/downgrade, invoice history. Often embedded in Profile or split to `/billing`. | Freemium or subscription model. | API-only or flat-fee. |
| **API / Developer** | API key generation, docs link, webhook config. | Target has a developer tier or public API. | Consumer-only tools. |

When mapping a new target: open the app sidebar and note which items map to which surfaces. Non-standard surfaces (e.g. a "community templates" marketplace) are deviations — note them for the IA map.

---

## 2. Editor 4-zone layout

Nearly every timeline-centric editor shares this spatial layout:

```
┌──────────┬──────────────────────────────────────────┬───────────────┐
│          │                                          │               │
│  Left    │  Preview / Stage                         │  Right rail   │
│  icon    │  (canvas or video player, centered)      │  (property    │
│  sidebar │                                          │   accordion)  │
│  (~72px) │──────────────────────────────────────────│               │
│          │  Playback toolbar                        │  (~300-360px) │
│          │──────────────────────────────────────────│               │
│          │  Timeline (tracks + ruler)               │               │
│          │  (~160-220px tall, scrollable)           │               │
└──────────┴──────────────────────────────────────────┴───────────────┘
```

### Proportions

- **Left sidebar:** 64-80px wide. Icon + label stacked (or icon-only with tooltip). Fixed height, no scroll.
- **Preview/stage:** flex-grows to fill remaining horizontal space. Maintains aspect ratio (16:9 or user-selected). Centered with padding.
- **Right rail:** 280-380px. Fixed. Scrollable if accordion content overflows.
- **Timeline:** fixed height at the bottom of the center column. Horizontally scrollable. Vertically fixed unless tracks exceed ~6-8.
- **Playback toolbar:** ~48px strip between preview and timeline.

### Responsive considerations

- Narrow (< 1100px): right rail collapses to a toggle panel or hides entirely.
- Very narrow (< 800px): editor is generally not mobile-targeted; show a "use desktop" gate or redirect.
- Example visual-layer choices (your clone picks its own): right rail defaults open at 320px; collapses via a toggle button at the rail edge.

---

## 3. Icon sidebar category taxonomy

The left sidebar holds 5-8 drawer-toggle slots. Each slot = icon + label (stacked). Clicking opens a panel/drawer that replaces the previous one. One slot is a navigation exit (Home/Back), not a drawer.

### Universal slots (present in nearly every editor)

| Slot | Category | Drawer content shape |
|---|---|---|
| **Home / Back** | Navigation exit. Returns user to project list. No drawer. | — |
| **Media / Clips** | User-uploaded video clips. Thumbnails grid, duration badge, drag-to-timeline. | Upload button + thumbnail grid + drag-drop zone |
| **Images** | Still images. AI generation optional. | Import button + grid + optional AI generate section |
| **Audio / Music** | Background music or soundtrack. Library browse + AI generation optional. | Track list + preview player + import |

### Common but not universal

| Slot | Category | Present when |
|---|---|---|
| **Sounds / SFX** | Short audio effects, often AI-generatable. | Target emphasizes audio polish. |
| **Voice / Voiceover** | TTS or recorded narration. Pick voice → write/edit script → generate. | Target has AI narration. |
| **Text / Captions** | Caption style picker or subtitle import. Sometimes split from "Assets". | Target focuses on captioning. |
| **Generate / AI** | General AI generation entry. Sometimes collapses the AI sub-tabs above. | Target has a unified AI pane. |
| **Templates** | Pre-made clip or motion sequences. | Target has a template library. |
| **Brand / Assets** | Logos, brand colors, saved assets from Library. | Team plans. |

### Drawer pattern (shared across all slots)

```
┌─────────────────────────────────┐
│ [Icon] Label            [Close] │  <- header row
│─────────────────────────────────│
│  [Import / Upload button]       │  <- primary action
│                                 │
│  [Library grid or list]         │  <- content body
│   item · item · item            │
│   item · item · item            │
│                                 │
│  [AI section if present]        │  <- optional generation
│   Model picker dropdown         │
│   Prompt textarea               │
│   [Generate button]             │
└─────────────────────────────────┘
```

Opening a new drawer replaces the current one (one drawer open at a time). Active slot is highlighted.

Example visual-layer choices (your clone picks its own): drawer background `zinc-900`, border `zinc-800`, header text `zinc-100`, close button `zinc-500`.

---

## 4. Right-rail accordion pattern

The right rail is a vertical stack of collapsible sections. Fixed order convention:

1. **Export** — always at top. Contains the primary CTA (gradient button). Never collapsed by default.
2. **Primary feature group** — whatever the tool specializes in (captions, effects, color grade). Expanded by default.
3. **AI tools** — one-tap toggles for quality-of-life automation. Binary on/off, no config.
4. **Layout / Format** — aspect ratio, resolution, orientation. Radio group or dropdown.
5. **Advanced** (optional) — edge-case settings, collapsible, closed by default.

### Item types inside sections

| Item type | Control | When to use |
|---|---|---|
| Binary feature on/off | Toggle switch | "Enable denoise", "Show captions" |
| One-of-many selection | Radio group or swatch grid | Aspect ratio, caption style, theme |
| Continuous value | Slider | Volume, zoom, opacity |
| Structured pick | Dropdown or modal picker | Font family, voice, language |

### Accordion mechanics

- Each section = `<h3>` with chevron icon (rotates 180 on collapse).
- Only first 1-2 are open by default; rest collapsed.
- No nesting beyond two levels.
- Scrollable container if total height overflows viewport.

Example visual-layer choices (your clone picks its own): accordion headers `text-zinc-300`, chevron `text-zinc-500`, active section border-left `fuchsia-500`.

---

## 5. Timeline auto-track pattern

Tracks auto-appear when assets of that type are added. No pre-configured track list.

```
ruler:   0s ──────── 1s ──────── 2s ──────── 3s ──────── 4s
         ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
captions │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
video    │ [███ clip-1 ████][██ clip-2 ████]               │
image    │         [■ img ■]                               │
music    │ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
                                  ↑ playhead
```

### Track row anatomy

```
[icon + label (72px)] [────────── media strip ─────────────────────] [+]
```

- **Label column:** fixed width (matches sidebar), icon + type name.
- **Media strip:** thumbnails for video, waveform blocks for audio, text chips for captions/voiceover.
- **`+` button:** far-right of label column (or far-left of strip). Quick-add for that track type.
- **Playhead:** thin vertical line in accent color, spans all tracks, draggable.

### Ruler

- Integer-second marks at major intervals.
- Fractional ticks (0.5s or 0.25s) at minor intervals.
- Ruler label = `HH:MM:SS.ms` or `MM:SS.f` depending on expected duration.
- Zoom changes tick density, not row heights.

### Playback toolbar (center column, above timeline)

```
[← 10s]  [play/pause]  [10s →]  [HH:MM.ss / total]  |  [+ add]  [✂ split]  [🗑 delete]  |  [zoom slider]
```

Left cluster: transport controls + timer. Center: edit actions (disabled when no clip selected). Right: zoom.

Example visual-layer choices (your clone picks its own): playhead `fuchsia-500`, toolbar background `zinc-900`, disabled state `zinc-700`.

---

## 6. Project-list patterns

### Card grid

```
┌─────────────────────────────────┐
│  [16:9 thumbnail]               │
│─────────────────────────────────│
│  Filename.mp4                   │
│  1:23 · 1080p · 24.5 MB · 30fps │  <- metadata tuple
│                           [···] │  <- quick actions menu
└─────────────────────────────────┘
```

Metadata tuple: `duration · resolution · file size · fps`. Not all fields always present. `duration` is the most reliable cross-product.

`···` menu (top-right overlay): Rename, Duplicate, Delete. Sometimes Download. Three-dot always in top-right corner.

Empty state: illustration + headline + single CTA into the creation funnel. The illustration is product-specific (don't copy it); the pattern is universal.

### Bottom-anchored prompt widget

Present on the project list whether empty or loaded. Always at the bottom of the page (sticky or just visually anchored).

```
┌──────────────────────────────────────────────────────────────┐
│ 💬 Describe your video...            [magic] [media] [Upload] │
│                                                   [Continue →]│
└──────────────────────────────────────────────────────────────┘
```

- Textarea or input left.
- Utility icons for toggling options (magic/enhance, media picker).
- Upload button for direct file entry.
- `Continue` primary CTA on the right, advances into funnel.

Example visual-layer choices (your clone picks its own): widget background `zinc-900`, border `zinc-800`, textarea `zinc-950`, Continue button `fuchsia→pink gradient`.

---

## 7. Funnel patterns (prompt → customize → confirm)

Creation funnels are 2-3 steps. Consistent across tools:

```
Step 1: [Prompt / Input]     (project list bottom widget or tool landing CTA)
Step 2: [Customize]          (pick style / voice / template / aspect ratio)
Step 3: [Confirm / Generate] (review script or settings, trigger generation)
```

### Step 2 layout (Customize)

Often a 3-column picker:

```
┌──────────────┬──────────────────┬───────────────────┐
│  Category    │  Items in        │  Selected item    │
│  list        │  category        │  detail / preview │
│  (left)      │  (middle)        │  (right)          │
└──────────────┴──────────────────┴───────────────────┘
     [Back]                                [Continue →]
```

Progress bar at bottom of modal or page. Persistent `Back` button bottom-left. Advancing CTA bottom-right. CTA label changes per step (`Continue` → `Generate Video` → `Create`).

### Step 3 layout (Confirm)

Script or settings review card. Textarea with char counter. `Back` + `Generate [final noun]` CTA.

### Tool landing pattern

On first visit to a specialized tool URL:

```
┌────────────────────────────────────────────────┐
│  [Large demo media / animation]                │
│                                                │
│  [Headline]                                    │
│  [Tagline]                                     │
│                                                │
│  [CTA option A]  [CTA option B]  [CTA option C]│
└────────────────────────────────────────────────┘
```

Each CTA is a distinct path (record, upload, generate from prompt). `beforeunload` warning on navigate-away from partially-started flows.

Example visual-layer choices (your clone picks its own): modal background `zinc-900`, overlay `zinc-950/80`, CTA buttons use gradient for primary, `zinc-800` for secondary.

---

## 8. Profile / Settings stacked-sections pattern

Single column, no tabs for simple products. Tabbed (`General | Security | Billing | Team`) for complex ones.

Simple column order (no tabs):

```
[Avatar / profile picture]
[Display name field]
[Sign-in method card: provider + email]
[Language / locale dropdown]
[Subscription card: tier + upgrade/manage CTA]
[Danger zone: Log out + Delete Account]
```

Each section is visually separated (border-b or margin gap). Destructive actions (Delete Account, Log out) at the bottom, visually distinct (red text or ghost button).

API Dashboard (if present): minimal. API key card with Generate/Regenerate button + masked key display + external docs link.

Example visual-layer choices (your clone picks its own): sections on `zinc-900` card, borders `zinc-800`, destructive text `red-400`.

---

## 9. What to look for on the target — 10-item checklist

Run through this in the first session before writing any clone spec.

- [ ] **Auth gate.** Does the app require login? What subdomain? Confirm you have session cookies on the exact app subdomain, not just the marketing domain.
- [ ] **Surface count.** List all top-level nav items. Map each to the surface table in section 1. Note any non-standard surfaces.
- [ ] **Editor zones.** Does the editor follow the 4-zone layout? What is the left sidebar slot count? Note any zone that's missing or differently positioned.
- [ ] **Sidebar slots.** Walk each slot. Which are universal (media, images, audio)? Which are product-specific? What does each drawer contain?
- [ ] **Right rail structure.** Is Export always at top? How many accordion sections? What item types (toggle, radio, slider)?
- [ ] **Timeline auto-tracks.** Which track types auto-appear? Is there a fixed track count or fully dynamic?
- [ ] **Project list.** Card grid or list view? Metadata tuple fields? Does the bottom-anchored prompt widget exist?
- [ ] **Funnel steps.** How many steps from prompt to generation? Does each step follow the 3-column picker or a different layout?
- [ ] **Profile surface.** Tabs or single column? Which sections are present?
- [ ] **Deviations.** Any zone, surface, or pattern that doesn't match this template? Document them before writing the clone spec.

---

## 10. Visual-divergence notes

Your clone's visual language must deliberately diverge from any captured reference. This section is a one-line reminder per pattern that structure and visual are separate concerns. Fill in the right column with your own tokens in `clones/{domain}/visual-decisions.md`.

| Section | Structural pattern (reuse) | Your visual expression (example tokens shown; pick your own) |
|---|---|---|
| 4-zone layout | Same spatial arrangement | e.g. neutral dark bg, panel/border scale of two shades lighter |
| Icon sidebar | Same slot count and drawer-toggle mechanic | e.g. open-source icon set, inactive/active/indicator tokens |
| Right rail | Export at top, accordion below | e.g. gradient Export button, muted section header color |
| Timeline | Auto-tracks, label + strip, playhead | e.g. accent playhead, muted track row, slightly lighter strip |
| Project cards | Same grid + metadata tuple | e.g. your display font, primary text + muted metadata colors |
| Prompt widget | Same bottom-anchor, same textarea+CTA | e.g. gradient Continue button, inset textarea color |
| Funnel | Same 3-column picker + progress bar | Original copy, original category labels, gradient primary CTA |
| Profile | Same single-column stacked sections | e.g. destructive red, card background |

**Bottom line:** copy the skeleton positions, flows, and interaction patterns exactly. Replace every visual token, icon, label, and copy string with your own originals before shipping.
