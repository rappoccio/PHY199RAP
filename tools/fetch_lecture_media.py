#!/usr/bin/env python3
"""
fetch_lecture_media.py
======================
Download Wikimedia Commons / Wikipedia media (and, optionally, other direct URLs)
for a PHY199RAP lecture, capturing the LICENSE, a ready-to-cite ATTRIBUTION string,
and ALT TEXT for every file, into a per-lecture images/ folder.

WHY THIS SCRIPT EXISTS
----------------------
Claude's Cowork sandbox (and the mounted-folder VM) have no route to Wikimedia's
servers, so Claude can prepare the manifest + attributions + alt text but cannot pull
the image bytes. This script runs in YOUR OWN terminal, which has normal internet,
and does the download for you. Standard library only -- no `pip install` needed.

USAGE
-----
  # Download everything named in a manifest into ./images (next to the lecture .qmd):
  python3 fetch_lecture_media.py manifest.json

  # Choose the output folder and cap the long edge at 1600 px (good for slides):
  python3 fetch_lecture_media.py manifest.json --out images --max-width 1600

  # See what a Wikipedia ARTICLE offers, with each image's license, before committing:
  python3 fetch_lecture_media.py --from-article "Utica Shale"

  # Re-run safely: already-downloaded files are skipped unless you pass --force.
  python3 fetch_lecture_media.py manifest.json --force
  python3 fetch_lecture_media.py manifest.json --dry-run   # plan only, no downloads

MANIFEST FORMATS (auto-detected by extension)
---------------------------------------------
  *.json : a JSON list of entry objects (see sample_manifest.json)
  *.txt  : one Commons/Wikipedia file title or URL per line
           (blank lines and lines starting with # are ignored)

JSON ENTRY FIELDS
-----------------
  file    : Commons file title ("File:Foo.jpg") OR a commons/wikipedia file-page URL
  url     : a DIRECT media URL for a non-Wikimedia source (skips the API); needs `credit`
  name    : desired local filename (otherwise derived from the source name)
  alt     : alt text for this image (recorded in CREDITS.md and credits.json)
  caption : the on-slide caption (recorded too)
  credit  : manual attribution string -- REQUIRED for `url` (non-Wikimedia) entries

OUTPUTS (into the --out folder)
-------------------------------
  <image files>
  CREDITS.md    : human-readable, per image -- filename, source, license, attribution, alt, caption
  credits.json  : the same, machine-readable (handy for scripting the .qmd alt text)

Non-free or license-uncertain files are NEVER downloaded silently: they are reported
with a "!! NON-FREE / CHECK" marker and skipped unless you pass --allow-nonfree.

Author: prepared for PHY199-RAP (Energy in the 21st Century). Public domain / CC0.
"""

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

# Wikimedia asks all API clients to send a descriptive User-Agent with contact info.
# https://foundation.wikimedia.org/wiki/Policy:Wikimedia_Foundation_User-Agent_Policy
USER_AGENT = ("PHY199RAP-lecture-media/1.1 "
              "(University at Buffalo seminar; contact: srappoc@buffalo.edu)")

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
ENWIKI_API = "https://en.wikipedia.org/w/api.php"

# License short-names / machine-names that mean "NOT freely reusable" -- trip the flag.
NONFREE_PAT = re.compile(
    r"(non[- ]?free|fair[- ]?use|all rights reserved|screenshot|"
    r"copyright(?!ed:\s*false)|©)", re.I)
FREE_MACHINE_PREFIXES = ("cc-", "cc0", "pd", "publicdomain", "no restrictions")

POLITE_DELAY = 0.5  # seconds between API/download calls -- be a good citizen


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #
def _req(url):
    return urllib.request.Request(url, headers={"User-Agent": USER_AGENT})


def api_get(endpoint, params, tries=3):
    """GET a MediaWiki API endpoint, returning parsed JSON (with simple backoff)."""
    params = dict(params, format="json")
    url = endpoint + "?" + urllib.parse.urlencode(params)
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(_req(url), timeout=30) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(POLITE_DELAY * (i + 1) * 2)
    raise RuntimeError(f"API request failed after {tries} tries: {last}\n  {url}")


