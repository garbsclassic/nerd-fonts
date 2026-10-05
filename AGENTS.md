# Font patching

Nerd Fonts `font-patcher` (v3.5.1, script 4.27.2) run against our own fonts. Not a git checkout of
upstream: `font-patcher`, `src/glyphs/`, `bin/scripts/`, and `glyphnames.json` come from a release.
Replacing them with a newer release reverts the shebang fix below.

## Layout

| Path                              | What                                                    |
| --------------------------------- | ------------------------------------------------------- |
| `Libron/`                         | Source TTFs (4 styles, no weights to choose from)       |
| `Inter-4.1/extras/ttf/`           | Inter static TTFs (`Inter-*`; ignore `InterDisplay-*`)   |
| `JetBrainsMono-2.304/fonts/ttf/`  | JetBrains Mono static TTFs (ignore `JetBrainsMonoNL-*`) |
| `patched/<family>[-propo]/`       | Outputs: `<Family>NerdFont-<Style>.ttf`, `...NerdFontPropo-...` |

## Rules

- **Sources:** static TTFs only. Not the variable fonts (FontForge ignores variations as far as we
  know; untested) and not woff2 (works, but no reason to compress before patching).
- **Weights:** drop Thin, ExtraLight, ExtraBold, Black, each with its italic. Keep Light, Regular,
  Medium, SemiBold, Bold (+ italics).
- **No `--mono`.** Variants are regular (default) and Propo (`--variable-width-glyphs`).
- **Sets per family** (used instead of `--complete`; `--complete` is ~2x the size, MDI is 6,896 glyphs):

  | Family         | Variants         | Flags                                                                                   |
  | -------------- | ---------------- | --------------------------------------------------------------------------------------- |
  | Libron, Inter  | Libron: regular; Inter: regular + Propo | `--fontawesome --octicons --codicons --material`                 |
  | JetBrains Mono | regular + Propo  | `--powerline --powerlineextra --fontawesome --material --octicons --fontlogos --powersymbols --codicons` |

  Weather, Pomicons and Font Awesome Extension are deliberately left out (stale, unused in our
  dotfiles). Devicons and Seti appear to be included regardless of flags; there is no flag for them.

## Run

`font-patcher`'s shebang is `#!/usr/bin/env python`, which does not exist on macOS; it is edited to
`python3`. `/opt/homebrew/bin/python3` has the `fontforge` bindings (brew `fontforge`); a mise or uv
Python ahead of it on PATH breaks the import.

```sh
python3 font-patcher SRC.ttf --fontawesome --octicons --codicons --material --quiet \
  [--variable-width-glyphs] -out patched/<dir>
```

- About 30-60 s per font. Run ~4 in parallel. Clear old outputs first; partial flags change the
  output filename, so stale files pile up next to new ones.
- **Job files:** `xargs` splits lines on spaces. Use `tr '\n' '\0' < jobs | xargs -0 -n1 -P4 script`.
- **zsh:** unquoted `$VAR` is not word-split (use `${=VAR}`), and an unmatched glob aborts the whole
  command. Quote globs or use `fd`.

## Post-processing

Partial flags make the patcher write names like `Inter Nerd Font Plus Font Awesome Plus ...`.
`scripts/postprocess.py` (idempotent) fixes them; it needs only `uv`:

```sh
uv run scripts/postprocess.py patched/libron patched/jetbrains-mono patched/jetbrains-mono-propo
uv run scripts/postprocess.py --strip-powerline patched/inter patched/inter-propo
```

- **Name ID 16** (typographic family, en-US and Mac records): cut at " Plus ", e.g.
  `Inter Nerd Font Propo`.
- **Name ID 6** (PostScript): `<Family>NF-<Style>`, Propo `<Family>NFP-<Style>` (e.g.
  `InterNFP-Medium`); the script aborts if two files collide.
- **Filenames:** drops the `Plus...` segment before the hyphen.
- **`--strip-powerline` (Inter only):** Inter ships U+E0A0-E0D7 natively and the patcher cannot
  remove source glyphs, so the script subsets them out, keeping layout features. JetBrains Mono
  keeps Powerline (terminal use).

macOS caches font names: reinstall and clear the cache after changing them.

## Verify

- Glyph counts per set from the cmap (Codicons 439, Font Awesome 1,488, Octicons 308, MDI 6,896,
  Font Logos 130, Powerline 0 for Inter/Libron).
- Kerning: `hb-shape SRC.ttf AV --output-format=text` and the same on the patched file; advances
  must match (also `To`, `Wa`).
- Rendering has not been checked visually.

## Known noise (harmless here)

- `WARNING: Fontforge 20251009 produces unusable fonts in some cases`: no breakage seen.
- `Internal Error: ... 'kern' ... is too big. Will not be useable.` on Libron-Bold: FontForge
  complains while saving, but the output's kerning is identical to the source.
- `The glyph named X is mapped to U+... But its name indicates ...`: FontForge opening Inter.
