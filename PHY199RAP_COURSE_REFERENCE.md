# PHY199-RAP: Energy in the 21st Century — Course Reference

> Read this at the start of each task. It captures the syllabus so work stays aligned with the course.

## Course at a Glance
- **Title:** PHY199-RAP — Energy in the 21st Century (UB Seminar, 1st-year students)
- **Instructor:** Dr. Salvatore Rappoccio (he/they) — "Sal". Office: 335 Fronczak Hall. Tel: 645-6250. Email: srappoc@buffalo.edu
- **Homepage:** ublearns.buffalo.edu
- **Textbook:** None. Material is from handouts and lectures.
- **Scope:** Physics of energy generation (mechanical, atomic, nuclear); history of energy production/consumption; anthropogenic climate change; supply chains and their impacts on ethnic/social groups; geopolitics of energy; 20th-century tech/social change; energy challenges in the age of AI; social justice throughout.

## What This Project Is For
Per project instructions: **gather resources, make slide decks, and do simple calculations.** Deliverables are typically research, slides (.pptx), and lightweight physics/energy math.

## Grading
- Participation: 20% (answer 80% of in-class questions = 100%; lowest 20% dropped for absences)
- In-class quizzes / homework: 20% (homework assigned but ungraded; quizzes based on it; lowest 20% dropped)
- Midterm: 30% (Week 9, 19-Oct)
- Final presentation: 30%

### Final Presentation Breakdown (30%)
- Proposal: 5% (due Week 8, ~one month before presentations)
- Slides: 10%
- Delivery: 10%
- Answering questions: 5%
- Format: 10-min talk + 5-10 min Q&A. Individual (no groups). Topic must be relevant to class. May include an optional 1-3 min self-made social media video (**made without AI**), counted within the 10 min.

### Grade Scale
A 93-100 (4.0) · A- 90-92.9 (3.67) · B+ 87-89.9 (3.33) · B 83-86.9 (3.0) · B- 80-82.9 (2.67) · C+ 77-79.9 (2.33) · C 73-76.9 (2.0) · C- 70-72.9 (1.67) · D+ 67-69.9 (1.33) · D 60-66.9 (1.0) · F ≤59.9 (0). Curved to the class; never curved down.

## Generative AI Policy (important for this project)
- AI is allowed for **study material** freely.
- AI is allowed for **final projects only with citation of all PRIMARY sources**, AND you must quantify the ecological/social implications of your AI use: **which AI model, which company, the source material the answer derives from, where the data centers are, and an estimate of the compute time.**
- Students face probing Q&A on their presented material — must actually understand it. Present material accordingly (understandable, defensible, well-sourced).
- No AI on quizzes/midterm (those are in-class).

## Course Schedule
| Wk | Date | Topic | Material / Skills | Assignment |
|----|------|-------|-------------------|------------|
| 1 | 24-Aug | Introduction | Syllabus, lecture notes | Syllabus quiz |
| 2 | 31-Aug | Energy generation | Electricity & magnetism, nuclear fission & fusion, levelized cost, the grid. Skill: note-taking | Academic Integrity course + quiz; share badge |
| 3 | 7-Sep | Political implications of energy | AC/DC Current Wars, anthropogenic climate change, Battle of Blair Mountain | Quiz on note-taking + wks 1-2 |
| 4 | 14-Sep | Political implications (cont.) | Death cost of electricity generation, public health costs of carbon. Skill: time management | Quiz on wk 3 |
| 5 | 21-Sep | Human costs of energy | Excerpts: *Hiroshima*, uranium mining & the Navajo, Love Canal. Films: Hiroshima: The Aftermath / Fat Man and Little Boy / Oppenheimer | Quiz on films + time mgmt |
| 6 | 28-Sep | Human costs (cont.) | Rare-earth mining for batteries, solar panel disposal. Skill: research | Quiz on wks 5-6 |
| 7 | 5-Oct | Computing and AI | Generative AI capability, water cost, chip production, the AI bubble, workplace automation | Quiz on research skills |
| 8 | 12-Oct | Future of energy | Population predictions, energy needs | **Research proposal due** |
| 9 | 19-Oct | Review | Review | **Midterm** |
| 10 | 26-Oct | How to give a good talk | Presenting to different audiences | — |
| 11 | 2-Nov | Communicating to non-specialists | Scientific communication | **Bibliography due** |
| 12 | 9-Nov | Special topics (class vote) | Student-relevant topics | Quiz on wks 10-11 |
| 13 | 16-Nov | Special topics (class vote) | Student-relevant topics | **First draft of presentation due** |
| 14 | 23-Nov | In-class work on presentations | — | Thanksgiving break |
| 15 | 30-Nov | Presentations | — | Presentations |
| 16 | 7-Dec | Presentations | — | Presentations |
| 17 | 14-Dec | Presentations | — | Presentations |

