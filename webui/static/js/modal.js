// ============================================================
// Modal Manager — Unified modal show/hide system
// ============================================================

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
