#!/usr/bin/env python3
"""content_quality.py 单元测试 — 覆盖 18 个测试用例。

测试设计：
  - 使用固定 fixture，不访问网络
  - 覆盖正常/异常/边界/自定义配置
  - 所有 issue 使用枚举值断言
"""

from __future__ import annotations

import sys
from pathlib import Path

# 确保 tools/ 在 sys.path 中
_TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import pytest

from content_quality import (
    DEFAULT_CONFIG,
    FATAL_ISSUES,
    QualityConfig,
    QualityIssue,
    QualityReport,
    assess_article,
    diagnostic_summary,
    quick_check,
    _compute_duplication_ratio,
    _compute_navigation_ratio,
    _compute_natural_language_ratio,
    _strip_markdown_noise,
    _is_navigation_line,
)


# ═══════════════════════════════════════════════════════════════════
# Fixtures
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def long_cn_article() -> tuple[str, str]:
    """正常中文长文章。"""
    title = "深度学习在自然语言处理中的应用"
    content = """
深度学习是机器学习的一个分支，它使用多层神经网络来学习数据的表示。

## 引言

自然语言处理（NLP）是人工智能领域的一个重要方向。近年来，随着计算能力的提升和
大规模标注数据的出现，深度学习技术在 NLP 领域取得了突破性进展。

## 主要方法

### 循环神经网络

循环神经网络（RNN）是最早被广泛应用于序列建模的深度学习模型之一。
它通过在时间步之间传递隐藏状态来捕捉序列信息。然而，传统 RNN 存在
梯度消失和梯度爆炸的问题。

### Transformer 架构

Transformer 架构的提出彻底改变了 NLP 领域。它完全基于注意力机制，
摒弃了循环结构，使得模型可以并行处理整个序列。BERT、GPT 等预训练
语言模型都基于 Transformer 架构。

## 应用场景

深度学习在以下 NLP 任务中表现出色：

- 机器翻译：神经机器翻译系统已经取代了传统的统计机器翻译方法。
- 文本分类：情感分析、主题分类、垃圾邮件检测等任务都可以用深度学习解决。
- 问答系统：基于预训练模型的问答系统在多个基准测试中超越了人类水平。
- 文本生成：GPT 系列模型展现了强大的文本生成能力。

## 挑战与展望

尽管取得了显著进展，深度学习在 NLP 中仍然面临一些挑战。模型的可解释性、
数据偏见、计算资源消耗等问题都需要进一步研究。

未来的研究方向可能包括更高效的模型架构、小样本学习、多模态融合等。

## 结论

深度学习已经并将继续深刻影响自然语言处理的研究和应用。通过不断改进
模型架构和训练方法，我们有望构建更加智能和可靠的语言理解系统。
"""
    return title, content


@pytest.fixture
def long_en_article() -> tuple[str, str]:
    """正常英文长文章。"""
    title = "A Comprehensive Guide to Python Async Programming"
    content = """
Asynchronous programming has become an essential paradigm in modern software development.
Python's asyncio library provides a powerful framework for writing concurrent code.

## Introduction to AsyncIO

The asyncio library was introduced in Python 3.4 and has been steadily improved
through subsequent releases. It enables writing single-threaded concurrent code
using the async/await syntax.

## Core Concepts

### Coroutines

Coroutines are the building blocks of async programming in Python. They are
defined using the `async def` syntax and can be awaited using the `await` keyword.
When a coroutine encounters an await expression, it yields control back to the
event loop, allowing other coroutines to run.

### Event Loop

The event loop is the heart of asyncio. It manages and distributes the execution
of different tasks. You can think of it as a scheduler that keeps track of all
running coroutines and decides which one to execute next.

### Tasks and Futures

Tasks are used to schedule coroutines concurrently. When you wrap a coroutine
into a Task, it will be scheduled to run on the event loop as soon as possible.
Futures represent a result that may not be available yet.

## Practical Examples

Let's look at some practical examples of async programming:

```python
import asyncio

async def fetch_data(url):
    # Simulate network request
    await asyncio.sleep(1)
    return f"Data from {url}"

async def main():
    urls = ["http://example.com/a", "http://example.com/b"]
    tasks = [fetch_data(url) for url in urls]
    results = await asyncio.gather(*tasks)
    for result in results:
        print(result)

asyncio.run(main())
```

## Performance Considerations

Async programming excels at I/O-bound tasks. For CPU-bound operations,
you should use multiprocessing or threading instead.

## Conclusion

Python's asyncio is a mature and powerful framework for async programming.
Understanding its core concepts is essential for building high-performance
network applications.
"""
    return title, content


