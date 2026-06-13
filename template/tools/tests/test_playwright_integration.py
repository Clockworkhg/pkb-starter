#!/usr/bin/env python3
"""Playwright 真实 Chromium 集成测试。

需求: playwright install chromium
运行: python -m pytest tests/test_playwright_integration.py -v -p no:asyncio -p no:anyio
"""

from __future__ import annotations

import http.server
import json as json_mod
import sys
import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("playwright", reason="Playwright is optional; install with: playwright install chromium")

_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "dynamic_site"

pytestmark = pytest.mark.playwright_integration

# ── 测试数据 ──
LONG_ARTICLE = {
    "title": "深度学习在自然语言处理中的最新进展",
    "content": (
        "深度学习是机器学习的一个核心分支，它利用多层神经网络从海量数据中自动学习层次化的特征表示。"
        "自然语言处理作为人工智能领域的关键方向，致力于让计算机理解、生成和处理人类语言。"
        "传统的NLP方法依赖于人工设计的特征和规则，面临数据稀疏和泛化能力弱等固有局限。"
        "Transformer架构的提出是NLP领域的分水岭，完全基于自注意力机制实现高效并行训练。"
        "BERT通过掩码语言模型预训练任务，在11项NLP基准测试中刷新了记录。"
        "GPT系列模型展示了自回归语言模型在少样本和零样本场景下的惊人能力。"
        "在实际应用中，深度学习NLP系统在机器翻译、情感分析和智能问答等领域取得了突破。"
        "当前深度NLP模型面临可解释性不足、训练成本高昂、对数据分布偏移敏感等挑战。"
    ),
    "blocks": [
        "深度学习是机器学习的一个核心分支，它利用多层神经网络从海量数据中自动学习层次化的特征表示。",
        "自然语言处理作为人工智能领域的关键方向，致力于让计算机理解、生成和处理人类语言。",
        "传统的NLP方法依赖于人工设计的特征和规则，面临数据稀疏和泛化能力弱等固有局限。",
        "Transformer架构的提出是NLP领域的分水岭，完全基于自注意力机制实现高效并行训练。",
        "BERT通过掩码语言模型预训练任务，在11项NLP基准测试中刷新了记录。",
        "GPT系列模型展示了自回归语言模型在少样本和零样本场景下的惊人能力。",
        "在实际应用中，深度学习NLP系统在机器翻译、情感分析和智能问答等领域取得了突破。",
        "当前深度NLP模型面临可解释性不足、训练成本高昂、对数据分布偏移敏感等挑战。",
    ],
}


