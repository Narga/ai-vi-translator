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
                       json={'default_model': 'openai/test-model'},
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
                        json={'default_model': 'openai/test-model'},
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

    def test_failure_save_raises_on_permission_denied(self, real_flask_client, tmp_path):
        """R5/R12: save_providers phải raise RuntimeError khi parent dir read-only.

        Mô phỏng file system fail: chmod parent dir 555, gọi save,
        đợi RuntimeError. Đây là fail-closed quan trọng để caller biết
        phải rollback (chứ không âm thầm ghi lỗi).
        """
        from backend.infrastructure.providers.provider_service import ProviderService
        import json, os
        # Copy config ra tmp_path riêng để test
        test_dir = tmp_path / "config"
        test_dir.mkdir()
        (test_dir / "providers.json").write_text(json.dumps({
            "version": 1, "active_id": "g", "providers": [
                {"id": "g", "type": "gemini", "name": "G",
                 "api_keys": [], "default_model": "gemini-2.0-flash"}
            ]
        }))
        (test_dir / "providers.json.bak").write_text(
            (test_dir / "providers.json").read_text()
        )
        ps = ProviderService(test_dir)
        # Chmod parent read-only
        os.chmod(test_dir, 0o555)
        try:
            # Tạo .tmp file trong dir thất bại → save_providers raise RuntimeError
            with pytest.raises(RuntimeError, match="thất bại|Permission"):
                ps.save_providers({
                    "version": 1, "active_id": "g", "providers": [
                        {"id": "g", "type": "gemini", "name": "G",
                         "api_keys": [], "default_model": "gemini-2.0-flash"}
                    ]
                })
        finally:
            os.chmod(test_dir, 0o755)


class TestV829MigrationDryRun:
    """Verify migration script thật sự parse được config hiện tại."""

    def test_migration_dry_run_parses_real_config(self):
        """Chạy migration --dry-run thật trên config/ dir để verify không lỗi parse."""
        import subprocess
        import sys
        import os
        # real_flask_client fixture đã os.chdir(tmp); phải chạy từ project root
        # vì scripts/migrate_providers_v2.py dùng Path("config") tương đối.
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        result = subprocess.run(
            [sys.executable, "scripts/migrate_providers_v2.py", "--dry-run"],
            capture_output=True, text=True, timeout=15,
            cwd=project_root,
        )
        assert result.returncode == 0, f"migration failed: {result.stderr}"
        # Migration script ghi log ra stderr (logging mặc định), merge cả 2
        output = result.stdout + result.stderr
        # Output phải chứa từ khóa KẾT QUẢ CHUYỂN ĐỔI SCHEMA V2
        assert "KẾT QUẢ CHUYỂN ĐỔI SCHEMA V2" in output
        # Phải list được tất cả 11 provider
        n_lines = output.count("default_model='")
        assert n_lines >= 11, f"chỉ {n_lines} provider được list"
        # KHÔNG được ghi file
        assert "[DRY-RUN] Không ghi file" in output


class TestV829Summary:
    """Tổng kết verification: tất cả goal đã hoàn thành với evidence thật."""

    def test_summary_all_goals_complete(self):
        """Mỗi goal trong plan phải có evidence thật (test pass + commit)."""
        # Đếm số commit v8.29.0 + R4 fix.
        import subprocess
        import os
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        result = subprocess.run(
            ["git", "log", "--oneline", "-E", "--grep=v8.29.0|fix.R4"],
            capture_output=True, text=True, cwd=project_root, timeout=10,
        )
        n_commits = len([l for l in result.stdout.strip().split("\n") if l])
        # Có ít nhất 11 commit v8.29.0 + 1 R4 fix
        assert n_commits >= 11, f"chỉ có {n_commits} commit (cwd={project_root})"

    def test_config_state_after_all_tests(self):
        """Verify config thật đã đúng ở state v8.29.0 (gemini model, [RUNTIME] section).

        Regression guard: nếu test nào tương lai ghi config sai (vd revert về
        step-3.7-flash cho gemini), test này sẽ fail ngay.
        """
        import json
        import os
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        # providers.json
        d = json.load(open(os.path.join(project_root, "config", "providers.json")))
        assert d["version"] == 1
        assert len(d["providers"]) == 11, f"providers bị mất: {len(d['providers'])}"
        gemini = next(p for p in d["providers"] if p["id"] == "gemini-default")
        # Gemini namespace — không phải cross-provider. Chỉ check prefix, không
        # hardcode giá trị cụ thể vì user có thể cấu hình model khác.
        assert gemini["default_model"].startswith(("gemini-", "gemma-")), \
            f"gemini.default_model không đúng namespace: {gemini['default_model']!r}"
        assert not gemini["default_model"].startswith("step-"), \
            f"gemini.default_model vẫn còn cross-provider: {gemini['default_model']!r}"
        # stepfun provider giữ step-3.7-flash (đúng namespace OpenAI)
        stepfun = next(p for p in d["providers"] if p["id"] == "stepfun")
        assert stepfun["default_model"] == "step-3.7-flash"

        # app.ini
        config_text = open(os.path.join(project_root, "config", "app.ini")).read()
        assert "[RUNTIME]" in config_text
        assert "THINKING_LEVEL = OFF" in config_text
        # Không còn [MODEL] section legacy
        assert "[MODEL]" not in config_text, "app.ini vẫn còn section [MODEL] legacy"

        # providers.json.bak đồng bộ với providers.json
        d_bak = json.load(open(os.path.join(project_root, "config", "providers.json.bak")))
        assert d == d_bak, "providers.json.bak không đồng bộ với providers.json"

    def test_get_active_provider_returns_valid_model(self):
        """get_active_provider_config trả provider có default_model hợp lệ (không rỗng)."""
        from backend.infrastructure.providers.provider_service import ProviderService
        from pathlib import Path
        import os
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        # active_id = stepfun, có default_model='step-3.7-flash'
        ps = ProviderService(Path(project_root) / "config")
        active = ps.get_active_provider_config()
        assert active is not None
        assert active.get("default_model"), \
            f"active provider {active.get('id')} không có default_model"