# ═══════════════════════════════════════════════════════════════════
# Test 1: 正常中文长文章 → complete=True
# ═══════════════════════════════════════════════════════════════════

def test_long_cn_article_complete(long_cn_article):
    title, content = long_cn_article
    report = assess_article(title, content)
    assert report.complete is True, f"Expected complete, got issues: {report.issues}"
    assert report.score >= 60, f"Score {report.score} too low for long article"
    assert report.metrics["title_present"] is True
    assert report.metrics["valid_paragraph_count"] >= 3
    assert report.metrics["navigation_ratio"] < 0.30


# ═══════════════════════════════════════════════════════════════════
# Test 2: 正常英文长文章 → complete=True
# ═══════════════════════════════════════════════════════════════════

def test_long_en_article_complete(long_en_article):
    title, content = long_en_article
    report = assess_article(title, content)
    assert report.complete is True, f"Expected complete, got issues: {report.issues}"
    assert report.score >= 60
    assert report.metrics["title_present"] is True
    assert report.metrics["valid_paragraph_count"] >= 3


# ═══════════════════════════════════════════════════════════════════
# Test 3: 169 字导航文本 → complete=False
# ═══════════════════════════════════════════════════════════════════

def test_nav_only_text_not_complete():
    """模拟 '小黑盒只有 169 字导航' 的场景。"""
    title = "小黑盒"
    content = """
首页
下载App
登录
注册
热门
社区
商城
搜索
首页
游戏
新闻
攻略
视频
关于我们
隐私政策
用户协议
联系我们
商务合作
Copyright 2024 小黑盒
"""
    report = assess_article(title, content)
    assert report.complete is False
    assert QualityIssue.TEXT_TOO_SHORT in report.issues
    assert report.metrics["navigation_ratio"] > 0.40 or QualityIssue.NAVIGATION_RATIO_HIGH in report.issues


# ═══════════════════════════════════════════════════════════════════
# Test 4: 只有菜单和页脚 → complete=False
# ═══════════════════════════════════════════════════════════════════

def test_menu_footer_only_not_complete():
    title = ""
    content = """
导航
首页 产品 关于 联系
页脚
© 2024 Company. All rights reserved.
Privacy Policy | Terms of Service
"""
    report = assess_article(title, content)
    assert report.complete is False
    assert QualityIssue.MENU_OR_FOOTER_ONLY in report.issues or report.score < 35


# ═══════════════════════════════════════════════════════════════════
# Test 5: "请开启 JavaScript" → complete=False
# ═══════════════════════════════════════════════════════════════════

def test_js_placeholder_not_complete():
    title = ""
    content = """
请开启JavaScript

您的浏览器不支持JavaScript，请启用后刷新页面。

This page requires JavaScript to function properly.
"""
    report = assess_article(title, content)
    assert report.complete is False
    assert QualityIssue.SCRIPT_PLACEHOLDER in report.issues


# ═══════════════════════════════════════════════════════════════════
# Test 6: 登录页 → complete=False
# ═══════════════════════════════════════════════════════════════════

