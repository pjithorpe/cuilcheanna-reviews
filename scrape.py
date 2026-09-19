#!/usr/bin/env python3
"""
Scrape Cuilcheanna House reviews from FreeToBook and write reviews.json.

FreeToBook renders the first few reviews server-side, then hydrates the rest
via GET /reviews/get. That endpoint returns an HTML fragment containing ALL
reviews and works without cookies, so we call it directly with a large limit.

Each review in the fragment is a flat run of sibling elements:
    <div class="flex justify-between"> ... name / date / "X.X of 5" ... </div>  <- header
    <div class="flex"> ...comment... </div>                                      <- comment (next sibling)
    <div class="display-hidden ...">Ratings ...</div>                            <- hidden detail (ignored)
    <div class="flex float-right ...">more</div>                                 <- (ignored)
    <hr>                                                                         <- (ignored)

We only keep reviews that have a written comment. Results are merged into any
existing reviews.json so testimonials accumulate over time and are never lost
even if FreeToBook later drops them from the returned window. Which of those
reviews are actually displayed (e.g. 5-star only) is the front-end's decision --
this file keeps the full record.

A scrape that finds nothing is treated as a failure: reviews.json is left
untouched (so the site never blanks) and the process exits non-zero so the
GitHub Action goes red and emails us.

Environment:
    FTB_W_ID, FTB_PROPERTY_ID, FTB_W_TKN   FreeToBook widget parameters
    FTB_OUT                                output path (default reviews.json)
    FTB_HTML_FILE                          parse this local file instead of
                                           fetching (used by the tests)
"""

import os
import copy
import re
import json
import sys
import time
import datetime

import requests
from bs4 import BeautifulSoup

ENDPOINT = "https://www.freetobook.com/reviews/get"
OUT_PATH = os.environ.get("FTB_OUT", "reviews.json")
PROPERTY_NAME = "Cuilcheanna House B&B"

W_ID = os.environ.get("FTB_W_ID", "50548")
PROPERTY_ID = os.environ.get("FTB_PROPERTY_ID", "55894")
W_TKN = os.environ.get("FTB_W_TKN", "")
HTML_FILE = os.environ.get("FTB_HTML_FILE", "")

PAGE_LIMIT = 100  # reviews per request; the property has ~45 in total
MAX_PAGES = 20  # hard stop, so a misbehaving endpoint can't loop forever
RETRIES = 3
RETRY_WAIT = 3  # seconds, multiplied by the attempt number

NO_COMMENT_RE = re.compile(r"^\s*No comment submitted\.?\s*$", re.I)
RATING_RE = re.compile(r"([\d.]+)\s*of\s*5")
DATE_RE = re.compile(r"(\d+)(?:st|nd|rd|th)?\s+([A-Za-z]+),?\s+(\d{4})")

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; CuilcheannaReviewsBot/1.0; "
        "+https://cuilcheannahouse.com)"
    ),
    "Accept": "text/html,application/xhtml+xml",
}


def fetch_html(offset: int = 0, limit: int = PAGE_LIMIT) -> str:
    if not W_TKN:
        raise SystemExit("FTB_W_TKN is not set (expected in env / GitHub secret).")
    params = {
        "w_id": W_ID,
        "w_tkn": W_TKN,
        "property_id": PROPERTY_ID,
        "reviews_from": offset,
        "reviews_limit": limit,
    }
    last_error = None
    for attempt in range(1, RETRIES + 1):
        try:
            resp = requests.get(
                ENDPOINT, params=params, headers=REQUEST_HEADERS, timeout=30
            )
            resp.raise_for_status()
            resp.encoding = resp.encoding or "utf-8"
            return resp.text
        except requests.RequestException as exc:
            last_error = exc
            if attempt < RETRIES:
                print(f"fetch attempt {attempt} failed ({exc}); retrying...")
                time.sleep(RETRY_WAIT * attempt)
    raise SystemExit(f"Could not fetch reviews after {RETRIES} attempts: {last_error}")


