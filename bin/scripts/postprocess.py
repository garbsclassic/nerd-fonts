#!/usr/bin/env -S uv run --quiet
# /// script
# requires-python = ">=3.10"
# dependencies = ["fonttools", "brotli"]
# ///
"""Clean up font-patcher output: short family/PostScript names, short filenames, optional
Powerline strip. Idempotent; see AGENTS.md.

    uv run scripts/postprocess.py patched/libron patched/jetbrains-mono patched/jetbrains-mono-propo
    uv run scripts/postprocess.py --strip-powerline patched/inter patched/inter-propo
"""
import argparse
import os
import re
import sys
from pathlib import Path

from fontTools import subset
from fontTools.ttLib import TTFont

POWERLINE = range(0xE0A0, 0xE0D8)
PLUS_SEGMENT = re.compile(r"Plus[A-Za-z]+(?=-)")  # "...NerdFontPlusFontAwesomePlus...-Bold"
PS_ABBREVIATIONS = (("NerdFontPropo", "NFP"), ("NerdFont", "NF"))


def strip_powerline(font: TTFont) -> int:
    cmap = font.getBestCmap()
    keep = [u for u in cmap if u not in POWERLINE]
    if len(keep) == len(cmap):
        return 0
    options = subset.Options()
    options.layout_features = ["*"]
    options.glyph_names = True
    options.notdef_outline = True
    options.name_IDs = ["*"]
    options.name_languages = ["*"]
    options.legacy_cmap = True
    options.recommended_glyphs = True
    options.drop_tables = []  # keep everything the patcher wrote
    subsetter = subset.Subsetter(options)
    subsetter.populate(unicodes=keep)
    subsetter.subset(font)
    return len(cmap) - len(keep)


def shorten_family(font: TTFont) -> int:
    """Cut the long typographic family (ID 16) at " Plus ", in every platform record."""
    fixed = 0
    for record in font["name"].names:
        text = record.toUnicode()
        if record.nameID == 16 and " Plus " in text:
            record.string = text.split(" Plus ")[0]
            fixed += 1
    return fixed


def set_postscript_name(font: TTFont, style: str) -> str:
    family = font["name"].getDebugName(16) or font["name"].getDebugName(1)
    prefix = family.replace(" ", "")
    for long, short in PS_ABBREVIATIONS:
        prefix = prefix.replace(long, short)
    name = f"{prefix}-{style}"
    assert len(name) <= 63, f"PostScript name too long: {name}"
    for record in font["name"].names:
        if record.nameID == 6:
            record.string = name
    return name


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dirs", nargs="+", type=Path)
    parser.add_argument("--strip-powerline", action="store_true",
                        help="remove U+E0A0-E0D7 (Inter ships these natively)")
    args = parser.parse_args()

    files = sorted(p for d in args.dirs for p in d.glob("*.ttf"))
    if not files:
        sys.exit("no .ttf files found")

    ps_names: dict[str, Path] = {}
    for path in files:
        font = TTFont(path)
        dropped = strip_powerline(font) if args.strip_powerline else 0
        fixed = shorten_family(font)
        style = path.stem.rsplit("-", 1)[1]
        ps_name = set_postscript_name(font, style)
        if ps_name in ps_names:
            sys.exit(f"duplicate PostScript name {ps_name}: {path} and {ps_names[ps_name]}")
        ps_names[ps_name] = path

        target = path.with_name(PLUS_SEGMENT.sub("", path.name))
        if target != path and target.exists():
            sys.exit(f"refusing to overwrite {target}")
        tmp = path.with_suffix(".ttf.tmp")  # fontTools reads lazily, so never save over the source
        font.save(tmp)
        os.replace(tmp, target)
        if target != path:
            path.unlink()
        print(f"{target.name}: ps={ps_name} family-records={fixed} powerline-dropped={dropped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