def strip_html(value):
    """extmetadata values are HTML fragments; reduce to clean single-line text."""
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", " ", value)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_title(entry_file):
    """Accept a bare 'File:Foo.jpg', a 'Foo.jpg', or a full file-page URL."""
    s = entry_file.strip()
    if s.startswith("http"):
        path = urllib.parse.urlparse(s).path
        s = urllib.parse.unquote(path.rsplit("/", 1)[-1])
    if not s.lower().startswith("file:"):
        s = "File:" + s
    return s


def safe_filename(name):
    name = urllib.parse.unquote(name)
    name = name.replace("File:", "").replace("file:", "")
    name = name.replace(" ", "_")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return re.sub(r"_+", "_", name).strip("_") or "media"


def build_attribution(meta):
    """Compose a citation line from extmetadata fields."""
    artist = strip_html(meta.get("artist"))
    lic = meta.get("license_short") or meta.get("license_machine") or "see source"
    src = meta.get("descriptionurl", "")
    bits = []
    if artist:
        bits.append(artist)
    bits.append(lic)
    line = " — ".join(bits) if bits else lic
    if src:
        line += f". Source: {src}"
    return line


# --------------------------------------------------------------------------- #
# Wikimedia lookups
# --------------------------------------------------------------------------- #
def imageinfo(endpoint, title, max_width):
    iiprop = "url|size|mime|extmetadata"
    params = {
        "action": "query", "titles": title, "redirects": "1",
        "prop": "imageinfo", "iiprop": iiprop,
    }
    if max_width:
        params["iiurlwidth"] = str(max_width)
    data = api_get(endpoint, params)
    pages = data.get("query", {}).get("pages", {})
    for _pid, pg in pages.items():
        if "imageinfo" not in pg:
            return None
        ii = pg["imageinfo"][0]
        em = ii.get("extmetadata", {})

        def emv(k):
            return em.get(k, {}).get("value", "")

        meta = {
            "title": pg.get("title", title),
            "pageid": pg.get("pageid"),
            "original_url": ii.get("url", ""),
            "thumb_url": ii.get("thumburl", ""),
            "thumb_width": ii.get("thumbwidth"),
            "descriptionurl": ii.get("descriptionurl", ""),
            "mime": ii.get("mime", ""),
            "size": ii.get("size"),
            "width": ii.get("width"),
            "height": ii.get("height"),
            "license_short": strip_html(emv("LicenseShortName")),
            "license_machine": strip_html(emv("License")),
            "license_url": strip_html(emv("LicenseUrl")),
            "artist": emv("Artist"),
            "credit": strip_html(emv("Credit")),
            "usage_terms": strip_html(emv("UsageTerms")),
            "attribution_required": strip_html(emv("AttributionRequired")),
            "copyrighted": strip_html(emv("Copyrighted")),
            # upstream alt-ish text #1: the file page's own description
            "image_description": strip_html(emv("ImageDescription")),
        }
        return meta
    return None


def is_free(meta, host):
    machine = (meta.get("license_machine") or "").lower()
    short = (meta.get("license_short") or "").lower()
    if machine.startswith(FREE_MACHINE_PREFIXES):
        return True
    if NONFREE_PAT.search(short) or NONFREE_PAT.search(meta.get("usage_terms", "")):
        return False
    if "public domain" in short or short.startswith("cc"):
        return True
    # en.wikipedia states many public-domain files only as a short tag
    # ("PD-US", "PD-1923", "PD-USGov") with no machine-readable license, which
    # used to fall through to the enwiki branch below and read as non-free.
    if re.match(r"\s*(pd\b|pd-|public[ -]?domain|cc0|no restrictions)", short):
        return True
    # Commons only accepts free content; treat an unknown-license Commons file as free.
    if host == "commons" and machine:
        return True
    return False if host == "enwiki" else bool(machine)


def resolve_wikimedia(title, max_width):
    """Look on Commons first, then English Wikipedia (where non-free files live)."""
    meta = imageinfo(COMMONS_API, title, max_width)
    host = "commons"
    if meta is None:
        time.sleep(POLITE_DELAY)
        meta = imageinfo(ENWIKI_API, title, max_width)
        host = "enwiki"
    if meta is None:
        return None
    meta["host"] = host
    meta["free"] = is_free(meta, host)
    return meta


