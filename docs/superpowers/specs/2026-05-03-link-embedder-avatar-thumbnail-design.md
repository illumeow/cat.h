# Link embedder: Threads avatar fallback + video frame embed fixes

## Problem

The link embedder's custom embed (`cogs/link_embedder.py::_build_preview_embeds`) has two visual bugs that surface only on Threads, both stemming from how Threads serves `og:image`.

### Bug 1: avatar-as-hero on text-only posts

When a Threads post has no media, the page's `og:image` is the **poster's avatar** (~600×600 in observed data, fetched from a `profile_pic.django` CDN path). The bot currently feeds every `og:image` value through `embed.set_image(...)`, so this avatar renders as the embed's full-width hero. Result: text-only posts look broken — a small portrait stretched into the main slot, dominating an otherwise text-only embed.

### Bug 2: play-button overlay on video posts

For Threads video posts, `og:image` is a still frame from the video — and Meta bakes a **play-button glyph** into the frame server-side. The embed is a static image (Discord cannot play arbitrary video streams inline), so users see a play button that does nothing when clicked.

We already handle the analogous case for Instagram Reels via `_is_instagram_reel(url)` plus a `Reel · cannot be played here` footer. The detector keys on the `/reel/` path segment in the URL, which Threads has no equivalent of — every post URL is `/@user/post/<shortcode>`.

Both bugs are Threads-specific: Instagram does not have a media-less post mode, and IG reels are already covered.

## Detection signals

Verified by probing six representative posts (two avatar-fallback, two video, two image-only) against a local Playwright instance. Full data lives outside this spec; the relevant columns:

| Post | `twitter:card` | `og:image:width/height` | `og:image` URL's `stp=` |
|------|---------------|-------------------------|--------------------------|
| no-media (avatar) | `summary` | **absent** | `dst-jpg_s640x640_tt6` |
| video portrait | `summary_large_image` | 640×1136 | `cmp1_dst-jpg_e35_s640x640_tt6` |
| video landscape | `summary_large_image` | 640×360 | `cmp1_dst-jpg_e35_s640x640_tt6` |
| image-only #1 | `summary_large_image` | 1076×1435 | `cp6_dst-jpg_e35_tt6` |
| image-only #2 | `summary_large_image` | 776×578 | `dst-jpg_e35_tt6` |

**Avatar fallback signal** — `twitter:card == "summary"`. Web-standard semantics ("small-thumbnail card"). Threads emits exactly this when the og:image is the poster's avatar; emits `summary_large_image` whenever real post media (image or video frame) is present. Robust.

**Video-frame signal** — the `og:image` URL's `stp=` query parameter starts with `cmp1_`. This is Meta's internal image-pipeline tag (composite-from-video-frame). Visible to inspection, but undocumented and may drift. False negatives (rule misses a future video pattern) keep current behavior — same as IG Reels handling, which the project already accepts. False positives are unlikely in observed data: image-only posts use `cp6_` / `dst-jpg_`, never `cmp1_`.

DOM-level checks (`<video>` element count) are not useful — Threads does not eagerly mount a `<video>` tag in the page, even on a single-post URL.

## Behavior change

When the preview sidecar returns a Threads post:

1. **If `twitter:card == "summary"`** (avatar fallback) — route `og:image` to `embed.set_thumbnail(...)` instead of `embed.set_image(...)`. Title/description fill the main area; the avatar shows as a small inset on the right.
2. **If the og:image URL's `stp=` starts with `cmp1_`** (video frame) — set the embed footer to `Video · cannot be played here`, mirroring the existing IG Reel footer. Image still renders via `set_image`; the footer just sets expectation.

The two cases are mutually exclusive in observed data (avatar fallback ⇒ `summary` ⇒ no real media ⇒ no `cmp1_`). The implementation does not gate one on the other; if Threads ever produces both signals on the same post, both rules fire independently with no harm (thumbnail + footer).

For all non-Threads platforms, behavior is unchanged.

## Sidecar contract change (`preview/server.cjs`)

The Playwright `page.evaluate(...)` block in `probe(...)` adds two fields to its returned object:

- `twitterCard: string | null` — from `<meta name="twitter:card" content="...">`. Null when the tag is absent.
- `imageStp: string | null` — the `stp` query parameter parsed out of `og:image`'s URL. Parsed inside `page.evaluate` (the page already has `URL` and `URLSearchParams`). Null when there's no `og:image`, or when the URL has no `stp=` param.

Purely additive: clients that don't read the new fields are unaffected.

We do not add `og:image:width` / `og:image:height` — they were the original detection plan, but the probe showed Threads omits them on the very case (avatar fallback) we wanted to detect, so they would not have helped.

## Bot-side change (`cogs/link_embedder.py`)

Two new helpers, scoped to Threads via `meta.get("platform") == "threads"`:

