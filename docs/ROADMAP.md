# RoadMap - Lộ trình phát triển Content Translator

Tài liệu này theo dõi các giai đoạn phát triển của dự án, tập trung vào tính ổn định, trải nghiệm người dùng và sức mạnh AI.

---

## ✅ Giai đoạn 1-5: Hoàn thiện nền tảng (Đã xong)
- [x] Tái cấu trúc WebUI thành Blueprints
- [x] Tích hợp Multi-Provider AI (Gemini & OpenAI)
- [x] Hệ thống quản lý dự án (Project-based Workspace)
- [x] Tối ưu hóa UI Dashboard với Tachyons Card-style
- [x] Hệ thống lưu trữ (Archiving System) chuyên nghiệp

---

## ✅ Giai đoạn 6: Nâng cao trải nghiệm & Tiện ích (Đã xong)

### 📊 6.1 Dashboard & Monitoring
- [x] Thống kê hệ thống chi tiết (Active/Archived projects, Cache)
- [x] Hover tooltips, cải thiện tốc độ render bảng file lớn

### 🏗️ 6.5 Refactoring & Assets
- [x] Hệ thống 7-Tab UI, di chuyển dữ liệu vào `assets/`, tinh gọn prompt

### ⚙️ 6.6-6.8 UI/UX Polish & AI Resilience
- [x] Consolidated Project Modal, Scroll Fix, API Resilience Overhaul
- [x] Multi-Prompt System, Real-time Progress Logs, UI Polish

### 🛡️ 6.9 Remediation & Modularization
- [x] Security Hardening (Path Traversal, Host binding)
- [x] OCR Engine Decomposition (7.7k→modules), Cache Modernization (pickle→JSON)
- [x] UI/UX Remediation (HTML fixes, 5-Tab, Persistence, Smart Merge)

---

## ✅ Giai đoạn 7: Backend Separation & UI Redesign (v7.0.0 — Đã xong)

### 🏗️ 7.0 Backend Separation — Hexagonal Architecture
- [x] Package `backend/`: Application/Domain/Infrastructure/Facade layers
- [x] 8 services: AppConfig, ApiKey, Prompt, Provider, ModelCatalog, Workspace, Project, FileDiscovery
- [x] 3 use cases: TranslateText, TranslateProjectFiles, SpellcheckProjectFiles
- [x] Progress Event System (ProgressEventType + ProgressMapper)
- [x] WebUIProgressBridge, SettingsFacade, RuntimeState singleton
- [x] CLI decoupling (bỏ `sys.argv` manipulation), WebUI route refactors

### 🎨 7.1 UI/UX Redesign — Slate & Indigo Theme
- [x] Hệ màu Slate & Indigo, header nền trắng, emoji cleanup
- [x] Segmented Control cho provider, stats panel với dấu chấm màu

### 🧪 7.2 Test Suite (158 tests)
- [x] Smoke tests (CLI, WebUI) + Unit tests (8 suites)
- [x] Fixtures: temp dirs, mock config, mock files, platform adaptive

---

## ✅ Giai đoạn 7.3: Provider Management & Frontend Optimization (v7.3.0 — Đã xong)

### 🔧 7.3.1 Provider Single Source of Truth
- [x] `providers.json` là nguồn duy nhất cho tất cả provider configs
- [x] Migration một chiều từ `API.txt` + `app.ini` → `providers.json`
- [x] Atomic write (`os.replace` + `shutil.move` fallback)
- [x] Bảo vệ `gemini-default` — không cho xóa
- [x] API mới: `/api/providers` (GET/POST/PUT/DELETE) + `/api/providers/select`

### 🎨 7.3.2 Config Tab Rebuild
- [x] Dropdown chọn OpenAI provider + nút Xóa
- [x] Input "Nhà cung cấp mẫu hình" + nút Thêm/Sửa
- [x] Auto-fill Tên + API Key + Base URL khi chọn provider
- [x] Đổi "QA Model" → "Review Model", ẩn vào Advanced
- [x] Đưa Chunk Size ra khỏi Advanced
- [x] Sửa click handler: input/textarea không trigger toast

### 🐛 7.3.3 Bug Fixes (12 lỗi)
- [x] Nav bar stats không hiển thị (loadProjects → loadProjectCards)
- [x] Ctrl+S / AutoSave targets sai element ID
- [x] PromptManager load/save project prompts sai ID
- [x] deleteGenre ref null element
- [x] switchProvider CSS class sai
- [x] 12 hàm ProjectManager bị thiếu
- [x] Archive restore/delete không hoạt động
- [x] Syntax error do code thừa sau consolidate

