#!/usr/bin/env python3
"""
PKB Playwright 渲染器 — 可选的动态网页渲染能力。

职责（仅限本模块）：
  - 可选依赖检测
  - browser / context 生命周期管理
  - 页面导航 + 超时控制
  - 有限滚动（触发懒加载）
  - 返回渲染后的 title / html / final_url
  - 资源清理（安全关闭，支持上下文管理器）

不负责：
  - 正文评分（见 content_quality.py）
  - Markdown 编译（见 web_pack.py）
  - 网络 JSON 分析（阶段 3）
  - PKB 入库
  - 站点专用逻辑

设计原则：
  - 同步 API (playwright.sync_api)，与 web_pack.py 的同步架构一致
  - browser/context 在整个采集周期复用，page 按 URL 创建/销毁
  - 安全关闭：重复 close() 安全，异常中 close() 不抛异常
  - 不遗留 Chromium 进程
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

# ── 可选依赖检测 ──
try:
    from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    sync_playwright = None  # type: ignore[assignment]
    HAS_PLAYWRIGHT = False

# ── 安装提示 ──
_PLAYWRIGHT_INSTALL_HINT = (
    "Playwright 未安装。安装步骤:\n"
    "  pip install -r requirements-playwright.txt\n"
    "  playwright install chromium\n"
    "安装后即可使用 --render 参数启用动态渲染。"
)

_CHROMIUM_MISSING_HINT = (
    "Chromium 浏览器未安装。请运行:\n"
    "  playwright install chromium"
)


# ═══════════════════════════════════════════════════════════════════
# 渲染结果
# ═══════════════════════════════════════════════════════════════════

class RenderResult:
    """单次页面渲染的结果。"""

    __slots__ = (
        "title", "html", "final_url", "success", "error",
        "network_candidates", "network_diagnostic",
    )

    def __init__(
        self,
        title: str = "",
        html: str = "",
        final_url: str = "",
        success: bool = False,
        error: str = "",
        network_candidates: tuple = (),
        network_diagnostic: Any = None,
    ):
        self.title = title
        self.html = html
        self.final_url = final_url
        self.success = success
        self.error = error
        self.network_candidates = network_candidates
        self.network_diagnostic = network_diagnostic


# ═══════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════

class RenderOptions:
    """Playwright 渲染配置。

    所有字段有默认值，未启用时 enabled=False。
    """

    __slots__ = (
        "enabled", "headed", "navigation_timeout_ms", "settle_timeout_ms",
        "max_scrolls", "scroll_wait_ms", "profile_dir", "use_persistent_profile",
        "network", "html_extractor",
    )

    def __init__(
        self,
        enabled: bool = False,
        headed: bool = False,
        navigation_timeout_ms: int = 30_000,
        settle_timeout_ms: int = 3_000,
        max_scrolls: int = 5,
        scroll_wait_ms: int = 600,
        profile_dir: Path | None = None,
        use_persistent_profile: bool = True,
        network: Any = None,
        html_extractor: Any = None,
    ):
        self.enabled = enabled
        self.headed = headed
        self.navigation_timeout_ms = navigation_timeout_ms
        self.settle_timeout_ms = settle_timeout_ms
        self.max_scrolls = max_scrolls
        self.scroll_wait_ms = scroll_wait_ms
        self.profile_dir = profile_dir
        self.use_persistent_profile = use_persistent_profile
        self.network = network        # NetworkCaptureOptions | None
        self.html_extractor = html_extractor  # callable for HTML→text extraction


# ═══════════════════════════════════════════════════════════════════
# PlaywrightRenderer — 浏览器生命周期
# ═══════════════════════════════════════════════════════════════════

class PlaywrightRenderer:
    """Playwright 浏览器渲染器。

    生命周期:
      renderer = PlaywrightRenderer(options)
      renderer.start()        # 启动 browser + context（一次）
      result = renderer.render_page(url)  # 可多次调用，每次创建/关闭 page
      renderer.close()        # 关闭 context + browser + playwright

    支持上下文管理器:
      with PlaywrightRenderer(options) as renderer:
          result = renderer.render_page(url)
    """

    def __init__(self, options: RenderOptions):
        if not HAS_PLAYWRIGHT:
            raise RuntimeError(_PLAYWRIGHT_INSTALL_HINT)

        self._options = options
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._temp_dir: Path | None = None
        self._started = False
        self._closed = False
        self._is_persistent: bool = False

    # ── 公开方法 ──

    def start(self) -> None:
        """启动浏览器和 context。幂等：重复调用不重复启动。"""
        if self._started:
            return
        if self._closed:
            raise RuntimeError("PlaywrightRenderer 已关闭，不可复用")

        try:
            self._playwright = sync_playwright().start()

            # 确定 profile 目录
            profile_dir = self._resolve_profile_dir()

            if profile_dir is not None:
                # 持久化 context — context 拥有 browser
                self._is_persistent = True
                self._context = self._playwright.chromium.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=not self._options.headed,
                    args=["--no-first-run", "--no-default-browser-check"],
                    no_viewport=False,
                )
                self._browser = self._context.browser
            else:
                # 临时 context — 我们拥有 browser
                self._is_persistent = False
                self._browser = self._playwright.chromium.launch(
                    headless=not self._options.headed,
                    args=["--no-first-run", "--no-default-browser-check"],
                )
                self._context = self._browser.new_context(
                    no_viewport=False,
                )

            self._started = True

        except Exception as e:
            # 启动失败 → 清理已创建的资源
            self._cleanup_on_failure()
            raise RuntimeError(
                f"Playwright 浏览器启动失败: {e}\n{_CHROMIUM_MISSING_HINT}"
            ) from e

    def render_page(self, url: str) -> RenderResult:
        """渲染单个页面。每次调用创建新 page，使用后关闭。

        步骤:
          1. 创建 page
          2. 挂载网络捕获监听器（如果启用）
          3. 导航到 url
          4. 等待页面稳定
          5. 有限次数滚动
          6. 网络捕获 grace period
          7. 提取网络候选
          8. 提取 title / html / final_url
          9. 关闭 page
        """
        if not self._started:
            raise RuntimeError("请先调用 start()")
        if self._closed:
            raise RuntimeError("PlaywrightRenderer 已关闭")

        if self._context is None:
            return RenderResult(success=False, error="Browser context 未初始化")

        page: Page | None = None
        capture_session: Any = None
        network_candidates: tuple = ()
        network_diagnostic: Any = None

        try:
            page = self._context.new_page()
            page.set_default_navigation_timeout(self._options.navigation_timeout_ms)

            # ── 网络捕获 ──
            net_opts = getattr(self._options, 'network', None)
            if net_opts is not None and net_opts.enabled:
                try:
                    from network_capture import ResponseCaptureSession, NetworkCaptureOptions
                    from network_content import extract_candidates

                    capture_session = ResponseCaptureSession(net_opts)
                    capture_session.attach(page)
                except ImportError:
                    pass  # 网络捕获模块不存在，跳过

            # 导航
            try:
                page.goto(url, wait_until="domcontentloaded")
            except Exception as e:
                return RenderResult(
                    success=False,
                    error=f"页面导航失败: {e}",
                    final_url=getattr(page, 'url', url),
                )

            # 等待页面稳定
            time.sleep(self._options.settle_timeout_ms / 1000.0)

            # 有限滚动
            self._perform_scrolls(page)

            # 网络捕获 grace period
            if capture_session is not None and net_opts is not None:
                grace_ms = getattr(net_opts, 'network_grace_ms', 1000)
                if grace_ms > 0:
                    time.sleep(grace_ms / 1000.0)

            # 提取网络候选
            if capture_session is not None:
                try:
                    capture_session.finalize()
                    responses = capture_session.get_responses()
                    network_diagnostic = capture_session.get_diagnostic()

                    if responses:
                        title = page.title()
                        extractor = getattr(self._options, 'html_extractor', None)
                        network_candidates = tuple(
                            extract_candidates(
                                responses, net_opts, network_diagnostic,
                                page_title=title, html_extractor=extractor,
                            )
                        )
                except Exception:
                    pass  # 网络候选提取失败不影响 DOM 提取
                finally:
                    try:
                        capture_session.close()
                    except Exception:
                        pass

            # 提取 DOM 结果
            title = page.title()
            html = page.content()
            final_url = page.url

            return RenderResult(
                title=title,
                html=html,
                final_url=final_url,
                success=True,
                network_candidates=network_candidates,
                network_diagnostic=network_diagnostic,
            )

        except Exception as e:
            return RenderResult(
                success=False,
                error=f"页面渲染异常: {e}",
                final_url=url,
            )
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    pass  # 关闭 page 失败不传播

    def close(self) -> None:
        """关闭浏览器资源。幂等：重复调用安全。

        持久化 context 模式 — context 拥有 browser：
          context.close() → browser 自动关闭 → stop playwright

        非持久化 context 模式 — 我们拥有 browser：
          context.close() → browser.close() → stop playwright
        """
        if self._closed:
            return

        # 先关 context
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None

        # 非持久化 context：browser 需要单独关闭
        if not self._is_persistent and self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
        self._browser = None

        # 最后关 playwright
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

        # 清理临时目录
        if self._temp_dir is not None and self._temp_dir.exists():
            try:
                shutil.rmtree(self._temp_dir, ignore_errors=True)
            except Exception:
                pass
            self._temp_dir = None

        self._started = False
        self._closed = True

    # ── 上下文管理器 ──

    def __enter__(self) -> "PlaywrightRenderer":
        self.start()
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
        return None  # 不吞异常

    # ── 内部方法 ──

    def _resolve_profile_dir(self) -> Path | None:
        """确定 profile 目录。

        - 使用持久化 profile 且指定了路径 → 用指定路径
        - 使用持久化 profile 但未指定路径 → 用临时目录（safe 模式）
        - 不使用持久化 profile → 返回 None（临时 context）
        """
        if not self._options.use_persistent_profile:
            return None

        if self._options.profile_dir is not None:
            # 确保目录存在
            self._options.profile_dir.mkdir(parents=True, exist_ok=True)
            return self._options.profile_dir

        # safe 模式或无指定路径 → 临时目录
        self._temp_dir = Path(tempfile.mkdtemp(prefix="pkb_playwright_"))
        return self._temp_dir

    def _perform_scrolls(self, page: Page) -> None:
        """执行有限次数滚动，触发懒加载内容。"""
        prev_height = 0
        for _ in range(self._options.max_scrolls):
            try:
                current_height = page.evaluate("document.body.scrollHeight")
            except Exception:
                break

            if current_height == prev_height:
                break  # 高度稳定，停止滚动
            prev_height = current_height

            try:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            except Exception:
                break

            time.sleep(self._options.scroll_wait_ms / 1000.0)

    def _cleanup_on_failure(self) -> None:
        """启动失败时的紧急清理。"""
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass

    # ── 静态方法 ──

    @staticmethod
    def is_available() -> bool:
        """检查 Playwright 是否可用。"""
        return HAS_PLAYWRIGHT

    @staticmethod
    def install_hint() -> str:
        """返回安装提示文本。"""
        return _PLAYWRIGHT_INSTALL_HINT
