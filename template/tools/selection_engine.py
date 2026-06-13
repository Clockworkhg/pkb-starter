#!/usr/bin/env python3
"""
PKB 正文选择引擎 — HTTP / Playwright DOM / Playwright Network 三方比较。

职责（仅限本模块）：
  - 从网络候选中选出最佳网络候选
  - 在 HTTP / DOM / Network 之间执行三方选择
  - 输出确定性、可测试的选择结果

不负责：
  - 正文提取（见 web_pack.py, network_content.py）
  - 质量评分（见 content_quality.py）
  - 网络捕获（见 network_capture.py）
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# 分数差阈值
NETWORK_REPLACE_DOM_MARGIN = 8       # Network 替换 DOM 需要 >= 8 分优势
NETWORK_REPLACE_INCOMPLETE_MARGIN = 5  # 不完整时 Network 替换需要 >= 5 分优势

# 负面路径关键词
NEGATIVE_PATH_KEYWORDS = frozenset({
    "comment", "comments", "reply", "replies",
    "recommend", "recommendation", "related",
    "user", "users", "profile", "account",
    "config", "configuration", "setting",
    "nav", "navigation", "menu", "sidebar",
    "footer", "header",
})


# ═══════════════════════════════════════════════════════════════════
# 统一候选结构
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ExtractionCandidate:
    """统一的正文候选结构，三种方法归一化为此格式。"""
    method: str                    # "http" | "playwright_dom" | "playwright_network"
    title: str
    content: str                   # 正文（Markdown 或纯文本）
    html: str                      # 原始 HTML（DOM 候选有，Network 可能为空）
    final_url: str

    quality_score: int             # quality_report.score (0-100)
    quality_complete: bool         # quality_report.complete

    # 元数据
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_summary(self) -> dict:
        """转为可 JSON 序列化的摘要。"""
        return {
            "method": self.method,
            "title": self.title,
            "quality_score": self.quality_score,
            "quality_complete": self.quality_complete,
            "content_length": len(self.content),
            "has_html": bool(self.html),
        }


# ═══════════════════════════════════════════════════════════════════
# 最佳网络候选选择
# ═══════════════════════════════════════════════════════════════════

@dataclass
class BestNetworkCandidate:
    """从最多 10 个网络候选中选出的最佳候选。"""

    # 来源信息
    source_url: str = ""
    source_content_type: str = ""
    source_kind: str = ""        # json_string / json_html / json_block_array / html_document / plain_text
    json_path: str = ""

    # 内容
    content: str = ""
    title: str = ""
    html: str = ""

    # 评分
    quality_score: int = 0
    ranking_score: int = 0       # 仅用于网络候选内部排序
    quality_complete: bool = False

    # 标识
    hints: list[str] = field(default_factory=list)
    content_sha256: str = ""

    def to_summary(self) -> dict:
        """转为可 JSON 序列化的摘要（不含正文）。"""
        return {
            "source_url": self.source_url,
            "source_content_type": self.source_content_type,
            "source_kind": self.source_kind,
            "json_path": self.json_path,
            "quality_score": self.quality_score,
            "ranking_score": self.ranking_score,
            "quality_complete": self.quality_complete,
            "hints": list(self.hints),
            "content_sha256": self.content_sha256,
            "content_length": len(self.content),
        }


def select_best_network_candidate(
    candidates: list[Any],
    min_content_length: int = 200,
) -> BestNetworkCandidate | None:
    """从网络候选列表中选出最佳候选。

    规则（按优先级）：
      1. 排除 content 为空的候选
      2. 排除 content 太短的候选
      3. 优先 quality_complete=True
      4. 在 complete 候选中按 ranking_score 降序
      5. 若均不 complete，按 quality_score、ranking_score 降序
      6. 排除强负面路径提示的候选

    返回 None 表示无合格候选。
    """
    if not candidates:
        return None

    valid = []
    for c in candidates:
        # 检查 content 属性
        content = getattr(c, 'content', '') or ''
        if not content or len(content) < min_content_length:
            continue

        # 检查致命问题
        if _has_fatal_quality_issues(c):
            continue

        valid.append(c)

    if not valid:
        return None

    # 分离 complete 和 incomplete
    complete = []
    incomplete = []
    for c in valid:
        qc = getattr(c, 'quality_complete', False)
        if qc:
            complete.append(c)
        else:
            incomplete.append(c)

    # 优先 complete，按 ranking_score 降序
    if complete:
        complete.sort(key=lambda c: (
            getattr(c, 'ranking_score', 0),
            getattr(c, 'quality_score', 0),
        ), reverse=True)
        # 跳过有强负面路径提示的
        for c in complete:
            if not _has_negative_path(c):
                return _make_best(c)
        # 所有 complete 都有负面路径 → 取第一个
        return _make_best(complete[0])

    # 都不完整，按 quality_score、ranking_score 排序
    if incomplete:
        incomplete.sort(key=lambda c: (
            getattr(c, 'quality_score', 0),
            getattr(c, 'ranking_score', 0),
        ), reverse=True)
        for c in incomplete:
            if not _has_negative_path(c):
                return _make_best(c)
        return _make_best(incomplete[0])

    return None


def _has_fatal_quality_issues(candidate: Any) -> bool:
    """检查候选是否有致命质量问题。"""
    # 检查 quality_issues（可能存储为字符串枚举值列表）
    issues = getattr(candidate, 'quality_issues', None)
    if issues:
        fatal = {
            "script_placeholder", "login_required", "captcha_detected",
            "title_missing",
        }
        for issue in issues:
            val = getattr(issue, 'value', str(issue))
            if val in fatal:
                return True

    # 检查 hints 中的负面信号
    hints = getattr(candidate, 'hints', None)
    if hints:
        fatal_hints = {"error", "captcha", "login", "access_denied"}
        for h in hints:
            if any(fh in str(h).lower() for fh in fatal_hints):
                return True

    return False


def _has_negative_path(candidate: Any) -> bool:
    """检查候选 JSON Path 是否有强负面提示（评论/推荐/用户）。"""
    json_path = (getattr(candidate, 'json_path', '') or '').lower()
    if not json_path:
        return False

    strong_negatives = {"comment", "comments", "reply", "replies",
                        "recommend", "recommendation", "user", "users", "profile"}
    path_parts = json_path.replace('$', '').replace('[', '.').replace(']', '').split('.')
    for part in path_parts:
        part = part.strip().lower()
        if part in strong_negatives:
            # 排除 "article" / "content" 等正面词出现在同一路径
            if "article" not in path_parts and "content" not in path_parts and "post" not in path_parts:
                return True
    return False


def _make_best(candidate: Any) -> BestNetworkCandidate:
    """从 NetworkContentCandidate 转为 BestNetworkCandidate。"""
    return BestNetworkCandidate(
        source_url=getattr(candidate, 'source_url', ''),
        source_content_type=getattr(candidate, 'source_content_type', ''),
        source_kind=getattr(candidate, 'source_kind', ''),
        json_path=getattr(candidate, 'json_path', ''),
        content=getattr(candidate, 'content', ''),
        title=getattr(candidate, 'title', ''),
        html=getattr(candidate, 'html', ''),
        quality_score=getattr(candidate, 'quality_score', 0),
        ranking_score=getattr(candidate, 'ranking_score', 0),
        quality_complete=getattr(candidate, 'quality_complete', False),
        hints=list(getattr(candidate, 'hints', [])),
        content_sha256=getattr(candidate, 'content_sha256', ''),
    )


# ═══════════════════════════════════════════════════════════════════
# 三方选择
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SelectionResult:
    """三方选择的决策结果。"""

    selected_method: str           # "http" | "playwright_dom" | "playwright_network"
    selection_reason: str          # 稳定机器码

    # 各方法评分
    http_score: int = 0
    dom_score: int = 0
    network_score: int = 0

    http_complete: bool = False
    dom_complete: bool = False
    network_complete: bool = False

    # 警告
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "selected_method": self.selected_method,
            "selection_reason": self.selection_reason,
            "http_score": self.http_score,
            "dom_score": self.dom_score,
            "network_score": self.network_score,
            "http_complete": self.http_complete,
            "dom_complete": self.dom_complete,
            "network_complete": self.network_complete,
            "warnings": list(self.warnings),
        }


def select_best_result(
    http_candidate: ExtractionCandidate | None,
    dom_candidate: ExtractionCandidate | None,
    network_candidate: BestNetworkCandidate | None,
) -> SelectionResult:
    """在 HTTP / DOM / Network 之间执行确定性选择。

    规则（按优先级）：
      1. HTTP 完整 → 使用 HTTP（不必触发 Playwright）
      2. Network 完整且 DOM 不完整 → 使用 Network
      3. DOM 完整且 Network 不完整 → 使用 DOM
      4. DOM 和 Network 都完整 → 默认 DOM，除非 Network 高出 >= 8 分且无负面路径
      5. 都不完整 → 选最高分者，Network 需要 >= 5 分优势
      6. 同分 → DOM > HTTP > Network
    """
    # 提取评分
    http_score = http_candidate.quality_score if http_candidate else 0
    http_complete = http_candidate.quality_complete if http_candidate else False
    dom_score = dom_candidate.quality_score if dom_candidate else 0
    dom_complete = dom_candidate.quality_complete if dom_candidate else False
    net_score = network_candidate.quality_score if network_candidate else 0
    net_complete = network_candidate.quality_complete if network_candidate else False

    result = SelectionResult(
        selected_method="http",
        selection_reason="",
        http_score=http_score,
        dom_score=dom_score,
        network_score=net_score,
        http_complete=http_complete,
        dom_complete=dom_complete,
        network_complete=net_complete,
    )

    # ── 规则 1：HTTP 完整 ──
    if http_complete:
        result.selected_method = "http"
        result.selection_reason = "http_already_complete"
        return result

    # 如果没有 DOM 和 Network，保持 HTTP
    if dom_candidate is None and network_candidate is None:
        result.selected_method = "http"
        result.selection_reason = "no_alternatives_available"
        return result

    # ── 规则 2：Network 完整，DOM 不完整 ──
    if net_complete and not dom_complete:
        result.selected_method = "playwright_network"
        result.selection_reason = "network_result_complete"
        return result

    # ── 规则 3：DOM 完整，Network 不完整 ──
    if dom_complete and not net_complete:
        result.selected_method = "playwright_dom"
        result.selection_reason = "rendered_dom_complete"
        return result

    # ── 规则 4：DOM 和 Network 都完整 ──
    if dom_complete and net_complete:
        margin = net_score - dom_score
        if margin >= NETWORK_REPLACE_DOM_MARGIN and network_candidate is not None:
            if not _has_negative_path(network_candidate):
                result.selected_method = "playwright_network"
                result.selection_reason = "network_score_significantly_higher"
                return result
            else:
                result.warnings.append("network_has_negative_path")
        result.selected_method = "playwright_dom"
        result.selection_reason = "prefer_dom_for_rich_structure"
        return result

    # ── 规则 5：都不完整 ──
    # 找最高分
    scores = []
    if http_candidate:
        scores.append(("http", http_score))
    if dom_candidate:
        scores.append(("playwright_dom", dom_score))
    if network_candidate:
        scores.append(("playwright_network", net_score))

    if not scores:
        result.selected_method = "http"
        result.selection_reason = "no_valid_candidates"
        return result

    # 排序：先按分数降序，同分时 DOM > HTTP > Network
    _method_priority = {"playwright_dom": 3, "http": 2, "playwright_network": 1}
    scores.sort(key=lambda x: (x[1], _method_priority.get(x[0], 0)), reverse=True)
    best_method, best_score = scores[0]

    # Network 替换不完整结果需要 >= 5 分优势
    if best_method == "playwright_network":
        second_best_score = scores[1][1] if len(scores) > 1 else 0
        if best_score - second_best_score >= NETWORK_REPLACE_INCOMPLETE_MARGIN:
            result.selected_method = "playwright_network"
            result.selection_reason = "network_highest_incomplete"
        else:
            # 优先 DOM
            if dom_candidate:
                result.selected_method = "playwright_dom"
                result.selection_reason = "incomplete_prefer_dom"
            elif http_candidate:
                result.selected_method = "http"
                result.selection_reason = "incomplete_fallback_http"
            else:
                result.selected_method = "playwright_network"
                result.selection_reason = "incomplete_only_network"
    elif best_method == "playwright_dom":
        result.selected_method = "playwright_dom"
        result.selection_reason = "incomplete_dom_highest"
    else:
        result.selected_method = "http"
        result.selection_reason = "incomplete_http_highest"

    return result


def _has_negative_path(best: BestNetworkCandidate) -> bool:
    """检查 BestNetworkCandidate 是否有负面路径。"""
    path = (best.json_path or '').lower()
    if not path:
        return False
    strong_negatives = {"comment", "comments", "reply", "replies",
                        "recommend", "recommendation", "user", "users", "profile"}
    parts = path.replace('$', '').replace('[', '.').replace(']', '').split('.')
    for part in parts:
        if part.strip().lower() in strong_negatives:
            if "article" not in parts and "content" not in parts and "post" not in parts:
                return True
    return False
