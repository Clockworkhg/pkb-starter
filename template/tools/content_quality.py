#!/usr/bin/env python3
"""
PKB 正文质量检查模块 — 统一的文章完整性评估。

供 web_pack.py 的各条提取路径使用：
  - 普通 HTTP 提取结果
  - readability-lxml 结果
  - trafilatura 结果
  - Playwright DOM 提取结果 (阶段 2)
  - Playwright 网络响应提取结果 (阶段 3)

设计原则：
  - 不依赖 fetch_page() 的 dict 结构
  - 所有阈值集中在 QualityConfig
  - 问题枚举用稳定英文机器码
  - 评分公式：clamp(positive - penalty, 0, 100)
  - complete 判定综合考虑分数、致命问题和最低指标
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable


# ═══════════════════════════════════════════════════════════════════
# 问题枚举 — 稳定英文机器码
# ═══════════════════════════════════════════════════════════════════

class QualityIssue(StrEnum):
    TITLE_MISSING = "title_missing"
    TEXT_TOO_SHORT = "text_too_short"
    TOO_FEW_PARAGRAPHS = "too_few_paragraphs"
    NAVIGATION_RATIO_HIGH = "navigation_ratio_high"
    DUPLICATION_RATIO_HIGH = "duplication_ratio_high"
    NATURAL_LANGUAGE_RATIO_LOW = "natural_language_ratio_low"
    SCRIPT_PLACEHOLDER = "script_placeholder"
    LOGIN_REQUIRED = "login_required"
    CAPTCHA_DETECTED = "captcha_detected"
    MENU_OR_FOOTER_ONLY = "menu_or_footer_only"
    POSSIBLY_TRUNCATED = "possibly_truncated"


# 面向用户的中文标签映射 — 仅供展示使用，不参与程序逻辑
ISSUE_LABELS: dict[QualityIssue, str] = {
    QualityIssue.TITLE_MISSING: "缺少标题",
    QualityIssue.TEXT_TOO_SHORT: "正文过短",
    QualityIssue.TOO_FEW_PARAGRAPHS: "有效段落不足",
    QualityIssue.NAVIGATION_RATIO_HIGH: "导航/菜单文本占比过高",
    QualityIssue.DUPLICATION_RATIO_HIGH: "重复内容占比过高",
    QualityIssue.NATURAL_LANGUAGE_RATIO_LOW: "自然语言占比过低",
    QualityIssue.SCRIPT_PLACEHOLDER: "页面仅为脚本占位提示",
    QualityIssue.LOGIN_REQUIRED: "页面为登录/注册页",
    QualityIssue.CAPTCHA_DETECTED: "页面为验证码/安全验证页",
    QualityIssue.MENU_OR_FOOTER_ONLY: "页面仅含菜单和页脚",
    QualityIssue.POSSIBLY_TRUNCATED: "正文可能被截断",
}

# 致命问题 — 出现任一即 complete=False（不依赖总分）
FATAL_ISSUES: frozenset[QualityIssue] = frozenset({
    QualityIssue.SCRIPT_PLACEHOLDER,
    QualityIssue.LOGIN_REQUIRED,
    QualityIssue.CAPTCHA_DETECTED,
})


# ═══════════════════════════════════════════════════════════════════
# 配置 — 所有阈值集中定义
# ═══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class QualityConfig:
    """正文质量检查的阈值配置。

    所有阈值均可通过构造新实例覆盖。默认值保持保守，
    避免把正常短文（如公告、简介）全部判为不完整。
    """

    # ── 最低指标 ──
    min_content_length: int = 200
    """正文纯文本最低字符数。低于此值触发 TEXT_TOO_SHORT。"""

    min_valid_paragraphs: int = 1
    """最低有效段落数。低于此值触发 TOO_FEW_PARAGRAPHS。"""

    valid_paragraph_min_chars: int = 20
    """段落去掉空白后达到此字符数才算有效。"""

    # ── 比例阈值 ──
    max_navigation_ratio: float = 0.40
    """导航文本行占比上限。超过触发 NAVIGATION_RATIO_HIGH。"""

    max_duplication_ratio: float = 0.35
    """5-gram 重复率上限。超过触发 DUPLICATION_RATIO_HIGH。"""

    min_natural_language_ratio: float = 0.25
    """自然语言字符占比下限。低于此值触发 NATURAL_LANGUAGE_RATIO_LOW。"""

    # ── 特殊页面检测 ──
    placeholder_density_threshold: float = 0.30
    """特殊文本（JS提示/登录/验证码）占正文比例超过此值视为占位页。"""

    short_text_threshold: int = 500
    """短文本判定线：正文少于此字符数时，特殊文本命中直接判失败。"""

    # ── 截断检测 ──
    truncation_last_para_ratio: float = 0.25
    """末段长度低于平均段长的此比例时标记疑似截断。"""

    # ── 评分权重 ──
    length_score_max: int = 30
    paragraph_score_max: int = 25
    language_score_max: int = 25
    structure_score_max: int = 20

    navigation_penalty_max: int = 25
    duplication_penalty_max: int = 25
    placeholder_penalty_max: int = 40
    login_penalty_max: int = 40
    captcha_penalty_max: int = 40
    truncation_penalty_max: int = 10

    # ── 判定门槛 ──
    min_score_complete: int = 35
    """总分低于此值 → complete=False（即使无致命问题）。"""

    # ── 性能 ──
    max_duplication_analysis_chars: int = 4000
    """重复率分析最多处理的字符数，防止长文性能问题。"""


# 默认配置单例
DEFAULT_CONFIG = QualityConfig()


# ═══════════════════════════════════════════════════════════════════
# 报告数据结构
# ═══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class QualityReport:
    """正文质量评估结果。"""

    complete: bool
    """文章是否被判定为完整。综合 score、致命问题和最低指标。"""

    score: int
    """质量评分 0–100。clamp(positive - penalty, 0, 100)。"""

    issues: tuple[QualityIssue, ...]
    """检测到的问题列表（枚举值，非自由文本）。"""

    metrics: dict[str, float | int | str | bool]
    """各项指标的值。供调试和诊断输出使用。"""


# ═══════════════════════════════════════════════════════════════════
# 文本预处理
# ═══════════════════════════════════════════════════════════════════

# Markdown 链接: [text](url)
_MD_LINK_RE = re.compile(r'\[([^\]]*)\]\([^)]*\)')
# Markdown 图片: ![alt](url)
_MD_IMAGE_RE = re.compile(r'!\[[^\]]*\]\([^)]*\)')
# Markdown 标题: # ## ### ...
_MD_HEADING_RE = re.compile(r'^#{1,6}\s+', re.MULTILINE)
# Markdown 代码块: ``` ... ```
_MD_CODE_BLOCK_RE = re.compile(r'```[^`]*```', re.DOTALL)
# 行内代码: `code`
_MD_INLINE_CODE_RE = re.compile(r'`[^`]+`')
# URL 模式
_URL_RE = re.compile(r'https?://\S+')
# HTML 标签 (轻量，不引入 BeautifulSoup)
_HTML_TAG_RE = re.compile(r'<[^>]+>')
# HTML 实体
_HTML_ENTITY_RE = re.compile(r'&[a-zA-Z]+;|&#\d+;')


def _strip_markdown_noise(text: str) -> str:
    """移除 Markdown/HTML 标记，提取纯可读文本。

    不修改原始内容。处理顺序：
      图片 → 代码块 → 行内代码 → 链接(保留文本) → 强调标记 →
      HTML标签 → URL → 空白归一
    """
    t = _MD_IMAGE_RE.sub('', text)
    t = _MD_CODE_BLOCK_RE.sub(' ', t)
    t = _MD_INLINE_CODE_RE.sub(' ', t)
    t = _MD_LINK_RE.sub(r'\1', t)          # 保留链接可见文本
    # 强调标记 (不影响内部文本)
    t = re.sub(r'\*\*(.+?)\*\*', r'\1', t)  # **bold**
    t = re.sub(r'__(.+?)__', r'\1', t)       # __bold__
    t = re.sub(r'\*(.+?)\*', r'\1', t)       # *italic*
    t = re.sub(r'_(.+?)_', r'\1', t)         # _italic_
    t = re.sub(r'~~(.+?)~~', r'\1', t)       # ~~strikethrough~~
    t = _MD_HEADING_RE.sub('', t)
    t = _HTML_TAG_RE.sub(' ', t)
    t = _HTML_ENTITY_RE.sub(' ', t)
    t = _URL_RE.sub(' ', t)
    # 统一空白
    t = re.sub(r'[ \t]+', ' ', t)
    t = re.sub(r'\n{3,}', '\n\n', t)
    return t.strip()


def _extract_visible_text_from_html(html: str) -> str:
    """从 HTML 中提取可见文本（轻量实现，不引入 BeautifulSoup）。

    仅作为辅助信号，不替代 Markdown 正文分析。
    """
    if not html:
        return ""
    # 移除 script / style / noscript
    t = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL | re.IGNORECASE)
    t = re.sub(r'<style[^>]*>.*?</style>', ' ', t, flags=re.DOTALL | re.IGNORECASE)
    t = re.sub(r'<noscript[^>]*>.*?</noscript>', ' ', t, flags=re.DOTALL | re.IGNORECASE)
    t = _HTML_TAG_RE.sub(' ', t)
    t = _HTML_ENTITY_RE.sub(' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


# ═══════════════════════════════════════════════════════════════════
# 导航/模板词 — 克制的中英文词表
# ═══════════════════════════════════════════════════════════════════

_NAV_TERMS_CN = frozenset({
    "首页", "回到首页", "返回首页",
    "登录", "注册", "立即登录", "立即注册",
    "下载App", "下载APP", "下载客户端", "打开App",
    "返回顶部", "回到顶部",
    "上一篇", "下一篇", "上一页", "下一页",
    "隐私政策", "隐私条款", "隐私声明",
    "用户协议", "服务条款", "使用协议",
    "联系我们", "关于我们", "商务合作",
    "版权", "版权所有", "保留所有权利",
    "搜索", "导航", "菜单",
    "分享到", "分享至", "转发",
    "收藏", "点赞", "评论", "举报",
    "扫一扫", "扫码", "二维码",
    "热门推荐", "相关推荐", "为你推荐",
    "广告", "推广",
})

_NAV_TERMS_EN = frozenset({
    "home", "back to home",
    "login", "log in", "sign in", "signin",
    "register", "sign up", "signup", "create account",
    "download app", "open in app", "get the app",
    "back to top", "scroll to top",
    "previous", "next", "prev", "next page",
    "privacy policy", "privacy", "privacy statement",
    "terms of service", "terms of use", "terms and conditions",
    "contact us", "about us", "about",
    "copyright", "all rights reserved",
    "search", "navigation", "menu", "sitemap",
    "share", "tweet", "share to",
    "save", "bookmark", "like", "comment", "report",
    "advertisement", "sponsored", "promoted",
    "subscribe", "newsletter", "follow us",
    "cookie", "cookie policy", "cookie settings",
    "dark mode", "light mode", "theme",
})


def _is_navigation_line(line: str) -> bool:
    """判断单行文本是否主要为导航/模板内容。

    算法：对一行文本，检查它与导航词表的匹配程度。
    如果该行去掉空白后几乎全部被导航词覆盖 → 视为导航行。

    这比逐字符匹配更准确，因为不会因为正文中偶然出现
    "登录"二字就把整行判为导航。
    """
    stripped = line.strip()
    if not stripped:
        return False

    lower = stripped.lower()

    # 检查中文导航词 (使用 in 判断，因为中文词不依赖词边界)
    cn_hits = sum(1 for term in _NAV_TERMS_CN if term in stripped)
    # 检查英文导航词
    en_hits = sum(1 for term in _NAV_TERMS_EN if term in lower)

    total_hits = cn_hits + en_hits
    if total_hits == 0:
        return False

    # 计算被导航词覆盖的字符数（粗略估算）
    nav_chars = 0
    for term in _NAV_TERMS_CN:
        if term in stripped:
            nav_chars += len(term) * stripped.count(term)
    for term in _NAV_TERMS_EN:
        if term in lower:
            nav_chars += len(term) * lower.count(term)

    line_len = max(len(stripped), 1)
    # 导航词覆盖超过 50% 行长度 → 导航行
    return (nav_chars / line_len) >= 0.50


# ═══════════════════════════════════════════════════════════════════
# 特殊页面模式
# ═══════════════════════════════════════════════════════════════════

_SCRIPT_PLACEHOLDER_PATTERNS: list[re.Pattern] = [
    # 中文
    re.compile(r"请(?:开启|启用|打开)[Jj]ava[Ss]cript"),
    re.compile(r"您的浏览器(?:不支持|需要|必须)"),
    re.compile(r"请(?:使用|升级).*浏览器"),
    re.compile(r"JavaScript\s*(?:未启用|被禁用|is\s+disabled)"),
    # 英文
    re.compile(r"JavaScript\s+is\s+(?:required|not\s+available|disabled)", re.IGNORECASE),
    re.compile(r"Please\s+enable\s+JavaScript", re.IGNORECASE),
    re.compile(r"This\s+(?:page|site)\s+requires?\s+JavaScript", re.IGNORECASE),
    re.compile(r"Your\s+browser\s+(?:does\s+not\s+support|is\s+not\s+supported)",
              re.IGNORECASE),
]

_LOGIN_PATTERNS: list[re.Pattern] = [
    # 中文 — 需要登录才能查看
    re.compile(r"登录后(?:查看|可见|阅读|浏览)"),
    re.compile(r"请先登录"),
    re.compile(r"登录(?:才能|即可|后方可)"),
    re.compile(r"您需要登录"),
    # 英文
    re.compile(r"(?:Sign|Log)\s+in\s+to\s+(?:view|read|continue|access)", re.IGNORECASE),
    re.compile(r"Please\s+(?:sign|log)\s+in", re.IGNORECASE),
    re.compile(r"You\s+(?:need|must)\s+(?:to\s+)?(?:sign|log)\s+in", re.IGNORECASE),
    re.compile(r"(?:Sign|Log)\s+in\s+required", re.IGNORECASE),
]

_CAPTCHA_PATTERNS: list[re.Pattern] = [
    re.compile(r"验证码"),
    re.compile(r"安全验证"),
    re.compile(r"人机验证"),
    re.compile(r"CAPTCHA", re.IGNORECASE),
    re.compile(r"verify\s+(?:you\s+are|that\s+you\s+are)\s+(?:a\s+)?human", re.IGNORECASE),
    re.compile(r"security\s+(?:verification|check)", re.IGNORECASE),
    re.compile(r"prove\s+you\s+(?:are|'re)\s+(?:human|not\s+a\s+robot)", re.IGNORECASE),
    re.compile(r"请输入(?:验证码|图片中的|图中的)"),
    re.compile(r"滑动验证"),
    re.compile(r"点击(?:验证|确认)"),
]

_NOT_FOUND_PATTERNS: list[re.Pattern] = [
    re.compile(r"(?:页面|内容|文章)(?:不存在|已删除|已下架|已失效|未找到)"),
    re.compile(r"Page\s+(?:not\s+found|does\s+not\s+exist)", re.IGNORECASE),
    re.compile(r"404\s*(?:Not\s+Found|Page)?", re.IGNORECASE),
    re.compile(r"Content\s+(?:not\s+found|removed|deleted|unavailable)", re.IGNORECASE),
    re.compile(r"链接已失效"),
]


def _detect_special_patterns(
    plain_text: str,
) -> dict[str, float]:
    """检测特殊页面模式，返回 {类型: 命中字符占比}。

    占比基于 pattern 匹配到的总字符数 / 纯文本长度。
    对短文本（<500 chars）更敏感，对长文本更宽容。
    """
    text_len = max(len(plain_text), 1)
    results: dict[str, float] = {}

    def _match_ratio(patterns: list[re.Pattern], text: str) -> float:
        matched_chars = 0
        for pat in patterns:
            for m in pat.finditer(text):
                matched_chars += len(m.group())
        # 去重估计：同一字符被多个 pattern 命中时可能重复计数
        # 简单 clamp 到文本长度
        return min(matched_chars / text_len, 1.0)

    results["script_placeholder"] = _match_ratio(_SCRIPT_PLACEHOLDER_PATTERNS, plain_text)
    results["login"] = _match_ratio(_LOGIN_PATTERNS, plain_text)
    results["captcha"] = _match_ratio(_CAPTCHA_PATTERNS, plain_text)
    results["not_found"] = _match_ratio(_NOT_FOUND_PATTERNS, plain_text)

    return results


# ═══════════════════════════════════════════════════════════════════
# 重复率计算
# ═══════════════════════════════════════════════════════════════════

# 标点/空白 5-gram — 不应计入重复率
# 纯标点/空白 5-gram — 不应计入重复率统计
_NON_CONTENT_5GRAM_RE = re.compile(
    r'^[\s,;:!?\.，。；：！？、'
    r'"“”‘’'    # 弯引号
    r'「」『』'    # 直角引号
    r'【】《》'    # 各种括号
    r'（）\[\]{}'           # 半角全角括号
    r'\-—…·'                        # 连接号和省略号
    r'\t\n\r]+$'
)


def _compute_duplication_ratio(text: str, max_chars: int = 4000) -> float:
    """计算文本 5-gram 重复率。

    算法：
      1. 取前 max_chars 个字符
      2. 滑动 5-gram 窗口，跳过纯标点/空白窗口
      3. 用 Counter 统计每个 5-gram 的出现频次
      4. 重复率 = 重复窗口实例数 / 总窗口数

    关键：用 Counter 保留频次信息（不使用 set），统计的是
    "所有窗口中，有多少个是之前已经出现过的"。
    计算公式：(sum(count) - unique_count) / sum(count)
    即 (总窗口数 - 唯一窗口数) / 总窗口数。

    这保证了：
      - "abcde" 出现 1 次 → 不贡献重复
      - "abcde" 出现 5 次 → 贡献 4 个重复窗口实例
      - 正确反映内容的实际重复程度

    Args:
        text: 标准化后的纯文本
        max_chars: 最大分析字符数

    Returns:
        0.0–1.0 的重复比例
    """
    if not text:
        return 0.0

    # 取前 max_chars
    analysis_text = text[:max_chars]

    if len(analysis_text) < 5:
        return 0.0

    # 5-gram 窗口
    windows: list[str] = []
    for i in range(len(analysis_text) - 4):
        window = analysis_text[i:i + 5]
        # 跳过纯标点/空白窗口
        if _NON_CONTENT_5GRAM_RE.match(window):
            continue
        windows.append(window)

    if not windows:
        return 0.0

    counter = Counter(windows)
    total_windows = len(windows)
    unique_windows = len(counter)

    # 重复窗口实例数 = 总窗口数 - 唯一窗口数
    # 每个 5-gram 的第一次出现不重复，后续每次出现都是重复
    return (total_windows - unique_windows) / total_windows


# ═══════════════════════════════════════════════════════════════════
# 自然语言比例
# ═══════════════════════════════════════════════════════════════════

# 中文字符 Unicode 范围
_CJK_RANGES: list[tuple[int, int]] = [
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs
    (0x3400, 0x4DBF),   # CJK Unified Ideographs Extension A
    (0x20000, 0x2A6DF), # CJK Unified Ideographs Extension B
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
]


def _is_cjk(char: str) -> bool:
    cp = ord(char)
    return any(lo <= cp <= hi for lo, hi in _CJK_RANGES)


def _compute_natural_language_ratio(text: str) -> float:
    """计算自然语言字符占比。

    自然语言 = 中文字符 + 英文字母。
    排除：数字、空白、标点、URL残留、标记残留、代码特征。

    返回值 0.0–1.0。

    注意：技术文章含代码块时比例会偏低，但不应因此
    把正常技术文章判为不完整。本指标主要用于识别
    空壳 HTML、纯脚本、纯配置、乱码等极端情况。
    """
    if not text:
        return 0.0

    lang_chars = 0
    total = 0

    for ch in text:
        if ch.isspace():
            continue
        total += 1
        if _is_cjk(ch):
            lang_chars += 1
        elif ch.isalpha() and ch.isascii():
            lang_chars += 1
        # 数字、标点、符号不计入自然语言

    return lang_chars / max(total, 1)


# ═══════════════════════════════════════════════════════════════════
# 段落分析
# ═══════════════════════════════════════════════════════════════════

def _analyze_paragraphs(
    plain_text: str,
    config: QualityConfig,
) -> tuple[int, int]:
    """分析段落。返回 (总段落数, 有效段落数)。

    段落以连续两个及以上换行符分隔。
    有效段落定义：
      - 去空白后 >= valid_paragraph_min_chars
      - 不是纯链接或图片标记残骸
      - 不是导航行集合（>60% 行为导航行）
    """
    if not plain_text:
        return 0, 0

    # 按空行分隔段落
    raw_paras = re.split(r'\n\s*\n', plain_text)
    total = len(raw_paras)
    valid = 0

    for para in raw_paras:
        stripped = para.strip()
        if len(stripped) < config.valid_paragraph_min_chars:
            continue

        # 纯 URL 残留 → 跳过
        if re.match(r'^https?://\S+$', stripped):
            continue

        # 检查是否为导航行集合
        lines = stripped.split('\n')
        nav_lines = sum(1 for line in lines if _is_navigation_line(line))
        if len(lines) > 1 and nav_lines / len(lines) > 0.6:
            continue

        valid += 1

    return total, valid


def _analyze_code_blocks(content: str) -> int:
    """统计代码块数量（```围栏），用于技术文章识别。"""
    return len(re.findall(r'```', content)) // 2  # 每对 ``` 为一个代码块


