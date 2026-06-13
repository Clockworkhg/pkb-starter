---
name: document-converter
description: Convert between document formats. DOCX→MD, PDF→MD, MD→DOCX, MD→PDF. Wraps pandoc, markitdown, and LibreOffice. Trigger: /doc, "转换格式", "转为markdown"
user-invocable: true
---

# Document Converter — 文档格式转换

## 用途
在常见文档格式之间转换：DOCX ↔ MD ↔ PDF，支持批量转换。

## 支持格式

| 源格式 | 目标格式 | 工具 |
|--------|---------|------|
| DOCX | MD | Microsoft MarkItDown (Phase 1.5) |
| PDF | MD | Microsoft MarkItDown (Phase 1.5) |
| PPTX | MD | Microsoft MarkItDown (Phase 1.5) |
| XLSX/XLS | MD | Microsoft MarkItDown (Phase 1.5) |
| MD | DOCX | pandoc |
| MD | PDF | pandoc + wkhtmltopdf |
| .doc (旧版) | — | ❌ 不支持 — 请先用 Word/LibreOffice 转为 .docx |

## Phase 1.5 集成状态

**Microsoft MarkItDown 已作为 PKB 本地文档预提取器集成** (`tools/markitdown_convert.py` + `tools/pkb_ingest.py`)。
- 仅 `/pkb --mode full` 启用，其他 mode 行为不变
- 成功时写入缓存文件 `.pkb-cache/extractions/`，CLI 返回 `extracted_path`（不含完整正文）
- 提取失败 → `fallback_required=true` → LLM 直接读取 _INBOX 副本
- 元数据: `extraction_method: markitdown`、`extractor_version` (动态)、`quality_passed`
- Fallback 状态由 LLM 实际执行后记录到 wiki frontmatter
- `.doc` 显式返回 `legacy_doc_unsupported` + `fallback_required=true`
- OCR / OpenAI / Azure / 音频 / YouTube / ZIP **未启用**
- MarkItDown 为可选依赖 (`markitdown[pdf,docx,pptx,xlsx,xls]==0.1.6`)，未安装时自动走 LLM fallback

## 依赖
```bash
# MarkItDown Phase 1 (推荐)
pip install "markitdown[pdf,docx,pptx,xlsx,xls]==0.1.6"

# 备选 / 补充
pip install pypdf pdfplumber python-pptx

# 可选更优方案:
# choco install pandoc    (Windows)
# choco install wkhtmltopdf
```

## Workflow

### Step 1: 确认源文件和目标格式
- 用户指定源文件路径和目标格式
- 自动检测源格式（如未指定）

### Step 2: 选择转换工具
按优先级:
1. **PKB markitdown_convert.py** (Phase 1): 结构化调用，带质量检查和 fallback
2. **markitdown CLI** (Microsoft): DOCX/PPTX/PDF/XLSX/XLS → MD
3. **pandoc** (通用): DOCX ↔ MD, MD → PDF
4. **pypdf + pdfplumber**: PDF → 文本
5. **python-docx / python-pptx**: 精细控制

### Step 3: 执行转换
```bash
# PKB 封装 (推荐)
python tools/markitdown_convert.py <文件路径>
```
- 保留格式: 标题层级、表格、列表、加粗/斜体
- 图片处理: 提取到 assets/ 目录
- 元数据: 保留作者、日期等

### Step 4: 后处理
- 清理转换产物的格式问题
- 添加 PKB frontmatter
- 保存到指定路径

## 与其他 Skill 的关系
- `/add` + `/pkb` → 自动调用 document-converter 处理导入的文档
- `/paper` → 用于提取论文 PDF 的文本内容
- z-excel-editor / z-md-excel → Excel 专用（不走此通用转换器）
