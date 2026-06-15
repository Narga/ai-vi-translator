/* Novel Translator - main.js v6.0 (Modular Entry Point) */

// ============================================================
// Global State (shared across modules)
// ============================================================
window.prompts = window.initialPrompts || {};
window.currentOutputFile = '';
window.selectedFiles = new Set();
window.selectedTranslatedFiles = new Set();
window.availableModels = window.initialAvailableModels || [];
window.availableGeminiModels = [];
window.availableOpenAIModels = [];
window.defaultModel = window.initialDefaultModel || '';
window.currentDoneFile = '';
window.currentGenre = '';
window.currentProject = null;
window.currentProjectFile = null;
window.currentModelInfo = null;
window.isCloning = false;
window._autoReturnTimer = null;

// ============================================================
// Unsaved Changes Tracking
// ============================================================
const DirtyState = {
    _dirty: new Set(),
    mark(editorId) {
        this._dirty.add(editorId);
        this._updateIndicator();
    },
    clean(editorId) {
        this._dirty.delete(editorId);
        this._updateIndicator();
    },
    isDirty(editorId) {
        return editorId ? this._dirty.has(editorId) : this._dirty.size > 0;
    },
    _updateIndicator() {
        document.querySelectorAll('.unsaved-dot').forEach(el => {
            el.style.display = this._dirty.size > 0 ? 'inline-block' : 'none';
        });
    }
};
window.DirtyState = DirtyState;

window.addEventListener('beforeunload', function(e) {
    if (DirtyState.isDirty()) {
        e.preventDefault();
        e.returnValue = '';
    }
});

// ============================================================
// Tab Switching (Main Navigation)
// ============================================================
function initTabs() {
    const navItems = document.querySelectorAll('.nav-link');
    const sections = document.querySelectorAll('.nt-tab-content');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            const targetId = item.getAttribute('data-tab');

            if (targetId === 'archive') ApiClient.loadArchiveList();
            if (targetId === 'logs') ApiClient.loadLogList();
            if (targetId === 'projects') ProjectManager.loadProjectCards();
            if (targetId === 'prompts') PromptManager.loadGenres();
            if (targetId === 'config') {
                ApiClient.loadApiKeys();
                if (typeof OpenAIProvider !== 'undefined') OpenAIProvider.loadProviders();
            }

            if (targetId === 'workspace') {
                if (typeof startStatsPolling === 'function') startStatsPolling();
            } else {
                if (typeof stopStatsPolling === 'function') stopStatsPolling();
            }

            localStorage.setItem('nt_active_main_tab', targetId);

            navItems.forEach(n => n.classList.remove('active'));
            item.classList.add('active');

            sections.forEach(sec => {
                sec.classList.remove('active');
                sec.classList.add('dn');
            });
            const targetSection = document.getElementById('tab-' + targetId);
            if (targetSection) {
                targetSection.classList.remove('dn');
                targetSection.classList.add('active');
                targetSection.scrollTo(0, 0);
            }
        });
    });
}

// ============================================================
// Keyboard Navigation
// ============================================================
var _selectedFileIndex = -1;

document.addEventListener('keydown', function(e) {
    if (e.target.tagName === 'TEXTAREA' || e.target.tagName === 'INPUT') return;
    if (!window.currentProject) return;

    var rows = document.querySelectorAll('#pm-file-list .file-item-compact');
    
    if (!rows.length) return;

    if (e.key === 'j' || e.key === 'ArrowDown') {
        e.preventDefault();
        if (_selectedFileIndex < rows.length - 1) {
            _selectedFileIndex++;
            _highlightFileRow(rows, _selectedFileIndex);
        }
    }
    if (e.key === 'k' || e.key === 'ArrowUp') {
        e.preventDefault();
        if (_selectedFileIndex > 0) {
            _selectedFileIndex--;
            _highlightFileRow(rows, _selectedFileIndex);
        }
    }
    if (e.key === 'Enter' && _selectedFileIndex >= 0 && _selectedFileIndex < rows.length) {
        e.preventDefault();
        rows[_selectedFileIndex].click();
    }
});

function _highlightFileRow(rows, index) {
    rows.forEach(function(r) { r.style.background = ''; });
    if (rows[index]) {
        rows[index].style.background = '#eff6ff';
        rows[index].scrollIntoView({ block: 'nearest' });
    }
}

// Ctrl+S để lưu bản dịch
document.addEventListener('keydown', function(e) {
    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        
        const resultText = document.getElementById('pm-result-text');
        const spellResultText = document.getElementById('pm-spell-result-text');
        
        if (document.activeElement === resultText || DirtyState.isDirty('pm-result-text')) {
            EditorComponent.saveChunkTranslation();
        } else if (document.activeElement === spellResultText || DirtyState.isDirty('pm-spell-result-text')) {
            EditorComponent.saveSpellcheckResult();
        }
    }
});

