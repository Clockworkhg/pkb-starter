#!/usr/bin/env python3
"""
PKB Starter -- Runtime Skill Manager (v0.4.0)

Manages optional skills in a live PKB installation. Supports listing, describing,
installing, auditing, enabling, disabling, and updating skills. All third-party
skills are downloaded to skills/_vendor/ and never auto-executed.

Usage:
    python skill_manager.py --target "D:\\MyKB" --list
    python skill_manager.py --target "D:\\MyKB" --describe deep-research-skills
    python skill_manager.py --target "D:\\MyKB" --install deep-research-skills
    python skill_manager.py --target "D:\\MyKB" --install-profile student
    python skill_manager.py --target "D:\\MyKB" --audit
    python skill_manager.py --target "D:\\MyKB" --enabled
    python skill_manager.py --target "D:\\MyKB" --enable <skill-id>
    python skill_manager.py --target "D:\\MyKB" --disable <skill-id>
    python skill_manager.py --target "D:\\MyKB" --update-catalog

Safety:
    - No third-party code is auto-executed (git clone only).
    - High-risk skills require explicit user confirmation.
    - Reference-only skills are never installed.
    - Plugin marketplace skills show manual install instructions.
    - MCP is never auto-configured.
    - API keys are never read, stored, or configured.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path


# -- Path resolution --------------------------------------------------------

STARTER_DIR = Path(__file__).resolve().parent.parent
CATALOG_PATH = STARTER_DIR / "skills_registry" / "skill_catalog.json"
PROFILES_PATH = STARTER_DIR / "skills_registry" / "profiles.json"
ADAPTERS_SRC = STARTER_DIR / "template" / "skill_adapters"

VENDOR_DIR_REL = "skills/_vendor"
ADAPTER_DIR_REL = "templates/skill_adapters"

ALLOWED_PROFILES = ["core", "student", "research", "developer", "creator", "output", "security", "full", "custom"]

CATEGORY_LABELS = {
    "knowledge_capture": "Knowledge Capture",
    "academic_research": "Academic Research",
    "document_processing": "Document Processing",
    "knowledge_management": "Knowledge Management",
    "security_privacy": "Security & Privacy",
    "creation_output": "Creation & Output",
    "meta_tooling": "Meta Tooling",
    "development": "Development",
    "reference": "Reference Only",
}

RISK_SYMBOLS = {
    "low": "[LOW]",
    "medium": "[MEDIUM]",
    "high": "[HIGH]",
    "reference_only": "[REF]",
}

# Profile descriptions for display (English)
PROFILE_DESCRIPTIONS = {
    "core": {
        "title": "Core",
        "tagline": "Pure PKB. Zero external skills.",
        "desc": "Basic personal knowledge base with PKB's built-in tools only: web collection, auto ingest, file import, health checks, privacy scanning, document conversion, git versioning. Start here and add skills later.",
        "skills": 0,
    },
    "student": {
        "title": "Student",
        "tagline": "Coursework, papers, literature review.",
        "desc": "Academic essentials for students: literature search and review, paper section writing, citation management (APA/GB/T 7714/IEEE), article extraction for research sources, YouTube transcript capture. Ideal for undergraduates and coursework-focused grad students.",
        "skills": 8,
    },
    "research": {
        "title": "Research",
        "tagline": "Full academic pipeline. Graduate-level.",
        "desc": "Comprehensive academic workflow: deep multi-turn research, agent-based research pipeline (31 sub-skills), literature tools, experiment design, data analysis, figure/table generation, Zotero integration, CNKI Chinese database access. For systematic academic research.",
        "skills": 12,
    },
    "developer": {
        "title": "Developer",
        "tagline": "Code projects, docs, GitHub research.",
        "desc": "Software engineering focused: document processing for technical docs, semantic code search (QMD), project kanban boards, GitHub repository analysis, code debugging, article extraction. For developers documenting projects and researching code.",
        "skills": 7,
    },
    "creator": {
        "title": "Creator",
        "tagline": "Writers, musicians, filmmakers.",
        "desc": "Content creation toolkit: AI prompt library management, song/lyrics archive with version tracking, script breakdown and storyboard generation, article extraction, YouTube transcripts, kanban project management. For creative professionals building a reference library.",
        "skills": 7,
    },
    "output": {
        "title": "Output & Publishing",
        "tagline": "Reports, papers, presentations.",
        "desc": "Output-focused: document conversion (DOCX/PDF/PPTX/MD), academic paper writing with evidence support, citation management, prompt library, slide generation. For users who primarily produce documents and reports.",
        "skills": 7,
    },
    "security": {
        "title": "Security & Privacy",
        "tagline": "Audit, sanitize, harden.",
        "desc": "Security-hardened minimal setup: enhanced secret scanning, privacy sanitization, git versioning with pre-commit checks. For auditing your knowledge base before sharing or publishing.",
        "skills": 3,
    },
    "full": {
        "title": "Full Stack",
        "tagline": "All 24 recommended skills. Power user.",
        "desc": "Complete PKB ecosystem: academic research, document processing, creation tools, semantic search, project management, security hardening. High-risk skills (CNKI, Zotero) are NOT auto-enabled -- use --enable-risky to add them. Review risk levels before installing.",
        "skills": 24,
    },
    "custom": {
        "title": "Custom",
        "tagline": "Hand-pick from 43 entries.",
        "desc": "Interactive selection: browse the full 43-entry catalog and choose exactly which skills to install. See descriptions and risk levels before selecting. Best for advanced users who know what they need.",
        "skills": "interactive",
    },
}

# Profile descriptions in Chinese
PROFILE_DESCRIPTIONS_ZH = {
    "core": {
        "title": "Core",
        "tagline": "纯 PKB，零外部技能。",
        "desc": "基础个人知识库，仅使用 PKB 内置工具：网页采集、自动入库、文件导入、健康检查、隐私扫描、文档转换、Git 版本管理。从这里开始，之后按需添加技能。",
        "skills": 0,
    },
    "student": {
        "title": "Student",
        "tagline": "课程作业、论文、文献综述。",
        "desc": "学生学术必备：文献搜索与综述、论文章节写作、引用管理（APA/GB/T 7714/IEEE）、研究来源文章提取、YouTube 转录采集。适合本科生和以课程为中心的研究生。",
        "skills": 8,
    },
    "research": {
        "title": "Research",
        "tagline": "完整学术流程，研究生级别。",
        "desc": "全面学术工作流：深度多轮研究、Agent 驱动研究流程（31 个子技能）、文献工具、实验设计、数据分析、图表生成、Zotero 集成、中国知网数据库访问。适用于系统性学术研究。",
        "skills": 12,
    },
    "developer": {
        "title": "Developer",
        "tagline": "代码项目、文档、GitHub 研究。",
        "desc": "软件工程方向：技术文档处理、语义代码搜索（QMD）、项目看板、GitHub 仓库分析、代码调试、文章提取。适合记录项目和研究代码的开发者。",
        "skills": 7,
    },
    "creator": {
        "title": "Creator",
        "tagline": "写作者、音乐人、影视制作人。",
        "desc": "内容创作工具包：AI prompt 库管理、带版本追踪的歌词/歌曲归档、剧本分解与分镜生成、文章提取、YouTube 转录、看板项目管理。适合构建参考资料库的创意专业人士。",
        "skills": 7,
    },
    "output": {
        "title": "Output & Publishing",
        "tagline": "报告、论文、演示文稿。",
        "desc": "产出导向：文档转换（DOCX/PDF/PPTX/MD）、带证据支持的学术论文写作、引用管理、prompt 库、幻灯片生成。适合主要生产文档和报告的用户。",
        "skills": 7,
    },
    "security": {
        "title": "Security & Privacy",
        "tagline": "审计、脱敏、加固。",
        "desc": "安全加固最小化设置：增强密钥扫描、隐私脱敏、带提交前检查的 Git 版本管理。用于分享或发布前审计你的知识库。",
        "skills": 3,
    },
    "full": {
        "title": "Full Stack",
        "tagline": "全部 24 个推荐技能。高级用户。",
        "desc": "完整 PKB 生态：学术研究、文档处理、创作工具、语义搜索、项目管理、安全加固。高风险技能（CNKI、Zotero）不自动启用 -- 使用 --enable-risky 添加。安装前请查看风险等级。",
        "skills": 24,
    },
    "custom": {
        "title": "Custom",
        "tagline": "从 43 个条目中手选。",
        "desc": "交互式选择：浏览全部 43 个目录条目，精确选择要安装的技能。选择前可查看说明和风险等级。最适合知道自己需要什么的高级用户。",
        "skills": "interactive",
    },
}

# Chinese translations for zh-CN mode
CATEGORY_LABELS_ZH = {
    "knowledge_capture": "知识采集",
    "academic_research": "学术研究",
    "document_processing": "文档处理",
    "knowledge_management": "知识管理",
    "security_privacy": "安全与隐私",
    "creation_output": "创作与产出",
    "meta_tooling": "元工具",
    "development": "开发",
    "reference": "仅供参考",
}

RISK_SYMBOLS_ZH = {
    "low": "[低风险]",
    "medium": "[中风险]",
    "high": "[高风险]",
    "reference_only": "[参考]",
}

RISK_EXPLANATIONS_ZH = {
    "low": "低风险 -- 仅操作本地文件，无需外部 API，不需要特殊权限",
    "medium": "中风险 -- 可能涉及网络请求或可选的外部 API，请查看说明",
    "high": "高风险 -- 需要外部运行时、MCP 服务器或 API key，需明确同意才能安装",
    "reference_only": "仅供参考 -- 不会安装。需要手动从插件市场或 MCP 商店获取",
}

# Language cache per target
_lang_cache = {}

def detect_language(target: Path) -> str:
    """Detect language preference from pkb.config.json. Returns 'en' or 'zh-CN'."""
    target_key = str(target.resolve())
    if target_key in _lang_cache:
        return _lang_cache[target_key]
    try:
        config = load_pkb_config(target)
        lang = config.get("language") or config.get("output_language") or "en"
    except Exception:
        lang = "en"
    _lang_cache[target_key] = lang
    return lang

def zh_label(zh_text: str, en_text: str, target: Path = None) -> str:
    """Return Chinese or English label based on target language."""
    if target is not None and detect_language(target) in ("zh-CN", "bilingual"):
        return zh_text
    return en_text

def get_category_label(cat: str, target: Path = None) -> str:
    """Get category label in the appropriate language."""
    return zh_label(
        CATEGORY_LABELS_ZH.get(cat, cat),
        CATEGORY_LABELS.get(cat, cat),
        target
    )

def get_risk_symbol(level: str, target: Path = None) -> str:
    """Get risk symbol in the appropriate language."""
    return zh_label(
        RISK_SYMBOLS_ZH.get(level, level),
        RISK_SYMBOLS.get(level, level),
        target
    )

def get_field_zh(entry: dict, field_en: str, field_zh: str) -> str:
    """Get a field from catalog entry, preferring Chinese if available."""
    zh_val = entry.get(field_zh)
    if zh_val:
        if isinstance(zh_val, list):
            return zh_val
        return zh_val
    return entry.get(field_en, "")

def get_profile_desc(profile_id: str, target: Path = None) -> dict:
    """Get profile description in the appropriate language."""
    is_zh = target is not None and detect_language(target) in ("zh-CN", "bilingual")
    if is_zh and profile_id in PROFILE_DESCRIPTIONS_ZH:
        return PROFILE_DESCRIPTIONS_ZH[profile_id]
    return PROFILE_DESCRIPTIONS.get(profile_id, {})


# -- JSON Helpers ------------------------------------------------------------

def load_json(path: Path) -> dict:
    """Load a JSON file. Exit with message on failure."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[FAIL] Cannot load {path}: {e}")
        sys.exit(1)