## Learning Outcomes (UB Seminar / SLI)
1. Critical thinking via multiple modes of inquiry — historical energy debates applied to 21st-century challenges.
2. Analysis, synthesis, critical reading — energy at mechanical/atomic/nuclear levels and transfer across the grid; assess pros/cons.
3. Effective research & study habits — note-taking, time management, low-stakes quizzes, participation discussions.
4. Identify/analyze disciplinary debates & deliberative discourse — AC/DC wars, Manhattan Project, AI, materials science.
5. Ethical issues — mining, water usage, power generation, waste, the "death cost."
6. Academic integrity — external resources incl. AI with proper citation + real-cost estimation of AI use.

## Slide Deck Format Convention (project memory)
- **Lectures are built in Powerpoint.** Each lecture lives in its own subfolder named `LectureXY_Description` (XY = zero-padded lecture number, Description = topic label), e.g. `Lecture01_Introduction/`.
- Each lecture folder already contains its own `lectureXX_topic.ppt` (the file to edit). Edit the existing pptx file.
- When AI helps build a lecture/deliverable, include the AI-usage disclosure (see Working Style Notes) — as a closing slide when appropriate, and report the token/energy/water estimate to Sal.
- Add all external sources as hyperlinks that include a 2-3 word fragment of the content

## Lecture-Building Workflow (project memory — how Sal and Claude collaborate)
- **Workflow changed 01-Oct-2026:** the qmd-content-quarry stage is retired. Claude now builds directly into each lecture's `lectureXX.pptx` (copied from `Lectures/lectureXX_topic.pptx`, renamed lowercase without the topic label) using python-pptx and the UB template's own named layouts — no separate qmd draft.
- **Sal provides an outline** with instructions for each lecture to Claude (when he has one ready; Claude can also draft an initial skeleton on request, as with Lecture 5).
- **Claude still fills the outline as a content quarry, just directly in the pptx.** Per outline topic: properly-cited PRIMARY sources (not just secondary summaries), first-year-level summaries, suggested figures (with license + attribution + pre-written alt text), and simple calculations — built straight into the deck's slides/speaker notes as a draft, not a finished deck.
- Sal owns final content; Claude's job is sourcing, drafting, alt text, and math.
- Each time Claude does an update, commit to git locally (see **Git & Repository Workflow** below for how commits vs. pushes actually work).

