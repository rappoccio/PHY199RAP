# LCOE deck — UB-branded Quarto (reveal.js)

A Quarto slide deck styled with the University at Buffalo MasterBrand template,
set up for the live-preview workflow.

## Files
- `lcoe.qmd` — the slides. **This is the file you edit** (in MacDown or any editor).
- `ub.scss` — the UB reveal.js theme. Self-contained: the UB blue, the crest
  backgrounds, and the white logo are embedded, so there's no asset folder to
  manage. Reuse it in any deck.
- `lcoe.html` — a ready-rendered copy you can open in a browser right now.
- `UB-template.pptx` — the original UB PowerPoint (only needed if you also want a
  native PowerPoint export; see the bottom).

## Live preview (the Overleaf-style loop)

Open Terminal in this folder and run:

```
quarto preview lcoe.qmd
```

Your browser opens the slides. Now edit `lcoe.qmd` in MacDown — **every time you
save, the browser refreshes automatically.** Press `Ctrl-C` in Terminal to stop.

MacDown's own preview shows plain Markdown (so `##` looks like a heading, not a
slide) — the *browser* from `quarto preview` is where you see the real slides.

## Writing slides

- Each `## Heading` starts a new slide (the heading is the slide title).
- Use `---` on its own line for a slide with no title.
- Normal Markdown: `**bold**`, `*italic*`, `-` bullets, and Markdown tables.
- Math with LaTeX: inline `$E=mc^2$`, display `$$ ... $$` (renders with KaTeX).
- Speaker notes: put them in `::: notes` / `:::` blocks.
- The UB theme is applied by this line already in the file:
  `theme: [default, ub.scss]`

## Export a finished file

```
quarto render lcoe.qmd
```

produces `lcoe.html` — a single self-contained file you can upload or present
full-screen (press `F`). Math renders as long as you have internet.

## Optional: native UB PowerPoint

reveal.js is the live/HTML format. If you also need an editable PowerPoint that
inherits the UB masters, add a `pptx` format that points at the template:

```yaml
format:
  revealjs:
    theme: [default, ub.scss]
  pptx:
    reference-doc: UB-template.pptx
```

Then `quarto render lcoe.qmd` makes both `lcoe.html` and `lcoe.pptx`. Note the
`.pptx` uses PowerPoint's own layouts (not the reveal.js CSS), so the two look
related but not pixel-identical.