def load_pkb_config(target: Path) -> dict:
    """Load pkb.config.json, creating default if missing."""
    config_path = target / "pkb.config.json"
    if not config_path.is_file():
        return {
            "version": "0.1.0",
            "skills": {
                "catalog_version": "0.4.0",
                "installed_profiles": [],
                "installed_skills": [],
                "enabled_skills": [],
                "disabled_skills": [],
                "vendor_downloads": [],
                "enabled_adapters": [],
                "pending_audit": [],
            }
        }
    config = load_json(config_path)
    if "skills" not in config:
        config["skills"] = {
            "catalog_version": "0.4.0",
            "installed_profiles": [],
            "installed_skills": [],
            "enabled_skills": [],
            "disabled_skills": [],
            "vendor_downloads": [],
            "enabled_adapters": [],
            "pending_audit": [],
        }
    return config


def save_pkb_config(target: Path, config: dict):
    """Save pkb.config.json."""
    config_path = target / "pkb.config.json"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


# -- Display Helpers ---------------------------------------------------------

def print_header(title: str):
    print()
    print("=" * 72)
    print(f"  {title}")
    print("=" * 72)
    print()


def print_separator():
    print("-" * 72)


# -- Status / Overview -------------------------------------------------------

def cmd_status(target: Path, catalog: dict, profiles: dict, pkb_config: dict):
    """Show installed skills, available profiles, and enabled status."""
    skills_state = pkb_config.get("skills", {})
    catalog_map = {s["id"]: s for s in catalog["skills"]}
    is_zh = detect_language(target) in ("zh-CN", "bilingual")

    title = "PKB Skill Manager -- Status"
    if is_zh:
        title = "PKB 技能管理器 -- 状态"
    print_header(title)

    # Installed profiles
    installed_profiles = skills_state.get("installed_profiles", [])
    if is_zh:
        profiles_str = ', '.join(installed_profiles) if installed_profiles else '无 (仅 core)'
        print(f"  已安装配置预设: {profiles_str}")
    else:
        print(f"  Installed profiles: {', '.join(installed_profiles) if installed_profiles else 'None (core only)'}")

    # Installed skills (from skills/_vendor/)
    vendor_dir = target / VENDOR_DIR_REL
    installed_ids = []
    if vendor_dir.is_dir():
        installed_ids = [d.name for d in vendor_dir.iterdir() if d.is_dir()]

    enabled_ids = skills_state.get("enabled_skills", [])
    disabled_ids = skills_state.get("disabled_skills", [])
    pending_ids = skills_state.get("pending_audit", [])

    print()
    if is_zh:
        print(f"  skills/_vendor/ 中的技能: {len(installed_ids)}")
    else:
        print(f"  Skills in skills/_vendor/: {len(installed_ids)}")
    print()

    if installed_ids:
        if is_zh:
            print(f"  {'技能 ID':<35s} {'风险':<10s} {'状态':<15s} {'来源'}")
        else:
            print(f"  {'Skill ID':<35s} {'Risk':<10s} {'Status':<15s} {'Source'}")
        print(f"  {'-'*35} {'-'*10} {'-'*15} {'-'*20}")
        for sid in sorted(installed_ids):
            entry = catalog_map.get(sid, {})
            risk = entry.get("risk_level", "unknown")
            src = entry.get("source_type", "unknown").replace("_", " ")

            if sid in enabled_ids:
                status = "[ENABLED]" if not is_zh else "[已启用]"
            elif sid in disabled_ids:
                status = "[DISABLED]" if not is_zh else "[已停用]"
            elif sid in pending_ids:
                status = "[PENDING AUDIT]" if not is_zh else "[待审计]"
            else:
                status = "[INSTALLED]" if not is_zh else "[已安装]"

            print(f"  {sid:<35s} {risk:<10s} {status:<15s} {src}")
        print()

    # Available adapters
    adapter_dir = target / ADAPTER_DIR_REL
    if adapter_dir.is_dir():
        adapters = [f.name for f in adapter_dir.iterdir() if f.is_file() and f.suffix == ".md"]
        enabled_adapters = skills_state.get("enabled_adapters", [])
        if is_zh:
            print(f"  适配器: {len(adapters)} 可用, {len(enabled_adapters)} 已启用")
        else:
            print(f"  Adapters: {len(adapters)} available, {len(enabled_adapters)} enabled")
        if adapters:
            for a in sorted(adapters):
                tag = " [ENABLED]" if a in enabled_adapters else ""
                if is_zh:
                    tag = " [已启用]" if a in enabled_adapters else ""
                print(f"    {a}{tag}")
        print()

    # Available profiles summary
    if is_zh:
        print(f"  可用配置预设 (使用 --install-profile <名称>):")
    else:
        print(f"  Available profiles (use --install-profile <name>):")
    print()
    for pid in ALLOWED_PROFILES:
        pdef = profiles.get("profiles", {}).get(pid, {})
        count = len(pdef.get("skills", []))
        desc = pdef.get("description", "")
        if is_zh:
            pd_zh = PROFILE_DESCRIPTIONS_ZH.get(pid, {})
            desc = pd_zh.get("tagline", desc)
        installed_tag = ""
        if pid in installed_profiles:
            installed_tag = " [INSTALLED]" if not is_zh else " [已安装]"
        print(f"    {pid:<12s} {count:>2d} skills  {desc[:80]}{installed_tag}")
    print()

    print_separator()
    if is_zh:
        print(f"  目录版本: {catalog.get('version', '?')}  |  PKB 技能配置版本: {skills_state.get('catalog_version', '?')}")
        print(f"  运行 --list 查看全部 43 个目录条目及说明。")
        print(f"  运行 --describe <id> 查看技能完整详情。")
    else:
        print(f"  Catalog version: {catalog.get('version', '?')}  |  PKB skills config version: {skills_state.get('catalog_version', '?')}")
        print(f"  Run --list to see all 43 catalog entries with descriptions.")
        print(f"  Run --describe <id> to see full details for a skill.")
    print()


# -- List Catalog ------------------------------------------------------------

def cmd_list(catalog: dict, target: Path):
    """List the full skill catalog with descriptions."""
    skills = catalog.get("skills", [])
    pkb_config = load_pkb_config(target)
    installed_ids = set(pkb_config.get("skills", {}).get("installed_skills", []))
    enabled_ids = set(pkb_config.get("skills", {}).get("enabled_skills", []))
    is_zh = detect_language(target) in ("zh-CN", "bilingual")

    title = "PKB Skill Catalog -- {} entries (v{})".format(len(skills), catalog.get("version", "?"))
    if is_zh:
        title = f"PKB 技能目录 -- {len(skills)} 个条目 (v{catalog.get('version', '?')})"
    print_header(title)

    categories = {}
    for s in skills:
        cat = s.get("category", "other")
        categories.setdefault(cat, []).append(s)

    for cat_key in sorted(categories.keys()):
        cat_label = get_category_label(cat_key, target)
        print()
        print(f"  [{cat_label}]")
        print()

        for s in sorted(categories[cat_key], key=lambda x: x["id"]):
            risk_sym = get_risk_symbol(s.get('risk_level', ''), target)
            src = s.get("source_type", "?").replace("_", " ")
            mcp = " [MCP]" if s.get("requires_mcp") else ""
            api = " [API]" if s.get("requires_api_key") else ""
            installed = " [已安装]" if s["id"] in installed_ids and is_zh else " [INSTALLED]" if s["id"] in installed_ids else ""
            enabled = " [已启用]" if s["id"] in enabled_ids and is_zh else " [ENABLED]" if s["id"] in enabled_ids else ""

            # Use Chinese description if available
            desc = get_field_zh(s, "short_description", "short_description_zh")
            if not desc:
                desc = s.get("description", "")

            print(f"  {s['id']:<35s} {risk_sym:<8s} {src}{mcp}{api}{installed}{enabled}")
            print(f"    {desc}")
            sub = s.get("sub_skills", [])
            sub_label = "Sub-skills" if not is_zh else "子技能"
            if sub:
                print(f"    {sub_label} ({len(sub)}): {', '.join(sub[:8])}{' ...' if len(sub) > 8 else ''}")
            print()

    print_separator()
    print()
    if is_zh:
        print("  风险说明:")
        print("    [低风险] = 可安全自动安装，无外部依赖")
        print("    [中风险] = 安装时有警告（依赖、token 或 API）")
        print("    [高风险] = 需要确认（MCP、外部运行时、登录）")
        print("    [参考]   = 仅供参考，不可安装")
        print()
        print("  使用 --describe <skill-id> 查看技能详情。")
        print("  使用 --install-profile <profile> 安装预设技能组。")
    else:
        print("  Risk legend:")
        print("    [LOW]     = auto-install safe, no external dependencies")
        print("    [MEDIUM]  = install with warnings (deps, tokens, or API)")
        print("    [HIGH]    = requires confirmation (MCP, external runtime, login)")
        print("    [REF]     = reference only, never installable")
        print()
        print("  Use --describe <skill-id> to see full details for any skill.")
        print("  Use --install-profile <profile> to install a preset group.")
    print()


# -- Describe Skill ----------------------------------------------------------

