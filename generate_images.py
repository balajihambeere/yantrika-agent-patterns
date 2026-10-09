#!/usr/bin/env python3
"""
Generates the 16 product images (8 wiring-harness, 8 fastener/bolt) from
the prompt sets in 01-agentic-loop/images/PROMPTS.md and
shared-fastener-images/PROMPTS.md, using OpenAI's gpt-image-1 at low
quality (~$0.011/image, ~$0.18 total for all 16 — see those PROMPTS.md
files' Notes section for the pricing this was based on).

The prompts are embedded directly below rather than parsed out of the
Markdown files, so this script has no dependency on their formatting —
if you edit a prompt, update it in both places (or just use this script
as the source of truth going forward).

Setup:
    pip install openai
    Put OPENAI_API_KEY=sk-... in a .env file at the repo root (see
    01-agentic-loop/.env.example), or export it directly — either works,
    this script loads .env itself with no extra dependency required.

Run:
    python3 generate_images.py              # generate all 16
    python3 generate_images.py --set harness   # just the 8 harness images
    python3 generate_images.py --set fastener  # just the 8 fastener images
    python3 generate_images.py --dry-run       # print what would happen, no API calls, no cost

Already-generated files are skipped automatically (safe to re-run after a
partial failure without paying to regenerate images you already have).
"""
from __future__ import annotations

import argparse
import base64
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
MODEL = "gpt-image-1"
QUALITY = "low"
SIZE = "1024x1024"
COST_PER_IMAGE = 0.011  # USD, gpt-image-1, low quality, 1024x1024 — see PROMPTS.md Notes


def load_dotenv(path: Path) -> None:
    """
    Minimal .env loader — no python-dotenv dependency needed. Only sets a
    variable if it isn't already present in the real environment, so an
    explicit `export` always wins over the file.
    """
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)

HARNESS_STYLE_SUFFIX = (
    " Plain white background, no text, no labels, no shadows, centered "
    "composition, icon-like, clean vector style — like a parts-catalog diagram."
)

HARNESS_PRODUCTS = [
    (
        "eh-4200.png",
        "Engine Wiring Harness (EH-4200)",
        "01-agentic-loop/images",
        "A flat, minimalist technical line-art illustration of an automotive engine "
        "wiring harness: a thick central bundle of cables wrapped in black corrugated "
        "loom tubing, branching into 4-5 shorter sub-branches each ending in a small "
        "rectangular connector plug. Single accent color (orange) used only for the "
        "connector plugs, everything else in black line art." + HARNESS_STYLE_SUFFIX,
    ),
    (
        "dh-3100.png",
        "Dashboard Wiring Harness (DH-3100)",
        "01-agentic-loop/images",
        "A flat, minimalist technical line-art illustration of an automotive "
        "dashboard wiring harness: a wide, flat fan of cables spreading out from one "
        "thick trunk into 7-8 thin branches, each ending in a small multi-pin "
        "connector block of varying sizes. Single accent color (orange) used only "
        "for the connector blocks, everything else in black line art." + HARNESS_STYLE_SUFFIX,
    ),
    (
        "drh-220l.png",
        "Door Wiring Harness, Left (DRH-220L)",
        "01-agentic-loop/images",
        "A flat, minimalist technical line-art illustration of an automotive door "
        "wiring harness: a medium-length cable bundle passing through a round "
        "rubber grommet/boot in the middle (representing the door hinge pass-through), "
        "with three branch connectors at one end (for a window motor, a speaker, and "
        "a lock actuator) and one larger connector at the other end. Single accent "
        "color (orange) used only for the connectors and grommet, everything else in "
        "black line art." + HARNESS_STYLE_SUFFIX,
    ),
    (
        "drh-220r.png",
        "Door Wiring Harness, Right (DRH-220R)",
        "01-agentic-loop/images",
        "A flat, minimalist technical line-art illustration of an automotive door "
        "wiring harness, mirrored left-to-right from a standard left-door harness: a "
        "medium-length cable bundle passing through a round rubber grommet/boot in "
        "the middle, with three branch connectors at one end (for a window motor, a "
        "speaker, and a lock actuator) and one larger connector at the other end. "
        "Single accent color (orange) used only for the connectors and grommet, "
        "everything else in black line art." + HARNESS_STYLE_SUFFIX,
    ),
    (
        "bwh-500.png",
        "Battery Wiring Harness (BWH-500)",
        "01-agentic-loop/images",
        "A flat, minimalist technical line-art illustration of an automotive battery "
        "wiring harness: two thick, heavy-gauge cables (noticeably thicker than a "
        "standard harness bundle) each ending in a ring terminal lug, running to a "
        "small in-line fuse box connector. Single accent color (orange) used only "
        "for the ring terminals and fuse box, everything else in black line art." + HARNESS_STYLE_SUFFIX,
    ),
    (
        "cwh-750.png",
        "Chassis Wiring Harness (CWH-750)",
        "01-agentic-loop/images",
        "A flat, minimalist technical line-art illustration of an automotive chassis "
        "wiring harness: a long, straight cable run wrapped in ribbed protective "
        "conduit, with evenly spaced small connector branches along its length (for "
        "ABS wheel-speed sensors) and a larger connector at each end. Single accent "
        "color (orange) used only for the connectors, everything else in black line "
        "art." + HARNESS_STYLE_SUFFIX,
    ),
    (
        "twh-310.png",
        "Transmission Wiring Harness (TWH-310)",
        "01-agentic-loop/images",
        "A flat, minimalist technical line-art illustration of an automotive "
        "transmission wiring harness: a short, compact cable bundle wrapped in "
        "heat-resistant woven sleeving, ending in one sealed multi-pin connector "
        "plug with a visible latch clip. Single accent color (orange) used only for "
        "the connector and latch clip, everything else in black line art." + HARNESS_STYLE_SUFFIX,
    ),
    (
        "hwh-150.png",
        "Headlamp Wiring Harness (HWH-150)",
        "01-agentic-loop/images",
        "A flat, minimalist technical line-art illustration of an automotive "
        "headlamp wiring harness: a short Y-shaped cable bundle splitting into two "
        "round bulb-socket connectors at one end, with a small relay plug at the "
        "other end. Single accent color (orange) used only for the connectors and "
        "relay plug, everything else in black line art." + HARNESS_STYLE_SUFFIX,
    ),
]