```python
def _is_threads_avatar_fallback(meta: dict[str, Any]) -> bool:
    """Threads serves twitter:card='summary' (small-thumbnail card) when the
    post has no media — og:image then resolves to the poster's avatar. With
    real media (image or video frame), Threads emits 'summary_large_image'.
    Detected here so the avatar is shown as a thumbnail inset rather than
    the embed's full-width hero."""
    return (
        meta.get("platform") == "threads"
        and meta.get("twitterCard") == "summary"
    )


def _is_threads_video_frame(meta: dict[str, Any]) -> bool:
    """Threads has no /reel/-style URL marker, but its video-post og:image
    goes through Meta's 'cmp1_' image pipeline (a composite-from-video-frame
    tag visible in the URL's stp= query param). Photo posts use cp6_ or no
    prefix; avatar fallbacks use plain dst-jpg_. Heuristic — false negatives
    keep current behavior, same trade-off as the IG reel detector."""
    if meta.get("platform") != "threads":
        return False
    stp = meta.get("imageStp")
    return isinstance(stp, str) and stp.startswith("cmp1_")
```

In `_build_preview_embeds`, the embed-assembly block becomes:

```python
if meta.get("image"):
    if _is_threads_avatar_fallback(meta):
        embed.set_thumbnail(url=meta["image"])
    else:
        embed.set_image(url=meta["image"])

if _is_instagram_reel(url):
    embed.set_footer(text="Reel · cannot be played here")
elif _is_threads_video_frame(meta):
    embed.set_footer(text="Video · cannot be played here")
```

The IG Reel footer wording is preserved (Reel is the platform-correct term); Threads gets the more general "Video" label since the platform doesn't brand it as a single product. Both convey the same expectation.

The existing nothing-worth-rendering guard (`if not title and not description and not meta.get("image"): continue`) is unchanged — a thumbnail is still a rendered image and still passes the guard.

The `<URL>` auto-embed-suppression wrapping in `_process_message` is unchanged. We're still emitting a custom embed; image position and footer changes don't affect Discord's competing native preview, which we still need to suppress.

## Scope

Threads only. Both helpers gate on `meta.get("platform") == "threads"`. Instagram (the other `preview=True` platform) does not exhibit either bug:

- IG has no media-less post mode, so `twitter:card == "summary"` would not normally surface.
- IG reels are already covered by `_is_instagram_reel(url)`.

We deliberately keep the helpers platform-gated rather than universal, because both signals are observation-level inferences about Threads' specific OG-tag behavior. Applying them to a future preview platform without re-probing that platform would risk wrong demotions or wrong footers.

## Edge cases

- **`twitter:card` absent** (older or non-standard pages, sidecar interrupted by Cloudflare-style challenge). Heuristic does not fire — `set_image` fallback. Same as today.
- **`og:image` absent**. Embed-image branch not entered at all (current behavior). Footer logic also no-ops because video detection requires `imageStp`.
- **Sidecar unreachable / `PREVIEW_SERVICE_URL` empty**. Already handled today — no custom embed is rendered.
- **Cloudflare challenge page**. Already handled today via `CHALLENGE_TITLE_RE`. New helpers run after the challenge guard; if metadata is incomplete, they fall through cleanly.
- **`stp=` prefix changes upstream** (Meta renames `cmp1_`). Video footer stops appearing on Threads videos until we update the prefix; rest of the embed is unaffected. Same maintenance posture as the existing IG `/reel/` URL detector.
- **Avatar fallback AND video frame both detected** (not observed today, would require Threads to emit `summary` on a video post). Both rules fire independently — thumbnail + video footer. Acceptable.

## Verification

Manual checks (no automated test suite in the project). Test URLs from the user:

**Avatar-fallback (text-only) posts:**
- `https://www.threads.com/@janetkuo/post/DX0y9JlFc95`
- `https://www.threads.com/@_ljjky.11/post/DXzRL7FAUvr`

Expected: webhook repost with custom embed where the poster's avatar appears as a small thumbnail on the right; title and description fill the main area. No video footer.

**Video posts:**
- Portrait — `https://www.threads.com/@hsinting._/post/DX1150kE6jR`
- Landscape — `https://www.threads.com/@batseng/post/DX0KR7wk0d-`

Expected: webhook repost with custom embed where the video frame renders as the full-width hero (current behavior), plus a `Video · cannot be played here` footer.

**Image-only posts:**
- `https://www.threads.com/@yeu_ub.illus/post/DX1vJ40E0Eg`
- `https://www.threads.com/@iic3h1o_/post/DTA6XV6k0uy`

Expected: unchanged from current behavior — post image renders as full-width hero, no thumbnail, no video footer.

**Instagram regression check:**
- Any IG post URL — expect unchanged behavior (no thumbnail demotion, reels still get the `Reel · cannot be played here` footer).

## Files touched

- `preview/server.cjs` — add `twitterCard` and `imageStp` to the response.
- `cogs/link_embedder.py` — add `_is_threads_avatar_fallback` and `_is_threads_video_frame`; branch on them in `_build_preview_embeds`.
- `CLAUDE.md` — small update to the link-embedder paragraph noting Threads' avatar-fallback (→ thumbnail) and video-frame (→ footer hint) handling, alongside the existing IG reel mention.

## Out of scope

- A genuine post screenshot via Playwright (alternative considered during brainstorming). Heavier infrastructure (un-blocking image/CSS in the sidecar, longer per-request budget, fragile DOM selectors, attachment upload). Revisit only if even the cleaned-up text-only embeds feel too thin.
- Detecting carousel vs single-image Threads posts. Out of scope; current behavior already shows the first image in either case, which is acceptable.
- Generalizing the `stp=` prefix detection to a broader Meta-CDN heuristic for other platforms. Wait for a second platform to need it before extracting.
