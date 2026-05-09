# Báo cáo Rà soát Cấu trúc Thư mục & Tập tin ngoài Dự án

Ngày: 09/05/2026 | Phiên bản: 1.0

## 1. Tổng quan
Hiện tại, ngoài mã nguồn chính của dự án Novel-Translator, trong thư mục gốc còn tồn tại nhiều tập tin và thư mục phục vụ cho các công cụ AI IDE (Claude Code, Antigravity), quản lý ngữ cảnh (ACMS), và các công cụ bổ trợ (GitNexus, Ruff, Stylelint).

Tài liệu này phân loại và đề xuất phương án xử lý để giữ cho kho lưu trữ (repository) sạch sẽ và đúng tiêu chuẩn.

---

## 2. Danh sách các Tập tin & Thư mục ngoài Dự án

| Tên | Phân loại | Thuộc về | Chức năng | Đề xuất |
| :--- | :--- | :--- | :--- | :--- |
| `.acms/` | Metadata | Antigravity (ACMS) | Lưu trữ ngữ cảnh và checkpoints | **Gitignore** (Đã có) |
| `.agent/` | Config/Logs | AI Agent | Lưu trữ trạng thái phiên làm việc của Agent | **Gitignore** (Đã có) |
| `.agents/` | Skill Modules | AI Agent (Skills) | Chứa mã nguồn các kỹ năng bổ trợ (cavecrew, gitnexus) | **Giữ lại & Gitignore** |
| `.claude/` | Config | Claude Code | Cấu hình và dữ liệu của IDE Claude Code | **Thêm vào Gitignore** |
| `.gitnexus/` | Index | GitNexus Tool | Chỉ mục đồ thị kiến thức mã nguồn | **Gitignore** (Đã có) |
| `.ruff_cache/`| Cache | Ruff Linter | Bộ nhớ đệm của công cụ kiểm tra mã nguồn Python | **Thêm vào Gitignore** |
| `.venv/` | Environment | Python Project | Môi trường ảo chứa các thư viện dependencies | **Gitignore** (Đã có) |
| `AGENTS.md` | Documentation | AI Agent / Skills | Hướng dẫn sử dụng các kỹ năng của Agent | **Giữ lại** (Tài liệu dự án) |
| `CLAUDE.md` | Documentation | Claude Code | Quy tắc và chỉ dẫn cho Claude Code | **Giữ lại** (Tài liệu dự án) |
| `skills-lock.json`| Metadata | Skills/Agent | File khóa phiên bản của các kỹ năng AI | **Thêm vào Gitignore** |
| `package-lock.json`| Lock file | Node.js Tooling | Quản lý phiên bản cho các công cụ JS (GitNexus) | **Giữ lại** (Nếu dùng tool cục bộ) |
| `.DS_Store` | System Junk | macOS | File rác hệ thống của macOS | **Gitignore** (Đã có) |

---

## 3. Đánh giá cụ thể

### 3.1 Nhóm Công cụ AI (Antigravity/Claude Code)
- **.acms, .agent, .agents, skills-lock.json**: Đây là "hệ sinh thái" hỗ trợ AI hiểu và tương tác với dự án. 
  - *Vấn đề:* `skills-lock.json` và `.agents` hiện đang hiện diện nhưng chưa được đưa vào `.gitignore` một cách nhất quán (hoặc mới được thêm vào nhưng chưa commit).
  - *Đề xuất:* Đưa toàn bộ vào `.gitignore` để tránh gây nhiễu cho mã nguồn chính, trừ các file `.md` cần thiết cho hướng dẫn.

### 3.2 Nhóm Tooling & Cache
- **.ruff_cache**: Đây là dữ liệu tạm, tuyệt đối không nên đưa vào Git.
- **.claude**: Chứa dữ liệu riêng của phiên làm việc Claude, không mang giá trị dự án chung.
- **.venv**: Môi trường cục bộ của từng máy developer, đã có `requirements.txt` và `pyproject.toml` để tái tạo.

---

## 4. Đề xuất cập nhật .gitignore

Cần bổ sung các dòng sau vào tệp `.gitignore` để tối ưu hóa:

```gitignore
# AI IDE & Agent Tooling
.claude/
.agents/
skills-lock.json

# Linter caches
.ruff_cache/
.stylelint_cache/
```

## 5. Các tập tin cần loại bỏ (Cleanup)
Nếu các tập tin sau không được sử dụng bởi các thành viên khác trong nhóm, có thể cân nhắc loại bỏ để làm gọn thư mục gốc:
- `package-lock.json` (Nếu GitNexus và các tool JS được cài đặt global hoặc qua npx mà không cần node_modules cục bộ).
- `eslint.config.mjs` (Nếu dự án không thực sự thực hiện linting cho Javascript một cách hệ thống).

---
*Báo cáo được tạo bởi Antigravity Agent - 09/05/2026*
