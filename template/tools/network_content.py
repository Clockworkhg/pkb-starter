#!/usr/bin/env python3
"""
PKB 网络正文候选提取模块。

职责（仅限本模块）：
  - 解析 JSON / HTML / 纯文本响应 body
  - 递归遍历 JSON，寻找正文字符串候选
  - 合并数组块结构
  - 候选级去重（content_sha256）
  - 调用 assess_article() 进行质量评分
  - 计算网络候选内部 ranking_score
  - 返回排名最高的有限候选列表

不负责：
  - Playwright 生命周期
  - 网络监听（见 network_capture.py）
  - 文件写入
  - PKB 入库
"""

from __future__ import annotations

import hashlib
import json as json_mod
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from network_capture import (
    CapturedResponse,
    CaptureDiagnostic,
    NetworkCaptureOptions,
    _classify_content_type,
)

# 延迟导入 content_quality（避免循环）
_QUALITY_AVAILABLE = False
_assess_article = None
_QualityReport = None
try:
    from content_quality import assess_article as _aa
    _assess_article = _aa
    _QUALITY_AVAILABLE = True
except ImportError:
    pass


# ═══════════════════════════════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class NetworkContentCandidate:
    """一个从网络响应中提取的正文候选。"""

    source_url: str
    """脱敏后的来源 URL。"""
    source_content_type: str
    """Content-Type（json / html / plain）。"""
    json_path: str | None
    """JSON Path（仅 JSON/HTML-in-JSON 候选）。"""
    source_kind: str
    """json_string / json_html / json_block_array / html_document / plain_text。"""

    raw_length: int
    """原始字符串长度。"""
    normalized_length: int
    """标准化后长度。"""
    content: str
    """标准化后的正文文本。"""
    content_sha256: str
    """标准化正文的 SHA256（用于候选去重）。"""

    quality_score: int
    """来自 assess_article() 的质量评分 0–100。"""
    ranking_score: float
    """网络候选内部排序分 0–120，仅用于候选间排序。"""
    quality_complete: bool
    """assess_article().complete 的结果。"""

    hints: tuple[str, ...]
    """提取来源提示（例如命名的字段名）。"""

    # 可选扩展字段
    title: str = ""
    """候选内提取的标题（可为空，使用页面标题作为回退）。"""
    html: str = ""
    """候选的原始 HTML（仅 HTML 候选有）。"""
    quality_issues: tuple[str, ...] = ()
    """质量问题的机器码列表（来自 assess_article）。"""


# ═══════════════════════════════════════════════════════════════════
# JSON Path
# ═══════════════════════════════════════════════════════════════════

def _build_json_path(stack: list[str | int]) -> str:
    """构建 JSON Path 字符串，如 $.data.article.content。"""
    parts: list[str] = ["$"]
    for item in stack:
        if isinstance(item, int):
            parts.append(f"[{item}]")
        else:
            parts.append(f".{item}")
    return "".join(parts)


# ═══════════════════════════════════════════════════════════════════
# 字段提示
# ═══════════════════════════════════════════════════════════════════

# 正文字段提示 — 作为加分信号
_CONTENT_FIELD_HINTS: frozenset[str] = frozenset({
    "content", "html", "body", "article", "article_body", "articlebody",
    "text", "description", "detail", "post", "story",
    "markdown", "rich_text", "richtext", "richtextbody",
    "summary", "abstract", "intro", "introduction",
    "message", "msg", "commenttext",
})

# 容器字段 — 继续递归，不直接当正文
_CONTAINER_FIELD_HINTS: frozenset[str] = frozenset({
    "data", "result", "payload", "response", "items", "list",
    "results", "records", "entities", "objects",
    "info", "info_list", "feed", "feeds",
})

# 正向路径词 — ranking 加分
_POSITIVE_PATH_TERMS: list[str] = [
    "article", "post", "story", "detail", "content", "body",
    "document", "news", "page", "topic", "thread",
]

# 负向路径词 — ranking 惩罚
_NEGATIVE_PATH_TERMS: list[str] = [
    "comment", "comments", "reply", "replies",
    "user", "author", "profile",
    "tag", "tags", "category", "categories",
    "recommend", "recommendation", "related",
    "advertisement", "ad", "ads", "sponsor",
    "analytics", "stat", "tracking",
    "config", "setting", "settings",
    "navigation", "nav", "menu", "footer", "header", "sidebar",
    "notification", "alert", "banner",
]


