/*  CN-only edge rewriter
 *  - Images/GIF  → jsDelivr (ICP-licensed CDN)
 *  - Google Fonts → loli.net mirror + async load (non-render-blocking)
 */

const IMG_CDN = "https://cdn.jsdelivr.net/gh/weidaozhong/Tongluv@gh-pages/";

export async function onRequest(context) {
  const response = await context.next();
  const country = context.request.headers.get("CF-IPCountry");

  if (country !== "CN") return response;
  const ct = response.headers.get("Content-Type") || "";
  if (!ct.includes("text/html")) return response;

  let html = await response.text();

  // ── Image / icon CDN ──────────────────────────────────────
  html = html.replaceAll('src="docs/',   `src="${IMG_CDN}docs/`);
  html = html.replaceAll('src="icons/',  `src="${IMG_CDN}icons/`);
  html = html.replaceAll('href="icons/', `href="${IMG_CDN}icons/`);

  // ── Google Fonts → China mirror ───────────────────────────
  //  fonts.loli.net mirrors both the CSS and the font files,
  //  so we only need to rewrite the HTML-level URLs.
  html = html.replaceAll('https://fonts.googleapis.com', 'https://fonts.loli.net');
  html = html.replaceAll('https://fonts.gstatic.com',    'https://gstatic.loli.net');

  // Make the font stylesheet non-render-blocking:
  //   rel="stylesheet"  →  rel="stylesheet" media="print" onload="this.media='all'"
  // This lets the page render immediately with system fonts,
  // then swaps to the web font once it finishes loading.
  html = html.replace(
    'rel="stylesheet">',
    "rel=\"stylesheet\" media=\"print\" onload=\"this.media='all'\">"
  );

  return new Response(html, {
    status: response.status,
    headers: response.headers,
  });
}
