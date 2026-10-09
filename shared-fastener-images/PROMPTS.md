# Fastener/bolt product image prompts — paste into ChatGPT, one at a time

Used by **02-po-acknowledgment-agent**, **05-federation-arbitration**, and
**06-registry-precedence-arbitration** — the three examples whose data is
about fasteners, not wiring harnesses (suppliers like "Deccan Fasteners",
"Nashik Precision Fasteners", "Continental Fasteners"; SKUs like
`M8x40-hex-flange-bolt` in 06 and `fastener_family_F12` in 05).

Only one SKU is actually named in the existing data —
`M8x40-hex-flange-bolt` (06's `bolt_sku`) — so prompt 1 below matches it
exactly. The other 7 are plausible same-family variants a fastener
supplier in this project would realistically also carry, invented the same
way the 8 harness products were.

Same style suffix on every prompt, on purpose, so the set is visually
consistent with itself — but it's a **different style from the harness
set** (hex-head bolt icon language instead of cable-bundle language),
since that's what actually reads correctly for this product category.

Save each result using the filename noted above its prompt.

## 1 — `m8x40-hex-flange-bolt.png` — M8x40 Hex Flange Bolt

The real SKU from `06-registry-precedence-arbitration`.

```text
A flat, minimalist technical line-art illustration of a hex flange bolt:
a hexagonal bolt head with an integrated circular flange/washer sitting
directly under the head, a threaded shaft extending downward with visible
thread lines. Single accent color (teal) used only for the flange,
everything else in black line art. Plain white background, no text, no
labels, no shadows, centered composition, icon-like, clean vector style —
like a parts-catalog diagram.
```

## 2 — `m10x30-hex-flange-bolt.png` — M10x30 Hex Flange Bolt

```text
A flat, minimalist technical line-art illustration of a hex flange bolt,
slightly shorter and thicker than a standard M8 bolt: a hexagonal bolt
head with an integrated circular flange/washer sitting directly under the
head, a threaded shaft extending downward with visible thread lines.
Single accent color (teal) used only for the flange, everything else in
black line art. Plain white background, no text, no labels, no shadows,
centered composition, icon-like, clean vector style — like a parts-catalog
diagram.
```

## 3 — `m6x20-socket-head-cap-screw.png` — M6x20 Socket-Head Cap Screw

```text
A flat, minimalist technical line-art illustration of a socket-head cap
screw: a small cylindrical head with a visible hexagonal socket recess on
top, a straight threaded shaft extending downward with visible thread
lines. Single accent color (teal) used only for the hexagonal socket
recess, everything else in black line art. Plain white background, no
text, no labels, no shadows, centered composition, icon-like, clean vector
style — like a parts-catalog diagram.
```

## 4 — `m8-hex-flange-nut.png` — M8 Hex Flange Nut

```text
A flat, minimalist technical line-art illustration of a hex flange nut: a
hexagonal nut body with an integrated circular flange at its base, a
visible threaded hole through the center. Single accent color (teal) used
only for the flange, everything else in black line art. Plain white
background, no text, no labels, no shadows, centered composition,
icon-like, clean vector style — like a parts-catalog diagram.
```

## 5 — `m8-spring-washer.png` — M8 Spring Washer

```text
A flat, minimalist technical line-art illustration of a split spring
lock washer: a thin ring with a single diagonal split/gap and a visible
twist, giving it a slightly helical look. Single accent color (teal) used
for the washer ring, everything else in black line art. Plain white
background, no text, no labels, no shadows, centered composition,
icon-like, clean vector style — like a parts-catalog diagram.
```

## 6 — `5mm-pop-rivet.png` — 5mm Pop Rivet

```text
A flat, minimalist technical line-art illustration of a pop rivet
(blind rivet): a cylindrical rivet body with a domed head on one end and
a thin mandrel/pin extending out the other end through the center. Single
accent color (teal) used for the domed head, everything else in black
line art. Plain white background, no text, no labels, no shadows,
centered composition, icon-like, clean vector style — like a
parts-catalog diagram.
```

## 7 — `m8x25-u-bolt-clamp.png` — M8x25 U-Bolt Clamp

```text
A flat, minimalist technical line-art illustration of a U-bolt clamp: a
bolt bent into a U shape with threaded ends on both straight sections,
paired with a flat rectangular mounting plate with two holes that the
threaded ends pass through, secured by two small hex nuts. Single accent
color (teal) used only for the two hex nuts, everything else in black
line art. Plain white background, no text, no labels, no shadows,
centered composition, icon-like, clean vector style — like a
parts-catalog diagram.
```

## 8 — `m10-wheel-stud.png` — M10 Wheel Stud

```text
A flat, minimalist technical line-art illustration of a wheel stud: a
straight cylindrical shaft, threaded along its full length, with a small
knurled (textured) collar section near one end instead of a head. Single
accent color (teal) used for the knurled collar section, everything else
in black line art. Plain white background, no text, no labels, no
shadows, centered composition, icon-like, clean vector style — like a
parts-catalog diagram.
```

## Notes

- Accent color here is **teal**, not the harness set's orange — on
  purpose, so the two product families are visually distinguishable at a
  glance if they ever appear in the same UI.
- If you'd rather match the harness set's orange instead, find-and-replace
  "teal" across all 8 before you start.
- Recommended output size: square, 1024×1024 — same reasoning as the
  harness set, easiest to lay out evenly in a grid later.
