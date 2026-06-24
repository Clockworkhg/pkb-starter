#!/usr/bin/env python3
"""
PKB BM25 检索引擎 (pkb_retrieve.py)

对 wiki/ 层做 BM25 全文检索，补充 /ask-pkb 的 index.md 路由 + grep 管线。
零强制依赖；rank_bm25 和 PyYAML 存在时自动加速。

用法:
    python tools/pkb_retrieve.py --build              # 构建/重建索引
    python tools/pkb_retrieve.py "查询词" --top-k 10   # 搜索
    python tools/pkb_retrieve.py --check              # 过期检测（exit 1 if stale）
    python tools/pkb_retrieve.py --stats              # 索引统计
    # 所有模式支持 --json

设计受 claude-obsidian v1.7 hybrid retrieval (AgriciDaniel/claude-obsidian, MIT)
和 Anthropic contextual retrieval 研究 (Sep 2024) 启发。代码全部独立实现。
"""

from __future__ import annotations

import argparse
import json
import os
import pickle
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import log
from pathlib import Path
from typing import Optional

# ── 编码: Windows 兼容 ──
sys.stdout.reconfigure(encoding='utf-8', errors='replace')  # type: ignore[attr-defined]

# ── 项目根 ──
_PKB_ROOT = Path(__file__).resolve().parent.parent
WIKI_DIR = _PKB_ROOT / "wiki"
CACHE_DIR = _PKB_ROOT / ".pkb-cache" / "retrieval"
INDEX_PATH = CACHE_DIR / "bm25_index.pkl"
MANIFEST_PATH = CACHE_DIR / "bm25_manifest.json"

# ── 排除文件 ──
EXCLUDE_STEMS = {"index", "log"}

# ── BM25 参数 ──
K1 = 1.5
B = 0.75

# ── 可选依赖 ──
try:
    from rank_bm25 import BM25Okapi
    HAS_RANK_BM25 = True
except ImportError:
    HAS_RANK_BM25 = False

try:
    import yaml as _yaml_lib
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

try:
    from sentence_transformers import SentenceTransformer
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

# ── Embedding 配置 ──
DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
BGE_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："
EMBEDDING_BATCH_SIZE = 32
EMBEDDING_MAX_CHARS = 2000  # 文档截断（bge-small max_seq_length=512 tokens）

# ── 向量索引路径 ──
EMBEDDINGS_PATH = CACHE_DIR / "embeddings.npy"
EMBEDDINGS_IDS_PATH = CACHE_DIR / "embeddings_ids.json"

# ── RRF 参数 ──
RRF_K = 60
RRF_POOL_SIZE = 50  # 每路召回数

# ── Reranker 配置 ──
DEFAULT_RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"
RERANK_TOP_K = 20  # RRF/检索召回后送入 reranker 的候选数

# ── Reranker 依赖检测 ──
try:
    from sentence_transformers import CrossEncoder
    HAS_CROSS_ENCODER = True
except ImportError:
    HAS_CROSS_ENCODER = False

# ── 模型缓存 ──
_embedding_model = None
_embedding_model_name = None
_embeddings_enabled = HAS_SENTENCE_TRANSFORMERS and HAS_NUMPY
_reranker_model = None
_reranker_model_name = None
_reranker_available = HAS_CROSS_ENCODER and HAS_NUMPY


# ═══════════════════════════════════════════════════════════════════
# Data Models
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SearchResult:
    """单条检索结果。"""
    file: str           # 相对路径，如 "wiki/concepts/llm-wiki.md"
    title: str          # 首个 # 标题
    score: float        # 最终分数（reranker > RRF > BM25 > cosine）
    snippet: str        # ~200 字符最佳匹配片段
    type: str           # concept / source-note / output / project / ...
    tags: list[str]
    bm25_score: float = 0.0     # 融合前的 BM25 原始分数
    vector_score: float = 0.0   # 融合前的 cosine 相似度
    rerank_score: float = 0.0   # Cross-encoder 重排序分数（0 = 未 rerank）
    mode: str = "bm25"          # bm25 / vector / hybrid

    def to_dict(self) -> dict:
        d = {
            "file": self.file,
            "title": self.title,
            "score": round(self.score, 4),
            "snippet": self.snippet,
            "type": self.type,
            "tags": self.tags,
        }
        if self.mode == "hybrid" or self.bm25_score > 0:
            d["bm25_score"] = round(self.bm25_score, 4)
        if self.mode == "hybrid" or self.vector_score > 0:
            d["vector_score"] = round(self.vector_score, 4)
        if self.rerank_score != 0.0:
            d["rerank_score"] = round(self.rerank_score, 4)
        d["mode"] = self.mode
        return d


@dataclass
class BM25Index:
    """可序列化的 BM25 索引。"""
    doc_ids: list[str]                  # 相对路径
    doc_vectors: list[dict[str, int]]   # token -> freq per doc
    doc_lengths: list[int]
    avgdl: float
    idf: dict[str, float]
    k1: float = K1
    b: float = B


@dataclass
class IndexManifest:
    """索引元数据（JSON 序列化，人类/LLM 可读）。"""
    version: int = 3
    built_at: str = ""
    doc_count: int = 0
    total_tokens: int = 0
    file_mtimes: dict[str, float] = field(default_factory=dict)
    embeddings_available: bool = False
    embedding_model: str = ""
    embedding_dims: int = 0
    reranker_available: bool = False
    reranker_model: str = ""


