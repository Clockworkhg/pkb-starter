# PKB 升级指南

## 系统更新时用户数据保护

PKB 更新不会覆盖以下用户数据目录：

### 受保护的目录

| 目录 | 内容 | 保护方式 |
|------|------|---------|
| `.pkb_local/scholarly/cache.sqlite3` | 学术元数据缓存 | `.gitignore` + 更新器跳过 |
| `.pkb_local/scholarly/rankings/*.csv` | 导入的期刊等级 CSV | `.gitignore` + 更新器跳过 |
| `.pkb_local/scholarly/jobs/` | 批量任务断点状态 | `.gitignore` + 更新器跳过 |
| `.pkb_local/scholarly/styles/*.csl` | 自定义引用样式 | `.gitignore` + 更新器跳过 |
| `pkb.config.json` | 用户配置（含 scholarly 配置） | 不会被覆盖 |
| `.claude/settings.local.json` | Claude Code 本地设置 | `.gitignore` |
| `wiki/` | 知识库内容 | 不含在系统更新中 |
| `raw/` | 原始资料 | 不含在系统更新中 |
| `_INBOX/` | 待处理文件 | `.gitignore` |

### 数据安全原则

1. **系统工具和用户数据分离**：`tools/` 和 `.claude/` 是系统文件，`.pkb_local/`、`wiki/`、`raw/` 是用户数据
2. **SHA-256 校验**：升级前后所有用户配置文件 SHA-256 保持不变
3. **不自动删除**：系统更新不会删除 `.pkb_local/` 下的任何用户文件

### 更新后验证

```bash
# 检查用户数据完整性
python tools/pkb_auto.py --check

# 验证学术元数据缓存
python tools/scholarly_enrich.py --cache-only --scan wiki/ --dry-run
```

## 期刊目录迁移

升级时已导入的期刊目录（`.pkb_local/scholarly/rankings/`）自动保留。

重新导入不会重复已有数据：

```bash
python tools/import_journal_rankings.py import new-data.csv  # 增量导入
python tools/import_journal_rankings.py list                  # 查看当前
```

## 故障排查

### 升级后 scholarly 模块报错

1. 确认 Python 依赖已安装：
   ```bash
   pip install -r tools/requirements-scholarly.txt
   ```

2. 检查配置：
   ```bash
   python -c "import json; c=json.load(open('pkb.config.json')); print(c.get('scholarly', {}))"
   ```

3. 运行诊断：
   ```bash
   python -m pytest tests/test_scholarly_integration.py -v
   ```

### Bun / claude-mem 故障

若 SessionStart Hook 报错 bun 或 claude-mem：
- 这些是可选的 MCP 服务，不影响核心功能
- 在 `.claude/settings.local.json` 中禁用相关 MCP 服务

### 当前不支持

- 网络首发论文（无正式卷期页码）的引用格式可能不完整
- 非期刊类型（图书、会议论文、学位论文）的 GB/T 7714 fallback 尚未金样验证
- JCR / Scopus / 中科院分区（Phase 1C 规划中）