# ═══════════════════════════════════════════════════════════════════
# 截断检测
# ═══════════════════════════════════════════════════════════════════

_SENTENCE_END_RE = re.compile(r'[。！？.!?…"”\'》\)】]\s*$')


def _detect_truncation(
    plain_text: str,
    paragraph_count: int,
    config: QualityConfig,
) -> bool:
    """检测正文是否被截断。

    启发式规则（不可靠，仅作辅助信号）：
      - 最后一段远短于前几段平均长度
      - 最后一句话没有正常结束标点
    """
    if paragraph_count < 2:
        return False

    paragraphs = [p.strip() for p in re.split(r'\n\s*\n', plain_text) if p.strip()]
    if len(paragraphs) < 2:
        return False

    # 最后一段
    last = paragraphs[-1]
    # 前面各段平均长度
    prev_avg = sum(len(p) for p in paragraphs[:-1]) / (len(paragraphs) - 1)

    if prev_avg <= 0:
        return False

    # 末段太短
    if len(last) / prev_avg < config.truncation_last_para_ratio:
        return True

    # 末段没有正常句末标点
    if len(last) > 20 and not _SENTENCE_END_RE.search(last):
        return True

    return False


# ═══════════════════════════════════════════════════════════════════
# 导航比例计算
# ═══════════════════════════════════════════════════════════════════

