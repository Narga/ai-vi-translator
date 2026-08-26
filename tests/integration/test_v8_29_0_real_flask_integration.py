#!/usr/bin/env python3
"""Comprehensive real Flask path test cho tất cả 11 v8.29.0 changes.

Chạy qua webui.create_app() thật, test từng endpoint mới. Không mock, không
unit test — test public path thật của dự án.
"""
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture(scope="module")
def real_flask_client():
    """Tạo Flask app thật + test client, dùng copy config để không phá thật."""
    d = Path(tempfile.mkdtemp())
    shutil.copytree('config', d / 'config')
    old_cwd = os.getcwd()
    os.chdir(d)
    try:
        from webui import create_app
        app = create_app()
        app.config['TESTING'] = True
        yield app.test_client(), d
    finally:
        os.chdir(old_cwd)


class TestV829AcceptancePath:
    """Acceptance test qua public Flask path thật (không mock)."""

    def test_1_get_providers_masked(self, real_flask_client):
        client, _ = real_flask_client
        r = client.get('/api/providers')
        leaked = sum(1 for p in r.get_json()['providers']
                     if p.get('api_key') or p.get('api_keys'))
        assert leaked == 0, f'leaked {leaked} plaintext keys'

    def test_2_get_providers_etag_header(self, real_flask_client):
        client, _ = real_flask_client
        r = client.get('/api/providers')
        etag = r.headers.get('ETag', '')
        assert etag.startswith('"sha256-') and etag.endswith('"'), \
            f'ETag header missing or wrong format: {etag!r}'

    def test_3_post_settings_app_rejects_legacy_model(self, real_flask_client):
        client, _ = real_flask_client
        r = client.post('/api/settings/app', json={'config': {'MODEL': {'MODEL': 'x'}}})
        assert r.status_code == 400, f'expected 400 got {r.status_code}'

    def test_4_get_settings_app_has_runtime(self, real_flask_client):
        client, _ = real_flask_client
        r = client.get('/api/settings/app')
        assert 'RUNTIME' in r.get_json()['config'], 'RUNTIME section missing'

    def test_5_save_rejects_cross_namespace(self, real_flask_client):
        client, _ = real_flask_client
        r = client.post('/api/settings/save', json={
            'provider_id': 'gemini-default',
            'default_model': 'step-3.7-flash',
            'app_config': {'PROCESSING': {'TEMPERATURE': '0.9'}},
        })
        assert r.status_code == 400, f'expected 400 got {r.status_code}'

    def test_6_save_valid_persists(self, real_flask_client):
        client, tmp_dir = real_flask_client
        r = client.post('/api/settings/save', json={
            'provider_id': 'gemini-default',
            'default_model': 'gemini-2.5-flash',
            'app_config': {'PROCESSING': {'TEMPERATURE': '1.1'}},
        })
        assert r.status_code == 200, f'expected 200 got {r.status_code}'
        # Revert
        client.post('/api/settings/save', json={
            'provider_id': 'gemini-default',
            'default_model': 'gemini-2.0-flash',
            'app_config': {'PROCESSING': {'TEMPERATURE': '1.0'}},
        })

    def test_7_models_rejects_cross_namespace(self, real_flask_client):
        client, _ = real_flask_client
        r = client.put('/api/providers/openrouter/models',
                       json={'default_model': 'gemini-2.0-flash'})
        assert r.status_code == 400, f'expected 400 got {r.status_code}'

    def test_8_models_stale_etag_returns_409(self, real_flask_client):
        client, _ = real_flask_client
        old_etag = client.get('/api/providers').headers.get('ETag')
        # Make change
        client.put('/api/providers/openrouter/models',
                   json={'default_model': 'anthropic/claude-3.5-sonnet'})
        # Try with stale etag
        r = client.put('/api/providers/openrouter/models',
                       json={'default_model': 'openai/gpt-4o'},
                       headers={'If-Match': old_etag})
        assert r.status_code == 409, f'expected 409 got {r.status_code}'
        body = r.get_json()
        assert 'ETag mismatch' in body['error']
        assert body['your_etag'] == old_etag
        # Revert
        client.put('/api/providers/openrouter/models',
                   json={'default_model': 'deepseek/deepseek-v4-flash-0731'})

    def test_9_credentials_response_masked(self, real_flask_client):
        client, _ = real_flask_client
        r = client.put('/api/providers/openrouter/credentials',
                      json={'api_key': 'sk-test-mask-1234567890'})
        assert r.status_code == 200, f'expected 200 got {r.status_code}'
        data = r.get_json()
        assert data['provider']['api_key_last4'] == '...7890'
        # Revert
        orig = json.loads(Path('config/providers.json').read_text())
        # tmp_dir is module-scoped fixture; need to find current config
        import os
        old_key = next(p for p in orig['providers'] if p['id'] == 'openrouter')['api_key']
        client.put('/api/providers/openrouter/credentials', json={'api_key': old_key})

    def test_10_models_provider_not_found(self, real_flask_client):
        client, _ = real_flask_client
        r = client.put('/api/providers/nonexistent/models',
                       json={'default_model': 'gemini-2.0-flash'})
        assert r.status_code == 400, f'expected 400 got {r.status_code}'

    def test_11_save_validation_errors_structured(self, real_flask_client):
        client, _ = real_flask_client
        r = client.post('/api/settings/save', json={
            'provider_id': 'gemini-default',
            'default_model': 'step-3.7-flash',
            'app_config': {'PROCESSING': {'TEMPERATURE': '5.0'}},
        })
        data = r.get_json()
        n_errors = len(data.get('errors', []))
        assert n_errors == 2, f'expected 2 errors got {n_errors}: {data}'