def choose_download_url(meta, max_width):
    """Prefer a scaled thumb for big rasters; keep originals for gif/svg."""
    mime = meta.get("mime", "")
    if mime in ("image/gif", "image/svg+xml") or not max_width:
        return meta["original_url"]
    if meta.get("thumb_url") and meta.get("width") and meta["width"] > max_width:
        return meta["thumb_url"]
    return meta["original_url"]


def download(url, dest):
    with urllib.request.urlopen(_req(url), timeout=60) as r, open(dest, "wb") as f:
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            f.write(chunk)
    return os.path.getsize(dest)


# --------------------------------------------------------------------------- #
# manifest loading
# --------------------------------------------------------------------------- #
def load_manifest(path):
    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise SystemExit("JSON manifest must be a list of entry objects.")
        return data
    entries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            entries.append({"file": line})
    return entries


# --------------------------------------------------------------------------- #
# upstream alt-text harvesting
#
# Three independent places Wikimedia keeps alt-ish text for a file:
#   1. the file page description   (extmetadata ImageDescription, grabbed above)
#   2. the Commons structured-data caption  (Wikibase label on the M-id)
#   3. the alt= attribute used where an article actually embeds the file
# (3) is usually the best of the three, because a human wrote it for a context.
# --------------------------------------------------------------------------- #
def sd_caption(pageid, host):
    """Commons structured-data caption(s) -- Wikibase labels on entity M<pageid>."""
    if not pageid or host != "commons":
        return ""
    try:
        data = api_get(COMMONS_API, {
            "action": "wbgetentities", "ids": "M%d" % int(pageid), "props": "labels",
        })
    except Exception:  # noqa: BLE001
        return ""
    ent = (data.get("entities") or {}).get("M%d" % int(pageid)) or {}
    labels = ent.get("labels") or {}
    for lang in ("en", "en-gb", "en-us"):
        if labels.get(lang, {}).get("value"):
            return labels[lang]["value"].strip()
    for v in labels.values():                      # any language beats nothing
        if v.get("value"):
            return v["value"].strip()
    return ""


_ALT_IN_LINK = re.compile(r"(?:^|\|)\s*alt\s*=\s*([^|\]]+)", re.I)


def _file_link_alts(wikitext, bare_name):
    """Pull alt= out of every [[File:<bare_name>|...]] link in one article."""
    # Wikitext treats spaces and underscores in file names as interchangeable,
    # so build the pattern from the name's words rather than escaping it whole.
    esc = r"[ _]+".join(re.escape(part) for part in re.split(r"[ _]+", bare_name.strip()))
    pat = re.compile(r"\[\[\s*(?:File|Image)\s*:\s*" + esc + r"\s*(\|.*?)?\]\]",
                     re.I | re.S)
    out = []
    for m in pat.finditer(wikitext):
        params = m.group(1) or ""
        a = _ALT_IN_LINK.search(params)
        if a:
            text = strip_html(a.group(1)).strip()
            if text and text not in out:
                out.append(text)
    return out


def article_alt_texts(title, limit=4):
    """Find mainspace en.wikipedia articles using this file; read their alt= text."""
    bare = title.split(":", 1)[-1]
    try:
        data = api_get(ENWIKI_API, {
            "action": "query", "list": "imageusage", "iutitle": title,
            "iunamespace": "0", "iulimit": str(limit),
        })
    except Exception:  # noqa: BLE001
        return []
    pages = [pg.get("title") for pg in (data.get("query", {}).get("imageusage") or [])
             if pg.get("title")]
    found = []
    for art in pages:
        time.sleep(POLITE_DELAY)
        try:
            rev = api_get(ENWIKI_API, {
                "action": "query", "titles": art, "prop": "revisions",
                "rvprop": "content", "rvslots": "main", "formatversion": "2",
            })
        except Exception:  # noqa: BLE001
            continue
        for pg in rev.get("query", {}).get("pages", []) or []:
            for r in pg.get("revisions", []) or []:
                body = ((r.get("slots") or {}).get("main") or {}).get("content", "")
                for a in _file_link_alts(body, bare):
                    found.append({"article": art, "alt": a})
    return found