def cmd_describe(catalog: dict, skill_id: str, target: Path = None):
    """Show full details for a single skill."""
    catalog_map = {s["id"]: s for s in catalog["skills"]}
    s = catalog_map.get(skill_id)

    if not s:
        if target is not None and detect_language(target) in ("zh-CN", "bilingual"):
            print(f"[FAIL] 未找到技能: {skill_id}")
            print(f"       运行 --list 查看所有可用技能。")
        else:
            print(f"[FAIL] Skill not found: {skill_id}")
            print(f"       Run --list to see all available skills.")
        sys.exit(1)

    is_zh = target is not None and detect_language(target) in ("zh-CN", "bilingual")

    name_display = get_field_zh(s, "name", "name_zh") if is_zh else s['name']
    print_header(f"Skill: {name_display} ({s['id']})" if not is_zh else f"技能: {name_display} ({s['id']})")

    # Identity
    print(f"  ID:              {s['id']}")
    if s.get("name_zh") and is_zh:
        print(f"  Name (EN):       {s['name']}")
        print(f"  Name (ZH):       {s['name_zh']}")
    else:
        print(f"  Name:            {s['name']}")
    print(f"  Category:        {get_category_label(s.get('category', ''), target) if target else CATEGORY_LABELS.get(s.get('category', ''), s.get('category', ''))}")
    print()

    # Description
    section_what = "[What it does]" if not is_zh else "[功能说明]"
    print(f"  {section_what}")
    short_desc = get_field_zh(s, "short_description", "short_description_zh") if is_zh else s.get('short_description', 'No description.')
    if not short_desc:
        short_desc = s.get("short_description", "No description.")
    print(f"  {short_desc}")
    print()
    section_detail = "[Details]" if not is_zh else "[详细说明]"
    print(f"  {section_detail}")
    long_desc = get_field_zh(s, "long_description", "long_description_zh") if is_zh else s.get('long_description', s.get('description', ''))
    if not long_desc:
        long_desc = s.get("long_description", s.get("description", ""))
    for line in textwrap.wrap(long_desc, width=68):
        print(f"  {line}")
    print()

    # Best for / Not for
    best = get_field_zh(s, "best_for", "best_for_zh") if is_zh else s.get("best_for", [])
    if not best:
        best = s.get("best_for", [])
    if best:
        section_best = "[Best for]" if not is_zh else "[适用场景]"
        print(f"  {section_best}")
        for b in best:
            print(f"    - {b}")
        print()

    not_for = get_field_zh(s, "not_for", "not_for_zh") if is_zh else s.get("not_for", [])
    if not not_for:
        not_for = s.get("not_for", [])
    if not_for:
        section_not = "[Not for]" if not is_zh else "[不适用场景]"
        print(f"  {section_not}")
        for n in not_for:
            print(f"    - {n}")
        print()

    # Risk
    risk = s.get("risk_level", "unknown")
    section_risk = "[Risk]" if not is_zh else "[风险]"
    print(f"  {section_risk}")
    print(f"  Level:          {risk.upper()}")
    risk_exp = get_field_zh(s, "risk_explanation", "risk_explanation_zh") if is_zh else s.get('risk_explanation', 'No explanation provided.')
    if not risk_exp:
        risk_exp = s.get("risk_explanation", "No explanation provided.")
    label_exp = "Explanation:" if not is_zh else "说明:"
    print(f"  {label_exp}    {risk_exp}")
    print()

    # Requirements
    section_req = "[Requirements]" if not is_zh else "[环境要求]"
    print(f"  {section_req}")
    label_api = "API key needed:" if not is_zh else "需要 API key:"
    label_mcp = "MCP server needed:" if not is_zh else "需要 MCP 服务器:"
    label_ext = "External runtime:" if not is_zh else "需要外部运行时:"
    yn_yes = "Yes" if not is_zh else "是"
    yn_no = "No" if not is_zh else "否"
    print(f"  {label_api:<22s} {yn_yes if s.get('requires_api_key') else yn_no}")
    print(f"  {label_mcp:<22s} {yn_yes if s.get('requires_mcp') else yn_no}")
    print(f"  {label_ext:<22s} {yn_yes if s.get('requires_external_runtime') else yn_no}")
    print()

    # Installation
    section_inst = "[Installation]" if not is_zh else "[安装信息]"
    print(f"  {section_inst}")
    label_src = "Source type:" if not is_zh else "来源类型:"
    label_method = "Install method:" if not is_zh else "安装方式:"
    label_repo = "Repository:" if not is_zh else "仓库地址:"
    label_lic = "License:" if not is_zh else "许可证:"
    print(f"  {label_src:<16s} {s.get('source_type', 'unknown')}")
    print(f"  {label_method:<16s} {s.get('install_method', 'unknown')}")
    if s.get("repo_url"):
        print(f"  {label_repo:<16s} {s['repo_url']}")
    print(f"  {label_lic:<16s} {s.get('license_status', 'unknown')}")
    print()

    # Adapter
    adapter = s.get("adapter")
    if adapter:
        section_adapter = "[Adapter]" if not is_zh else "[适配器]"
        print(f"  {section_adapter}")
        print(f"  Adapter file:    {adapter}")
        print(f"  Installed to:    templates/skill_adapters/{adapter}")
        print()

    # Profiles
    profiles_list = s.get("recommended_profiles", [])
    if profiles_list:
        section_prof = "[Recommended profiles]" if not is_zh else "[推荐配置预设]"
        print(f"  {section_prof}")
        print(f"  {', '.join(profiles_list)}")
        print()

    # Sub-skills
    sub = s.get("sub_skills", [])
    if sub:
        section_sub = "[Sub-skills]" if not is_zh else "[子技能]"
        print(f"  {section_sub} ({len(sub)})")
        for sk in sub:
            print(f"    - {sk}")
        print()

    # Default enabled
    section_def = "[Default]" if not is_zh else "[默认状态]"
    print(f"  {section_def}")
    label_en = "Enabled by default:" if not is_zh else "默认启用:"
    yn_yes2 = "Yes" if not is_zh else "是"
    yn_no2 = "No" if not is_zh else "否"
    print(f"  {label_en} {yn_yes2 if s.get('default_enabled') else yn_no2}")
    print()

    # Notes
    notes = s.get("notes", "")
    if notes:
        section_notes = "[Additional notes]" if not is_zh else "[补充说明]"
        print(f"  {section_notes}")
        for line in textwrap.wrap(notes, width=68):
            print(f"  {line}")
        print()

    print_separator()
    print()

    # Install hint
    installable = s.get("install_method") not in ("reference_only",)
    if installable:
        if is_zh:
            print(f"  安装命令: python scripts/skill_manager.py --target . --install {skill_id}")
        else:
            print(f"  To install: python scripts/skill_manager.py --target . --install {skill_id}")
    else:
        if is_zh:
            print(f"  [仅供参考] 此技能不可安装。")
        else:
            print(f"  [REFERENCE ONLY] This skill cannot be installed.")
    print()


# -- Install Single Skill ----------------------------------------------------

def cmd_install(target: Path, catalog: dict, skill_id: str, dry_run: bool = False,
                enable_risky: bool = False, yes: bool = False):
    """Install a single skill."""
    catalog_map = {s["id"]: s for s in catalog["skills"]}
    entry = catalog_map.get(skill_id)
    is_zh = detect_language(target) in ("zh-CN", "bilingual")

    if not entry:
        if is_zh:
            print(f"[FAIL] 未找到技能: {skill_id}")
        else:
            print(f"[FAIL] Skill not found: {skill_id}")
        sys.exit(1)

    method = entry.get("install_method", "git_clone")

    # Check installability
    if method == "reference_only":
        if is_zh:
            print(f"[阻止] {skill_id} 仅供参考，不可安装。")
            print(f"       {entry.get('risk_explanation', '')}")
        else:
            print(f"[BLOCKED] {skill_id} is reference-only. Never installed.")
            print(f"         {entry.get('risk_explanation', '')}")
        sys.exit(1)

    if method == "plugin_marketplace":
        if is_zh:
            print(f"[需手动] {skill_id} 是 Claude Code 插件市场技能。")
            print(f"         安装方式: /plugin marketplace add {entry.get('repo_url', '?')}")
            print(f"         然后: /plugin install {skill_id}")
        else:
            print(f"[MANUAL] {skill_id} is a Claude Code plugin marketplace skill.")
            print(f"         Install via: /plugin marketplace add {entry.get('repo_url', '?')}")
            print(f"         Then: /plugin install {skill_id}")
        return

    if method == "mcp_config":
        if is_zh:
            print(f"[需手动] {skill_id} 需要 MCP 服务器配置。")
            print(f"         请在 .claude/mcp.json 中手动配置。")
            print(f"         PKB 绝不自动配置 MCP 服务器。")
        else:
            print(f"[MANUAL] {skill_id} requires MCP server configuration.")
            print(f"         Configure in .claude/mcp.json manually.")
            print(f"         PKB never auto-configures MCP servers.")
        return

    if method == "requires_z_skills_vendor_clone":
        if is_zh:
            print(f"[阻止] {skill_id} 需要先安装 z-skills。")
            print(f"       运行: python scripts/skill_manager.py --target . --install z-skills")
            print(f"       然后审计 z-skills，再启用 {skill_id}。")
        else:
            print(f"[BLOCKED] {skill_id} requires z-skills to be installed first.")
            print(f"         Run: python scripts/skill_manager.py --target . --install z-skills")
            print(f"         Then audit z-skills, then enable {skill_id}.")
        sys.exit(1)

    # Special handling for z-skills
    if skill_id == "z-skills":
        return _cmd_install_z_skills(target, entry, dry_run, enable_risky, yes)

    # Risk check
    risk = entry.get("risk_level", "medium")
    if risk == "high" and not enable_risky:
        if is_zh:
            print(f"[阻止] {skill_id} 为高风险。使用 --enable-risky 安装。")
            print(f"       {entry.get('risk_explanation', '')}")
        else:
            print(f"[BLOCKED] {skill_id} is HIGH RISK. Use --enable-risky to install.")
            print(f"         {entry.get('risk_explanation', '')}")
        sys.exit(1)

    # Show what will be installed
    print()
    name_disp = get_field_zh(entry, "name", "name_zh") if is_zh else entry['name']
    cat_disp = get_category_label(entry.get('category', ''), target)
    skill_label = "Skill" if not is_zh else "技能"
    cat_label = "Category" if not is_zh else "分类"
    risk_label = "Risk" if not is_zh else "风险"
    print(f"  {skill_label}: {name_disp} ({entry['id']})")
    print(f"  {cat_label}: {cat_disp}")
    print(f"  {risk_label}: {risk.upper()}")
    short_d = get_field_zh(entry, "short_description", "short_description_zh") if is_zh else entry.get('short_description', '')
    if not short_d:
        short_d = entry.get('short_description', '')
    print(f"  {short_d}")
    print()

    if risk == "high":
        risk_exp_d = get_field_zh(entry, "risk_explanation", "risk_explanation_zh") if is_zh else entry.get('risk_explanation', '')
        if not risk_exp_d:
            risk_exp_d = entry.get('risk_explanation', '')
        if is_zh:
            print(f"  [!] 高风险: {risk_exp_d}")
        else:
            print(f"  [!] HIGH RISK: {entry.get('risk_explanation', '')}")
        print()

    warn_label = "WARN" if not is_zh else "警告"
    if entry.get("requires_mcp"):
        print(f"  [{warn_label}] {zh_label('需要 MCP 服务器 -- 必须手动配置', 'Requires MCP server -- must be configured manually', target)}")
    if entry.get("requires_external_runtime"):
        print(f"  [{warn_label}] {zh_label('需要外部运行时 -- 必须单独安装', 'Requires external runtime -- must be installed separately', target)}")
    if entry.get("requires_api_key"):
        print(f"  [{warn_label}] {zh_label('需要 API key -- 请自行配置，切勿存入 PKB', 'Requires API key -- configure yourself, never store in PKB', target)}")
    if entry.get("license_status", "").startswith("NO LICENSE"):
        print(f"  [{warn_label}] {entry['license_status']}")

    if any([entry.get("requires_mcp"), entry.get("requires_external_runtime"),
            entry.get("requires_api_key")]):
        print()

    # Confirm unless --yes
    if not yes and not dry_run:
        install_to = f"{target / VENDOR_DIR_REL / skill_id}/"
        print(f"  {zh_label('安装到:', 'Install to:', target)} {install_to}")
        print()
        prompt = "  确认安装? [y/N]: " if is_zh else "  Proceed with installation? [y/N]: "
        response = input(prompt).strip().lower()
        if response not in ("y", "yes"):
            print(f"  {zh_label('已取消。', 'Cancelled.', target)}")
            return

    # Execute installation
    if dry_run:
        dr_label = "DRY RUN" if not is_zh else "预览模式"
        print(f"  [{dr_label}] {zh_label(f'将安装: {skill_id}', f'Would install: {skill_id}', target)}")
        _simulate_install(entry, target, dry_run=True)
        return

    installing_label = f"Installing {skill_id}..." if not is_zh else f"正在安装 {skill_id}..."
    print(f"  {installing_label}")
    result = _do_install_skill(entry, target)

    if result["status"] == "installed":
        if is_zh:
            print(f"  [OK] 已安装到 {result['vendor_path']}")
        else:
            print(f"  [OK] Installed to {result['vendor_path']}")

        # Copy adapter
        if entry.get("adapter"):
            copied = _copy_adapter(entry, target)
            if copied:
                print(f"  [OK] {zh_label('适配器:', 'Adapter:', target)} {entry['adapter']} -> {ADAPTER_DIR_REL}/")

        # Update config
        _update_pkb_config_for_install(target, entry)
        _update_skill_links_for_install(target, entry)
        print(f"  [OK] {zh_label('配置已更新: pkb.config.json, SKILL_LINKS.md', 'Config updated: pkb.config.json, SKILL_LINKS.md', target)}")

        # Add to pending audit
        _mark_pending_audit(target, entry["id"])

        print()
        if is_zh:
            print(f"  后续步骤:")
            print(f"    1. 在 {VENDOR_DIR_REL}/{skill_id}/ 中查看技能的 LICENSE")
            print(f"    2. 运行 --audit 验证安装")
            print(f"    3. 运行 --enable {skill_id} 激活适配器")
            print(f"    4. 重启 Claude Code 加载新技能")
        else:
            print(f"  Next steps:")
            print(f"    1. Review the skill's LICENSE in {VENDOR_DIR_REL}/{skill_id}/")
            print(f"    2. Run --audit to verify installation")
            print(f"    3. Run --enable {skill_id} to activate the adapter")
            print(f"    4. Restart Claude Code to load new skills")
    else:
        print(f"  [FAIL] {result.get('error', 'unknown error')}")


