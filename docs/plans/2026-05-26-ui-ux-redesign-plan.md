# UI/UX Redesign — Detailed Implementation Plan

> **Base proposal**: `2026-05-26-ui-ux-redesign-proposal.md`
> **Strategy**: Incremental rollout (3 phases, deploy after each)
> **CSS Framework**: Keep Tachyons 4.12.0 + custom CSS overrides
> **Editor**: Keep textarea + overlay for glossary highlight
> **Focus Mode**: Keep as-is, update CSS only
> **Modal System**: Keep existing modal behavior, style refresh only

---

## Phase Overview & Dependencies

```
Phase 1: CSS & Header Redesign (no JS logic changes)
    ↓
Phase 2: Workspace Restructure (sidebar → file tree, unified editor)
    ↓
Phase 3: Feature Enhancements (glossary overlay, plugin file picker, prompt floating panel)
```

**Rule**: Each phase must be fully functional and deployable before starting the next. No partial states.

---

## PHASE 1: CSS & Header Redesign

**Goal**: New color system, new header style, config tab Segmented Control. Zero JS logic changes.

### Task 1.1 — Update CSS Variables & Global Styles

**Files to modify**:
- `webui/static/css/style.css`

**Changes**:
```css
/* REPLACE lines 2-8 with: */
:root {
  --primary: #4f46e5;           /* Indigo-600 (was #3b82f6 blue) */
  --primary-hover: #4338ca;     /* Indigo-700 */
  --primary-light: #eef2ff;     /* Indigo-50 for hover backgrounds */
  --bg-app: #f8fafc;            /* Slate-50 (was #f1f5f9) */
  --bg-card: #ffffff;           /* Pure white for cards */
  --border: #e2e8f0;            /* Slate-200 (unchanged) */
  --border-light: #f1f5f9;      /* Slate-100 for subtle dividers */
  --text-main: #0f172a;         /* Slate-900 for headings */
  --text-body: #334155;         /* Slate-700 for body text */
  --text-muted: #64748b;        /* Slate-500 for labels */
  --text-subtle: #94a3b8;       /* Slate-400 for hints */
  --shadow-sm: 0 1px 2px rgba(0,0,0,0.05);
  --shadow-md: 0 4px 6px -1px rgba(0,0,0,0.07);
  --radius-sm: 6px;
  --radius-md: 8px;
  --radius-lg: 12px;
}
```

**Also update**:
- All `#3b82f6` references → `var(--primary)` (already using CSS var, just update the var value)
- `.header-container` background: `#0b3d59` → `#ffffff` with `border-bottom: 1px solid var(--border)`
- `.nav-link` color: white → `var(--text-muted)`, active → `var(--primary)` with `border-bottom-color: var(--primary)`
- `.header-left span.dark-gray` color: white → `var(--text-main)`
- `.header-right .bg-near-white` stats pill: remove white-on-dark override, use light background
- `.header-right .blue/.green/.orange`: revert to standard colors (remove white-theme overrides)
- `.header-right button.bg-transparent`: remove white color override

**Acceptance Criteria**:
- [ ] Page loads with white header, indigo accents, slate text
- [ ] All buttons use indigo instead of blue
- [ ] Stats pill in header is light-themed (not white-on-dark)
- [ ] Focus Mode still works (header hidden)
- [ ] All existing Tachyons utility classes still function

### Task 1.2 — Redesign Header HTML

**Files to modify**:
- `webui/templates/partials/header.html`

**Changes to header.html**:

1. **Brand section** (lines 22-26):
   - Remove emoji `📚`
   - Change `Content Translator` text color from white to `var(--text-main)`
   - Version badge: use `var(--text-subtle)` instead of white

2. **Stats section** (lines 39-48):
   - Replace emoji icons with colored dots (CSS circles):
     - API Keys: blue dot `●` with `color: var(--primary)`
     - Cache: green dot `●` with `color: #10b981`
     - Projects: amber dot `●` with `color: #f59e0b`
   - Restart button: replace `🔄` with SVG icon or text "Restart"
   - Remove all emoji from stats (🔑, 📦, 💬, 🔄)

3. **Focus Mode button** (line 40):
   - Replace `🖥️` emoji with text-only: "Focus"

