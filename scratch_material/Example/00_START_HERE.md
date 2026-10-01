# Markdown → Slides: Marp vs. reveal.js vs. Quarto

A hands-on comparison for PHY199-RAP. The **same deck** — a 5-slide intro to the
levelized cost of energy (LCOE), with a heading, body text, a rendered math
formula, and a data table — was built three ways so you can compare the *tools*,
not the content.

Open **`COMPARISON.png`** for the side-by-side at a glance. Each tool's folder
holds its source file, a PDF of the result, and (for the web tools) the live
HTML.

## What's in each folder

| Folder | Source you edit | Rendered output | Opens in |
|--------|-----------------|-----------------|----------|
| `marp/` | `lcoe.md` (plain Markdown + a few `---` directives) | `lcoe.pdf`, `lcoe.html` | Any browser / PDF viewer |
| `revealjs/` | `lcoe.html` (hand-written HTML) + `revealjs_bundle.zip` | `lcoe.pdf` | Any browser (unzip the bundle first) |
| `quarto/` | `lcoe.qmd` (Markdown + YAML header) + `quarto_bundle.zip` | `lcoe.pdf`, **`lcoe.pptx`** | Browser, **PowerPoint/Keynote** |

## The short version

All three take you from a plain-text file to a polished, presentable deck, and
all three handled the math and the table cleanly. They differ in *what you write*
and *what you get out*.

**Marp** is the lowest-friction. You write ordinary Markdown, add a small YAML
header (`theme`, `paginate`, `math`), and separate slides with `---`. It bundles
a math engine and a set of clean built-in themes, so a good-looking deck needs
almost no fuss. It exports to PDF, HTML, PNG, and PPTX. The catch: PPTX/PDF
export drives a headless Chrome under the hood, which can be finicky in locked-down
environments (it needed extra setup here), and its exported HTML still reaches out
to a font CDN, so the **PDF is the most reliable offline artifact**.

**reveal.js** gives the most control and the nicest *on-screen* presenting
experience — smooth transitions, speaker-notes view, fragments that appear on
click, and it runs entirely in a browser from your laptop. The cost is that you
write real HTML, not Markdown, so it's the most verbose to author. It's also a
fixed-canvas format: unlike Marp, it does **not** auto-shrink content to fit, so
an overfull slide will clip (you can see the formula slide crop its last line in
the comparison). There's **no PPTX export** — the deliverable is the web page.

**Quarto** is the most capable and the best fit for a physics course. You write
Markdown with a YAML header, and from *one source file* it renders to reveal.js
HTML, **PowerPoint (.pptx)**, and Beamer/LaTeX PDF. Its real advantage is that it
runs embedded code: you can put a Python or R calculation directly in a slide and
have the computed number or a generated chart appear automatically — which is
exactly the "simple calculations" side of this course. The trade-off is the
steepest setup (a full Quarto install) and the most moving parts.

## One gotcha worth knowing (it bit all three here)

Math rendering (KaTeX/MathJax) is normally fetched from an internet CDN. In an
offline or firewalled setting that fetch fails and formulas show as raw
`\[ ... \]` text. Marp bakes the math in at build time so it mostly survives;
reveal.js and Quarto needed the math library **vendored locally** to render
offline. The bundled versions here already have that fix applied, so they work
without a network connection.

## Which should you use?

- **Fastest path to a clean deck, minimal learning:** Marp.
- **Best live talk from your laptop, willing to write HTML:** reveal.js.
- **One source → PowerPoint *and* web, with live calculations:** Quarto — and the
  strongest match for this class.

Since the class asks you to upload slides ahead of time, Marp (→ PDF/PPTX) and
Quarto (→ PPTX) both hand you a file you can submit directly; the `quarto/lcoe.pptx`
here opens straight in your PowerPoint or Keynote.

*Practical note: none of these needs VS Code. Marp and Quarto are command-line
tools (`marp deck.md -o deck.pdf`, `quarto render deck.qmd`); reveal.js is just an
HTML file you open in a browser.*