def parse_reviews(html: str) -> list[dict]:
    """Every review in the fragment, commented or not (comment may be "")."""
    soup = BeautifulSoup(html, "html.parser")
    reviews = []
    for header in soup.select("div.flex.justify-between"):
        # Name + date live in the first <p> that mentions "Guest from".
        name, date = "", ""
        name_p = None
        for p in header.find_all("p"):
            if "Guest from" in p.get_text():
                name_p = p
                break
        if name_p is not None:
            first_text = name_p.find(string=True)
            name = (first_text or "").strip()
            span = name_p.find("span")
            if span is not None:
                date = span.get_text(strip=True)
        if not name:
            continue

        rating_match = RATING_RE.search(header.get_text(" ", strip=True))
        rating = float(rating_match.group(1)) if rating_match else None

        # Comment is the element immediately after the header.
        comment = ""
        sib = header.find_next_sibling()
        if sib is not None:
            comment = re.sub(r"\s+", " ", sib.get_text(" ", strip=True)).strip()
        if NO_COMMENT_RE.match(comment):
            comment = ""

        reviews.append(
            {
                "name": name,
                "date": date,
                "date_iso": iso_date(date),
                "rating": rating,
                "comment": comment,
            }
        )
    return reviews


def fetch_all_reviews() -> list[dict]:
    """Walk the endpoint's pages until it stops handing us a full page."""
    if HTML_FILE:
        with open(HTML_FILE, encoding="utf-8") as f:
            return parse_reviews(f.read())

    collected: list[dict] = []
    for page in range(MAX_PAGES):
        offset = page * PAGE_LIMIT
        batch = parse_reviews(fetch_html(offset, PAGE_LIMIT))
        collected.extend(batch)
        if len(batch) < PAGE_LIMIT:
            break
    return collected


def parse_date(date_str: str):
    m = DATE_RE.search(date_str or "")
    if not m:
        return None
    day, month_name, year = m.group(1), m.group(2), m.group(3)
    try:
        return datetime.datetime.strptime(f"{int(day)} {month_name} {year}", "%d %B %Y")
    except ValueError:
        return None


def iso_date(date_str: str):
    parsed = parse_date(date_str)
    return parsed.date().isoformat() if parsed else None


def date_sort_key(date_str: str):
    return parse_date(date_str) or datetime.datetime.min


def dedup_key(r: dict):
    return (r.get("name", ""), r.get("date", ""), (r.get("comment", "") or "")[:80])


def load_existing(path: str) -> list[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    if isinstance(data, dict):
        return data.get("reviews", [])
    if isinstance(data, list):
        return data
    return []


def merge(existing: list[dict], scraped: list[dict]) -> tuple[list[dict], int]:
    seen = {dedup_key(r) for r in existing}
    merged = []
    for r in existing:
        # Backfill date_iso on records written by older versions of this script.
        r.setdefault("date_iso", iso_date(r.get("date", "")))
        merged.append(r)

    added = 0
    for r in scraped:
        if dedup_key(r) not in seen:
            merged.append(r)
            seen.add(dedup_key(r))
            added += 1

    merged.sort(key=lambda r: date_sort_key(r.get("date", "")), reverse=True)
    return merged, added


def main() -> int:
    all_reviews = fetch_all_reviews()
    scraped = [r for r in all_reviews if r["comment"]]

    # Never blank the widget on a bad scrape: keep whatever we already have,
    # but fail the run so the breakage is visible.
    if not all_reviews:
        print(
            "ERROR: parsed 0 reviews -- FreeToBook markup or endpoint has likely "
            f"changed. Leaving {OUT_PATH} untouched.",
            file=sys.stderr,
        )
        return 1
    if not scraped:
        print(
            f"ERROR: parsed {len(all_reviews)} reviews but none had a comment -- "
            f"the comment selector has likely broken. Leaving {OUT_PATH} untouched.",
            file=sys.stderr,
        )
        return 1

    existing = load_existing(OUT_PATH)
    before = copy.deepcopy(existing)
    merged, added = merge(existing, scraped)

    # Leave the file alone when the reviews themselves haven't changed --
    # otherwise the "updated" timestamp alone would produce a commit every
    # single day. "updated" therefore means "reviews last changed".
    if merged == before and os.path.exists(OUT_PATH):
        print(
            f"fetched={len(all_reviews)} with_comment={len(scraped)} "
            f"total={len(merged)} -- no changes, {OUT_PATH} left as is."
        )
        return 0

    payload = {
        "property": PROPERTY_NAME,
        "source": "freetobook",
        "updated": datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z"),
        "count": len(merged),
        "reviews": merged,
    }
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
        f.write("\n")

    print(
        f"fetched={len(all_reviews)} with_comment={len(scraped)} "
        f"existing={len(existing)} added={added} total={len(merged)} -> {OUT_PATH}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