// ============================================================
// Persistence for Info Sub-tabs
// ============================================================
document.querySelectorAll('.nt-tab-radio').forEach(radio => {
    radio.addEventListener('change', () => {
        if (radio.checked) {
            localStorage.setItem('nt_active_info_tab', radio.id);
        }
    });
});

// ============================================================
// Initialization
// ============================================================
document.addEventListener('DOMContentLoaded', function () {
    initTabs();
    UiHelpers.initDialogs();
    
    // Load plugin configuration early
    if (window.PluginManager) {
        PluginManager.ensureLoaded();
    }

    ProjectManager.loadProjectCards();
    ApiClient.loadStats();
    ApiClient.loadModels();
    PromptManager.loadGenres();
    ApiClient.loadApiKeys();
    UiHelpers.initProvider();
    UiHelpers.restoreAppState();
    
    // Khởi tạo Auto-save
    AutoSave.init();
    
    // Khởi tạo Drag-and-drop
    ProjectManager.initDragDrop();

    // Click-outside to close Project Info Modal
    const projInfoModal = document.getElementById('project-info-modal');
    if (projInfoModal) {
        projInfoModal.addEventListener('click', function(e) {
            if (e.target === projInfoModal) ProjectManager.hideProjectInfoModal();
        });
    }

    // Spell-check tab buttons
    const btnCopySpell = document.getElementById('btn-copy-spellcheck');
    if (btnCopySpell) btnCopySpell.addEventListener('click', EditorComponent.copySpellcheckResult);
    const btnDownSpell = document.getElementById('download-spellcheck-btn');
    if (btnDownSpell) btnDownSpell.addEventListener('click', EditorComponent.downloadSpellCheckResult);
    const btnRunSpell = document.getElementById('spellcheck-btn');
    if (btnRunSpell) btnRunSpell.addEventListener('click', TranslationWorker.runSpellcheck);

    // Stats polling
    var _statsInterval = null;
    window.startStatsPolling = function() {
        if (_statsInterval) return;
        ApiClient.loadStats();
        _statsInterval = setInterval(ApiClient.loadStats, 30000);
    };
    window.stopStatsPolling = function() {
        if (_statsInterval) { clearInterval(_statsInterval); _statsInterval = null; }
    };
    startStatsPolling();

    // Temperature slider
    const tempEl = document.getElementById('temperature');
    if (tempEl) {
        tempEl.addEventListener('input', function () {
            const valEl = document.getElementById('temp-value');
            if (valEl) valEl.textContent = this.value;
        });
    }

    // Cache button removed: Translation Cache is deprecated

    // Prompt Manager buttons
    const btnDelGenre = document.getElementById('btn-delete-genre');
    if (btnDelGenre) btnDelGenre.addEventListener('click', PromptManager.deleteGenre);
    const btnCloneGenre = document.getElementById('btn-clone-genre');
    if (btnCloneGenre) btnCloneGenre.addEventListener('click', PromptManager.cloneGenre);
    const btnSaveGenre = document.getElementById('btn-save-genre');
    if (btnSaveGenre) btnSaveGenre.addEventListener('click', PromptManager.saveGenre);
    const btnUseGenre = document.getElementById('btn-use-genre');
    if (btnUseGenre) btnUseGenre.addEventListener('click', PromptManager.useGenre);


});

