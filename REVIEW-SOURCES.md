# Adding more review sources

Findings from investigating Booking.com, Airbnb and Google as additional sources alongside
FreeToBook. Investigated 2026-09-19/20. **Nothing here has been built** — this is the analysis
that a Phase 7 would start from.

## Why FreeToBook was easy

It is the property's *own* booking system, serving the property's *own* reviews through a widget
token, over an endpoint with no bot protection, no `robots.txt` restriction and stable markup. None
of that is true of the two OTAs.

## Booking.com

Listing: `https://www.booking.com/hotel/gb/cuilcheanna-guest-house.en-gb.html`

| Check | Result |
|---|---|
| Plain HTTPS GET, real browser user-agent, residential IP | **HTTP 202, 3,962 bytes** — an AWS WAF bot challenge (`awsWafCookieDomainList`, `challenge.js`). No listing content at all. |
| Review content in the response | None — the page was never served |
| `robots.txt`, `User-agent: *` | `Disallow: /hotelfeaturedreviews/` — the review fragment is off-limits to every crawler |

The block happens from a *home* IP with a normal browser user-agent, which is the friendliest
possible case. GitHub Actions runners use datacenter IPs and fare considerably worse.

**Difficulty: very hard, and against their terms.** It would need a stealth headless browser plus
residential proxies (~£25–60/month) running in CI, and would break every few weeks.

## Airbnb

Listing: `https://www.airbnb.co.uk/rooms/1441936202706751361`

| Check | Result |
|---|---|
| Plain HTTPS GET | HTTP 200, 507 KB — the real page (`og:title` confirms ★5.0) |
| Review text in that HTML | **None.** No `reviews`, `comments` or review-id markers anywhere in the payload |
| How reviews actually load | A follow-up call to Airbnb's internal GraphQL (`StaysPdpReviewsQuery`) needing an API key lifted from the page bundle plus signed headers |
| `robots.txt`, `User-agent: *` | `Disallow: /rooms/*/reviews` — and repeated for every named bot, including `GPTBot` and `anthropic-ai` |

**Difficulty: hard, and against their terms.** More tractable than Booking.com, but still a headless
browser, still brittle, still explicitly disallowed.

## What that rules out

A DIY scraper for either source is roughly 1–2 days to build and then indefinite maintenance on
something that fails silently. Worse, it would contaminate the part that works: a flaky source in the
same daily job means red runs and alert fatigue around the FreeToBook feed, which currently runs clean.

**If any additional source is ever added, each source must be fetched in its own step writing its own
file, merged at build time**, so one source breaking leaves the others untouched and raises only its
own alert.

## Routes actually worth considering

1. **Ask FreeToBook.** They are already the channel manager connected to Booking.com. If they expose
   Booking review data, it is the same legitimate token-based pattern already built. One email to find
   out — cheapest thing to try first.
2. **Hand-curated additions (~1–2 hours of work).** A small `manual.json` in this repo that merges
   into the feed, holding the handful of Booking/Airbnb reviews worth showing, attributed on the card.
   No scraping, no anti-bot, nothing to break. Quoting your own guests with attribution is what every
   hotel site does.
3. **A third-party aggregator** — Revyoos, Elfsight, Trustmary, Common Ninja. Minutes to set up,
   £0–15/month. Note what you are buying: they scrape on your behalf, so the risk is transferred
   rather than removed, and most hand you *their* widget rather than JSON, which would mean dropping
   the marquee or paying for a tier that exposes the data.
4. **Google instead of the OTAs** — the only source with a genuinely licensed automated path. See below.

Neither OTA appears to offer a first-party embed for a property this size: Airbnb's API is
approved-partners-only, and the whole visible market is third-party widgets.

## Google: the two legitimate routes

Both require a Google Cloud project — there is no key-less way to get Google reviews. Setup is
console clicks, not infrastructure: create a project, enable one API, create an API key, add a
billing card. The scraper would then read the key from a repo secret exactly like `FTB_W_TKN`.

### Route A — Places API (New), `Place Details` with the `reviews` field

- **Access:** immediate. No application, no approval.
- **Cost:** `reviews` sits in the **Enterprise + Atmosphere** SKU, the most expensive Place Details
  tier, and you are billed at the highest tier any requested field belongs to. The relevant free
  allowance is ~1,000 Enterprise Place Details calls/month. At one call per day (~30/month) this
  should cost nothing, but the billing card is still mandatory.
- **Volume:** returns only a small subset of reviews, not the full history — historically five.
  **Confirm with a test call before designing around it.**
- **The blocker for our architecture:** Google's terms treat names, ratings, reviews and photos as
  live content to be requested and displayed with attribution, **not warehoused**. Place IDs may be
  stored indefinitely; the content may not. Our current design — accumulate every review forever in
  `reviews.json` — is exactly what those terms disallow. Google reviews would have to be a
  refresh-and-replace block, kept separate from the accumulating FreeToBook set.
- **Display duties:** Google attribution must be shown, unaltered and adjacent to the content, with
  the reviewer's name and the link back to the review on Google. That changes the card design.

### Route B — Google Business Profile API (the owner's own listing)

- **Access:** an application form, manually reviewed by Google. Stated turnaround 7–10 business days;
  reports in the wild range from days to weeks. Requires a verified profile active 60+ days and a
  website representing the business — both of which Cuilcheanna House satisfies.
- **Cost:** free.
- **Volume:** the full review set for locations you manage, not a five-review sample.
- **Trade-off:** more capable and cheaper than Route A, but gated behind approval and OAuth rather
  than a simple API key, so it is the slower thing to start and the fiddlier thing to run in CI.

**Recommendation if Google is wanted:** apply for Route B immediately since the clock is Google's,
and decide about Route A afterwards — it is a fast win only if five reviews, live-fetch-only and
mandatory attribution are all acceptable.

## Shape of the work, whichever route

Small, and mostly in the merge and display layers:

- a `source` field per review (`freetobook` | `google` | `manual` | …) and per-source dedupe;
- a "via Booking.com" / Google attribution line on the card;
- name and date normalisation (Airbnb gives first names, Booking first name + country, Google a
  display name and a relative timestamp);
- separate handling for sources that may not be cached, so they never enter the accumulating set.

## Sources

- Evidence above was gathered first-hand: HTTP status, response size, payload inspection and
  `robots.txt` parsing for both OTAs.
- [Places API data fields](https://developers.google.com/maps/documentation/places/web-service/data-fields) ·
  [Places API policies and attribution](https://developers.google.com/maps/documentation/places/web-service/policies) ·
  [Maps Platform service terms](https://cloud.google.com/maps-platform/terms/maps-service-terms) ·
  [Business Profile API prerequisites](https://developers.google.com/my-business/content/prereqs) ·
  [Business Profile review data](https://developers.google.com/my-business/content/review-data)