def harvest_alts(meta):
    """Collect all three upstream sources for one file."""
    out = {"alt_file_description": meta.get("image_description", ""),
           "alt_sd_caption": "", "alt_article": []}
    try:
        out["alt_sd_caption"] = sd_caption(meta.get("pageid"), meta.get("host"))
    except Exception:  # noqa: BLE001
        pass
    time.sleep(POLITE_DELAY)
    try:
        out["alt_article"] = article_alt_texts(meta["title"])
    except Exception:  # noqa: BLE001
        pass
    return out


# --------------------------------------------------------------------------- #
# main actions
# --------------------------------------------------------------------------- #
def do_from_article(article, max_width, as_json=False):
    data = api_get(ENWIKI_API, {
        "action": "query", "titles": article,
        "generator": "images", "gimlimit": "200", "prop": "info",
    })
    pages = data.get("query", {}).get("pages", {})
    titles = sorted(pg["title"] for pg in pages.values() if pg.get("title"))
    _report(titles, max_width, as_json,
            f"# Images used on Wikipedia article: {article}")


def _report(titles, max_width, as_json, header):
    """Shared printer for both discovery modes."""
    print(header + "\n")
    if not titles:
        print("(nothing found -- try different words, or check the article title)")
        return
    free_hits = []
    if not as_json:
        print(f"{'FREE?':<7} {'LICENSE':<24} {'DIMENSIONS':<12} TITLE")
        print("-" * 84)
    for t in titles:
        time.sleep(POLITE_DELAY)
        try:
            meta = resolve_wikimedia(t, max_width)
        except Exception as e:  # noqa: BLE001
            if not as_json:
                print(f"{'ERR':<7} {str(e)[:24]:<24} {'':<12} {t}")
            continue
        if not meta:
            if not as_json:
                print(f"{'?':<7} {'(no imageinfo)':<24} {'':<12} {t}")
            continue
        lic = (meta["license_short"] or meta["license_machine"])[:24]
        if meta["free"]:
            free_hits.append((t, meta))
        if not as_json:
            dims = f"{meta.get('width','?')}x{meta.get('height','?')}"
            print(f"{('yes' if meta['free'] else 'NO'):<7} {lic:<24} {dims:<12} "
                  f"{t}  [{meta['host']}]")
    if as_json:
        # a manifest skeleton of just the free files, ready to paste and edit
        out = []
        for t, meta in free_hits:
            desc = meta.get("image_description", "")[:200]
            out.append({
                "file": t,
                "name": safe_filename(t).lower(),
                "alt": desc or "TODO: write alt text",
                "caption": "TODO: caption. " + (meta["license_short"] or ""),
            })
        print(json.dumps(out, indent=2, ensure_ascii=False))
    else:
        print(f"\n{len(free_hits)} free file(s). Re-run with --json to get a "
              f"manifest skeleton of just those.")


def do_search(query, max_width, limit=25, as_json=False):
    """Find Commons files by KEYWORD -- for when you don't know the exact title."""
    data = api_get(COMMONS_API, {
        "action": "query", "list": "search", "srsearch": query,
        "srnamespace": "6", "srlimit": str(limit),
    })
    titles = [h["title"] for h in (data.get("query", {}).get("search") or [])]
    _report(titles, max_width, as_json,
            f"# Commons file search: {query!r}")