### ✂️ 7.3.4 Frontend Optimization (-331 dòng)
- [x] Consolidate loadFile/renderFile/showPanel functions
- [x] Xóa 50 global wrapper functions → direct Module.method()
- [x] Xóa ~200 dòng dead code (CSS + JS)
- [x] Inline styles → CSS classes
- [x] Modal z-index → CSS variables
- [x] Button styling consolidation
- [x] Modals hợp nhất vào 1 file

### 📦 7.3.5 Archive System Enhancements (v7.3.1 — Đã xong)
- [x] API `GET /api/archive/<filename>/download` tải về tệp lưu trữ an toàn (chống path traversal)
- [x] Nút "Tải về" trực tiếp từ danh sách lưu trữ và thẻ dự án
- [x] Hộp thoại xác nhận ghi đè (Overwrite) hoặc sao chép (Copy) khi tệp lưu trữ trùng tên


### 🚀 7.4 Refactoring & Provider Routing (v7.4.0 — Đã xong)
- [x] Provider Routing (7.4.0): Active provider được truyền chính xác khi dịch và soát lỗi
- [x] Nút Làm mới (Refresh) cho Quản lý dự án
- [x] HTML `<template>` Refactor: Chống XSS, code sạch hơn
- [x] Legacy Route Cleanup (7.4.1): Xoá `/api/translate`, `/api/provider`
- [x] Helper Normalization (7.4.1): `get_default_model()` đọc từ `ProviderService`
- [x] Chunk API Integration (7.4.1): Frontend gọi `POST /api/projects/<slug>/chunk/<filename>` thay vì chỉ hiển thị modal
- [x] Ẩn file log `_info.txt` (7.4.1): Không hiển thị file log spellcheck trong danh sách đã soát

---

## 🎯 Giai đoạn 8: Cải tiến & Tính năng mới (Next)

### ✅ Đã hoàn thành (v7.5.0)
- [x] **Sửa lỗi API Key Invalid**: Xử lý key bị từ chối, cooldown 24 giờ, tie-break round-robin
- [x] **File Selection & Deletion Fix**: `data-filename` attribute, escapeHtml an toàn, xoá source/translated
- [x] **Tab State Preservation**: Giữ trạng thái mini-tab (Bản dịch/Đã soát) khi reload workspace
- [x] **Provider Routing Fix**: Shim `/api/provider`, sửa `switchProvider()`/`initProvider()` dùng `/api/providers/*`, `loadModels()` endpoint thống nhất
- [x] **Nút xóa tab Biên tập**: `deleteSelectedSourceFiles()` + SVG icon xóa
- [x] **Generate tab Thông tin**: Dropdown source file, `aiGenerateFromInfoTab()`, `saveGuidelineFromInfoTab()`, response mở rộng (`content`, `asset_file`)
- [x] **ProjectContextService**: Service đọc `style_guide.txt` + `summary.txt` từ assets, chèn vào prompt dịch qua placeholder hoặc fallback append
- [x] **ProjectContextService Unit Tests**: 9 tests cho load_context và render_prompt

### ✅ Đã hoàn thành (v7.6.0)
- [x] **Xóa Translation Cache**: Xóa `services/cache_service.py`, loại bỏ toàn bộ logic cache
- [x] **Force Retranslate**: Checkbox "Dịch lại từ đầu", executor bỏ qua checkpoint/TM
- [x] **Clear Project TM**: API `POST /api/projects/<slug>/tm/clear` + nút "Xóa TM dự án"
- [x] **Frontend Improvements**: Select all checkbox, batch delete, project card redesign, tab state preservation

### ✅ Đã hoàn thành (v7.7.0)
- [x] **Hợp nhất giao diện Biên tập & Kiểm chính tả**: Workspace thống nhất, sidebar 3 mini-tab (Nội dung nguồn, Bản dịch, Soát chính tả)
- [x] **Xoá sidebar spellcheck riêng**: `#pm-spell-file-sidebar`, các hàm JavaScript không dùng
- [x] **Toolbar & Icons mới**: Nút soát lỗi đã chọn, CSS tooltip scoped, icon A kèm dấu tích
- [x] **Đặt lại bộ nhớ dịch**: Đổi tên + confirm message mới cho nút Clear TM

### ✅ Đã hoàn thành (v7.8.0)
- [x] **Tái cấu trúc Plugin Navigation**: Xoá thẻ "Công cụ", chuyển EPUB Converter & OCR Reader thành workspace tabs
- [x] **Quản lý Plugin**: Khối quản lý plugin trong tab Cấu hình, bật/tắt, phân loại Core vs Tool
- [x] **PluginManager ES Module**: `plugin-manager.js` mới + `PluginBase`/`ConverterPlugin` interfaces
- [x] **Backend Plugin Routes**: Routes project-scoped cho EPUB/OCR, `config/plugins.json`, middleware kiểm tra trạng thái
- [x] **Plugin Integration Regression Fixes**: Sửa Alpine store, lifecycle, tab UI, API URL, backend execution

