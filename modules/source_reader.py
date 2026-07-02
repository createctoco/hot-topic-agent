"""Safely fetch and extract source material for a selected hot topic."""

from __future__ import annotations

import ipaddress
import json
import logging
import re
import socket
from html import unescape
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlparse

import requests

logger = logging.getLogger(__name__)

MAX_DOWNLOAD_BYTES = 1_500_000
MAX_SOURCE_CHARS = 8_000
MAX_REDIRECTS = 5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/json,text/plain;q=0.9,*/*;q=0.5",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
}

REDIRECT_STATUSES = {301, 302, 303, 307, 308}
JSON_TEXT_KEYS = {
    "title", "description", "summary", "excerpt", "content", "text",
    "detail", "answer", "question", "article",
}


class _ArticleHTMLParser(HTMLParser):
    BLOCK_TAGS = {"h1", "h2", "h3", "p", "li", "blockquote"}
    SKIP_TAGS = {"script", "style", "noscript", "svg", "nav", "header", "footer", "form"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._primary_depth = 0
        self._block_tag = ""
        self._buffer: list[str] = []
        self.primary_lines: list[str] = []
        self.fallback_lines: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if self._skip_depth:
            self._skip_depth += 1
            return
        if tag in self.SKIP_TAGS:
            self._skip_depth = 1
            return
        if tag in {"article", "main"}:
            self._primary_depth += 1
        if tag in self.BLOCK_TAGS and not self._block_tag:
            self._block_tag = tag
            self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == self._block_tag:
            line = re.sub(r"\s+", " ", "".join(self._buffer)).strip()
            if line:
                self.fallback_lines.append(line)
                if self._primary_depth:
                    self.primary_lines.append(line)
            self._block_tag = ""
            self._buffer = []
        if tag in {"article", "main"} and self._primary_depth:
            self._primary_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth and self._block_tag:
            self._buffer.append(data)


def _is_public_host(hostname: str) -> bool:
    if not hostname or hostname.lower() == "localhost":
        return False
    try:
        addresses = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return False
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if any((ip.is_private, ip.is_loopback, ip.is_link_local, ip.is_multicast, ip.is_reserved, ip.is_unspecified)):
            return False
    return bool(addresses)


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("source URL must use public HTTP or HTTPS")
    if not _is_public_host(parsed.hostname):
        raise ValueError("source URL resolves to a non-public address")


def _decode_body(body: bytes, content_type: str) -> str:
    charset = re.search(r"charset=([\w-]+)", content_type, re.I)
    encodings = [charset.group(1)] if charset else []
    encodings.extend(["utf-8", "gb18030"])
    for encoding in encodings:
        try:
            return body.decode(encoding)
        except (UnicodeDecodeError, LookupError):
            continue
    return body.decode("utf-8", errors="replace")


def _clean_lines(lines: list[str], max_chars: int) -> str:
    ignored = {"登录", "注册", "打开APP", "下载APP", "查看更多", "返回首页"}
    result: list[str] = []
    seen: set[str] = set()
    length = 0
    for raw in lines:
        line = re.sub(r"\s+", " ", unescape(raw)).strip()
        if len(line) < 6 or line in ignored or line in seen:
            continue
        seen.add(line)
        if length + len(line) + 1 > max_chars:
            remaining = max_chars - length
            if remaining >= 40:
                result.append(line[:remaining])
            break
        result.append(line)
        length += len(line) + 1
    return "\n".join(result)


def _extract_html(text: str, max_chars: int) -> str:
    parser = _ArticleHTMLParser()
    parser.feed(text)
    lines = parser.primary_lines if len(parser.primary_lines) >= 3 else parser.fallback_lines
    return _clean_lines(lines, max_chars)


def _collect_json_text(value: Any, output: list[str], key: str = "") -> None:
    if isinstance(value, dict):
        for child_key, child in value.items():
            normalized = str(child_key).lower()
            if normalized in JSON_TEXT_KEYS or isinstance(child, (dict, list)):
                _collect_json_text(child, output, normalized)
    elif isinstance(value, list):
        for child in value[:30]:
            _collect_json_text(child, output, key)
    elif isinstance(value, str) and key in JSON_TEXT_KEYS and len(value.strip()) >= 6:
        if "<" in value and ">" in value:
            output.extend(_extract_html(value, MAX_SOURCE_CHARS).splitlines())
        else:
            output.append(value)


def _extract_json(text: str, max_chars: int) -> str:
    data = json.loads(text)
    lines: list[str] = []
    _collect_json_text(data, lines)
    return _clean_lines(lines, max_chars)


def fetch_source(url: str, max_chars: int = MAX_SOURCE_CHARS, session: requests.Session | None = None) -> dict[str, Any]:
    """Fetch a public source URL and return bounded, cleaned source text."""
    result: dict[str, Any] = {
        "status": "unavailable",
        "requested_url": url or "",
        "final_url": "",
        "text": "",
        "char_count": 0,
        "error": "",
    }
    if not url:
        result["error"] = "missing source URL"
        return result

    client = session or requests.Session()
    current = url
    try:
        for _ in range(MAX_REDIRECTS + 1):
            _validate_url(current)
            response = client.get(
                current,
                headers=HEADERS,
                timeout=(5, 12),
                allow_redirects=False,
                stream=True,
            )
            if response.status_code in REDIRECT_STATUSES:
                location = response.headers.get("Location", "")
                if not location:
                    raise ValueError("redirect did not provide a location")
                current = urljoin(current, location)
                continue
            response.raise_for_status()
            break
        else:
            raise ValueError("too many source redirects")

        chunks: list[bytes] = []
        size = 0
        for chunk in response.iter_content(chunk_size=32_768):
            if not chunk:
                continue
            size += len(chunk)
            if size > MAX_DOWNLOAD_BYTES:
                raise ValueError("source page exceeds download limit")
            chunks.append(chunk)

        content_type = response.headers.get("Content-Type", "").lower()
        decoded = _decode_body(b"".join(chunks), content_type)
        if "json" in content_type or decoded.lstrip().startswith(("{", "[")):
            extracted = _extract_json(decoded, max_chars)
        else:
            extracted = _extract_html(decoded, max_chars)

        result.update({
            "status": "ok" if len(extracted) >= 200 else "insufficient",
            "final_url": current,
            "text": extracted,
            "char_count": len(extracted),
        })
        if result["status"] != "ok":
            result["error"] = "source page did not contain enough article text"
        return result
    except Exception as error:
        result["final_url"] = current
        result["error"] = str(error)[:300]
        logger.warning("来源正文读取失败 (%s): %s", url, error)
        return result