def _cmd_install_z_skills(target: Path, entry: dict, dry_run: bool,
                          enable_risky: bool, yes: bool):
    """Special installation flow for z-skills with explicit warnings."""
    is_zh = detect_language(target) in ("zh-CN", "bilingual")
    print()
    print("=" * 72)
    if is_zh:
        print("  [!] Z-Skills -- 第三方本地安装")
        print("=" * 72)
        print()
        print("  重要 -- 请仔细阅读:")
        print()
        print("  1. PKB Starter 不二次分发 z-skills 代码。")
        print("     本次安装直接从以下地址克隆:")
        print(f"     {entry.get('repo_url', 'https://github.com/tjxj/z-skills')}")
        print()
        print("  2. z-skills 是第三方仓库。每个子目录可能有各自的")
        print("     许可条款。使用前必须审计。")
        print()
        print("  3. 安装后，z-skills 将位于:")
        print(f"     skills/_vendor/z-skills/")
        print("     状态: pending_audit (不自动启用)")
        print()
        print("  4. 你必须明确运行 --audit 和 --enable 之后，任何")
        print("     z-skills 代码才能通过 PKB 适配器被调用。")
        print()
        print("  5. PKB 绝不自动执行 z-skills 脚本。")
        print("     适配器仅将 z-web-pack 输出路由到 raw/webpacks/。")
        print()
        print("  6. 你有责任遵守仓库的许可条款。如果未找到许可证，")
        print("     视为'保留所有权利' -- 仅供个人参考。")
        print()
    else:
        print("  [!] Z-Skills -- Third-Party Local Installation")
        print("=" * 72)
        print()
        print("  IMPORTANT -- Please read carefully:")
        print()
        print("  1. PKB Starter does NOT redistribute z-skills code.")
        print("     This installation clones directly from:")
        print(f"     {entry.get('repo_url', 'https://github.com/tjxj/z-skills')}")
        print()
        print("  2. z-skills is a third-party repository. Each sub-directory")
        print("     may have its own license terms. You must audit before use.")
        print()
        print("  3. After installation, z-skills will be in:")
        print(f"     skills/_vendor/z-skills/")
        print("     Status: pending_audit (NOT auto-enabled)")
        print()
        print("  4. You must explicitly run --audit and --enable before any")
        print("     z-skills code can be invoked through the PKB adapter.")
        print()
        print("  5. PKB never auto-executes z-skills scripts.")
        print("     The adapter only routes z-web-pack output to raw/webpacks/.")
        print()
        print("  6. You are responsible for complying with the repository's")
        print("     license terms. If no license is found, treat as")
        print("     'all rights reserved' -- personal reference only.")
        print()

    if dry_run:
        if is_zh:
            print("  [预览模式] 将 git clone 到: skills/_vendor/z-skills/")
            print("  [预览模式] 状态将为: pending_audit")
            print("  [预览模式] 适配器: z_skills_adapter.md")
        else:
            print("  [DRY RUN] Would git clone into: skills/_vendor/z-skills/")
            print("  [DRY RUN] Status would be: pending_audit")
            print("  [DRY RUN] Adapter: z_skills_adapter.md")
        print()
        _simulate_install(entry, target, dry_run=True)
        return

    # Confirmation
    if not yes:
        prompt = "  输入 'INSTALL' 确认你理解并同意: " if is_zh else "  Type 'INSTALL' to confirm you understand and consent: "
        response = input(prompt).strip()
        if response != "INSTALL":
            print(f"  {zh_label('已取消。z-skills 未安装。', 'Cancelled. z-skills was not installed.', target)}")
            return

    print()
    print(f"  {zh_label('正在克隆 z-skills 到 skills/_vendor/z-skills/...', 'Cloning z-skills into skills/_vendor/z-skills/...', target)}")
    result = _do_install_skill(entry, target)

    if result["status"] == "installed":
        if is_zh:
            print(f"  [OK] z-skills 已安装到 {result['vendor_path']}")
        else:
            print(f"  [OK] z-skills installed to {result['vendor_path']}")

        # Copy adapter
        if entry.get("adapter"):
            copied = _copy_adapter(entry, target)
            if copied:
                print(f"  [OK] {zh_label('适配器:', 'Adapter:', target)} {entry['adapter']} -> {ADAPTER_DIR_REL}/")

        # Update config (pending_audit, NOT enabled)
        _update_pkb_config_for_install(target, entry)
        _update_skill_links_for_install(target, entry)
        _mark_pending_audit(target, entry["id"])
        if is_zh:
            print(f"  [OK] 配置已更新。状态: pending_audit")
        else:
            print(f"  [OK] Config updated. Status: pending_audit")

        print()
        if is_zh:
            print(f"  后续步骤:")
            print(f"    1. 运行 --audit 检查 LICENSE 和结构")
            print(f"       python scripts/skill_manager.py --target . --audit")
            print(f"    2. 查看审计报告: zskill_audit_report.md")
            print(f"    3. 运行 --enable z-web-pack-local 激活适配器")
            print(f"    4. 适配器随后将 z-web-pack 输出连接到 raw/webpacks/")
        else:
            print(f"  Next steps:")
            print(f"    1. Run --audit to check LICENSE and structure")
            print(f"       python scripts/skill_manager.py --target . --audit")
            print(f"    2. Review the audit report: zskill_audit_report.md")
            print(f"    3. Run --enable z-web-pack-local to activate the adapter")
            print(f"    4. The adapter then connects z-web-pack output to raw/webpacks/")
    else:
        print(f"  [FAIL] {result.get('error', 'unknown error')}")


def _do_install_skill(entry: dict, target: Path) -> dict:
    """Execute git clone for a skill. Returns result dict."""
    skill_id = entry["id"]
    repo_url = entry.get("repo_url")
    vendor_dir = target / VENDOR_DIR_REL / skill_id

    vendor_dir.parent.mkdir(parents=True, exist_ok=True)

    if vendor_dir.exists():
        shutil.rmtree(vendor_dir, ignore_errors=True)

    try:
        proc = subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", repo_url, str(vendor_dir)],
            capture_output=True, text=True, timeout=180,
            encoding="utf-8", errors="replace",
        )
        if proc.returncode == 0:
            return {"status": "installed", "vendor_path": str(vendor_dir.relative_to(target)), "id": skill_id}
        else:
            return {"status": "failed", "error": proc.stderr.strip()[:500], "id": skill_id}
    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": "Clone timed out (180s)", "id": skill_id}
    except FileNotFoundError:
        return {"status": "failed", "error": "git not found in PATH", "id": skill_id}
    except Exception as e:
        return {"status": "failed", "error": str(e)[:500], "id": skill_id}


