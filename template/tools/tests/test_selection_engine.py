#!/usr/bin/env python3
"""selection_engine.py 单元测试 — 最佳网络候选选择 + 三方比较。

测试规则 1–15（见阶段 3B 规范）。
"""

from __future__ import annotations

import sys
from pathlib import Path

_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import pytest
from selection_engine import (
    ExtractionCandidate,
    BestNetworkCandidate,
    SelectionResult,
    select_best_network_candidate,
    select_best_result,
    NETWORK_REPLACE_DOM_MARGIN,
    NETWORK_REPLACE_INCOMPLETE_MARGIN,
)


# ── 辅助 ──

def _make_http(score=30, complete=False):
    return ExtractionCandidate(
        method="http", title="Test", content="HTTP content " * 20,
        html="<html>http</html>", final_url="https://example.com",
        quality_score=score, quality_complete=complete,
    )


def _make_dom(score=50, complete=False):
    return ExtractionCandidate(
        method="playwright_dom", title="Test", content="DOM content " * 20,
        html="<html>dom</html>", final_url="https://example.com",
        quality_score=score, quality_complete=complete,
    )


def _make_net(score=60, complete=False, json_path="$", source_kind="json_string"):
    return BestNetworkCandidate(
        source_url="https://api.example.com/data",
        source_content_type="application/json",
        source_kind=source_kind,
        json_path=json_path,
        content="Network content " * 20,
        quality_score=score,
        ranking_score=score + 5,
        quality_complete=complete,
        content_sha256="abc123",
    )


# ── 最佳网络候选选择 ──

def test_empty_candidates_returns_none():
    assert select_best_network_candidate([]) is None


def test_best_from_complete_candidates():
    """按 ranking_score 选择最佳。"""
    class MockCand:
        pass

    c1 = MockCand()
    c1.content = "A" * 500
    c1.quality_score = 80
    c1.ranking_score = 90
    c1.quality_complete = True
    c1.hints = []
    c1.quality_issues = []
    c1.json_path = "$.data.article.content"
    c1.source_url = "url1"
    c1.source_content_type = "json"
    c1.source_kind = "json_string"
    c1.content_sha256 = "aaa"
    c1.title = ""
    c1.html = ""

    c2 = MockCand()
    c2.content = "B" * 500
    c2.quality_score = 70
    c2.ranking_score = 75
    c2.quality_complete = True
    c2.hints = []
    c2.quality_issues = []
    c2.json_path = "$.data.backup.content"
    c2.source_url = "url2"
    c2.source_content_type = "json"
    c2.source_kind = "json_string"
    c2.content_sha256 = "bbb"
    c2.title = ""
    c2.html = ""

    best = select_best_network_candidate([c1, c2])
    assert best is not None
    assert best.quality_score == 80
    assert best.json_path == "$.data.article.content"


def test_complete_beats_incomplete():
    """complete=True 优先于 incomplete。"""
    class MockCand:
        pass

    c1 = MockCand()
    c1.content = "A" * 500
    c1.quality_score = 30
    c1.ranking_score = 35
    c1.quality_complete = False
    c1.hints = []
    c1.quality_issues = []
    c1.json_path = "$.data.x"
    c1.source_url = "u1"
    c1.source_content_type = "json"
    c1.source_kind = "json_string"
    c1.content_sha256 = "aaa"
    c1.title = ""
    c1.html = ""

    c2 = MockCand()
    c2.content = "B" * 500
    c2.quality_score = 80
    c2.ranking_score = 85
    c2.quality_complete = True
    c2.hints = []
    c2.quality_issues = []
    c2.json_path = "$.data.article"
    c2.source_url = "u2"
    c2.source_content_type = "json"
    c2.source_kind = "json_string"
    c2.content_sha256 = "bbb"
    c2.title = ""
    c2.html = ""

    best = select_best_network_candidate([c1, c2])
    assert best is not None
    assert best.quality_complete is True


