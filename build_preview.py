#!/usr/bin/env python3
"""
Regenerate preview.html from squarespace-injection.html + reviews.json.

The preview exists so the design can be reviewed without touching the live
site. Building it from the real snippet (rather than a copy of it) means the
two can't drift apart. Reviews are embedded as FTB_REVIEWS_SAMPLE so the file
works over file:// where a cross-origin fetch would be blocked.

The live site renders in Adobe Fonts' kepler-std, which is licensed to the
site's domain; the preview substitutes EB Garamond, which is close enough to
judge layout and rhythm.

    python build_preview.py
"""

import json
import re
import sys

SNIPPET = "squarespace-injection.html"
DATA = "reviews.json"
OUT = "preview.html"

MIN_RATING = 5  # keep in step with the snippet's CONFIG block
MAX_CARDS = 18

HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Cuilcheanna House — Reviews section preview</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,300;0,400;0,500;1,400&display=swap" rel="stylesheet">
<style>
  html,body{margin:0}
  body{ background:#f6f5ea; color:#37342a; }
  /* The live site uses Adobe Fonts' kepler-std, which is licensed to
     cuilcheannahouse.com; EB Garamond stands in for it here. */
  .ftbr-section{ --ftbr-font:"EB Garamond", Georgia, serif !important; }
  .preview-note{ text-align:center; font-family:"EB Garamond",Georgia,serif; font-size:.8rem; color:#a49f8c; padding:26px 16px 0; letter-spacing:.08em; text-transform:uppercase; }
</style>
</head>
<body>
  <p class="preview-note">▼ Design preview · real 5-star FreeToBook reviews · the live site renders in kepler-std ▼</p>
  <div id="ftb-reviews"></div>
  <script>
    window.FTB_REVIEWS_SAMPLE = __REVIEWS__;
  </script>
"""

FOOT = """
</body>
</html>
"""


def main() -> int:
    snippet = open(SNIPPET, encoding="utf-8").read()

    style = re.search(r"<style>.*?</style>", snippet, re.S)
    script = re.search(r"<script>.*?</script>", snippet, re.S)
    if not style or not script:
        print(f"Could not find <style>/<script> in {SNIPPET}", file=sys.stderr)
        return 1

    data = json.load(open(DATA, encoding="utf-8"))
    reviews = [
        r
        for r in data["reviews"]
        if r.get("comment") and (r.get("rating") or 0) >= MIN_RATING
    ][:MAX_CARDS]

    head = HEAD.replace("__REVIEWS__", json.dumps(reviews, ensure_ascii=False, indent=6))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(head + style.group(0) + "\n" + script.group(0) + FOOT)

    print(f"{OUT}: {len(reviews)} cards from {len(data['reviews'])} reviews")
    return 0


if __name__ == "__main__":
    sys.exit(main())