## Git & Repository Workflow (project memory — added 01-Oct-2026)
- Repo lives at `~/Claude/PHY199RAP` (the mounted project folder itself). Initialized 01-Oct-2026; remote `origin` = `git@github.com:rappoccio/PHY199RAP.git`.
- **Default branch is `main`, never `master`** — Sal's explicit instruction (the old term is rooted in racist terminology). Don't recreate a `master` branch.
- **Claude can commit locally but cannot push.** The mounted-folder VM (where Claude's `device_bash` runs) has no outbound internet/DNS at all — confirmed 01-Oct-2026 via a failed `ssh-keyscan`/`ssh -T git@github.com` (`Temporary failure in name resolution`). Same sandbox limitation already documented above for Wikimedia. So: Claude runs `git add` / `git commit` there after a real update, but **Sal pushes by hand** from his own Terminal: `cd ~/Claude/PHY199RAP && git push -u origin main` (after the first push, plain `git push` is enough).
- `.gitignore` covers: `.DS_Store`, `.obsidian/`, `_quarto_internal_scss_error.scss` (macOS/Obsidian/Quarto cruft); `Grading/` and any `Assignments/*Classlist_Export*.csv` / `*GradesExport*.xlsx` (student PII — **never** track grade/roster exports, FERPA); Office/editor lock files (`~$*`); Python `__pycache__/` and `*.pyc`.
- Root commit: `e227560` — "restarting the PHY199RAP workflow, and adding an overview of how to effectively use agentic AI" (01-Oct-2026). Covers the qmd-quarry retirement, the 8 cleaned-out lecture folders, the renamed template copies, and the Lecture 5 pptx skeleton (see Progress Log below). Pushed to `origin/main` same day.

## Sal's Deck Voice & Style (learned from Lecture 1 final)
Draft toward these so Sal's hand-pass is lighter:
- **Chronological spine with dated slide titles** ("435 Mya: Utica Shale", "1825–1900: The Erie Canal"), not thematic titles.
- **Recurring forward-reference tag** on early slides: "This will be relevant for our discussion about ___."
- **A running pop-culture motif** carried across the whole deck (Lecture 1 used Game of Thrones: White Walkers = climate change, AI = the zombie dragon, "Winter is coming", "Be like Arya"); xkcd comics welcome.
- **Blunt, funny, morally direct voice** — names injustice plainly (colonization, redlining, Church Rock vs. Three Mile Island on race), with editorial asides. Keep the physics rigorous underneath the jokes.
- **Real physics even in the "intro"** — Lecture 1 added the Four Forces, energy magnitudes, Faraday/turbine, batteries, and the EIA generation mix. Don't underweight the quantitative content.
- **Local Buffalo throughline** ties every theme to the city; **personal authenticity** (CMS/CERN, karate, his band) is a feature.
- **Lecture 1 is an overview — keep AI light here.** The deep AI material (goldfish/statelessness, watermarking coin-flip stats, the AI-cost disclosure capstone) was cut from Lecture 1 and belongs in **Week 7 (Computing & AI)**.

## Wikipedia / Wikimedia Media Workflow (project memory)
Wikipedia/Commons is an approved, level-appropriate source for this first-year seminar (ease of CC reuse). Rules:
- **Text:** summarize/paraphrase freely at first-year level, but treat Wikipedia as a *finding aid* — trace claims to the PRIMARY sources it cites, cite those, and still corroborate any `.gov` claim per the source-integrity rule.
- **Images:** every file needs an individual license check. Commons files are free (PD/CC0/CC BY/CC BY-SA) and reusable **with a per-image attribution line**. **Trap:** English Wikipedia also hosts non-free "fair-use" images (logos, many photos of living people) that are NOT reusable — prefer Commons PD/CC alternatives.
- **Tooling:** `tools/fetch_lecture_media.py` (stdlib-only) reads a per-lecture `manifest.json`, downloads each file, and writes `images/CREDITS.md` + `credits.json` with license, attribution, and alt text. It **flags and skips non-free files**. Claude prepares the manifest (titles + alt text + captions); Sal runs the script locally. See `tools/README_media.md`.
- **Sandbox limit (why the script exists):** Claude's Cowork sandbox and the mounted-folder VM have **no route to Wikimedia** (image servers + API blocked; the local VM has no outbound internet at all), and WebFetch reaches Wikipedia *article* pages only. So Claude can summarize articles and prepare manifests/alt text, but **cannot download images or auto-read licenses** — the local script closes that gap.

## Working Style Notes
- Audience is first-year students; keep explanations accessible, tie to social-justice / human-cost / ethical framing that recurs in the course.
- For slide decks: individual talks, ~10 min, understandable enough to defend in Q&A.
- For calculations: keep them "simple" — levelized cost, death cost, energy/power estimates, compute/water costs of AI, etc.
- When AI is used in any deliverable that could become coursework, include the required AI-cost disclosure (model, company, sources, data-center location, compute estimate).
- Cite PRIMARY sources and Wikipedia articles with 2-3 word fragments in a hyperlink.
- **Source integrity (per Sal, Aug 2026):** Do NOT let any factual claim rest on a US federal (.gov) page alone. Given the current administration's interference with federal science, treat .gov sources — especially science/environment agencies (EPA, and note NASA/NOAA are also federal) — as potentially altered, scrubbed, or reframed. Corroborate every .gov factual claim with an INDEPENDENT source: peer-reviewed literature, academic institutions, nonprofits, or international bodies (IPCC, WMO, IJC). For climate/environment, prefer international/peer-reviewed anchors and use federal pages only as secondary corroboration. Archival federal record (NARA, presidential libraries) is lower-risk but still pair it with academic/nonprofit sources.
- **Image policy (per Sal, Aug 2026):** Do NOT add fabricated or AI-generated *realistic* images, or any AI-generated/altered depiction of real people, places, artworks, or events, unless Sal explicitly asks. **Cartoon-level / schematic diagrams that Claude draws for explanatory purposes ARE allowed** (e.g., a labeled Pangaea cartoon, a concept schematic) — keep them clearly diagrammatic, not photorealistic. For anything depicting a real person/artwork/photo (e.g., historical portraits), use only REAL, properly-licensed images (public domain or licensed) with attribution + citation. Charts/plots of real data are fine. When unsure, ask Sal.

## Trusted Media Creators (project memory)
Creators/handles Sal has vetted as reputable for Gen Z–friendly explainers. Prefer these when adding YouTube/short-form (Instagram/TikTok/YouTube) media; this list grows as we go. Handles are as Sal provided — confirm the exact profile/video URL at build time.

**Physics**
- learnwithsherlock
- particleclara
- cern (CERN — official)
- alice_experiment · cmsexperiment · atlasexperiment · lhcbexperiment (the four big LHC experiments — official)
- astro.alexandra
- blitzphd
- ellecordova

**AI**
- askcatgpt
- alberta.tech
- cahdoria
- kylascan
- evaroyt

**Math**
- 3Blue1Brown (Grant Sanderson) — rigorous math & neural-network / LLM visual explainers

**Trusted "traditional" communicators**
- Brian Greene
- Brian Cox

**Sal's personal connections (adds credibility — can mention his direct ties):**
- Sal is a **CMS experimentalist** (CMS = one of the big LHC experiments at CERN) — he can speak to CERN/CMS/ATLAS/ALICE/LHCb material firsthand.
- **particleclara** is a personal friend of Sal's.
- Sal has worked with many of the above, including **Brian Cox**.
- When useful, lean into this authenticity ("I work on CMS…", "a friend of mine makes these…") — it resonates with first-years.

## Progress Log (for the next session — "feed the goldfish")
- **Lecture 1 (Introduction) — COMPLETE & DELIVERED.** True final is Sal's hand-built `Lecture01_Introduction/lecture01.pptx` (66 slides); the `lecture01.qmd` was the draft/quarry. In the final, Sal cut the deep AI section (goldfish/watermarking/AI-disclosure) — that moves to Week 7 — and added a chronological timeline spine, a Game-of-Thrones motif, more physics (Four Forces, energy magnitudes, Faraday/turbine, battery, EIA mix), and many Wikimedia figures with on-slide attributions.
  - Tuition math: verified model in `Lecture01_Introduction/UB_loan_pay_vs_defer.xlsx`; cost slides show **total cost of the loan over the 10-yr repayment term** per scenario (pay-in-school vs full deferral), at 6.52% and 9.84%, fees included.
  - Images live in `Lecture01_Introduction/images/`: `pangaea.gif` (Scripps Institution of Oceanography), `red_jacket.jpg` (Charles Bird King, PD), `joseph_brant.jpg` (George Romney 1776, PD). (`pangaea.svg` is an old unused cartoon.)
  - Open/optional: pin exact trusted-creator video URLs (named in speaker notes as "verify at build"); optional fix of the pre-existing `ub.scss` css-vars warning (cosmetic — theme still applies).
- **Session 2 (this session) — workflow + tooling captured.** Diffed Lecture 1's final pptx vs the qmd draft and recorded the collaboration model: qmd = content quarry Claude populates, pptx = Sal's hand-assembled final. Added three reference sections: **Lecture-Building Workflow** (rewritten), **Sal's Deck Voice & Style**, and **Wikipedia / Wikimedia Media Workflow**. Built `tools/fetch_lecture_media.py` (+ `sample_manifest.json`, `README_media.md`): a stdlib-only local downloader that fetches Wikimedia figures with license/attribution/alt-text capture and flags non-free files. **Reason it's local:** the Cowork sandbox and the mounted-folder VM have no route to Wikimedia (and the VM has no outbound internet at all); Claude preps manifests, Sal runs the script. Live Wikimedia API path not yet tested end-to-end.
- **Session 3 (this session) — Lecture 2 (Energy Generation) DRAFTED & DELIVERED as a quarry.** Populated `Lecture02_EnergyGeneration/lecture02.qmd` (6 sections / 33+ slides): note-taking skill (Cornell method, process-don't-transcribe), E&M (Ørsted→Faraday→Maxwell, "every plant is one machine"), fission & fusion (binding-energy curve, worked "gram of uranium" calc, NIF 2022 + ITER now ~2034/2039), LCOE (worked 1-MW-solar ≈ $34/MWh, **Lazard June 2025** table, what LCOE hides), and the grid (I²R→AC, 60 Hz balancing, 2003 Northeast blackout, NYISO). All calcs re-checked; every claim carries a primary source; .gov claims corroborated.
  - **Media:** prepped `manifest.json`; Sal ran `fetch_lecture_media.py`. 6 figures placed in `images/` with verified licenses (oersted, faraday — both PD; binding_energy_curve PD; sun PD/NASA; fission_chain **CC BY-SA 4.0**; transmission_towers **CC BY-SA 3.0** — CC attributions on-slide). Faraday-ring & 2003-blackout satellite were skipped (not found/uncertain license).
  - **Social media added at end:** a **vetted-creators** section (3Blue1Brown, Elle Cordova, particleclara/Clara Nellist [Sal's friend], CERN, Brian Cox; Veritasium/Kurzgesagt marked secondary) + a **separate "creators to vet"** section broadening the net, esp. LCOE/economics (Engineering with Rosie's LCOE video, Our World in Data, Volts, Just Have a Think, Undecided, Ziroth; Practical Engineering for the grid; Illinois EnergyProf for nuclear; Justin Sung/Benjamin Keep for note-taking).
  - **Course-values note (per Sal, this session):** do **not** perform false "balance" by giving fossil-fuel advocacy equal time — which power source is cheapest (LCOE) and that fossil combustion drives warming are settled *empirical* questions, not contested values. Real scrutiny = per-creator rigor + primary sourcing + watching for hype, not manufactured counter-sides. (Fixed a false-balance line in lecture02.qmd accordingly.)
- **Tooling upgrade (Session 4): `fetch_lecture_media.py` now harvests upstream alt text and injects figures into the qmd.** Per Sal's request, it collects **all three** places Wikimedia keeps alt-ish text — the file-page description (`extmetadata.ImageDescription`), the Commons **structured-data caption** (Wikibase label on the file's M-id), and the **`alt=` attribute used where an article embeds the file** (via `list=imageusage` + wikitext parse; usually the best of the three). All three go into `CREDITS.md`/`credits.json` and a paste-ready `images/ALT_BLOCKS.md`.
  - New flags: **`--inject-qmd FILE.qmd`** fills `<!-- IMG: name.jpg -->` markers with a real Quarto figure `![caption](path){fig-alt="..."}` plus every alt candidate as an editable comment; `--no-harvest` skips the extra API calls; `--force-alt` overwrites hand-edited alt text.
  - **Claude's alt stays primary**, upstream sits beside it for Sal to swap in by hand. **Injection is idempotent and preserves hand-edited `fig-alt`** across re-runs (reports how many it kept). Markers naming files outside the current manifest are left alone, so the AC/DC and Blair Mountain manifests can share one qmd.
  - Manifests gained a **`note` field** for "verify this title"-type reminders, which is kept OUT of the on-slide caption (it was leaking into captions before).
  - **Quarto gotcha documented:** `![text](img)` renders `text` as a visible *caption*, NOT alt text — alt must go in `fig-alt=`. The script does this correctly.
  - Bug found & fixed while testing: this Python's `re.escape` escapes spaces, which corrupted the space/underscore-tolerant file-name regex. Offline unit tests + a monkeypatched end-to-end run (network faked) both pass; **the live Wikimedia path is still untested** since neither the sandbox nor the mounted VM can reach Wikimedia. Backup at `tools/fetch_lecture_media.py.bak`.
- **Tooling (Session 4, cont.): keyword search + a PD bug fix in `fetch_lecture_media.py`.** After Sal's first run, 14 of 22 guessed `File:` titles did not resolve — the normal failure mode, since exact Commons titles are unguessable. Added **`--search WORDS`** (searches the Commons File namespace by keyword) alongside the existing `--from-article`, and **`--json`** on either, which prints a **manifest skeleton of just the FREE results** with the upstream file description pre-filled as draft alt text. Also **fixed `is_free()`**: en.wikipedia-hosted public-domain files tagged only as `PD-US` / `PD-1923` / `PD-USGov` (no machine-readable license) were being flagged NON-FREE and skipped — `bill_blizzard.jpg` was a false positive. Fair-use detection is unaffected (verified with an 8-case offline test).
  - **`tools/discover_blair_media.sh`** runs all 17 outstanding searches in one go: `bash ../../tools/discover_blair_media.sh | tee discovery.txt`.
  - **Confirmed for the record:** Claude cannot run discovery itself. The container's proxy returns 403 for `commons.wikimedia.org`, `en.wikipedia.org/w/api.php` and `upload.wikimedia.org`; WebFetch reaches only canonical `/wiki/` article URLs and **strips image URLs from the markup**, so file titles are not recoverable that way either. The mounted VM has no outbound internet. **Discovery must run in Sal's own terminal** — this is exactly why the script exists.
- **Planned future session — "Are fossil fuels actually cheaper, or just heavily subsidized?" (Sal's idea, this session).** Political economy of fossil subsidies + lobbying; natural bridge from L2's LCOE caveats into Weeks 3–4. Resource quarry started at `scratch_material/FossilFuelSubsidies/RESOURCE_BRIEF.md` — data spine (IMF 2022 record **~$7T** total / **~$1.3T** explicit; OpenSecrets US oil & gas lobbying **$124.4M** in 2022), the explicit-vs-implicit nuance for Q&A defensibility, a 10-slide skeleton, simple calcs, and where it sits in the course. Not yet scheduled.
- **Session 4 (15-Sep-2026) — Lecture 3 PART 2 (Battle of Blair Mountain) DRAFTED as a quarry.** Rewrote `Lecture03_.../lecture03_battle_of_blair_mountain.qmd` (was just a stale copy of the AC/DC header) into 25 slides across 5 sections per Sal's outline: (1) post-Civil-War industrialization + Vanderbilt/Rockefeller/Morgan, (2) why coal — anthracite, Lehigh Valley, the Steel Belt, plus the Susquehannock dispossession that preceded it, (3) the Coal Wars → Matewan → Blair Mountain → "the oligarchy won" → Teddy Roosevelt with his colonial asterisks, (4) company towns then (scrip, Pullman) and now (Starbase TX, California Forever, Praxis, "Freedom Cities"), (5) Muckrakers, labor songs, John Henry/Lead Belly and convict leasing, and the second KKK vs. the integrated miners' army. Old file backed up as `lecture03_battle_of_blair_mountain_backup_20260915_*.qmd`.
  - **Buffalo throughline found (strong one):** TR became president **in Buffalo, 14-Sep-1901**, after McKinley was shot at the Pan-American Exposition — a fair lit by **AC power from Niagara**, i.e. the War of the Currents settled as set dressing — one year before he forced Morgan to the table in the 1902 anthracite strike. Also **Lackawanna Steel moved Scranton → Buffalo, 1899-1902, partly to escape a newly-unionized workforce**; Lackawanna NY is named for Lackawanna PA.
  - **Motif suggested (Sal to accept/kill):** *The Hunger Games* — District 12 is an Appalachian coal company town, Peacekeepers = mine guards, mockingjay pin = the red bandana. Tagged `[MOTIF]` in the qmd.
  - **Contested number flagged on-slide, deliberately:** Blair Mountain miner deaths are 50-100 (Wikipedia) vs ~16 confirmed (WV Mine Wars Museum). Left as an explicit research-skills teaching moment rather than picking one.
  - **Simple calc for the day:** scrip discount — $5.00/day paid in scrip, redeemed at 25% off elsewhere = $3.75 real, ~$375/yr taken (≈3 months' earnings).
  - **PPTX BUILT (Session 4).** Per Sal's preference, slides were **appended onto the existing `lecture03_battle_of_blair_mountain.pptx` with python-pptx using the UB template's own named layouts** (Divider Slide / 1-Column Bulleted List / 1-Column Text + Photo), NOT rendered fresh from quarto — this is what avoids PowerPoint's "repair" prompt. Deck is now **33 slides, 25 with speaker notes**; `validate.py --original` passes; visual QA done via LibreOffice render. Backup of the pre-append file: `lecture03_battle_of_blair_mountain_titleonly_backup_*.pptx`.
  - **Build script kept** at `Lectures/Lecture03_.../` workflow notes: content lives as a Python list of slide dicts; re-runnable. Gotchas hit: the UB table style renders **white bold text on light fills**, so table cell colours must be set explicitly (white on the blue header row, near-black on body rows) or the tables are unreadable; and a `**bold**` span must not straddle a `\n` inside a table cell or the asterisks print literally.
  - **MEDIA COMPLETE (Session 4).** Second run with `--search`-derived titles: **24/24 fetched, zero failures**, all free (21 PD, 1 CC BY 2.0, plus the PD-US fix). Deck now carries **24 figures across 33 slides**, several slides with 2 and the Blair Mountain slide with 4 (map, machine-gun nest, miner, and the Washington Times front page reading "Aviators will drop bombs on marchers").
  - **Lesson learned - ALWAYS eyeball fetched images before use.** A correct file title does not mean the right picture. Verified all 24 on a contact sheet; **six of Claude's pre-written alt texts described something other than what arrived** (the "airfleet" file is a newspaper front page, not photos of planes; "lehigh_canal" is an engraving not a photo; "lackawanna_steel" is a mill interior not an exterior; "breaker_boys" is a posed group portrait not the in-breaker Hine shot; "pullman" is a modern colour photo of surviving houses). All six corrected in the manifest, `credits.json` and the injected `fig-alt` values. Two LoC/HAER scans were cropped to remove colour-calibration bars and film edges (`rough_riders.jpg`, `lackawanna_steel.jpg`).
  - **`pullman.jpg` is CC BY 2.0** - on-slide attribution "Photo Richie Diesterheft, CC BY 2.0" is already in its caption; keep it if the slide is reused.
  - **Don Chafin: no free portrait exists.** Every hit was unrelated. The Blair Mountain slide uses the map + machine-gun nest instead.
  - **Media:** `manifest_blair_mountain.json` (22 entries, separate from the AC/DC `manifest.json`) + `MEDIA_NOTES_blair_mountain.md` with confidence tiers and discovery commands. 22 `<!-- IMG: name.jpg -->` markers placed in the qmd at the right slides. Sal's FIRST run: 5 usable images (rockefeller, mother_jones, teddy_roosevelt, ida_b_wells + a WRONG ida_tarbell), **14 titles did not resolve**, 3 flagged non-free. **`ida_tarbell.jpg` is NOT Ida Tarbell — it is a photo of a house in the snow (the Tarbell homestead); do not use it.** The alt-harvest worked (Commons structured-data captions came through). Remaining figures still needed — `manifest.json` still only covers the AC/DC half. Five `FIGURE TO ADD` markers with proposed Commons searches + pre-written alt text are in the qmd; a new manifest can be prepped on request.
  - Verified render with `pandoc -t pptx` (quarto is not installed in the mounted-folder VM, so Sal renders locally).
- **Session 5 (01-Oct-2026) — Workflow restart + Lecture 5 (Computing & AI) pptx skeleton built.** Sal retired the qmd-quarry stage; Claude cleaned out the stale `.qmd`/`title-slide.html`/`ub.scss` scaffold (and a stray `ub_py410_datascience.pptx`) from Lecture05_ComputingAndAI, 06_HumanCostsOfEnergyGeneration, 08_FutureOfEnergyGeneration, 09_Review, 10_HowToGiveAGoodTalk, 11_HowToCommunicateToNonSpecialists, 12 & 13_SpecialTopicsVotedByClass, then copied `Lectures/lectureXX_topic.pptx` into each as `lectureXX.pptx`.
  - **Lecture 5 built out as a 14-slide skeleton** directly in `lecture05.pptx` via python-pptx + the UB template's named layouts (Divider / 1-Column Bulleted List / 1-Column Text), topic: "Working With Agentic AI (Without Losing Your Sources)." Flow: 2017 Transformer origins → Nov-2024 Model Context Protocol / agentic toolbelts → Anthropic's workflow-vs-agent distinction → "it's a goldfish" statelessness → citation-fabrication risk → real energy/water/chip cost → a worked Wh calc using *this build session* as the example → the AI bubble → a practical "how to actually use this thing" slide → a meta "Case Study: This Slide Deck" slide → a filled-in AI Usage Summary disclosure → a Takeaway.
  - **8 primary sources, each a 2–3-word hyperlink fragment per convention:** Vaswani et al., "Attention Is All You Need" (arXiv:1706.03762, 2017); Anthropic's MCP announcement (Nov 2024) and "Building Effective Agents" post; Linardon et al., JMIR Mental Health 2025;12:e80371 (19.9% of LLM-generated citations fully fabricated); Hannah Ritchie's AI-electricity analysis (~0.3 Wh/large query, May 2026); plus the course's existing water-cost (NPR) / chip-production / AI-bubble (Wikipedia) links. Full citations are in each slide's speaker notes.
  - **Git repo initialized this session** — see **Git & Repository Workflow** above. First commit `e227560` pushed to `origin/main`.
  - **Still to do on Lecture 5:** Sal's hand-pass (cut to ~10 min, pick the jokes, make it sound like him); the other 7 copied decks (`lecture06.pptx`, `lecture08.pptx`–`lecture13.pptx`) are still just the 2-slide stub, not yet built out.
- **Next up:** Lecture 3 — Political implications of energy (AC/DC Current Wars, anthropogenic climate change, Battle of Blair Mountain; skill/quiz: note-taking + wks 1–2). The fossil-subsidies session could open or feed Wk 3.

## Key Admin
- Communication: use university email; clear subject line "PHY199-RAP …"; allow 48h (excl. weekends/holidays).
- Absence policy: adults, trusted; system drops lowest 20% of quizzes/participation to cover absences.
- Note: syllabus lists 2016 resignation dates (drop Feb 1; resign Apr 15) — likely a stale template; current term runs Aug–Dec (semester start 24-Aug).


## Technical details for the human

* Get media images from a `Lecture` directory: `python3 ../../tools/fetch_lecture_media.py manifest.json --out images`


 