"""
网页内容抓取服务 — 提取网页正文内容供桌宠对话使用
特性：
  - 后台线程抓取，不阻塞主线程
  - 自动识别 B站视频（走 API）、百度百科等来源
  - 仅使用标准库，无额外依赖
"""
import json
import os
import re
import threading
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

# 请求超时（秒）
_TIMEOUT = 15

# 最大段落数
_MAX_PARAGRAPHS = 20

# 最小段落长度（过短的视为噪音）
_MIN_PARAGRAPH_LEN = 15

# 请求 User-Agent
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 需要跳过的 HTML 标签（导航、脚本等无关内容）
_SKIP_TAGS = {"script", "style", "nav", "footer", "header", "aside", "form", "noscript", "svg"}


# ─── HTML 内容提取器 ────────────────────────────────────────────────────────────

class _ContentExtractor(HTMLParser):
    """基于 HTMLParser 的正文提取器，跳过无关标签内的内容"""

    def __init__(self):
        super().__init__()
        self._skip_depth = 0          # 当前处于跳过标签内的嵌套深度
        self._skip_stack = []         # 跳过标签栈
        self._text_parts = []         # 收集到的文本片段
        self._title = ""              # 页面标题
        self._in_title = False        # 是否在 <title> 内

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()
        if tag_lower == "title":
            self._in_title = True
        if tag_lower in _SKIP_TAGS:
            self._skip_stack.append(tag_lower)
            self._skip_depth += 1
        # 块级元素前插入换行，辅助段落分割
        if tag_lower in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6",
                         "article", "section", "blockquote", "tr"):
            self._text_parts.append("\n\n")

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        if tag_lower == "title":
            self._in_title = False
        if self._skip_stack and self._skip_stack[-1] == tag_lower:
            self._skip_stack.pop()
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._in_title:
            self._title += data.strip()
        if self._skip_depth == 0:
            self._text_parts.append(data)

    def get_title(self):
        return self._title.strip()

    def get_paragraphs(self):
        """将收集到的文本切分为有意义的段落"""
        full_text = "".join(self._text_parts)
        # 按多个换行或空白行分割
        raw_parts = re.split(r"\n{2,}|\r\n{2,}", full_text)
        paragraphs = []
        for part in raw_parts:
            # 清理多余空白
            cleaned = re.sub(r"\s+", " ", part).strip()
            if len(cleaned) < _MIN_PARAGRAPH_LEN:
                continue
            # 跳过看起来像样板文本的段落（如版权声明、cookie 提示等）
            if _is_boilerplate(cleaned):
                continue
            paragraphs.append(cleaned)
            if len(paragraphs) >= _MAX_PARAGRAPHS:
                break
        return paragraphs


def _is_boilerplate(text):
    """简单判断是否为样板/广告文本"""
    boilerplate_patterns = [
        r"©\s*\d{4}",
        r"All [Rr]ights [Rr]eserved",
        r"Cookie",
        r"隐私政策",
        r"用户协议",
        r"备案号",
        r"ICP备",
        r"京公网安备",
        r"var\s+\w+\s*=",       # JS 变量残留
        r"function\s*\(",       # JS 函数残留
    ]
    for pattern in boilerplate_patterns:
        if re.search(pattern, text):
            return True
    return False


# ─── 来源自动检测 ────────────────────────────────────────────────────────────────

def _detect_source(url):
    """根据 URL 自动检测来源名称"""
    host = urlparse(url).hostname or ""
    host = host.lower()
    if "bilibili.com" in host:
        return "B站"
    if "baike.baidu.com" in host:
        return "百度百科"
    # 返回主域名作为来源
    parts = host.split(".")
    if len(parts) >= 2:
        return parts[-2] + "." + parts[-1]
    return host


# ─── B站视频 API 处理 ──────────────────────────────────────────────────────────

def _extract_bvid(url):
    """从 B站视频 URL 中提取 BV 号"""
    match = re.search(r"(BV[A-Za-z0-9]+)", url)
    return match.group(1) if match else None