def _simulate_install(entry: dict, target: Path, dry_run: bool = True):
    """Simulate installation -- print what would happen."""
    is_zh = detect_language(target) in ("zh-CN", "bilingual")
    vendor_path = target / VENDOR_DIR_REL / entry["id"]
    print(f"    {zh_label('Vendor 路径:', 'Vendor path:', target)}    {vendor_path}")
    print(f"    {zh_label('仓库:', 'Repo:', target)}           {entry.get('repo_url', 'N/A')}")
    print(f"    {zh_label('方式:', 'Method:', target)}         {entry.get('install_method', 'git_clone')}")
    if entry.get("adapter"):
        print(f"    {zh_label('适配器:', 'Adapter:', target)}        {entry['adapter']} -> {ADAPTER_DIR_REL}/")
    if entry.get("requires_mcp"):
        print(f"    [{zh_label('警告', 'WARN', target)}] {zh_label('需要 MCP 配置 (手动)', 'MCP configuration needed (manual)', target)}")
    if entry.get("requires_external_runtime"):
        print(f"    [{zh_label('警告', 'WARN', target)}] {zh_label('需要外部运行时 (手动安装)', 'External runtime needed (manual install)', target)}")
    if entry.get("requires_api_key"):
        print(f"    [{zh_label('警告', 'WARN', target)}] {zh_label('需要 API key (手动配置)', 'API key needed (manual configuration)', target)}")
    print(f"    {zh_label('许可证:', 'License:', target)}        {entry.get('license_status', 'unknown')}")
    print()


# -- Install Profile ---------------------------------------------------------

def cmd_install_profile(target: Path, catalog: dict, profiles: dict, profile: str,
                        dry_run: bool = False, enable_risky: bool = False, yes: bool = False):
    """Install all skills from a profile."""
    is_zh = detect_language(target) in ("zh-CN", "bilingual")

    if profile not in profiles.get("profiles", {}):
        if is_zh:
            print(f"[FAIL] 未知配置预设: {profile}")
            print(f"       可用: {', '.join(profiles['profiles'].keys())}")
        else:
            print(f"[FAIL] Unknown profile: {profile}")
            print(f"       Available: {', '.join(profiles['profiles'].keys())}")
        sys.exit(1)

    profile_def = profiles["profiles"][profile]
    skill_ids = profile_def.get("skills", [])
    profile_desc = profile_def.get("description", "")
    pd_local = get_profile_desc(profile, target)
    if pd_local.get("desc"):
        profile_desc = pd_local["desc"]

    if profile == "custom":
        skill_ids = _interactive_select(catalog, target)
        if not skill_ids:
            if is_zh:
                print("[INFO] 未选择技能。仅使用 PKB core。")
            else:
                print("[INFO] No skills selected. PKB core only.")
            return

    if not skill_ids:
        if is_zh:
            print(f"[INFO] 配置预设 '{profile}' 没有额外技能。")
            print(f"       {profile_desc}")
            print(f"       PKB 核心工具始终可用。")
        else:
            print(f"[INFO] Profile '{profile}' has no additional skills.")
            print(f"       {profile_desc}")
            print(f"       PKB core tools are always available.")
        return

    catalog_map = {s["id"]: s for s in catalog["skills"]}

    # Show profile overview
    title = f"Install Profile: {profile}" if not is_zh else f"安装配置预设: {profile}"
    print_header(title)
    print(f"  {profile_desc}")
    print()
    skills_label = f"{len(skill_ids)} skill(s) in this profile:" if not is_zh else f"此配置预设包含 {len(skill_ids)} 个技能:"
    print(f"  {skills_label}")
    print()

    to_install = []
    skipped = []
    for sid in skill_ids:
        entry = catalog_map.get(sid)
        if not entry:
            skip_msg = f"  [SKIP] {sid} -- not found in catalog" if not is_zh else f"  [跳过] {sid} -- 目录中未找到"
            print(skip_msg)
            skipped.append(sid)
            continue
        method = entry.get("install_method", "")
        risk = entry.get("risk_level", "")

        if method == "reference_only":
            skip_msg = f"  [SKIP] {sid} -- reference only (not installable)" if not is_zh else f"  [跳过] {sid} -- 仅供参考 (不可安装)"
            print(skip_msg)
            skipped.append(sid)
            continue
        if method == "user_approved_clone":
            man_msg = f"  [MANUAL] {sid} -- requires explicit user consent (use --install {sid})" if not is_zh else f"  [需手动] {sid} -- 需要明确用户同意 (使用 --install {sid})"
            print(man_msg)
            skipped.append(sid)
            continue
        if method == "requires_z_skills_vendor_clone":
            man_msg = f"  [MANUAL] {sid} -- requires z-skills first (use --install z-skills)" if not is_zh else f"  [需手动] {sid} -- 需要先安装 z-skills (使用 --install z-skills)"
            print(man_msg)
            skipped.append(sid)
            continue
        if risk == "high" and not enable_risky:
            skip_msg = f"  [SKIP] {sid} -- HIGH RISK (use --enable-risky)" if not is_zh else f"  [跳过] {sid} -- 高风险 (使用 --enable-risky)"
            print(skip_msg)
            skipped.append(sid)
            continue
        if method == "plugin_marketplace":
            man_msg = f"  [MANUAL] {sid} -- plugin marketplace (install via Claude Code)" if not is_zh else f"  [需手动] {sid} -- 插件市场 (通过 Claude Code 安装)"
            print(man_msg)
            skipped.append(sid)
            continue
        if method == "mcp_config":
            man_msg = f"  [MANUAL] {sid} -- MCP server (configure manually)" if not is_zh else f"  [需手动] {sid} -- MCP 服务器 (手动配置)"
            print(man_msg)
            skipped.append(sid)
            continue

        mcp = " [MCP]" if entry.get("requires_mcp") else ""
        api = " [API]" if entry.get("requires_api_key") else ""
        short_d = get_field_zh(entry, "short_description", "short_description_zh") if is_zh else entry.get('short_description', '')
        if not short_d:
            short_d = entry.get('short_description', '')
        print(f"  [{risk.upper():<7s}] {sid:<35s} {short_d[:60]}{mcp}{api}")
        to_install.append(entry)

    print()
    install_label = f"To install: {len(to_install)}  |  Skipped: {len(skipped)}" if not is_zh else f"将安装: {len(to_install)}  |  已跳过: {len(skipped)}"
    print(f"  {install_label}")
    print()

    if not to_install:
        if is_zh:
            print("[INFO] 此配置预设中没有可自动安装的技能。")
            if skipped:
                print("       跳过的技能可能需要 --enable-risky、手动 MCP 配置、")
                print("       或通过 Claude Code 插件市场安装。")
        else:
            print("[INFO] No auto-installable skills in this profile.")
            if skipped:
                print("       Skipped skills may require --enable-risky, manual MCP config,")
                print("       or Claude Code plugin marketplace installation.")
        return

    if dry_run:
        dr_label = f"[DRY RUN] Would install {len(to_install)} skills:" if not is_zh else f"[预览模式] 将安装 {len(to_install)} 个技能:"
        print(f"  {dr_label}")
        for entry in to_install:
            _simulate_install(entry, target, dry_run=True)
        _print_dry_run_config_summary(target, to_install, profile)
        return

    # Confirm
    if not yes:
        prompt = f"  确认安装 {len(to_install)} 个技能? [y/N]: " if is_zh else f"  Proceed with installation of {len(to_install)} skill(s)? [y/N]: "
        response = input(prompt).strip().lower()
        if response not in ("y", "yes"):
            print(f"  {zh_label('已取消。', 'Cancelled.', target)}")
            return

    # Install each
    print()
    results = []
    for entry in to_install:
        install_msg = f"  Installing: {entry['id']}..." if not is_zh else f"  正在安装: {entry['id']}..."
        print(install_msg)
        result = _do_install_skill(entry, target)
        results.append(result)

        if result["status"] == "installed":
            ok_msg = f"    [OK] -> {result['vendor_path']}" if not is_zh else f"    [OK] -> {result['vendor_path']}"
            print(ok_msg)
            if entry.get("adapter"):
                _copy_adapter(entry, target)
                print(f"    [OK] {zh_label('适配器:', 'Adapter:', target)} {entry['adapter']}")
            _update_pkb_config_for_install(target, entry)
        else:
            fail_msg = f"    [FAIL] {result.get('error', 'unknown')[:120]}" if not is_zh else f"    [失败] {result.get('error', 'unknown')[:120]}"
            print(fail_msg)

    # Final config update
    _update_pkb_config_for_profile(target, profile, results)
    _update_skill_links_for_profile(target, to_install, profile)

    # Report
    succeeded = [r for r in results if r["status"] == "installed"]
    failed = [r for r in results if r["status"] == "failed"]

    print()
    report_title = "Installation Report" if not is_zh else "安装报告"
    print_header(report_title)
    profile_label = "Profile" if not is_zh else "配置预设"
    installed_label = "Installed" if not is_zh else "已安装"
    failed_label = "Failed" if not is_zh else "失败"
    skipped_label = "Skipped" if not is_zh else "已跳过"
    print(f"  {profile_label}:    {profile}")
    print(f"  {installed_label}:  {len(succeeded)}")
    print(f"  {failed_label}:     {len(failed)}")
    print(f"  {skipped_label}:    {len(skipped)}")
    if succeeded:
        path_label = "Path" if not is_zh else "路径"
        next_label = "Next steps" if not is_zh else "后续步骤"
        print(f"  {path_label}:       {VENDOR_DIR_REL}/")
        print()
        print(f"  {next_label}:")
        if is_zh:
            print(f"    1. 运行 --audit 验证安装")
            print(f"    2. 运行 --enable <id> 激活你想使用的技能")
            print(f"    3. 重启 Claude Code 加载新技能")
        else:
            print(f"    1. Run --audit to verify installations")
            print(f"    2. Run --enable <id> for skills you want to activate")
            print(f"    3. Restart Claude Code to load new skills")
    print("=" * 72)


def _print_dry_run_config_summary(target: Path, to_install: list, profile: str):
    """Print what config changes would be made."""
    is_zh = detect_language(target) in ("zh-CN", "bilingual")
    print()
    if is_zh:
        print(f"  [预览模式] 将更新:")
    else:
        print(f"  [DRY RUN] Would update:")
    print(f"    pkb.config.json  -- installed_profiles += [{profile}]")
    print(f"    pkb.config.json  -- installed_skills += [{', '.join(e['id'] for e in to_install)}]")
    print(f"    SKILL_LINKS.md   -- add entries for {len(to_install)} skills")
    for entry in to_install:
        if entry.get("adapter"):
            print(f"    {ADAPTER_DIR_REL}/{entry['adapter']}")
    print()


