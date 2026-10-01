# Lecture media downloader

`fetch_lecture_media.py` pulls Wikimedia Commons / Wikipedia figures (and other direct
URLs) into a lecture's `images/` folder, and records the **license + attribution + alt
text** for each one. Run it in your **own terminal** (it needs normal internet; the
Cowork sandbox blocks Wikimedia).

## Quick start

```bash
cd Lectures/Lecture02_EnergyGeneration        # wherever the lecture lives
python3 /path/to/fetch_lecture_media.py manifest.json --out images --max-width 1600
```

That writes the image files plus `images/CREDITS.md` and `images/credits.json`.
Standard-library only — no `pip install`.

## What Claude gives you per lecture

A `manifest.json` (one entry per figure) with the exact file title, a suggested
filename, pre-written **alt text**, and a caption. You run the script; it fetches the
bytes and fills in the real license + attribution from the Wikimedia API.

## Manifest entry fields

| field     | meaning |
|-----------|---------|
| `file`    | Commons file title (`File:Foo.jpg`) or a Commons/Wikipedia file-page URL |
| `url`     | a **direct** media URL for a non-Wikimedia source (skips the API) |
| `name`    | desired local filename (optional) |
| `alt`     | alt text, recorded for the slide / `.qmd` (optional) |
| `caption` | on-slide caption (optional) |
| `credit`  | manual attribution — **required** for `url` (non-Wikimedia) entries |
| `note`    | a reminder to yourself (e.g. "verify this title") — kept OUT of the on-slide caption |

A plain `.txt` file with one `File:` title (or URL) per line also works.

## Upstream alt text, and injecting it into the `.qmd`

Wikimedia already holds alt-ish text in three separate places, and the script now
collects all three per file:

1. the **file-page description** (`extmetadata.ImageDescription`)
2. the **Commons structured-data caption** (the Wikibase label on the file's M-id)
3. the **`alt=` attribute** used where an article actually embeds the file — usually
   the best of the three, because a human wrote it for a specific context

All three land in `CREDITS.md` / `credits.json`, and in a paste-ready
`images/ALT_BLOCKS.md`. Claude's hand-written `alt` stays the **primary** one; the
upstream versions sit beside it so you can swap in a better phrasing by hand.

### Injecting into a deck

Put a marker on the slide where the figure belongs:

```markdown
<!-- IMG: breaker_boys.jpg -->
```

then run with `--inject-qmd`:

```bash
python3 ../../tools/fetch_lecture_media.py manifest_blair_mountain.json \
    --out images --inject-qmd lecture03_battle_of_blair_mountain.qmd
```

Each marker is filled in with a Quarto figure plus every alt candidate as a comment:

```markdown
<!-- IMG: breaker_boys.jpg -->
<!-- ALT-BLOCK:BEGIN breaker_boys.jpg -->
![Breaker boys, Kingston PA. Public domain.](images/breaker_boys.jpg){fig-alt="Black-and-white photograph of dozens of soot-covered boys..."}

<!-- alt candidates for breaker_boys.jpg - edit the fig-alt= above by hand.
     [manifest-note        ] ...
     [claude               ] ...
     [sd-caption           ] ...
     [file-desc            ] ...
     [article-alt: Breaker boy] ...
-->
<!-- ALT-BLOCK:END breaker_boys.jpg -->
```

Notes on behaviour:

- **It is idempotent.** Re-running refreshes the candidate list in place; it does not
  stack up duplicate blocks.
- **Your hand edits survive.** If you rewrite a `fig-alt=`, a later run keeps it and
  reports how many it preserved. Pass `--force-alt` to overwrite them deliberately.
- **Markers for files not in this manifest are left alone**, so two manifests can share
  one `.qmd` (which is exactly the Lecture 3 situation — AC/DC half and Blair Mountain
  half).
- **Non-free files get a commented-out figure** and a "find a free substitute" note, so
  the deck never references a file that was never downloaded.
- `--no-harvest` skips the upstream lookups (fewer API calls, faster).

**Why `fig-alt=` and not the bracket text:** in Quarto, `![text](img.jpg)` renders
`text` as a visible *caption*, not as alt text. Alt text has to go in `fig-alt`. The
script puts your caption in the brackets and the alt text in `fig-alt`, which is what
you want for both PowerPoint and reveal.js.

## Safeguards

- **Non-free images are flagged and skipped.** English Wikipedia hosts some copyrighted
  "fair-use" images (logos, many photos of living people). The script marks these
  `!! NON-FREE / CHECK` and does not download them unless you pass `--allow-nonfree`
  (only do that if *you* hold the rights). Prefer a Commons-hosted PD/CC alternative.
- **Every license still needs a human glance.** `CREDITS.md` says at the top to verify.
- **Corroborate federal sources.** Per the course source-integrity rule, any `.gov`
  figure (EIA/NASA/NOAA/EPA) must be paired with an independent source.

## Discovery mode

Two ways to find files. Both print `FREE? / LICENSE / DIMENSIONS / TITLE`.

**By article** — what figures does this Wikipedia page already use?

```bash
python3 fetch_lecture_media.py --from-article "Utica Shale"
```

**By keyword** — when you don't know the exact `File:` title. This is the one to reach
for when a manifest entry comes back "not found on Commons or en.wikipedia", which is
the usual failure: guessed titles are almost always slightly wrong.

```bash
python3 fetch_lecture_media.py --search "Sid Hatfield"
```

Add `--json` to either one and it prints a **manifest skeleton of just the free
results**, with the upstream file description pre-filled as draft alt text:

```bash
python3 fetch_lecture_media.py --search "coal scrip token" --json
```

Paste that into your manifest and edit the `alt` / `caption`.

## Handy flags

`--out DIR` · `--max-width PX` (0 = originals) · `--dry-run` · `--force` · `--allow-nonfree`