**Acceptance Criteria**:
- [ ] Header is white with clean typography
- [ ] No emojis in header area
- [ ] Stats show colored dots + numbers
- [ ] Hover on stats shows tooltip with full info
- [ ] Focus Mode button still works

### Task 1.3 — Config Tab: Segmented Control

**Files to modify**:
- `webui/templates/partials/tab_config.html`
- `webui/static/css/style.css` (add new styles)
- `webui/static/js/main.js` (add `switchProviderTab()` function)

**Current behavior**: Two provider cards shown side-by-side, click card to switch provider.

**New behavior**:
1. Add Segmented Control at top of config section:
   ```html
   <div class="nt-segmented-control">
     <button class="nt-seg-btn active" data-provider="gemini" onclick="switchProviderTab('gemini')">Google Gemini</button>
     <button class="nt-seg-btn" data-provider="openai" onclick="switchProviderTab('openai')">OpenAI Compatible</button>
   </div>
   ```
2. Only show the selected provider's config section (hide the other)
3. API Key inputs: change Gemini textarea to `type="password"` with toggle visibility button
4. OpenAI API Key: already `<input type="text">`, change to `type="password"` with toggle

**New CSS** (add to style.css):
```css
.nt-segmented-control {
  display: inline-flex;
  background: var(--bg-app);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 3px;
  gap: 2px;
}
.nt-seg-btn {
  padding: 0.5rem 1.25rem;
  border: none;
  border-radius: var(--radius-sm);
  font-size: 0.875rem;
  font-weight: 600;
  cursor: pointer;
  background: transparent;
  color: var(--text-muted);
  transition: all 0.15s;
}
.nt-seg-btn.active {
  background: white;
  color: var(--text-main);
  box-shadow: var(--shadow-sm);
}
```

**New JS function** (add to main.js):
```javascript
function switchProviderTab(provider) {
    // Update segmented control active state
    document.querySelectorAll('.nt-seg-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.provider === provider);
    });
    // Show/hide provider config sections
    document.getElementById('provider-gemini-section').classList.toggle('dn', provider !== 'gemini');
    document.getElementById('provider-openai-section').classList.toggle('dn', provider !== 'openai');
}
```

**Acceptance Criteria**:
- [ ] Segmented control switches between Gemini/OpenAI views
- [ ] Only one provider config visible at a time
- [ ] API Keys are masked by default, toggle to show
- [ ] `switchProvider()` still calls the API to change active provider
- [ ] Existing provider state loads correctly on page refresh

### Task 1.4 — Remove Emojis from Tab Labels & Buttons

**Files to modify**:
- `webui/templates/partials/tab_workspace.html`
- `webui/templates/partials/tab_config.html`
- `webui/templates/partials/tab_prompts.html`
- `webui/templates/partials/tab_plugins.html`
- `webui/templates/partials/tab_logs.html`
- `webui/templates/partials/tab_archive.html`

**Rules**:
- Remove all emojis from: tab buttons, section headings, button labels
- Keep emojis ONLY in: status indicators (🛑⏳✅ for file status), and tooltip content
- Replace with text or leave empty (the context makes meaning clear)

**Examples**:
| Before | After |
|--------|-------|
| `📄 Nội dung gốc` | `Nội dung gốc` |
| `📤 Tải lên` | `Tải lên` |
| `✂️ Chia chunk` | `Chia chunk` |
| `🚀 Dịch đã chọn` | `Dịch đã chọn` |
| `📚 EPUB Converter` | `EPUB Converter` |
| `🔍 OCR Reader` | `OCR Reader` |
| `💾 Lưu` | `Lưu` |
| `📊 Diff` | `Diff` |
| `↩️ Wrap` | `Wrap` |

**Acceptance Criteria**:
- [ ] No emojis in tab navigation, button labels, or section headings
- [ ] File status emojis preserved (🛑⏳✅)
- [ ] All buttons still clickable and functional
- [ ] UI feels cleaner without emoji clutter

### Task 1.5 — Style Refresh for Cards, Tables, Inputs

**Files to modify**:
- `webui/static/css/style.css`

