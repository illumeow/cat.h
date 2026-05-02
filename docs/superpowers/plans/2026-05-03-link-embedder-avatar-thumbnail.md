# Threads avatar-fallback and video-frame embed fixes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two visual bugs in the link embedder's custom embed for Threads posts: (1) demote the poster's avatar to a thumbnail inset when a Threads post has no media (`twitter:card == "summary"`); (2) add a "Video · cannot be played here" footer when the og:image is a play-button-stamped video frame (Meta's `cmp1_` image-pipeline tag).

**Architecture:** The preview sidecar (`preview/server.cjs`) extracts two new metadata fields — `twitterCard` and `imageStp` — and exposes them in its JSON response. The bot (`cogs/link_embedder.py`) adds two small platform-gated helpers (`_is_threads_avatar_fallback`, `_is_threads_video_frame`) and consumes the new fields when assembling the embed. Both helpers gate on `meta["platform"] == "threads"`, so Instagram and other platforms keep current behavior. Existing IG reel detection (`_is_instagram_reel`) remains untouched.

**Tech Stack:** Node.js + Playwright (sidecar), Python 3.14 + discord.py + aiosqlite (bot), pytest + pytest-asyncio (tests).

**Spec:** `docs/superpowers/specs/2026-05-03-link-embedder-avatar-thumbnail-design.md`

---

## File map

