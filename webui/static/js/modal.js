// ============================================================
// Modal Manager — Unified modal show/hide system
// ============================================================

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

const ModalManager = {
    show(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) { console.warn('Modal not found:', modalId); return; }
        modal.classList.remove('dn');
        modal.classList.add('flex');
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    },

    hide(modalId) {
        const modal = document.getElementById(modalId);
        if (!modal) return;
        modal.classList.add('dn');
        modal.classList.remove('flex');
        modal.style.display = '';
        document.body.style.overflow = '';
    },

    hideAll() {
        document.querySelectorAll('[id$="-modal"]').forEach(function(modal) {
            if (modal.classList.contains('flex') || modal.style.display === 'flex') {
                ModalManager.hide(modal.id);
            }
        });
    },

    isOpen(modalId) {
        var modal = document.getElementById(modalId);
        return modal && (modal.classList.contains('flex') || modal.style.display === 'flex');
    }
};

// ============================================================
// Custom Confirm Dialog
// Returns: Promise<boolean>
// ============================================================
function showConfirm(message, options) {
    options = options || {};
    var title = options.title || 'Xác nhận';
    var confirmText = options.confirmText || 'Đồng ý';
    var cancelText = options.cancelText || 'Hủy';
    var danger = options.danger || false;

    return new Promise(function(resolve) {
        var overlay = document.createElement('div');
        overlay.className = 'fixed absolute--fill bg-black-50 z-max items-center justify-center';
        overlay.style.cssText = 'display:flex; z-index:99999;';
        overlay.innerHTML = 
            '<div class="bg-white br3 shadow-5 w-100 mw6 pa4 animate-pop">' +
                '<h3 class="f5 mt0 mb3 fw6 dark-gray pb2 bb b--black-10">' + escapeHtml(title) + '</h3>' +
                '<p class="f6 gray mb4">' + escapeHtml(message) + '</p>' +
                '<div class="flex justify-end gap-3 pt3 bt b--black-10">' +
                    '<button class="nt-btn nt-btn-outline" data-action="cancel">' + escapeHtml(cancelText) + '</button>' +
                    '<button class="nt-btn ' + (danger ? 'nt-btn-danger' : 'nt-btn-primary') + '" data-action="confirm">' + escapeHtml(confirmText) + '</button>' +
                '</div>' +
            '</div>';
        
        document.body.appendChild(overlay);

        overlay.addEventListener('click', function(e) {
            var action = e.target.getAttribute('data-action');
            if (action === 'confirm') { resolve(true); overlay.remove(); }
            else if (action === 'cancel' || e.target === overlay) { resolve(false); overlay.remove(); }
        });
    });
}

// ============================================================
// Custom Prompt Dialog
// Returns: Promise<string|null> (null = user cancelled)
// ============================================================
function showPrompt(message, defaultValue) {
    defaultValue = defaultValue || '';

    return new Promise(function(resolve) {
        var overlay = document.createElement('div');
        overlay.className = 'fixed absolute--fill bg-black-50 z-max items-center justify-center';
        overlay.style.cssText = 'display:flex; z-index:99999;';
        overlay.innerHTML = 
            '<div class="bg-white br3 shadow-5 w-100 mw6 pa4 animate-pop">' +
                '<h3 class="f5 mt0 mb3 fw6 dark-gray pb2 bb b--black-10">Nhập thông tin</h3>' +
                '<label class="db f6 gray mb2">' + escapeHtml(message) + '</label>' +
                '<input type="text" class="nt-input w-100 mb4" value="' + escapeHtml(defaultValue) + '" id="custom-prompt-input">' +
                '<div class="flex justify-end gap-3 pt3 bt b--black-10">' +
                    '<button class="nt-btn nt-btn-outline" data-action="cancel">Hủy</button>' +
                    '<button class="nt-btn nt-btn-primary" data-action="confirm">OK</button>' +
                '</div>' +
            '</div>';
        
        document.body.appendChild(overlay);

        var input = overlay.querySelector('#custom-prompt-input');
        setTimeout(function() { input.focus(); input.select(); }, 50);

        overlay.addEventListener('click', function(e) {
            var action = e.target.getAttribute('data-action');
            if (action === 'confirm') { resolve(input.value); overlay.remove(); }
            else if (action === 'cancel' || e.target === overlay) { resolve(null); overlay.remove(); }
        });

        input.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') { resolve(input.value); overlay.remove(); }
            if (e.key === 'Escape') { resolve(null); overlay.remove(); }
        });
    });
}

// Auto-wire: close modal khi click vào overlay (background đen)
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('bg-black-70') || e.target.classList.contains('bg-black-50')) {
        var modal = e.target.closest('[id$="-modal"]');
        if (modal) ModalManager.hide(modal.id);
    }
});

// Auto-wire: close modal khi nhấn Escape
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        ModalManager.hideAll();
    }
});
