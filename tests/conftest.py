# tests/conftest.py
# Shared fixtures cho test suite

import sys
import pytest
from pathlib import Path

# Đảm bảo project root trong sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def project_root():
    """Trả về Path của project root."""
    return PROJECT_ROOT


@pytest.fixture
def config_dir(project_root):
    """Trả về Path của config directory."""
    return project_root / "config"


@pytest.fixture
def workspace_dir(project_root):
    """Trả về Path của workspace directory."""
    return project_root / "workspace"


@pytest.fixture
def app_config_path(config_dir):
    """Trả về Path của app.ini."""
    return config_dir / "app.ini"


@pytest.fixture
def flask_app():
    """Tạo Flask app cho testing."""
    from webui import create_app
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def flask_client(flask_app):
    """Tạo Flask test client."""
    return flask_app.test_client()


# ============================================================
# P0 harness (append 2026-08-16) — cancel scoped / resume / recovery
# `pytest`, `Path`, `sys.path.insert(PROJECT_ROOT)` đã có ở đầu file; không import lại.
# ⚠️ KHÔNG dùng fixture `workspace_dir`/`flask_app`/`flask_client` sẵn có trong các test P0:
#    `workspace_dir` trỏ workspace THẬT và `flask_app` gọi create_app() (chạy startup scan +
#    ghi vào workspace/tasks.db thật). Test P0 chỉ dùng `tmp_path` + `sync_app`.
# ============================================================
import re as _re

from services.checkpoint_service import CheckpointService
from services.task_store import TaskStore

# Chunker legacy: process_text_for_chunking(text, min_chars=size-2000, max_chars=size).
# Đã kiểm chứng bằng chính chunker: 24 câu x 1207 ký tự + chunk_size=2400 → ĐÚNG 24 chunk,
# mỗi chunk 1 câu (không gộp, không cắt). ĐỪNG đổi 2 hằng số này nếu không chạy lại kiểm chứng.
E2E_CHUNK_SIZE = 2400
E2E_TOTAL_CHUNKS = 24


