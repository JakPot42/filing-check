"""build.py -- generate the self-contained methodology page at the repository root.

The page is one file with no external requests: the four IBM Plex woff2 subsets in
`fonts/` are base64-inlined into the stylesheet at build time. Nothing is fetched at
render time, so the page renders identically offline and cannot break because a CDN
moved.

Usage:
    python page/build.py            # write ../index.html
    python page/build.py --check    # verify the committed index.html matches the
                                    # template, without writing. Exit 1 on drift.

The ship gate below refuses to emit a page that violates a rule the design depends
on. It fails loudly rather than writing a broken page.
"""
from __future__ import annotations

import base64
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "index.html"

FONTS = {
    "__FONT_SERIF_400__": "IBMPlexSerif-Regular-Latin1.woff2",
    "__FONT_SERIF_600__": "IBMPlexSerif-SemiBold-Latin1.woff2",
    "__FONT_MONO_400__": "IBMPlexMono-Regular-Latin1.woff2",
    "__FONT_MONO_600__": "IBMPlexMono-SemiBold-Latin1.woff2",
}


def render() -> str:
    html = (HERE / "template.html").read_text(encoding="utf-8")
    for token, fname in FONTS.items():
        path = HERE / "fonts" / fname
        raw = path.read_bytes()
        if raw[:4] != b"wOF2":
            sys.exit(f"ABORT: {fname} is not a woff2 file")
        if token not in html:
            sys.exit(f"ABORT: token {token} not present in template")
        html = html.replace(token, base64.b64encode(raw).decode("ascii"))
    return html


def ship_gate(html: str) -> list[str]:
    """Return a list of violations. Empty means the page may ship."""
    errs: list[str] = []

    if "__FONT" in html:
        errs.append("unreplaced font placeholder remains")

    # Em-dash and en-dash are banned everywhere the reader can see, including CSS
    # `content:` strings. Long lines are the base64 blobs and cannot contain them.
    for ch, name in (("—", "em-dash"), ("–", "en-dash")):
        if ch in html:
            hits = [f"{name} at L{i}: {ln.strip()[:80]}"
                    for i, ln in enumerate(html.splitlines(), 1)
                    if ch in ln and len(ln) < 400]
            errs.extend(hits or [f"{name} present inside a long line"])

    # Self-containment: every url() must be a data: URI, and no external subresource.
    for m in re.finditer(r"url\(([^)]+)\)", html):
        if not m.group(1).lstrip().startswith("data:"):
            errs.append(f"non-inline url(): {m.group(1)[:60]}")
    if re.search(r"<link[^>]+href=", html) or re.search(r"<script", html):
        errs.append("external <link> or <script> present")

    # Structural guarantees the design depends on.
    if html.count("prefers-color-scheme") < 2:
        errs.append("dark mode tokens missing")
    if "prefers-reduced-motion" not in html:
        errs.append("reduced-motion block missing")
    if 'lang="en"' not in html:
        errs.append("lang attribute missing")

    return errs


def main() -> int:
    check_only = "--check" in sys.argv
    html = render()

    errs = ship_gate(html)
    if errs:
        print("SHIP GATE FAILED")
        for e in errs:
            print("  -", e)
        return 1

    if check_only:
        if not OUT.exists():
            print(f"DRIFT: {OUT.name} does not exist; run `python page/build.py`")
            return 1
        current = OUT.read_text(encoding="utf-8")
        if current != html:
            print(f"DRIFT: {OUT.name} does not match the template; "
                  f"run `python page/build.py`")
            return 1
        print(f"{OUT.name} is up to date with the template.")
        return 0

    OUT.write_text(html, encoding="utf-8", newline="\n")
    kb = len(html.encode("utf-8")) / 1024
    print(f"ship gate passed. wrote {OUT} ({kb:.0f} KB, single file, 0 external requests)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