def do_download(entries, out_dir, max_width, force, dry_run, allow_nonfree,
                harvest=True, inject_qmd=None, force_alt=False):
    os.makedirs(out_dir, exist_ok=True)
    records = []
    warnings = []
    for i, e in enumerate(entries, 1):
        alt = e.get("alt", "")
        caption = e.get("caption", "")
        note = e.get("note", "")

        # -- non-Wikimedia direct URL --------------------------------------
        if e.get("url") and not e.get("file"):
            fname = safe_filename(e.get("name") or e["url"].rsplit("/", 1)[-1])
            dest = os.path.join(out_dir, fname)
            credit = e.get("credit", "")
            if not credit:
                warnings.append(f"[{i}] {fname}: direct URL with no 'credit' -- add attribution manually.")
            rec = {"file": fname, "source": e["url"], "license": "(manual)",
                   "attribution": credit, "alt": alt, "caption": caption,
                   "note": note, "free": None}
            print(f"[{i}] {fname}  <- (direct)  {e['url']}")
            if not dry_run and (force or not os.path.exists(dest)):
                try:
                    n = download(e["url"], dest)
                    print(f"      saved {n:,} bytes")
                except Exception as ex:  # noqa: BLE001
                    warnings.append(f"[{i}] {fname}: download failed -- {ex}")
            records.append(rec)
            time.sleep(POLITE_DELAY)
            continue

        # -- Wikimedia file -------------------------------------------------
        title = normalize_title(e["file"])
        try:
            meta = resolve_wikimedia(title, max_width)
        except Exception as ex:  # noqa: BLE001
            warnings.append(f"[{i}] {title}: lookup failed -- {ex}")
            continue
        if not meta:
            warnings.append(f"[{i}] {title}: not found on Commons or en.wikipedia.")
            continue

        attribution = build_attribution(meta)
        fname = safe_filename(e.get("name") or meta["title"])
        dest = os.path.join(out_dir, fname)
        free = meta["free"]
        tag = "ok " if free else "!! NON-FREE / CHECK"
        print(f"[{i}] {fname}  [{tag}]  {meta['license_short'] or meta['license_machine']}  ({meta['host']})")

        rec = {
            "file": fname, "source": meta["descriptionurl"],
            "license": meta.get("license_short") or meta.get("license_machine", ""),
            "license_url": meta.get("license_url", ""),
            "attribution": attribution, "alt": alt, "caption": caption,
            "note": note, "mime": meta["mime"], "free": free,
        }
        if harvest:
            rec.update(harvest_alts(meta))
        if not free and not allow_nonfree:
            warnings.append(f"[{i}] {fname}: NON-FREE ({meta['license_short']}) -- skipped. "
                            f"Use a free alternative, or --allow-nonfree if you have rights.")
            records.append(rec)
            time.sleep(POLITE_DELAY)
            continue

        if dry_run:
            records.append(rec)
            time.sleep(POLITE_DELAY)
            continue
        if os.path.exists(dest) and not force:
            print("      exists -- skipping (use --force to overwrite)")
            records.append(rec)
            continue
        url = choose_download_url(meta, max_width)
        try:
            n = download(url, dest)
            print(f"      saved {n:,} bytes  <- {url}")
        except Exception as ex:  # noqa: BLE001
            warnings.append(f"[{i}] {fname}: download failed -- {ex}")
        records.append(rec)
        time.sleep(POLITE_DELAY)

    write_credits(out_dir, records)
    write_alt_blocks(out_dir, records)
    print(f"\nWrote {len(records)} record(s) -> {os.path.join(out_dir, 'CREDITS.md')}, "
          f"credits.json and ALT_BLOCKS.md")
    if inject_qmd:
        n, kept = inject_into_qmd(inject_qmd, records, out_dir, force_alt=force_alt)
        print(f"Injected {n} figure block(s) into {inject_qmd}"
              + (f" ({kept} hand-edited fig-alt preserved)" if kept else ""))
    if warnings:
        print("\n" + "=" * 60 + "\nWARNINGS / TO CHECK:")
        for w in warnings:
            print("  - " + w)