**Changes**:
1. **Cards** (`.ba.b--black-10.br2.bg-white`): Update border to `var(--border)`, border-radius to `var(--radius-md)`, shadow to `var(--shadow-sm)`
2. **Tables** (`.minimal-table`): Lighter row dividers (`var(--border-light)`), hover state uses `var(--primary-light)`
3. **Inputs** (`.nt-input`, all `input[type="text"]`, `textarea`): Focus ring uses `var(--primary)` with 3px alpha ring
4. **Buttons**: Update `.nt-btn-primary` to use `var(--primary)`, add `.nt-btn-ghost` for subtle actions
5. **Scrollbar**: Keep current custom scrollbar style
6. **Toasts**: Update to use `var(--text-main)` background instead of `#1e293b`

**Acceptance Criteria**:
- [ ] Cards have softer borders and consistent radius
- [ ] Input focus rings are indigo-colored
- [ ] Table hover rows use light indigo background
- [ ] All existing layout unchanged (no width/height shifts)

---

## PHASE 2: Workspace Restructure

**Goal**: Transform workspace from "file list on top + editor below" to "file tree sidebar + unified editor". Eliminate double-scrollbar.

### Task 2.1 — Redesign Workspace Layout Structure

**Files to modify**:
- `webui/templates/partials/tab_workspace.html`
- `webui/static/css/style.css`

**Current layout** (per sub-tab: workspace/translated/spellcheck):
```
┌─────────────────────────────────┐
│ [File Table - 350px height]     │  ← file-list-box, resizable
├─────────────────────────────────┤
│ [Side-by-Side Editor - 420px]   │  ← editor-container, min-height
└─────────────────────────────────┘
```

**New layout** (unified across all sub-tabs):
```
┌──────────┬────────────────────────┐
│ FILE     │ EDITOR                 │
│ TREE     │ [Mode: Dropdown]       │
│ 250px    │ ┌────────┬───────────┐ │
│          │ │ Source │ Translation│ │
│          │ │        │           │ │
│          │ │        │           │ │
│          │ └────────┴───────────┘ │
│          │ [Token bar + Actions]  │
└──────────┴────────────────────────┘
```

**Implementation details**:

1. **Remove the separate file table sections** from `ptab-workspace`, `ptab-translated`, and `ptab-spellcheck`. The file list moves to the sidebar.

2. **New sidebar structure** (replace current project-list sidebar):
   ```html
   <div class="sidebar ba br2 bg-white flex flex-column shadow-sm" style="width: 260px;">
     <!-- Project selector header -->
     <div class="pa3 bb b--black-10 bg-near-white flex justify-between items-center">
       <span class="f7 fw6 uppercase tracked" style="color: var(--text-muted);">Files</span>
       <div class="flex gap-1">
         <button class="..." onclick="showUploadDialog()" title="Upload">+</button>
       </div>
     </div>
     <!-- File tree -->
     <div id="file-tree" class="flex-auto overflow-y-auto">
       <!-- Injected by JS: file items with status icons -->
     </div>
     <!-- Quick actions at bottom -->
     <div class="pa2 bt b--black-10 flex gap-1">
       <button class="flex-auto ... onclick="translateSelectedInProject()">Dịch</button>
       <button class="flex-auto ..." onclick="showChunkConfig()">Chunk</button>
     </div>
   </div>
   ```

3. **File tree items** (rendered by JS):
   ```html
   <div class="file-tree-item pa2 ph3 pointer flex items-center gap-2" data-file="chapter1.txt" onclick="loadFileInEditor('chapter1.txt')">
     <span class="file-status" title="Chưa dịch">●</span>  <!-- colored dot -->
     <span class="f7 truncate flex-auto">chapter1.txt</span>
     <input type="checkbox" class="file-check" onclick="event.stopPropagation(); toggleFileSelect('chapter1.txt')">
   </div>
   ```

4. **Status dot colors**:
   - Gray `●` = Chưa dịch
   - Amber `●` = Đang dịch
   - Green `●` = Đã dịch xong

5. **Editor area**: Keep existing side-by-side editor structure but make it fill 100% remaining height (viewport-fit). Remove `min-height: 420px` constraint.

6. **Mode dropdown** (above editor):
   ```html
   <select id="editor-mode" onchange="switchEditorMode(this.value)">
     <option value="translate">Dịch thuật</option>
     <option value="spellcheck">Soát lỗi chính tả</option>
   </select>
   ```
   When mode changes: swap left/right textarea labels and behavior (not DOM, just data).