def _crawl_bilibili_video(url):
    """通过 B站 API 获取视频信息"""
    bvid = _extract_bvid(url)
    if not bvid:
        return None, "无法从 URL 中提取 BV 号"

    api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    req = Request(api_url, headers={"User-Agent": _USER_AGENT})

    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return None, f"B站 API 请求失败：{e}"

    if data.get("code") != 0:
        return None, f"B站 API 返回错误：{data.get('message', '未知错误')}"

    info = data.get("data", {})
    title = info.get("title", "未知标题")
    desc = info.get("desc", "暂无简介")
    owner = info.get("owner", {}).get("name", "未知UP主")

    # 构建段落
    paragraphs = [
        f"视频标题：{title}",
        f"UP主：{owner}",
        f"视频简介：{desc}",
    ]

    # 获取标签（需要额外请求 tags 接口）
    tags = _fetch_bilibili_tags(bvid)
    if tags:
        paragraphs.append(f"标签：{', '.join(tags)}")

    result = {
        "title": title,
        "url": url,
        "paragraphs": paragraphs,
        "source": "B站",
    }
    return result, None


def _fetch_bilibili_tags(bvid):
    """获取 B站视频标签列表"""
    api_url = f"https://api.bilibili.com/x/tag/archive/tags?bvid={bvid}"
    req = Request(api_url, headers={"User-Agent": _USER_AGENT})
    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("code") == 0 and data.get("data"):
            return [tag["tag_name"] for tag in data["data"] if "tag_name" in tag]
    except Exception:
        pass
    return []


# ─── 通用 HTML 抓取 ─────────────────────────────────────────────────────────────

def _crawl_html(url):
    """通用 HTML 页面抓取与正文提取"""
    req = Request(url, headers={"User-Agent": _USER_AGENT})

    try:
        with urlopen(req, timeout=_TIMEOUT) as resp:
            status = resp.status
            if status != 200:
                return None, f"HTTP 请求失败，状态码：{status}"
            # 尝试检测编码
            content_type = resp.headers.get("Content-Type", "")
            encoding = "utf-8"
            if "charset=" in content_type:
                encoding = content_type.split("charset=")[-1].strip()
            html_bytes = resp.read()
    except HTTPError as e:
        return None, f"HTTP 请求失败，状态码：{e.code}"
    except URLError as e:
        if "timed out" in str(e.reason):
            return None, "请求超时，请稍后重试"
        return None, f"网络请求失败：{e.reason}"
    except TimeoutError:
        return None, "请求超时，请稍后重试"
    except Exception as e:
        return None, f"请求异常：{e}"

    # 解析 HTML
    try:
        html_text = html_bytes.decode(encoding, errors="replace")
    except (LookupError, UnicodeDecodeError):
        html_text = html_bytes.decode("utf-8", errors="replace")

    try:
        extractor = _ContentExtractor()
        extractor.feed(html_text)
    except Exception:
        return None, "页面内容解析失败"

    title = extractor.get_title() or "无标题"
    paragraphs = extractor.get_paragraphs()

    if not paragraphs:
        return None, "页面内容解析失败"

    result = {
        "title": title,
        "url": url,
        "paragraphs": paragraphs,
        "source": _detect_source(url),
    }
    return result, None


# ─── 主入口 ─────────────────────────────────────────────────────────────────────

def _is_bilibili_video(url):
    """判断是否为 B站视频页面"""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path
    return "bilibili.com" in host and "/video/" in path


def _do_crawl(url):
    """根据 URL 类型选择抓取策略"""
    if _is_bilibili_video(url):
        return _crawl_bilibili_video(url)
    else:
        return _crawl_html(url)


def crawl_url(url, callback=None):
    """
    抓取指定 URL 的网页内容（后台线程执行）

    参数:
        url: 要抓取的网页地址
        callback: 回调函数，签名为 callback(result_dict, error_string)
                  成功时 error_string 为 None，失败时 result_dict 为 None

    返回:
        Thread 对象（可用于检测是否完成）
    """
    def _worker():
        result, error = _do_crawl(url)
        if callback:
            callback(result, error)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t