# -- Audit -------------------------------------------------------------------

def cmd_audit(target: Path, catalog: dict, dry_run: bool = False):
    """Audit installed skills against the catalog."""
    vendor_dir = target / VENDOR_DIR_REL
    catalog_map = {s["id"]: s for s in catalog["skills"]}
    pkb_config = load_pkb_config(target)
    skills_state = pkb_config.get("skills", {})
    is_zh = detect_language(target) in ("zh-CN", "bilingual")

    title = "PKB Skill Audit" if not is_zh else "PKB 技能审计"
    print_header(title)

    if not vendor_dir.is_dir():
        if is_zh:
            print("  未找到 skills/_vendor/ 目录。")
            print("  没有已安装的技能。使用 --install-profile <name> 开始。")
        else:
            print("  No skills/_vendor/ directory found.")
            print("  No skills installed. Use --install-profile <name> to get started.")
        print()
        return

    installed_dirs = [d for d in vendor_dir.iterdir() if d.is_dir()]
    if not installed_dirs:
        if is_zh:
            print("  skills/_vendor/ 为空。")
            print("  没有已安装的技能。使用 --install-profile <name> 开始。")
        else:
            print("  skills/_vendor/ is empty.")
            print("  No skills installed. Use --install-profile <name> to get started.")
        print()
        return

    found_label = f"Found {len(installed_dirs)} installed skill(s):" if not is_zh else f"找到 {len(installed_dirs)} 个已安装技能:"
    print(f"  {found_label}")
    print()

    known = 0
    unknown = 0
    pending = []
    no_license = []
    no_adapter = []
    issues = []

    for d in sorted(installed_dirs):
        skill_id = d.name
        entry = catalog_map.get(skill_id)

        if entry:
            known += 1
            risk = entry.get("risk_level", "unknown")
            lic = entry.get("license_status", "")
            name = entry.get("name", "?")

            print(f"  [{risk.upper():<7s}] {skill_id}  -- {name}")
            repo_label = "Repo" if not is_zh else "仓库"
            lic_label = "License" if not is_zh else "许可证"
            print(f"              {repo_label}: {entry.get('repo_url', 'N/A')}")
            print(f"              {lic_label}: {lic}")
        else:
            unknown += 1
            print(f"  [UNKNOWN ] {skill_id}")
            unknown_msg = f"              NOT in catalog -- may be manually installed" if not is_zh else "              不在目录中 -- 可能是手动安装的"
            print(unknown_msg)
            issues.append(f"{skill_id}: not in catalog")

        # Check .git
        if not (d / ".git").is_dir():
            git_msg = f"{skill_id}: missing .git (not a git clone)" if not is_zh else f"{skill_id}: 缺少 .git (非 git clone)"
            issues.append(git_msg)
            print(f"              [!] .git MISSING (may be copy, not clone)" if not is_zh else f"              [!] .git 缺失 (可能为复制而非克隆)")

        # Check INSTALL_NOTE.md
        install_note_msg_en = "INSTALL_NOTE.md: present" if (d / "INSTALL_NOTE.md").is_file() else "INSTALL_NOTE.md: MISSING"
        install_note_msg_zh = "INSTALL_NOTE.md: 存在" if (d / "INSTALL_NOTE.md").is_file() else "INSTALL_NOTE.md: 缺失"
        print(f"              {install_note_msg_zh if is_zh else install_note_msg_en}")

        # Check license in repo
        if entry and lic.startswith("NO LICENSE"):
            no_license.append(skill_id)

        # Check adapter
        adapter = entry.get("adapter") if entry else None
        if adapter:
            adapter_path = target / ADAPTER_DIR_REL / adapter
            if adapter_path.is_file():
                print(f"              Adapter: {adapter} -- present" if not is_zh else f"              适配器: {adapter} -- 存在")
            else:
                no_adapter.append(skill_id)
                print(f"              Adapter: {adapter} -- MISSING" if not is_zh else f"              适配器: {adapter} -- 缺失")

        # Enabled?
        enabled_ids = skills_state.get("enabled_skills", [])
        disabled_ids = skills_state.get("disabled_skills", [])
        pending_ids = skills_state.get("pending_audit", [])
        if skill_id in enabled_ids:
            print(f"              Status: ENABLED" if not is_zh else f"              状态: 已启用")
        elif skill_id in disabled_ids:
            print(f"              Status: DISABLED" if not is_zh else f"              状态: 已停用")
        elif skill_id in pending_ids:
            print(f"              Status: PENDING AUDIT" if not is_zh else f"              状态: 待审计")
            pending.append(skill_id)
        else:
            print(f"              Status: installed (not yet classified)" if not is_zh else f"              状态: 已安装 (尚未分类)")

        print()

    # Summary
    print_separator()
    summary_label = f"Summary: {known} known, {unknown} unknown -- {known + unknown} total" if not is_zh else f"摘要: {known} 已知, {unknown} 未知 -- 共 {known + unknown}"
    print(f"  {summary_label}")
    print(f"  {zh_label('目录版本:', 'Catalog version:', target)} {catalog.get('version', '?')}")
    print(f"  {zh_label('PKB 技能配置:', 'PKB skills config:', target)} {skills_state.get('catalog_version', '?')}")
    print()

    if no_license:
        if is_zh:
            print(f"  [!] 无 LICENSE 的技能 ({len(no_license)}):")
            for sid in no_license:
                print(f"      {sid}")
            print(f"      视为保留所有权利。仅供个人参考使用。")
        else:
            print(f"  [!] Skills with NO LICENSE ({len(no_license)}):")
            for sid in no_license:
                print(f"      {sid}")
            print(f"      Treat as all rights reserved. Use for personal reference only.")
        print()

    if no_adapter:
        if is_zh:
            print(f"  [!] 缺少适配器的技能 ({len(no_adapter)}):")
            for sid in no_adapter:
                print(f"      {sid}")
            print(f"      重新运行 --install {sid} 以复制适配器。")
        else:
            print(f"  [!] Skills with missing adapters ({len(no_adapter)}):")
            for sid in no_adapter:
                print(f"      {sid}")
            print(f"      Run --install {sid} again to copy the adapter.")
        print()

    if pending:
        if is_zh:
            print(f"  [!] 待审计的技能 ({len(pending)}):")
            for sid in pending:
                print(f"      {sid}")
            print(f"      在 --enable 之前，请审查 LICENSE、代码和适配器。")
        else:
            print(f"  [!] Skills pending audit ({len(pending)}):")
            for sid in pending:
                print(f"      {sid}")
            print(f"      Review LICENSE, code, and adapter before --enable.")
        print()

    if issues:
        issues_label = f"Issues found: {len(issues)}" if not is_zh else f"发现的问题: {len(issues)}"
        print(f"  {issues_label}")
        for i in issues:
            print(f"    - {i}")
        print()

    if not issues and not no_license and not no_adapter and not pending:
        if is_zh:
            print(f"  [OK] 所有已安装技能通过审计。")
        else:
            print(f"  [OK] All installed skills pass audit.")
        print()

    print_separator()

    # Generate report file
    if not dry_run:
        report_path = target / "skill_manager_report.md"
        _write_audit_report(report_path, installed_dirs, catalog_map, skills_state,
                           known, unknown, issues, no_license, no_adapter, pending, catalog)
        print(f"  {zh_label('报告:', 'Report:', target)} {report_path}")

    # Z-Skills specific audit (delegates to zskill_bridge.py if z-skills is installed)
    _audit_z_skills_if_present(target, dry_run)


def _audit_z_skills_if_present(target: Path, dry_run: bool):
    """Run zskill_bridge.py audit if z-skills is installed."""
    is_zh = detect_language(target) in ("zh-CN", "bilingual")
    z_skills_path = target / VENDOR_DIR_REL / "z-skills"
    if not z_skills_path.is_dir():
        return

    bridge_script = target / "tools" / "zskill_bridge.py"
    if not bridge_script.is_file():
        # Bridge script might not be in target PKB yet; check pkb-starter
        bridge_script = STARTER_DIR / "template" / "tools" / "zskill_bridge.py"

    if not bridge_script.is_file():
        print()
        if is_zh:
            print("  [INFO] z-skills 已安装但未找到 zskill_bridge.py。")
            print("         请从 pkb-starter/template/tools/zskill_bridge.py 复制。")
        else:
            print("  [INFO] z-skills installed but zskill_bridge.py not found.")
            print("         Copy it from pkb-starter/template/tools/zskill_bridge.py")
        return

    print()
    z_audit_label = "--- Z-Skills Audit (via zskill_bridge.py) ---" if not is_zh else "--- Z-Skills 审计 (通过 zskill_bridge.py) ---"
    print(f"  {z_audit_label}")
    print()

    if dry_run:
        dr_label = f"[DRY RUN] Would run: python {bridge_script} audit" if not is_zh else f"[预览模式] 将运行: python {bridge_script} audit"
        print(f"  {dr_label}")
        return

    try:
        proc = subprocess.run(
            [sys.executable, str(bridge_script), "audit"],
            capture_output=True, text=True, timeout=30,
            encoding="utf-8", errors="replace",
            cwd=str(target),
        )
        print(proc.stdout)
        if proc.stderr.strip():
            print(proc.stderr)
    except subprocess.TimeoutExpired:
        print(f"  {zh_label('[WARN] z-skills 审计超时', '[WARN] z-skills audit timed out', target)}")
    except Exception as e:
        print(f"  {zh_label(f'[WARN] z-skills 审计失败: {e}', f'[WARN] z-skills audit failed: {e}', target)}")