7. **Sync Scroll toggle**: Add toggle button next to mode dropdown.

**Acceptance Criteria**:
- [ ] Sidebar shows file tree with colored status dots
- [ ] Click file in tree → loads content in editor
- [ ] Checkboxes for multi-select (chunk, translate)
- [ ] Editor fills remaining viewport height (no page scroll)
- [ ] Mode dropdown switches between translate/spellcheck
- [ ] Upload/Chunk/Translate buttons accessible from sidebar bottom
- [ ] Focus Mode still works (hides sidebar + header)

### Task 2.2 — Unified Editor: Remove Redundant Sub-tabs

**Files to modify**:
- `webui/templates/partials/tab_workspace.html`
- `webui/static/js/main.js`

**Current**: 5 sub-tabs (workspace/translated/spellcheck/info/prompt) each with their own file list + editor.

**New**: 2 sub-tabs only:
1. **Biên tập** (Editor) — unified editor with mode dropdown (translate/spellcheck)
2. **Thông tin & Chỉ dẫn** (Info & Prompts) — merged tab with sub-panels

**Why merge translated into workspace**: The "translated" tab duplicates the editor layout. With the new file tree, clicking a translated file can show its content in the same editor (different mode).

**Implementation**:

1. **Remove** `ptab-translated` and `ptab-spellcheck` sections from HTML
2. **Keep** `ptab-workspace` as the main editor (rename to `ptab-editor`)
3. **Merge** `ptab-info` and `ptab-prompt` into one tab `ptab-info-prompt` with nested radio sub-tabs
4. **Update** `switchProjectTab()` in main.js to handle 2 tabs instead of 5
5. **Update** `loadProjectFile()` to detect file type (source vs translated) and set editor mode accordingly

**Acceptance Criteria**:
- [ ] Only 2 sub-tabs visible: "Biên tập" and "Thông tin & Chỉ dẫn"
- [ ] Clicking source file → editor in translate mode (left=source, right=translation)
- [ ] Clicking translated file → editor shows translated content with source on left
- [ ] Info & Prompts tab shows all 4+5 sub-panels in one place
- [ ] No broken keyboard shortcuts

### Task 2.3 — Sync Scroll Implementation

**Files to modify**:
- `webui/static/js/main.js`
- `webui/templates/partials/tab_workspace.html`

**Current**: `setupSyncScroll()` exists in main.js (line ~1293) but may not be fully wired.

**Implementation**:

1. Add a toggle button in editor toolbar:
   ```html
   <button id="btn-sync-scroll" class="..." onclick="toggleSyncScroll()">Cuộn đồng bộ: Bật</button>
   ```

2. JS logic:
   ```javascript
   let syncScrollEnabled = true;
   function toggleSyncScroll() {
     syncScrollEnabled = !syncScrollEnabled;
     document.getElementById('btn-sync-scroll').textContent = 
       'Cuộn đồng bộ: ' + (syncScrollEnabled ? 'Bật' : 'Tắt');
   }
   function setupSyncScroll(sourceEl, targetEl) {
     sourceEl.addEventListener('scroll', () => {
       if (!syncScrollEnabled) return;
       const ratio = sourceEl.scrollTop / (sourceEl.scrollHeight - sourceEl.clientHeight);
       targetEl.scrollTop = ratio * (targetEl.scrollHeight - targetEl.clientHeight);
     });
   }
   ```

3. Wire up on file load: when `loadProjectFile()` completes, call `setupSyncScroll(sourceTextarea, resultTextarea)`.

**Acceptance Criteria**:
- [ ] Scrolling left textarea scrolls right textarea proportionally
- [ ] Toggle button can enable/disable sync
- [ ] Works in both translate and spellcheck modes
- [ ] No performance issues on long chapters (10k+ words)

### Task 2.4 — Keyboard Navigation Update

**Files to modify**:
- `webui/static/js/main.js`

**Current**: J/K/Arrow keys navigate file list in `renderProjectSources()` table rows.

**New**: Update keyboard navigation to work with the new file tree items.

**Changes**:
- Update selectors from `#project-source-table-body tr` to `.file-tree-item`
- Keep J/K for up/down, Enter to open file, Esc for focus mode
- Add `Space` to toggle checkbox on focused file