def write_credits(out_dir, records):
    with open(os.path.join(out_dir, "credits.json"), "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)
    lines = ["# Media credits\n",
             "_Generated by fetch_lecture_media.py. Verify every license before publishing._\n"]
    for r in records:
        lines.append(f"## `{r['file']}`")
        if r.get("free") is False:
            lines.append("> **!! NON-FREE / CHECK — do not reuse without confirming rights.**")
        lines.append(f"- **License:** {r.get('license','')}"
                     + (f" ({r['license_url']})" if r.get("license_url") else ""))
        lines.append(f"- **Attribution:** {r.get('attribution','')}")
        if r.get("source"):
            lines.append(f"- **Source:** {r['source']}")
        if r.get("alt"):
            lines.append(f"- **Alt text:** {r['alt']}")
        if r.get("caption"):
            lines.append(f"- **Caption:** {r['caption']}")
        if r.get("note"):
            lines.append(f"- **Note:** {r['note']}")
        if r.get("alt_sd_caption"):
            lines.append(f"- **Upstream (structured-data caption):** {r['alt_sd_caption']}")
        if r.get("alt_file_description"):
            lines.append(f"- **Upstream (file description):** {r['alt_file_description']}")
        for a in r.get("alt_article") or []:
            lines.append(f"- **Upstream (alt= on _{a['article']}_):** {a['alt']}")
        lines.append("")
    with open(os.path.join(out_dir, "CREDITS.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _q(text):
    """Make text safe inside a fig-alt="..." attribute."""
    return re.sub(r"\s+", " ", (text or "").replace('"', "'")).strip()


def _b(text):
    """Make text safe inside markdown ![...] bracket text."""
    return re.sub(r"\s+", " ", (text or "").replace("[", "(").replace("]", ")")).strip()


def _alt_candidates(rec):
    """All four candidates, labelled, longest-useful first. Claude's stays primary."""
    cands = []
    if rec.get("alt"):
        cands.append(("claude", rec["alt"]))
    if rec.get("alt_sd_caption"):
        cands.append(("sd-caption", rec["alt_sd_caption"]))
    if rec.get("alt_file_description"):
        cands.append(("file-desc", rec["alt_file_description"]))
    for a in rec.get("alt_article") or []:
        cands.append(("article-alt: %s" % a["article"], a["alt"]))
    return cands


def _figure_block(rec, out_dir, existing_alt=None):
    """One ready-to-edit Quarto figure + a comment listing every alt candidate."""
    name = rec["file"]
    path = "%s/%s" % (out_dir.rstrip("/\\"), name)
    cands = _alt_candidates(rec)
    primary = existing_alt if existing_alt else (rec.get("alt") or "")
    cap = _b(rec.get("caption") or "")
    img = '![%s](%s){fig-alt="%s"}' % (cap, path, _q(primary))
    if rec.get("free") is False:
        img = ("<!-- NON-FREE upstream, not downloaded - find a free substitute:\n"
               "     %s\n-->" % img)
    lines = ["<!-- ALT-BLOCK:BEGIN %s -->" % name, img, ""]
    lines.append("<!-- alt candidates for %s - edit the fig-alt= above by hand." % name)
    if rec.get("note"):
        lines.append("     [%-22s] %s" % ("manifest-note", _q(rec["note"])))
    if existing_alt:
        lines.append("     (fig-alt above is YOUR hand-edit; re-running preserves it "
                     "unless you pass --force-alt)")
    for label, text in cands:
        wrapped = _q(text)
        if len(wrapped) > 300:
            wrapped = wrapped[:297] + "..."
        lines.append("     [%-22s] %s" % (label, wrapped))
    if not cands:
        lines.append("     (no alt text found anywhere upstream - write one)")
    lines.append("-->")
    lines.append("<!-- ALT-BLOCK:END %s -->" % name)
    return "\n".join(lines)


def write_alt_blocks(out_dir, records):
    """A paste-ready file, in case you'd rather not inject into the .qmd."""
    parts = ["# Figure blocks with alt-text candidates\n",
             "_Generated by fetch_lecture_media.py. `[claude]` is used as the primary "
             "`fig-alt`; the others are what Wikimedia already had. Edit by hand._\n",
             "Paste a block into the .qmd, or put `<!-- IMG: <filename> -->` on the "
             "slide and re-run with `--inject-qmd <file.qmd>`.\n"]
    for r in records:
        parts.append("## `%s`\n" % r["file"])
        parts.append("```markdown\n" + _figure_block(r, out_dir) + "\n```\n")
    with open(os.path.join(out_dir, "ALT_BLOCKS.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(parts))


# A marker line, optionally followed by a block this script wrote earlier.
_MARKER_BLOCK = re.compile(
    r"^(?P<indent>[ \t]*)<!--[ \t]*IMG:[ \t]*(?P<name>[^\s>]+?)[ \t]*-->[ \t]*$"
    r"(?P<old>\n[ \t]*<!-- ALT-BLOCK:BEGIN (?P=name) -->"
    r".*?<!-- ALT-BLOCK:END (?P=name) -->)?",
    re.M | re.S)

_EXISTING_ALT = re.compile(r'fig-alt="(?P<alt>[^"]*)"')


def inject_into_qmd(qmd_path, records, out_dir, force_alt=False):
    """Fill every <!-- IMG: name.jpg --> marker with a figure block. Idempotent.

    Re-running refreshes the candidate list but KEEPS a fig-alt you edited by
    hand, unless force_alt. Markers naming a file that isn't in this manifest
    are left untouched, so two manifests can share one .qmd.
    """
    by_name = {r["file"]: r for r in records}
    with open(qmd_path, encoding="utf-8") as f:
        text = f.read()
    stats = {"injected": 0, "preserved": 0}

    def repl(m):
        name = m.group("name")
        rec = by_name.get(name)
        if rec is None:
            return m.group(0)
        indent = m.group("indent")
        existing_alt = None
        old = m.group("old")
        if old and not force_alt:
            ma = _EXISTING_ALT.search(old)
            if ma:
                prev = ma.group("alt").strip()
                # only "preserved" if a human changed it away from what we generated
                if prev and prev != _q(rec.get("alt") or ""):
                    existing_alt = prev
                    stats["preserved"] += 1
        block = _figure_block(rec, out_dir, existing_alt=existing_alt)
        block = "\n".join((indent + ln) if ln.strip() else ln
                          for ln in block.split("\n"))
        stats["injected"] += 1
        return "%s<!-- IMG: %s -->\n%s" % (indent, name, block)

    text = _MARKER_BLOCK.sub(repl, text)
    with open(qmd_path, "w", encoding="utf-8") as f:
        f.write(text)
    return stats["injected"], stats["preserved"]


def main(argv=None):
    p = argparse.ArgumentParser(description="Download lecture media with license + attribution capture.")
    p.add_argument("manifest", nargs="?", help="manifest .json or .txt")
    p.add_argument("--from-article", metavar="TITLE",
                   help="list images used on a Wikipedia article (discovery mode)")
    p.add_argument("--search", metavar="WORDS",
                   help="search Commons for files by keyword, when you don't know "
                        "the exact File: title (discovery mode)")
    p.add_argument("--json", action="store_true",
                   help="with a discovery mode: print a manifest skeleton of the "
                        "FREE results instead of a table")
    p.add_argument("--out", default="images", help="output folder (default: images)")
    p.add_argument("--max-width", type=int, default=1600,
                   help="cap the long edge in px for rasters (default 1600; 0 = originals)")
    p.add_argument("--force", action="store_true", help="re-download existing files")
    p.add_argument("--dry-run", action="store_true", help="plan only; no downloads")
    p.add_argument("--allow-nonfree", action="store_true",
                   help="download files flagged non-free (only if YOU hold the rights)")
    p.add_argument("--inject-qmd", metavar="FILE.qmd",
                   help="fill <!-- IMG: name.jpg --> markers in this .qmd with a "
                        "figure block + every upstream alt-text candidate")
    p.add_argument("--no-harvest", action="store_true",
                   help="skip harvesting upstream alt text (faster; fewer API calls)")
    p.add_argument("--force-alt", action="store_true",
                   help="overwrite fig-alt values you edited by hand in the .qmd")
    args = p.parse_args(argv)

    mw = args.max_width if args.max_width and args.max_width > 0 else 0

    if args.from_article:
        do_from_article(args.from_article, mw or 800, as_json=args.json)
        return 0
    if args.search:
        do_search(args.search, mw or 800, as_json=args.json)
        return 0
    if not args.manifest:
        p.error("give a manifest, or use --from-article TITLE")
    entries = load_manifest(args.manifest)
    if not entries:
        print("Manifest is empty.")
        return 1
    do_download(entries, args.out, mw, args.force, args.dry_run, args.allow_nonfree,
                harvest=not args.no_harvest, inject_qmd=args.inject_qmd,
                force_alt=args.force_alt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