def _is_content_field(name: str) -> bool:
    """判断字段名是否为正文提示。"""
    return name.lower() in _CONTENT_FIELD_HINTS


def _is_container_field(name: str) -> bool:
    """判断字段名是否为容器。"""
    return name.lower() in _CONTAINER_FIELD_HINTS


def _field_hint_bonus(name: str) -> float:
    """字段名匹配加分 0–5。"""
    lower = name.lower()
    if lower in _CONTENT_FIELD_HINTS:
        if lower in {"content", "article", "articlebody", "body", "post", "story"}:
            return 5.0
        if lower in {"html", "richtext", "richtextbody", "markdown"}:
            return 4.0
        return 2.0
    return 0.0


# ═══════════════════════════════════════════════════════════════════
# JSON 遍历
# ═══════════════════════════════════════════════════════════════════

@dataclass
class _TraversalState:
    """JSON 递归遍历的运行时状态。"""
    depth: int = 0
    node_count: int = 0
    string_count: int = 0
    max_depth: int = 12
    max_nodes: int = 50_000
    max_strings: int = 2_000
    truncated: bool = False


def _traverse_json(
    obj: Any,
    stack: list[str | int],
    state: _TraversalState,
    candidates: list[dict[str, Any]],
    visited_ids: set[int] | None = None,
) -> None:
    """递归遍历 JSON，收集正文字符串候选。

    防御性限制：最大深度、最大节点数、最大字符串数。
    递归前检查 id() 防止非标准循环引用。
    """
    if state.truncated:
        return

    state.node_count += 1
    if state.node_count > state.max_nodes:
        state.truncated = True
        return

    state.depth += 1
    if state.depth > state.max_depth:
        state.depth -= 1
        return

    try:
        if isinstance(obj, str):
            state.string_count += 1
            if state.string_count > state.max_strings:
                state.truncated = True
                state.depth -= 1
                return

            stripped = obj.strip()
            if len(stripped) >= 200 and not _looks_like_noise(stripped):
                field_name = str(stack[-1]) if stack else ""
                path = _build_json_path(stack)
                candidates.append({
                    "content": stripped,
                    "json_path": path,
                    "field_name": field_name,
                    "hints": [field_name] if _is_content_field(field_name) else [],
                })
        elif isinstance(obj, dict):
            if visited_ids is not None:
                oid = id(obj)
                if oid in visited_ids:
                    state.depth -= 1
                    return
                visited_ids.add(oid)

            for key, value in obj.items():
                if state.truncated:
                    break
                stack.append(str(key))
                _traverse_json(value, stack, state, candidates, visited_ids)
                stack.pop()
        elif isinstance(obj, list):
            if visited_ids is not None:
                oid = id(obj)
                if oid in visited_ids:
                    state.depth -= 1
                    return
                visited_ids.add(oid)

            for idx, item in enumerate(obj):
                if state.truncated:
                    break
                stack.append(idx)
                _traverse_json(item, stack, state, candidates, visited_ids)
                stack.pop()
    finally:
        state.depth -= 1


# ═══════════════════════════════════════════════════════════════════
# 数组块合并
# ═══════════════════════════════════════════════════════════════════

_BLOCK_FIELD_NAMES: frozenset[str] = frozenset({
    "text", "content", "html", "value", "children",
    "paragraph", "paragraphs", "body", "richtext",
})

_BLOCK_PATTERNS = [
    "text", "content", "html", "value",
    "children", "paragraph", "paragraphs",
    "body", "richtext", "data", "desc",
]


def _merge_block_array(
    arr: list[Any],
    stack: list[str | int],
    state: _TraversalState,
    merged_candidates: list[dict[str, Any]],
) -> None:
    """尝试合并数组中的块结构为单一候选。

    检测模式：数组中多个相邻对象有 {type, text} 或 {text, ...} 结构。
    """
    if len(arr) < 2 or len(arr) > 200:
        return

    texts: list[str] = []
    has_content = False

    for item in arr:
        if state.truncated:
            break
        if not isinstance(item, dict):
            return  # 非字典数组不合并

        # 查找 text/content 字段
        found = None
        for key in item:
            if key.lower() in _BLOCK_FIELD_NAMES:
                val = item[key]
                if isinstance(val, str) and len(val.strip()) >= 10:
                    found = val
                    break
        if found is None:
            # 也检查 value 字段
            if "value" in item and isinstance(item["value"], str):
                found = item["value"]

        if found:
            texts.append(found)
            has_content = True

    if not has_content or len(texts) < 2:
        return

    merged = "\n\n".join(texts)
    if len(merged.strip()) >= 200:
        path = _build_json_path(stack)
        merged_candidates.append({
            "content": merged,
            "json_path": path,
            "field_name": str(stack[-1]) if stack else "",
            "hints": ["merged_blocks"],
        })