# ═══════════════════════════════════════════════════════════════════
# Tokenizer
# ═══════════════════════════════════════════════════════════════════

def _has_cjk(text: str) -> bool:
    """检测是否包含 CJK 字符。"""
    return any('一' <= c <= '鿿' for c in text)


# 尝试加载 jieba（Phase 2 计划）
try:
    import jieba as _jieba
    HAS_JIEBA = True
except ImportError:
    HAS_JIEBA = False


def tokenize(text: str) -> list[str]:
    """小写 + Unicode NFKC 归一化 → 分词 → 过滤短词/纯数字。

    Phase 1 字符级中文切分：每个 CJK 字符独立为一个 token。
    非 CJK 文本用 \\W+ 切分。
    Phase 2 计划用 jieba 替代字符级切分。
    """
    text = unicodedata.normalize("NFKC", text.lower())

    if HAS_JIEBA and _has_cjk(text):
        # jieba 精确模式
        raw_tokens: list[str] = list(_jieba.cut(text))
    elif _has_cjk(text):
        # 字符级：CJK 字符独立，非 CJK 用 \\W+
        parts: list[str] = []
        buf = ""
        for c in text:
            if '一' <= c <= '鿿':
                if buf.strip():
                    parts.append(buf)
                    buf = ""
                parts.append(c)
            else:
                buf += c
        if buf.strip():
            parts.append(buf)
        # 对非 CJK 部分再做 \\W+ 切分
        final: list[str] = []
        for p in parts:
            if _has_cjk(p) and len(p) == 1:
                final.append(p)
            else:
                final.extend(re.split(r"\W+", p))
        raw_tokens = final
    else:
        raw_tokens = re.split(r"\W+", text)

    out = []
    for t in raw_tokens:
        if not t:
            continue
        if len(t) < 2 and not _has_cjk(t):
            # 单个英文字母过滤，但单 CJK 字符保留
            continue
        if t.isdigit():
            continue
        out.append(t)
    return out


# ═══════════════════════════════════════════════════════════════════
# Frontmatter Parser
# ═══════════════════════════════════════════════════════════════════

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """解析 YAML frontmatter，返回 (fields_dict, body_text)。

    PyYAML 存在时自动加速；否则用内置正则解析 PKB 的简单 key: value 格式。
    """
    if not text.startswith("---"):
        return {}, text

    end = text.find("---", 3)
    if end == -1:
        return {}, text

    fm_text = text[3:end].strip()
    body = text[end + 3:].strip()

    if HAS_YAML:
        try:
            fields = _yaml_lib.safe_load(fm_text) or {}
            if isinstance(fields, dict):
                return fields, body
        except Exception:
            pass  # fall through to regex parser

    # 内置正则解析
    fields: dict = {}
    tags_val = None

    # tags: [a, b, c] 或 tags:\n  - a\n  - b
    tags_block = re.search(r'^tags:\s*$(.+?)(?:^\w+:|\Z)', fm_text, re.MULTILINE | re.DOTALL)
    if tags_block:
        tag_lines = tags_block.group(1).strip()
        tags_val = [t.strip().lstrip('- ') for t in tag_lines.split('\n') if t.strip().lstrip('- ')]
        if tags_val:
            fields["tags"] = tags_val

    # 单行 key: value（非 tags 块）
    for line in fm_text.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("tags:"):
            # 内联 tags: [a, b, c]
            m = re.match(r"^tags:\s*\[(.+)\]$", line)
            if m:
                fields["tags"] = [t.strip().strip("'\"") for t in m.group(1).split(",") if t.strip()]
            continue
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*):\s*(.*)", line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val.startswith("[") and val.endswith("]"):
                inner = val[1:-1]
                fields[key] = [v.strip().strip("'\"") for v in inner.split(",") if v.strip()]
            elif val in ("true", "false"):
                fields[key] = val == "true"
            else:
                fields[key] = val.strip("'\"")

    return fields, body


# ═══════════════════════════════════════════════════════════════════
# Snippet Extractor
# ═══════════════════════════════════════════════════════════════════

def extract_snippet(body: str, query_tokens: list[str], max_chars: int = 200) -> str:
    """找到 query_tokens 密度最高的段落，返回 ~max_chars 窗口。"""
    if not query_tokens or not body:
        return body[:max_chars]

    # 按段落切分
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if not paragraphs:
        return body[:max_chars]

    lower_body = body.lower()
    best_para = paragraphs[0]
    best_score = 0

    for para in paragraphs:
        lower_para = para.lower()
        score = sum(lower_para.count(t) for t in query_tokens)
        if score > best_score:
            best_score = score
            best_para = para

    if len(best_para) <= max_chars:
        return best_para
    return best_para[:max_chars] + "…"


# ═══════════════════════════════════════════════════════════════════
# Index Builder
# ═══════════════════════════════════════════════════════════════════

