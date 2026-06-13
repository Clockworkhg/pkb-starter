#!/usr/bin/env python3
"""本地动态测试站点 — HTTP Server。

用于 Playwright 本地集成测试。
不访问外部网络。

用法:
    # 固定端口（人工调试）
    python tests/fixtures/dynamic_site/server.py

    # 动态端口（pytest fixture）
    from tests.fixtures.dynamic_site.server import create_server
    server, port = create_server(0)
"""

import json
import http.server
import sys
from pathlib import Path

FIXTURES_DIR = Path(__file__).resolve().parent

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
        "自然语言处理（Natural Language Processing，简称NLP）作为人工智能领域的关键方向，"
        "致力于让计算机理解、生成和处理人类语言。近年来，深度学习技术的突破性进展深刻改变了NLP的研究范式。",
        "传统的NLP方法依赖于人工设计的特征和规则，例如词袋模型、N-gram语言模型和基于规则的句法分析器。"
        "这些方法在处理复杂语言现象时面临数据稀疏、泛化能力弱等固有局限。",
        "Transformer架构的提出是NLP领域的分水岭。与循环神经网络不同，Transformer完全基于自注意力机制，"
        "能够在常数时间复杂度内建模序列中任意两个位置之间的依赖关系。这一特性使得模型可以高效并行训练，"
        "并有效捕获长距离上下文信息。",
        "BERT（Bidirectional Encoder Representations from Transformers）通过掩码语言模型预训练任务，"
        "在11项NLP基准测试中刷新了记录。GPT系列模型则展示了自回归语言模型在少样本和零样本场景下的惊人能力。",
        "在实际应用中，深度学习驱动的NLP系统已在机器翻译、情感分析、智能问答、文本摘要、"
        "对话系统和代码生成等领域取得了接近甚至超越人类水平的表现。",
        "然而，当前的深度NLP模型仍然面临可解释性不足、训练成本高昂、对数据分布偏移敏感等挑战。"
        "未来的研究需要关注模型压缩、知识蒸馏、持续学习和多模态理解等方向。",
    ],
}

LAZY_CONTENT = {
    "extra": "（本文未完，以下为滚动加载的补充内容）联邦学习作为保护数据隐私的分布式机器学习范式，"
             "在NLP领域的应用日益广泛。通过在不共享原始数据的前提下协作训练语言模型，"
             "联邦学习为跨机构、跨语言的知识共享提供了新的技术路径。"
}

SHORT_ARTICLE = {"title": "摘要", "blocks": ["简短摘要内容。" * 1]}

MEDIUM_ARTICLE = {
    "title": "机器学习入门指南",
    "content": (
        "机器学习是人工智能的一个子领域，专注于构建能够从数据中学习的系统。"
        "监督学习是机器学习中最常见的范式，使用带标签的数据训练模型进行预测。"
        "无监督学习则在没有标签的数据中发现隐藏的模式和结构，如聚类和降维。"
        "深度学习使用多层神经网络，在图像识别和自然语言处理中取得了突破性成果。"
    ),
    "blocks": [
        "机器学习是人工智能的一个子领域，专注于构建能够从数据中学习的系统。",
        "监督学习是机器学习中最常见的范式，使用带标签的数据训练模型进行预测。",
        "无监督学习则在没有标签的数据中发现隐藏的模式和结构，如聚类和降维。",
        "深度学习使用多层神经网络，在图像识别和自然语言处理中取得了突破性成果。",
    ],
}

COMMENTS_DATA = [
    {"user": "alice", "text": "好文章！学到很多。"},
    {"user": "bob", "text": "感谢分享，收藏了。"},
    {"user": "charlie", "text": "这个方向很有前景。"},
]

RECOMMENDATIONS_DATA = [
    {"title": "推荐文章1", "desc": "关于机器学习的深入讨论" * 10},
    {"title": "推荐文章2", "desc": "NLP最新研究趋势分析" * 10},
]

EMPTY_RESPONSE = {"data": None}


# ── 场景 HTML ──

def _scenario_html(title: str, api_path: str, dom_content: str = "",
                   insert_into_dom: bool = True) -> str:
    """生成场景页面的 HTML 模板。

    Args:
        title: 页面标题
        api_path: JS fetch 的 API 路径（空字符串表示不请求 API）
        dom_content: 静态 DOM 正文（放在 #static-content 中）
        insert_into_dom: True = JS 将 API 数据插入 DOM（#content）；
                         False = JS 只发起请求但不插入 DOM（仅触发网络捕获）
    """
    dom_block = ""
    if dom_content:
        dom_block = f'<article id="static-content"><h2>DOM正文</h2><p>{dom_content}</p></article>'
    js_block = ""
    if api_path:
        if insert_into_dom:
            js_block = f'''
    <script>
      setTimeout(async () => {{
        try {{
          const resp = await fetch('{api_path}');
          const data = await resp.json();
          const el = document.getElementById('content');
          const title = data.title || '';
          const blocks = data.blocks || [];
          const extra = data.extra || '';
          let html = title ? '<h1>' + title + '</h1>' : '';
          html += blocks.map(b => '<p>' + b + '</p>').join('');
          if (extra) html += '<p>' + extra + '</p>';
          el.innerHTML = html;
        }} catch(e) {{
          document.getElementById('content').textContent = '加载失败: ' + e;
        }}
      }}, 200);
    </script>'''
        else:
            # 只发请求不插入 DOM — 用于测试"仅有 Network 候选可用"的场景
            js_block = f'''
    <script>
      setTimeout(async () => {{
        try {{
          await fetch('{api_path}');
        }} catch(e) {{}}
      }}, 200);
    </script>'''
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="utf-8"><title>{title}</title></head>
<body>
<nav>首页 登录 注册 关于</nav>
<main>
  <div id="loading">加载中...</div>
  {dom_block}
  <article id="content"></article>