# ── 测试服务器 Handler ──
class _TestHandler(http.server.SimpleHTTPRequestHandler):
    """T_: 前缀避免 pytest 收集为测试类。"""
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=str(FIXTURES_DIR), **kw)

    def do_GET(self):
        if self.path == "/api/article":
            body = json_mod.dumps(LONG_ARTICLE, ensure_ascii=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            super().do_GET()

    def log_message(self, fmt, *args):
        pass


# ── 共享 fixture ──

@pytest.fixture(scope="module")
def dynamic_base_url():
    """启动动态测试服务器，返回 base URL。"""
    server = http.server.HTTPServer(("127.0.0.1", 0), _TestHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    thread.join(timeout=2)


@pytest.fixture(scope="module")
def pw_browser():
    """整个模块共享一个 Playwright browser 实例。"""
    from playwright.sync_api import sync_playwright
    pw = sync_playwright().start()
    browser = pw.chromium.launch()
    yield browser
    browser.close()
    pw.stop()


def _wait_for_content(page, timeout_ms=10000):
    """等待 JS 将正文插入 DOM 并 API 响应完成。"""
    try:
        page.wait_for_function(
            "document.getElementById('loading') === null",
            timeout=timeout_ms,
        )
    except Exception:
        pass
    time.sleep(0.5)  # 额外等待网络响应事件完成传播


# ── 测试 ──

def test_1_chromium_launch(pw_browser):
    """Chromium 可以启动。"""
    assert pw_browser.is_connected()


def test_2_page_navigate(pw_browser, dynamic_base_url):
    """page 能访问动态端口本地服务器。"""
    page = pw_browser.new_page()
    page.goto(dynamic_base_url, wait_until="domcontentloaded")
    assert page.title() is not None
    page.close()


def test_3_listener_capture(pw_browser, dynamic_base_url):
    """网络监听器捕获 JS fetch 的 JSON 响应。"""
    from network_capture import ResponseCaptureSession, NetworkCaptureOptions

    page = pw_browser.new_page()
    opts = NetworkCaptureOptions(enabled=True)
    session = ResponseCaptureSession(opts)
    session.attach(page)

    page.goto(dynamic_base_url, wait_until="domcontentloaded")
    _wait_for_content(page)

    session.finalize()
    diag = session.get_diagnostic()
    responses = session.get_responses()
    json_resps = [r for r in responses if "json" in r.content_type]

    assert diag.total_responses_seen >= 1, f"应至少有 1 个响应, got {diag.total_responses_seen}"
    assert len(json_resps) > 0, (
        f"应捕获 JSON API 响应, got: {[r.content_type for r in responses]}, "
        f"total_seen={diag.total_responses_seen}, eligible={diag.eligible_responses_seen}"
    )

    session.close()
    page.close()


def test_4_empty_shell_not_content(pw_browser, dynamic_base_url):
    """初始空壳不被误判为正文。"""
    from content_quality import assess_article

    page = pw_browser.new_page()
    page.goto(dynamic_base_url, wait_until="domcontentloaded")
    html = page.content()
    report = assess_article("测试", "", html)
    assert not report.complete, "初始空壳不应被判为完整"
    page.close()


def test_5_network_candidates(pw_browser, dynamic_base_url):
    """JSON 正文生成 Network 候选。"""
    from network_capture import ResponseCaptureSession, NetworkCaptureOptions
    from network_content import extract_candidates

    page = pw_browser.new_page()
    opts = NetworkCaptureOptions(enabled=True)
    session = ResponseCaptureSession(opts)
    session.attach(page)

    page.goto(dynamic_base_url, wait_until="domcontentloaded")
    _wait_for_content(page)

    session.finalize()
    responses = session.get_responses()
    diag = session.get_diagnostic()

    candidates = extract_candidates(responses, opts, diag, page_title=page.title())
    assert len(candidates) > 0, (
        f"应生成 Network 候选, responses={len(responses)}, "
        f"ctypes={[r.content_type for r in responses]}"
    )
    assert candidates[0].quality_score > 30, f"评分应 > 30, got {candidates[0].quality_score}"

    session.close()
    page.close()


def test_6_dom_from_js(pw_browser, dynamic_base_url):
    """JS 插入的正文生成 DOM 候选。"""
    from web_pack import _extract_content_from_html
    from content_quality import assess_article

    page = pw_browser.new_page()
    page.goto(dynamic_base_url, wait_until="domcontentloaded")
    _wait_for_content(page)

    html = page.content()
    result = _extract_content_from_html(html, dynamic_base_url)
    assert result is not None, "应从渲染后 HTML 提取正文"
    title, markdown, method = result
    report = assess_article(title, markdown, html)
    assert report.score > 30, f"评分应 > 30, got {report.score}"

    page.close()


def test_7_scroll_lazy(pw_browser, dynamic_base_url):
    """滚动触发懒加载。"""
    page = pw_browser.new_page()
    page.goto(dynamic_base_url, wait_until="domcontentloaded")
    _wait_for_content(page)

    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
    time.sleep(1.0)

    content_after = page.content()
    assert len(content_after) > 0
    page.close()


def test_8_selection_integration(pw_browser, dynamic_base_url):
    """DOM 和 Network 选择结果合理。"""
    from network_capture import ResponseCaptureSession, NetworkCaptureOptions
    from network_content import extract_candidates
    from web_pack import _extract_content_from_html
    from content_quality import assess_article
    from selection_engine import (
        ExtractionCandidate, select_best_network_candidate, select_best_result,
    )

    page = pw_browser.new_page()
    opts = NetworkCaptureOptions(enabled=True)
    session = ResponseCaptureSession(opts)
    session.attach(page)

    page.goto(dynamic_base_url, wait_until="domcontentloaded")
    _wait_for_content(page)

    session.finalize()
    candidates = extract_candidates(session.get_responses(), opts,
                                     session.get_diagnostic(), page_title=page.title())

    html = page.content()
    dom_result = _extract_content_from_html(html, dynamic_base_url)
    dom_title, dom_md, dom_method = dom_result if dom_result else ("", "", "")
    dom_report = assess_article(dom_title, dom_md, html) if dom_result else None

    http_c = ExtractionCandidate(
        method="http", title="", content="short", html="",
        final_url=dynamic_base_url, quality_score=10, quality_complete=False,
    )
    dom_c = ExtractionCandidate(
        method="playwright_dom", title=dom_title, content=dom_md,
        html=html, final_url=dynamic_base_url,
        quality_score=dom_report.score if dom_report else 0,
        quality_complete=dom_report.complete if dom_report else False,
    ) if dom_result else None

    best_net = select_best_network_candidate(candidates) if candidates else None

    if dom_c and best_net:
        result = select_best_result(http_c, dom_c, best_net)
        assert result.selected_method in ("playwright_dom", "playwright_network"), \
            f"Unexpected method: {result.selected_method}"
        assert result.selection_reason != ""

    session.close()
    page.close()


def test_9_sensitive_redaction(pw_browser, dynamic_base_url):
    """敏感 URL 参数脱敏。"""
    from network_capture import sanitize_url

    url_with_secrets = (
        f"{dynamic_base_url}?token=KNOWN_SECRET_123"
        f"&hkey=KNOWN_HKEY_456"
        f"&signature=KNOWN_SIGNATURE_789"
    )
    sanitized = sanitize_url(url_with_secrets)
    assert "KNOWN_SECRET_123" not in sanitized
    assert "KNOWN_HKEY_456" not in sanitized
    assert "KNOWN_SIGNATURE_789" not in sanitized
    assert sanitized.count("***REDACTED***") == 3


def test_10_browser_close(pw_browser):
    """Browser 正确保持和清理。"""
    assert pw_browser.is_connected()
    page = pw_browser.new_page()
    page.goto("about:blank", wait_until="domcontentloaded")
    page.close()
    assert pw_browser.is_connected()
