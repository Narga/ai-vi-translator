"""Unit tests cho ProjectContextService."""

import pytest
from pathlib import Path
from backend.infrastructure.config.project_context_service import ProjectContextService


@pytest.fixture
def tmp_project(tmp_path):
    """Tạo project dir tạm."""
    assets = tmp_path / "assets"
    assets.mkdir()
    return tmp_path


@pytest.fixture
def service():
    return ProjectContextService()


class TestLoadContext:
    def test_empty_assets(self, service, tmp_project):
        ctx = service.load_context(tmp_project)
        assert ctx == {}

    def test_reads_style_guide(self, service, tmp_project):
        (tmp_project / "assets" / "style_guide.txt").write_text("Dùng tone trang trọng")
        ctx = service.load_context(tmp_project)
        assert ctx["translation_guidelines"] == "Dùng tone trang trọng"

    def test_reads_summary(self, service, tmp_project):
        (tmp_project / "assets" / "summary.txt").write_text("Câu chuyện về...")
        ctx = service.load_context(tmp_project)
        assert ctx["project_summary"] == "Câu chuyện về..."

    def test_skips_empty_file(self, service, tmp_project):
        (tmp_project / "assets" / "style_guide.txt").write_text("   ")
        ctx = service.load_context(tmp_project)
        assert "translation_guidelines" not in ctx

    def test_skips_comment_template(self, service, tmp_project):
        (tmp_project / "assets" / "style_guide.txt").write_text("# Template comment only")
        ctx = service.load_context(tmp_project)
        assert "translation_guidelines" not in ctx


class TestRenderPrompt:
    def test_no_context(self, service):
        prompt = "Dịch văn bản sau:"
        result = service.render_prompt(prompt, {})
        assert result == prompt

    def test_placeholder_replaced(self, service):
        prompt = "Hướng dẫn: {translation_guidelines}\n\nDịch:"
        ctx = {"translation_guidelines": "Dùng tone nhẹ nhàng"}
        result = service.render_prompt(prompt, ctx)
        assert "Dùng tone nhẹ nhàng" in result
        assert "{translation_guidelines}" not in result

    def test_project_context_placeholder(self, service):
        prompt = "Context: {project_context}\n\nDịch:"
        ctx = {"translation_guidelines": "Tone X", "project_summary": "Summary Y"}
        result = service.render_prompt(prompt, ctx)
        assert "Tone X" in result
        assert "Summary Y" in result
        assert "{project_context}" not in result

    def test_fallback_append(self, service):
        prompt = "Dịch văn bản sau:"
        ctx = {"translation_guidelines": "Tone trang trọng"}
        result = service.render_prompt(prompt, ctx)
        assert result.startswith("Dịch văn bản sau:")
        assert "Tone trang trọng" in result
        assert "# Hướng dẫn phong cách" in result