**Acceptance Criteria**:
- [ ] J/K moves focus highlight between files in tree
- [ ] Enter loads focused file in editor
- [ ] Space toggles file checkbox
- [ ] Esc enters focus mode

---

## PHASE 3: Feature Enhancements

**Goal**: Glossary overlay, plugin file picker, prompt floating panel. Each is independent.

### Task 3.1 — Interactive Glossary Overlay

**Files to modify**:
- `webui/static/js/main.js`
- `webui/static/css/style.css`
- `webui/templates/partials/tab_workspace.html`

**Prerequisite**: Phase 2 complete (unified editor exists).

**Design**: When a file is loaded, scan the source text for glossary terms. Create a transparent overlay `div` on top of the source textarea that shows dashed underlines for matched terms. Hover shows tooltip with translation.

**Implementation**:

1. **Backend**: Add API endpoint `GET /api/projects/{slug}/glossary-terms` that returns the project's glossary as JSON array:
   ```json
   [
     {"original": "Nhân vật A", "translation": "Character A", "note": "Main protagonist"},
     {"original": "Ma thuật", "translation": "Magic", "note": ""}
   ]
   ```

2. **Frontend**: Create overlay system:
   ```javascript
   function highlightGlossaryTerms(textarea, terms) {
     // Create overlay div positioned exactly over textarea
     const overlay = document.createElement('div');
     overlay.className = 'glossary-overlay';
     overlay.setAttribute('aria-hidden', 'true');
     
     // Mirror textarea's font, padding, dimensions
     // Scan text for term occurrences
     // Generate HTML with <mark> elements for matches
     // Position overlay absolutely on top of textarea
   }
   ```

3. **CSS**:
   ```css
   .editor-pane-wrapper { position: relative; }
   .glossary-overlay {
     position: absolute;
     top: 0; left: 0; right: 0; bottom: 0;
     pointer-events: none;  /* clicks pass through to textarea */
     overflow: hidden;
     /* Mirror textarea font properties */
     font-family: inherit;
     font-size: inherit;
     line-height: inherit;
     padding: inherit;
     white-space: pre-wrap;
     word-wrap: break-word;
     color: transparent;  /* invisible text, only show decorations */
   }
   .glossary-overlay mark {
     pointer-events: auto;  /* hover targets */
     background: transparent;
     border-bottom: 2px dashed #fbbf24;  /* amber underline */
     cursor: help;
   }
   .glossary-overlay mark:hover {
     background: rgba(251, 191, 36, 0.15);
   }
   ```

4. **Tooltip**: On hover, show popup with translation + note. Use CSS-only tooltip (similar to `.nt-help-icon::after` pattern).

5. **Click-to-insert**: When user clicks a highlighted term, insert the translation at cursor position in the result textarea:
   ```javascript
   overlay.addEventListener('click', (e) => {
     if (e.target.tagName === 'MARK') {
       const translation = e.target.dataset.translation;
       const resultTextarea = document.getElementById('result-text');
       const pos = resultTextarea.selectionStart;
       resultTextarea.value = 
         resultTextarea.value.slice(0, pos) + translation + resultTextarea.value.slice(pos);
       resultTextarea.selectionStart = resultTextarea.selectionEnd = pos + translation.length;
       resultTextarea.focus();
     }
   });
   ```

6. **Sync overlay with textarea scroll**:
   ```javascript
   textarea.addEventListener('scroll', () => {
     overlay.scrollTop = textarea.scrollTop;
     overlay.scrollLeft = textarea.scrollLeft;
   });
   ```

**Acceptance Criteria**:
- [ ] Glossary terms get dashed underline in source textarea
- [ ] Hover shows translation tooltip
- [ ] Click inserts translation into result textarea at cursor
- [ ] Overlay stays aligned when scrolling
- [ ] Overlay doesn't interfere with typing in textarea
- [ ] Performance acceptable with 50+ glossary terms and 10k+ word files
- [ ] No overlay shown when glossary is empty

### Task 3.2 — Plugin File Picker (Remove Manual Path Input)

**Files to modify**:
- `webui/templates/partials/tab_plugins.html`
- `webui/static/js/main.js`
- `webui/routes/plugins.py` (add file listing endpoint)

**Current**: User types file paths manually (e.g., `workspace/input/novel.epub`).