def make_chunked_source(n: int = E2E_TOTAL_CHUNKS, body_chars: int = 1200) -> str:
    """Sinh source ép chunker tạo ĐÚNG n chunk, mỗi chunk mang nhãn SEG{index:03d}.

    Mỗi block là MỘT câu (kết thúc bằng '.', không có dấu câu bên trong) dài ~1207 ký tự:
      - < max_chars (2400) → không rơi vào fallback intelligent_chunking
      - 2 block = 2415 > 2400 → không bao giờ gộp 2 block vào 1 chunk
      - > min_chars*0.3 = 120 → không bị hậu xử lý "gộp chunk nhỏ"
    KHÔNG dùng chữ "CHUNK" trong nhãn: test đếm marker "[CHUNK n CHƯA DỊCH …]" bằng
    text.count("CHUNK") nên nhãn nguồn phải không chứa chuỗi đó.
    """
    filler = ("ma " * (body_chars // 3)).strip()
    return "\n\n".join(f"SEG{i:03d} {filler}." for i in range(n))


def make_fake_robust_translate(sent_log, fail_at=None, fail_once=True,
                               fail_status="censorship_blocked"):
    """Fake cho `core.executor.robust_translate` — KHÔNG gọi mạng.

    Chữ ký thật (core/executor.py:659) gọi bằng keyword:
        robust_translate(original_chunk=…, api_manager=…, prompts=…,
                         config_params=…, previous_chunk_context=…)
    → trả về tuple (result, status, api_key_used). Nhận **kwargs để không vỡ nếu
    executor thêm tham số.

    `fail_once=True` (mặc định) là BẮT BUỘC cho luồng 451→recovery: nếu fail vĩnh viễn
    tại `fail_at` thì lần recovery sẽ fail lại đúng chunk đó và task recovery không bao
    giờ `completed` (đây chính là lỗi B8 của bản nháp).
    """
    state = {"failed": False}

    def fake_rt(original_chunk=None, api_manager=None, prompts=None,
                config_params=None, previous_chunk_context="", **kwargs):
        m = _re.search(r"SEG(\d+)", original_chunk or "")
        idx = int(m.group(1)) if m else -1
        sent_log.append(idx)
        if fail_at is not None and idx == fail_at and not (fail_once and state["failed"]):
            state["failed"] = True
            return None, fail_status, "key-451"
        return f"[dịch {idx}]", "success", "key-ok"

    return fake_rt


@pytest.fixture
def rt_reset():
    """Reset singleton RuntimeState + TaskRegistry trước/sau mỗi test."""
    from backend.infrastructure.progress.runtime_state import RuntimeState
    from backend.infrastructure.progress.task_registry import TaskRegistry

    TaskRegistry._instance = None
    RuntimeState.reset()
    yield
    TaskRegistry._instance = None
    RuntimeState.reset()


@pytest.fixture
def task_store(tmp_path):
    return TaskStore(str(tmp_path / "ws"))


@pytest.fixture
def checkpoint_service(tmp_path):
    return CheckpointService(str(tmp_path / "ws" / "checkpoints"))


class FakeProvider:
    """Provider config giả cho route translate/recovery (không gọi mạng).

    `base_url` phải là host thật trong `classify_endpoint` (api.openai.com → NativeOpenAIPolicy)
    và model phải qua `validate_model` (đã kiểm chứng: "gpt-test" hợp lệ).
    """

    CONFIG = {
        "type": "openai",
        "api_key": "test-key",
        "gateway_api_key": "",
        "credential_mode": "default",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-test",
        "id": "openai-test",
        "name": "OpenAI Test",
    }

    def get_active_provider_config(self):
        return dict(self.CONFIG)

    def get_provider_by_id(self, provider_id):
        return dict(self.CONFIG)


@pytest.fixture
def fake_provider():
    return FakeProvider()


def bind_tmp_task_store(monkeypatch, workspace_dir):
    """Gắn TaskStore/TaskRegistry vào tmp workspace và CẮT mọi đường ghi vào DB thật.

    ⚠️ `webui/routes/tasks.py` tạo `registry = TaskRegistry(store=_get_task_store())` ở
    MODULE LEVEL. Vì TaskRegistry là singleton, sau khi ta set `_instance = None` và tạo
    instance mới, biến `webui.routes.tasks.registry` VẪN trỏ tới instance cũ đang gắn
    `workspace/tasks.db` THẬT — mọi POST /api/tasks/<id>/cancel trong test sẽ ghi vào dữ
    liệu thật. Phải patch cả biến module đó (đây là điều bản nháp thiếu).
    """
    from backend.infrastructure.progress.task_registry import TaskRegistry

    TaskRegistry._instance = None
    tmp_store = TaskStore(str(workspace_dir))
    registry = TaskRegistry(store=tmp_store)
    monkeypatch.setenv("WORKSPACE_DIR", str(workspace_dir))
    monkeypatch.setattr("webui.routes.tasks._task_store", tmp_store, raising=False)
    monkeypatch.setattr("webui.routes.tasks._get_task_store", lambda: tmp_store)
    monkeypatch.setattr("webui.routes.tasks.registry", registry)
    return tmp_store, registry


@pytest.fixture
def sync_app(tmp_path, monkeypatch):
    """Flask app tối thiểu (projects_bp + tasks_bp + translation_bp) trỏ tới tmp_path.

    TRÁNH create_app() thật vì nó chạy startup scan và tạo DB trong workspace thật.
    Tất cả route tạo TaskStore/CheckpointService qua _get_workspace_dir/_get_checkpoint_dir
    nên chỉ cần patch 2 hàm đó + _get_project_dir.

    Trả về: (client, tmp_store, ws, proj)
    """
    from flask import Flask

    from webui.routes.projects import projects_bp
    from webui.routes.tasks import tasks_bp
    from webui.routes.translation import translation_bp

    ws = tmp_path / "ws"
    ck_dir = ws / "checkpoints"
    proj = tmp_path / "proj"
    ck_dir.mkdir(parents=True, exist_ok=True)
    (proj / "sources").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr("webui.routes.projects._get_checkpoint_dir", lambda: str(ck_dir))
    monkeypatch.setattr("webui.routes.projects._get_workspace_dir", lambda: str(ws))
    monkeypatch.setattr("webui.routes.projects._get_project_dir", lambda slug: proj)

    tmp_store, _registry = bind_tmp_task_store(monkeypatch, ws)

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(projects_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(translation_bp)

    return app.test_client(), tmp_store, ws, proj


class SyncThread:
    """Thread chạy inline — dùng để test route mà worker hoàn tất ngay trong request.

    Chỉ nhận các tham số mà production đang dùng (`target`, `args`, `daemon`).
    `join()`/`is_alive()` được cung cấp để route nào gọi cancel-and-wait (Phase 3) vẫn chạy.
    """

    def __init__(self, target=None, args=(), kwargs=None, daemon=None):
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}
        self._done = False

    def start(self):
        if self._target:
            self._target(*self._args, **self._kwargs)
        self._done = True

    def join(self, timeout=None):
        return None

    def is_alive(self):
        return False