</main>
<footer>Copyright 2024</footer>
{js_block}
</body>
</html>'''.strip()


# 预生成场景 HTML
#
# 设计要点：
#   - DOM 候选来自 Playwright 渲染后的页面内容
#   - Network 候选来自 JS fetch 的 API 响应（由 network_capture 监听器捕获）
#   - 所有场景原始 HTML 只含 nav/footer（无正文），强制 HTTP 提取不完整 → 触发 Playwright
#   - 控制 insert_into_dom 来决定 JS 是否将 API 数据插入 DOM
SCENARIOS = {
    # 1. DOM 和 Network 都有完整内容 → DOM 优先（富结构）
    "dom-complete": _scenario_html(
        "DOM和Network都完整",
        "/api/article",
        dom_content="",
        insert_into_dom=True,  # JS 将完整文章插入 DOM
    ),

    # 2. DOM 空壳（无静态内容，JS 不插入），Network 有完整文章 → Network 胜
    "network-only": _scenario_html(
        "DOM空壳Network完整",
        "/api/article",
        dom_content="",
        insert_into_dom=False,  # JS 发请求但不插入 DOM
    ),

    # 3. DOM 有正文（JS 插入），Network 抓取的是评论数据 → 评论不能替换 DOM
    #    JS 抓取两个 API：先抓文章插入 DOM，再抓评论（评论 API 被网络监听器捕获）
    "comments-noise": _scenario_html(
        "DOM正文Network评论",
        "/api/article",
        dom_content="",
        insert_into_dom=True,  # JS 将文章插入 DOM
        # 额外：页面也会请求 /api/comments（通过在模板后追加脚本）
    ),

    # 4. DOM 和 Network 都不完整 → 按规则选最高分
    "all-incomplete": _scenario_html(
        "都不完整",
        "/api/short",
        dom_content="",
        insert_into_dom=True,  # 只有简短摘要
    ),

    # 5. Network 显著优于 DOM（DOM 被插入短文章，Network 捕获长文章）
    "network-better": _scenario_html(
        "Network显著优于DOM",
        "/api/short",
        dom_content="",
        insert_into_dom=True,  # JS 将短文章插入 DOM → DOM 质量低
    ),

    # 6. DOM 和 Network 分数接近 → 优先选 DOM
    "scores-close": _scenario_html(
        "DOM和Network分数接近",
        "/api/medium",
        dom_content="",
        insert_into_dom=True,  # DOM 有中等文章，Network 也有中等文章
    ),
}

# ── 为 comments-noise 场景追加评论 API 请求 ──
# 在 JS 文章插入后额外请求 /api/comments
_ORIGINAL = SCENARIOS["comments-noise"]
SCENARIOS["comments-noise"] = _ORIGINAL.replace(
    '</script>',
    '''
      // 额外请求评论 API（网络监听器会捕获到 $.comments 负面路径）
      setTimeout(async () => {
        try { await fetch('/api/comments'); } catch(e) {}
      }, 400);
    </script>''',
    1  # 只替换第一个 </script>
)

# ── 为 network-better 场景追加长文章 API 请求 ──
# DOM 已有短文章（/api/short），页面额外请求 /api/article → 网络捕获到长文章
_ORIGINAL_NB = SCENARIOS["network-better"]
SCENARIOS["network-better"] = _ORIGINAL_NB.replace(
    '</script>',
    '''
      // 额外请求长文章 API（网络监听器捕获 → Network 候选质量更高）
      setTimeout(async () => {
        try { await fetch('/api/article'); } catch(e) {}
      }, 400);
    </script>''',
    1
)


class ScenariosHandler(http.server.SimpleHTTPRequestHandler):
    """支持多场景的动态测试 Handler。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(FIXTURES_DIR), **kwargs)

    def do_GET(self):
        if self.path == "/api/article":
            self._send_json(LONG_ARTICLE)
        elif self.path == "/api/lazy":
            self._send_json(LAZY_CONTENT)
        elif self.path == "/api/short":
            self._send_json(SHORT_ARTICLE)
        elif self.path == "/api/comments":
            self._send_json({"comments": COMMENTS_DATA})
        elif self.path == "/api/medium":
            self._send_json(MEDIUM_ARTICLE)
        elif self.path == "/api/recommendations":
            self._send_json({"recommendations": RECOMMENDATIONS_DATA})
        elif self.path == "/api/empty":
            self._send_json(EMPTY_RESPONSE)
        elif self.path.startswith("/scenario/"):
            scenario = self.path.split("/scenario/", 1)[1]
            if scenario in SCENARIOS:
                self._send_html(SCENARIOS[scenario])
            else:
                self.send_error(404)
        else:
            super().do_GET()

    def _send_json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self, html: str):
        body = html.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass


def create_server(port: int = 0) -> tuple[http.server.HTTPServer, int]:
    """创建测试服务器。port=0 表示操作系统自动分配端口。"""
    server = http.server.HTTPServer(("127.0.0.1", port), ScenariosHandler)
    actual_port = server.server_address[1]
    return server, actual_port


def main():
    port = 18765  # 固定端口用于人工调试
    server, actual_port = create_server(port)
    print(f"Dynamic test server at http://127.0.0.1:{actual_port}")
    print(f"Scenarios: /scenario/dom-complete, /scenario/network-only, "
          f"/scenario/comments-noise, /scenario/all-incomplete, /scenario/network-better")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