def _compute_navigation_ratio(plain_text: str) -> float:
    """计算导航文本行占比。

    算法：
      1. 将文本按行分割
      2. 对每行调用 _is_navigation_line()
      3. 导航比例 = 导航行数 / 总行数

    使用行级而非字符级命中率，避免正常文章因偶然
    提到"登录"一词被严重扣分。
    """
    if not plain_text:
        return 0.0

    lines = [l for l in plain_text.split('\n') if l.strip()]
    if not lines:
        return 0.0

    nav_lines = sum(1 for line in lines if _is_navigation_line(line))
    return nav_lines / len(lines)


# ═══════════════════════════════════════════════════════════════════
# 评分
# ═══════════════════════════════════════════════════════════════════

def _score_length(content_length: int, config: QualityConfig) -> float:
    """正文长度评分 0 – length_score_max。

    分段线性：
      -    0–200  chars → 0–5 分
      -  200–500  chars → 5–15 分
      -  500–2000 chars → 15–25 分
      - 2000+     chars → 25–30 分
    """
    if content_length <= 0:
        return 0.0
    if content_length < 200:
        return 5.0 * (content_length / 200)
    if content_length < 500:
        return 5.0 + 10.0 * ((content_length - 200) / 300)
    if content_length < 2000:
        return 15.0 + 10.0 * ((content_length - 500) / 1500)
    return min(float(config.length_score_max),
               25.0 + 5.0 * min((content_length - 2000) / 3000, 1.0))


