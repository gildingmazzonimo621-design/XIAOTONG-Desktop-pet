export async function onRequest(context) {
  const gitHubDownloadUrl = "https://github.com/weidaozhong/Tongluv/releases/download/v1.0.1/xiaotong.exe";
  const fileName = "xiaotong-v1.0.1.exe";
  
  // 获取请求用户的国家/地区代码 (Cloudflare 自动提供)
  const country = context.request.headers.get("CF-IPCountry");
  
  // 如果不是中国大陆 (CN) 用户，直接 302 重定向到 GitHub 官方原始下载链接
  if (country && country !== "CN") {
    return Response.redirect(gitHubDownloadUrl, 302);
  }
  
  // 如果是中国大陆 (CN) 用户，走 Cloudflare 专属的高速流式代理
  try {
    const response = await fetch(gitHubDownloadUrl);
    if (!response.ok) {
      return new Response("无法从源站获取文件", { status: response.status });
    }
    const newHeaders = new Headers(response.headers);
    newHeaders.set("Content-Disposition", `attachment; filename="${fileName}"`);
    newHeaders.set("Access-Control-Allow-Origin", "*");
    
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: newHeaders
    });
  } catch (err) {
    return new Response("下载代理服务暂时不可用: " + err.message, { status: 500 });
  }
}