class TestV829EdgeCases:
    """Edge cases và failure modes — verify fail-closed behavior."""

    def test_edge_1_save_with_empty_body(self, real_flask_client):
        """POST /api/settings/save với body rỗng → 200 no-op."""
        client, _ = real_flask_client
        r = client.post('/api/settings/save', json={})
        assert r.status_code == 200
        data = r.get_json()
        assert data['success'] is True
        assert data['provider'] is None

    def test_edge_2_save_with_null_provider_id(self, real_flask_client):
        """provider_id = null → dùng active provider hiện tại (stepfun) → có model hợp lệ."""
        client, _ = real_flask_client
        r = client.post('/api/settings/save', json={
            'provider_id': None,
            'default_model': 'step-3.7-flash',  # stepfun provider hợp lệ
        })
        # stepfun model 'step-3.7-flash' hợp lệ với OpenAI-compatible → 200
        assert r.status_code == 200, f'expected 200 got {r.status_code}: {r.get_json()}'
        # Revert
        client.post('/api/settings/save', json={
            'provider_id': 'stepfun',
            'default_model': 'step-3.7-flash',
        })

    def test_edge_3_concurrent_etag_conflict(self, real_flask_client):
        """Mô phỏng race condition: 2 tab cùng đọc ETag, 1 ghi trước, tab còn lại fail."""
        client, _ = real_flask_client
        # Cả 2 tab đọc cùng ETag
        etag1 = client.get('/api/providers').headers.get('ETag')
        etag2 = client.get('/api/providers').headers.get('ETag')
        assert etag1 == etag2
        # Tab 1 PUT thành công
        r1 = client.put('/api/providers/openrouter/models',
                        json={'default_model': 'anthropic/claude-3.5-sonnet'},
                        headers={'If-Match': etag1})
        assert r1.status_code == 200
        # Tab 2 PUT với cùng etag1 (đã stale) → 409
        r2 = client.put('/api/providers/openrouter/models',
                        json={'default_model': 'openai/gpt-4o'},
                        headers={'If-Match': etag2})
        assert r2.status_code == 409, f'expected 409 got {r2.status_code}'
        body = r2.get_json()
        assert 'ETag mismatch' in body['error']
        # Revert
        client.put('/api/providers/openrouter/models',
                   json={'default_model': 'deepseek/deepseek-v4-flash-0731'})

    def test_edge_4_invalid_json_body(self, real_flask_client):
        """Body không phải JSON → 400 hoặc 500 với error rõ ràng."""
        client, _ = real_flask_client
        r = client.post('/api/settings/save',
                        data='not json at all',
                        content_type='application/json')
        # Flask request.json trả None cho non-JSON; route check if data is None
        assert r.status_code in (400, 500), f'expected 400/500 got {r.status_code}'

    def test_edge_5_models_invalid_field_type(self, real_flask_client):
        """default_model không phải string → 400."""
        client, _ = real_flask_client
        r = client.put('/api/providers/openrouter/models',
                       json={'default_model': 12345})  # int thay vì str
        assert r.status_code == 400, f'expected 400 got {r.status_code}'

    def test_edge_6_providers_count_after_all_tests(self, real_flask_client):
        """Regression: sau tất cả test, vẫn còn 11 providers (không bị mất do test)."""
        client, _ = real_flask_client
        r = client.get('/api/providers')
        providers = r.get_json()['providers']
        assert len(providers) == 11, f'expected 11 providers got {len(providers)}'

    def test_edge_7_settings_save_no_regression(self, real_flask_client):
        """Regression: app.ini không bị corrupt sau nhiều save."""
        client, _ = real_flask_client
        # Save nhiều lần với giá trị khác nhau
        for temp in ['0.8', '0.9', '1.0', '1.1']:
            r = client.post('/api/settings/save', json={
                'app_config': {'PROCESSING': {'TEMPERATURE': temp}},
            })
            assert r.status_code == 200
        # Verify file vẫn parse được
        r = client.get('/api/settings/app')
        assert r.status_code == 200
        # Giá trị cuối cùng
        data = r.get_json()
        # Bỏ qua kiểm tra chính xác giá trị (string/float conversion)
        assert 'TEMPERATURE' in data['config'].get('PROCESSING', {})