def _score_paragraphs(valid_count: int, config: QualityConfig) -> float:
    """有效段落评分 0 – paragraph_score_max。

      - 0 段 → 0
      - 1 段 → 5
      - 2 段 → 10
      - 3–5 段 → 15–20
      - 6+ 段 → 20–25
    """
    if valid_count <= 0:
        return 0.0
    if valid_count == 1:
        return 5.0
    if valid_count == 2:
        return 10.0
    if valid_count <= 5:
        return 15.0 + 5.0 * ((valid_count - 3) / 3)
    return min(float(config.paragraph_score_max),
               20.0 + 5.0 * min((valid_count - 6) / 10, 1.0))


def _score_language(nl_ratio: float, config: QualityConfig) -> float:
    """自然语言比例评分 0 – language_score_max。

      - 0.0–0.25 → 0–5
      - 0.25–0.50 → 5–15
      - 0.50–0.75 → 15–22
      - 0.75–1.0  → 22–25
    """
    if nl_ratio <= 0.0:
        return 0.0
    if nl_ratio < 0.25:
        return 5.0 * (nl_ratio / 0.25)
    if nl_ratio < 0.50:
        return 5.0 + 10.0 * ((nl_ratio - 0.25) / 0.25)
    if nl_ratio < 0.75:
        return 15.0 + 7.0 * ((nl_ratio - 0.50) / 0.25)
    return min(float(config.language_score_max),
               22.0 + 3.0 * min((nl_ratio - 0.75) / 0.25, 1.0))