def build_index(wiki_root: Path) -> BM25Index:
    """遍历 wiki/**/*.md，构建 BM25Index。"""
    doc_ids: list[str] = []
    doc_vectors: list[dict[str, int]] = []
    doc_lengths: list[int] = []
    file_mtimes: dict[str, float] = {}
    total_tokens = 0

    md_files = sorted(
        f for f in wiki_root.rglob("*.md")
        if f.stem not in EXCLUDE_STEMS
    )

    for mf in md_files:
        try:
            raw = mf.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        fields, body = parse_frontmatter(raw)

        # 相对路径
        rel_path = str(mf.relative_to(wiki_root.parent)).replace("\\", "/")

        # tags 2x 权重 → 重复注入
        tags = fields.get("tags", [])
        if isinstance(tags, list):
            tags_str = " ".join(str(t) for t in tags)
        else:
            tags_str = ""

        # 加权文本: tags × 2 + body
        weighted_text = f"{tags_str} {tags_str} {body}"
        tokens = tokenize(weighted_text)
        vec: dict[str, int] = {}
        for t in tokens:
            vec[t] = vec.get(t, 0) + 1

        doc_ids.append(rel_path)
        doc_vectors.append(vec)
        doc_lengths.append(len(tokens))
        total_tokens += len(tokens)
        file_mtimes[rel_path] = mf.stat().st_mtime

    # IDF
    N = len(doc_ids)
    df: dict[str, int] = {}
    for vec in doc_vectors:
        for term in vec:
            df[term] = df.get(term, 0) + 1

    idf: dict[str, float] = {}
    for term, d in df.items():
        idf[term] = log((N - d + 0.5) / (d + 0.5) + 1.0)

    avgdl = total_tokens / N if N > 0 else 0.0

    index = BM25Index(
        doc_ids=doc_ids,
        doc_vectors=doc_vectors,
        doc_lengths=doc_lengths,
        avgdl=avgdl,
        idf=idf,
    )

    # 写缓存
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(INDEX_PATH, "wb") as f:
        pickle.dump(index, f, protocol=pickle.HIGHEST_PROTOCOL)

    # ── Embeddings ──
    emb_available = False
    emb_model = ""
    emb_dims = 0
    if _embeddings_enabled:
        try:
            _build_embeddings(doc_ids, wiki_root, model_name=_embedding_model_name)
            emb_available = True
            emb_model = _embedding_model_name or DEFAULT_EMBEDDING_MODEL
            emb_dims = _get_embedding_dims()
        except Exception as e:
            print(f"  ⚠️ Embeddings skipped: {e}", file=sys.stderr)

    manifest = IndexManifest(
        version=3,
        built_at=datetime.now(timezone.utc).isoformat(),
        doc_count=N,
        total_tokens=total_tokens,
        file_mtimes=file_mtimes,
        embeddings_available=emb_available,
        embedding_model=emb_model,
        embedding_dims=emb_dims,
        reranker_available=_reranker_available,
        reranker_model=(_reranker_model_name or DEFAULT_RERANKER_MODEL) if _reranker_available else "",
    )
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest.__dict__, f, ensure_ascii=False, indent=2)

    return index


# ═══════════════════════════════════════════════════════════════════
# Embedding Engine
# ═══════════════════════════════════════════════════════════════════

def _get_model(model_name: str | None = None):
    """懒加载 SentenceTransformer 模型。"""
    global _embedding_model, _embedding_model_name
    name = model_name or DEFAULT_EMBEDDING_MODEL
    if _embedding_model is None or _embedding_model_name != name:
        if not HAS_SENTENCE_TRANSFORMERS:
            raise RuntimeError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
        _embedding_model = SentenceTransformer(name)
        _embedding_model_name = name
    return _embedding_model


def _get_embedding_dims() -> int:
    """获取当前模型的向量维度。"""
    model = _get_model()
    try:
        return model.get_sentence_embedding_dimension()
    except AttributeError:
        return model.get_embedding_dimension()


def _doc_text_for_embedding(file_path: Path) -> str:
    """提取文档文本用于 embedding：标题 + 正文（不含 tags 和 frontmatter）。"""
    try:
        raw = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    fields, body = parse_frontmatter(raw)
    title = _extract_title(body)
    return f"{title}\n{body[:EMBEDDING_MAX_CHARS]}"


