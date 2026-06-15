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
            .then(res => res.json())
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

    renderWorkspaceTabs() {
        if (!window.currentProject) return;

        const container = document.getElementById('pm-plugin-workspace-tabs');
        if (!container) return;

        const plugins = this.getEnabledWorkspacePlugins();
        let html = '';

        plugins.forEach(p => {
            // Render the tab button
            html += `<button class="tab-button pv2 ph3 bn bg-transparent pointer dim" 
                            x-bind:class="$store.workspace.wsTab === '${p.workspace_tab}' ? 'blue bb bw2 b--blue fw6' : 'gray'" 
                            x-on:click="$store.workspace.wsTab = '${p.workspace_tab}'">${p.name}</button>`;
        });

        container.innerHTML = html;
    },

    setWorkspaceTab(tabName) {
        if (window.Alpine) {
            Alpine.store('workspace').wsTab = tabName;
        }
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
                if (!enabled && window.Alpine && Alpine.store('workspace').wsTab === updatedPlugin.workspace_tab) {
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
