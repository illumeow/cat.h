// Headless-Chromium link preview service for the bot's link embedder.
//
// One endpoint: GET /preview?url=<encoded url>. Drives a long-lived
// Chromium instance with a fresh browser context per request. Returns
// JSON with Open Graph metadata. The bot calls this when it rewrites a
// tracked link so it can attach a custom Discord embed (Threads / IG
// embeds Discord renders natively are usually broken or missing).

const http = require('http');
const { chromium } = require('playwright');

const PORT = Number.parseInt(process.env.PORT || '3000', 10);
const GOTO_TIMEOUT_MS = Number.parseInt(process.env.GOTO_TIMEOUT_MS || '8000', 10);
const NETWORKIDLE_TIMEOUT_MS = Number.parseInt(
  process.env.NETWORKIDLE_TIMEOUT_MS || '1500',
  10,
);
// Cap on how long we'll wait for a Cloudflare-style "Just a moment..."
// challenge to clear via its own JS handshake. Some sites (Dcard) sit
// behind one of these; without the wait we'd capture the challenge page
// as the OG metadata.
const CHALLENGE_WAIT_MS = Number.parseInt(
  process.env.CHALLENGE_WAIT_MS || '8000',
  10,
);
// Mirrors the Python-side CHALLENGE_TITLE_RE in cogs/link_embedder.py;
// any change here probably wants a matching change there.
const CHALLENGE_TITLE_RE =
  /\b(?:just a moment|cloudflare|attention required|checking your browser|security check)\b/i;
const USER_AGENT =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36';

// Hosts we know how to probe. Anything else gets a 415.
const SUPPORTED_HOSTS = new Set([
  'threads.net', 'www.threads.net',
  'threads.com', 'www.threads.com',
  'instagram.com', 'www.instagram.com',
  'dcard.tw', 'www.dcard.tw',
]);

let browser = null;
// Tracks the in-flight chromium.launch promise so two requests racing
// against the cold cache (or against a crashed browser) don't end up
// spawning two Chromium instances and leaking the loser.
let browserLaunching = null;

async function getBrowser() {
  if (browser && browser.isConnected()) return browser;
  if (!browserLaunching) {
    browserLaunching = (async () => {
      try {
        browser = await chromium.launch({ headless: true });
        return browser;
      } finally {
        // Cleared on both success and failure so a failed launch is
        // retryable on the next request rather than wedging us.
        browserLaunching = null;
      }
    })();
  }
  return browserLaunching;
}

// Resource types we never need to read OG metadata. Blocking them keeps
// each probe fast (no image/font bytes) and lets `networkidle` settle
// sooner. JS, XHR, and the document itself are still allowed — Threads
// and IG hydrate their OG tags from JS, and Cloudflare's challenge
// handshake runs in JS.
const BLOCKED_RESOURCE_TYPES = new Set([
  'image',
  'font',
  'media',
  'stylesheet',
]);

async function probe(targetUrl) {
  const b = await getBrowser();
  const context = await b.newContext({ userAgent: USER_AGENT });
  await context.route('**/*', (route) => {
    if (BLOCKED_RESOURCE_TYPES.has(route.request().resourceType())) {
      route.abort().catch(() => {});
    } else {
      route.continue().catch(() => {});
    }
  });
  const page = await context.newPage();
  try {
    await page.goto(targetUrl, {
      waitUntil: 'domcontentloaded',
      timeout: GOTO_TIMEOUT_MS,
    });
    // Best-effort wait for late-arriving OG tags from JS hydration. Don't
    // let it block the response — racing against a fixed timeout keeps
    // the worst case bounded even if the page never goes idle.
    await Promise.race([
      page.waitForLoadState('networkidle', { timeout: NETWORKIDLE_TIMEOUT_MS }),
      page.waitForTimeout(NETWORKIDLE_TIMEOUT_MS),
    ]).catch(() => null);

    // Cloudflare's basic JS challenge sets `document.title` to "Just a
    // moment..." then resolves itself a few seconds later. If we read
    // metadata immediately we capture the challenge page; wait for the
    // title to change before extracting (bounded so a permanent block
    // doesn't hang the request).
    const initialTitle = await page.evaluate(() => document.title || '');
    if (CHALLENGE_TITLE_RE.test(initialTitle)) {
      // Inline the regex inside the page function — Playwright's
      // waitForFunction takes (pageFunction, arg, options); passing a
      // RegExp across the boundary is awkward. Keep this list in sync
      // with CHALLENGE_TITLE_RE above.
      await page
        .waitForFunction(
          () =>
            !/\b(?:just a moment|cloudflare|attention required|checking your browser|security check)\b/i.test(
              document.title || '',
            ),
          null,
          { timeout: CHALLENGE_WAIT_MS, polling: 500 },
        )
        .catch(() => null);
    }

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
    return meta;
  } finally {
    // Close the context (and its page) but keep the browser around for
    // the next request — context.close() is fast (~tens of ms); a fresh
    // browser launch is multiple seconds.
    await context.close().catch(() => {});
  }
}

function platformFromHost(host) {
  // `endsWith('threads.net')` would match `evilthreads.net` — anchor to
  // the domain boundary so a future caller that drops the SUPPORTED_HOSTS
  // gate doesn't open us up to subdomain spoofing for SSRF.
  const matches = (h, domain) => h === domain || h.endsWith('.' + domain);
  if (matches(host, 'threads.net') || matches(host, 'threads.com')) {
    return 'threads';
  }
  if (matches(host, 'instagram.com')) return 'instagram';
  if (matches(host, 'dcard.tw')) return 'dcard';
  return null;
}

function send(res, status, body) {
  res.writeHead(status, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(body));
}

async function handlePreview(req, res, parsedUrl) {
  const target = parsedUrl.searchParams.get('url');
  if (!target) {
    send(res, 400, { error: 'missing url query param' });
    return;
  }
  let parsed;
  try {
    parsed = new URL(target);
  } catch (_) {
    send(res, 400, { error: 'invalid url' });
    return;
  }
  if (parsed.protocol !== 'https:' && parsed.protocol !== 'http:') {
    send(res, 400, { error: 'unsupported scheme' });
    return;
  }
  const platform = platformFromHost(parsed.hostname);
  if (!platform || !SUPPORTED_HOSTS.has(parsed.hostname)) {
    send(res, 415, { error: 'unsupported host', host: parsed.hostname });
    return;
  }

  try {
    const meta = await probe(target);
    send(res, 200, { platform, url: target, ...meta });
  } catch (err) {
    console.error('probe failed for %s: %s', target, err.message);
    send(res, 502, { error: 'probe failed', detail: err.message });
  }
}

const server = http.createServer(async (req, res) => {
  const parsedUrl = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
  if (req.method === 'GET' && parsedUrl.pathname === '/preview') {
    await handlePreview(req, res, parsedUrl);
    return;
  }
  if (req.method === 'GET' && parsedUrl.pathname === '/health') {
    send(res, 200, { status: 'ok', browser: !!browser });
    return;
  }
  send(res, 404, { error: 'not found' });
});

async function shutdown() {
  console.log('shutdown: closing server and browser');
  server.close();
  if (browser) await browser.close().catch(() => {});
  process.exit(0);
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);

(async () => {
  // Eagerly launch the browser at startup so the first request doesn't pay
  // the 2–3s cold-start penalty.
  await getBrowser();
  server.listen(PORT, () => {
    console.log(`preview service listening on :${PORT}`);
  });
})();