**New**: Add file browser dialog + drag-and-drop zone.

**Implementation**:

1. **Backend**: Add endpoint `GET /api/plugins/files?type=epub|pdf|image` that lists files in `workspace/input/` filtered by extension:
   ```json
   {
     "files": [
       {"name": "novel.epub", "path": "workspace/input/novel.epub", "size": "2.3 MB"},
       {"name": "scan.pdf", "path": "workspace/input/scan.pdf", "size": "15.1 MB"}
     ],
     "workspace_path": "/absolute/path/to/workspace/input/"
   }
   ```

2. **Frontend**: Replace text inputs with file picker component:
   ```html
   <div class="file-picker-wrapper">
     <div class="file-drop-zone" ondrop="handleFileDrop(event)" ondragover="event.preventDefault()">
       <input type="text" id="epub-path" class="..." placeholder="Kéo thả file vào đây hoặc nhấn Browse...">
       <button onclick="openFileBrowser('epub')">Browse</button>
     </div>
   </div>
   ```

3. **File Browser Modal**: Reuse existing modal pattern (`.dn.fixed.absolute--fill`):
   ```html
   <div id="file-browser-modal" class="dn fixed absolute--fill bg-black-70 items-center justify-center z-max">
     <div class="bg-white pa4 br3 w-100 mw5 shadow-5">
       <h3>Chọn file</h3>
       <div id="file-browser-list" class="overflow-y-auto" style="max-height: 400px;">
         <!-- File items injected by JS -->
       </div>
       <button onclick="closeFileBrowser()">Hủy</button>
     </div>
   </div>
   ```

4. **Drag-and-Drop**: Handle `drop` event, read file name, fill input.

**Acceptance Criteria**:
- [ ] "Browse" button opens file browser modal showing workspace/input/ files
- [ ] Files filtered by type (EPUB for converter, PDF/images for OCR)
- [ ] Click file → fills the path input
- [ ] Drag-and-drop zone accepts files visually
- [ ] Manual path input still works (for custom paths)
- [ ] Output path also gets browse button

### Task 3.3 — Prompt Floating Help Panel

**Files to modify**:
- `webui/templates/partials/tab_workspace.html`
- `webui/templates/partials/tab_prompts.html`
- `webui/static/css/style.css`
- `webui/static/js/main.js`

**Current**: Placeholder help block (`{source_text}`, `{glossary}`, etc.) is a static block below prompt textareas, always visible.

**New**: Convert to floating panel that can be toggled.

**Implementation**:

1. **Remove** the `.prompt-help-block` sections from both `tab_workspace.html` (lines 314-324) and `tab_prompts.html`.

2. **Add toggle button** in prompt tab toolbar:
   ```html
   <button class="..." onclick="togglePromptHelp()" title="Xem danh sách biến">💡 Biến</button>
   ```

3. **Floating panel** (positioned fixed, bottom-right):
   ```html
   <div id="prompt-help-panel" class="dn">
     <div class="prompt-help-floating">
       <div class="flex justify-between items-center mb2">
         <span class="f7 fw6 uppercase tracked">Biến Template</span>
         <button onclick="togglePromptHelp()" class="f7">×</button>
       </div>
       <div class="placeholder-grid">
         <!-- Same content as before -->
       </div>
     </div>
   </div>
   ```

4. **CSS**:
   ```css
   .prompt-help-floating {
     position: fixed;
     bottom: 2rem;
     right: 2rem;
     width: 360px;
     max-height: 50vh;
     overflow-y: auto;
     background: white;
     border: 1px solid var(--border);
     border-radius: var(--radius-lg);
     box-shadow: var(--shadow-md);
     padding: 1rem;
     z-index: 500;
   }
   ```

5. **JS**:
   ```javascript
   function togglePromptHelp() {
     const panel = document.getElementById('prompt-help-panel');
     panel.classList.toggle('dn');
   }
   ```

**Acceptance Criteria**:
- [ ] Help panel hidden by default
- [ ] Click "Biến" button toggles floating panel
- [ ] Panel appears bottom-right, doesn't block editor
- [ ] Panel has close button
- [ ] Works in both system prompts tab and project prompts tab
- [ ] Panel state persists during session (localStorage)

### Task 3.4 — Reset Individual Prompt

