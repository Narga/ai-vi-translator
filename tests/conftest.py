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