def test_fatal_quality_skipped():
    """有致命质量问题的候选被排除。"""
    class MockCand:
        pass

    c1 = MockCand()
    c1.content = "A" * 500
    c1.quality_score = 80
    c1.ranking_score = 85
    c1.quality_complete = True
    c1.hints = []
    c1.quality_issues = ["script_placeholder"]
    c1.json_path = "$.x"
    c1.source_url = "u1"
    c1.source_content_type = "json"
    c1.source_kind = "json_string"
    c1.content_sha256 = "aaa"
    c1.title = ""
    c1.html = ""

    c2 = MockCand()
    c2.content = "B" * 500
    c2.quality_score = 50
    c2.ranking_score = 55
    c2.quality_complete = False
    c2.hints = []
    c2.quality_issues = []
    c2.json_path = "$.y"
    c2.source_url = "u2"
    c2.source_content_type = "json"
    c2.source_kind = "json_string"
    c2.content_sha256 = "bbb"
    c2.title = ""
    c2.html = ""

    best = select_best_network_candidate([c1, c2])
    assert best is not None
    assert best.quality_score == 50  # c2 chosen, c1 skipped


def test_negative_path_penalized():
    """负面路径候选被降级。"""
    class MockCand:
        pass

    c1 = MockCand()
    c1.content = "A" * 500
    c1.quality_score = 90
    c1.ranking_score = 95
    c1.quality_complete = True
    c1.hints = []
    c1.quality_issues = []
    c1.json_path = "$.comments.0.text"
    c1.source_url = "u1"
    c1.source_content_type = "json"
    c1.source_kind = "json_string"
    c1.content_sha256 = "aaa"
    c1.title = ""
    c1.html = ""

    c2 = MockCand()
    c2.content = "B" * 500
    c2.quality_score = 70
    c2.ranking_score = 75
    c2.quality_complete = True
    c2.hints = []
    c2.quality_issues = []
    c2.json_path = "$.article.content"
    c2.source_url = "u2"
    c2.source_content_type = "json"
    c2.source_kind = "json_string"
    c2.content_sha256 = "bbb"
    c2.title = ""
    c2.html = ""

    best = select_best_network_candidate([c1, c2])
    assert best is not None
    # c2 has positive path "article", should be preferred
    assert "article" in (best.json_path or "")
    assert best.quality_score == 70


def test_empty_content_skipped():
    """空正文候选被排除。"""
    class MockCand:
        pass

    c = MockCand()
    c.content = ""
    c.quality_score = 50
    c.quality_complete = True
    c.hints = []
    c.quality_issues = []
    c.json_path = "$.x"

    assert select_best_network_candidate([c]) is None


# ── 三方选择 ──

def test_http_complete_no_render():
    """规则1: HTTP 完整时不启动 Playwright。"""
    http = _make_http(score=80, complete=True)
    dom = _make_dom(score=90, complete=True)
    net = _make_net(score=95, complete=True)

    result = select_best_result(http, dom, net)
    assert result.selected_method == "http"
    assert result.selection_reason == "http_already_complete"


def test_network_complete_dom_incomplete():
    """规则2: Network 完整 DOM 不完整 → 选 Network。"""
    http = _make_http(score=24, complete=False)
    dom = _make_dom(score=47, complete=False)
    net = _make_net(score=89, complete=True, json_path="$.data.article.content")

    result = select_best_result(http, dom, net)
    assert result.selected_method == "playwright_network"
    assert result.selection_reason == "network_result_complete"


def test_dom_complete_network_incomplete():
    """规则3: DOM 完整 Network 不完整 → 选 DOM。"""
    http = _make_http(score=24, complete=False)
    dom = _make_dom(score=70, complete=True)
    net = _make_net(score=40, complete=False)

    result = select_best_result(http, dom, net)
    assert result.selected_method == "playwright_dom"
    assert result.selection_reason == "rendered_dom_complete"


def test_both_complete_prefer_dom():
    """规则4: DOM 和 Network 都完整 → 默认 DOM。"""
    http = _make_http(score=24, complete=False)
    dom = _make_dom(score=70, complete=True)
    net = _make_net(score=75, complete=True)  # 仅高 5 分，不足 8

    result = select_best_result(http, dom, net)
    assert result.selected_method == "playwright_dom"
    assert result.selection_reason == "prefer_dom_for_rich_structure"


def test_network_significantly_higher():
    """规则4: Network 比 DOM 高 >= 8 分 → 选 Network。"""
    http = _make_http(score=24, complete=False)
    dom = _make_dom(score=60, complete=True)
    net = _make_net(score=68, complete=True, json_path="$.article.content")

    result = select_best_result(http, dom, net)
    assert result.selected_method == "playwright_network"
    assert result.selection_reason == "network_score_significantly_higher"


def test_network_margin_below_threshold():
    """规则4: Network 高不足 8 分 → 保留 DOM。"""
    http = _make_http(score=24, complete=False)
    dom = _make_dom(score=70, complete=True)
    net = _make_net(score=77, complete=True)  # 高 7, 不足 8

    result = select_best_result(http, dom, net)
    assert result.selected_method == "playwright_dom"