// ============================================================
// Legacy functions (kept for backward compatibility with HTML onclick)
// ============================================================
function showCreateProjectDialog() { ProjectManager.showCreateProjectDialog(); }
function showProjectInfoModal() { ProjectManager.showProjectInfoModal(); }
function hideProjectInfoModal() { ProjectManager.hideProjectInfoModal(); }
function saveProjectInfo() { ProjectManager.saveProjectInfo(); }
function archiveProjectFromModal() { ProjectManager.archiveProjectFromModal(); }
function deleteProjectFromModal() { ProjectManager.deleteProjectFromModal(); }
function showChunkConfig() { ProjectManager.showChunkConfig(); }
function confirmChunking() { ProjectManager.confirmChunking(); }
function selectAllProjectFiles() { ProjectManager.selectAllProjectFiles(); }
function selectAllTranslatedFiles() { ProjectManager.selectAllTranslatedFiles(); }
function mergeTranslatedFiles() { ProjectManager.mergeTranslatedFiles(); }
function translateSelectedInProject() { TranslationWorker.translateSelectedInProject(); }
function spellcheckSelectedInProject() { TranslationWorker.spellcheckSelectedInProject(); }
function startTranslation() { TranslationWorker.startTranslation(); }
function runSpellcheck() { TranslationWorker.runSpellcheck(); }
function saveChunkTranslation() { EditorComponent.saveChunkTranslation(); }
function saveSpellcheckResult() { EditorComponent.saveSpellcheckResult(); }
function copyResult() { EditorComponent.copyResult(); }
function downloadResult() { EditorComponent.downloadResult(); }
function copySpellcheckResult() { EditorComponent.copySpellcheckResult(); }
function downloadSpellCheckResult() { EditorComponent.downloadSpellCheckResult(); }
function toggleWordWrap(id) { EditorComponent.toggleWordWrap(id); }
function findInText(id) { EditorComponent.findInText(id); }
function showDiffView(s, t) { EditorComponent.showDiffView(s, t); }
function aiGenerateContent(key) { PromptManager.aiGenerateContent(key); }
function saveGuidelineField(key) { PromptManager.saveGuidelineField(key); }
function importPromptFromLibrary() { PromptManager.importPromptFromLibrary(); }
function saveProjectPrompts() { PromptManager.saveProjectPrompts(); }
function resetProjectPrompts() { PromptManager.resetProjectPrompts(); }
function loadArchiveList() { ApiClient.loadArchiveList(); }
function archiveProjectFromList(slug) { ProjectManager.archiveProjectFromList(slug); }
function downloadArchive(filename) { ProjectManager.downloadArchive(filename); }
function deleteSelectedLogs() { UiHelpers.deleteSelectedLogs(); }
function deleteCurrentLog() { UiHelpers.deleteCurrentLog(); }
function switchProvider(p) { UiHelpers.switchProvider(p); }
function saveAppConfig() { ApiClient.saveAppConfig(); }
function saveApiKeys() { ApiClient.saveApiKeys(); }
function saveOpenAIConfig() { UiHelpers.saveOpenAIConfig(); }
function restartServer() { ApiClient.restartServer(); }
function uploadProjectFile() { ProjectManager.uploadProjectFile(); }
function markModel() { ApiClient.markModel(); }
function onModelChange(m) { ApiClient.onModelChange(m); }
function loadModels() { ApiClient.loadModels(); }
function createNewProject() { ProjectManager.createNewProject(); }
function loadProjectCards() { ProjectManager.loadProjectCards(); }
function openProject(slug) { ProjectManager.openProject(slug); }
function exportProject(slug) { ProjectManager.exportProject(slug); }
function importProject() { ProjectManager.importProject(); }
function closeProgress() { TranslationWorker.closeProgress(); }

// Automatically convert native tooltips (title, alt) on hover to custom CSS tooltips
document.addEventListener('mouseover', function(e) {
    const target = e.target.closest('button, a, .pointer, [title], [alt], [data-tooltip]');
    if (target) {
        // Convert title/alt if present
        if (target.hasAttribute('title')) {
            const titleVal = target.getAttribute('title');
            if (titleVal && titleVal.trim() !== '') {
                target.setAttribute('data-tooltip', titleVal);
                if (!target.hasAttribute('aria-label')) {
                    target.setAttribute('aria-label', titleVal);
                }
                target.removeAttribute('title');
            }
        } else if (target.hasAttribute('alt') && target.tagName !== 'IMG') {
            const altVal = target.getAttribute('alt');
            if (altVal && altVal.trim() !== '') {
                target.setAttribute('data-tooltip', altVal);
                if (!target.hasAttribute('aria-label')) {
                    target.setAttribute('aria-label', altVal);
                }
                target.removeAttribute('alt');
            }
        }

        // Dynamically adjust alignment to prevent screen edge overflow clipping
        if (target.hasAttribute('data-tooltip')) {
            const rect = target.getBoundingClientRect();
            const viewportWidth = window.innerWidth;
            const tooltipText = target.getAttribute('data-tooltip') || '';

            // Approximate tooltip width (6px padding on sides + ~7px per char at 0.75rem font size)
            const approxWidth = Math.max(120, tooltipText.length * 7 + 20);
            const halfWidth = approxWidth / 2;

            // Check right edge clearance
            if (rect.left + rect.width / 2 + halfWidth > viewportWidth - 16) {
                target.classList.add('tooltip-align-right');
                target.classList.remove('tooltip-align-left');
            }
            // Check left edge clearance
            else if (rect.left + rect.width / 2 - halfWidth < 16) {
                target.classList.add('tooltip-align-left');
                target.classList.remove('tooltip-align-right');
            }
            // Reset to centered otherwise
            else {
                target.classList.remove('tooltip-align-right', 'tooltip-align-left');
            }
        }
    }
});