def test_login_page_not_complete():
    title = "登录"
    content = """
登录

用户名
密码
登录
忘记密码？
还没有账号？立即注册

Please sign in to continue.
"""
    report = assess_article(title, content)
    assert report.complete is False
    assert QualityIssue.LOGIN_REQUIRED in report.issues or QualityIssue.TEXT_TOO_SHORT in report.issues


# ═══════════════════════════════════════════════════════════════════
# Test 7: 验证码页 → complete=False
# ═══════════════════════════════════════════════════════════════════

def test_captcha_page_not_complete():
    title = "安全验证"
    content = """
安全验证

请输入验证码以继续访问。

CAPTCHA - Security Check

Verify you are human by completing the challenge below.
"""
    report = assess_article(title, content)
    assert report.complete is False
    assert QualityIssue.CAPTCHA_DETECTED in report.issues


# ═══════════════════════════════════════════════════════════════════
# Test 8: 正常文章偶然出现"登录""验证码" → 不会误判
# ═══════════════════════════════════════════════════════════════════

def test_incidental_keywords_not_misjudged(long_cn_article):
    """正常长文中提到登录/验证码不应触发特殊页面检测。"""
    title, base_content = long_cn_article
    # 在长文中插入一次性的"登录"和"验证码"提及
    content = base_content + """

## 用户体验说明

在某些场景下，用户需要登录后才能使用个性化功能。
系统会通过验证码机制防止机器人滥用。但整体而言，
这些只是安全保障的一部分，不影响主要功能的体验。
"""
    report = assess_article(title, content)
    assert report.complete is True
    # 不应有致命问题
    assert QualityIssue.LOGIN_REQUIRED not in report.issues
    assert QualityIssue.CAPTCHA_DETECTED not in report.issues
    assert QualityIssue.SCRIPT_PLACEHOLDER not in report.issues


# ═══════════════════════════════════════════════════════════════════
# Test 9: 重复菜单文本 → 高重复率
# ═══════════════════════════════════════════════════════════════════

def test_repeated_menu_high_duplication():
    title = ""
    # 无空格重复：每个中文字符都是 5-gram 窗口的一部分
    # "首页产品关于联系" × 10 → 显著的重复率
    content = "首页产品关于联系首页产品关于联系首页产品关于联系首页产品关于联系" \
              "首页产品关于联系首页产品关于联系首页产品关于联系首页产品关于联系" \
              "首页产品关于联系首页产品关于联系"
    report = assess_article(title, content)
    assert report.metrics["duplication_ratio"] > 0.25, \
        f"Expected high duplication, got {report.metrics['duplication_ratio']}"


# ═══════════════════════════════════════════════════════════════════
# Test 10: 正常长文不会因常用词重复而误判
# ═══════════════════════════════════════════════════════════════════

def test_long_article_low_duplication(long_cn_article):
    title, content = long_cn_article
    report = assess_article(title, content)
    # 正常文章重复率应很低
    assert report.metrics["duplication_ratio"] < 0.30, \
        f"Normal article should have low duplication, got {report.metrics['duplication_ratio']}"


# ═══════════════════════════════════════════════════════════════════
# Test 11: Markdown 链接 URL 不虚增正文质量
# ═══════════════════════════════════════════════════════════════════

def test_markdown_links_not_counted_as_text():
    title = "Test"
    # 大量链接，极少量正文（不够形成有效段落）
    content = """
See [this link](https://example.com/very-long-path/page?id=12345&token=abc).

Also [another resource](https://other.example.com/articles/how-to-build-apps).
And [one more](https://third.example.com/docs/reference/api/v2/endpoints).
"""
    report = assess_article(title, content)
    # 纯文本长度应远小于 content 长度
    assert report.metrics["plain_text_length"] < report.metrics["content_length"] * 0.8
    # 链接残余文本不足以满足有效段落要求
    assert report.metrics["valid_paragraph_count"] <= 1


# ═══════════════════════════════════════════════════════════════════
# Test 12: Markdown 图片不计入正文长度
# ═══════════════════════════════════════════════════════════════════

