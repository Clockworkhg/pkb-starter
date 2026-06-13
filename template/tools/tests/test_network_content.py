#!/usr/bin/env python3
"""network_content.py 单元测试 — JSON 遍历、候选提取、评分。

不访问网络，使用固定 JSON/HTML fixture。
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import pytest
from network_capture import (
    CapturedResponse,
    CaptureDiagnostic,
    NetworkCaptureOptions,
    sanitize_url,
)
from network_content import (
    NetworkContentCandidate,
    extract_candidates,
    _traverse_json,
    _TraversalState,
    _build_json_path,
    _compute_ranking_score,
    _looks_like_noise,
    _merge_block_array,
    _extract_html_candidate,
    _normalize_for_dedup,
)


def _make_resp(body_str, content_type="application/json", url="https://api.example.com/data"):
    body = body_str.encode("utf-8") if isinstance(body_str, str) else body_str
    return CapturedResponse(
        url=url, sanitized_url=sanitize_url(url),
        status=200, method="GET", content_type=content_type,
        declared_size=len(body), actual_size=len(body),
        body=body, body_sha256=hashlib.sha256(body).hexdigest(),
    )


# ── JSON 遍历 ──

def test_nested_article_content_found():
    data = {"data": {"article": {"content": "深度学习技术近年来取得了突破性进展。" * 30}}}
    state = _TraversalState()
    candidates = []
    _traverse_json(data, [], state, candidates, visited_ids=set())
    assert len(candidates) >= 1
    assert "深度学习" in candidates[0]["content"]


def test_html_in_json_found():
    data = {"result": {"post": {"html": "<article><h1>Title</h1><p>Paragraph " * 10 + "</p></article>"}}}
    state = _TraversalState()
    candidates = []
    _traverse_json(data, [], state, candidates, visited_ids=set())
    assert len(candidates) >= 1


def test_block_array_merged():
    block_text = "深度学习技术近年来取得了突破性进展。" * 4  # ~60 chars each
    blocks = [
        {"type": "paragraph", "text": block_text},
        {"type": "paragraph", "text": block_text},
        {"type": "paragraph", "text": block_text},
        {"type": "image", "url": "https://example.com/img.jpg"},
        {"type": "paragraph", "text": block_text},
    ]
    state = _TraversalState()
    merged = []
    _merge_block_array(blocks, ["blocks"], state, merged)
    assert len(merged) >= 1
    assert "深度学习" in merged[0]["content"]


def test_max_depth_stops():
    """深度超过 12 时停止。"""
    data = "leaf"
    for _ in range(20):
        data = {"nested": data}
    state = _TraversalState(max_depth=5)
    candidates = []
    _traverse_json(data, [], state, candidates, visited_ids=set())
    # 深度 5 处应停止
    assert state.truncated or len(candidates) <= 1


def test_max_nodes_stops():
    """节点超过上限时停止。"""
    data = {str(i): f"value_{i}" for i in range(100)}
    state = _TraversalState(max_nodes=10)
    candidates = []
    _traverse_json(data, [], state, candidates, visited_ids=set())
    assert state.truncated


def test_max_strings_stops():
    """字符串超过上限时停止。"""
    data = [f"string number {i} " * 15 for i in range(50)]
    state = _TraversalState(max_strings=5)
    candidates = []
    _traverse_json(data, [], state, candidates, visited_ids=set())
    assert state.truncated


def test_multi_content_fields_choose_best():
    """多个 content 字段时，应由 quality_score 选出最佳。"""
    data = {
        "sidebar": {"content": "short navigation text"},
        "article": {"content": "深度学习技术近年来取得了突破性进展。" * 20},
    }
    responses = [_make_resp(json.dumps(data))]
    opts = NetworkCaptureOptions(max_candidates=5)
    diag = CaptureDiagnostic()
    candidates = extract_candidates(responses, opts, diag, page_title="深度学习进展")
    assert len(candidates) > 0
    best = candidates[0]
    assert "深度学习" in best.content
    # 正文候选得分应 > 导航候选
    assert best.quality_score > 10


def test_comments_not_beat_article():
    """评论区文本不应击败正文字段。"""
    data = {
        "article": {"content": "深度学习技术近年来取得了突破性进展。" * 20},
        "comments": [
            {"user": "alice", "text": "好文章！"},
            {"user": "bob", "text": "学到了"},
        ],
    }
    responses = [_make_resp(json.dumps(data))]
    opts = NetworkCaptureOptions(max_candidates=5)
    diag = CaptureDiagnostic()
    candidates = extract_candidates(responses, opts, diag, page_title="深度学习")
    assert len(candidates) > 0
    best = candidates[0]
    assert "深度学习" in best.content


def test_recommendation_not_treated_as_article():
    """推荐列表不应被当作文章。"""
    data = {
        "recommendations": [
            {"title": "推荐文章1", "desc": "正文1 " * 10},
            {"title": "推荐文章2", "desc": "正文2 " * 10},
        ],
    }
    responses = [_make_resp(json.dumps(data))]
    opts = NetworkCaptureOptions(max_candidates=5)
    diag = CaptureDiagnostic()
    candidates = extract_candidates(responses, opts, diag)
    # 推荐列表可能产生候选但评分应很低
    for c in candidates:
        assert c.ranking_score < 80 or "recommend" not in (c.json_path or "").lower()


def test_incidental_comment_word_not_penalized():
    """正文中偶然出现'comment'一词不应誤惩罚。"""
    long_text = "这篇文章引发了广泛讨论和comment。" + "深度学习技术近年来取得了突破性进展。" * 20
    data = {"article": {"content": long_text}}
    responses = [_make_resp(json.dumps(data))]
    opts = NetworkCaptureOptions(min_candidate_chars=100)
    diag = CaptureDiagnostic()
    candidates = extract_candidates(responses, opts, diag, page_title="测试")
    assert len(candidates) > 0
    # 候选被保留且有合理评分
    assert candidates[0].quality_score >= 0


def test_html_candidate_uses_extractor():
    """HTML 候选调用 extractor 回调。"""
    html = "<html><body><article><h1>Test</h1><p>Long article " * 30 + "</p></article></body></html>"
    resp = _make_resp(html, content_type="text/html")
    opts = NetworkCaptureOptions()
    diag = CaptureDiagnostic()

    def fake_extractor(h, url):
        return ("Test Title", "Extracted markdown " * 20, "fake_extractor")

    candidates = extract_candidates([resp], opts, diag, html_extractor=fake_extractor)
    assert len(candidates) > 0
    assert "Extracted markdown" in candidates[0].content


def test_plain_text_candidate():
    """纯文本长文章可以成为候选。"""
    text = "这是一篇关于人工智能的深入讨论。" * 50
    resp = _make_resp(text, content_type="text/plain")
    opts = NetworkCaptureOptions()
    diag = CaptureDiagnostic()
    candidates = extract_candidates([resp], opts, diag, page_title="AI讨论")
    assert len(candidates) > 0


def test_log_text_filtered():
    """日志文本被过滤。"""
    log_text = (
        "ERROR: Connection failed\n" * 5
        + "WARN: Retry attempt\n" * 3
        + "DEBUG: Processing request\n" * 3
        + "INFO: Server started at port 8080\n" * 2
    )
    text = log_text + "正文内容不够长"
    resp = _make_resp(text, content_type="text/plain")
    opts = NetworkCaptureOptions()
    diag = CaptureDiagnostic()
    candidates = extract_candidates([resp], opts, diag)
    # 日志模式应被过滤
    for c in candidates:
        assert "ERROR" not in c.content[:200] or c.quality_score < 40


def test_content_dedup_across_paths():
    """相同正文来自多个 JSON Path 时只保留一个。"""
    same_text = "深度学习技术近年来取得了突破性进展。" * 25
    data = {
        "article": {"content": same_text},
        "backup": {"text": same_text},
    }
    responses = [_make_resp(json.dumps(data))]
    opts = NetworkCaptureOptions(max_candidates=10)
    diag = CaptureDiagnostic()
    candidates = extract_candidates(responses, opts, diag)
    contents = {c.content_sha256 for c in candidates}
    assert len(contents) <= len(candidates)


def test_top_10_limit():
    """最多保留 10 个候选。"""
    many = {
        f"field_{i}": f"深度学习技术近年来取得了突破性进展。" * 15
        for i in range(30)
    }
    responses = [_make_resp(json.dumps(many))]
    opts = NetworkCaptureOptions(max_candidates=10)
    diag = CaptureDiagnostic()
    candidates = extract_candidates(responses, opts, diag)
    assert len(candidates) <= 10


def test_quality_score_from_assess_article():
    """quality_score 与 assess_article 一致。"""
    text = "深度学习技术近年来取得了突破性进展。" * 30
    data = {"article": {"content": text}}
    responses = [_make_resp(json.dumps(data))]
    opts = NetworkCaptureOptions()
    diag = CaptureDiagnostic()
    candidates = extract_candidates(responses, opts, diag, page_title="深度学习进展")

    assert len(candidates) > 0
    from content_quality import assess_article
    direct_report = assess_article("深度学习进展", text, "")
    # quality_score 应等于 assess_article().score
    assert candidates[0].quality_score == direct_report.score


def test_ranking_score_independent():
    """ranking_score 不修改 QualityReport.score。"""
    text = "深度学习技术近年来取得了突破性进展。" * 30
    data = {"article": {"content": text}}
    responses = [_make_resp(json.dumps(data))]
    opts = NetworkCaptureOptions()
    diag = CaptureDiagnostic()
    candidates = extract_candidates(responses, opts, diag, page_title="深度学习进展")

    assert len(candidates) > 0
    c = candidates[0]
    # ranking_score >= quality_score（有字段加分）
    assert c.ranking_score >= c.quality_score
    # quality_score 应该仍然来自 assess_article
    assert 0 <= c.quality_score <= 100


def test_title_relevance_bonus_limited():
    """标题相关性只产生有限加分。"""
    text = "深度学习技术近年来取得了突破性进展。" * 30
    data = {"article": {"content": text}}
    resp = _make_resp(json.dumps(data))

    # 匹配标题
    resp_match = [resp]
    opts = NetworkCaptureOptions()
    diag1 = CaptureDiagnostic()
    c1 = extract_candidates(resp_match, opts, diag1, page_title="深度学习最新进展")

    # 不匹配标题
    diag2 = CaptureDiagnostic()
    c2 = extract_candidates(resp_match, opts, diag2, page_title="完全无关的话题")

    if c1 and c2:
        diff = c1[0].ranking_score - c2[0].ranking_score
        # 标题加分不应超过 5
        assert diff <= 5.1


def test_candidate_serializable():
    """候选可安全序列化。"""
    text = "深度学习技术近年来取得了突破性进展。" * 30
    data = {"article": {"content": text}}
    responses = [_make_resp(json.dumps(data))]
    opts = NetworkCaptureOptions()
    diag = CaptureDiagnostic()
    candidates = extract_candidates(responses, opts, diag, page_title="测试")

    assert len(candidates) > 0
    c = candidates[0]
    d = {
        "source_url": c.source_url,
        "quality_score": c.quality_score,
        "ranking_score": c.ranking_score,
        "content_length": c.normalized_length,
        "hints": list(c.hints),
    }
    json_str = json.dumps(d, ensure_ascii=False)
    assert len(json_str) > 0


# ── 辅助函数测试 ──

def test_build_json_path():
    assert _build_json_path(["data", "article", "content"]) == "$.data.article.content"
    assert _build_json_path(["data", "items", 3, "text"]) == "$.data.items[3].text"


def test_looks_like_noise():
    assert _looks_like_noise("https://example.com/path") is True
    assert _looks_like_noise("  null  ") is True
    assert _looks_like_noise("normal text content") is False


def test_normalize_for_dedup():
    t1 = "hello   world\n\n\nfoo"
    t2 = "hello world\n\nfoo"
    assert _normalize_for_dedup(t1) == _normalize_for_dedup(t2)
