const CDN = "https://cdn.jsdelivr.net/gh/weidaozhong/Tongluv@gh-pages/";

export async function onRequest(context) {
  const response = await context.next();
  const country = context.request.headers.get("CF-IPCountry");

  // Only rewrite for China mainland users, only for HTML responses
  if (country !== "CN") return response;
  const ct = response.headers.get("Content-Type") || "";
  if (!ct.includes("text/html")) return response;

  let html = await response.text();
  html = html.replaceAll('src="docs/',    `src="${CDN}docs/`);
  html = html.replaceAll('src="icons/',   `src="${CDN}icons/`);
  html = html.replaceAll('href="icons/',  `href="${CDN}icons/`);

  return new Response(html, {
    status: response.status,
    headers: response.headers,
  });
}