def test_markdown_images_not_counted():
    title = "Gallery"
    content = """
![photo1](https://example.com/img1.jpg)
![photo2](https://example.com/img2.jpg)
![photo3](https://example.com/img3.jpg)

This is the only real text content here.
"""
    report = assess_article(title, content)
    # 纯文本长度应该只包含 "This is the only real text content here."
    assert report.metrics["plain_text_length"] < 60


# ═══════════════════════════════════════════════════════════════════
# Test 13: 含代码块的技术文章不误判
# ═══════════════════════════════════════════════════════════════════

def test_technical_article_with_code_not_misjudged():
    title = "Python Context Managers Explained"
    content = """
Context managers are a powerful feature in Python that help manage resources
like files, network connections, and locks.

## What is a Context Manager?

A context manager is an object that defines the runtime context to be
established when executing a `with` statement. It handles setup and teardown
operations automatically, ensuring resources are properly released.

## Basic Usage

The most common example is file handling:

```python
with open("data.txt", "r") as f:
    content = f.read()
    print(content)
```

## Creating Custom Context Managers

You can create custom context managers using classes:

```python
class DatabaseConnection:
    def __init__(self, db_url):
        self.db_url = db_url

    def __enter__(self):
        self.conn = connect(self.db_url)
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.conn.close()
        return False
```

## Contextlib Approach

The contextlib module provides utilities for working with context managers:

```python
from contextlib import contextmanager

@contextmanager
def managed_resource(*args, **kwargs):
    resource = acquire_resource(*args, **kwargs)
    try:
        yield resource
    finally:
        release_resource(resource)
```

## When to Use Context Managers

Context managers are ideal for any situation where you need paired operations:
setup and teardown, open and close, acquire and release. They make your code
more readable and less error-prone by ensuring cleanup always happens.

## Conclusion

Python's context manager protocol is a elegant solution for resource management.
It is widely used throughout the standard library and third-party packages.
"""
    report = assess_article(title, content)
    # 技术文章含代码块应仍然被判为完整
    assert report.complete is True, \
        f"Technical article should be complete. Issues: {report.issues}"
    assert report.metrics["code_block_count"] >= 3
    # 自然语言比例可以偏低但不能直接失败
    # （代码块被 strip 后不影响 plain_text 的自然语言比例）


# ═══════════════════════════════════════════════════════════════════
# Test 14: 空标题但正文完整 → 得分降低，complete 取决于配置
# ═══════════════════════════════════════════════════════════════════

def test_no_title_decent_body():
    title = ""
    content = """
机器学习是人工智能的一个核心领域，近年来发展迅速。

深度学习作为机器学习的重要分支，在图像识别和自然语言处理领域取得了突破性进展。

强化学习通过智能体与环境的交互来学习最优策略，在游戏和机器人控制中表现优异。

迁移学习利用源任务的知识来辅助目标任务的学习，减少了对大量标注数据的需求。

联邦学习允许多个参与方在不共享原始数据的情况下协作训练模型，保护了数据隐私。

图神经网络将深度学习扩展到图结构数据，在社交网络分析和推荐系统中广泛应用。
"""
    report = assess_article(title, content)
    # 有 TITLE_MISSING issue
    assert QualityIssue.TITLE_MISSING in report.issues
    # 默认配置下，正文够长，应该仍然 complete
    assert report.complete is True

    # 用更严格的配置（要求必须有标题）
    strict = QualityConfig(min_score_complete=60)
    report_strict = assess_article(title, content, config=strict)
    # 因缺少标题，结构分减少，总分可能低于 60
    assert report_strict.score < report.score or QualityIssue.TITLE_MISSING in report_strict.issues


# ═══════════════════════════════════════════════════════════════════
# Test 15: 空正文 → 稳定的 QualityReport
# ═══════════════════════════════════════════════════════════════════

