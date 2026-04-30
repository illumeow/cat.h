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
const USER_AGENT =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36';

// Hosts we know how to probe. Anything else gets a 415.
const SUPPORTED_HOSTS = new Set([
  'threads.net', 'www.threads.net',
  'threads.com', 'www.threads.com',
  'instagram.com', 'www.instagram.com',
]);

let browser = null;

async function getBrowser() {
  if (browser && browser.isConnected()) return browser;
  browser = await chromium.launch({ headless: true });
  return browser;
}

async function probe(targetUrl) {
  const b = await getBrowser();
  const context = await b.newContext({ userAgent: USER_AGENT });
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

    const meta = await page.evaluate(() => {
      const get = (attr, name) =>
        document.head
          .querySelector(`meta[${attr}="${name}"]`)
          ?.getAttribute('content')
          ?.trim() || null;
      return {
        title: get('property', 'og:title') || document.title || null,
        description:
          get('property', 'og:description') ||
          get('name', 'description') ||
          null,
        image:
          get('property', 'og:image') ||
          get('name', 'twitter:image') ||
          null,
        video:
          get('property', 'og:video') ||
          get('property', 'og:video:url') ||
          get('name', 'twitter:player:stream') ||
          null,
        siteName: get('property', 'og:site_name') || null,
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
  if (host.endsWith('threads.net') || host.endsWith('threads.com')) {
    return 'threads';
  }
  if (host.endsWith('instagram.com')) return 'instagram';
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
