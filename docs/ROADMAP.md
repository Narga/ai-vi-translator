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

## 🎯 Giai đoạn 8: Cải tiến & Tính năng mới (Next)

### Ưu tiên cao
- [ ] **Frontend Modularization**: Tách `main.js` (~3.4k lines) → ES modules (projects.js, editor.js, api-client.js, ui-handlers.js)
- [ ] **Interactive Glossary**: Highlight thuật ngữ glossary trong Editor, cho phép áp dụng nhanh
- [ ] **Batch Progress UI**: Thanh tiến độ tổng thể khi dịch nhiều file

### Ưu tiên trung bình
- [ ] **HTML \<template\> Refactor**: Thay thế nối chuỗi HTML trong JS bằng thẻ `<template>`
- [ ] **Prompt Versioning**: Lưu lịch sử các phiên bản prompt của dự án
- [ ] **EPUB/HTML Fidelity Pipeline**: Dịch bảo toàn cấu trúc DOM, ảnh và CSS

### Ưu tiên thấp
- [ ] **Local LLM Integration**: Kết nối Ollama/LocalAI
- [ ] **Agentic Post-Editing**: AI tự động rà soát bản dịch sau hoàn tất
- [ ] **Multi-Language Expansion**: Hỗ trợ Anh-Việt, Nhật-Việt

---
*Cập nhật lần cuối: 2026-05-31*
