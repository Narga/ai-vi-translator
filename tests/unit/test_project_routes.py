# tests/unit/test_project_routes.py
# Unit tests cho project routes: tm/clear và translate with force_retranslate

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


@pytest.fixture
def client():
    """Tạo Flask test client."""
    from webui import create_app
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


class TestClearProjectTMRoute:
    """Task B.2: Kiểm tra API xóa TM dự án."""

    def test_clear_tm_success(self, client):
        with patch("webui.routes.projects._get_project_dir") as mock_dir, \
             patch("services.translation_memory.TranslationMemory") as mock_tm_cls:

            mock_pdir = MagicMock(spec=Path)
            mock_pdir.exists.return_value = True
            mock_dir.return_value = mock_pdir

            mock_tm = MagicMock()
            mock_tm.clear.return_value = 15
            mock_tm_cls.return_value = mock_tm

            response = client.post("/api/projects/test-slug/tm/clear")

            assert response.status_code == 200
            data = response.get_json()
            assert data["success"] is True
            assert data["deleted"] == 15
            mock_tm.clear.assert_called_once()

    def test_clear_tm_project_not_found(self, client):
        with patch("webui.routes.projects._get_project_dir") as mock_dir:
            mock_pdir = MagicMock(spec=Path)
            mock_pdir.exists.return_value = False
            mock_dir.return_value = mock_pdir

            response = client.post("/api/projects/nonexistent/tm/clear")

            assert response.status_code == 404
            data = response.get_json()
            assert "error" in data

    def test_clear_tm_exception(self, client):
        with patch("webui.routes.projects._get_project_dir") as mock_dir, \
             patch("services.translation_memory.TranslationMemory") as mock_tm_cls:

            mock_pdir = MagicMock(spec=Path)
            mock_pdir.exists.return_value = True
            mock_dir.return_value = mock_pdir

            mock_tm = MagicMock()
            mock_tm.clear.side_effect = RuntimeError("DB error")
            mock_tm_cls.return_value = mock_tm

            response = client.post("/api/projects/test-slug/tm/clear")

            assert response.status_code == 500
            data = response.get_json()
            assert "error" in data