def test_all_incomplete_highest_wins():
    """规则5: 都不完整时选最高分。"""
    http = _make_http(score=24, complete=False)
    dom = _make_dom(score=50, complete=False)
    net = _make_net(score=30, complete=False)

    result = select_best_result(http, dom, net)
    assert result.selected_method == "playwright_dom"
    assert result.selection_reason == "incomplete_dom_highest"


def test_incomplete_network_needs_margin():
    """规则5: Network 替换不完整需要 >= 5 分优势。"""
    http = _make_http(score=24, complete=False)
    dom = _make_dom(score=50, complete=False)
    net = _make_net(score=56, complete=False)  # 高 6 ≥ 5

    result = select_best_result(http, dom, net)
    assert result.selected_method == "playwright_network"
    assert result.selection_reason == "network_highest_incomplete"


def test_incomplete_network_insufficient_margin():
    """Network 高不足 5 分 → 降级。"""
    http = _make_http(score=24, complete=False)
    dom = _make_dom(score=50, complete=False)
    net = _make_net(score=53, complete=False)  # 高 3 < 5

    result = select_best_result(http, dom, net)
    assert result.selected_method != "playwright_network"
    assert "incomplete" in result.selection_reason


def test_same_score_priority():
    """规则6: 同分时 DOM > HTTP > Network。"""
    http = _make_http(score=50, complete=False)
    dom = _make_dom(score=50, complete=False)
    net = _make_net(score=50, complete=False)

    result = select_best_result(http, dom, net)
    assert result.selected_method == "playwright_dom"


def test_comments_path_not_selected():
    """评论路径的 Network 候选不被选中。"""
    http = _make_http(score=24, complete=False)
    dom = _make_dom(score=70, complete=True)
    net = _make_net(score=95, complete=True,
                    json_path="$.data.comments.0.text")

    result = select_best_result(http, dom, net)
    assert result.selected_method == "playwright_dom"


def test_recommendation_path_not_selected():
    """推荐路径的 Network 候选不被选中。"""
    http = _make_http(score=24, complete=False)
    dom = _make_dom(score=60, complete=True)
    net = _make_net(score=88, complete=True,
                    json_path="$.data.recommend.0")

    result = select_best_result(http, dom, net)
    assert result.selected_method == "playwright_dom"


def test_no_network_candidate():
    """无 Network 候选时正常降级。"""
    http = _make_http(score=24, complete=False)
    dom = _make_dom(score=70, complete=True)

    result = select_best_result(http, dom, None)
    assert result.selected_method == "playwright_dom"
    assert result.network_score == 0


def test_selection_reason_stable():
    """selection_reason 使用稳定机器码。"""
    http = _make_http(score=80, complete=True)
    result = select_best_result(http, None, None)
    assert result.selection_reason == "http_already_complete"

    http2 = _make_http(score=24, complete=False)
    dom = _make_dom(score=70, complete=True)
    result2 = select_best_result(http2, dom, None)
    assert result2.selection_reason == "rendered_dom_complete"


def test_selection_diagnostic_serializable():
    """SelectionResult.to_dict() 可 JSON 序列化。"""
    import json
    http = _make_http(score=24, complete=False)
    dom = _make_dom(score=50, complete=False)
    net = _make_net(score=56, complete=False)

    result = select_best_result(http, dom, net)
    d = result.to_dict()
    json_str = json.dumps(d, ensure_ascii=False)
    assert "playwright_network" in json_str


def test_ranking_score_not_in_direct_comparison():
    """ranking_score 不参与三方直接比较。"""
    http = _make_http(score=24, complete=False)
    dom = _make_dom(score=50, complete=False)
    # ranking_score 很高但不影响三方比较
    net = BestNetworkCandidate(
        source_url="u", source_content_type="json",
        source_kind="json_string", json_path="$",
        content="x" * 200, quality_score=30,
        ranking_score=110,  # 很高
        quality_complete=False,
    )

    result = select_best_result(http, dom, net)
    # 应选 DOM (score 50 > 30)，ranking_score 不影响
    assert result.selected_method == "playwright_dom"


def test_no_alternatives_fallback():
    """没有 DOM 和 Network 时回退到 HTTP。"""
    http = _make_http(score=24, complete=False)
    result = select_best_result(http, None, None)
    assert result.selected_method == "http"
    assert result.selection_reason == "no_alternatives_available"
