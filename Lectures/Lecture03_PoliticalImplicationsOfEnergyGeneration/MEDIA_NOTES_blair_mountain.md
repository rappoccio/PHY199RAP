# Media notes — Blair Mountain half of Lecture 3

`manifest_blair_mountain.json` is **separate from** `manifest.json` (which covers only
the AC/DC half). 22 entries. Run it into the same `images/` folder — filenames don't
collide with the AC/DC set.

## Run it

```bash
cd Lectures/Lecture03_PoliticalImplicationsOfEnergyGeneration
python3 ../../tools/fetch_lecture_media.py manifest_blair_mountain.json \
    --out images --max-width 1600 \
    --inject-qmd lecture03_battle_of_blair_mountain.qmd
```

`--inject-qmd` fills the 22 `<!-- IMG: name.jpg -->` markers already placed in the
deck with a real Quarto figure, and drops **every** alt-text candidate in beside it as
a comment: my hand-written one (used as the live `fig-alt`), the Commons
structured-data caption, the file-page description, and the `alt=` text any Wikipedia
article uses for that file. Edit the `fig-alt=` by hand from those; re-running the
script preserves your edits and only refreshes the candidate list. See
`tools/README_media.md` for the details.

Add `--dry-run` first if you want to see what it would do without writing anything.
`CREDITS.md` / `credits.json` in `images/` will be **overwritten or appended** — back
up the existing ones first if you want to keep the AC/DC credits separate:

```bash
cp images/CREDITS.md images/CREDITS_acdc.md
```

## Confidence tiers

I could not reach Wikimedia from here, so **no file title below is verified.** They're
graded:

**High confidence (well-known LoC / Detroit Publishing, almost certainly PD):**
`breaker_boys`, `teddy_roosevelt`, `rough_riders`, `ida_b_wells`, `kkk_parade_1928`

**Likely fine, title may be slightly off:** `rockefeller`, `mother_jones`,
`ida_tarbell`, `panam_electric_tower`, `pullman`, `sid_hatfield`, `lehigh_canal`,
`susquehannock`

**MUST VERIFY — these are the ones I expect to fail:** `blair_mountain_miners`,
`blair_mountain_troops`, `bill_blizzard`, `don_chafin`, `lackawanna_steel`,
`coal_scrip`, `company_store`, `lead_belly`

Blair Mountain photographs are the weak spot: many circulating copies live in the
**WV State Archives**, which is *not* automatically free, and English Wikipedia hosts
some of them under fair use. The script will flag those `!! NON-FREE / CHECK` and skip
them — that's the correct outcome, don't override it with `--allow-nonfree`.

## Discovery mode for the failures

```bash
python3 ../../tools/fetch_lecture_media.py --from-article "Battle of Blair Mountain"
python3 ../../tools/fetch_lecture_media.py --from-article "West Virginia coal wars"
python3 ../../tools/fetch_lecture_media.py --from-article "Ludlow Massacre"
python3 ../../tools/fetch_lecture_media.py --from-article "Company town"
python3 ../../tools/fetch_lecture_media.py --from-article "Lead Belly"
python3 ../../tools/fetch_lecture_media.py --from-article "Pan-American Exposition"
```

Paste me the FREE ones and I'll rewrite the manifest entries with correct titles and
matching alt text.

## Two judgment calls for you

1. **`kkk_parade_1928`** — the 1928 Pennsylvania Avenue parade photo is public domain
   and is genuinely the most effective image for that slide, because it is broad
   daylight in the capital and nobody is hiding. It is also a room full of first-years.
   Your call whether to show it, describe it, or use a membership-map graphic instead.
2. **Starbase** — I left it out deliberately. SpaceX imagery licensing is mixed and the
   obvious Commons candidates are uncertain. A screenshot of the Texas Tribune
   incorporation-vote story, or a plain 212–6 number on a UB-branded slide, is cleaner
   and carries no license risk.

## Still missing a figure

No good free image for **John Henry** — the well-known Talcott WV statue is a modern
sculpture and likely still under copyright even as a photograph. Options: PD sheet-music
covers of the ballad, or a Lewis Hine convict/tunnel-labor photograph, or just the
lyric set as type.