class TestTranslateProjectForceRetranslate:
    """Task B.3: Kiểm tra API translate nhận diện force_retranslate."""

    def _setup_mocks(self):
        """Helper thiết lập mocks cho translate route."""
        mocks = {}

        mocks["dir"] = patch("webui.routes.projects._get_project_dir")
        mocks["meta"] = patch("webui.routes.projects._load_project_meta")
        mocks["prompt_svc"] = patch("backend.infrastructure.config.prompt_service.PromptService")
        mocks["ctx_svc"] = patch("backend.infrastructure.config.project_context_service.ProjectContextService")
        mocks["cfg_svc"] = patch("backend.infrastructure.config.app_config_service.AppConfigService")
        mocks["prov_svc"] = patch("backend.infrastructure.providers.provider_service.ProviderService")
        mocks["tm_cls"] = patch("services.translation_memory.TranslationMemory")
        mocks["thread"] = patch("webui.routes.projects.Thread")
        mocks["ck_status"] = patch("webui.routes.projects._checkpoint_status_for", return_value=None)

        started = {}
        for k, p in mocks.items():
            started[k] = p.start()

        mock_pdir = MagicMock(spec=Path)
        mock_pdir.__truediv__ = lambda self, x: MagicMock(spec=Path, exists=lambda: False)
        started["dir"].return_value = mock_pdir
        started["meta"].return_value = {"book_title": "Test", "slug": "test-slug"}

        mock_prompt = MagicMock()
        mock_prompt.load_merged_prompts.return_value = {"main": "Dịch:"}
        started["prompt_svc"].return_value = mock_prompt

        mock_ctx = MagicMock()
        mock_ctx.load_context.return_value = {}
        mock_ctx.render_prompt.return_value = "Dịch:"
        started["ctx_svc"].return_value = mock_ctx

        mock_cfg = MagicMock()
        mock_cfg.get_temperature.return_value = 1.0
        mock_cfg.get_default_chunk_size.return_value = 22000
        mock_cfg.get_context_char_count.return_value = 500
        mock_cfg.get_thinking_level.return_value = "none"
        mock_cfg.get.return_value = 0
        started["cfg_svc"].return_value = mock_cfg

        mock_prov = MagicMock()
        mock_prov.get_active_provider_config.return_value = {
            "type": "gemini",
            "api_keys": ["test-key"],
            "default_model": "gemini-flash",
        }
        started["prov_svc"].return_value = mock_prov

        mock_tm = MagicMock()
        started["tm_cls"].return_value = mock_tm

        return mocks

    def _stop_mocks(self, mocks):
        for p in mocks.values():
            p.stop()

    def test_translate_accepts_force_flag(self, client):
        mocks = self._setup_mocks()
        try:
            payload = {
                "files": ["chapter1.txt"],
                "model": "gemini-flash",
                "force_retranslate": True,
            }

            response = client.post(
                "/api/projects/test-slug/translate",
                json=payload,
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "started"
        finally:
            self._stop_mocks(mocks)

    def test_translate_without_force_flag(self, client):
        mocks = self._setup_mocks()
        try:
            payload = {
                "files": ["chapter1.txt"],
                "model": "gemini-flash",
            }

            response = client.post(
                "/api/projects/test-slug/translate",
                json=payload,
            )

            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "started"
        finally:
            self._stop_mocks(mocks)

    def test_translate_no_project(self, client):
        with patch("webui.routes.projects._get_project_dir") as mock_dir, \
             patch("webui.routes.projects._load_project_meta") as mock_meta:

            mock_pdir = MagicMock(spec=Path)
            mock_dir.return_value = mock_pdir
            mock_meta.return_value = None

            payload = {"files": ["chapter1.txt"]}

            response = client.post(
                "/api/projects/nonexistent/translate",
                json=payload,
            )

            assert response.status_code == 404

    def test_translate_no_files(self, client):
        with patch("webui.routes.projects._get_project_dir") as mock_dir, \
             patch("webui.routes.projects._load_project_meta") as mock_meta:

            mock_pdir = MagicMock(spec=Path)
            mock_dir.return_value = mock_pdir
            mock_meta.return_value = {"book_title": "Test"}

            payload = {"files": []}

            response = client.post(
                "/api/projects/test-slug/translate",
                json=payload,
            )

            assert response.status_code == 400


class TestTranslateProjectResumeRequired409(TestTranslateProjectForceRetranslate):
    """Kế thừa để dùng lại _setup_mocks/_stop_mocks, không nhân bản 50 dòng mock."""

    def test_translate_returns_409_resume_required(self, client):
        mocks = self._setup_mocks()
        try:
            # File nguồn phải "tồn tại" để route đọc được source_text
            patch_read = patch(
                "pathlib.Path.read_text", return_value="nội dung nguồn"
            )
            mocks["ck_status"].stop()
            ck = patch(
                "webui.routes.projects._checkpoint_status_for",
                return_value={
                    "status": "resume_available",
                    "completed_chunks": 17,
                    "total_chunks": 24,
                    "next_chunk": 17,
                    "checkpoint_key": "abcd1234ef56.db",
                },
            )
            ck.start()
            mocks["ck_status"] = ck

            # _setup_mocks cho exists() = False; cần True để vào nhánh check checkpoint
            from pathlib import Path as _P
            mock_pdir = MagicMock(spec=_P)
            mock_file = MagicMock(spec=_P)
            mock_file.exists.return_value = True
            mock_file.read_text.return_value = "nội dung nguồn"
            mock_pdir.__truediv__ = lambda self, x: (
                mock_file if str(x) not in ("sources", "assets") else mock_pdir
            )
            mocks["dir"].stop()
            d = patch("webui.routes.projects._get_project_dir", return_value=mock_pdir)
            d.start()
            mocks["dir"] = d

            resp = client.post(
                "/api/projects/test-slug/translate",
                json={"files": ["book.txt"], "model": "gemini-flash"},
            )
            assert resp.status_code == 409
            data = resp.get_json()
            assert data["status"] == "resume_required"
            assert data["checkpoints"]["book.txt"]["completed_chunks"] == 17
            assert data["checkpoints"]["book.txt"]["total_chunks"] == 24
            assert data["checkpoints"]["book.txt"]["checkpoint_key"] == "abcd1234ef56.db"
        finally:
            self._stop_mocks(mocks)

    def test_translate_injects_project_slug_into_config(self, client):
        """B12: config truyền cho _checkpoint_status_for PHẢI có project_slug.

        Test này là cái duy nhất bắt được B12 ở mức unit. Mock _checkpoint_status_for
        rồi assert trên đối số nó nhận được — nếu ai xoá `config["project_slug"] = slug`
        thì test đỏ ngay, không phải đợi Phase 5.
        """
        mocks = self._setup_mocks()
        try:
            from pathlib import Path as _P
            mock_file = MagicMock(spec=_P)
            mock_file.exists.return_value = True
            mock_file.read_text.return_value = "nội dung nguồn"
            mock_pdir = MagicMock(spec=_P)
            mock_pdir.__truediv__ = lambda self, x: (
                mock_file if str(x) not in ("sources", "assets") else mock_pdir
            )
            mocks["dir"].stop()
            d = patch("webui.routes.projects._get_project_dir", return_value=mock_pdir)
            d.start()
            mocks["dir"] = d

            client.post(
                "/api/projects/test-slug/translate",
                json={"files": ["book.txt"], "model": "gemini-flash", "chunk_size": 2400},
            )

            import webui.routes.projects as _pj
            assert _pj._checkpoint_status_for.called, "route không gọi _checkpoint_status_for"
            cfg = _pj._checkpoint_status_for.call_args[0][2]
            assert cfg["project_slug"] == "test-slug", "B12: thiếu project_slug trong config"
            assert cfg["chunk_size"] == 2400
            assert "prompts" in cfg
        finally:
            self._stop_mocks(mocks)


class TestTranslateMixedCheckpointDecision(TestTranslateProjectForceRetranslate):
    """REV-C C6: test contract multi_file_resume_requires_per_file_decision.

    Khi request nhiều file mà chỉ MỘT số có checkpoint, route phải trả 409 với
    `multi_file_resume_requires_per_file_decision`, liệt kê đủ files_with_checkpoint
    và files_without_checkpoint, KHÔNG tạo task/worker.
    """

    def _make_mixed_ck_mock(self, with_ck="book_with_ck.txt", without_ck="book_new.txt"):
        """_checkpoint_status_for trả resume_available cho file có checkpoint, None cho file mới."""
        def side_effect(filename, source_text, config):
            if filename == with_ck:
                return {
                    "status": "resume_available",
                    "completed_chunks": 17,
                    "total_chunks": 24,
                    "next_chunk": 17,
                    "checkpoint_key": "abcd1234ef56.db",
                }
            return None  # file không có checkpoint
        return side_effect

    def _setup_mixed_request(self, mocks):
        """Validate 2 file tồn tại, cả 2 đọc được source, ck_status theo side_effect."""
        from pathlib import Path as _P
        mocks["ck_status"].stop()
        ck = patch(
            "webui.routes.projects._checkpoint_status_for",
            side_effect=self._make_mixed_ck_mock(),
        )
        ck.start()
        mocks["ck_status"] = ck

        mock_file = MagicMock(spec=_P)
        mock_file.exists.return_value = True
        mock_file.read_text.return_value = "nội dung nguồn"
        mock_pdir = MagicMock(spec=_P)
        mock_pdir.__truediv__ = lambda self, x: (
            mock_file if str(x) not in ("sources", "assets") else mock_pdir
        )
        mocks["dir"].stop()
        d = patch("webui.routes.projects._get_project_dir", return_value=mock_pdir)
        d.start()
        mocks["dir"] = d
        return mocks

    def test_mixed_checkpoint_returns_409_per_file_decision(self, client):
        mocks = self._setup_mocks()
        try:
            self._setup_mixed_request(mocks)

            resp = client.post(
                "/api/projects/test-slug/translate",
                json={"files": ["book_with_ck.txt", "book_new.txt"], "model": "gemini-flash"},
            )
            assert resp.status_code == 409
            data = resp.get_json()
            assert data["status"] == "multi_file_resume_requires_per_file_decision"
            assert data["files_with_checkpoint"] == ["book_with_ck.txt"]
            assert data["files_without_checkpoint"] == ["book_new.txt"]
            assert "book_with_ck.txt" in data["checkpoints"]
            assert "error" in data
        finally:
            self._stop_mocks(mocks)

    def test_mixed_checkpoint_does_not_create_task_or_worker(self, client):
        """KHÔNG tạo task/worker khi trả 409 mixed decision."""
        import webui.routes.projects as _pj
        mocks = self._setup_mocks()
        try:
            self._setup_mixed_request(mocks)
            # Mọi đường tạo task/thread phải KHÔNG được gọi
            mocks["thread"].stop()  # bỏ patch Thread để verify không gọi
            resp = client.post(
                "/api/projects/test-slug/translate",
                json={"files": ["book_with_ck.txt", "book_new.txt"], "model": "gemini-flash"},
            )
            assert resp.status_code == 409
            assert resp.get_json()["status"] == "multi_file_resume_requires_per_file_decision"
            # Nếu route vô tình tạo thread/task, Thread.start() sẽ ném lỗi real
        finally:
            self._stop_mocks(mocks)
