"""动态站点测试 fixture — 提供自动分配端口的测试服务器。"""

import sys
import threading
import time
from pathlib import Path

import pytest

# 确保 tools/ 可被导入
_TOOLS_DIR = Path(__file__).resolve().parent.parent.parent / "tools"
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))


@pytest.fixture(scope="module")
def dynamic_server():
    """启动动态测试服务器（自动分配端口）。"""
    from tests.fixtures.dynamic_site.server import create_server

    server, port = create_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.15)

    yield server, port

    server.shutdown()
    thread.join(timeout=2)


@pytest.fixture(scope="module")
def dynamic_base_url(dynamic_server):
    """返回测试服务器的 base URL。"""
    _server, port = dynamic_server
    return f"http://127.0.0.1:{port}"