def _build_embeddings(
    doc_ids: list[str],
    wiki_root: Path,
    model_name: str | None = None,
) -> "np.ndarray":
    """构建向量索引 → 存 .npy + embeddings_ids.json。"""
    if not HAS_NUMPY:
        raise RuntimeError("numpy not installed. Run: pip install numpy")

    model = _get_model(model_name)
    texts = [_doc_text_for_embedding(wiki_root.parent / did) for did in doc_ids]

    print(f"  Encoding {len(texts)} documents with {_embedding_model_name}...",
          file=sys.stderr, flush=True)
    embeddings = model.encode(
        texts,
        batch_size=EMBEDDING_BATCH_SIZE,
        show_progress_bar=True,
        normalize_embeddings=True,  # L2 normalize → cosine sim = dot product
    )

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(str(EMBEDDINGS_PATH), embeddings.astype(np.float32))

    emb_manifest = {
        "model": _embedding_model_name,
        "dims": embeddings.shape[1],
        "doc_count": len(doc_ids),
        "doc_ids": doc_ids,
        "built_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(EMBEDDINGS_IDS_PATH, "w", encoding="utf-8") as f:
        json.dump(emb_manifest, f, ensure_ascii=False, indent=2)

    print(f"  Embeddings saved: {embeddings.shape[1]}d × {len(doc_ids)} docs",
          file=sys.stderr, flush=True)
    return embeddings


def _load_embeddings() -> tuple["np.ndarray", list[str]]:
    """加载向量索引。返回 (matrix[N, dims], doc_ids)。无索引时抛异常。"""
    if not EMBEDDINGS_PATH.exists() or not EMBEDDINGS_IDS_PATH.exists():
        raise FileNotFoundError("Embeddings index not built. Run --build first.")
    if not HAS_NUMPY:
        raise RuntimeError("numpy not installed. Run: pip install numpy")
    matrix = np.load(str(EMBEDDINGS_PATH))
    with open(EMBEDDINGS_IDS_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)
    return matrix, meta["doc_ids"]


# ═══════════════════════════════════════════════════════════════════
# BM25 Scorer
# ═══════════════════════════════════════════════════════════════════

def _bm25_score_single(
    query_tokens: list[str],
    doc_vec: dict[str, int],
    doc_len: int,
    avgdl: float,
    idf: dict[str, float],
    k1: float = K1,
    b: float = B,
) -> float:
    """计算单篇文档的 BM25 分数。"""
    score = 0.0
    for qt in query_tokens:
        if qt not in idf:
            continue
        tf = doc_vec.get(qt, 0)
        if tf == 0:
            continue
        idf_val = idf[qt]
        numerator = tf * (k1 + 1)
        denominator = tf + k1 * (1 - b + b * (doc_len / max(avgdl, 1.0)))
        score += idf_val * (numerator / denominator)
    return score


def _bm25_score_all(
    query_tokens: list[str],
    index: BM25Index,
) -> list[tuple[int, float]]:
    """批量计算所有文档的 BM25 分数。返回 [(doc_idx, score), ...] 按分数降序。"""
    if HAS_RANK_BM25:
        # rank_bm25 加速路径
        corpus = [
            list(vec.keys()) for vec in index.doc_vectors
        ]
        bm25 = BM25Okapi(corpus, k1=index.k1, b=index.b)
        scores = bm25.get_scores(query_tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
        return [(i, s) for i, s in ranked if s > 0]
    else:
        results = []
        for i, (vec, dlen) in enumerate(zip(index.doc_vectors, index.doc_lengths)):
            s = _bm25_score_single(query_tokens, vec, dlen, index.avgdl, index.idf, index.k1, index.b)
            if s > 0:
                results.append((i, s))
        results.sort(key=lambda x: x[1], reverse=True)
        return results


# ═══════════════════════════════════════════════════════════════════
# Vector Search
# ═══════════════════════════════════════════════════════════════════

def _vector_search(
    query: str,
    top_k: int = 50,
) -> list[tuple[int, float]]:
    """向量语义检索 → [(doc_idx, cosine_score), ...] 降序。"""
    if not HAS_NUMPY:
        return []

    try:
        emb_matrix, emb_ids = _load_embeddings()
    except (FileNotFoundError, RuntimeError):
        return []

    model = _get_model()
    query_text = BGE_QUERY_PREFIX + query
    query_vec = model.encode(
        [query_text],
        normalize_embeddings=True,
        show_progress_bar=False,
    )[0]  # shape: (dims,)

    # cosine similarity = dot product (vectors are L2-normalized)
    scores = np.dot(emb_matrix, query_vec)  # shape: (N,)

    # top-K
    if top_k >= len(scores):
        idxs = list(range(len(scores)))
    else:
        idxs = np.argpartition(-scores, top_k)[:top_k]
        idxs = idxs[np.argsort(-scores[idxs])]

    results = [(int(i), float(scores[i])) for i in idxs if float(scores[i]) > 0]
    return results


# ═══════════════════════════════════════════════════════════════════
# RRF Fusion
# ═══════════════════════════════════════════════════════════════════

def _rrf_fusion(
    bm25_results: list[tuple[int, float]],
    vector_results: list[tuple[int, float]],
    k: int = RRF_K,
) -> list[tuple[int, float, float, float]]:
    """RRF 融合 BM25 和向量两路结果。

    返回 [(doc_idx, rrf_score, bm25_score, vector_score), ...] 按 rrf_score 降序。

    RRF_score(d) = Σ 1/(k + rank_i(d))
    其中 k=60（标准值），只有一边有结果也保留。
    """
    # 建 rank map
    bm25_rank: dict[int, int] = {}
    for rank, (doc_idx, _) in enumerate(bm25_results, 1):
        bm25_rank[doc_idx] = rank

    vector_rank: dict[int, int] = {}
    for rank, (doc_idx, _) in enumerate(vector_results, 1):
        vector_rank[doc_idx] = rank

    bm25_score_map = {doc_idx: score for doc_idx, score in bm25_results}
    vec_score_map = {doc_idx: score for doc_idx, score in vector_results}

    # 所有出现过的文档
    all_docs = set(bm25_rank.keys()) | set(vector_rank.keys())

    fused: list[tuple[int, float, float, float]] = []
    for doc_idx in all_docs:
        rrf = 0.0
        if doc_idx in bm25_rank:
            rrf += 1.0 / (k + bm25_rank[doc_idx])
        if doc_idx in vector_rank:
            rrf += 1.0 / (k + vector_rank[doc_idx])
        fused.append((
            doc_idx,
            rrf,
            bm25_score_map.get(doc_idx, 0.0),
            vec_score_map.get(doc_idx, 0.0),
        ))

    fused.sort(key=lambda x: x[1], reverse=True)
    return fused


# ═══════════════════════════════════════════════════════════════════
# Reranker Engine (Cross-Encoder 二阶段重排)
# ═══════════════════════════════════════════════════════════════════

def _get_reranker(model_name: str | None = None) -> "CrossEncoder":
    """懒加载 CrossEncoder reranker 模型。

    模型首次加载时自动下载 (~568MB for bge-reranker-v2-m3)。
    """
    global _reranker_model, _reranker_model_name
    name = model_name or DEFAULT_RERANKER_MODEL
    if _reranker_model is None or _reranker_model_name != name:
        if not HAS_CROSS_ENCODER:
            raise RuntimeError(
                "sentence-transformers not installed. "
                "Run: pip install sentence-transformers"
            )
        print(f"  Loading reranker: {name}...", file=sys.stderr, flush=True)
        _reranker_model = CrossEncoder(name)
        _reranker_model_name = name
        print(f"  Reranker ready.", file=sys.stderr, flush=True)
    return _reranker_model


def _rerank(query: str, doc_texts: list[str]) -> list[float]:
    """Cross-encoder 重排序：对 (query, doc) 对逐一打分。

    返回与 doc_texts 等长的 float 列表，高分 = 更相关。
    """
    model = _get_reranker()
    pairs = [[query, text] for text in doc_texts]
    scores = model.predict(pairs, show_progress_bar=False)
    # scores 可能是 list[float] 或 numpy array
    if hasattr(scores, 'tolist'):
        scores = scores.tolist()
    return list(scores)


def _apply_reranker(
    query: str,
    candidates: list[tuple[int, float, float, float]],
    doc_ids: list[str],
    wiki_root: Path,
    top_n: int = RERANK_TOP_K,
) -> list[tuple[int, float, float, float]]:
    """对候选集 top-N 应用 cross-encoder 重排序。

    candidates: [(doc_idx, score, bm25_score, vector_score), ...]
    返回: 同格式，top-N 的 score 被替换为 reranker 分数并重排。

    失败时静默回退（保留原始分数）。
    """
    if not _reranker_available or len(candidates) == 0:
        return candidates

    n = min(top_n, len(candidates))

    # 读取候选文档文本
    texts: list[str] = []
    for doc_idx, _, _, _ in candidates[:n]:
        doc_path = wiki_root.parent / doc_ids[doc_idx]
        texts.append(_doc_text_for_embedding(doc_path))

    # 重排序
    try:
        scores = _rerank(query, texts)
    except Exception as e:
        print(f"  ⚠️ Reranker failed, using original scores: {e}",
              file=sys.stderr, flush=True)
        return candidates

    # 替换分数
    for i in range(n):
        doc_idx, _, bm25_s, vec_s = candidates[i]
        candidates[i] = (doc_idx, float(scores[i]), bm25_s, vec_s)

    # top-N 按 reranker 分数重排
    candidates[:n] = sorted(candidates[:n], key=lambda x: x[1], reverse=True)

    return candidates


# ═══════════════════════════════════════════════════════════════════
# Title Parser
# ═══════════════════════════════════════════════════════════════════

def _extract_title(body: str) -> str:
    """从 Markdown body 提取首个 # 标题。"""
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("# ") and not line.startswith("## "):
            return line[2:].strip()
    return "[no-title]"


# ═══════════════════════════════════════════════════════════════════
# Search
# ═══════════════════════════════════════════════════════════════════

def _read_result(
    doc_idx: int,
    doc_ids: list[str],
    wiki_root: Path,
    score: float,
    bm25_score: float,
    vector_score: float,
    mode: str,
    query_tokens: list[str],
    type_filter: str | None,
    include_snippet: bool,
    rerank_score: float = 0.0,
) -> SearchResult | None:
    """读取文档元数据，构建 SearchResult。失败返回 None。"""
    file_path = wiki_root.parent / doc_ids[doc_idx]
    try:
        raw = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    fields, body = parse_frontmatter(raw)
    title = _extract_title(body)
    page_type = str(fields.get("type", "unknown"))
    tags = fields.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    if type_filter and page_type != type_filter:
        return None

    snippet = ""
    if include_snippet:
        snippet = extract_snippet(body, query_tokens)

    return SearchResult(
        file=doc_ids[doc_idx],
        title=title,
        score=score,
        snippet=snippet,
        type=page_type,
        tags=tags,
        bm25_score=bm25_score,
        vector_score=vector_score,
        rerank_score=rerank_score,
        mode=mode,
    )


def search(
    index: BM25Index,
    query: str,
    wiki_root: Path,
    top_k: int = 10,
    mode: str = "hybrid",
    type_filter: str | None = None,
    min_score: float = 0.0,
    include_snippet: bool = True,
    no_rerank: bool = False,
) -> list[SearchResult]:
    """统一检索入口，支持 hybrid / bm25 / vector 三种模式。

    hybrid: BM25 + 向量 RRF 融合 + 可选 cross-encoder 重排（默认）
    bm25:  纯 BM25 关键词检索 + 可选 reranker
    vector: 纯向量语义检索 + 可选 reranker

    no_rerank=True 时跳过 cross-encoder 二阶段重排。
    """
    query_tokens = tokenize(query)
    if not query_tokens and mode != "vector":
        return []

    results: list[SearchResult] = []

    # ── vector-only ──
    if mode == "vector":
        if not _embeddings_enabled:
            print("Error: vector mode requires sentence-transformers + numpy. "
                  "Run: pip install sentence-transformers", file=sys.stderr)
            return []
        vec_scored = _vector_search(query, top_k=RRF_POOL_SIZE)
        if not vec_scored:
            print("Error: Embeddings index not built. Run --build first.", file=sys.stderr)
            return []
        # 转为 4-tuple: (doc_idx, score, bm25_score, vector_score)
        candidates = [(i, s, 0.0, s) for i, s in vec_scored]
        candidates = [c for c in candidates if c[1] >= min_score]
        # Reranker 二阶段重排
        was_reranked = False
        if not no_rerank and _reranker_available:
            candidates = _apply_reranker(query, candidates, index.doc_ids, wiki_root)
            was_reranked = True
        for doc_idx, score, bm25_s, vec_s in candidates:
            sr = _read_result(
                doc_idx, index.doc_ids, wiki_root,
                score=score, bm25_score=bm25_s, vector_score=vec_s,
                mode="vector", query_tokens=query_tokens,
                type_filter=type_filter, include_snippet=include_snippet,
                rerank_score=score if was_reranked else 0.0,
            )
            if sr:
                results.append(sr)
            if len(results) >= top_k:
                break
        return results

    # ── BM25 ──
    bm25_scored = _bm25_score_all(query_tokens, index)

    # ── bm25-only ──
    if mode == "bm25":
        # 转为 4-tuple: (doc_idx, score, bm25_score, vector_score)
        candidates = [(i, s, s, 0.0) for i, s in bm25_scored]
        candidates = [c for c in candidates if c[1] >= min_score]
        # Reranker 二阶段重排
        was_reranked = False
        if not no_rerank and _reranker_available:
            candidates = _apply_reranker(query, candidates, index.doc_ids, wiki_root)
            was_reranked = True
        for doc_idx, score, bm25_s, vec_s in candidates:
            sr = _read_result(
                doc_idx, index.doc_ids, wiki_root,
                score=score, bm25_score=bm25_s, vector_score=vec_s,
                mode="bm25", query_tokens=query_tokens,
                type_filter=type_filter, include_snippet=include_snippet,
                rerank_score=score if was_reranked else 0.0,
            )
            if sr:
                results.append(sr)
            if len(results) >= top_k:
                break
        return results

    # ── hybrid ──
    if mode == "hybrid":
        # 先跑 BM25 top-50
        bm25_pool = bm25_scored[:RRF_POOL_SIZE]

        # 尝试向量
        vec_pool: list[tuple[int, float]] = []
        if _embeddings_enabled:
            try:
                vec_pool = _vector_search(query, top_k=RRF_POOL_SIZE)
            except Exception:
                pass  # 降级

        if not vec_pool:
            # 降级为纯 BM25 + 可选 reranker
            candidates = [(i, s, s, 0.0) for i, s in bm25_pool]
            candidates = [c for c in candidates if c[1] >= min_score]
            was_reranked = False
            if not no_rerank and _reranker_available:
                candidates = _apply_reranker(query, candidates, index.doc_ids, wiki_root)
                was_reranked = True
            for doc_idx, score, bm25_s, vec_s in candidates:
                sr = _read_result(
                    doc_idx, index.doc_ids, wiki_root,
                    score=score, bm25_score=bm25_s, vector_score=vec_s,
                    mode="bm25", query_tokens=query_tokens,
                    type_filter=type_filter, include_snippet=include_snippet,
                    rerank_score=score if was_reranked else 0.0,
                )
                if sr:
                    results.append(sr)
                if len(results) >= top_k:
                    break
            return results

        # RRF 融合
        fused = _rrf_fusion(bm25_pool, vec_pool)

        # 按 RRF 分数过滤（reranker 前）
        fused = [f for f in fused if f[1] >= min_score]

        # Reranker 二阶段重排
        was_reranked = False
        if not no_rerank and _reranker_available:
            fused = _apply_reranker(query, fused, index.doc_ids, wiki_root)
            was_reranked = True

        for doc_idx, score, bm25_s, vec_s in fused:
            if score <= 0:
                continue
            sr = _read_result(
                doc_idx, index.doc_ids, wiki_root,
                score=score, bm25_score=bm25_s, vector_score=vec_s,
                mode="hybrid", query_tokens=query_tokens,
                type_filter=type_filter, include_snippet=include_snippet,
                rerank_score=score if was_reranked else 0.0,
            )
            if sr:
                results.append(sr)
            if len(results) >= top_k:
                break
        return results

    # 未知 mode
    return []


# ═══════════════════════════════════════════════════════════════════
# Staleness Check
# ═══════════════════════════════════════════════════════════════════

def check_stale(wiki_root: Path) -> dict:
    """比对 manifest 与当前文件系统 mtime。

    返回 {"stale": bool, "changed": [...], "new": [...], "deleted": [...]}
    """
    if not MANIFEST_PATH.exists():
        return {"stale": True, "changed": [], "new": [], "deleted": [], "reason": "no_index"}

    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            mdata = json.load(f)
    except Exception:
        return {"stale": True, "changed": [], "new": [], "deleted": [], "reason": "manifest_corrupt"}

    stored_mtimes = mdata.get("file_mtimes", {})
    changed = []
    current_paths = set()

    for rel_path, stored_mtime in stored_mtimes.items():
        abs_path = wiki_root.parent / rel_path
        if not abs_path.exists():
            changed.append({"file": rel_path, "reason": "deleted"})
            continue
        current_mtime = abs_path.stat().st_mtime
        current_paths.add(rel_path)
        if current_mtime > stored_mtime:
            changed.append({"file": rel_path, "reason": "modified"})

    # 新增文件
    for mf in wiki_root.rglob("*.md"):
        if mf.stem in EXCLUDE_STEMS:
            continue
        rel = str(mf.relative_to(wiki_root.parent)).replace("\\", "/")
        if rel not in stored_mtimes:
            changed.append({"file": rel, "reason": "new"})

    stale = len(changed) > 0

    return {
        "stale": stale,
        "changed": changed,
        "built_at": mdata.get("built_at", ""),
    }


# ═══════════════════════════════════════════════════════════════════
# Stats
# ═══════════════════════════════════════════════════════════════════

def get_stats() -> dict:
    """读取索引统计。"""
    if not MANIFEST_PATH.exists():
        return {"error": "Index not built. Run --build first."}

    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            mdata = json.load(f)
    except Exception:
        return {"error": "Manifest corrupt. Rebuild with --build."}

    stale_info = check_stale(WIKI_DIR)

    bm25_stats = {
        "doc_count": mdata.get("doc_count", 0),
        "total_tokens": mdata.get("total_tokens", 0),
        "built_at": mdata.get("built_at", ""),
        "stale": stale_info["stale"],
        "index_size_bytes": INDEX_PATH.stat().st_size if INDEX_PATH.exists() else 0,
    }

    emb_info = {
        "available": mdata.get("embeddings_available", False),
    }
    if emb_info["available"]:
        emb_info["model"] = mdata.get("embedding_model", "")
        emb_info["dims"] = mdata.get("embedding_dims", 0)
        emb_info["size_bytes"] = EMBEDDINGS_PATH.stat().st_size if EMBEDDINGS_PATH.exists() else 0
        emb_info["stale"] = stale_info["stale"]  # same staleness as BM25

    reranker_info = {
        "available": mdata.get("reranker_available", False),
    }
    if reranker_info["available"]:
        reranker_info["model"] = mdata.get("reranker_model", "")

    return {
        "bm25": bm25_stats,
        "embeddings": emb_info,
        "reranker": reranker_info,
    }


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

def _cli_main() -> int:
    global _embeddings_enabled, _embedding_model_name, _reranker_model_name

    parser = argparse.ArgumentParser(
        description="PKB 混合检索引擎 — wiki/ BM25 + 向量语义检索 + Cross-encoder 重排",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python tools/pkb_retrieve.py --build
  python tools/pkb_retrieve.py --build --no-embeddings
  python tools/pkb_retrieve.py "费尔巴哈 唯物主义" --mode hybrid --top-k 10 --json
  python tools/pkb_retrieve.py "德国古典哲学" --mode vector --json
  python tools/pkb_retrieve.py --check --json
  python tools/pkb_retrieve.py --stats --json
  python tools/pkb_retrieve.py --rebuild-embeddings
  python tools/pkb_retrieve.py "查询" --no-rerank --json
""",
    )

    parser.add_argument(
        "query", nargs="?", default=None,
        help="搜索查询词"
    )
    parser.add_argument(
        "--build", action="store_true",
        help="构建/重建索引（BM25 + 向量）"
    )
    parser.add_argument(
        "--no-embeddings", action="store_true",
        help="--build 时跳过向量索引"
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help=f"Embedding 模型名称（默认: {DEFAULT_EMBEDDING_MODEL}）"
    )
    parser.add_argument(
        "--rebuild-embeddings", action="store_true",
        help="仅重建向量索引（保持 BM25 不变）"
    )
    parser.add_argument(
        "--check", action="store_true",
        help="检查索引是否过期（exit 1 if stale）"
    )
    parser.add_argument(
        "--stats", action="store_true",
        help="打印索引统计"
    )
    parser.add_argument(
        "--mode", type=str, default="hybrid",
        choices=["hybrid", "bm25", "vector"],
        help="检索模式（默认: hybrid）"
    )
    parser.add_argument(
        "--top-k", type=int, default=10,
        help="返回结果数（默认 10）"
    )
    parser.add_argument(
        "--type", dest="type_filter", default=None,
        help="按页面类型过滤（concept/source-note/output/project）"
    )
    parser.add_argument(
        "--min-score", type=float, default=0.0,
        help="最低分数阈值（默认 0.0）"
    )
    parser.add_argument(
        "--no-snippet", action="store_true",
        help="省略摘要片段（加速）"
    )
    parser.add_argument(
        "--no-rerank", action="store_true",
        help="禁用 cross-encoder 二阶段重排（仅用 BM25/RRF/向量分数）"
    )
    parser.add_argument(
        "--reranker-model", type=str, default=None,
        help=f"Reranker 模型名称（默认: {DEFAULT_RERANKER_MODEL}）"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="JSON 格式输出（供 LLM 消费）"
    )

    args = parser.parse_args()

    # ── --build ──
    if args.build:
        if args.no_embeddings:
            _embeddings_enabled = False
        if args.model:
            _embedding_model_name = args.model
        if args.reranker_model:
            _reranker_model_name = args.reranker_model

        emb_status = " + embeddings" if _embeddings_enabled else " (BM25 only)"
        print(f"Building index{emb_status}...",
              file=sys.stderr if args.json else sys.stdout, flush=True)
        index = build_index(WIKI_DIR)
        if args.json:
            stats = get_stats()
            json.dump({"status": "ok", **stats}, sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            print(f"  Index built: {index.doc_ids.__len__()} documents, "
                  f"avg length {index.avgdl:.0f} tokens")
            if _embeddings_enabled:
                mname = _embedding_model_name or DEFAULT_EMBEDDING_MODEL
                print(f"  Embeddings: {mname}")
            if _reranker_available:
                rname = _reranker_model_name or DEFAULT_RERANKER_MODEL
                print(f"  Reranker:   {rname}")
        return 0

    # ── --rebuild-embeddings ──
    if args.rebuild_embeddings:
        if not _embeddings_enabled:
            print("Error: sentence-transformers + numpy required for embeddings.",
                  file=sys.stderr)
            return 1
        if args.model:
            _embedding_model_name = args.model
        # 加载已有 doc_ids
        doc_ids = list(get_stats().get("file_mtimes", {}).keys()) if False else []
        if not MANIFEST_PATH.exists():
            print("Error: BM25 index not found. Run --build first.", file=sys.stderr)
            return 1
        try:
            with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
                mdata = json.load(f)
            doc_ids = list(mdata.get("file_mtimes", {}).keys())
        except Exception:
            print("Error: Cannot read manifest.", file=sys.stderr)
            return 1
        if not doc_ids:
            print("Error: No documents in index.", file=sys.stderr)
            return 1
        print(f"Rebuilding embeddings for {len(doc_ids)} documents...",
              file=sys.stderr if args.json else sys.stdout, flush=True)
        try:
            _build_embeddings(doc_ids, WIKI_DIR, model_name=_embedding_model_name)
            if args.json:
                json.dump({"status": "ok", "embeddings_rebuilt": True},
                          sys.stdout, ensure_ascii=False)
                print()
            else:
                print("  Embeddings rebuilt successfully.")
        except Exception as e:
            msg = f"Embeddings rebuild failed: {e}"
            if args.json:
                json.dump({"status": "error", "error": msg}, sys.stdout, ensure_ascii=False)
                print()
            else:
                print(f"  ✗ {msg}", file=sys.stderr)
            return 1
        return 0

    # ── --check ──
    if args.check:
        stale_info = check_stale(WIKI_DIR)
        if args.json:
            json.dump(stale_info, sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            if stale_info["stale"]:
                print(f"⚠️  Index STALE ({len(stale_info['changed'])} files changed)")
            else:
                print(f"✅ Index fresh ({stale_info.get('built_at', 'unknown')})")
        return 1 if stale_info["stale"] else 0

    # ── --stats ──
    if args.stats:
        stats = get_stats()
        if args.json:
            json.dump(stats, sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            if "error" in stats:
                print(stats["error"])
                return 1
            bm = stats["bm25"]
            emb = stats["embeddings"]
            rerank = stats["reranker"]
            print(f"BM25:     {bm['doc_count']} docs, {bm['total_tokens']:,} tokens, "
                  f"{bm['index_size_bytes']:,} bytes")
            print(f"          built {bm['built_at']}, "
                  f"{'⚠️ STALE' if bm['stale'] else '✅ fresh'}")
            if emb["available"]:
                print(f"Vector:   {emb['model']} ({emb['dims']}d), "
                      f"{emb['size_bytes']:,} bytes")
            else:
                print(f"Vector:   ❌ not available "
                      f"(pip install sentence-transformers)")
            if rerank["available"]:
                print(f"Reranker: {rerank['model']} (cross-encoder)")
            else:
                print(f"Reranker: ❌ not available "
                      f"(pip install sentence-transformers)")
        return 0

    # ── 搜索 ──
    if args.query:
        if not INDEX_PATH.exists():
            msg = "Index not built. Run --build first."
            if args.json:
                json.dump({"error": msg}, sys.stdout, ensure_ascii=False)
                print()
            else:
                print(msg, file=sys.stderr)
            return 1

        try:
            with open(INDEX_PATH, "rb") as f:
                index: BM25Index = pickle.load(f)
        except Exception:
            msg = "Failed to load index. Rebuild with --build."
            if args.json:
                json.dump({"error": msg}, sys.stdout, ensure_ascii=False)
                print()
            else:
                print(msg, file=sys.stderr)
            return 1

        # 覆盖 reranker 模型
        if args.reranker_model:
            _reranker_model_name = args.reranker_model

        results = search(
            index,
            args.query,
            WIKI_DIR,
            top_k=args.top_k,
            mode=args.mode,
            type_filter=args.type_filter,
            min_score=args.min_score,
            include_snippet=not args.no_snippet,
            no_rerank=args.no_rerank,
        )

        if args.json:
            output = {
                "query": args.query,
                "mode": args.mode,
                "top_k": args.top_k,
                "result_count": len(results),
                "results": [r.to_dict() for r in results],
            }
            json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
            print()
        else:
            mode_label = f"[{args.mode}]" if args.mode != "bm25" else ""
            print(f"Query: {args.query} {mode_label} ({len(results)} results)")
            print("-" * 60)
            for i, r in enumerate(results, 1):
                extra = ""
                if r.mode == "hybrid":
                    extra = f"  BM25:{r.bm25_score:.2f} Vec:{r.vector_score:.3f}"
                    if r.rerank_score != 0.0:
                        extra += f" Rerank:{r.rerank_score:.4f}"
                elif r.rerank_score != 0.0:
                    extra = f"  Rerank:{r.rerank_score:.4f}"
                print(f"{i}. [{r.type}] {r.title}  (score: {r.score:.4f}){extra}")
                print(f"   {r.file}")
                if r.snippet:
                    print(f"   \"{r.snippet[:120]}…\"")
                if r.tags:
                    print(f"   tags: {', '.join(r.tags[:5])}")
                print()

        return 0

    # ── 无操作 ──
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(_cli_main())
