# Cuilcheanna House reviews — implementation plan (remaining work)

**Date:** 2026-09-19
**Repo:** `pjithorpe/cuilcheanna-reviews` (public, default branch `master`)
**Goal:** a daily-refreshed, cached JSON feed of FreeToBook guest reviews, rendered as an
auto-scrolling testimonials section on cuilcheannahouse.com via Squarespace Code Injection.

This plan covers everything left after the previous session, which was interrupted part-way through
uploading files to GitHub through the browser.

> **Status 2026-09-19:** Phases 0–3 are **done** — the repo is published, the feed is live at
> `raw.githubusercontent.com/pjithorpe/cuilcheanna-reviews/master/reviews.json` (35 commented reviews,
> 29 of them 5-star), the secret is set, and two manual workflow runs have gone green. Next up is
> Phase 4 (front-end), then Phase 5 (Squarespace) behind the approval gate.
>
> One fix came out of the first live run: the scraper rewrote `reviews.json` on every run because the
> `updated` timestamp always changed, which would have meant a commit every day. It now only writes when
> the reviews themselves change.

---

## 1. Where we actually are (verified today)

| Thing | State |
|---|---|
| GitHub repo | Exists, public, `master` default, **contains only `README.md`** — no code pushed |
| Local clone | `C:\personal\cuilcheanna-reviews`, clean, in sync with `origin/master` |
| Built artifacts | Exported from the old chat, staged in the session scratchpad (`zipx/`): `scrape.py` (174 lines), `requirements.txt`, `reviews.yml`, `squarespace-injection.html`, `preview.html`, `README.md` |
| FreeToBook endpoint | **Re-verified working anonymously today**: `GET /reviews/get?w_id=50548&w_tkn=…&property_id=55894&reviews_from=0&reviews_limit=100` → HTTP 200, 184 KB, **45 reviews, 10 without comments → 35 usable testimonials** |
| `reviews.json` | Does not exist yet, anywhere |
| Repo secret `FTB_W_TKN` | Not set |
| Squarespace | Nothing injected yet; homepage has both `footer` and `#footer-sections`, 6 page sections, headings render in `kepler-std` |
| Local tooling | Python 3.14.5 present, **`requests`/`beautifulsoup4` not installed**; `gh` CLI **not installed**; git uses the Windows credential manager |

**Consequence:** everything the old session built survived in the export, but *none of it is deployed*.
The remaining work is hardening, publishing, wiring and verification — not redesign.

## 2. Target architecture (unchanged, for reference)

```
GitHub Actions (daily cron)
  └─ scrape.py → GET freetobook.com/reviews/get   (server-side, so no CORS problem)
       └─ parse + merge into reviews.json → commit only when changed
            └─ raw.githubusercontent.com/.../master/reviews.json   (CORS: *, ~5 min CDN cache)
                 └─ Squarespace Footer Code Injection → fetch + render CSS marquee
                      └─ mounts into <div id="ftb-reviews"></div> on the homepage
```

Visitors never touch FreeToBook. The JSON accumulates over time, so a testimonial is never lost even if
FreeToBook stops returning it.

---

## Phase 0 — Local workspace (~10 min)

1. Copy the staged files into the repo, with `reviews.yml` → `.github/workflows/reviews.yml`.
2. Add `.gitignore` (`.venv/`, `__pycache__/`, `*.pyc`, `.env`).
3. Create a venv and install deps: `py -m venv .venv`, then `.venv\Scripts\python -m pip install -r requirements.txt`.
4. Save the live fragment already fetched today as `tests/fixtures/reviews_fragment.html`, **with the
   `w_tkn` scrubbed out** — it becomes the golden input for offline parser tests.

**Done when:** the repo tree matches the intended layout and the venv imports `requests` + `bs4`.

## Phase 1 — Harden the scraper, add tests (~45 min)

The exported `scrape.py` parses correctly, but has gaps worth closing before it runs unattended for months.

