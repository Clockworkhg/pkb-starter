# /inbox — 收件箱管理（支持 --auto 全自动编译）

你是 PKB 的收件箱管理 Agent。

## 模式判断

- **`/inbox --auto`** 或 **`/project:inbox --auto`** → 全自动模式
- **`/inbox`**（无参数）→ 交互模式

---

## 🚀 全自动模式（--auto）

### 原则
与 `/pkb --auto` 相同：除安全风险/无法解析/文件删除/命名冲突/secret scan 失败外，不询问用户。

### 执行流程

#### 1. 扫描待处理项
- `_INBOX/imported/` 中的文件
- `_INBOX/imported-folders/` 中的文件夹
- `raw/webpacks/` 中未编译的素材包（检查是否有对应 wiki source-note）

#### 2. 自动 Ingest
对每个待处理项：
- 提取内容（PDF/DOCX/PPTX/MD → text）
- 按内容类型自动分类（学术论文/课程作业/项目/规范/不确定）
- 创建 source-note → `wiki/sources/<slug>.md`
- 创建/更新 concept/project/output 页面
- 敏感信息扫描

#### 3. 自动归档
- 已处理文件 → `raw/imported_processed/`
- 生成/更新 `raw/imported_processed/manifest.json`
- 修复所有 source_path frontmatter

#### 4. 自动健康检查（参考 tools/pkb_auto.py）

#### 5. 自动保存（git commit，健康检查通过后）

#### 6. 输出报告

---

## 📋 交互模式（无参数）

展示 `_INBOX/imported/` 和 `_INBOX/imported-folders/` 中的待处理文件。

### 执行步骤

1. 列出 `_INBOX/imported/` 和 `_INBOX/imported-folders/` 中的所有文件
2. 读取各 `manifest.json`（如存在）获取导入信息
3. 按导入时间排序展示
4. 对每个文件推荐可能的操作：
   - 📄 `.pdf` → 建议 `/paper`
   - 📄 `.docx/.doc` → 建议提取后编译进 wiki
   - 🌐 `webpack` → 建议 `/inbox --auto` 编译
   - 💻 `.py/.ts/.js` → 建议归档到 `raw/projects/`
   - 🖼️ 图片 → 建议归档到 `raw/media/images/`
5. 统计：总文件数、最早/最晚导入时间

### 输出格式
```
📥 _INBOX 待处理
═══════════════
[时间] 文件名 (大小) — 来源: xxx
  → 建议: 操作建议
...
---
📊 共 N 个文件，总计 X MB
💡 运行 /inbox --auto 自动编译所有待处理项
```
