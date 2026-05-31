# tests/unit/test_workspace_services.py
# Unit tests cho Phase 06: Workspace, Project, FileDiscovery Services

import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestWorkspaceServiceImport:
    """Test import WorkspaceService."""

    def test_import(self):
        """Test import WorkspaceService."""
        from backend.infrastructure.workspace.workspace_service import WorkspaceService
        assert WorkspaceService is not None

    def test_create_instance(self):
        """Test tạo WorkspaceService instance."""
        from backend.infrastructure.workspace.workspace_service import WorkspaceService
        service = WorkspaceService()
        assert service is not None


class TestWorkspaceServiceMethods:
    """Test các methods của WorkspaceService."""

    def test_get_workspace_root(self):
        """Test get_workspace_root trả về Path."""
        from backend.infrastructure.workspace.workspace_service import WorkspaceService
        service = WorkspaceService()
        root = service.get_workspace_root()
        assert isinstance(root, Path)

    def test_get_projects_root(self):
        """Test get_projects_root trả về Path."""
        from backend.infrastructure.workspace.workspace_service import WorkspaceService
        service = WorkspaceService()
        root = service.get_projects_root()
        assert isinstance(root, Path)
        assert root.name == "projects"

    def test_get_logs_dir(self):
        """Test get_logs_dir trả về Path."""
        from backend.infrastructure.workspace.workspace_service import WorkspaceService
        service = WorkspaceService()
        logs = service.get_logs_dir()
        assert isinstance(logs, Path)
        assert logs.name == "logs"

    def test_get_cache_dir(self):
        """Test get_cache_dir trả về Path."""
        from backend.infrastructure.workspace.workspace_service import WorkspaceService
        service = WorkspaceService()
        cache = service.get_cache_dir()
        assert isinstance(cache, Path)
        assert cache.name == "cache"

    def test_is_valid_project_slug(self):
        """Test is_valid_project_slug."""
        from backend.infrastructure.workspace.workspace_service import WorkspaceService
        service = WorkspaceService()
        assert service.is_valid_project_slug("my-project") is True
        assert service.is_valid_project_slug("") is False
        assert service.is_valid_project_slug("../etc") is False
        assert service.is_valid_project_slug("foo/bar") is False

    def test_project_exists(self):
        """Test project_exists trả về bool."""
        from backend.infrastructure.workspace.workspace_service import WorkspaceService
        service = WorkspaceService()
        result = service.project_exists("default-project")
        assert isinstance(result, bool)

    def test_ensure_workspace_structure(self, tmp_path):
        """Test ensure_workspace_structure tạo dirs."""
        from backend.infrastructure.workspace.workspace_service import WorkspaceService
        service = WorkspaceService(workspace_dir=tmp_path)
        service.ensure_workspace_structure()

        assert (tmp_path / "projects").exists()
        assert (tmp_path / "logs").exists()
        assert (tmp_path / "cache").exists()
        assert (tmp_path / "checkpoints").exists()
        assert (tmp_path / "prompts").exists()
        assert (tmp_path / "archive").exists()


class TestProjectServiceImport:
    """Test import ProjectService."""

    def test_import(self):
        """Test import ProjectService."""
        from backend.infrastructure.workspace.project_service import ProjectService
        assert ProjectService is not None

    def test_create_instance(self):
        """Test tạo ProjectService instance."""
        from backend.infrastructure.workspace.project_service import ProjectService
        service = ProjectService()
        assert service is not None


class TestProjectServiceMethods:
    """Test các methods của ProjectService."""

    def test_list_projects(self):
        """Test list_projects trả về list."""
        from backend.infrastructure.workspace.project_service import ProjectService
        service = ProjectService()
        projects = service.list_projects()
        assert isinstance(projects, list)

    def test_project_exists(self):
        """Test project_exists trả về bool."""
        from backend.infrastructure.workspace.project_service import ProjectService
        service = ProjectService()
        result = service.project_exists("default-project")
        assert isinstance(result, bool)

    def test_load_project_meta(self):
        """Test load_project_meta trả về dict hoặc None."""
        from backend.infrastructure.workspace.project_service import ProjectService
        service = ProjectService()
        meta = service.load_project_meta("default-project")
        if meta is not None:
            assert isinstance(meta, dict)
            assert "name" in meta
            assert "slug" in meta

    def test_get_project_stats(self):
        """Test get_project_stats trả về dict."""
        from backend.infrastructure.workspace.project_service import ProjectService
        service = ProjectService()
        stats = service.get_project_stats("default-project")
        assert isinstance(stats, dict)
        assert "source_count" in stats
        assert "translated_count" in stats

    def test_create_and_delete_project(self, tmp_path):
        """Test tạo và xóa project."""
        from backend.infrastructure.workspace.project_service import ProjectService
        service = ProjectService(workspace_dir=tmp_path)

        # Tạo project
        result = service.create_project("Test Project", "Test description")
        assert result["success"] is True
        slug = result["slug"]
        assert slug == "test-project"

        # Verify project tồn tại
        assert service.project_exists(slug) is True

        # Load meta
        meta = service.load_project_meta(slug)
        assert meta is not None
        assert meta["name"] == "Test Project"

        # Delete project
        service.delete_project(slug)
        assert service.project_exists(slug) is False

    def test_update_project_meta(self, tmp_path):
        """Test update_project_meta."""
        from backend.infrastructure.workspace.project_service import ProjectService
        service = ProjectService(workspace_dir=tmp_path)

        # Tạo project
        result = service.create_project("Update Test")
        slug = result["slug"]

        # Update meta
        updated = service.update_project_meta(slug, {"description": "New description"})
        assert updated is not None
        assert updated["description"] == "New description"

        # Cleanup
        service.delete_project(slug)

    def test_update_file_status(self, tmp_path):
        """Test update_file_status."""
        from backend.infrastructure.workspace.project_service import ProjectService
        service = ProjectService(workspace_dir=tmp_path)

        # Tạo project
        result = service.create_project("Status Test")
        slug = result["slug"]

        # Update file status
        file_status = service.update_file_status(slug, "test.txt", "Xong")
        assert file_status["test.txt"] == "Xong"

        # Cleanup
        service.delete_project(slug)

    def test_ensure_default_project(self, tmp_path):
        """Test ensure_default_project."""
        from backend.infrastructure.workspace.project_service import ProjectService
        service = ProjectService(workspace_dir=tmp_path)

        service.ensure_default_project()
        assert service.project_exists("default-project") is True


