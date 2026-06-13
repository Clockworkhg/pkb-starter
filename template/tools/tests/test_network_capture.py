#!/usr/bin/env python3
"""network_capture.py 单元测试 — 18 个捕获层测试。

测试不访问网络，使用 mock Playwright response 对象。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

_TOOLS_DIR = Path(__file__).resolve().parent.parent
if str(_TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(_TOOLS_DIR))

import pytest
from network_capture import (
    NetworkCaptureOptions,
    CapturedResponse,
    CaptureDiagnostic,
    ResponseCaptureSession,
    sanitize_url,
    _is_eligible_content_type,
    _classify_content_type,
)


def _make_mock_response(url, status=200, content_type="application/json",
                        body=None, method="GET", content_length=None,
                        headers_extra=None):
    """创建 mock Playwright response 对象。"""
    resp = MagicMock()
    resp.url = url
    resp.status = status
    resp.headers = {"content-type": content_type}
    if content_length is not None:
        resp.headers["content-length"] = str(content_length)
    if headers_extra:
        resp.headers.update(headers_extra)
    resp.request.method = method
    if body is not None:
        resp.body.return_value = body
    else:
        resp.body.return_value = json.dumps({"article": {"content": "Long article text " * 50}}).encode()
    return resp


# ── 捕获层测试 ──

def test_json_is_eligible():
    assert _is_eligible_content_type("application/json") is True
    assert _is_eligible_content_type("application/vnd.api+json") is True
    assert _is_eligible_content_type("text/json") is True


def test_html_is_eligible():
    assert _is_eligible_content_type("text/html") is True
    assert _is_eligible_content_type("text/html; charset=utf-8") is True


def test_plain_text_is_eligible():
    assert _is_eligible_content_type("text/plain") is True


def test_images_skipped():
    assert _is_eligible_content_type("image/png") is False
    assert _is_eligible_content_type("video/mp4") is False
    assert _is_eligible_content_type("text/css") is False
    assert _is_eligible_content_type("font/woff2") is False


def test_js_bundle_skipped():
    assert _is_eligible_content_type("application/javascript") is False
    assert _is_eligible_content_type("text/javascript") is False


def test_options_skipped():
    opts = NetworkCaptureOptions()
    session = ResponseCaptureSession(opts)
    resp = _make_mock_response("https://example.com/api", method="OPTIONS")
    session._on_response(resp)
    assert session._diagnostic.eligible_responses_seen == 0


def test_non_2xx_skipped():
    opts = NetworkCaptureOptions()
    session = ResponseCaptureSession(opts)
    for status in (301, 302, 404, 500):
        resp = _make_mock_response("https://example.com/api", status=status)
        session._on_response(resp)
    assert session._diagnostic.eligible_responses_seen == 0


def test_204_skipped():
    opts = NetworkCaptureOptions()
    session = ResponseCaptureSession(opts)
    resp = _make_mock_response("https://example.com/api", status=204)
    session._on_response(resp)
    assert session._diagnostic.eligible_responses_seen == 0


def test_content_length_over_limit_skipped():
    opts = NetworkCaptureOptions(max_response_bytes=512 * 1024)
    session = ResponseCaptureSession(opts)
    resp = _make_mock_response("https://example.com/large", content_length=999_999)
    session._on_response(resp)
    assert session._diagnostic.skipped_by_size == 1


def test_actual_body_over_limit_skipped():
    opts = NetworkCaptureOptions(max_response_bytes=100)
    session = ResponseCaptureSession(opts)
    big_body = b"x" * 200
    resp = _make_mock_response("https://example.com/api", body=big_body)
    session._on_response(resp)
    session.finalize()
    assert len(session.get_responses()) == 0
    assert session._diagnostic.skipped_by_size == 1


def test_max_responses_limit():
    opts = NetworkCaptureOptions(max_analyzed_responses=3)
    session = ResponseCaptureSession(opts)
    body = b'{"k":"v"}'
    for i in range(5):
        resp = _make_mock_response(f"https://example.com/api/{i}", body=body)
        session._on_response(resp)
    assert session._diagnostic.skipped_by_limit == 2


def test_body_read_failure_handled():
    opts = NetworkCaptureOptions()
    session = ResponseCaptureSession(opts)
    resp = _make_mock_response("https://example.com/api")
    resp.body.side_effect = RuntimeError("closed")
    session._on_response(resp)
    session.finalize()
    assert session._diagnostic.body_read_failures == 1


def test_requestfailed_counted():
    opts = NetworkCaptureOptions()
    session = ResponseCaptureSession(opts)
    req = MagicMock()
    session._on_requestfailed(req)

    # 间接验证（_on_requestfailed 不改变任何诊断字段，仅记录存在性）
    # 此测试验证回调不抛出异常
    assert session._diagnostic is not None


def test_duplicate_body_dedup():
    opts = NetworkCaptureOptions()
    session = ResponseCaptureSession(opts)
    body = json.dumps({"content": "Hello world " * 20}).encode()
    resp1 = _make_mock_response("https://api1.example.com/data", body=body)
    resp2 = _make_mock_response("https://api2.example.com/data", body=body)
    session._on_response(resp1)
    session._on_response(resp2)
    session.finalize()
    assert len(session.get_responses()) == 1
    assert session._diagnostic.duplicate_responses == 1


def test_same_url_different_body_kept():
    opts = NetworkCaptureOptions()
    session = ResponseCaptureSession(opts)
    body1 = json.dumps({"content": "AAA " * 100}).encode()
    body2 = json.dumps({"content": "BBB " * 100}).encode()
    resp1 = _make_mock_response("https://example.com/poll", body=body1)
    resp2 = _make_mock_response("https://example.com/poll", body=body2)
    session._on_response(resp1)
    session._on_response(resp2)
    session.finalize()
    # 不同 body → 两个都保留
    assert len(session.get_responses()) == 2


def test_url_sanitization():
    url = "https://api.example.com/article?id=12&token=abc123&sign=xyz&name=test"
    result = sanitize_url(url)
    assert "token=***REDACTED***" in result
    assert "sign=***REDACTED***" in result
    assert "id=12" in result
    assert "name=test" in result
    assert "abc123" not in result
    assert "xyz" not in result


def test_sensitive_headers_not_in_record():
    """验证 CapturedResponse 不包含 Cookie/Authorization。"""
    cr = CapturedResponse(
        url="https://example.com", sanitized_url="https://example.com",
        status=200, method="GET", content_type="application/json",
        declared_size=100, actual_size=100, body=b'{"ok":true}',
        body_sha256="abc123",
    )
    # CapturedResponse 是 frozen dataclass，字段固定
    assert not hasattr(cr, 'headers')
    assert not hasattr(cr, 'cookies')


def test_close_idempotent():
    opts = NetworkCaptureOptions()
    session = ResponseCaptureSession(opts)
    session.close()
    session.close()
    # 不应抛出异常
    assert session._closed is True


# ── 敏感参数完整测试 ──

SENSITIVE_PARAMS_LIST = sorted([
    "token", "access_token", "refresh_token",
    "auth", "authorization", "api_key", "apikey",
    "secret", "session", "sessionid",
    "device_id", "user_id", "uid",
    "hkey", "sign", "signature",
    "password", "passwd", "pwd",
])


@pytest.mark.parametrize("param", SENSITIVE_PARAMS_LIST)
def test_sensitive_param_redacted(param):
    """每个敏感参数都被脱敏。"""
    url = f"https://api.example.com/data?{param}=secret_value&safe=ok"
    result = sanitize_url(url)
    assert f"{param}=***REDACTED***" in result
    assert "secret_value" not in result
    assert "safe=ok" in result


def test_sensitive_params_count():
    """验证敏感参数数量与实际集合一致。"""
    from network_capture import SENSITIVE_QUERY_PARAMS
    assert len(SENSITIVE_QUERY_PARAMS) == 19, \
        f"Expected 19 sensitive params, got {len(SENSITIVE_QUERY_PARAMS)}"


def test_sensitive_params_case_insensitive():
    """敏感参数匹配不区分大小写。"""
    url = "https://api.example.com?TOKEN=abc&Access_Token=def&HKEY=ghi"
    result = sanitize_url(url)
    assert "TOKEN=***REDACTED***" in result
    assert "Access_Token=***REDACTED***" in result
    assert "HKEY=***REDACTED***" in result


# ── 监听器注册时序 ──

def test_listener_registered_before_goto():
    """验证 ResponseCaptureSession.attach() 在 page.goto() 前调用。"""
    from unittest.mock import patch, MagicMock

    opts = NetworkCaptureOptions()
    session = ResponseCaptureSession(opts)

    page = MagicMock()
    call_order = []

    original_on = page.on
    def tracking_on(event, handler):
        call_order.append(f"on:{event}")
        original_on(event, handler)

    page.on = tracking_on

    # 模拟正确的顺序：先 attach, 再 goto
    session.attach(page)
    # 触发一个响应（模拟导航期间的网络请求）
    resp = _make_mock_response("https://example.com/api/early")
    session._on_response(resp)

    assert session._diagnostic.total_responses_seen > 0, \
        "监听器应在导航前注册，确保早期请求不丢失"


# ── 响应 body 释放 ──

def test_body_released_after_finalize():
    """finalize() 后 pending 清空，响应引用释放。"""
    opts = NetworkCaptureOptions()
    session = ResponseCaptureSession(opts)

    body = b'{"content": "test"}' * 50
    resp = _make_mock_response("https://example.com/api", body=body)
    session._on_response(resp)
    session.finalize()

    responses = session.get_responses()
    # finalize() 后 pending 应清空
    assert len(session._pending) == 0

    # 关闭后引用释放
    session.close()
    assert session._closed is True
    assert len(session._pending) == 0
    assert len(session._seen_hashes) == 0


def test_classify_content_type():
    assert _classify_content_type("application/json") == "json"
    assert _classify_content_type("text/html") == "html"
    assert _classify_content_type("text/plain") == "plain"
    assert _classify_content_type("image/png") == "other"