def _write_audit_report(report_path: Path, installed_dirs, catalog_map, skills_state,
                        known, unknown, issues, no_license, no_adapter, pending, catalog):
    """Write skill_manager_report.md."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# PKB Skill Manager Report",
        "",
        f"> Generated: {today}",
        f"> Catalog version: {catalog.get('version', '?')}",
        "",
        "## Summary",
        "",
        f"- Installed skills: {len(installed_dirs)}",
        f"- Known (in catalog): {known}",
        f"- Unknown (not in catalog): {unknown}",
        f"- Issues: {len(issues)}",
        f"- No license: {len(no_license)}",
        f"- Missing adapter: {len(no_adapter)}",
        f"- Pending audit: {len(pending)}",
        "",
    ]
    if issues:
        lines.append("## Issues")
        lines.append("")
        for i in issues:
            lines.append(f"- {i}")
        lines.append("")
    if no_license:
        lines.append("## No License")
        lines.append("")
        for sid in no_license:
            lines.append(f"- {sid}")
        lines.append("")
    lines.append("---")
    lines.append(f"*Generated by PKB skill_manager.py v{catalog.get('version', '?')}*")
    lines.append("")
    report_path.write_text("\n".join(lines), encoding="utf-8")


# -- Enable / Disable --------------------------------------------------------

def cmd_enable(target: Path, catalog: dict, skill_id: str):
    """Enable a skill's adapter."""
    catalog_map = {s["id"]: s for s in catalog["skills"]}
    entry = catalog_map.get(skill_id)
    is_zh = detect_language(target) in ("zh-CN", "bilingual")

    # Special check for z-web-pack-local: requires z-skills installed + audited
    if skill_id == "z-web-pack-local":
        z_skills_path = target / VENDOR_DIR_REL / "z-skills"
        if not z_skills_path.is_dir():
            if is_zh:
                print(f"[FAIL] z-web-pack-local 需要先安装 z-skills。")
                print(f"       运行: --install z-skills")
            else:
                print(f"[FAIL] z-web-pack-local requires z-skills to be installed first.")
                print(f"       Run: --install z-skills")
            sys.exit(1)

        audit_report = target / "zskill_audit_report.md"
        if not audit_report.is_file():
            if is_zh:
                print(f"[FAIL] z-skills 尚未审计。")
                print(f"       运行: --audit (包含 z-skills 审计)")
                print(f"       或: python tools/zskill_bridge.py audit")
            else:
                print(f"[FAIL] z-skills has not been audited yet.")
                print(f"       Run: --audit (which includes z-skills audit)")
                print(f"       Or: python tools/zskill_bridge.py audit")
            sys.exit(1)

        print()
        print(f"  z-skills: INSTALLED at {z_skills_path}")
        print(f"  {zh_label('审计报告:', 'Audit report:', target)} {audit_report}")
        print()

    # Verify installed
    vendor_path = target / VENDOR_DIR_REL / skill_id
    if skill_id == "z-web-pack-local":
        # z-web-pack-local is adapter_only, doesn't have its own vendor dir
        pass
    elif not vendor_path.is_dir():
        if is_zh:
            print(f"[FAIL] {skill_id} 未安装在 {VENDOR_DIR_REL}/")
            print(f"       请先运行 --install {skill_id}。")
        else:
            print(f"[FAIL] {skill_id} is not installed in {VENDOR_DIR_REL}/")
            print(f"       Run --install {skill_id} first.")
        sys.exit(1)

    config = load_pkb_config(target)
    skills_state = config.setdefault("skills", {})

    # Move from disabled/pending to enabled
    enabled = set(skills_state.get("enabled_skills", []))
    disabled = set(skills_state.get("disabled_skills", []))
    pending = set(skills_state.get("pending_audit", []))

    disabled.discard(skill_id)
    pending.discard(skill_id)
    enabled.add(skill_id)

    # Enable adapter
    adapter = entry.get("adapter") if entry else None
    if adapter:
        adapter_src = ADAPTERS_SRC / adapter
        adapter_dst = target / ADAPTER_DIR_REL / adapter
        if adapter_src.is_file():
            adapter_dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(adapter_src, adapter_dst)
            enabled_adapters = set(skills_state.get("enabled_adapters", []))
            enabled_adapters.add(adapter)
            skills_state["enabled_adapters"] = list(enabled_adapters)
            print(f"  [OK] {zh_label('适配器已启用:', 'Adapter enabled:', target)} {adapter}")
        else:
            if is_zh:
                print(f"  [WARN] pkb-starter 中未找到适配器: {adapter}")
                print(f"         预期位置: {adapter_src}")
            else:
                print(f"  [WARN] Adapter not found in pkb-starter: {adapter}")
                print(f"         Expected: {adapter_src}")

    skills_state["enabled_skills"] = list(enabled)
    skills_state["disabled_skills"] = list(disabled)
    skills_state["pending_audit"] = list(pending)

    save_pkb_config(target, config)

    if is_zh:
        print(f"  [OK] {skill_id} 现在已启用")
    else:
        print(f"  [OK] {skill_id} is now ENABLED")
    if entry:
        short_d = get_field_zh(entry, "short_description", "short_description_zh") if is_zh else entry.get('short_description', '')
        if not short_d:
            short_d = entry.get('short_description', '')
        print(f"       {short_d}")
    restart_msg = "Restart Claude Code to load the skill." if not is_zh else "重启 Claude Code 以加载此技能。"
    print(f"       {restart_msg}")


def cmd_disable(target: Path, skill_id: str):
    """Disable a skill without deleting its code."""
    is_zh = detect_language(target) in ("zh-CN", "bilingual")

    # Special handling for z-web-pack-local (adapter-only, no vendor dir)
    if skill_id == "z-web-pack-local":
        config = load_pkb_config(target)
        skills_state = config.setdefault("skills", {})

        enabled = set(skills_state.get("enabled_skills", []))
        disabled = set(skills_state.get("disabled_skills", []))
        enabled_adapters = set(skills_state.get("enabled_adapters", []))

        enabled.discard(skill_id)
        disabled.add(skill_id)
        enabled_adapters.discard("z_skills_adapter.md")

        skills_state["enabled_skills"] = list(enabled)
        skills_state["disabled_skills"] = list(disabled)
        skills_state["enabled_adapters"] = list(enabled_adapters)

        save_pkb_config(target, config)

        if is_zh:
            print(f"  [OK] z-web-pack-local 现在已停用")
            print(f"       适配器已停用。z-skills 代码保留在 {VENDOR_DIR_REL}/z-skills/")
            print(f"       运行 --enable z-web-pack-local 重新启用。")
            print(f"       要完全删除 z-skills: 删除 {VENDOR_DIR_REL}/z-skills/")
        else:
            print(f"  [OK] z-web-pack-local is now DISABLED")
            print(f"       Adapter deactivated. z-skills code remains in {VENDOR_DIR_REL}/z-skills/")
            print(f"       Run --enable z-web-pack-local to re-enable.")
            print(f"       To fully remove z-skills: delete {VENDOR_DIR_REL}/z-skills/")
        return

    vendor_path = target / VENDOR_DIR_REL / skill_id
    if not vendor_path.is_dir():
        if is_zh:
            print(f"[FAIL] {skill_id} 未安装。")
        else:
            print(f"[FAIL] {skill_id} is not installed.")
        sys.exit(1)

    config = load_pkb_config(target)
    skills_state = config.setdefault("skills", {})

    enabled = set(skills_state.get("enabled_skills", []))
    disabled = set(skills_state.get("disabled_skills", []))

    enabled.discard(skill_id)
    disabled.add(skill_id)

    skills_state["enabled_skills"] = list(enabled)
    skills_state["disabled_skills"] = list(disabled)

    save_pkb_config(target, config)

    if is_zh:
        print(f"  [OK] {skill_id} 现在已停用")
        print(f"       源代码保留在 {VENDOR_DIR_REL}/{skill_id}/")
        print(f"       运行 --enable {skill_id} 重新启用。")
        print(f"       要完全删除: 删除 {VENDOR_DIR_REL}/{skill_id}/")
    else:
        print(f"  [OK] {skill_id} is now DISABLED")
        print(f"       Source code remains in {VENDOR_DIR_REL}/{skill_id}/")
        print(f"       Run --enable {skill_id} to re-enable.")
        print(f"       To fully remove: delete {VENDOR_DIR_REL}/{skill_id}/")


# -- Show enabled ------------------------------------------------------------

def cmd_enabled(target: Path, catalog: dict):
    """Show enabled skills and adapters."""
    config = load_pkb_config(target)
    skills_state = config.get("skills", {})
    enabled_ids = skills_state.get("enabled_skills", [])
    enabled_adapters = skills_state.get("enabled_adapters", [])
    catalog_map = {s["id"]: s for s in catalog["skills"]}
    is_zh = detect_language(target) in ("zh-CN", "bilingual")

    title = "Enabled Skills & Adapters" if not is_zh else "已启用的技能与适配器"
    print_header(title)

    if not enabled_ids and not enabled_adapters:
        if is_zh:
            print("  当前没有启用任何技能或适配器。")
            print()
            print("  使用 --install-profile <name> 安装技能，")
            print("  然后 --enable <id> 激活它们。")
        else:
            print("  No skills or adapters are currently enabled.")
            print()
            print("  Use --install-profile <name> to install skills,")
            print("  then --enable <id> to activate them.")
        print()
        return

    if enabled_ids:
        if is_zh:
            print(f"  已启用的技能 ({len(enabled_ids)}):")
        else:
            print(f"  Enabled skills ({len(enabled_ids)}):")
        print()
        for sid in sorted(enabled_ids):
            entry = catalog_map.get(sid, {})
            name = get_field_zh(entry, "name", "name_zh") if is_zh else entry.get("name", sid)
            if not name:
                name = sid
            cat = entry.get("category", "?")
            print(f"    {sid:<35s} [{get_category_label(cat, target)}] {name}")
        print()

    if enabled_adapters:
        if is_zh:
            print(f"  已启用的适配器 ({len(enabled_adapters)}):")
        else:
            print(f"  Enabled adapters ({len(enabled_adapters)}):")
        print()
        for a in sorted(enabled_adapters):
            adapter_path = target / ADAPTER_DIR_REL / a
            exists = adapter_path.is_file()
            tag = "present" if exists else "MISSING"
            tag_zh = "存在" if exists else "缺失"
            print(f"    {a:<40s} [{tag_zh if is_zh else tag}]")
        print()

    print_separator()


# -- Update Catalog ----------------------------------------------------------

def cmd_update_catalog(target: Path, catalog: dict, dry_run: bool = False):
    """Update the local skill catalog from pkb-starter source."""
    is_zh = detect_language(target) in ("zh-CN", "bilingual")

    if dry_run:
        dr_label = f"[DRY RUN] Would update catalog from: {CATALOG_PATH}" if not is_zh else f"[预览模式] 将从以下路径更新目录: {CATALOG_PATH}"
        print(f"  {dr_label}")
        return

    config = load_pkb_config(target)
    skills_state = config.setdefault("skills", {})
    old_version = skills_state.get("catalog_version", "?")
    skills_state["catalog_version"] = catalog.get("version", "0.4.0")
    save_pkb_config(target, config)

    if is_zh:
        print(f"  [OK] 本地目录版本已更新: {old_version} -> {catalog.get('version', '?')}")
        print(f"       来源: {CATALOG_PATH}")
    else:
        print(f"  [OK] Local catalog version updated: {old_version} -> {catalog.get('version', '?')}")
        print(f"       Source: {CATALOG_PATH}")


# -- Config Helpers ----------------------------------------------------------

