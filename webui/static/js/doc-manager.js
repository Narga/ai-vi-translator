// doc-manager.js — Project Documentation Reader
// Requires: marked.min.js loaded before this file

const DocManager = {
    _loaded: false,

    _files: [],

    loadDocList() {
        const listEl = document.getElementById('doc-list');
        const pathsInput = document.getElementById('doc-config-paths');
        const rootCheckbox = document.getElementById('doc-config-root');
        if (!listEl) return;

        // Chỉ hiển thị 'Đang tải...' ở lần load đầu
        if (!this._loaded) {
            listEl.innerHTML = '<p class="pa3 tc silver i f7">Đang tải...</p>';
        }

        // Tải cấu hình trước để đồng bộ các ô input
        fetch('/api/docs/config')
            .then(r => r.json())
            .then(config => {
                if (pathsInput) pathsInput.value = config.paths || '';
                if (rootCheckbox) rootCheckbox.checked = config.include_root !== false;

                // Sau đó tải danh sách file
                return fetch('/api/docs');
            })
            .then(r => r.json())
            .then(files => {
                this._loaded = true;
                this._files = files; // Lưu trữ danh sách để lọc nhanh offline

                // Reset ô tìm kiếm
                const queryEl = document.getElementById('doc-search-filter');
                if (queryEl) queryEl.value = '';
                const clearBtn = document.getElementById('doc-search-clear');
                if (clearBtn) clearBtn.classList.add('dn');

                if (!files.length) {
                    listEl.innerHTML = '<p class="pa3 tc silver i f7">Không tìm thấy tài liệu nào.</p>';
                    return;
                }
                listEl.innerHTML = this._buildSidebar(files);
            })
            .catch(err => {
                listEl.innerHTML = `<p class="pa3 tc red f7">Lỗi tải dữ liệu: ${err.message}</p>`;
            });
    },

    filterList() {
        const queryEl = document.getElementById('doc-search-filter');
        const listEl = document.getElementById('doc-list');
        const clearBtn = document.getElementById('doc-search-clear');
        if (!queryEl || !listEl || !this._files) return;

        const query = queryEl.value.trim().toLowerCase();

        // Ẩn/hiện nút xóa nhanh keyword
        if (clearBtn) {
            if (queryEl.value) {
                clearBtn.classList.remove('dn');
            } else {
                clearBtn.classList.add('dn');
            }
        }

        if (!query) {
            listEl.innerHTML = this._buildSidebar(this._files);
            return;
        }

        const filtered = this._files.filter(f => 
            f.name.toLowerCase().includes(query) || 
            f.path.toLowerCase().includes(query)
        );

        if (!filtered.length) {
            listEl.innerHTML = '<p class="pa3 tc silver i f7">Không tìm thấy tài liệu phù hợp.</p>';
            return;
        }

        listEl.innerHTML = this._buildSidebar(filtered);
    },

    clearFilter() {
        const queryEl = document.getElementById('doc-search-filter');
        if (queryEl) {
            queryEl.value = '';
            this.filterList();
        }
    },

    _buildSidebar(files) {
        // Nhóm theo thư mục
        const groups = {};
        files.forEach(f => {
            const dir = f.dir || '_root_';
            if (!groups[dir]) groups[dir] = [];
            groups[dir].push(f);
        });

        let html = '';

        // File gốc trước
        if (groups['_root_']) {
            groups['_root_'].forEach(f => {
                html += this._fileItem(f);
            });
        }

        // Sau đó các thư mục con
        Object.keys(groups).sort().forEach(dir => {
            if (dir === '_root_') return;
            html += `<div class="mt2 mb1">
                <p class="f7 silver fw6 tracked ttu ma0 ph2 pv1">${dir}</p>
                ${groups[dir].map(f => this._fileItem(f)).join('')}
            </div>`;
        });

        return html;
    },

    _fileItem(f) {
        const icon = f.ext === '.md' ? '📝' : f.ext === '.html' ? '🌐' : '📄';
        const escapedPath = f.path.replace(/"/g, '&quot;');
        return `<button
            class="doc-list-item w-100 tl pa2 f7 pointer bg-transparent bn br2 hover-bg-near-white dark-gray flex items-center gap-1"
            onclick="DocManager.loadDoc('${escapedPath}', this)"
            title="${escapedPath}">
            <span>${icon}</span>
            <span class="truncate">${f.name}</span>
        </button>`;
    },

    loadDoc(path, triggerEl) {
        // Highlight active
        document.querySelectorAll('.doc-list-item').forEach(el => el.classList.remove('doc-item-active'));
        if (triggerEl) triggerEl.classList.add('doc-item-active');

        const contentEl = document.getElementById('doc-reader-content');
        const titleEl = document.getElementById('doc-reader-title');
        const pathEl = document.getElementById('doc-reader-path');

        if (!contentEl) return;

        contentEl.innerHTML = '<p class="tc silver i mt5 f7">⏳ Đang tải...</p>';
        if (titleEl) titleEl.textContent = path.split('/').pop();
        if (pathEl) pathEl.textContent = path;

        fetch(`/api/docs/content?path=${encodeURIComponent(path)}`)
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    contentEl.innerHTML = `<p class="red pa3">${data.error}</p>`;
                    return;
                }
                if (data.ext === '.md') {
                    if (typeof marked !== 'undefined') {
                        contentEl.innerHTML = `<div class="doc-markdown">${marked.parse(data.content)}</div>`;
                    } else {
                        contentEl.innerHTML = `<pre class="doc-preformatted">${this._escape(data.content)}</pre>`;
                    }
                } else if (data.ext === '.html') {
                    contentEl.innerHTML = `<pre class="doc-preformatted">${this._escape(data.content)}</pre>`;
                } else {
                    contentEl.innerHTML = `<pre class="doc-preformatted">${this._escape(data.content)}</pre>`;
                }
                contentEl.scrollTop = 0;
            })
            .catch(err => {
                contentEl.innerHTML = `<p class="red pa3">Lỗi: ${err.message}</p>`;
            });
    },

    saveConfig() {
        const pathsInput = document.getElementById('doc-config-paths');
        const rootCheckbox = document.getElementById('doc-config-root');
        if (!pathsInput || !rootCheckbox) return;

        const paths = pathsInput.value;
        const include_root = rootCheckbox.checked;

        const button = document.querySelector('button[onclick="DocManager.saveConfig()"]');
        if (button) {
            button.disabled = true;
            button.textContent = 'Đang lưu...';
        }

        fetch('/api/docs/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ paths, include_root })
        })
        .then(r => r.json())
        .then(res => {
            if (res.success) {
                // Đặt lại load để tải lại danh sách file mới
                this._loaded = false;
                this.loadDocList();
            } else {
                alert('Có lỗi xảy ra khi lưu cấu hình.');
            }
        })
        .catch(err => {
            alert('Lỗi kết nối: ' + err.message);
        })
        .finally(() => {
            if (button) {
                button.disabled = false;
                button.textContent = 'Lưu cấu hình';
            }
        });
    },

    _escape(str) {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }
};
