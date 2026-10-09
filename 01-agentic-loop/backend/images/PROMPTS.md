# Product image prompts — paste into ChatGPT, one at a time

Style is kept identical across all 8 so they read as one consistent set.
Each prompt ends with the same style suffix on purpose — don't drop it.

Save each result using the filename noted above its prompt (keeps them
matched to the SKUs used in `data/harness_products_100.json`).

## 1 — `eh-4200.png` — Engine Wiring Harness (EH-4200)

```text
A flat, minimalist technical line-art illustration of an automotive engine
wiring harness: a thick central bundle of cables wrapped in black corrugated
loom tubing, branching into 4-5 shorter sub-branches each ending in a small
rectangular connector plug. Single accent color (orange) used only for the
connector plugs, everything else in black line art. Plain white background,
no text, no labels, no shadows, centered composition, icon-like, clean
vector style, isometric-ish but simple — like a parts-catalog diagram.
```

## 2 — `dh-3100.png` — Dashboard Wiring Harness (DH-3100)

```text
A flat, minimalist technical line-art illustration of an automotive
dashboard wiring harness: a wide, flat fan of cables spreading out from one
thick trunk into 7-8 thin branches, each ending in a small multi-pin
connector block of varying sizes. Single accent color (orange) used only
for the connector blocks, everything else in black line art. Plain white
background, no text, no labels, no shadows, centered composition,
icon-like, clean vector style — like a parts-catalog diagram.
```

## 3 — `drh-220l.png` — Door Wiring Harness, Left (DRH-220L)

```text
A flat, minimalist technical line-art illustration of an automotive door
wiring harness: a medium-length cable bundle passing through a round
rubber grommet/boot in the middle (representing the door hinge pass-through),
with three branch connectors at one end (for a window motor, a speaker, and
a lock actuator) and one larger connector at the other end. Single accent
color (orange) used only for the connectors and grommet, everything else in
black line art. Plain white background, no text, no labels, no shadows,
centered composition, icon-like, clean vector style — like a parts-catalog
diagram.
```

## 4 — `drh-220r.png` — Door Wiring Harness, Right (DRH-220R)

```text
A flat, minimalist technical line-art illustration of an automotive door
wiring harness, mirrored left-to-right from a standard left-door harness: a
medium-length cable bundle passing through a round rubber grommet/boot in
the middle, with three branch connectors at one end (for a window motor, a
speaker, and a lock actuator) and one larger connector at the other end.
Single accent color (orange) used only for the connectors and grommet,
everything else in black line art. Plain white background, no text, no
labels, no shadows, centered composition, icon-like, clean vector style —
like a parts-catalog diagram.
```

## 5 — `bwh-500.png` — Battery Wiring Harness (BWH-500)

```text
A flat, minimalist technical line-art illustration of an automotive battery
wiring harness: two thick, heavy-gauge cables (noticeably thicker than a
standard harness bundle) each ending in a ring terminal lug, running to a
small in-line fuse box connector. Single accent color (orange) used only
for the ring terminals and fuse box, everything else in black line art.
Plain white background, no text, no labels, no shadows, centered
composition, icon-like, clean vector style — like a parts-catalog diagram.
```

## 6 — `cwh-750.png` — Chassis Wiring Harness (CWH-750)

```text
A flat, minimalist technical line-art illustration of an automotive chassis
wiring harness: a long, straight cable run wrapped in ribbed protective
conduit, with evenly spaced small connector branches along its length (for
ABS wheel-speed sensors) and a larger connector at each end. Single accent
color (orange) used only for the connectors, everything else in black line
art. Plain white background, no text, no labels, no shadows, centered
composition, icon-like, clean vector style — like a parts-catalog diagram.
```

## 7 — `twh-310.png` — Transmission Wiring Harness (TWH-310)

```text
A flat, minimalist technical line-art illustration of an automotive
transmission wiring harness: a short, compact cable bundle wrapped in
heat-resistant woven sleeving, ending in one sealed multi-pin connector
plug with a visible latch clip. Single accent color (orange) used only for
the connector and latch clip, everything else in black line art. Plain
white background, no text, no labels, no shadows, centered composition,
icon-like, clean vector style — like a parts-catalog diagram.
```

## 8 — `hwh-150.png` — Headlamp Wiring Harness (HWH-150)

```text
A flat, minimalist technical line-art illustration of an automotive
headlamp wiring harness: a short Y-shaped cable bundle splitting into two
round bulb-socket connectors at one end, with a small relay plug at the
other end. Single accent color (orange) used only for the connectors and
relay plug, everything else in black line art. Plain white background, no
text, no labels, no shadows, centered composition, icon-like, clean vector
style — like a parts-catalog diagram.
```

## Notes

- If ChatGPT drifts off-style on any one of them, just re-paste the same
  prompt again (or add "match the style of the previous image exactly") —
  regenerating one is cheap.
- If you'd rather have a different accent color than orange, find-and-replace
  "orange" across all 8 before you start, so the set stays consistent.
- Recommended output size for a product-grid UI: ask for a square image
  (1024×1024) — easiest to lay out evenly in a Next.js grid later.
