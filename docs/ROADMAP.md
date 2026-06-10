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
- [x] Sửa lỗi Provider Routing: Active provider được truyền chính xác khi dịch và soát lỗi, thay vì luôn dùng Gemini.
- [x] Nút Làm mới (Refresh) cho Quản lý dự án để tải lại danh sách dễ dàng.
- [x] HTML `<template>` Refactor: Chuyển đổi nối chuỗi HTML trong thẻ sang JS template để chống XSS và giữ code sạch.

---

## 🎯 Giai đoạn 8: Cải tiến & Tính năng mới (Next)

### Ưu tiên cao
- [ ] **Interactive Glossary**: Highlight thuật ngữ glossary trong Editor, cho phép áp dụng nhanh
- [ ] **Batch Progress UI**: Thanh tiến độ tổng thể khi dịch nhiều file
- [x] **HTML \<template\> Refactor**: Thay thế nối chuỗi HTML trong JS bằng thẻ `<template>`

### Ưu tiên trung bình
- [ ] **Prompt Versioning**: Lưu lịch sử các phiên bản prompt của dự án
- [ ] **EPUB/HTML Fidelity Pipeline**: Dịch bảo toàn cấu trúc DOM, ảnh và CSS
- [ ] **Sync Scroll**: Đồng bộ cuộn giữa editor trái và phải

### Ưu tiên thấp
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

*Cập nhật lần cuối: 2026-06-10*