FASTENER_STYLE_SUFFIX = (
    " Plain white background, no text, no labels, no shadows, centered "
    "composition, icon-like, clean vector style — like a parts-catalog diagram."
)

FASTENER_PRODUCTS = [
    (
        "m8x40-hex-flange-bolt.png",
        "M8x40 Hex Flange Bolt",
        "shared-fastener-images",
        "A flat, minimalist technical line-art illustration of a hex flange bolt: "
        "a hexagonal bolt head with an integrated circular flange/washer sitting "
        "directly under the head, a threaded shaft extending downward with visible "
        "thread lines. Single accent color (teal) used only for the flange, "
        "everything else in black line art." + FASTENER_STYLE_SUFFIX,
    ),
    (
        "m10x30-hex-flange-bolt.png",
        "M10x30 Hex Flange Bolt",
        "shared-fastener-images",
        "A flat, minimalist technical line-art illustration of a hex flange bolt, "
        "slightly shorter and thicker than a standard M8 bolt: a hexagonal bolt "
        "head with an integrated circular flange/washer sitting directly under the "
        "head, a threaded shaft extending downward with visible thread lines. "
        "Single accent color (teal) used only for the flange, everything else in "
        "black line art." + FASTENER_STYLE_SUFFIX,
    ),
    (
        "m6x20-socket-head-cap-screw.png",
        "M6x20 Socket-Head Cap Screw",
        "shared-fastener-images",
        "A flat, minimalist technical line-art illustration of a socket-head cap "
        "screw: a small cylindrical head with a visible hexagonal socket recess on "
        "top, a straight threaded shaft extending downward with visible thread "
        "lines. Single accent color (teal) used only for the hexagonal socket "
        "recess, everything else in black line art." + FASTENER_STYLE_SUFFIX,
    ),
    (
        "m8-hex-flange-nut.png",
        "M8 Hex Flange Nut",
        "shared-fastener-images",
        "A flat, minimalist technical line-art illustration of a hex flange nut: a "
        "hexagonal nut body with an integrated circular flange at its base, a "
        "visible threaded hole through the center. Single accent color (teal) used "
        "only for the flange, everything else in black line art." + FASTENER_STYLE_SUFFIX,
    ),
    (
        "m8-spring-washer.png",
        "M8 Spring Washer",
        "shared-fastener-images",
        "A flat, minimalist technical line-art illustration of a split spring "
        "lock washer: a thin ring with a single diagonal split/gap and a visible "
        "twist, giving it a slightly helical look. Single accent color (teal) used "
        "for the washer ring, everything else in black line art." + FASTENER_STYLE_SUFFIX,
    ),
    (
        "5mm-pop-rivet.png",
        "5mm Pop Rivet",
        "shared-fastener-images",
        "A flat, minimalist technical line-art illustration of a pop rivet "
        "(blind rivet): a cylindrical rivet body with a domed head on one end and "
        "a thin mandrel/pin extending out the other end through the center. Single "
        "accent color (teal) used for the domed head, everything else in black "
        "line art." + FASTENER_STYLE_SUFFIX,
    ),
    (
        "m8x25-u-bolt-clamp.png",
        "M8x25 U-Bolt Clamp",
        "shared-fastener-images",
        "A flat, minimalist technical line-art illustration of a U-bolt clamp: a "
        "bolt bent into a U shape with threaded ends on both straight sections, "
        "paired with a flat rectangular mounting plate with two holes that the "
        "threaded ends pass through, secured by two small hex nuts. Single accent "
        "color (teal) used only for the two hex nuts, everything else in black "
        "line art." + FASTENER_STYLE_SUFFIX,
    ),
    (
        "m10-wheel-stud.png",
        "M10 Wheel Stud",
        "shared-fastener-images",
        "A flat, minimalist technical line-art illustration of a wheel stud: a "
        "straight cylindrical shaft, threaded along its full length, with a small "
        "knurled (textured) collar section near one end instead of a head. Single "
        "accent color (teal) used for the knurled collar section, everything else "
        "in black line art." + FASTENER_STYLE_SUFFIX,
    ),
]