def _copy_adapter(entry: dict, target: Path) -> bool:
    """Copy adapter from pkb-starter to target PKB."""
    adapter_name = entry.get("adapter")
    if not adapter_name:
        return False
    adapter_src = ADAPTERS_SRC / adapter_name
    if not adapter_src.is_file():
        return False
    adapter_dst = target / ADAPTER_DIR_REL / adapter_name
    adapter_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(adapter_src, adapter_dst)
    return True


def _update_pkb_config_for_install(target: Path, entry: dict):
    """Update pkb.config.json for a single skill install."""
    config = load_pkb_config(target)
    skills_state = config.setdefault("skills", {})

    installed = set(skills_state.get("installed_skills", []))
    installed.add(entry["id"])
    skills_state["installed_skills"] = list(installed)

    # Add to vendor_downloads
    downloads = set(skills_state.get("vendor_downloads", []))
    downloads.add(entry["id"])
    skills_state["vendor_downloads"] = list(downloads)

    # Add to pending audit
    pending = set(skills_state.get("pending_audit", []))
    pending.add(entry["id"])
    skills_state["pending_audit"] = list(pending)

    save_pkb_config(target, config)


def _update_pkb_config_for_profile(target: Path, profile: str, results: list):
    """Update pkb.config.json after profile installation."""
    config = load_pkb_config(target)
    skills_state = config.setdefault("skills", {})

    profiles = set(skills_state.get("installed_profiles", []))
    profiles.add(profile)
    skills_state["installed_profiles"] = list(profiles)

    for r in results:
        if r["status"] == "installed":
            installed = set(skills_state.get("installed_skills", []))
            installed.add(r["id"])
            skills_state["installed_skills"] = list(installed)

            downloads = set(skills_state.get("vendor_downloads", []))
            downloads.add(r["id"])
            skills_state["vendor_downloads"] = list(downloads)

            pending = set(skills_state.get("pending_audit", []))
            pending.add(r["id"])
            skills_state["pending_audit"] = list(pending)

    save_pkb_config(target, config)


def _mark_pending_audit(target: Path, skill_id: str):
    """Mark a skill as pending audit."""
    config = load_pkb_config(target)
    skills_state = config.setdefault("skills", {})
    pending = set(skills_state.get("pending_audit", []))
    pending.add(skill_id)
    skills_state["pending_audit"] = list(pending)
    save_pkb_config(target, config)


def _update_skill_links_for_install(target: Path, entry: dict):
    """Update SKILL_LINKS.md for a single skill install."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    links_path = target / "SKILL_LINKS.md"

    new_entry = f"""### {entry['name']}
- ID: `{entry['id']}`
- Category: {entry.get('category', 'unknown')}
- Repository: {entry.get('repo_url', 'N/A')}
- Install method: {entry.get('install_method', 'git_clone')}
- Vendor path: `{VENDOR_DIR_REL}/{entry['id']}/`
- Adapter: `templates/skill_adapters/{entry.get('adapter', 'none')}`
- Risk level: {entry.get('risk_level', 'unknown')}
- License: {entry.get('license_status', 'unknown')}
- Installed: {today}
- Status: pending audit
"""

    if links_path.is_file():
        content = links_path.read_text(encoding="utf-8")
        # Append before the closing marker
        if "---" in content:
            parts = content.rsplit("---", 1)
            content = parts[0].rstrip() + "\n" + new_entry + "\n---" + parts[1]
        else:
            content += "\n" + new_entry
        links_path.write_text(content, encoding="utf-8")
    else:
        header = f"""# SKILL_LINKS.md -- Installed Skill Index

> Auto-generated by PKB Starter skill_manager.py v0.4.0 on {today}.

## Installed Skills

"""
        links_path.write_text(header + new_entry, encoding="utf-8")


def _update_skill_links_for_profile(target: Path, entries: list, profile: str):
    """Update SKILL_LINKS.md after profile install."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    links_path = target / "SKILL_LINKS.md"

    lines = [
        "# SKILL_LINKS.md -- Installed Skill Index",
        "",
        f"> Auto-generated by PKB Starter skill_manager.py v0.4.0 on {today}.",
        f"> Profile: {profile}",
        "",
        "## Installed Skills",
        "",
    ]

    for entry in entries:
        lines.append(f"### {entry['name']}")
        lines.append(f"- ID: `{entry['id']}`")
        lines.append(f"- Category: {entry.get('category', 'unknown')}")
        if entry.get("repo_url"):
            lines.append(f"- Repository: {entry['repo_url']}")
        lines.append(f"- Install method: {entry.get('install_method', 'git_clone')}")
        lines.append(f"- Vendor path: `{VENDOR_DIR_REL}/{entry['id']}/`")
        adapter = entry.get("adapter")
        lines.append(f"- Adapter: `templates/skill_adapters/{adapter}`" if adapter else "- Adapter: none")
        lines.append(f"- Risk level: {entry.get('risk_level', 'unknown')}")
        lines.append(f"- License: {entry.get('license_status', 'unknown')}")
        sub = entry.get("sub_skills", [])
        if sub:
            lines.append(f"- Sub-skills ({len(sub)}): {', '.join(sub)}")
        lines.append(f"- Installed: {today}")
        lines.append("")

    lines.append("---")
    lines.append(f"*Generated by PKB Starter v0.4.0*")
    lines.append("")

    links_path.write_text("\n".join(lines), encoding="utf-8")


# -- Interactive Selection ---------------------------------------------------

def _interactive_select(catalog: dict, target: Path = None) -> list[str]:
    """Interactive skill selection for custom profile."""
    is_zh = target is not None and detect_language(target) in ("zh-CN", "bilingual")
    print()
    print("=" * 60)
    if is_zh:
        print("  自定义配置预设 -- 选择技能")
    else:
        print("  Custom Profile -- Select Skills")
    print("=" * 60)
    print()
    if is_zh:
        print("  输入技能 ID，以空格分隔，或输入 'all' 安装所有安全技能。")
        print("  仅供参考和 plugin_marketplace 技能无法自动安装。")
    else:
        print("  Enter skill IDs separated by spaces, or 'all' for all safe skills.")
        print("  Reference-only and plugin_marketplace skills cannot be auto-installed.")
    print()

    installable = [
        s for s in catalog["skills"]
        if s["install_method"] not in ("reference_only", "plugin_marketplace", "mcp_config")
    ]
    for i, skill in enumerate(installable, 1):
        risk_tag = get_risk_symbol(skill.get("risk_level"), target) if target else RISK_SYMBOLS.get(skill.get("risk_level"), "[?]")
        mcp_tag = " [MCP]" if skill.get("requires_mcp") else ""
        api_tag = " [API]" if skill.get("requires_api_key") else ""
        short_d = get_field_zh(skill, "short_description", "short_description_zh") if is_zh else skill.get("short_description", "")
        if not short_d:
            short_d = skill.get("short_description", "")
        print(f"  {i:2d}. {skill['id']:<32s} {risk_tag:<7s} {short_d[:60]}{mcp_tag}{api_tag}")

    print()
    prompt = "  输入技能 ID (空格分隔，或 'all'): " if is_zh else "  Enter skill IDs (space-separated, or 'all'): "
    choice = input(prompt).strip()

    if choice.lower() == "all":
        return [s["id"] for s in installable if s.get("risk_level") != "high"]

    selected = choice.split()
    valid_ids = {s["id"] for s in installable}
    return [s for s in selected if s in valid_ids]


# -- Main --------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="PKB Starter -- Runtime Skill Manager (v0.4.0)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python skill_manager.py --target "D:\\MyKB" --list
              python skill_manager.py --target "D:\\MyKB" --describe deep-research-skills
              python skill_manager.py --target "D:\\MyKB" --install deep-research-skills
              python skill_manager.py --target "D:\\MyKB" --install-profile student
              python skill_manager.py --target "D:\\MyKB" --audit
              python skill_manager.py --target "D:\\MyKB" --enabled
              python skill_manager.py --target "D:\\MyKB" --enable kanban-skill
              python skill_manager.py --target "D:\\MyKB" --disable kanban-skill
              python skill_manager.py --target "D:\\MyKB" --update-catalog
        """),
    )
    parser.add_argument("--target", required=True,
                        help="Path to PKB target directory")
    parser.add_argument("--list", action="store_true",
                        help="List all skills in the catalog with descriptions")
    parser.add_argument("--describe", default=None,
                        help="Show full details for a skill (by ID)")
    parser.add_argument("--install", default=None,
                        help="Install a single skill (by ID)")
    parser.add_argument("--install-profile", default=None,
                        help="Install all skills from a profile")
    parser.add_argument("--audit", action="store_true",
                        help="Audit installed skills")
    parser.add_argument("--enabled", action="store_true",
                        help="Show enabled skills and adapters")
    parser.add_argument("--enable", default=None,
                        help="Enable a skill's adapter (by ID)")
    parser.add_argument("--disable", default=None,
                        help="Disable a skill without deleting source (by ID)")
    parser.add_argument("--update-catalog", action="store_true",
                        help="Update local skill catalog version")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview actions without making changes")
    parser.add_argument("--enable-risky", action="store_true",
                        help="Allow installation of high-risk skills")
    parser.add_argument("--yes", action="store_true",
                        help="Skip confirmation prompts")

    args = parser.parse_args()

    # Load data sources
    catalog = load_json(CATALOG_PATH)
    profiles = load_json(PROFILES_PATH)
    target = Path(args.target).resolve()

    if not target.is_dir():
        # Try to detect language even when target doesn't exist
        print(f"[FAIL] Target directory does not exist: {target}")
        sys.exit(1)

    # Status (no other flag)
    no_action = not any([args.list, args.describe, args.install, args.install_profile,
                          args.audit, args.enabled, args.enable, args.disable,
                          args.update_catalog])

    if no_action:
        cmd_status(target, catalog, profiles, load_pkb_config(target))
        return

    # Dispatch
    if args.list:
        cmd_list(catalog, target)
    elif args.describe:
        cmd_describe(catalog, args.describe, target)
    elif args.install:
        cmd_install(target, catalog, args.install, args.dry_run, args.enable_risky, args.yes)
    elif args.install_profile:
        cmd_install_profile(target, catalog, profiles, args.install_profile,
                           args.dry_run, args.enable_risky, args.yes)
    elif args.audit:
        cmd_audit(target, catalog, args.dry_run)
    elif args.enabled:
        cmd_enabled(target, catalog)
    elif args.enable:
        cmd_enable(target, catalog, args.enable)
    elif args.disable:
        cmd_disable(target, args.disable)
    elif args.update_catalog:
        cmd_update_catalog(target, catalog, args.dry_run)


if __name__ == "__main__":
    main()