def test_empty_content():
    report = assess_article("", "")
    assert isinstance(report, QualityReport)
    assert report.complete is False
    assert report.score == 0
    assert QualityIssue.TEXT_TOO_SHORT in report.issues
    assert report.metrics["content_length"] == 0
    assert report.metrics["plain_text_length"] == 0

    # 有标题但无正文
    report2 = assess_article("Some Title", "")
    assert isinstance(report2, QualityReport)
    assert report2.complete is False


# ═══════════════════════════════════════════════════════════════════
# Test 16: 所有 issue 使用稳定枚举值
# ═══════════════════════════════════════════════════════════════════

def test_all_issues_are_enum_values():
    """验证 assess_article 返回的所有 issue 都是 QualityIssue 枚举成员。"""
    # 构造多种场景触发不同 issue
    test_cases = [
        ("", ""),                                          # TITLE_MISSING + TEXT_TOO_SHORT
        ("Title", "登录后查看"),                            # LOGIN_REQUIRED
        ("Title", "请开启JavaScript"),                      # SCRIPT_PLACEHOLDER
        ("Title", "验证码 CAPTCHA"),                        # CAPTCHA_DETECTED
    ]

    for title, content in test_cases:
        report = assess_article(title, content)
        for issue in report.issues:
            assert isinstance(issue, QualityIssue), \
                f"Issue {issue!r} is not a QualityIssue enum"
            # 验证枚举值出现在定义中
            assert issue in QualityIssue.__members__.values(), \
                f"Issue {issue!r} not in QualityIssue members"


# ═══════════════════════════════════════════════════════════════════
# Test 17: 自定义 QualityConfig
# ═══════════════════════════════════════════════════════════════════

def test_custom_config_thresholds():
    title = "Short Note"
    content = "This is a brief note about something interesting."
    # 默认配置：太短 → 不完整
    report_default = assess_article(title, content)
    assert report_default.complete is False

    # 宽松配置：降低所有阈值
    loose = QualityConfig(
        min_content_length=20,
        min_valid_paragraphs=0,
        min_score_complete=15,
        valid_paragraph_min_chars=10,
    )
    report_loose = assess_article(title, content, config=loose)
    assert report_loose.complete is True

    # 严格配置：提高阈值
    strict = QualityConfig(
        min_content_length=500,
        min_valid_paragraphs=5,
        min_score_complete=80,
    )
    report_strict = assess_article(title, content, config=strict)
    assert report_strict.complete is False


# ═══════════════════════════════════════════════════════════════════
# Test 18: 重复率计算在长输入下受 max_chars 限制
# ═══════════════════════════════════════════════════════════════════

def test_duplication_bounded_by_max_chars():
    # 长文本：前 4000 字符由高度重复内容构成
    unit = "这是重复内容。"
    repeated = unit * 600  # 7 chars × 600 = 4200 chars (> 4000)
    tail = "这是完全不同的正常文章内容。" * 100
    text = repeated + tail  # 远超 4000 chars

    ratio = _compute_duplication_ratio(text, max_chars=4000)
    # 前 4000 字符只有 3 种 5-gram 在循环重复 → 极高重复率
    assert ratio > 0.60, f"Expected high duplication in first 4000 chars, got {ratio}"

    # 短文本（< 4000），整个文本参与分析
    short_text = "这是重复。这是重复。这是重复。这是重复。这是重复。"
    ratio_short = _compute_duplication_ratio(short_text, max_chars=4000)
    # 短重复文本也应有较高重复率
    assert ratio_short > 0.10


# ═══════════════════════════════════════════════════════════════════
# 补充测试：内部函数
# ═══════════════════════════════════════════════════════════════════