def _score_structure(
    title_present: bool,
    heading_count: int,
    code_block_count: int,
    config: QualityConfig,
) -> float:
    """结构评分 0 – structure_score_max。

      - 有标题: +10
      - 有 1+ 个 Markdown 标题: +5
      - 有代码块（技术文章特征）: +5 (上限)
    """
    score = 0.0
    if title_present:
        score += 10.0
    if heading_count >= 1:
        score += 5.0
    score += min(5.0, code_block_count * 2.5)
    return min(score, float(config.structure_score_max))


def _penalty_navigation(nav_ratio: float, config: QualityConfig) -> float:
    """导航比例惩罚 0 – navigation_penalty_max。"""
    if nav_ratio <= config.max_navigation_ratio:
        return 0.0
    # 超出部分线性映射
    excess = min(nav_ratio - config.max_navigation_ratio, 1.0 - config.max_navigation_ratio)
    max_excess = 1.0 - config.max_navigation_ratio
    return (excess / max(max_excess, 0.01)) * config.navigation_penalty_max


def _penalty_duplication(dup_ratio: float, config: QualityConfig) -> float:
    """重复率惩罚 0 – duplication_penalty_max。"""
    if dup_ratio <= config.max_duplication_ratio:
        return 0.0
    excess = min(dup_ratio - config.max_duplication_ratio, 1.0 - config.max_duplication_ratio)
    max_excess = 1.0 - config.max_duplication_ratio
    return (excess / max(max_excess, 0.01)) * config.duplication_penalty_max