class TestFileDiscoveryServiceImport:
    """Test import FileDiscoveryService."""

    def test_import(self):
        """Test import FileDiscoveryService."""
        from backend.infrastructure.workspace.file_discovery_service import FileDiscoveryService
        assert FileDiscoveryService is not None

    def test_create_instance(self):
        """Test tạo FileDiscoveryService instance."""
        from backend.infrastructure.workspace.file_discovery_service import FileDiscoveryService
        service = FileDiscoveryService()
        assert service is not None


class TestFileDiscoveryServiceMethods:
    """Test các methods của FileDiscoveryService."""

    def test_find_input_files_empty(self, tmp_path):
        """Test find_input_files với thư mục rỗng."""
        from backend.infrastructure.workspace.file_discovery_service import FileDiscoveryService
        service = FileDiscoveryService()

        input_dir = tmp_path / "input"
        input_dir.mkdir()

        files = service.find_input_files(input_dir)
        assert isinstance(files, list)
        assert len(files) == 0

    def test_find_input_files_with_txt(self, tmp_path):
        """Test find_input_files với file .txt."""
        from backend.infrastructure.workspace.file_discovery_service import FileDiscoveryService
        service = FileDiscoveryService()

        input_dir = tmp_path / "input"
        input_dir.mkdir()

        # Tạo file test
        (input_dir / "file1.txt").write_text("content1")
        (input_dir / "file2.txt").write_text("content2")
        (input_dir / "file3.md").write_text("content3")  # Không phải .txt

        files = service.find_input_files(input_dir)
        assert len(files) == 2

    def test_find_input_files_not_exist(self, tmp_path):
        """Test find_input_files với thư mục không tồn tại."""
        from backend.infrastructure.workspace.file_discovery_service import FileDiscoveryService
        service = FileDiscoveryService()

        input_dir = tmp_path / "nonexistent"
        files = service.find_input_files(input_dir)
        assert len(files) == 0

    def test_merge_small_files_empty(self):
        """Test merge_small_files với list rỗng."""
        from backend.infrastructure.workspace.file_discovery_service import FileDiscoveryService
        service = FileDiscoveryService()

        files = service.merge_small_files([])
        assert len(files) == 0

    def test_merge_small_files_single(self, tmp_path):
        """Test merge_small_files với 1 file."""
        from backend.infrastructure.workspace.file_discovery_service import FileDiscoveryService
        service = FileDiscoveryService()

        f = tmp_path / "test.txt"
        f.write_text("content")

        files = service.merge_small_files([f])
        assert len(files) == 1
        assert files[0] == f

    def test_get_file_info(self, tmp_path):
        """Test get_file_info."""
        from backend.infrastructure.workspace.file_discovery_service import FileDiscoveryService
        service = FileDiscoveryService()

        f = tmp_path / "test.txt"
        f.write_text("test content")

        info = service.get_file_info(f)
        assert info["exists"] is True
        assert info["name"] == "test.txt"
        assert info["size"] > 0

    def test_get_file_info_not_exist(self, tmp_path):
        """Test get_file_info với file không tồn tại."""
        from backend.infrastructure.workspace.file_discovery_service import FileDiscoveryService
        service = FileDiscoveryService()

        f = tmp_path / "nonexistent.txt"
        info = service.get_file_info(f)
        assert info["exists"] is False

    def test_list_files_in_directory(self, tmp_path):
        """Test list_files_in_directory."""
        from backend.infrastructure.workspace.file_discovery_service import FileDiscoveryService
        service = FileDiscoveryService()

        # Tạo files
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")
        (tmp_path / ".hidden").write_text("hidden")

        # Không include hidden
        files = service.list_files_in_directory(tmp_path, include_hidden=False)
        assert len(files) == 2

        # Include hidden
        files = service.list_files_in_directory(tmp_path, include_hidden=True)
        assert len(files) == 3
