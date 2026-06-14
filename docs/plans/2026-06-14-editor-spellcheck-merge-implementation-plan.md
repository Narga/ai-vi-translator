# Editor & Spellcheck UI Merging Implementation Plan

> **For Antigravity:** REQUIRED WORKFLOW: Use `.agent/workflows/execute-plan.md` to execute this plan in single-flow mode.

**Goal:** Merge the "Editor" and "Spellcheck" sections of the Project workspace into a single "Editor" tab with a 3-tab sidebar, unified source file actions, an intuitive spellcheck icon, custom CSS tooltips, and a renamed Project TM reset button.

**Architecture:** We will consolidate the HTML templates of both views under a single sub-tab view, grouping related DOM panels and editors under respective parent wrappers. Frontend Javascript will handle showing/hiding these panels and dynamically adapting the sidebar toolbar based on the active mini-tab. Tooltips will be implemented with CSS attribute selectors for smooth performance and zero javascript dependencies.

**Tech Stack:** HTML5, Jinja2, Vanilla CSS (Tachyons styled), Vanilla JavaScript

---

### Task 1: Add Custom CSS Tooltips

**Files:**
- Modify: [style.css](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/static/css/style.css)

**Step 1: Write the tooltips styling**
Add the following CSS rules at the end of the file to support `[data-tooltip]` overlays.
```css
/* ============================================================ */
/* Custom CSS Tooltips                                         */
/* ============================================================ */
[data-tooltip] {
    position: relative;
}
[data-tooltip]::after {
    content: attr(data-tooltip);
    position: absolute;
    bottom: 125%;
    left: 50%;
    transform: translateX(-50%) scale(0.9);
    background: rgba(15, 23, 42, 0.95);
    color: #ffffff;
    font-size: 0.75rem;
    padding: 6px 10px;
    border-radius: 6px;
    white-space: nowrap;
    opacity: 0;
    visibility: hidden;
    transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1);
    z-index: 1000;
    pointer-events: none;
    box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06);
    backdrop-filter: blur(4px);
    border: 1px solid rgba(255, 255, 255, 0.1);
}
[data-tooltip]:hover::after {
    opacity: 1;
    visibility: visible;
    transform: translateX(-50%) scale(1);
}
```

**Step 2: Verify styles compile and exist**
Verify the file by opening it or validating that no syntax errors are introduced.

**Step 3: Commit changes**
```bash
git add webui/static/css/style.css
git commit -m "style: add custom CSS tooltip styles"
```

---

### Task 2: Refactor HTML Template

**Files:**
- Modify: [tab_projects.html](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/templates/partials/tab_projects.html)

**Step 1: Update workspace sub-tabs**
Remove the "Kiểm chính tả" tab button and keep only "Biên tập", "Thông tin", and "Chỉ dẫn".

**Step 2: Update Sidebar footer tabs**
Update `#pm-file-sidebar`'s bottom mini-tabs:
```html
<div class="flex bb b--black-10">
    <button class="sidebar-mini-tab active" onclick="ProjectManager.switchPmFileTab('sources')" id="pm-tab-sources">Nội dung nguồn</button>
    <button class="sidebar-mini-tab" onclick="ProjectManager.switchPmFileTab('translated')" id="pm-tab-translated">Bản dịch</button>
    <button class="sidebar-mini-tab" onclick="ProjectManager.switchPmFileTab('spelling')" id="pm-tab-spelling">Soát chính tả</button>
</div>
```

**Step 3: Update Sidebar header toolbar**
- Set specific `id` attributes on buttons to allow targeted show/hide actions in Javascript.
- Add "Soát lỗi đã chọn" button (`pm-btn-spellcheck-selected`) with the new checkmark SVG.
- Replace HTML `title` attributes with `data-tooltip` to utilize the new CSS tooltips.
- Remove the redundant `#pm-spell-file-sidebar` element entirely.

**Step 4: Restructure editor panels**
- Group translation editor panels (`#pm-source-editor`, `#pm-result-editor`) and their bottom action bar into a single container `#pm-translation-workspace`.
- Group spellcheck editor panels (`#pm-spell-source-editor`, `#pm-spell-result-editor`), the `.spell-log-panel`, and their bottom action bar into a single container `#pm-spellcheck-workspace` (with initial style `display: none;`).
- Remove the outer `#tab-spellcheck` subtab container.
- Rename "Xóa TM dự án" button text to "Đặt lại bộ nhớ dịch" and update its title to `data-tooltip`.