# ═══════════════════════════════════════════════════════════════════
# 噪声过滤
# ═══════════════════════════════════════════════════════════════════

_NOISE_PATTERNS: list[re.Pattern] = [
    re.compile(r'^\s*(?:[\[{]|null|true|false|undefined|NaN)\s*$', re.IGNORECASE),
    re.compile(r'^(?:https?://\S+)$'),
    re.compile(r'^(?:[a-f0-9]{32,})$'),  # hash
    re.compile(r'^(?:[A-Za-z0-9+/=]{100,})$'),  # base64
    re.compile(r'^<\?xml\s'),
    re.compile(r'^<!DOCTYPE\s+\w+', re.IGNORECASE),
    re.compile(r'^\s*#\d+\s+'),  # 纯序号
    re.compile(r'^(?:Error|Traceback|Exception|Stack\s+trace)[:\s]', re.IGNORECASE),
    re.compile(r'^Source\s+map\s+', re.IGNORECASE),
    re.compile(r'^\s*(?:OK|ok|success|error|fail|failed)\s*$', re.IGNORECASE),
]

# 日志/配置特征
_LOG_CONFIG_INDICATORS = [
    ("ERROR", "WARN", "DEBUG", "INFO", "TRACE"),
    ("timestamp", "level", "logger", "thread"),
    ("GET /", "POST /", "PUT /", "DELETE /"),
    ("nginx", "apache", "tomcat"),
]


def _looks_like_noise(text: str) -> bool:
    """快速判断字符串是否像噪声（URL/ID/配置/日志等）。"""
    t = text.strip()
    if not t:
        return True
    if len(t) < 50:
        for pat in _NOISE_PATTERNS[:4]:
            if pat.match(t):
                return True
    # 日志检测：包含多行且每行有 ERROR/WARN/DEBUG
    if t.count("\n") > 3:
        log_lines = t.split("\n")
        log_markers = sum(
            1 for line in log_lines
            if any(m in line for m in ("ERROR", "WARN", "DEBUG", "INFO", "TRACE"))
        )
        if log_markers > len(log_lines) * 0.3:
            return True
    return False


# ═══════════════════════════════════════════════════════════════════
# HTML 提取回调
# ═══════════════════════════════════════════════════════════════════