### ✅ Đã hoàn thành (v7.9.0)
- [x] **Tiền xử lý HTML/XHTML sang Markdown**: Module `core/source_normalizer.py` bóc tách body, convert ruby `漢字《かな》`, giữ nguyên `<u>` và dọn dẹp rác CSS offline.
- [x] **API Route & UI Integration**: POST API `/api/projects/<slug>/convert-markdown`, thêm nút bấm Chuyển Markdown hàng loạt và nút đơn lẻ tại mini toolbar của từng file.
- [x] **Cải tiến Sidebar & Status Bar**: Cấu trúc lại metadata dòng file tránh xô lệch layout, sửa lỗi checkbox chọn/bỏ chọn tất cả hoạt động sai, và hiển thị file đang mở trên status bar dưới cùng.

### 🔴 Cần làm (tương lai)
- [ ] **Unit Tests**: executor force_retranslate, route tm/clear, route translate with force_retranslate
- [ ] **Plugin Manager Unit Tests**: test toggle, list, enabled/disabled workflow

### 📋 Ưu tiên trung bình (tương lai)
- [ ] **Interactive Glossary**: Highlight thuật ngữ glossary trong Editor, cho phép áp dụng nhanh
- [ ] **Batch Progress UI**: Thanh tiến độ tổng thể khi dịch nhiều file
- [ ] **Prompt Versioning**: Lưu lịch sử các phiên bản prompt của dự án
- [ ] **EPUB/HTML Fidelity Pipeline**: Dịch bảo toàn cấu trúc DOM, ảnh và CSS
- [ ] **Sync Scroll**: Đồng bộ cuộn giữa editor trái và phải
- [ ] **Workspace tab content/file**: Restore lại nội dung/tập tin của workspace tab khi chuyển đổi tab chính

### 📋 Ưu tiên thấp (tương lai)
- [ ] **Local LLM Integration**: Kết nối Ollama/LocalAI
- [ ] **Agentic Post-Editing**: AI tự động rà soát bản dịch sau hoàn tất
- [ ] **Multi-Language Expansion**: Hỗ trợ Anh-Việt, Nhật-Việt

---

## ✅ Giai đoạn 7.1: Project Management & Workspace UI (v7.1.0 — Đã xong)

### 🎨 7.1.1 Project Management Tab
- [x] Tab "Quản lý dự án" độc lập trên navigation bar
- [x] Form tạo dự án: Tên tác phẩm, Tác giả, Thể loại, Mô tả
- [x] Danh sách dự án dạng card với thông tin đầy đủ
- [x] Import/Export dự án qua file zip
- [x] Tự động xác định trạng thái dự án

### 🖥️ 7.1.2 Workspace 3-Column Layout
- [x] Layout 3 cột: File list | Source editor | Translation editor
- [x] Tab Bản gốc/Bản dịch trong file list
- [x] Tab Chưa soát/Đã soát trong Kiểm chính tả
- [x] Ẩn/hiện cột với co giãn tự động
- [x] Token estimate real-time

### ⚡ 7.1.3 UX Enhancements
- [x] SVG icons thay thế emoji
- [x] Auto-save cho editor Bản dịch
- [x] Phím tắt Ctrl+S
- [x] Drag-and-drop upload
- [x] Spell Log Panel collapsible

### 🔧 7.1.4 Frontend Modularization
- [x] Tách main.js thành 6 ES modules
- [x] Namespace pattern cho tất cả modules
- [x] Alpine.js integration

---

## ✅ Giai đoạn 7.2: Bug Fixes & UX Improvements (v7.2.0 — Đã xong)

### 🐛 7.2.1 Model Loading & API Consistency
- [x] Xử lý danh sách models rỗng — không giữ models cũ
- [x] Đồng bộ `/api/openai/models` trả về `default` + `provider`
- [x] Tự động tải models sau khi lưu cấu hình OpenAI

### 🖥️ 7.2.2 Diff View Enhancement
- [x] Thêm chế độ xem Ngang (Side-by-side)
- [x] Nút chuyển đổi Dọc/Ngang

### 🔧 7.2.3 Project Manager & Translation Worker
- [x] Khôi phục các hàm thao tác file bị thiếu
- [x] Drag-and-drop cho spellcheck sidebar
- [x] Nút "Hoàn thành" đóng modal + auto-close 5 giây

### 🔌 7.2.4 Plugin & Backend Fixes
- [x] Sửa lỗi tham số `model_name` → `model` trong spellchecker
- [x] Tab switching tự động tải dữ liệu (prompts, API keys)

---

*Cập nhật lần cuối: 2026-07-10 (v7.9.0)