**Step 5: Verify template changes**
Check that the template loads without syntax/render errors by starting the server:
```bash
uv run python webui.py
```

**Step 6: Commit changes**
```bash
git add webui/templates/partials/tab_projects.html
git commit -m "templates: merge Editor and Spellcheck template views and update tooltips"
```

---

### Task 3: Implement Javascript UI Logic

**Files:**
- Modify: [project-manager.js](file:///Users/narga/Briefcase/Projects/Novel-Translator/webui/static/js/project-manager.js)

**Step 1: Update Icons**
Replace the spellcheck SVG icon in `Icons.spellcheck` to the clean 'A' with checkmark design:
```javascript
spellcheck: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m6 16 6-12 6 12"/><path d="M8 12h8"/><path d="m16 20 2 2 4-4"/></svg>',
```

**Step 2: Update `switchPmFileTab(tab)`**
Rewrite the function to support three tabs (`sources`, `translated`, `spelling`):
1. Manage the active button class `.active` on the three buttons: `pm-tab-sources`, `pm-tab-translated`, `pm-tab-spelling`.
2. Toggle visibility of the editor workspaces:
   - For `sources` and `translated`: show `#pm-translation-workspace` and hide `#pm-spellcheck-workspace`.
   - For `spelling`: show `#pm-spellcheck-workspace` and hide `#pm-translation-workspace`.
3. Toggle visibility of the sidebar toolbar buttons:
   - `sources`: show upload, chunk, translate, spellcheck, merge, delete-selected.
   - `translated`: show merge, delete-selected; hide upload, chunk, translate, spellcheck.
   - `spelling`: show delete-selected; hide others.
4. Call the correct rendering function:
   - `sources` -> `ProjectManager.renderPmFileList(window.currentProject?.sources || [])`
   - `translated` -> `ProjectManager.renderPmTranslatedList(window.currentProject?.translated || [])`
   - `spelling` -> `ProjectManager.renderPmSpellcheckedList()`

**Step 3: Update File Items Rendering**
In `renderPmFileList(sources)`, add the Spellcheck action icon to each item so it can trigger `TranslationWorker.spellcheckFileInProject` directly:
```javascript
<button onclick="event.stopPropagation();TranslationWorker.spellcheckFileInProject(this.closest('.file-item-compact').dataset.filename)" title="Soát lỗi AI">${Icons.spellcheck}</button>
```

**Step 4: Update sidebar file selection & delete actions**
- Update `deleteSelectedSidebarFiles()` to branch:
  - If `pm-tab-sources` is active: delete source files.
  - If `pm-tab-translated` is active: delete translated files.
  - If `pm-tab-spelling` is active: delete spelling files.
- Update `selectAllSidebarFiles()` to branch similarly.

**Step 5: Update `clearProjectTM()` confirm prompt**
Change confirm dialog text to use **Đặt lại bộ nhớ dịch** terminology.

**Step 6: Verify Javascript logic**
Run pytest to verify the Javascript logic modifications don't break any backend interfaces:
```bash
uv run pytest
```

**Step 7: Commit changes**
```bash
git add webui/static/js/project-manager.js
git commit -m "js: implement 3-tab sidebar switching and unify file list logic"
```

---

### Task 4: Complete and Verify

**Files:**
- Test: manual integration testing on the browser.

**Step 1: Start Web UI**
```bash
uv run python webui.py
```

**Step 2: Perform manual checklist**
- Open a project in the Web UI.
- Verify sub-tab "Kiểm chính tả" is gone and the new "Biên tập" tab functions properly.
- Test switching mini-tabs in the sidebar (Nội dung nguồn, Bản dịch, Soát chính tả).
- Verify the toolbar icons hide/show correctly based on the active mini-tab.
- Verify custom CSS tooltips show on hover.
- Click "Đặt lại bộ nhớ dịch" and check the updated confirmation text.

**Step 3: Final Commit**
```bash
git commit --allow-empty -m "chore: complete Editor and Spellcheck UI merge validation"
```
