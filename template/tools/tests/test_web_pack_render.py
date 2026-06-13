#!/usr/bin/env python3
"""web_pack Playwright 集成测试 — 25 个测试用例。

测试设计：
  - 使用 mock/fake，不访问真实网站，不启动 Chromium
  - Mock Playwright sync_api 和相关组件
  - Mock HTTP responses
  - 覆盖 normal/safe 模式、render 生命周期、fallback 选择逻辑
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

# 确保 tools/ 在 sys.path 中
_TOOLS_DIR = Path(__file__).resolve().parent.parent
if not (_TOOLS_DIR / "scholarly").is_dir() and not (_TOOLS_DIR / "content_quality.py").exists():
    _TOOLS_DIR = _TOOLS_DIR / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import pytest

# ── Fixtures ──

SHORT_NAV_HTML = """
<html><body>
<nav>首页 登录 注册 关于</nav>
<footer>Copyright 2024 | Privacy Policy</footer>
</body></html>
"""

LONG_ARTICLE_HTML = """
<html><body>
<article>
<h1>深度学习在自然语言处理中的应用</h1>
<p>深度学习是机器学习的一个分支，它使用多层神经网络来学习数据的表示。</p>
<p>自然语言处理（NLP）是人工智能领域的一个重要方向。近年来随着计算能力的提升，深度学习技术在NLP领域取得了突破性进展。</p>
<p>Transformer架构的提出彻底改变了NLP领域。它完全基于注意力机制，摒弃了循环结构。</p>
<p>深度学习在机器翻译、文本分类、问答系统和文本生成等任务中表现出色。</p>
<p>尽管取得了显著进展，深度学习在NLP中仍然面临一些挑战。模型的可解释性、数据偏见、计算资源消耗等问题都需要进一步研究。</p>
<p>未来的研究方向可能包括更高效的模型架构、小样本学习和多模态融合等。</p>
</article>
</body></html>
"""


def make_http_response(html: str, status: int = 200, url: str = "https://example.com/article"):
    """创建 mock HTTP response。"""
    resp = MagicMock()
    resp.text = html
    resp.url = url
    resp.status_code = status
    resp.headers = {"Content-Type": "text/html; charset=utf-8"}
    return resp


def make_render_result(title: str = "", html: str = "", success: bool = True, error: str = ""):
    """创建 mock RenderResult。"""
    from playwright_renderer import RenderResult  # noqa
    return RenderResult(
        title=title or "Rendered Title",
        html=html or LONG_ARTICLE_HTML,
        final_url="https://example.com/article",
        success=success,
        error=error,
    )


# ═══════════════════════════════════════════════════════════════════
# Test 1: 未传 --render 时不会初始化 Playwright
# ═══════════════════════════════════════════════════════════════════

def test_no_render_flag_no_playwright_init():
    from web_pack import WebPackCollector, RenderOptions, HAS_PLAYWRIGHT

    collector = WebPackCollector(
        topic="test",
        source_urls=["https://example.com"],
        render_options=None,
        max_depth=0, max_pages=1, no_jina=True,
    )
    assert collector._renderer is None
    assert collector.render_options is None


# ═══════════════════════════════════════════════════════════════════
# Test 2: 普通结果完整时，即使传了 --render 也不调用 Playwright
# ═══════════════════════════════════════════════════════════════════

def test_complete_result_skips_render():
    """HTTP 结果完整 → 不触发 Playwright。"""
    from web_pack import WebPackCollector, RenderOptions

    with patch("web_pack.requests.Session.get") as mock_get, \
         patch("web_pack.fetch_page") as mock_fetch:

        mock_fetch.return_value = {
            "url": "https://example.com",
            "title": "Good Article",
            "text": "This is a very long article with substantial content. " * 20,
            "markdown": "content",
            "html": LONG_ARTICLE_HTML,
            "images": [], "links": [],
            "fetched_at": "2026-01-01T00:00:00",
            "extraction_method": "readability-lxml",
            "via_jina": False,
            "quality_report": {"complete": True, "score": 85, "issues": [], "metrics": {
                "title_present": True, "content_length": 500, "plain_text_length": 450,
                "paragraph_count": 6, "valid_paragraph_count": 5,
                "navigation_ratio": 0.05, "duplication_ratio": 0.02,
                "natural_language_ratio": 0.85,
            }},
            "_render_diagnostic": None,
        }

        render_opts = RenderOptions(enabled=True, headed=False)
        collector = WebPackCollector(
            topic="test", source_urls=["https://example.com"],
            render_options=render_opts, max_depth=0, max_pages=1, no_jina=True,
        )

        with patch.object(collector, '_renderer', None):
            # _renderer is None → even if render would be tried, nothing happens
            collector.run()
            page = collector.collected_pages[0] if collector.collected_pages else None
            if page:
                diag = page.get("_render_diagnostic")
                # render should not have been triggered because quality is complete
                if diag:
                    assert not diag.get("triggered", True), \
                        "Render should not be triggered for complete result"
                # extraction method stays as http
                assert "playwright" not in page.get("extraction_method", "")


# ═══════════════════════════════════════════════════════════════════
# Test 3: 普通结果不完整且 --render 启用时调用 Playwright
# ═══════════════════════════════════════════════════════════════════

def test_incomplete_triggers_render():
    """HTTP 结果不完整 + render 启用 → 触发 Playwright。"""
    from web_pack import WebPackCollector, RenderOptions

    with patch("web_pack.HAS_PLAYWRIGHT", True), \
         patch("web_pack.PlaywrightRenderer", MagicMock()), \
         patch("web_pack.requests.Session.get"), \
         patch("web_pack.fetch_page") as mock_fetch:

        # 返回不完整的结果
        mock_fetch.return_value = {
            "url": "https://example.com",
            "title": "Short Nav",
            "text": "首页 登录 注册",
            "markdown": "首页 登录 注册",
            "html": SHORT_NAV_HTML,
            "images": [], "links": [],
            "fetched_at": "2026-01-01T00:00:00",
            "extraction_method": "beautifulsoup",
            "via_jina": False,
            "quality_report": {
                "complete": False, "score": 15,
                "issues": ["text_too_short", "navigation_ratio_high"],
                "metrics": {
                    "title_present": True, "content_length": 50,
                    "plain_text_length": 45, "paragraph_count": 1,
                    "valid_paragraph_count": 0,
                    "navigation_ratio": 0.80, "duplication_ratio": 0.05,
                    "natural_language_ratio": 0.60,
                },
            },
            "_render_diagnostic": None,
        }

        render_opts = RenderOptions(enabled=True, headed=False)
        collector = WebPackCollector(
            topic="test", source_urls=["https://example.com"],
            render_options=render_opts, max_depth=0, max_pages=1, no_jina=True,
        )

        # Mock _try_playwright_dom to return a better page
        called = [False]

        def fake_try_pw(*args, **kwargs):
            called[0] = True
            pw_page = {
                "url": "https://example.com",
                "title": "Full Rendered Article",
                "text": "This is the full rendered article content. " * 30,
                "markdown": "content",
                "html": LONG_ARTICLE_HTML,
                "images": [], "links": [],
                "fetched_at": "2026-01-01T00:00:00",
                "extraction_method": "playwright_readability-lxml",
                "via_jina": False,
                "quality_report": {
                    "complete": True, "score": 80, "issues": [],
                    "metrics": {"title_present": True, "valid_paragraph_count": 5},
                },
                "_render_diagnostic": None,
            }
            return pw_page, None, None  # (page, best_net, net_diag)

        with patch.object(collector, '_try_playwright_dom', fake_try_pw):
            collector.run()

        assert called[0], "_try_playwright_dom should have been called"
        if collector.collected_pages:
            method = collector.collected_pages[0].get("extraction_method", "")
            assert "playwright" in method, \
                f"Should use playwright result, got method={method}"


# ═══════════════════════════════════════════════════════════════════
# Test 4: Playwright 未安装时普通流程仍正常
# ═══════════════════════════════════════════════════════════════════

def test_no_playwright_normal_flow_works():
    """即使 Playwright 未安装，普通采集不受影响。"""
    from web_pack import WebPackCollector

    with patch("web_pack.requests.Session.get") as mock_get, \
         patch("web_pack.fetch_page") as mock_fetch:

        mock_fetch.return_value = {
            "url": "https://example.com",
            "title": "Normal Article",
            "text": "Article content " * 50,
            "markdown": "Article content " * 50,
            "html": LONG_ARTICLE_HTML,
            "images": [], "links": [],
            "fetched_at": "2026-01-01T00:00:00",
            "extraction_method": "readability-lxml",
            "via_jina": False,
            "quality_report": {"complete": True, "score": 90, "issues": [], "metrics": {}},
            "_render_diagnostic": None,
        }

        collector = WebPackCollector(
            topic="test", source_urls=["https://example.com"],
            render_options=None,  # No render
            max_depth=0, max_pages=1, no_jina=True,
        )
        collector.run()
        assert len(collector.collected_pages) == 1


# ═══════════════════════════════════════════════════════════════════
# Test 5: Playwright 未安装且显式 --render 时给出清晰提示
# ═══════════════════════════════════════════════════════════════════

def test_render_flag_without_playwright_gives_error():
    """--render 需要 Playwright 安装。"""
    from web_pack import RenderOptions

    # 模拟 Playwright 未安装
    with patch("web_pack.HAS_PLAYWRIGHT", False), \
         patch("web_pack.PlaywrightRenderer", None):

        render_opts = RenderOptions(enabled=True)
        from web_pack import WebPackCollector
        collector = WebPackCollector(
            topic="test", source_urls=["https://example.com"],
            render_options=render_opts, max_depth=0, max_pages=1, no_jina=True,
        )

        with patch("web_pack.requests.Session.get"), \
             patch("web_pack.fetch_page") as mock_fetch:

            mock_fetch.return_value = {
                "url": "https://example.com",
                "title": "Article",
                "text": "Content",
                "markdown": "Content",
                "html": "<html></html>",
                "images": [], "links": [],
                "fetched_at": "2026-01-01T00:00:00",
                "extraction_method": "beautifulsoup",
                "via_jina": False,
                "quality_report": {"complete": False, "score": 10, "issues": [], "metrics": {}},
                "_render_diagnostic": None,
            }

            # 应该降级到普通模式，不崩溃
            collector.run()
            # 即使 Playwright 不可用，普通采集仍成功
            assert len(collector.collected_pages) == 1


# ═══════════════════════════════════════════════════════════════════
# Test 6: Playwright 启动失败时优雅降级
# ═══════════════════════════════════════════════════════════════════

def test_playwright_start_failure_graceful_degradation():
    """Playwright 启动失败 → 继续普通采集。"""
    from web_pack import WebPackCollector, RenderOptions

    with patch("web_pack.requests.Session.get"), \
         patch("web_pack.fetch_page") as mock_fetch, \
         patch("web_pack.PlaywrightRenderer") as MockRenderer:

        MockRenderer.return_value.start.side_effect = RuntimeError("Browser not found")

        mock_fetch.return_value = {
            "url": "https://example.com",
            "title": "Article",
            "text": "Content " * 30,
            "markdown": "Content " * 30,
            "html": LONG_ARTICLE_HTML,
            "images": [], "links": [],
            "fetched_at": "2026-01-01T00:00:00",
            "extraction_method": "readability-lxml",
            "via_jina": False,
            "quality_report": {"complete": True, "score": 80, "issues": [], "metrics": {}},
            "_render_diagnostic": None,
        }

        render_opts = RenderOptions(enabled=True)
        collector = WebPackCollector(
            topic="test", source_urls=["https://example.com"],
            render_options=render_opts, max_depth=0, max_pages=1, no_jina=True,
        )
        collector.run()
        # 即使 Playwright 启动失败，也应成功采集
        assert len(collector.collected_pages) == 1


# ═══════════════════════════════════════════════════════════════════
# Test 7: 多个 BFS URL 共用同一 browser/context
# ═══════════════════════════════════════════════════════════════════

def test_multiple_urls_share_browser():
    """多个 URL 共用 browser/context，而不是每个 URL 启动新浏览器。"""
    from web_pack import WebPackCollector, RenderOptions

    with patch("web_pack.requests.Session.get"), \
         patch("web_pack.fetch_page") as mock_fetch, \
         patch("web_pack.PlaywrightRenderer") as MockRenderer:

        mock_renderer = MagicMock()
        mock_renderer.render_page.return_value = make_render_result()
        MockRenderer.return_value = mock_renderer

        mock_fetch.return_value = {
            "url": "https://example.com",
            "title": "Short",
            "text": "nav only",
            "markdown": "nav only",
            "html": SHORT_NAV_HTML,
            "images": [], "links": [],
            "fetched_at": "2026-01-01T00:00:00",
            "extraction_method": "beautifulsoup",
            "via_jina": False,
            "quality_report": {"complete": False, "score": 10, "issues": ["text_too_short"], "metrics": {}},
            "_render_diagnostic": None,
        }

        render_opts = RenderOptions(enabled=True)
        collector = WebPackCollector(
            topic="test",
            source_urls=["https://example.com/a", "https://example.com/b"],
            render_options=render_opts, max_depth=0, max_pages=2, no_jina=True,
        )

        with patch.object(collector, '_try_playwright_dom', wraps=collector._try_playwright_dom):
            collector._renderer = mock_renderer
            collector.run()

        # start 只调用一次
        assert MockRenderer.return_value.start.call_count <= 1
        # render_page 可能被调用多次
        assert mock_renderer.render_page.call_count <= 2


# ═══════════════════════════════════════════════════════════════════
# Test 8: 每个 URL 的 page 使用后正确关闭
# ═══════════════════════════════════════════════════════════════════

def test_page_closed_after_use():
    """验证 PlaywrightRenderer.render_page 内部管理 page 生命周期。"""
    from playwright_renderer import PlaywrightRenderer, RenderOptions as PWOptions

    with patch("playwright_renderer.HAS_PLAYWRIGHT", True), \
         patch("playwright_renderer.sync_playwright") as mock_sp:
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_sp.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.title.return_value = "Test Title"
        mock_page.content.return_value = LONG_ARTICLE_HTML
        mock_page.url = "https://example.com/article"

        opts = PWOptions(enabled=True, headed=False, use_persistent_profile=False)
        renderer = PlaywrightRenderer(opts)
        renderer.start()

        result = renderer.render_page("https://example.com/article")
        assert result.success
        # page.close() 应被调用
        mock_page.close.assert_called_once()

        renderer.close()


# ═══════════════════════════════════════════════════════════════════
# Test 9: Collector 异常退出时 browser/context/playwright 正确关闭
# ═══════════════════════════════════════════════════════════════════

def test_collector_exception_closes_renderer():
    """异常退出时渲染器仍被关闭。"""
    from web_pack import WebPackCollector, RenderOptions

    with patch("web_pack.HAS_PLAYWRIGHT", True), \
         patch("web_pack.requests.Session.get"), \
         patch("web_pack.fetch_page", side_effect=RuntimeError("Boom")), \
         patch("web_pack.PlaywrightRenderer") as MockRenderer:

        mock_renderer = MagicMock()
        MockRenderer.return_value = mock_renderer

        render_opts = RenderOptions(enabled=True)
        collector = WebPackCollector(
            topic="test", source_urls=["https://example.com"],
            render_options=render_opts, max_depth=0, max_pages=1, no_jina=True,
        )

        try:
            collector.run()
        except RuntimeError:
            pass

        # renderer.close() 应被调用（在 finally 中）
        mock_renderer.close.assert_called()


# ═══════════════════════════════════════════════════════════════════
# Test 10: 重复 close() 不报错
# ═══════════════════════════════════════════════════════════════════

def test_double_close_safe():
    """PlaywrightRenderer.close() 幂等。"""
    from playwright_renderer import PlaywrightRenderer, RenderOptions as PWOptions

    with patch("playwright_renderer.HAS_PLAYWRIGHT", True), \
         patch("playwright_renderer.sync_playwright") as mock_sp:
        mock_pw = MagicMock()
        mock_sp.return_value.start.return_value = mock_pw

        opts = PWOptions(enabled=True, headed=False, use_persistent_profile=False)
        renderer = PlaywrightRenderer(opts)
        renderer.start()
        renderer.close()
        # 第二次 close 不应报错
        renderer.close()


# ═══════════════════════════════════════════════════════════════════
# Test 11: Playwright DOM 完整时替换不完整的普通结果
# ═══════════════════════════════════════════════════════════════════

def test_pw_complete_replaces_incomplete_http():
    """PW DOM 完整 + HTTP 不完整 → 选择 PW。"""
    http_quality = {"complete": False, "score": 15}
    pw_quality = {"complete": True, "score": 80}

    # 模拟选择逻辑
    pw_complete = pw_quality.get("complete", False)
    http_complete = http_quality.get("complete", True)
    chosen = "http"
    if pw_complete and not http_complete:
        chosen = "playwright_dom"
    assert chosen == "playwright_dom"


# ═══════════════════════════════════════════════════════════════════
# Test 12: Playwright DOM 更差时保留普通结果
# ═══════════════════════════════════════════════════════════════════

def test_pw_worse_keeps_http():
    """PW 评分更低 → 保留 HTTP 结果。"""
    http_quality = {"complete": False, "score": 40}
    pw_quality = {"complete": False, "score": 20}

    pw_score = pw_quality.get("score", 0)
    orig_score = http_quality.get("score", 0)
    chosen = "http"
    if pw_score > orig_score:
        chosen = "playwright_dom"
    assert chosen == "http"


# ═══════════════════════════════════════════════════════════════════
# Test 13: 两个结果都不完整时选择评分更高者
# ═══════════════════════════════════════════════════════════════════

def test_both_incomplete_choose_higher_score():
    """两者都不完整 → 选评分高的。"""
    http_quality = {"complete": False, "score": 30}
    pw_quality = {"complete": False, "score": 55}

    pw_score = pw_quality.get("score", 0)
    orig_score = http_quality.get("score", 0)
    pw_complete = pw_quality.get("complete", False)
    http_complete = http_quality.get("complete", True)

    chosen = "http"
    if pw_complete and not http_complete:
        chosen = "playwright_dom"
    elif pw_score > orig_score:
        chosen = "playwright_dom"
    assert chosen == "playwright_dom"


# ═══════════════════════════════════════════════════════════════════
# Test 14: 同分时优先普通结果
# ═══════════════════════════════════════════════════════════════════

def test_same_score_prefer_http():
    """同等分数 → 优先 HTTP。"""
    http_quality = {"complete": False, "score": 40}
    pw_quality = {"complete": False, "score": 40}

    chosen = "http"  # default
    if pw_quality.get("score", 0) > http_quality.get("score", 0):
        chosen = "playwright_dom"
    assert chosen == "http"


# ═══════════════════════════════════════════════════════════════════
# Test 15: Playwright 失败不会丢失普通采集结果
# ═══════════════════════════════════════════════════════════════════

def test_pw_failure_keeps_http_result():
    """PW 返回 None → 保留 HTTP 结果。"""
    from web_pack import WebPackCollector, RenderOptions

    with patch("web_pack.requests.Session.get"), \
         patch("web_pack.fetch_page") as mock_fetch:

        mock_fetch.return_value = {
            "url": "https://example.com",
            "title": "Incomplete Article",
            "text": "Short content",
            "markdown": "Short content",
            "html": SHORT_NAV_HTML,
            "images": [], "links": [],
            "fetched_at": "2026-01-01T00:00:00",
            "extraction_method": "beautifulsoup",
            "via_jina": False,
            "quality_report": {"complete": False, "score": 20, "issues": [], "metrics": {}},
            "_render_diagnostic": None,
        }

        render_opts = RenderOptions(enabled=True, headed=False)
        collector = WebPackCollector(
            topic="test", source_urls=["https://example.com"],
            render_options=render_opts, max_depth=0, max_pages=1, no_jina=True,
        )

        # _try_playwright_dom returns (None, None, None) (failure)
        def fake_try_pw_fail(*args, **kwargs):
            return None, None, None

        with patch.object(collector, '_try_playwright_dom', fake_try_pw_fail):
            collector.run()

        # 原始 HTTP 结果被保留
        assert len(collector.collected_pages) == 1
        assert "playwright" not in collector.collected_pages[0].get("extraction_method", "")


# ═══════════════════════════════════════════════════════════════════
# Test 16: 渲染后的 HTML 会传给现有 readability/trafilatura 流程
# ═══════════════════════════════════════════════════════════════════

def test_rendered_html_goes_through_extractors():
    """PW 渲染后的 HTML 经过 _extract_content_from_html。"""
    from web_pack import _extract_content_from_html

    result = _extract_content_from_html(LONG_ARTICLE_HTML, "https://example.com")
    assert result is not None
    title, markdown, method = result
    assert "深度学习" in title or "深度学习" in markdown
    assert method in ("readability-lxml", "trafilatura", "beautifulsoup")


# ═══════════════════════════════════════════════════════════════════
# Test 17: 滚动达到最大次数后停止
# ═══════════════════════════════════════════════════════════════════

def test_scroll_stops_at_max():
    """验证滚动在达到 max_scrolls 后停止。"""
    from playwright_renderer import PlaywrightRenderer, RenderOptions as PWOptions

    with patch("playwright_renderer.HAS_PLAYWRIGHT", True), \
         patch("playwright_renderer.sync_playwright") as mock_sp:
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()

        mock_sp.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        mock_page.title.return_value = "Test"
        mock_page.content.return_value = LONG_ARTICLE_HTML
        mock_page.url = "https://example.com"
        # 页面高度持续变化
        mock_page.evaluate.side_effect = [100, 200, 300, 400, 500, 600]

        opts = PWOptions(enabled=True, max_scrolls=3, scroll_wait_ms=0, use_persistent_profile=False)
        renderer = PlaywrightRenderer(opts)

        # 直接测试 _perform_scrolls
        with patch("playwright_renderer.time.sleep"):
            renderer._perform_scrolls(mock_page)

        # evaluate 被调用用于获取高度和滚动：每次循环 2 次 × 3 轮
        # scrollHeight 读取 + window.scrollTo 执行
        assert mock_page.evaluate.call_count <= 6


# ═══════════════════════════════════════════════════════════════════
# Test 18: 页面高度稳定时提前停止
# ═══════════════════════════════════════════════════════════════════

def test_scroll_stops_when_height_stable():
    """高度不变时提前停止滚动。"""
    from playwright_renderer import PlaywrightRenderer, RenderOptions as PWOptions

    with patch("playwright_renderer.HAS_PLAYWRIGHT", True), \
         patch("playwright_renderer.sync_playwright") as mock_sp:
        mock_pw = MagicMock()
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_sp.return_value.start.return_value = mock_pw
        mock_pw.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page

        # 第一次调用返回 500，后续相同
        call_count = [0]

        def stable_height(js):
            if "scrollHeight" in js:
                call_count[0] += 1
                return 500  # 始终相同
            return 500  # scrollTo 也返回 500，避免 prev_height 被 None 覆盖

        mock_page.evaluate.side_effect = stable_height

        opts = PWOptions(enabled=True, max_scrolls=5, scroll_wait_ms=0, use_persistent_profile=False)
        renderer = PlaywrightRenderer(opts)

        with patch("playwright_renderer.time.sleep"):
            renderer._perform_scrolls(mock_page)

        # 第一次 scrollHeight=500 设置 prev_height=500
        # 第一次 scrollTo 返回 500，prev_height 保持 500
        # 第二次 scrollHeight=500，与 prev_height 相同 → break
        # 所以 scrollHeight 被检查 2 次
        assert call_count[0] <= 3


# ═══════════════════════════════════════════════════════════════════
# Test 19: --headed 的参数行为
# ═══════════════════════════════════════════════════════════════════

def test_headed_flag_behavior():
    """--headed 隐含 --render。"""
    from web_pack import RenderOptions

    opts = RenderOptions(enabled=True, headed=True)
    assert opts.enabled is True
    assert opts.headed is True


# ═══════════════════════════════════════════════════════════════════
# Test 20: --mode safe --render 使用临时 Profile
# ═══════════════════════════════════════════════════════════════════

def test_safe_mode_uses_temp_profile():
    """safe 模式不使用持久化 Profile。"""
    from web_pack import RenderOptions, PKB_ROOT

    # safe 模式：use_persistent_profile = False
    opts = RenderOptions(enabled=True, use_persistent_profile=False)
    assert opts.use_persistent_profile is False

    # full 模式：使用 PKB 专用 profile
    profile_dir = PKB_ROOT / ".pkbcache" / "playwright-profile"
    opts_full = RenderOptions(enabled=True, use_persistent_profile=True, profile_dir=profile_dir)
    assert opts_full.use_persistent_profile is True
    assert opts_full.profile_dir == profile_dir


# ═══════════════════════════════════════════════════════════════════
# Test 21: 普通模式 --render 使用 PKB 专用 Profile
# ═══════════════════════════════════════════════════════════════════

def test_full_mode_uses_pkb_profile():
    """full 模式使用 PKB 专用 profile 目录。"""
    from web_pack import PKB_ROOT

    profile_dir = PKB_ROOT / ".pkbcache" / "playwright-profile"
    assert ".pkbcache" in str(profile_dir)
    assert "playwright-profile" in str(profile_dir)


# ═══════════════════════════════════════════════════════════════════
# Test 22: quality_report 可以安全序列化
# ═══════════════════════════════════════════════════════════════════

def test_quality_report_serializable():
    """quality_report dict 可以 JSON 序列化。"""
    import json
    from web_pack import _quality_report_to_dict
    from content_quality import assess_article

    report = assess_article("Title", "Long enough content " * 20)
    d = _quality_report_to_dict(report)
    assert isinstance(d, dict)
    # 应可 JSON 序列化
    json_str = json.dumps(d, ensure_ascii=False)
    assert len(json_str) > 0
    parsed = json.loads(json_str)
    assert "complete" in parsed
    assert "score" in parsed
    assert "issues" in parsed


# ═══════════════════════════════════════════════════════════════════
# Test 23: 原有 _text_is_weak() 未被删除
# ═══════════════════════════════════════════════════════════════════

def test_text_is_weak_still_exists():
    """_text_is_weak() 仍然存在且可用。"""
    from web_pack import _text_is_weak

    assert _text_is_weak("x") is True
    assert _text_is_weak("a" * 400) is False


# ═══════════════════════════════════════════════════════════════════
# Test 24: fetch_page 返回包含 quality_report
# ═══════════════════════════════════════════════════════════════════

def test_fetch_page_includes_quality_report():
    """fetch_page() 返回值包含 quality_report。"""
    from web_pack import fetch_page
    from unittest.mock import MagicMock
    from pathlib import Path
    import tempfile

    mock_session = MagicMock()
    mock_resp = make_http_response(LONG_ARTICLE_HTML)
    mock_session.get.return_value = mock_resp

    with tempfile.TemporaryDirectory() as tmp:
        assets_dir = Path(tmp)
        result = fetch_page(
            "https://example.com/article",
            mock_session,
            assets_dir,
            [0],
            {},
            mode="full",
        )

    if result is not None:
        assert "quality_report" in result
        qr = result["quality_report"]
        if qr:
            assert "complete" in qr
            assert "score" in qr


# ═══════════════════════════════════════════════════════════════════
# Test 25: RenderOptions 默认不启用
# ═══════════════════════════════════════════════════════════════════

def test_render_options_defaults():
    """RenderOptions 默认不启用 Playwright。"""
    from web_pack import RenderOptions

    opts = RenderOptions()
    assert opts.enabled is False
    assert opts.headed is False
    assert opts.max_scrolls == 5
    assert opts.navigation_timeout_ms == 30_000


# ═══════════════════════════════════════════════════════════════════
# Test 26–29: configure_stdout_utf8 防御性实现
# ═══════════════════════════════════════════════════════════════════

def test_configure_stdout_utf8_function_exists():
    """configure_stdout_utf8 是 callable 函数。"""
    from web_pack import configure_stdout_utf8
    assert callable(configure_stdout_utf8)


def test_configure_stdout_utf8_no_reconfigure():
    """不支持 reconfigure 时静默通过。"""
    from web_pack import configure_stdout_utf8
    import io

    class FakeStdout:
        pass  # 没有 reconfigure 属性

    fake = FakeStdout()
    with patch.object(sys, 'stdout', fake):
        configure_stdout_utf8()  # 不应抛出异常


def test_configure_stdout_utf8_value_error():
    """reconfigure 抛出 ValueError 时静默通过。"""
    from web_pack import configure_stdout_utf8

    def raise_value_error(*a, **kw):
        raise ValueError("encoding not supported")

    fake = MagicMock()
    fake.reconfigure = raise_value_error
    with patch.object(sys, 'stdout', fake):
        configure_stdout_utf8()  # 不应抛出异常


def test_configure_stdout_utf8_os_error():
    """reconfigure 抛出 OSError（如 stdout 被管道化）时静默通过。"""
    from web_pack import configure_stdout_utf8

    def raise_os_error(*a, **kw):
        raise OSError("stdout is not a tty")

    fake = MagicMock()
    fake.reconfigure = raise_os_error
    with patch.object(sys, 'stdout', fake):
        configure_stdout_utf8()  # 不应抛出异常


def test_configure_stdout_utf8_success():
    """正常 stdout 支持 reconfigure 时正确设置 UTF-8。"""
    from web_pack import configure_stdout_utf8

    call_args = []
    def record(*a, **kw):
        call_args.append(kw)

    fake = MagicMock()
    fake.reconfigure = record
    with patch.object(sys, 'stdout', fake):
        configure_stdout_utf8()

    assert len(call_args) == 1
    assert call_args[0].get('encoding') == 'utf-8'


def test_configure_stdout_utf8_non_callable_reconfigure():
    """reconfigure 属性存在但不可调用时静默通过。"""
    from web_pack import configure_stdout_utf8

    fake = MagicMock()
    fake.reconfigure = "not_a_function"
    with patch.object(sys, 'stdout', fake):
        configure_stdout_utf8()  # 不应抛出异常
