// doc-manager.js — Project Documentation Reader
// Requires: marked.min.js loaded before this file

const DocManager = {
    _loaded: false,

    loadDocList() {
        if (this._loaded) return;  // Cache: chỉ load 1 lần mỗi session

        const listEl = document.getElementById('doc-list');
        if (!listEl) return;

        listEl.innerHTML = '<p class="pa3 tc silver i f7">Đang tải...</p>';

        fetch('/api/docs')
            .then(r => r.json())
            .then(files => {
                this._loaded = true;
                if (!files.length) {
                    listEl.innerHTML = '<p class="pa3 tc silver i f7">Không tìm thấy tài liệu nào.</p>';
                    return;
                }
                listEl.innerHTML = this._buildSidebar(files);
            })
            .catch(err => {
                listEl.innerHTML = `<p class="pa3 tc red f7">Lỗi tải danh sách: ${err.message}</p>`;
            });
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
                    // Dùng marked.js để render Markdown
                    if (typeof marked !== 'undefined') {
                        contentEl.innerHTML = `<div class="doc-markdown">${marked.parse(data.content)}</div>`;
                    } else {
                        // Fallback: hiển thị text thô nếu marked chưa load
                        contentEl.innerHTML = `<pre class="doc-preformatted">${this._escape(data.content)}</pre>`;
                    }
                } else if (data.ext === '.html') {
                    // HTML: hiển thị source code, không render để tránh XSS
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

    _escape(str) {
        return str
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;');
    }
};