1. **Fail loudly on a broken scrape.** Today a 0-review parse prints a warning and exits `0`, so a
   FreeToBook markup change would go unnoticed indefinitely. Change to: leave `reviews.json` untouched
   (as now) *and* exit non-zero, so the Action goes red and GitHub emails you.
2. **Offline mode for tests:** `FTB_HTML_FILE=<path>` bypasses the network, so the parser is testable
   without the token or internet.
3. **Transient-failure retry:** 2 retries with backoff on network errors / 5xx. The previous session
   already hit a one-off 503 from GitHub; FreeToBook can hiccup the same way.
4. **Pagination safety:** if the returned count equals `reviews_limit`, fetch the next window until
   exhausted. At 45 reviews against a limit of 100 this is pure future-proofing.
5. **Rating handling:** keep `rating: null` rather than guessing, and have the front-end omit the star row
   when it is null (today it would render 0 filled stars and an aria-label of `NaN`).
6. **Optional `date_iso` field** alongside the human `date` string, so the front-end can sort and format
   reliably and the Python parser stays the only thing that understands `"18th September, 2026"`.
7. **Tests — deliberately lean** (`tests/test_scrape.py`, stdlib `unittest`, no new deps). Enough to catch a
   FreeToBook markup change and a merge regression, and no more: parses the fixture to 35 commented reviews;
   excludes `"No comment submitted."`; the hidden Ratings/Tips block never leaks into a comment; merge is
   idempotent, dedups, keeps an old review the live window has dropped, and sorts newest-first.

**Done when:** `.venv\Scripts\python -m unittest discover tests -v` is green and a real run against the live
endpoint writes a `reviews.json` with `count: 35`.

**Known limitation to accept, not fix:** dedup keys on `(name, date, comment[:80])`, so if FreeToBook ever
edits an existing comment we get a duplicate card. Rare and low-impact — document it in the README.

## Phase 2 — Publish the repo (~20 min)

1. Seed `reviews.json` with a real local run and commit it, so the section has data the moment the snippet
   goes live and is never blank waiting for the first cron.
2. Update `README.md` with the real raw URL, a short runbook (manual re-run, token rotation, what a red run
   means) and the dedup caveat.
3. Commit and push to `master` (HTTPS via the credential manager; approve the prompt if one appears).

**Done when:** `https://raw.githubusercontent.com/pjithorpe/cuilcheanna-reviews/master/reviews.json` returns
the seeded JSON and `curl -I` confirms `access-control-allow-origin: *`.

## Phase 3 — Wire up GitHub Actions (~15 min, needs your browser)

1. Add the repo secret **`FTB_W_TKN`** (Settings → Secrets and variables → Actions) with the widget token.
   *Note: this token is not really secret — it already appears in the public FreeToBook share link and in
   the "Read all our reviews" link inside the injected snippet. Using a secret keeps it out of the repo and
   makes rotation a one-field change; treat it as hygiene, not security.*
2. Trigger **Run workflow** manually and watch the run.
3. Verify: run green; `reviews.json` either unchanged (expected, since Phase 2 seeded it) or updated by a
   `reviews-bot` commit; the job log shows `scraped=45 … total=35`.
4. Confirm the cron (`17 5 * * *`) is registered on the default branch.

**Done when:** a manual dispatch completes end-to-end with no local involvement.

## Phase 4 — Finish the front-end (~45 min)

All of this happens against `preview.html` and a local copy; nothing touches the live site in this phase.

1. Replace `__RAW_URL__` with the real raw URL.
2. **Fix the Squarespace AJAX-navigation gap.** The script binds once on `DOMContentLoaded`, but Squarespace
   7.1 swaps pages client-side — arriving at the homepage from another page can leave the section
   unrendered. Add a `mercury:load` / `popstate` listener plus a short-lived MutationObserver for the
   marker, all idempotent through the existing `data-ftbr-done` flag.
3. **Match the site's typography.** The title currently inherits `sans-serif` from `body`, while headings on
   cuilcheannahouse.com are `kepler-std`. Point `.ftbr-title` at the site's heading font so the section
   doesn't look bolted on.
