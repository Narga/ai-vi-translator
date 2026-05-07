# Kế Hoạch Tái Cấu Trúc Tab "Thông Tin"

> Tạo: 2026-05-07 | Status: Draft | Priority: High

---

## 1. Đánh Giá Hiện Trạng

### 1.1 Cấu trúc tab hiện tại (8 tab ngang hàng)

```
📄 Nội dung gốc  →  Editor side-by-side (source + result)
📚 Bản dịch      →  Editor side-by-side (translated-source + translated-result)
🖊️ Hướng dẫn     →  AI toolbar + textarea (guide-style-guide)
👥 Mối quan hệ   →  AI toolbar + textarea (guide-relationship)
📖 Thuật ngữ     →  AI toolbar + textarea (guide-glossary)
🎯 Chỉ dẫn       →  Sub-tabs (radio): Dịch thuật | Tóm tắt | Quan hệ | Thuật ngữ | Chính tả
📋 Tóm tắt       →  AI toolbar + textarea (guide-summary)
🔤 Chính tả      →  Editor side-by-side (spell-source + spell-result) + info panel
```

### 1.2 Vấn đề nhận diện

| # | Vấn đề | Chi tiết |
|---|--------|----------|
| 1 | **5 tab "phẳng" lặp cấu trúc** | Hướng dẫn, Mối quan hệ, Thuật ngữ, Tóm tắt — mỗi tab là 1 AI toolbar + 1 textarea. Giống nhau ~95%. |
| 2 | **Tab Chính tả khác biệt** | Có editor side-by-side + info panel, không cùng mẫu với 4 tab trên. |
| 3 | **Thanh tab quá dài** | 8 nút gây chật chội, người dùng phải cuộn ngang. |
| 4 | **Nhầm lẫn giữa Prompt và Content** | Tab 🎯 Chỉ dẫn có sub-tab "Quan hệ/Thuật ngữ/Tóm tắt" — trùng tên với tab riêng. Người dùng dễ nhầm "nên sửa ở đâu". |
| 5 | **Thiếu Wrap/Find trên tab Bản dịch** | Tab 📚 Bản dịch textarea nguồn không có toolbar (line 142-144), trong khi tab Nội dung gốc và Chính tả đều có. |

### 1.3 So sánh 3 editor side-by-side

| Feature | Nội dung gốc | Bản dịch | Chính tả |
|---------|:-----------:|:--------:|:--------:|
| Source toolbar | ✅ Wrap, Find | ❌ Không | ✅ Wrap, Find |
| Result toolbar | ✅ Diff, Wrap, Find, Lưu | ✅ Diff, Lưu | ✅ Diff, Wrap, Find, Lưu |
| Token bar đầy đủ | ✅ char + word + tokens + model | ✅ char + word + tokens + model | ❌ char + tokens (thiếu word) |
| Info panel | ❌ | ❌ | ✅ spell-info-text |
| Bảng file có checkbox | ✅ | ❌ | ✅ |

---

## 2. Thiết Kế Đề Xuất

### 2.1 Cấu trúc tab mới (5 tab)

```
📄 Nội dung gốc  →  Không đổi
📚 Bản dịch      →  Không đổi
📋 Thông tin     →  NEW: Sub-tabs (radio-based như Chỉ dẫn)
                     ├── 🖊️ Hướng dẫn
                     ├── 👥 Mối quan hệ
                     ├── 📖 Thuật ngữ
                     └── 📋 Tóm tắt
🎯 Chỉ dẫn       →  Không đổi (giữ nguyên sub-tabs hiện tại)
🔤 Chính tả      →  Không đổi
```

**Tại sao tách Chính tả riêng?**
- Cấu trúc khác hẳn (editor side-by-side + info panel vs chỉ textarea đơn)
- Workflow khác: chọn file → soát lỗi → xem kết quả → lưu
- Không có AI Generate toolbar

### 2.2 Ưu điểm

| Tiêu chí | Trước | Sau |
|---------|-------|-----|
| Số tab cấp 1 | 8 | 5 (-37.5%) |
| Tab lặp cấu trúc | 4 tab rời rạc | Gộp thành 1 tab cha + sub-tabs |
| Nhầm lẫn Prompt vs Content | Cao (trùng tên) | Thấp (rõ ràng: Chỉ dẫn = prompt, Thông tin = data) |
| Cuộn ngang thanh tab | Có (8 nút) | Không (5 nút) |

### 2.3 Template chung cho sub-tab "Thông tin"

Mỗi sub-tab sẽ có cùng mẫu:

```html
<div id="ptab-info-{name}" class="nt-ptab-content dn flex-auto flex flex-column overflow-hidden pa3">
    <div class="flex items-center gap-2 mb3 pa2 bg-near-white br2 ba b--black-05">
        <span class="f7 fw6 gray mr2">✨ AI Generate:</span>
        <select id="{name}-model" class="f7 ba b--black-10 br2 ph2 bg-white outline-0 flex-auto" style="height:28px">
            <option value="">— Chọn Model —</option>
        </select>
        <button class="pointer ph3 pv1 f7 bn white bg-purple br2 fw6 nowrap" onclick="aiGenerateContent('{name}')">✨ Generate</button>
        <button class="pointer ph3 pv1 f7 bn white bg-green br2 fw6" onclick="saveGuidelineField('{name}')">💾 Lưu</button>
    </div>
    <textarea id="guide-{name}" class="ba b--black-10 br2 pa3 w-100 f7 lh-copy outline-0 flex-auto" style="min-height:400px; resize:vertical" placeholder="..."></textarea>
</div>
```

---

## 3. Kế Hoạch Triển Khai

### Phase 1: Gộp 4 tab vào "Thông tin" (4 tasks)

| Task | Mô tả | File | Dòng ước tính |
|------|-------|------|--------------|
| **1.1** | Thêm tab button "📋 Thông tin" vào thanh project tabs | `tab_workspace.html` | ~1 dòng |
| **1.2** | Tạo container `#ptab-info` với radio-based sub-tabs (Hướng dẫn, Mối quan hệ, Thuật ngữ, Tóm tắt) | `tab_workspace.html` | ~40 dòng |
| **1.3** | Di chuyển nội dung 4 tab cũ vào sub-tabs mới (giữ nguyên IDs để JS không đổi) | `tab_workspace.html` | ~40 dòng |
| **1.4** | Xóa 4 tab button cũ (style-guide, relationship, glossary, summary) | `tab_workspace.html` | -4 dòng |

### Phase 2: Đồng nhất editor Bản dịch (2 tasks)

| Task | Mô tả | File | Dòng ước tính |
|------|-------|------|--------------|
| **2.1** | Thêm toolbar Wrap + Find cho textarea nguồn của tab Bản dịch | `tab_workspace.html:142-144` | +10 dòng |
| **2.2** | Bổ sung word count vào token bar của tab Chính tả | `tab_workspace.html:362-363` | +1 dòng |

### Phase 3: CSS DRY (1 task)

| Task | Mô tả | File | Dòng ước tính |
|------|-------|------|--------------|
| **3.1** | Tạo `.editor-container`, `.editor-pane`, `.editor-toolbar` classes thay inline styles | `style.css` | ~30 dòng |

### Phase 4: Cập nhật JS (2 tasks)

| Task | Mô tả | File | Dòng ước tính |
|------|-------|------|--------------|
| **4.1** | Cập nhật `switchProjectTab()` để xử lý tab "info" và sub-tabs | `main.js` | ~10 dòng |
| **4.2** | Load models cho các dropdown trong tab Thông tin | `main.js` | ~10 dòng |

---

## 4. Chi Tiết Phase 1 — Gộp tab "Thông tin"

### 4.1 Tab button mới (thay thế 4 button cũ)

**Xóa:**
```html
<button ... data-ptab="style-guide">🖊️ Hướng dẫn</button>
<button ... data-ptab="relationship">👥 Mối quan hệ</button>
<button ... data-ptab="glossary">📖 Thuật ngữ</button>
<button ... data-ptab="summary">📋 Tóm tắt</button>
```

**Thêm:**
```html
<button class="tab-btn ph3 pv3 pointer f7 fw6 tracked uppercase bg-transparent bn gray bb b--transparent nowrap" data-ptab="info" onclick="switchProjectTab('info')">📋 Thông tin</button>
```

### 4.2 Container sub-tabs "Thông tin"