def _extract_html_candidate(
    html: str,
    source_url: str,
    extractor: Callable[[str, str], tuple[str, str, str] | None] | None = None,
) -> dict[str, Any] | None:
    """从 HTML 字符串中提取正文候选。

    extractor: 与 web_pack._extract_content_from_html 签名兼容的回调。
    如果为 None，则只做简单文本提取。
    """
    if extractor is not None:
        try:
            result = extractor(html, source_url)
            if result:
                title, markdown, method = result
                return {
                    "content": markdown,
                    "json_path": None,
                    "field_name": "html_body",
                    "hints": ["html_document", method],
                    "title": title,
                    "html": html,
                }
        except Exception:
            pass

    # Fallback: 简单 HTML 标签剥离
    t = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    t = re.sub(r'<style[^>]*>.*?</style>', ' ', t, flags=re.DOTALL | re.IGNORECASE)
    t = re.sub(r'<[^>]+>', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    if len(t) >= 200:
        return {
            "content": t,
            "json_path": None,
            "field_name": "html_body",
            "hints": ["html_document"],
            "html": html,
        }
    return None


# ═══════════════════════════════════════════════════════════════════
# 候选评分
# ═══════════════════════════════════════════════════════════════════

def _compute_ranking_score(
    candidate: dict[str, Any],
    quality_score: int,
    page_title: str,
    source_kind: str,
) -> float:
    """计算网络候选的 ranking_score 0–120。

    ranking_score = quality_score + bonus - penalty
    只用于多个候选之间排序，不修改 quality_score。
    """
    score = float(quality_score)

    # 字段提示加分
    hints = candidate.get("hints", [])
    for hint in hints:
        score += _field_hint_bonus(str(hint)) if isinstance(hint, str) else 0

    # JSON Path 正向/负向
    path = candidate.get("json_path", "") or ""
    path_lower = path.lower()
    for term in _POSITIVE_PATH_TERMS:
        if term in path_lower:
            score += 2.0
            break  # 只加一次
    for term in _NEGATIVE_PATH_TERMS:
        if term in path_lower:
            score -= 3.0
            break  # 只扣一次

    # 标题相关性 (小幅加分 0–5)
    if page_title and len(page_title) > 2:
        content_lower = candidate.get("content", "").lower()[:1000]
        title_lower = page_title.lower()
        # 字符重叠
        title_chars = set(re.sub(r'\s+', '', title_lower))
        content_chars = set(re.sub(r'\s+', '', content_lower))
        overlap = len(title_chars & content_chars)
        if overlap > 5:
            score += min(5.0, overlap * 0.3)

    # 详情 API URL 加分
    if source_kind in ("json_string", "json_html"):
        url_lower = candidate.get("json_path", "").lower()
        detail_terms = ["detail", "article", "post", "story", "content"]
        if any(term in url_lower for term in detail_terms):
            score += 3.0

    return max(0.0, min(120.0, score))


# ═══════════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════════

def extract_candidates(
    responses: list[CapturedResponse],
    options: NetworkCaptureOptions,
    diagnostic: CaptureDiagnostic,
    page_title: str = "",
    html_extractor: Callable[[str, str], tuple[str, str, str] | None] | None = None,
) -> list[NetworkContentCandidate]:
    """从已捕获的响应列表中提取正文候选。

    Args:
        responses: CapturedResponse 列表
        options: 网络捕获配置
        diagnostic: 诊断对象（会更新 candidates_found）
        page_title: 页面标题，用于相关性加分
        html_extractor: HTML 正文提取回调

    Returns:
        排序后的候选列表（最多 options.max_candidates 个）
    """
    all_candidates: list[dict[str, Any]] = []
    seen_sha256: set[str] = set()

    for resp in responses:
        ct_class = _classify_content_type(resp.content_type)

        if ct_class == "json":
            _extract_from_json_response(resp, options, all_candidates)
        elif ct_class == "html":
            cand = _extract_html_candidate(
                resp.body.decode("utf-8", errors="replace"),
                resp.sanitized_url,
                html_extractor,
            )
            if cand:
                _add_with_dedup(cand, resp, all_candidates, seen_sha256)
        elif ct_class == "plain":
            text = resp.body.decode("utf-8", errors="replace")
            if len(text.strip()) >= options.min_candidate_chars and not _looks_like_noise(text):
                cand = {
                    "content": text,
                    "json_path": None,
                    "field_name": "plain_text",
                    "hints": ["plain_text"],
                }
                _add_with_dedup(cand, resp, all_candidates, seen_sha256)

    # 将原始候选转换为 NetworkContentCandidate 并评分
    scored: list[NetworkContentCandidate] = []
    for c in all_candidates:
        nc = _build_candidate(c, resp=None, page_title=page_title)
        if nc is not None:
            scored.append(nc)

    # 按 ranking_score 降序排序，取 top N
    scored.sort(key=lambda x: x.ranking_score, reverse=True)
    top = scored[:options.max_candidates]
    diagnostic.candidates_found = len(top)
    return top


def _extract_from_json_response(
    resp: CapturedResponse,
    options: NetworkCaptureOptions,
    all_candidates: list[dict[str, Any]],
) -> None:
    """从 JSON 响应 body 中提取候选。"""
    try:
        body_str = resp.body.decode("utf-8", errors="replace")
        obj = json_mod.loads(body_str)
    except (json_mod.JSONDecodeError, UnicodeDecodeError):
        return

    state = _TraversalState(
        max_depth=options.max_json_depth,
        max_nodes=options.max_json_nodes,
        max_strings=options.max_json_strings,
    )
    raw_candidates: list[dict[str, Any]] = []
    _traverse_json(obj, [], state, raw_candidates, visited_ids=set())

    # 合并块数组
    merged: list[dict[str, Any]] = []
    _merge_blocks_in_json(obj, [], state, merged)

    # 添加去重
    seen: set[str] = set()
    for c in raw_candidates:
        _add_with_dedup(c, resp, all_candidates, seen)
    for c in merged:
        _add_with_dedup(c, resp, all_candidates, seen)


def _merge_blocks_in_json(
    obj: Any,
    stack: list[str | int],
    state: _TraversalState,
    merged: list[dict[str, Any]],
    visited_ids: set[int] | None = None,
    depth: int = 0,
) -> None:
    """遍历 JSON 查找可合并的块数组。"""
    if state.truncated or depth > 8:
        return

    state.node_count += 1
    if state.node_count > state.max_nodes:
        state.truncated = True
        return

    try:
        if isinstance(obj, list):
            if visited_ids is not None:
                oid = id(obj)
                if oid in visited_ids:
                    return
                visited_ids.add(oid)
            _merge_block_array(obj, stack, state, merged)
            for idx, item in enumerate(obj):
                if state.truncated:
                    break
                stack.append(idx)
                _merge_blocks_in_json(item, stack, state, merged, visited_ids, depth + 1)
                stack.pop()
        elif isinstance(obj, dict):
            if visited_ids is not None:
                oid = id(obj)
                if oid in visited_ids:
                    return
                visited_ids.add(oid)
            for key, value in obj.items():
                if state.truncated:
                    break
                stack.append(str(key))
                _merge_blocks_in_json(value, stack, state, merged, visited_ids, depth + 1)
                stack.pop()
    except Exception:
        pass


def _add_with_dedup(
    candidate: dict[str, Any],
    resp: CapturedResponse,
    all_candidates: list[dict[str, Any]],
    seen_sha256: set[str],
) -> None:
    """候选去重后添加到列表。"""
    content = candidate.get("content", "")
    normalized = _normalize_for_dedup(content)
    sha = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    if sha in seen_sha256:
        return
    seen_sha256.add(sha)

    candidate["_source_url"] = resp.sanitized_url
    candidate["_content_type"] = resp.content_type
    candidate["_source_kind"] = _classify_source_kind(candidate, resp)
    candidate["_sha256"] = sha
    candidate["_normalized"] = normalized
    all_candidates.append(candidate)


def _normalize_for_dedup(text: str) -> str:
    """标准化文本用于去重 SHA256。"""
    t = re.sub(r'\r\n|\r', '\n', text)
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()


def _classify_source_kind(candidate: dict[str, Any], resp: CapturedResponse) -> str:
    """分类候选来源类型。"""
    hints = candidate.get("hints", [])
    if "merged_blocks" in hints:
        return "json_block_array"
    if "html_document" in hints:
        return "html_document"
    if "plain_text" in hints:
        return "plain_text"
    ct = _classify_content_type(resp.content_type)
    if ct == "json":
        field = str(candidate.get("field_name", "")).lower()
        if "html" in field:
            return "json_html"
        return "json_string"
    return ct


def _build_candidate(
    c: dict[str, Any],
    resp: CapturedResponse | None,
    page_title: str = "",
) -> NetworkContentCandidate | None:
    """从原始候选字典构建 NetworkContentCandidate。"""
    content = c.get("_normalized", c.get("content", ""))
    if not content or len(content) < 50:
        return None

    quality_score = 0
    quality_complete = False
    quality_issues: tuple[str, ...] = ()
    if _QUALITY_AVAILABLE and _assess_article is not None:
        try:
            report = _assess_article(page_title, content, "")
            quality_score = report.score
            quality_complete = report.complete
            quality_issues = tuple(i.value for i in report.issues)
        except Exception:
            pass
    else:
        # 无 content_quality 时使用简单启发式
        if len(content) >= 500:
            quality_score = 60
            quality_complete = True
        elif len(content) >= 200:
            quality_score = 30
        else:
            quality_score = 10

    source_kind = c.get("_source_kind", "json_string")
    hints = tuple(str(h) for h in c.get("hints", []))

    # 提取标题（从候选字段名推断或使用页面标题）
    title = c.get("title", "") or page_title or ""

    # 提取 HTML（仅 HTML 候选保留原始 body）
    html = c.get("html", "")

    ranking_score = _compute_ranking_score(
        c, quality_score, page_title, source_kind,
    )

    return NetworkContentCandidate(
        source_url=c.get("_source_url", ""),
        source_content_type=c.get("_content_type", ""),
        json_path=c.get("json_path"),
        source_kind=source_kind,
        raw_length=len(c.get("content", "")),
        normalized_length=len(content),
        content=content,
        content_sha256=c.get("_sha256", ""),
        quality_score=quality_score,
        ranking_score=ranking_score,
        quality_complete=quality_complete,
        hints=hints,
        title=title,
        html=html,
        quality_issues=quality_issues,
    )
