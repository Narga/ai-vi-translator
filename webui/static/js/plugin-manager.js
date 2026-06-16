/* Novel Translator - plugin-manager.js */

window.PluginManager = {
    _loadPromise: null,

    /**
     * Tải và cache cấu hình plugin
     */
    ensureLoaded() {
        if (window.pluginState && window.pluginState.loaded) {
            return Promise.resolve(window.pluginState.plugins);
        }
        if (this._loadPromise) {
            return this._loadPromise;
        }

        this._loadPromise = fetch('/api/plugins/list')
            .then(res => {
                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                return res.json();
            })
            .then(plugins => {
                window.pluginState = {
                    plugins: plugins || [],
                    loaded: true,
                    error: null
                };
                return window.pluginState.plugins;
            })
            .catch(err => {
                console.error("Lỗi tải danh sách plugin:", err);
                window.pluginState = {
                    plugins: [],
                    loaded: false,
                    error: err
                };
                UiHelpers.showToast("Không thể tải danh sách plugin", "error");
                return [];
            })
            .finally(() => {
                this._loadPromise = null;
            });

        return this._loadPromise;
    },

    getEnabledWorkspacePlugins() {
        if (!window.pluginState || !window.pluginState.plugins) return [];
        return window.pluginState.plugins.filter(p => p.enabled && p.workspace_tab);
    },

    getWorkspaceStore() {
        try {
            if (!window.Alpine) return null;
            return Alpine.store('workspace') || null;
        } catch (e) {
            return null;
        }
    },

    renderWorkspaceTabs() {
        if (!window.currentProject) return;

        const container = document.getElementById('pm-plugin-workspace-tabs');
        if (!container) return;

        container.innerHTML = '';
        this.getEnabledWorkspacePlugins().forEach(plugin => {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'workspace-sub-tab';
            btn.dataset.workspaceTab = plugin.workspace_tab;
            btn.textContent = plugin.name;
            btn.addEventListener('click', () => this.setWorkspaceTab(plugin.workspace_tab));
            container.appendChild(btn);
        });

        this.syncWorkspaceTabButtons();
    },

    syncWorkspaceTabButtons() {
        const store = this.getWorkspaceStore();
        const active = store ? store.wsTab : 'editor';
        document.querySelectorAll('#pm-plugin-workspace-tabs [data-workspace-tab]').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.workspaceTab === active);
        });
    },

    setWorkspaceTab(tabName) {
        const store = this.getWorkspaceStore();
        if (!store) return false;
        store.wsTab = tabName;
        this.syncWorkspaceTabButtons();
        return true;
    },

    async togglePlugin(pluginId, enabled) {
        try {
            const res = await fetch(`/api/plugins/${pluginId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled })
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.error || "Không thể cập nhật plugin");
            }

            const updatedPlugin = await res.json();
            
            // Cập nhật cache
            if (window.pluginState && window.pluginState.plugins) {
                const idx = window.pluginState.plugins.findIndex(p => p.id === pluginId);
                if (idx !== -1) {
                    window.pluginState.plugins[idx] = updatedPlugin;
                }
            }

            // Render lại tabs nếu có dự án đang mở
            if (window.currentProject) {
                this.renderWorkspaceTabs();
                
                // Nếu đang đứng ở tab vừa tắt, quay về editor
                const store = this.getWorkspaceStore();
                if (!enabled && store && store.wsTab === updatedPlugin.workspace_tab) {
                    this.setWorkspaceTab('editor');
                }
            }

            return updatedPlugin;
        } catch (err) {
            console.error("Lỗi toggle plugin:", err);
            UiHelpers.showToast(err.message, "error");
            throw err;
        }
    }
};