4. **Apply the display filter: 5-star, commented reviews only** (`MIN_RATING = 5`, `MIN_CHARS = 0`). Of the
   45 reviews, 37 are 5.0 and 35 have comments, so expect roughly 28–30 cards — comfortably more than the
   18-card `MAX_CARDS` window. With a 5-star floor the null-rating card variant never renders, so the
   Phase 1.5 change just stops a stray `NaN` rather than needing its own design.
5. Re-check against the **full real dataset** rather than the 6 samples: marquee duration
   (`reviews.length * 6s`) at 18 cards, the 7-line clamp against the longest real comment, and the seam on
   loop.
6. Verify desktop and mobile widths, hover-pause, and `prefers-reduced-motion` (falls back to a swipeable
   snap carousel).
7. Regenerate `preview.html` from the final snippet so the two never drift, and send it over for sign-off.

**Done when:** you approve the preview.

## Phase 5 — Squarespace deployment (~20 min, **explicit approval gate**)

Nothing here happens until Phase 4 is signed off, and I'll confirm immediately before each write to the live
site.

1. Settings → Advanced → **Code Injection → Footer**: paste the final block, Save.
2. Edit the homepage → add a **Code Block** containing `<div id="ftb-reviews"></div>` directly beneath the
   text block ending *"…on the way to Skye, Mull and the far north."* The snippet's homepage auto-mount
   above the footer is only the fallback; an explicit marker is better.
3. Verify on the **published** site, not the editor — Code Injection does not run in Squarespace's editor
   preview. Check in a logged-out/incognito window on desktop and mobile, plus one non-homepage page to
   confirm the section appears only where intended and nothing else broke.
4. Confirm there are no console errors and the JSON request is served from the CDN.

**Rollback:** delete the Code Block and clear the Footer injection — two reversible edits; no other site
state is touched.

## Phase 6 — Operations and handover (~15 min)

1. **Scheduled workflows are disabled after 60 days of repository inactivity.** If reviews arrive less often
   than every two months, the cron silently stops. **Decided: add a keepalive** — when `reviews.json` is
   unchanged, the workflow writes the run timestamp to `last-run.txt` and commits that instead, on the 1st
   of each month only, so the repo is never quiet for 60 days and the commit log stays close to noise-free.
2. Confirm Actions failure notifications reach your email.
3. README runbook: how to force a refresh, what to do if the section is empty, and the fact that rotating the
   FreeToBook token means updating **both** the repo secret and the `SUBLINK` in the Squarespace snippet.
4. Optional later: a jsDelivr mirror or `?v=` cache-buster if raw.githubusercontent.com ever gets slow.

---

## Decisions (settled 2026-09-19)

1. **Placement** — the marker Code Block goes directly **beneath the homepage text block** that reads:
   *"Spend your whole time in the Highlands with us or stop on the way to Skye, Mull and the far north."*
2. **Title** — *"Kind Words from Our Guests"*.
3. **Which reviews** — every review that has a written comment, **5-star only**. No minimum comment length
   (`MIN_CHARS = 0`, `MIN_RATING = 5`). Filtering happens in the front-end, not the scraper, so
   `reviews.json` keeps the full record and the threshold can change without a re-scrape.
4. **Keepalive** — yes, add it, so the daily cron survives quiet periods.

## Acceptance criteria

- [ ] `master` contains `scrape.py`, `requirements.txt`, `.github/workflows/reviews.yml`, `tests/`, `reviews.json`, `squarespace-injection.html`, `preview.html`, updated `README.md`
- [ ] Unit tests pass locally against the committed fixture
- [ ] A manual workflow dispatch completes green, and the daily cron is registered
- [ ] The raw JSON URL serves at least 35 reviews with `access-control-allow-origin: *`
- [ ] The live homepage renders the marquee on desktop and mobile with no console errors
- [ ] A failed scrape leaves the last good data in place and turns the Action red

## Out of scope

Cloudflare Workers migration, review moderation/editing UI, owner responses, multi-property support, and any
Squarespace change beyond one Footer injection and one Code Block.