**Files to modify**:
- `webui/static/js/main.js`
- `webui/routes/prompts.py` (add reset endpoint)
- `webui/templates/partials/tab_workspace.html`
- `webui/templates/partials/tab_prompts.html`

**Implementation**:

1. **Backend**: Add `POST /api/projects/{slug}/prompts/{prompt-key}/reset` that deletes project-specific prompt file, reverting to system default.

2. **Frontend**: Add small reset button next to each prompt textarea:
   ```html
   <button class="f8 silver hover-blue" onclick="resetSinglePrompt('main')" title="Khôi phục mặc định">↺</button>
   ```

3. **JS**:
   ```javascript
   async function resetSinglePrompt(key) {
     if (!confirm('Khôi phục prompt này về mặc định hệ thống?')) return;
     const res = await fetch(`/api/projects/${currentProject.slug}/prompts/${key}/reset`, {method: 'POST'});
     if (res.ok) loadProjectPrompts();  // reload
   }
   ```

**Acceptance Criteria**:
- [ ] Reset button visible next to each prompt textarea
- [ ] Click → confirms → resets to system default
- [ ] Other prompts in the set unaffected
- [ ] UI refreshes to show default content

### Task 3.5 — Plugin Log Terminal Styling

**Files to modify**:
- `webui/static/css/style.css`

**Changes**:
- Style `#epub-log` and `#ocr-log` with:
  - Rounded corners (`var(--radius-md)`)
  - Monospace font (already `code` class)
  - Auto-scroll to bottom on new content
  - "Clear" button

**Add to main.js**: In `pollPluginProgress()` callback, auto-scroll log:
```javascript
const logEl = document.getElementById('epub-log');
logEl.scrollTop = logEl.scrollHeight;
```

**Acceptance Criteria**:
- [ ] Log terminal has consistent styling with new theme
- [ ] Auto-scrolls to bottom on new log lines
- [ ] Clear button empties log content

---

## Cross-Cutting Concerns

### Testing Checklist (run after each phase)

```bash
# From project root
python -m pytest tests/ -x -q
```

**Manual verification per phase**:

| Check | Phase 1 | Phase 2 | Phase 3 |
|-------|---------|---------|---------|
| Page loads without errors | ✓ | ✓ | ✓ |
| All tabs switch correctly | ✓ | ✓ | ✓ |
| Focus Mode works | ✓ | ✓ | ✓ |
| Create/select/delete project | ✓ | ✓ | ✓ |
| Upload files | ✓ | ✓ | ✓ |
| Start translation (SSE progress) | ✓ | ✓ | ✓ |
| Save/load editor content | ✓ | ✓ | ✓ |
| Dirty state warning on leave | ✓ | ✓ | ✓ |
| Keyboard navigation (J/K/Enter) | ✓ | ✓ | ✓ |
| Config save/load | ✓ | ✓ | — |
| Plugin execution | — | — | ✓ |
| Glossary highlight | — | — | ✓ |

### Files Modified Summary

| Phase | Files Modified |
|-------|---------------|
| 1 | `style.css`, `header.html`, `tab_config.html`, `tab_workspace.html`, `tab_prompts.html`, `tab_plugins.html`, `tab_logs.html`, `tab_archive.html`, `main.js` |
| 2 | `tab_workspace.html`, `main.js`, `style.css` |
| 3 | `main.js`, `style.css`, `tab_workspace.html`, `tab_prompts.html`, `tab_plugins.html`, `plugins.py`, `prompts.py` |

### Rollback Strategy

Each phase is a separate git branch/commit:
- Phase 1 breaks nothing (CSS-only + HTML tweaks)
- Phase 2 is the riskiest (layout restructure) — if issues, revert to Phase 1 state
- Phase 3 features are additive — can revert individually

---

## What This Plan Does NOT Cover (Explicitly Out of Scope)

1. **main.js refactoring into modules** — The proposal mentions this but it's a separate effort. This plan keeps main.js monolithic and only adds/modifies functions.
2. **Backend API restructuring** — No changes to Flask blueprints or route organization.
3. **Mobile responsiveness** — Tachyons provides basic responsive utilities. Full mobile support is a separate project.
4. **Dark mode** — Not in scope. The new light theme is the only theme.
5. **Figma/mockup** — ASCII art in the proposal serves as the wireframe.
