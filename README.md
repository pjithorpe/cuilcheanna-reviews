# Cuilcheanna House — reviews feed

Automated, cached feed of guest reviews for [cuilcheannahouse.com](https://cuilcheannahouse.com),
sourced from FreeToBook.

**Feed URL (what the website reads):**
`https://raw.githubusercontent.com/pjithorpe/cuilcheanna-reviews/master/reviews.json`

## How it works
1. **`scrape.py`** calls FreeToBook's reviews endpoint (all reviews, no login needed),
   keeps the ones with written comments, and merges them into **`reviews.json`**
   (accumulating over time, newest first, de-duplicated).
2. **`.github/workflows/reviews.yml`** runs the tests and the scraper once a day
   (and on demand) and commits `reviews.json` when it changes.
3. The website reads the raw `reviews.json` and renders an auto-scrolling
   testimonials section (see `squarespace-injection.html`), live since 19 Sep 2026.

The snippet lives in **one place only**: Squarespace → Settings → Advanced →
Code Injection → **FOOTER**. It mounts itself on the homepage, under the section
holding the "…on the way to Skye, Mull and the far north." heading, and renders
nowhere else. Clearing that FOOTER box removes the section completely.

`reviews.json` holds **every** commented review. Which ones are shown is the
front-end's decision — the injected snippet currently displays 5-star reviews only,
newest first, capped at 18 cards.

The file is only rewritten when the reviews themselves change, so its `updated`
field means *"reviews last changed"*, not *"last checked"*. A run that finds nothing
new leaves the file (and the commit log) alone.

## Configuration
The FreeToBook widget token is stored as the repository secret **`FTB_W_TKN`**
(Settings → Secrets and variables → Actions). `w_id` and `property_id` are set
in the workflow. Nothing sensitive is committed.

Note the token is not really a secret — it already appears in FreeToBook's own public
reviews link, which the section links to. Keeping it in a repo secret is hygiene and
makes rotation a one-field change.

## Files
| File | Purpose |
|------|---------|
| `scrape.py` | Fetch + parse + merge reviews |
| `requirements.txt` | Python deps (`requests`, `beautifulsoup4`) |
| `.github/workflows/reviews.yml` | Daily scheduled scrape |
| `tests/` | Parser + merge tests, and a captured FreeToBook fragment |
| `reviews.json` | Generated data (do not edit by hand) |
| `squarespace-injection.html` | The site's Code Injection snippet |
| `preview.html` | Standalone design preview |
| `IMPLEMENTATION_PLAN.md` | Build/deploy plan and current status |

## Running it locally
```bash
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m unittest discover tests -v
set FTB_W_TKN=<token>
.venv\Scripts\python scrape.py
```
`FTB_HTML_FILE=<path>` parses a saved HTML fragment instead of fetching, which is how
the tests run without the token.

## Runbook
- **Force a refresh:** Actions → *Update reviews* → **Run workflow**.
- **A run went red:** the scraper found no reviews (FreeToBook markup or endpoint
  changed). `reviews.json` is deliberately left untouched, so the website keeps showing
  the last good data — the section never blanks. Fix the parser, confirm
  `python -m unittest discover tests` still passes, then re-run the workflow.
- **The section is empty on the site:** check the feed URL loads in a browser, then the
  browser console on the homepage for a fetch error.
- **Rotating the FreeToBook token:** update **both** the `FTB_W_TKN` repo secret and the
  `SUBLINK` URL inside `squarespace-injection.html` (and re-paste the snippet into
  Squarespace).
- **Quiet periods:** GitHub disables scheduled workflows after 60 days of repository
  inactivity, so on the 1st of each month the workflow commits a `last-run.txt`
  timestamp if nothing else changed.

## Known limitation
De-duplication keys on name + date + the first 80 characters of the comment. If a guest
or FreeToBook edits an existing comment, it can appear as a second card. Rare, and
easily fixed by hand-editing `reviews.json`.