def test_strip_markdown_noise():
    assert _strip_markdown_noise("![img](url)") == ""
    assert _strip_markdown_noise("[text](url)") == "text"
    assert _strip_markdown_noise("**bold** and *italic*") == "bold and italic"
    assert _strip_markdown_noise("# Heading\n\nContent") == "Heading\n\nContent"
    # 代码块被移除
    result = _strip_markdown_noise("```python\nprint('hello')\n```")
    assert "print" not in result or len(result) < 10


def test_is_navigation_line():
    assert _is_navigation_line("首页") is True
    assert _is_navigation_line("登录") is True
    assert _is_navigation_line("Home") is True
    assert _is_navigation_line("Privacy Policy") is True
    assert _is_navigation_line("这是一篇关于深度学习的文章") is False
    assert _is_navigation_line("The quick brown fox jumps over the lazy dog") is False
    # 正文中偶然出现"登录"
    assert _is_navigation_line("用户需要登录后才能查看个性化推荐内容") is False


def test_navigation_ratio():
    # 纯导航
    nav_text = "\n".join(["首页", "登录", "注册", "隐私政策", "联系我们"] * 3)
    assert _compute_navigation_ratio(nav_text) > 0.50

    # 正常文章
    normal = "深度学习是人工智能的一个重要分支。\n\n自然语言处理技术近年来发展迅速。\n\nTransformer架构改变了整个领域。"
    assert _compute_navigation_ratio(normal) < 0.20


def test_natural_language_ratio():
    # 纯中文
    assert _compute_natural_language_ratio("这是一段测试文本用于验证自然语言比例计算") > 0.90
    # 纯英文
    assert _compute_natural_language_ratio("This is a test sentence for natural language ratio") > 0.90
    # 数字和符号为主 → 自然语言比例低
    assert _compute_natural_language_ratio("12345 !@#$% 67890 ^&*()") < 0.30
    # 混合
    mix = "这是中文 text with English mixed 12345 !@#$%"
    ratio = _compute_natural_language_ratio(mix)
    assert 0.30 < ratio < 0.85


def test_diagnostic_summary():
    report = assess_article("Test", "Some content here that is quite short.")
    summary = diagnostic_summary(report)
    assert "评分:" in summary
    assert isinstance(summary, str)
    assert len(summary) > 0


def test_quick_check():
    assert quick_check("Title", "x") is False  # too short
    assert quick_check("Title", "Short text that is still too short for article") is False
    # 使用长文章
    title = "Test Article"
    content = "\n\n".join([
        "This is a comprehensive article about testing.",
        "It has multiple paragraphs with substantial content.",
        "Each paragraph discusses different aspects of the topic.",
        "This ensures the article passes the quality check.",
    ])
    # 构造足够长的内容
    long_content = (content + "\n") * 6
    result = quick_check("A Very Long Article Title", long_content)
    # 可能通过也可能不通过，取决于具体阈值，但不应该崩溃
    assert isinstance(result, bool)


def test_quality_config_immutable():
    """QualityConfig 是 frozen dataclass。"""
    config = QualityConfig()
    with pytest.raises(Exception):
        config.min_content_length = 500  # type: ignore[misc]


def test_quality_report_immutable():
    """QualityReport 是 frozen dataclass。"""
    report = assess_article("T", "Hello world")
    with pytest.raises(Exception):
        report.complete = True  # type: ignore[misc]
    with pytest.raises(Exception):
        report.score = 100  # type: ignore[misc]


def test_html_fallback_used():
    """提供 HTML 且正文为空时，使用 HTML 可见文本。"""
    title = "Test"
    content = ""  # Markdown 为空
    html = """
<html><body>
<h1>Article Title</h1>
<p>This is the first paragraph of the article.</p>
<p>This is the second paragraph with enough content to pass checks.</p>
<p>Third paragraph adds more substance to the analysis.</p>
<p>Fourth paragraph makes sure we have sufficient valid content.</p>
</body></html>
"""
    report = assess_article(title, content, html=html)
    # HTML 可见文本被提取出来
    assert report.metrics["analysis_text_length"] > 50
