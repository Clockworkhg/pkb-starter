#!/usr/bin/env python3
"""
PKB 网络响应捕获模块。

职责（仅限本模块）：
  - 监听 Playwright response/requestfailed 事件
  - 筛选符合条件的文本响应（JSON / HTML / plain text）
  - 安全读取响应 body（有大小限制）
  - 响应级去重（body_sha256 + content_type）
  - URL 脱敏
  - 输出结构化 CapturedResponse 列表和 CaptureDiagnostic

不负责：
  - JSON 内容解析和候选提取（见 network_content.py）
  - 正文质量评分
  - 最终正文选择
  - Playwright 生命周期管理
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse, urlunparse, parse_qs


# ═══════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class NetworkCaptureOptions:
    """网络响应捕获配置。集中定义所有参数。"""

    enabled: bool = True

    # 大小限制
    max_response_bytes: int = 512 * 1024     # 单响应 body 上限
    max_analyzed_responses: int = 200         # 最多分析响应数
    max_candidates: int = 10                  # 最终候选数（供 network_content.py 使用）

    # JSON 遍历限制（供 network_content.py 使用）
    max_json_depth: int = 12
    max_json_nodes: int = 50_000
    max_json_strings: int = 2_000

    # 内容类型筛选
    capture_json: bool = True
    capture_html: bool = True
    capture_plain_text: bool = True

    # 网络 grace period（页面滚动完成后额外等待 ms）
    network_grace_ms: int = 1_000

    # 最小候选字符数（供 network_content.py 使用）
    min_candidate_chars: int = 200


# ═══════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class CapturedResponse:
    """单个已捕获并筛选通过的 HTTP 响应。"""
    url: str                    # 脱敏后的 URL
    sanitized_url: str          # 脱敏后的 URL
    status: int
    method: str
    content_type: str
    declared_size: int | None   # Content-Length 声明的值，可能为 None
    actual_size: int
    body: bytes
    body_sha256: str


@dataclass
class CaptureDiagnostic:
    """网络捕获的诊断统计。"""
    total_responses_seen: int = 0
    eligible_responses_seen: int = 0
    analyzed_responses: int = 0
    skipped_by_type: int = 0
    skipped_by_status: int = 0
    skipped_by_size: int = 0
    skipped_by_limit: int = 0
    body_read_failures: int = 0
    duplicate_responses: int = 0
    request_failures: int = 0
    candidates_found: int = 0     # 由 network_content.py 填充


# ═══════════════════════════════════════════════════════════════════
# 内容类型筛选
# ═══════════════════════════════════════════════════════════════════

# 需要捕获的 MIME 类型
_ELIGIBLE_CONTENT_TYPES: list[tuple[str, re.Pattern]] = [
    ("json", re.compile(r'application/[\w.+-]*json', re.IGNORECASE)),
    ("json", re.compile(r'text/json', re.IGNORECASE)),
    ("html", re.compile(r'text/html', re.IGNORECASE)),
    ("plain", re.compile(r'text/plain', re.IGNORECASE)),
]

# 明确跳过的 MIME 类型
_SKIP_CONTENT_TYPE_PATTERNS: list[re.Pattern] = [
    re.compile(r'image/', re.IGNORECASE),
    re.compile(r'video/', re.IGNORECASE),
    re.compile(r'audio/', re.IGNORECASE),
    re.compile(r'font/', re.IGNORECASE),
    re.compile(r'application/(?:javascript|ecmascript)', re.IGNORECASE),
    re.compile(r'text/(?:css|javascript|ecmascript)', re.IGNORECASE),
    re.compile(r'application/(?:pdf|zip|gzip|octet-stream|protobuf)', re.IGNORECASE),
    re.compile(r'text/event-stream', re.IGNORECASE),
    re.compile(r'multipart/', re.IGNORECASE),
    re.compile(r'model/', re.IGNORECASE),
    re.compile(r'application/x-font', re.IGNORECASE),
]


def _is_eligible_content_type(content_type: str) -> bool:
    """判断 Content-Type 是否值得分析正文。"""
    if not content_type:
        return False
    ct = content_type.split(";")[0].strip()
    for _, pattern in _ELIGIBLE_CONTENT_TYPES:
        if pattern.match(ct):
            return True
    return False


def _classify_content_type(content_type: str) -> str:
    """将 Content-Type 归类为 json / html / plain / other。"""
    if not content_type:
        return "other"
    ct = content_type.split(";")[0].strip().lower()
    if "json" in ct:
        return "json"
    if "html" in ct:
        return "html"
    if ct == "text/plain":
        return "plain"
    return "other"


# ═══════════════════════════════════════════════════════════════════
# URL 脱敏
# ═══════════════════════════════════════════════════════════════════

SENSITIVE_QUERY_PARAMS: frozenset[str] = frozenset({
    "token", "access_token", "refresh_token",
    "auth", "authorization", "api_key", "apikey",
    "secret", "session", "sessionid",
    "device_id", "user_id", "uid",
    "hkey", "sign", "signature",
    "password", "passwd", "pwd",
})

_REDACTED = "***REDACTED***"


def sanitize_url(url: str) -> str:
    """脱敏 URL 中的敏感查询参数。

    https://api.example.com/data?id=12&token=abc123&sign=xyz
    → https://api.example.com/data?id=12&token=***REDACTED***&sign=***REDACTED***
    """
    parsed = urlparse(url)
    if not parsed.query:
        return url

    try:
        params = parse_qs(parsed.query, keep_blank_values=True)
    except Exception:
        return url

    sanitized_params = {}
    for key, values in params.items():
        if key.lower() in SENSITIVE_QUERY_PARAMS:
            sanitized_params[key] = [_REDACTED]
        else:
            sanitized_params[key] = values[:1]

    # 手动重建 query string 避免 urlencode 编码 ***REDACTED***
    parts: list[str] = []
    for key, vals in sanitized_params.items():
        for val in vals:
            parts.append(f"{key}={val}")
    new_query = "&".join(parts)
    return urlunparse(parsed._replace(query=new_query))


# ═══════════════════════════════════════════════════════════════════
# 响应捕获
# ═══════════════════════════════════════════════════════════════════

class ResponseCaptureSession:
    """单个页面的网络响应捕获会话。

    用法：
      session = ResponseCaptureSession(options)
      session.attach(page)           # 挂载监听器
      ... page 导航 / 滚动 / 等待 ...
      session.finalize()             # 读取 body，生成结果
      responses = session.get_responses()
    """

    def __init__(self, options: NetworkCaptureOptions):
        self._options = options
        # 轻量元数据队列（response 回调中不读取 body）
        self._pending: list[dict[str, Any]] = []
        self._diagnostic = CaptureDiagnostic()
        self._responses: list[CapturedResponse] = []
        self._seen_hashes: set[tuple[str, str]] = set()  # (body_sha256, content_type)
        self._finalized = False
        self._closed = False

    def attach(self, page: Any) -> None:
        """将监听器挂载到 Playwright page 上。"""
        if self._closed:
            return

        page.on("response", self._on_response)
        page.on("requestfailed", self._on_requestfailed)

    def _on_response(self, response: Any) -> None:
        """response 事件回调 — 只做轻量筛选和元数据收集。"""
        if self._closed or self._finalized:
            return

        self._diagnostic.total_responses_seen += 1

        # 检查分析上限
        if len(self._pending) >= self._options.max_analyzed_responses:
            self._diagnostic.skipped_by_limit += 1
            return

        try:
            status = response.status
            req = response.request
            method = (req.method if req else "GET")
            content_type = (response.headers.get("content-type", "") or "").split(";")[0].strip()
        except Exception:
            self._diagnostic.skipped_by_status += 1
            return

        # 筛选 status（优先于 content-type，204 立即过滤）
        if status == 204:
            self._diagnostic.skipped_by_status += 1
            return
        if not (200 <= status < 300):
            self._diagnostic.skipped_by_status += 1
            return

        # 跳过 OPTIONS
        if method.upper() == "OPTIONS":
            self._diagnostic.skipped_by_status += 1
            return

        # 筛选 content-type
        if not _is_eligible_content_type(content_type):
            self._diagnostic.skipped_by_type += 1
            return

        # 检查 Content-Length
        declared_size = None
        try:
            cl = response.headers.get("content-length", "")
            if cl:
                declared_size = int(cl)
                if declared_size > self._options.max_response_bytes:
                    self._diagnostic.skipped_by_size += 1
                    return
        except (ValueError, Exception):
            pass

        self._diagnostic.eligible_responses_seen += 1
        self._pending.append({
            "response": response,
            "url": response.url,
            "status": status,
            "method": method,
            "content_type": content_type,
            "declared_size": declared_size,
        })

    def _on_requestfailed(self, request: Any) -> None:
        """requestfailed 事件 — 记录到诊断。"""
        if self._closed or self._finalized:
            return

    def finalize(self) -> None:
        """读取所有已收集响应的 body，进行去重。应在 page 关闭前调用。"""
        if self._finalized or self._closed:
            return
        self._finalized = True

        for meta in self._pending:
            if len(self._responses) >= self._options.max_analyzed_responses:
                break

            self._diagnostic.analyzed_responses += 1

            try:
                response = meta["response"]
                body = response.body()
            except Exception:
                self._diagnostic.body_read_failures += 1
                continue

            actual_size = len(body)

            # 大小检查（content-length 缺失时只在此处检查）
            if actual_size > self._options.max_response_bytes:
                self._diagnostic.skipped_by_size += 1
                continue

            # 去重
            body_hash = hashlib.sha256(body).hexdigest()
            dedup_key = (body_hash, meta["content_type"])
            if dedup_key in self._seen_hashes:
                self._diagnostic.duplicate_responses += 1
                continue
            self._seen_hashes.add(dedup_key)

            sanitized = sanitize_url(meta["url"])

            self._responses.append(CapturedResponse(
                url=meta["url"],
                sanitized_url=sanitized,
                status=meta["status"],
                method=meta["method"],
                content_type=meta["content_type"],
                declared_size=meta["declared_size"],
                actual_size=actual_size,
                body=body,
                body_sha256=body_hash,
            ))

        # 清空 pending 释放引用
        self._pending.clear()

    def close(self) -> None:
        """关闭会话，释放资源。幂等。"""
        self._closed = True
        self._pending.clear()
        self._seen_hashes.clear()

    def get_responses(self) -> list[CapturedResponse]:
        """获取已捕获的响应列表。"""
        if not self._finalized:
            return []
        return list(self._responses)

    def get_diagnostic(self) -> CaptureDiagnostic:
        """获取捕获诊断信息。"""
        return self._diagnostic