def _penalty_placeholder(
    ratio: float,
    text_length: int,
    density_threshold: float,
    short_threshold: int,
    max_penalty: int,
) -> float:
    """特殊页面惩罚（JS占位/登录/验证码）。

    短文本（< short_threshold）且命中 → 全额惩罚。
    长文本 → 按密度超过阈值部分线性惩罚。
    """
    if ratio <= 0.0:
        return 0.0
    if text_length < short_threshold and ratio > 0.1:
        return float(max_penalty)
    if ratio > density_threshold:
        excess = ratio - density_threshold
        max_excess = 1.0 - density_threshold
        return (excess / max(max_excess, 0.01)) * max_penalty
    return 0.0


# ═══════════════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════════════

def assess_article(
    title: str,
    content: str,
    html: str = "",
    *,
    config: QualityConfig | None = None,
) -> QualityReport:
    """评估文章正文质量。

    Args:
        title: 文章标题（可为空字符串）
        content: 文章正文（Markdown 或纯文本）
        html: 原始 HTML（可选，用于辅助提取可见文本）
        config: 质量阈值配置。None 则使用默认配置。

    Returns:
        QualityReport: 包含 complete、score、issues、metrics。
    """
    cfg = config or DEFAULT_CONFIG

    # ── 预处理 ──
    plain_text = _strip_markdown_noise(content)
    plain_text_length = len(plain_text)

    # 如提供了 HTML，提取可见文本作为补充信号
    html_visible = _extract_visible_text_from_html(html) if html else ""
    # 合并 Markdown 纯文本和 HTML 可见文本，取较长者作为分析基础
    analysis_text = plain_text if len(plain_text) >= len(html_visible) else html_visible
    analysis_length = len(analysis_text)

    # 空内容快速返回
    if analysis_length == 0 and not title:
        return QualityReport(
            complete=False,
            score=0,
            issues=(QualityIssue.TEXT_TOO_SHORT, QualityIssue.TITLE_MISSING),
            metrics={
                "title_present": False,
                "content_length": len(content),
                "plain_text_length": 0,
                "paragraph_count": 0,
                "valid_paragraph_count": 0,
                "navigation_ratio": 0.0,
                "duplication_ratio": 0.0,
                "natural_language_ratio": 0.0,
                "placeholder_detected": False,
                "login_detected": False,
                "captcha_detected": False,
                "possible_truncation": False,
            },
        )

    # ── 基础指标 ──
    title_present = bool(title and title.strip())

    # 段落分析
    paragraph_count, valid_paragraph_count = _analyze_paragraphs(analysis_text, cfg)

    # Markdown 标题数（用于结构评分）
    heading_count = len(re.findall(r'^#{1,6}\s+\S', content, re.MULTILINE))

    # 代码块数
    code_block_count = _analyze_code_blocks(content)

    # 导航比例
    navigation_ratio = _compute_navigation_ratio(analysis_text)

    # 重复率
    duplication_ratio = _compute_duplication_ratio(
        analysis_text, cfg.max_duplication_analysis_chars
    )

    # 自然语言比例
    natural_language_ratio = _compute_natural_language_ratio(analysis_text)

    # 特殊页面检测
    special = _detect_special_patterns(analysis_text)
    placeholder_detected = special["script_placeholder"] > 0.1
    login_detected = special["login"] > 0.1
    captcha_detected = special["captcha"] > 0.1

    # 截断检测
    possible_truncation = _detect_truncation(analysis_text, paragraph_count, cfg)

    # ── 汇总问题 ──
    issues: list[QualityIssue] = []

    if not title_present:
        issues.append(QualityIssue.TITLE_MISSING)

    if analysis_length < cfg.min_content_length:
        issues.append(QualityIssue.TEXT_TOO_SHORT)

    if valid_paragraph_count < cfg.min_valid_paragraphs:
        issues.append(QualityIssue.TOO_FEW_PARAGRAPHS)

    if navigation_ratio > cfg.max_navigation_ratio:
        issues.append(QualityIssue.NAVIGATION_RATIO_HIGH)

    if duplication_ratio > cfg.max_duplication_ratio:
        issues.append(QualityIssue.DUPLICATION_RATIO_HIGH)

    if natural_language_ratio < cfg.min_natural_language_ratio:
        issues.append(QualityIssue.NATURAL_LANGUAGE_RATIO_LOW)

    # 特殊页面 — 基于密度判定
    if special["script_placeholder"] > cfg.placeholder_density_threshold or (
        analysis_length < cfg.short_text_threshold and placeholder_detected
    ):
        issues.append(QualityIssue.SCRIPT_PLACEHOLDER)

    if special["login"] > cfg.placeholder_density_threshold or (
        analysis_length < cfg.short_text_threshold and login_detected
    ):
        issues.append(QualityIssue.LOGIN_REQUIRED)

    if special["captcha"] > cfg.placeholder_density_threshold or (
        analysis_length < cfg.short_text_threshold and captcha_detected
    ):
        issues.append(QualityIssue.CAPTCHA_DETECTED)

    # 菜单/页脚 判定：有效段落极少 + 导航比例极高
    if valid_paragraph_count <= 1 and navigation_ratio > 0.50:
        issues.append(QualityIssue.MENU_OR_FOOTER_ONLY)

    if possible_truncation:
        issues.append(QualityIssue.POSSIBLY_TRUNCATED)

    # ── 评分 ──
    positive_score = (
        _score_length(analysis_length, cfg)
        + _score_paragraphs(valid_paragraph_count, cfg)
        + _score_language(natural_language_ratio, cfg)
        + _score_structure(title_present, heading_count, code_block_count, cfg)
    )

    penalty_score = (
        _penalty_navigation(navigation_ratio, cfg)
        + _penalty_duplication(duplication_ratio, cfg)
        + _penalty_placeholder(
            special["script_placeholder"], analysis_length,
            cfg.placeholder_density_threshold, cfg.short_text_threshold,
            cfg.placeholder_penalty_max,
        )
        + _penalty_placeholder(
            special["login"], analysis_length,
            cfg.placeholder_density_threshold, cfg.short_text_threshold,
            cfg.login_penalty_max,
        )
        + _penalty_placeholder(
            special["captcha"], analysis_length,
            cfg.placeholder_density_threshold, cfg.short_text_threshold,
            cfg.captcha_penalty_max,
        )
    )

    score = max(0, min(100, round(positive_score - penalty_score)))

    # ── 完整性判定 ──
    fatal_present = any(issue in FATAL_ISSUES for issue in issues)
    complete = (
        not fatal_present
        and score >= cfg.min_score_complete
        and analysis_length >= cfg.min_content_length
        and valid_paragraph_count >= cfg.min_valid_paragraphs
    )

    # ── 构建报告 ──
    metrics: dict[str, float | int | str | bool] = {
        "title_present": title_present,
        "content_length": len(content),
        "plain_text_length": plain_text_length,
        "analysis_text_length": analysis_length,
        "paragraph_count": paragraph_count,
        "valid_paragraph_count": valid_paragraph_count,
        "heading_count": heading_count,
        "code_block_count": code_block_count,
        "navigation_ratio": round(navigation_ratio, 4),
        "duplication_ratio": round(duplication_ratio, 4),
        "natural_language_ratio": round(natural_language_ratio, 4),
        "placeholder_detected": placeholder_detected,
        "login_detected": login_detected,
        "captcha_detected": captcha_detected,
        "possible_truncation": possible_truncation,
    }

    return QualityReport(
        complete=complete,
        score=score,
        issues=tuple(issues),
        metrics=metrics,
    )


# ═══════════════════════════════════════════════════════════════════
# 便捷函数 — 快速调用
# ═══════════════════════════════════════════════════════════════════

def quick_check(title: str, content: str, html: str = "") -> bool:
    """快速检查：文章是否完整？返回 bool。

    等价于 assess_article(title, content, html).complete。
    """
    return assess_article(title, content, html).complete


def diagnostic_summary(report: QualityReport) -> str:
    """生成面向用户的诊断摘要文本。

    用于调试输出和日志，不用于程序判断。
    """
    parts: list[str] = []

    parts.append(f"完整性: {'✅ 完整' if report.complete else '❌ 不完整'}")
    parts.append(f"评分: {report.score}/100")
    parts.append(f"正文字符: {report.metrics.get('analysis_text_length', '?')}")
    parts.append(f"有效段落: {report.metrics.get('valid_paragraph_count', '?')}")
    parts.append(f"导航比例: {report.metrics.get('navigation_ratio', '?')}")
    parts.append(f"自然语言比例: {report.metrics.get('natural_language_ratio', '?')}")

    if report.issues:
        parts.append("问题:")
        for issue in report.issues:
            label = ISSUE_LABELS.get(issue, issue.value)
            parts.append(f"  - {label}")

    return "\n".join(parts)