def generate_one(client, filename: str, label: str, folder: str, prompt: str, dry_run: bool) -> bool:
    out_dir = ROOT / folder
    out_path = out_dir / filename

    if out_path.exists():
        print(f"  skip   {filename:<28} already exists at {out_path.relative_to(ROOT)}")
        return False

    if dry_run:
        print(f"  would generate  {filename:<28} ({label}) -> {out_path.relative_to(ROOT)}")
        return True

    print(f"  generating  {filename:<28} ({label}) ...", end=" ", flush=True)
    result = client.images.generate(
        model=MODEL,
        prompt=prompt,
        size=SIZE,
        quality=QUALITY,
        n=1,
    )
    image_b64 = result.data[0].b64_json
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(base64.b64decode(image_b64))
    print(f"saved (${COST_PER_IMAGE:.3f})")
    return True


def main() -> None:
    load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", choices=["harness", "fastener", "both"], default="both")
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen; no API calls, no cost.")
    args = parser.parse_args()

    products = []
    if args.set in ("harness", "both"):
        products += HARNESS_PRODUCTS
    if args.set in ("fastener", "both"):
        products += FASTENER_PRODUCTS

    if not args.dry_run and not os.environ.get("OPENAI_API_KEY"):
        print(
            "OPENAI_API_KEY is not set. Export it or create a .env "
            "(see 01-agentic-loop/.env.example) before running this for real.\n"
            "Tip: use --dry-run first to see what would be generated at no cost.",
            file=sys.stderr,
        )
        sys.exit(1)

    client = None
    if not args.dry_run:
        from openai import OpenAI  # imported here so --dry-run never requires the package installed

        client = OpenAI()

    print(f"Model: {MODEL}  Quality: {QUALITY}  Size: {SIZE}")
    print(f"Planned: {len(products)} image(s)")
    print()

    generated = 0
    for filename, label, folder, prompt in products:
        if generate_one(client, filename, label, folder, prompt, args.dry_run):
            generated += 1

    print()
    if args.dry_run:
        print(f"Dry run: {generated} image(s) would be generated. No cost incurred.")
    else:
        print(f"Done: {generated} image(s) generated, ~${generated * COST_PER_IMAGE:.3f} spent.")


if __name__ == "__main__":
    main()