- **Modify:** `preview/server.cjs:124-148` — add `twitterCard` (from `<meta name="twitter:card">`) and `imageStp` (parsed from `og:image` URL's `stp=` query param) to the object returned by `page.evaluate`.
- **Modify:** `cogs/link_embedder.py:205-212` — add two helper functions next to `_is_instagram_reel`.
- **Modify:** `cogs/link_embedder.py:300-306` — branch on the new helpers in `_build_preview_embeds`'s embed-assembly block.
- **Modify:** `tests/test_link_embedder_cog.py` — add 5 tests covering avatar-fallback demotion, image-post regression, video-frame footer, IG-reel regression, IG-normal regression.
- **Modify:** `CLAUDE.md:75` — extend the link-embedder paragraph with one sentence about Threads avatar-thumbnail and video-footer handling.

No new files; this fix lives entirely in existing code paths.

---

## Task 1: Sidecar — expose `twitterCard` and `imageStp`

**Files:**
- Modify: `preview/server.cjs:124-148`

The current `probe(...)` runs `page.evaluate(...)` to pull a fixed set of og:* values. We add two more fields, both `string | null`. No automated JS tests in this project — manual verification via curl after a docker rebuild.

- [ ] **Step 1.1: Edit the `page.evaluate` block in `probe()`**

Locate the `const meta = await page.evaluate(() => { ... })` block (currently around line 124–147). Replace its body with:

```javascript
    const meta = await page.evaluate(() => {
      const get = (attr, name) =>
        document.head
          .querySelector(`meta[${attr}="${name}"]`)
          ?.getAttribute('content')
          ?.trim() || null;
      const ogImage =
        get('property', 'og:image') ||
        get('name', 'twitter:image') ||
        null;
      // The `stp` query param tags Meta's image-pipeline output. Threads
      // video posts (whose og:image is a play-button-stamped frame) ship
      // through the `cmp1_` pipeline; photo posts use `cp6_` or no
      // prefix; avatar fallbacks use plain `dst-jpg_`. The bot's
      // `_is_threads_video_frame` helper keys on this. Parsed here
      // because the sidecar already has URL-parsing context; null when
      // there's no og:image or no stp= param.
      let imageStp = null;
      if (ogImage) {
        try {
          imageStp = new URL(ogImage).searchParams.get('stp');
        } catch (_) {
          imageStp = null;
        }
      }
      return {
        title: get('property', 'og:title') || document.title || null,
        description:
          get('property', 'og:description') ||
          get('name', 'description') ||
          null,
        image: ogImage,
        video:
          get('property', 'og:video') ||
          get('property', 'og:video:url') ||
          get('name', 'twitter:player:stream') ||
          null,
        siteName: get('property', 'og:site_name') || null,
        // New: drives the bot's avatar-fallback detection. Threads emits
        // `summary` exactly when the post has no media (og:image is the
        // poster's avatar); `summary_large_image` whenever real post
        // media is present.
        twitterCard: get('name', 'twitter:card'),
        imageStp,
      };
    });
```

- [ ] **Step 1.2: Syntax-check the file**

Run: `node --check preview/server.cjs`
Expected: no output, exit 0.

- [ ] **Step 1.3: Rebuild and start the sidecar locally**

Run: `docker compose build preview`
Expected: build completes, image tagged.

Run: `docker run -d --rm --name preview-verify -p 3001:3000 discord-bot-preview && sleep 3 && curl -sf http://localhost:3001/health`
Expected: `{"status":"ok","browser":true}` (or similar with `browser:true`).

- [ ] **Step 1.4: Verify the new fields against three live URLs**

Run:
```bash
for u in \
  "https://www.threads.com/@janetkuo/post/DX0y9JlFc95" \
  "https://www.threads.com/@hsinting._/post/DX1150kE6jR" \
  "https://www.threads.com/@yeu_ub.illus/post/DX1vJ40E0Eg"; do
  echo "=== $u ==="
  curl -sf --get --data-urlencode "url=$u" http://localhost:3001/preview \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print('twitterCard:', d.get('twitterCard')); print('imageStp:', d.get('imageStp'))"
done
```

Expected:

```
=== https://www.threads.com/@janetkuo/post/DX0y9JlFc95 ===
twitterCard: summary
imageStp: dst-jpg_s640x640_tt6
=== https://www.threads.com/@hsinting._/post/DX1150kE6jR ===
twitterCard: summary_large_image
imageStp: cmp1_dst-jpg_e35_s640x640_tt6
=== https://www.threads.com/@yeu_ub.illus/post/DX1vJ40E0Eg ===
twitterCard: summary_large_image
imageStp: cp6_dst-jpg_e35_tt6
```

If any field is `None` or unexpected, debug before proceeding (the bot-side branches depend on these exact values).

- [ ] **Step 1.5: Stop the verification container**

Run: `docker stop preview-verify`
Expected: `preview-verify`.

- [ ] **Step 1.6: Commit**

```bash
git add preview/server.cjs
git commit -m "feat(preview): expose twitterCard and imageStp in sidecar response

Adds two metadata fields to the preview JSON for the link embedder's
upcoming Threads avatar-fallback and video-frame handling:

- twitterCard: from <meta name=\"twitter:card\">. Threads emits
  'summary' exactly when a post has no media; 'summary_large_image'
  whenever real post media is present.
- imageStp: the stp= query param parsed from og:image's URL. Threads
  video posts ship through Meta's 'cmp1_' image pipeline; photo posts
  use 'cp6_' or no prefix; avatar fallbacks use plain 'dst-jpg_'.

Purely additive — existing clients that don't read the fields are
unaffected."
```

---

## Task 2: Bot — demote Threads avatar fallback to thumbnail

**Files:**
- Modify: `cogs/link_embedder.py` (add helper near line 205, branch in `_build_preview_embeds` near line 302)
- Test: `tests/test_link_embedder_cog.py`

Add `_is_threads_avatar_fallback(meta)` and route the embed image to `set_thumbnail` when it fires.

- [ ] **Step 2.1: Add a failing test for avatar fallback demotion**

Append to `tests/test_link_embedder_cog.py`:

```python
# --- _build_preview_embeds: Threads avatar fallback → thumbnail -------


@pytest.mark.asyncio
async def test_build_preview_embeds_threads_avatar_fallback_uses_thumbnail(
    fresh_db, monkeypatch
):
    """A Threads post with no media: the page's og:image is the poster's
    avatar, and Threads signals this by setting twitter:card='summary'
    (vs 'summary_large_image' when real media is present). The avatar
    must render as a thumbnail inset, not as the full-width hero —
    otherwise a tiny portrait dominates an otherwise text-only embed."""
    from cogs.link_embedder import LinkEmbedderCog

    cog = LinkEmbedderCog(__import__("types").SimpleNamespace(db=fresh_db))
    cog._http = object()
    monkeypatch.setattr("cogs.link_embedder.PREVIEW_SERVICE_URL", "http://x")

    avatar_meta = {
        "platform": "threads",
        "url": "https://www.threads.com/@u/post/DX0y9JlFc95",
        "title": "Janet Kuo (@janetkuo) on Threads",
        "description": "想大聲宣佈，今天正式升 L7 Senior Staff SWE",
        "image": "https://example/avatar.jpg",
        "video": None,
        "siteName": "Threads",
        "twitterCard": "summary",
        "imageStp": "dst-jpg_s640x640_tt6",
    }
    monkeypatch.setattr(
        cog, "_fetch_preview", AsyncMock(return_value=avatar_meta)
    )

    embeds = await cog._build_preview_embeds(
        ["https://www.threads.com/@u/post/DX0y9JlFc95"]
    )
    assert len(embeds) == 1
    embed = embeds[0]
    assert embed.thumbnail.url == "https://example/avatar.jpg", (
        "avatar fallback should be routed to set_thumbnail"
    )
    assert embed.image.url is None, (
        "avatar fallback should NOT be routed to set_image"
    )
    assert embed.footer.text is None, (
        "no video footer expected on a no-media post"
    )
```

- [ ] **Step 2.2: Run the new test, confirm it fails**

Run: `uv run pytest tests/test_link_embedder_cog.py::test_build_preview_embeds_threads_avatar_fallback_uses_thumbnail -v`
Expected: FAIL — `embed.thumbnail.url is None` (current code calls `set_image`, not `set_thumbnail`).

- [ ] **Step 2.3: Add a regression test for image-only Threads posts**

Append to `tests/test_link_embedder_cog.py`:

```python
@pytest.mark.asyncio
async def test_build_preview_embeds_threads_image_post_keeps_main_image(
    fresh_db, monkeypatch
):
    """Regression guard for Task 2: a normal Threads post with media must
    still use set_image (full-width hero), not set_thumbnail. Threads
    signals real media via twitter:card='summary_large_image'."""
    from cogs.link_embedder import LinkEmbedderCog

    cog = LinkEmbedderCog(__import__("types").SimpleNamespace(db=fresh_db))
    cog._http = object()
    monkeypatch.setattr("cogs.link_embedder.PREVIEW_SERVICE_URL", "http://x")

    image_meta = {
        "platform": "threads",
        "url": "https://www.threads.com/@u/post/DX1vJ40E0Eg",
        "title": "Illustrator on Threads",
        "description": "Cute illustration",
        "image": "https://example/post-media.jpg",
        "video": None,
        "siteName": "Threads",
        "twitterCard": "summary_large_image",
        "imageStp": "cp6_dst-jpg_e35_tt6",
    }
    monkeypatch.setattr(
        cog, "_fetch_preview", AsyncMock(return_value=image_meta)
    )

    embeds = await cog._build_preview_embeds(
        ["https://www.threads.com/@u/post/DX1vJ40E0Eg"]
    )
    assert len(embeds) == 1
    embed = embeds[0]
    assert embed.image.url == "https://example/post-media.jpg"
    assert embed.thumbnail.url is None
    assert embed.footer.text is None
```

- [ ] **Step 2.4: Run the regression test, confirm it passes against current code**

Run: `uv run pytest tests/test_link_embedder_cog.py::test_build_preview_embeds_threads_image_post_keeps_main_image -v`
Expected: PASS (current code uses `set_image` for everything; this test confirms today's behavior so we don't regress it).

- [ ] **Step 2.5: Add the `_is_threads_avatar_fallback` helper**

In `cogs/link_embedder.py`, locate `_is_instagram_reel` (currently around line 205) and insert the new helper directly above it:

```python
def _is_threads_avatar_fallback(meta: dict[str, Any]) -> bool:
    """Threads serves twitter:card='summary' (small-thumbnail card) when
    the post has no media — og:image then resolves to the poster's
    avatar. With real media (image or video frame), Threads emits
    'summary_large_image'. Detected here so the avatar renders as a
    thumbnail inset rather than the embed's full-width hero."""
    return (
        meta.get("platform") == "threads"
        and meta.get("twitterCard") == "summary"
    )


```

(Keep `_is_instagram_reel` exactly where it is below; just add the new helper above it with one blank line of separation.)

- [ ] **Step 2.6: Branch on the helper in `_build_preview_embeds`**

In `cogs/link_embedder.py`, locate this block (currently around lines 302-303):

```python
            if meta.get("image"):
                embed.set_image(url=meta["image"])
```

Replace it with:

```python
            if meta.get("image"):
                if _is_threads_avatar_fallback(meta):
                    embed.set_thumbnail(url=meta["image"])
                else:
                    embed.set_image(url=meta["image"])
```

- [ ] **Step 2.7: Run both Task-2 tests, confirm both pass**

Run: `uv run pytest tests/test_link_embedder_cog.py::test_build_preview_embeds_threads_avatar_fallback_uses_thumbnail tests/test_link_embedder_cog.py::test_build_preview_embeds_threads_image_post_keeps_main_image -v`
Expected: 2 passed.

- [ ] **Step 2.8: Run the whole link-embedder test file to confirm no regression**

Run: `uv run pytest tests/test_link_embedder_cog.py tests/test_link_embedder_urls.py -v`
Expected: all pre-existing tests still pass; 2 new tests added in this task pass.

- [ ] **Step 2.9: Commit**

```bash
git add cogs/link_embedder.py tests/test_link_embedder_cog.py
git commit -m "feat(link_embedder): demote Threads avatar fallback to thumbnail

When a Threads post has no media, the page's og:image is the poster's
avatar (~600x600 in observed data) and Threads signals this with
twitter:card='summary'. The custom embed previously used set_image for
every og:image, so a tiny portrait was being rendered as the full-width
hero on text-only posts — visually weird and disproportionate.

The new _is_threads_avatar_fallback helper keys on twitter:card and
routes the avatar to set_thumbnail (small inset on the right) instead.
Real-media posts (twitter:card='summary_large_image') keep the
existing full-width hero behavior."
```

---

## Task 3: Bot — add "Video · cannot be played here" footer for Threads video posts

**Files:**
- Modify: `cogs/link_embedder.py` (add helper next to `_is_threads_avatar_fallback`, footer branch in `_build_preview_embeds`)
- Test: `tests/test_link_embedder_cog.py`

Mirrors the existing IG-reel footer behavior, keyed on Meta's `cmp1_` image-pipeline tag in the og:image URL's `stp=` param (Threads has no `/reel/`-style URL discriminator).

- [ ] **Step 3.1: Add a failing test for the Threads video footer**

Append to `tests/test_link_embedder_cog.py`:

```python
# --- _build_preview_embeds: Threads video frame footer ---------------


@pytest.mark.asyncio
async def test_build_preview_embeds_threads_video_post_gets_video_footer(
    fresh_db, monkeypatch
):
    """Threads video posts have a play-button glyph baked into the
    og:image, but the embed renders as a static image. We mark the
    video case with a footer so users don't expect inline playback.
    Detection: og:image's stp= query param starts with 'cmp1_' (Meta's
    composite-from-video-frame pipeline tag). Mirrors the existing IG
    reel handling, which keys on URL path instead since Threads has no
    /reel/ marker."""
    from cogs.link_embedder import LinkEmbedderCog

    cog = LinkEmbedderCog(__import__("types").SimpleNamespace(db=fresh_db))
    cog._http = object()
    monkeypatch.setattr("cogs.link_embedder.PREVIEW_SERVICE_URL", "http://x")

    video_meta = {
        "platform": "threads",
        "url": "https://www.threads.com/@u/post/DX1150kE6jR",
        "title": "シン (@hsinting._) on Threads",
        "description": "練習日文",
        "image": "https://example/video-frame.jpg",
        "video": None,
        "siteName": "Threads",
        "twitterCard": "summary_large_image",
        "imageStp": "cmp1_dst-jpg_e35_s640x640_tt6",
    }
    monkeypatch.setattr(
        cog, "_fetch_preview", AsyncMock(return_value=video_meta)
    )

    embeds = await cog._build_preview_embeds(
        ["https://www.threads.com/@u/post/DX1150kE6jR"]
    )
    assert len(embeds) == 1
    embed = embeds[0]
    assert embed.image.url == "https://example/video-frame.jpg", (
        "video frame should still be the full-width hero"
    )
    assert embed.thumbnail.url is None
    assert embed.footer.text == "Video · cannot be played here"
```

- [ ] **Step 3.2: Run the new test, confirm it fails**

Run: `uv run pytest tests/test_link_embedder_cog.py::test_build_preview_embeds_threads_video_post_gets_video_footer -v`
Expected: FAIL — `embed.footer.text is None` (current code only sets a footer for IG reels).

- [ ] **Step 3.3: Add an IG-reel regression test**

Append to `tests/test_link_embedder_cog.py`:

```python
@pytest.mark.asyncio
async def test_build_preview_embeds_instagram_reel_keeps_reel_footer(
    fresh_db, monkeypatch
):
    """Regression guard for Task 3: IG reels keep the existing
    'Reel · cannot be played here' wording. The two video-footer rules
    (IG via /reel/ URL path, Threads via cmp1_ stp= prefix) coexist
    independently and use platform-correct labels."""
    from cogs.link_embedder import LinkEmbedderCog

    cog = LinkEmbedderCog(__import__("types").SimpleNamespace(db=fresh_db))
    cog._http = object()
    monkeypatch.setattr("cogs.link_embedder.PREVIEW_SERVICE_URL", "http://x")

    reel_meta = {
        "platform": "instagram",
        "url": "https://www.instagram.com/reel/abc123/",
        "title": "Reel by @user",
        "description": "Reel caption",
        "image": "https://example/reel-frame.jpg",
        "video": None,
        "siteName": "Instagram",
        "twitterCard": "summary_large_image",
        "imageStp": "cmp1_dst-jpg_e35_s640x640_tt6",
    }
    monkeypatch.setattr(
        cog, "_fetch_preview", AsyncMock(return_value=reel_meta)
    )

    embeds = await cog._build_preview_embeds(
        ["https://www.instagram.com/reel/abc123/"]
    )
    assert len(embeds) == 1
    embed = embeds[0]
    assert embed.image.url == "https://example/reel-frame.jpg"
    assert embed.footer.text == "Reel · cannot be played here", (
        "IG reels must keep the Reel-specific wording even though the "
        "Threads cmp1_ rule could theoretically also fire — IG is gated "
        "out by platform check"
    )
```

- [ ] **Step 3.4: Add an IG-normal-post regression test**

Append to `tests/test_link_embedder_cog.py`:

```python
@pytest.mark.asyncio
async def test_build_preview_embeds_instagram_normal_post_no_footer(
    fresh_db, monkeypatch
):
    """Regression guard: a normal IG /p/ post (no /reel/) gets no footer
    even when the Threads-style cmp1_ signal is present. Both video-
    detection rules are platform-gated."""
    from cogs.link_embedder import LinkEmbedderCog

    cog = LinkEmbedderCog(__import__("types").SimpleNamespace(db=fresh_db))
    cog._http = object()
    monkeypatch.setattr("cogs.link_embedder.PREVIEW_SERVICE_URL", "http://x")

    post_meta = {
        "platform": "instagram",
        "url": "https://www.instagram.com/p/abc123/",
        "title": "Post by @user",
        "description": "Caption",
        "image": "https://example/post.jpg",
        "video": None,
        "siteName": "Instagram",
        "twitterCard": "summary_large_image",
        "imageStp": "cmp1_dst-jpg_e35_s640x640_tt6",
    }
    monkeypatch.setattr(
        cog, "_fetch_preview", AsyncMock(return_value=post_meta)
    )

    embeds = await cog._build_preview_embeds(
        ["https://www.instagram.com/p/abc123/"]
    )
    assert len(embeds) == 1
    assert embeds[0].footer.text is None
```

- [ ] **Step 3.5: Run the IG regression tests, confirm both pass**

Run: `uv run pytest tests/test_link_embedder_cog.py::test_build_preview_embeds_instagram_reel_keeps_reel_footer tests/test_link_embedder_cog.py::test_build_preview_embeds_instagram_normal_post_no_footer -v`
Expected: 2 passed (these characterize current behavior).

- [ ] **Step 3.6: Add the `_is_threads_video_frame` helper**

In `cogs/link_embedder.py`, directly below `_is_threads_avatar_fallback` (added in Task 2) and above `_is_instagram_reel`, insert:

```python
def _is_threads_video_frame(meta: dict[str, Any]) -> bool:
    """Threads has no /reel/-style URL marker, but its video-post
    og:image goes through Meta's 'cmp1_' image pipeline (a
    composite-from-video-frame tag visible in the URL's stp= query
    param). Photo posts use 'cp6_' or no prefix; avatar fallbacks use
    plain 'dst-jpg_'. Heuristic — false negatives keep current
    behavior, same trade-off as the IG reel detector."""
    if meta.get("platform") != "threads":
        return False
    stp = meta.get("imageStp")
    return isinstance(stp, str) and stp.startswith("cmp1_")


```

- [ ] **Step 3.7: Add the footer branch in `_build_preview_embeds`**

In `cogs/link_embedder.py`, locate this block in `_build_preview_embeds` (currently around line 304-305):

```python
            if _is_instagram_reel(url):
                embed.set_footer(text="Reel · cannot be played here")
```

Replace it with:

```python
            if _is_instagram_reel(url):
                embed.set_footer(text="Reel · cannot be played here")
            elif _is_threads_video_frame(meta):
                embed.set_footer(text="Video · cannot be played here")
```

- [ ] **Step 3.8: Run the Task-3 video footer test, confirm it passes**

Run: `uv run pytest tests/test_link_embedder_cog.py::test_build_preview_embeds_threads_video_post_gets_video_footer -v`
Expected: PASS.

- [ ] **Step 3.9: Run the whole link-embedder test file to confirm no regression**

Run: `uv run pytest tests/test_link_embedder_cog.py tests/test_link_embedder_urls.py -v`
Expected: all tests pass (existing + 5 new from Tasks 2 and 3).

- [ ] **Step 3.10: Syntax-check the cog**

Run: `uv run python -m py_compile cogs/link_embedder.py`
Expected: no output, exit 0.

- [ ] **Step 3.11: Commit**

```bash
git add cogs/link_embedder.py tests/test_link_embedder_cog.py
git commit -m "feat(link_embedder): add 'Video · cannot be played here' footer for Threads videos

Threads video posts have a play-button glyph baked into the og:image
server-side, but the embed is a static image — clicking the glyph does
nothing. This mirrors the same problem we already handle for IG reels;
the difference is that Threads has no /reel/-style URL marker.

Detection: the og:image URL's stp= query param starts with 'cmp1_'
(Meta's composite-from-video-frame image-pipeline tag). Photo posts
use cp6_ or no prefix; avatar fallbacks use plain dst-jpg_. Verified
across two video posts (portrait + landscape) and two image posts.

Footer wording differs from IG by intent: 'Reel' is the IG product
name, 'Video' is the more general term and matches what Threads users
expect to see."
```

---

## Task 4: Documentation — update CLAUDE.md

**Files:**
- Modify: `CLAUDE.md:75` (the link-embedder bullet)

The link-embedder paragraph already mentions the preview sidecar and the `<URL>` wrapping; we add one sentence about the new Threads-specific handling so future contributors know why two separate helpers exist for "video footer" detection.

- [ ] **Step 4.1: Locate the link-embedder bullet**

Run: `grep -n "Link embedder" CLAUDE.md`
Expected: one line, around line 75.

- [ ] **Step 4.2: Add a sentence about Threads avatar/video handling**

Use Edit to find the substring `If \`PREVIEW_SERVICE_URL\` is empty or the sidecar fails` in CLAUDE.md (that's the boundary of the per-platform-quirks part) and prepend a new sentence to it. Specifically, replace:

```
(Don't be tempted to use `suppress_embeds=True`: that flag sets the message-level SUPPRESS_EMBEDS bit, which hides every embed including our own.) If `PREVIEW_SERVICE_URL` is empty or the sidecar fails
```

with:

```
(Don't be tempted to use `suppress_embeds=True`: that flag sets the message-level SUPPRESS_EMBEDS bit, which hides every embed including our own.) Two Threads-specific quirks live alongside the existing IG reel handling: a media-less Threads post (signalled by `twitter:card == "summary"`) demotes its `og:image` from `set_image` to `set_thumbnail` so the poster's avatar shows as a small inset rather than a full-width hero, and a Threads video post (detected by Meta's `cmp1_` tag in the `og:image` URL's `stp=` query param) gets a `Video · cannot be played here` footer — Threads has no `/reel/`-style URL marker so we key on the image pipeline instead. If `PREVIEW_SERVICE_URL` is empty or the sidecar fails
```

- [ ] **Step 4.3: Confirm CLAUDE.md still reads cleanly**

Run: `head -76 CLAUDE.md | tail -2 | head -1` (sanity-check the line is one paragraph; the bullet keeps its single-line shape).
Expected: the line is unchanged in structure (still one bullet); only its prose is longer.

- [ ] **Step 4.4: Commit**

```bash
git add CLAUDE.md
git commit -m "docs(claude): note Threads avatar-thumbnail and video-footer handling

Document the two Threads-specific quirks the link embedder now handles
(twitter:card='summary' → set_thumbnail demotion, cmp1_ stp= prefix →
'Video · cannot be played here' footer) so future contributors don't
have to reverse-engineer why two separate footer-detection paths
exist."
```

---

## Task 5: End-to-end manual verification

**Files:** none.

The unit tests cover the helpers and `_build_preview_embeds` shaping; this task verifies the integrated path against live Threads posts in a real Discord channel. **This task does not produce a commit** — it's the operator-side smoke test before merging.

- [ ] **Step 5.1: Bring up the bot + sidecar locally**

Run: `docker compose up -d --build`
Expected: both `bot` and `preview` containers running. Confirm with `docker compose ps`.

Verify the bot logged in cleanly: `docker compose logs bot | tail -20`. Look for "Logged in as" / no extension load errors.

- [ ] **Step 5.2: In a non-excluded channel, post each test URL one at a time**

Allow the webhook repost to render before posting the next one, so embeds aren't conflated. Capture screenshots if you want a paper trail; not required.

**Avatar fallback (text-only Threads):**
- `https://www.threads.com/@janetkuo/post/DX0y9JlFc95`
- `https://www.threads.com/@_ljjky.11/post/DXzRL7FAUvr`

Expected: webhook repost with custom embed showing the avatar as a small inset on the right; title and description fill the main area; no footer.

**Threads video posts:**
- `https://www.threads.com/@hsinting._/post/DX1150kE6jR` (portrait)
- `https://www.threads.com/@batseng/post/DX0KR7wk0d-` (landscape)

Expected: video frame as the full-width hero, footer reads `Video · cannot be played here`.

**Threads image-only posts (regression):**
- `https://www.threads.com/@yeu_ub.illus/post/DX1vJ40E0Eg`
- `https://www.threads.com/@iic3h1o_/post/DTA6XV6k0uy`

Expected: post image as the full-width hero, no thumbnail, no footer.

**Instagram regression:**
- Any IG post URL — expect unchanged behavior.
- Any IG reel URL (e.g., paste a known reel from your feed) — expect `Reel · cannot be played here` footer still appears.

- [ ] **Step 5.3: Confirm no errors in bot logs during the runs**

Run: `docker compose logs bot --since=10m | grep -i "error\|exception\|traceback" | head -20`
Expected: no new errors related to the link embedder. (Pre-existing unrelated log lines are fine.)

- [ ] **Step 5.4: Tear down local environment**

Run: `docker compose down`
Expected: both containers stopped and removed.

If any expectation in Step 5.2 fails, file the symptom against the relevant Task (1, 2, or 3) and revise — do not patch around it in a later commit.

---

## Self-review

**Spec coverage:** Each spec section maps to at least one task:
- Bug 1 (avatar-as-hero) → Task 2
- Bug 2 (play-button overlay) → Task 3
- Detection signals → Task 1 (sidecar exposes the raw values), Tasks 2 & 3 (bot consumes them)
- Sidecar contract change → Task 1
- Bot-side change → Tasks 2, 3
- Scope (Threads only, helpers platform-gated) → Tasks 2, 3 (`platform == "threads"` check in both helpers)
- Edge cases (sidecar absent, missing fields, etc.) → covered by `meta.get(...)` defensive lookups; verified by existing Cloudflare-challenge test (kept passing in Step 2.8 / 3.9)
- Verification → Task 5
- Files touched → matches the file map in this plan

**Placeholders:** None. Every step has the exact code, command, or expected output.

**Type consistency:** The two new helpers share a signature (`meta: dict[str, Any] -> bool`); both use `meta["platform"]`, `meta["twitterCard"]`, `meta["imageStp"]` — exactly the keys Task 1's sidecar emits. The footer-branch elif uses `meta` (not `url`) for the Threads check, matching the helper signature, while the existing IG branch keeps using `url` (matching `_is_instagram_reel`'s signature). No drift.

**Frequent commits:** 4 commits across Tasks 1–4; Task 5 is verification-only and does not commit.

---

## Execution handoff

Plan complete. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration. Aligns with the project's `subagent-driven-development` workflow noted in CLAUDE.md.

**2. Inline Execution** — Execute tasks in this session via `executing-plans`, batch with checkpoints.

Either way, run `superpowers:using-git-worktrees` first to set up `.worktrees/<branch>` before any code changes — required by CLAUDE.md.
