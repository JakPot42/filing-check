# page/

Source for `index.html`, the self-contained methodology page at the repository root.

`index.html` is **generated**. Edit `template.html`, not the built page, then rebuild:

```bash
python page/build.py            # regenerate ../index.html
python page/build.py --check    # verify the committed page matches the template
```

`--check` exits non-zero if `index.html` has drifted from `template.html`, so an edit
made directly to the built page cannot pass unnoticed.

## Why the page is one file

The four IBM Plex woff2 subsets in `fonts/` are base64-inlined into the stylesheet at
build time. The page makes **no external requests at all**: no CDN, no `<link>`, no
`<script>`. It renders identically offline, and it cannot break because a font host
moved or went away. The cost is a 136 KB page, which is one request either way.

## The ship gate

`build.py` refuses to write a page that violates a rule the design depends on:

- no em-dash or en-dash anywhere the reader can see, including CSS `content:` strings
- every `url()` is a `data:` URI, and there is no external `<link>` or `<script>`
- light and dark tokens are both defined
- a `prefers-reduced-motion` block is present
- `lang` is set on the root element

A failure prints the offending line and writes nothing.

## Fonts

IBM Plex Serif and IBM Plex Mono, Latin-1 subsets, four faces. Licensed under the SIL
Open Font License 1.1; see `fonts/LICENSE.txt`. Copyright IBM Corp., with Reserved
Font Name "Plex".

## Design notes

Two decisions carry the page and should survive any future edit:

1. **The match rate is welded to its interpretation.** `models.py` raises on
   construction if the interpretation text is empty, so no code path can emit a bare
   percentage. The page enforces the same rule visually: the figure and its "read
   before quoting it" block are one bordered object, and the interpretation is set at
   full body size, not shrunk to a footnote. The number cannot be excerpted from its
   caveat.
2. **Caveats are heavier than body copy, not lighter.** The usual convention sets
   disclaimers smaller and greyer than the text they qualify. This tool's credibility
   depends on the opposite, so caveats get a tinted panel, an accent rule, and
   full-size ink text.

There are deliberately **no images and no icons**. The hero asset is real 74-column
tool output. Stock photography on a page about incident filings would imply the
project holds imagery and evidence it does not have.