```html
<div id="ptab-info" class="nt-ptab-content dn flex-auto flex flex-column overflow-hidden pa3">
    <!-- Radio inputs -->
    <input class="nt-tab-radio" type="radio" name="info-tabs" id="info-tab-style-guide" checked>
    <input class="nt-tab-radio" type="radio" name="info-tabs" id="info-tab-relationship">
    <input class="nt-tab-radio" type="radio" name="info-tabs" id="info-tab-glossary">
    <input class="nt-tab-radio" type="radio" name="info-tabs" id="info-tab-summary">

    <!-- Tab nav -->
    <div class="nt-tab-nav flex bb b--black-10 mb3 flex-wrap flex-shrink-0" role="tablist">
        <label for="info-tab-style-guide" class="nt-tab-label dib ph3 pv2 gray f7 fw6 tracked uppercase pointer">🖊️ Hướng dẫn</label>
        <label for="info-tab-relationship" class="nt-tab-label dib ph3 pv2 gray f7 fw6 tracked uppercase pointer">👥 Mối quan hệ</label>
        <label for="info-tab-glossary" class="nt-tab-label dib ph3 pv2 gray f7 fw6 tracked uppercase pointer">📖 Thuật ngữ</label>
        <label for="info-tab-summary" class="nt-tab-label dib ph3 pv2 gray f7 fw6 tracked uppercase pointer">📋 Tóm tắt</label>
    </div>

    <!-- Tab panels -->
    <div class="nt-tab-panels flex-auto">
        <!-- Style Guide -->
        <section id="info-panel-style-guide" class="nt-tab-panel h-100">
            <div class="flex items-center gap-2 mb3 pa2 bg-near-white br2 ba b--black-05">
                <span class="f7 fw6 gray mr2">✨ AI Generate:</span>
                <select id="style-guide-model" class="f7 ba b--black-10 br2 ph2 bg-white outline-0 flex-auto" style="height:28px">
                    <option value="">— Chọn Model —</option>
                </select>
                <button class="pointer ph3 pv1 f7 bn white bg-purple br2 fw6 nowrap" onclick="aiGenerateContent('style_guide')">✨ Generate</button>
                <button class="pointer ph3 pv1 f7 bn white bg-green br2 fw6" onclick="saveGuidelineField('style_guide')">💾 Lưu</button>
            </div>
            <textarea id="guide-style-guide" class="ba b--black-10 br2 pa3 w-100 f7 lh-copy outline-0 flex-auto" style="min-height:400px; resize:vertical" placeholder="Mô tả tone, phong cách dịch..."></textarea>
        </section>

        <!-- Relationship -->
        <section id="info-panel-relationship" class="nt-tab-panel h-100">
            <!-- Tương tự, giữ nguyên IDs guide-relationship, relationship-model -->
        </section>

        <!-- Glossary -->
        <section id="info-panel-glossary" class="nt-tab-panel h-100">
            <!-- Tương tự, giữ nguyên IDs guide-glossary, glossary-model -->
        </section>

        <!-- Summary -->
        <section id="info-panel-summary" class="nt-tab-panel h-100">
            <!-- Tương tự, giữ nguyên IDs guide-summary, summary-model -->
        </section>
    </div>
</div>
```

### 4.3 CSS cần thêm

```css
/* Info tab sub-tabs — reuse existing nt-tab-radio/nt-tab-label pattern */
/* Không cần CSS mới vì đã có từ tab Chỉ dẫn */
```

### 4.4 JS cần cập nhật

```javascript
// Trong loadProjectGuidelines() hoặc init():
// Đảm bảo load models cho các dropdown trong tab info
// (style-guide-model, relationship-model, glossary-model, summary-model)
// → Đã có trong loadModels() hiện tại, chỉ cần đảm bảo selector không đổi

// switchProjectTab('info') → hiện #ptab-info, ẩn các tab khác
// → Đã xử lý bởi switchProjectTab() hiện tại (dùng data-ptab attribute)
```

---

## 5. Rủi Ro & Giảm Thiểu

| Rủi ro | Khả năng | Tác động | Giảm thiểu |
|--------|----------|----------|------------|
| JS không load được model dropdowns sau khi move | Thấp | Medium | Giữ nguyên IDs, chỉ thay đổi wrapper HTML |
| Mất dữ liệu khi chuyển tab | Rất thấp | High | Không touch database/API, chỉ thay UI structure |
| Người dùng quen với tab cũ | Trung bình | Low | Icon + tên giữ nguyên, chỉ thay vị trí |
| CSS conflict với sub-tabs Chỉ dẫn | Thấp | Medium | Dùng namespace riêng: `info-tabs` vs `project-prompt-tabs` |

---

## 6. Thứ Tự Thực Hiện Khuyến Nghị

```
Phase 1 (1.1 → 1.4): Gộp tab "Thông tin"
    ↓
Phase 2 (2.1 → 2.2): Đồng nhất editor Bản dịch + token bar Chính tả
    ↓
Phase 3 (3.1): CSS DRY
    ↓
Phase 4 (4.1 → 4.2): Cập nhật JS nếu cần
```

Mỗi Phase = 1 commit. Tổng: 4 commits.

---

## 7. So Sánh Trước/Sau (UI Layout)

### Trước (8 tab):
```
[📄 Nội dung gốc] [📚 Bản dịch] [🖊️ Hướng dẫn] [👥 Mối quan hệ] [📖 Thuật ngữ] [🎯 Chỉ dẫn] [📋 Tóm tắt] [🔤 Chính tả]
```

### Sau (5 tab):
```
[📄 Nội dung gốc] [📚 Bản dịch] [📋 Thông tin ▼] [🎯 Chỉ dẫn] [🔤 Chính tả]
                                          ├── 🖊️ Hướng dẫn
                                          ├── 👥 Mối quan hệ
                                          ├── 📖 Thuật ngữ
                                          └── 📋 Tóm tắt
```

---

*Tài liệu này là kế hoạch chi tiết, chưa có code thay đổi.*
