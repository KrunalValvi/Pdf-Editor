/**
 * PDF Footer Editor
 */
class PDFFooterEditor {
    constructor() {
        this.sessionId = null;
        this.currentPage = 1;
        this.totalPages = 0;
        this.zoom = 1.0;
        this.textBlocks = [];
        this.selectedBlock = null;
        this.undoStack = [];
        this.redoStack = [];
        this.findResults = [];
        this.activeTool = 'select';
        this.fileName = '';
        this.imageVersion = 0;
        this.isMobile = window.matchMedia('(max-width: 768px)').matches || 
                        (window.matchMedia('(hover: none) and (pointer: coarse)').matches && window.innerWidth < 1024);
        this.activeSheet = null;
        this.mFindResults = [];
        this.mFindIndex = -1;
        this.renderZoom = 1.0;
        this.renderGen = 0;
        this._zoomTimer = null;
        this._baseWidth = 0;
        this._baseHeight = 0;

        this.init();
    }

    init() {
        this.bindEvents();
        this.setupDragAndDrop();
        this.setupKeyboardShortcuts();
        if (this.isMobile) this.initMobile();
    }

    /* ========================================
       EVENT BINDING
       ======================================== */
    bindEvents() {
        // Empty state open
        this.$('btn-open-empty').addEventListener('click', () => this.openFile());

        // Top bar
        this.$('btn-save').addEventListener('click', () => { this.closeExportPop(); this.exportPDF(); });
        this.$('btn-undo').addEventListener('click', () => this.undo());
        this.$('btn-redo').addEventListener('click', () => this.redo());
        this.$('btn-zoom-in').addEventListener('click', () => this.zoomIn());
        this.$('btn-zoom-out').addEventListener('click', () => this.zoomOut());
        this.$('btn-fit-page').addEventListener('click', () => this.fitPage());
        this.$('btn-export').addEventListener('click', () => this.toggleExportPop());

        // Tool rail
        document.querySelectorAll('.rail-btn[data-tool]').forEach(btn => {
            btn.addEventListener('click', () => this.selectTool(btn.dataset.tool));
        });

        // Pages drawer
        this.$('btn-toggle-pages').addEventListener('click', () => this.togglePagesDrawer());

        // Right panel close
        this.$('btn-close-panel').addEventListener('click', () => this.closePanel());

        // File input
        this.$('file-input').addEventListener('change', e => this.handleFileSelect(e));

        // Modal
        this.$('modal-close').addEventListener('click', () => this.closeModal());
        this.$('modal-cancel').addEventListener('click', () => this.closeModal());
        this.$('modal-apply').addEventListener('click', () => this.applyTextChange());

        // Modal scope radio
        document.querySelectorAll('input[name="modal-scope"]').forEach(radio => {
            radio.addEventListener('change', e => {
                // just for the modal
            });
        });

        // Page range radio (sidebar)
        document.querySelectorAll('input[name="apply-scope"]').forEach(radio => {
            radio.addEventListener('change', e => {
                this.$('page-range').style.display = e.target.value === 'range' ? '' : 'none';
            });
        });

        // Edit panel apply
        this.$('btn-apply-edit').addEventListener('click', () => this.applyQuickEdit());

        // Find overlay
        this.$('find-input').addEventListener('input', () => this.findAllAcrossPages());
        this.$('btn-close-find').addEventListener('click', () => this.closeFind());
        this.$('replaceToggle').addEventListener('click', () => this.toggleReplaceRow());
        this.$('btn-replace-selected').addEventListener('click', () => this.replaceSelectedOccurrences());
        this.$('btn-replace-all').addEventListener('click', () => this.replaceAllOccurrences());

        // Command palette
        this.$('btn-cmd-palette').addEventListener('click', () => this.toggleCmdPalette());
        this.$('cmd-palette').addEventListener('click', e => {
            if (e.target === this.$('cmd-palette')) this.closeCmdPalette();
        });
        this.$('cmd-input').addEventListener('input', e => this.filterCommands(e.target.value));
        document.querySelectorAll('.cmd-item').forEach(item => {
            item.addEventListener('click', () => this.runCommand(item.dataset.action));
        });

        // Close export pop on outside click
        document.addEventListener('click', e => {
            if (!e.target.closest('.export-wrap')) this.closeExportPop();
        });
    }

    /* ========================================
       DRAG & DROP
       ======================================== */
    setupDragAndDrop() {
        let dragCounter = 0;
        const overlay = this.$('drop-overlay');

        document.addEventListener('dragenter', e => {
            e.preventDefault();
            dragCounter++;
            if (this.$('editor').classList.contains('active')) {
                overlay.classList.add('active');
            }
        });

        document.addEventListener('dragleave', () => {
            dragCounter--;
            if (dragCounter <= 0) { dragCounter = 0; overlay.classList.remove('active'); }
        });

        document.addEventListener('dragover', e => e.preventDefault());

        document.addEventListener('drop', e => {
            e.preventDefault();
            dragCounter = 0;
            overlay.classList.remove('active');
            const files = e.dataTransfer.files;
            if (files.length > 0) this.loadFile(files[0]);
        });
    }

    /* ========================================
       KEYBOARD SHORTCUTS
       ======================================== */
    setupKeyboardShortcuts() {
        document.addEventListener('keydown', e => {
            // Ignore if typing in input
            if (['INPUT', 'TEXTAREA'].includes(e.target.tagName)) {
                if (e.key === 'Escape') e.target.blur();
                return;
            }

            if (e.ctrlKey && e.key === 'o') { e.preventDefault(); this.openFile(); }
            if (e.ctrlKey && e.key === 's') { e.preventDefault(); this.exportPDF(); }
            if (e.ctrlKey && e.key === 'z') { e.preventDefault(); this.undo(); }
            if (e.ctrlKey && e.key === 'y') { e.preventDefault(); this.redo(); }
            if (e.ctrlKey && e.key === '=') { e.preventDefault(); this.zoomIn(); }
            if (e.ctrlKey && e.key === '-') { e.preventDefault(); this.zoomOut(); }
            if (e.ctrlKey && e.key === 'k') { e.preventDefault(); this.toggleCmdPalette(); }
            if (e.ctrlKey && e.key === 'f') {
                e.preventDefault();
                this.openFind();
            }

            if (!e.ctrlKey && !e.metaKey) {
                if (e.key.toLowerCase() === 'e') this.selectTool('select');
                if (e.key.toLowerCase() === 'n') this.selectTool('select');
            }

            if (e.key === 'Escape') {
                this.closeCmdPalette();
                this.closeModal();
                this.closeFind();
                this.deselectText();
            }
        });
    }

    /* ========================================
       COMMAND PALETTE
       ======================================== */
    toggleCmdPalette() {
        const el = this.$('cmd-palette');
        if (el.style.display === 'none' || !el.style.display) {
            el.style.display = 'flex';
            this.$('cmd-input').value = '';
            this.$('cmd-input').focus();
            this.filterCommands('');
        } else {
            this.closeCmdPalette();
        }
    }

    closeCmdPalette() {
        this.$('cmd-palette').style.display = 'none';
    }

    filterCommands(query) {
        const q = query.toLowerCase();
        document.querySelectorAll('.cmd-item').forEach(item => {
            const text = item.textContent.toLowerCase();
            item.style.display = text.includes(q) ? '' : 'none';
        });
    }

    runCommand(action) {
        this.closeCmdPalette();
        switch (action) {
            case 'open': this.openFile(); break;
            case 'export': this.exportPDF(); break;
            case 'find': this.openFind(); break;
            case 'undo': this.undo(); break;
            case 'redo': this.redo(); break;
            case 'zoomin': this.zoomIn(); break;
            case 'zoomout': this.zoomOut(); break;
            case 'fitpage': this.fitPage(); break;
        }
    }

    /* ========================================
       TOOL / PANEL MANAGEMENT
       ======================================== */
    selectTool(tool) {
        this.activeTool = tool;

        // Update rail buttons
        document.querySelectorAll('.rail-btn[data-tool]').forEach(b => {
            b.classList.toggle('active', b.dataset.tool === tool);
        });

        if (tool === 'find') {
            this.openFind();
        } else {
            this.closeFind();
        }

        if (tool === 'select') {
            this.closePanel();
        }
    }

    openPanel(title) {
        this.$('rpTitle').textContent = title;
        this.$('rightPanel').classList.add('open');
        document.querySelectorAll('.rp-panel').forEach(p => p.classList.remove('active'));
        const panel = document.querySelector('.rp-panel[data-panel="select"]');
        if (panel) panel.classList.add('active');
    }

    closePanel() {
        this.$('rightPanel').classList.remove('open');
    }

    togglePagesDrawer() {
        this.$('pagesDrawer').classList.toggle('open');
    }

    /* ========================================
       EXPORT POPUP
       ======================================== */
    toggleExportPop() {
        this.$('exportPop').classList.toggle('open');
    }

    closeExportPop() {
        this.$('exportPop').classList.remove('open');
    }

    /* ========================================
       FIND OVERLAY
       ======================================== */
    openFind() {
        if (this.isMobile) {
            this.openSheet('m-find-sheet');
            setTimeout(() => this.$('m-find-input').focus(), 350);
            return;
        }
        this.$('findOverlay').classList.add('open');
        this.$('find-input').focus();
        this.$('find-input').select();
    }

    closeFind() {
        if (this.isMobile) {
            if (this.activeSheet === 'm-find-sheet') this.closeSheet();
            return;
        }
        this.$('findOverlay').classList.remove('open');
    }

    toggleReplaceRow() {
        const open = this.$('findReplaceRow').classList.toggle('open');
        const btn = this.$('replaceToggle');
        btn.classList.toggle('active', open);
        btn.title = open ? 'Hide replace field' : 'Show replace field';
    }

    /* ========================================
       FILE OPENING
       ======================================== */
    openFile() {
        this.$('file-input').click();
    }

    handleFileSelect(e) {
        const files = e.target.files;
        if (files.length > 0) this.loadFile(files[0]);
    }

    async loadFile(file) {
        if (!file.name.toLowerCase().endsWith('.pdf')) {
            this.showToast('Please select a PDF file', 'error');
            return;
        }

        this.showLoading('Opening PDF...');

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('/api/pdf/open', { method: 'POST', body: formData });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to open PDF');
            }

            const data = await response.json();
            this.sessionId = data.session_id;
            this.totalPages = data.info.page_count;
            this.currentPage = 1;
            this.fileName = file.name;

            this.showEditor();
            await this.loadThumbnails();
            await this.loadPage(1);

            this.showToast(`Opened ${file.name}`, 'success');

        } catch (error) {
            this.showToast(error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    showEditor() {
        this.$('emptyState').style.display = 'none';
        this.$('editor').classList.add('active');
        if (!this.isMobile) this.$('pagesDrawer').classList.add('open');
        this.$('fname').textContent = this.fileName;
        this.$('page-count').textContent = this.totalPages;
        if (this.isMobile) {
            this.$('m-filename').textContent = this.fileName;
            this.$('m-pages-count').textContent = this.totalPages;
            setTimeout(() => this.fitPage(), 100);
        }
    }

    /* ========================================
       THUMBNAILS
       ======================================== */
    async loadThumbnails() {
        const list = this.$('thumbnail-list');
        list.innerHTML = '';

        for (let i = 1; i <= this.totalPages; i++) {
            const el = document.createElement('div');
            el.className = 'page-thumb' + (i === this.currentPage ? ' current' : '');
            el.dataset.page = i;

            const box = document.createElement('div');
            box.className = 'thumb-box';

            const img = document.createElement('img');
            img.src = `/api/pdf/${this.sessionId}/page/${i}/thumbnail`;
            img.alt = `Page ${i}`;
            img.loading = 'lazy';

            const num = document.createElement('div');
            num.className = 'thumb-num';
            num.textContent = i;

            box.appendChild(img);
            el.appendChild(box);
            el.appendChild(num);
            el.addEventListener('click', () => this.loadPage(i));
            list.appendChild(el);
        }
    }

    /* ========================================
       PAGE LOADING
       ======================================== */
    async loadPage(pageNumber) {
        if (!this.sessionId || pageNumber < 1 || pageNumber > this.totalPages) return;

        this.currentPage = pageNumber;
        this.updatePageInfo();
        this.updateThumbnailHighlight();

        const gen = ++this.renderGen;

        try {
            const viewerContent = this.$('viewer-content');

            const container = document.createElement('div');
            container.className = 'pdf-page-container';

            const img = document.createElement('img');
            img.src = `/api/pdf/${this.sessionId}/page/${pageNumber}?zoom=${this.zoom}&v=${this.imageVersion}`;
            img.alt = `Page ${pageNumber}`;
            container.appendChild(img);

            await new Promise((resolve, reject) => {
                img.onload = resolve;
                img.onerror = () => reject(new Error('Failed to load image'));
            });

            if (gen !== this.renderGen) return;

            this.renderZoom = this.zoom;
            this._baseWidth = img.naturalWidth;
            this._baseHeight = img.naturalHeight;

            container.style.zoom = '';

            viewerContent.innerHTML = '';
            viewerContent.appendChild(container);

            await this.loadTextOverlay(pageNumber, container, img);

        } catch (error) {
            console.error('Error loading page:', error);
        }
    }

    async loadTextOverlay(pageNumber, container, img) {
        try {
            const response = await fetch(`/api/pdf/${this.sessionId}/page/${pageNumber}/text`);
            if (!response.ok) return;

            const data = await response.json();
            this.textBlocks = data.blocks;

            const overlay = document.createElement('div');
            overlay.className = 'text-overlay';

            const scale = img.clientWidth / img.naturalWidth;

            data.blocks.forEach((block, index) => {
                const el = document.createElement('div');
                el.className = 'text-block';
                el.dataset.index = index;

                const x = block.bbox[0] * scale;
                const y = block.bbox[1] * scale;
                const w = (block.bbox[2] - block.bbox[0]) * scale;
                const h = (block.bbox[3] - block.bbox[1]) * scale;

                el.style.cssText = `left:${x}px;top:${y}px;width:${w}px;height:${h}px;`;

                el.addEventListener('click', e => {
                    e.stopPropagation();
                    this.selectTextBlock(block, el);
                });

                overlay.appendChild(el);
            });

            container.appendChild(overlay);
        } catch (error) {
            console.error('Error loading text overlay:', error);
        }
    }

    /* ========================================
       TEXT SELECTION & EDITING
       ======================================== */
    selectTextBlock(block, element) {
        this.deselectText();
        this.selectedBlock = block;
        element.classList.add('selected');

        if (this.isMobile) {
            this.openMobileEditSheet(block);
            return;
        }

        // Open panel
        this.openPanel('Edit Text');
        this.updateEditPanel(block);
        this.showInlineEditor(block, element);
    }

    deselectText() {
        document.querySelectorAll('.text-block.selected').forEach(el => el.classList.remove('selected'));
        document.querySelectorAll('.text-block.editing').forEach(el => el.classList.remove('editing'));
        const existing = document.querySelector('.inline-editor');
        if (existing) existing.remove();
        this.selectedBlock = null;
        this.resetEditPanel();
        if (this.isMobile && this.activeSheet === 'm-edit-sheet') this.closeSheet();
    }

    showInlineEditor(block, element) {
        document.querySelectorAll('.inline-editor').forEach(el => el.remove());
        element.classList.add('editing');

        const container = this.$('viewer-content');
        const img = container.querySelector('.pdf-page-container img');
        if (!img) return;

        const scale = img.clientWidth / img.naturalWidth;
        const x = block.bbox[0] * scale;
        const y = block.bbox[1] * scale;
        const w = (block.bbox[2] - block.bbox[0]) * scale;
        const h = (block.bbox[3] - block.bbox[1]) * scale;

        const editor = document.createElement('div');
        editor.className = 'inline-editor';
        editor.style.cssText = `left:${x}px;top:${y}px;width:${w}px;min-height:${h}px;font-size:${Math.max(block.font_size * scale, 10)}px;color:rgb(${block.color.join(',')});font-family:sans-serif;`;

        const textarea = document.createElement('textarea');
        textarea.className = 'inline-editor-input';
        textarea.value = block.text;
        textarea.style.cssText = `width:100%;min-height:${h}px;font-size:inherit;color:inherit;font-family:inherit;background:transparent;border:none;outline:none;resize:none;padding:0;margin:0;line-height:1.2;overflow:hidden;`;

        textarea.addEventListener('input', () => {
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
        });

        textarea.addEventListener('keydown', e => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.applyInlineEdit(textarea.value);
            } else if (e.key === 'Escape') {
                this.deselectText();
            }
        });

        textarea.addEventListener('blur', e => {
            setTimeout(() => {
                if (!document.querySelector('.inline-editor')) return;
                const newText = textarea.value;
                if (newText !== block.text) {
                    this.applyInlineEdit(newText);
                } else {
                    this.deselectText();
                }
            }, 150);
        });

        editor.appendChild(textarea);
        element.appendChild(editor);

        requestAnimationFrame(() => {
            textarea.focus();
            textarea.select();
            textarea.style.height = 'auto';
            textarea.style.height = textarea.scrollHeight + 'px';
        });
    }

    updateEditPanel(block) {
        this.$('edit-selected-text').textContent = block.text;
        this.$('edit-font-name').textContent = block.font_name || '—';
        this.$('edit-font-size').value = Math.round(block.font_size);
        this.$('edit-font-color').value = this.rgbToHex(block.color);
        this.$('editor-text').value = block.text;
        this.$('btn-apply-edit').disabled = false;
    }

    resetEditPanel() {
        this.$('edit-selected-text').textContent = 'Click text on the PDF to select it.';
        this.$('edit-font-name').textContent = '—';
        this.$('edit-font-size').value = 12;
        this.$('edit-font-color').value = '#000000';
        this.$('editor-text').value = '';
        this.$('btn-apply-edit').disabled = true;
    }

    /* ========================================
       PDF API CALLS (PDF ENGINE - DON'T CHANGE)
       ======================================== */
    async applyInlineEdit(newText) {
        if (!this.selectedBlock || !newText.trim()) {
            this.deselectText();
            return;
        }

        this.showLoading('Applying changes...');

        try {
            const response = await fetch(`/api/pdf/${this.sessionId}/replace-text`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    page_number: this.currentPage,
                    original_text: this.selectedBlock.text,
                    new_text: newText,
                    bbox: this.selectedBlock.bbox
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to apply changes');
            }

            const result = await response.json();
            this.showToast(result.message || 'Text updated', 'success');
            this.selectedBlock = null;
            this.refreshPage();

        } catch (error) {
            this.showToast(error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async applyQuickEdit() {
        if (!this.selectedBlock) return;

        const newText = this.$('editor-text').value;
        const fontSize = parseFloat(this.$('edit-font-size').value);
        const color = this.$('edit-font-color').value;

        this.showLoading('Applying changes...');

        try {
            const response = await fetch(`/api/pdf/${this.sessionId}/replace-text`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    page_number: this.currentPage,
                    original_text: this.selectedBlock.text,
                    new_text: newText,
                    bbox: this.selectedBlock.bbox,
                    font_size: fontSize,
                    color: this.hexToRgb(color)
                })
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to apply changes');
            }

            this.showToast('Changes applied', 'success');
            this.refreshPage();

        } catch (error) {
            this.showToast(error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    openTextEditModal() {
        if (!this.selectedBlock) return;
        this.$('edit-text-original').value = this.selectedBlock.text;
        this.$('edit-text-new').value = this.selectedBlock.text;
        this.$('edit-font-size-modal').value = this.selectedBlock.font_size;
        this.$('edit-font-color-modal').value = this.rgbToHex(this.selectedBlock.color);
        this.$('text-editor-modal').classList.add('active');
    }

    closeModal() {
        this.$('text-editor-modal').classList.remove('active');
    }

    async applyTextChange() {
        const newText = this.$('edit-text-new').value;
        const scope = document.querySelector('input[name="modal-scope"]:checked').value;

        if (!newText.trim()) {
            this.showToast('Please enter replacement text', 'warning');
            return;
        }

        this.showLoading('Applying changes...');

        try {
            let endpoint = `/api/pdf/${this.sessionId}/replace-text`;
            let body = {
                page_number: this.currentPage,
                original_text: this.selectedBlock.text,
                new_text: newText,
                bbox: this.selectedBlock.bbox
            };

            if (scope === 'all') {
                endpoint = `/api/pdf/${this.sessionId}/replace-footer-all`;
                body = { search_text: this.selectedBlock.text, new_text: newText, case_sensitive: false };
            }

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to apply changes');
            }

            const result = await response.json();
            this.showToast(result.message || 'Changes applied', 'success');
            this.refreshPage();
            this.closeModal();

        } catch (error) {
            this.showToast(error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async exportPDF() {
        if (!this.sessionId) return;

        this.showLoading('Preparing PDF...');

        try {
            const response = await fetch(`/api/pdf/${this.sessionId}/download`);
            if (!response.ok) throw new Error('Failed to export PDF');

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = this.fileName.replace('.pdf', '') + '_edited.pdf';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            window.URL.revokeObjectURL(url);

            this.showToast('PDF exported successfully', 'success');

        } catch (error) {
            this.showToast(error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async undo() {
        if (!this.sessionId) return;
        try {
            const r = await fetch(`/api/pdf/${this.sessionId}/undo`, { method: 'POST' });
            const result = await r.json();
            if (result.success) this.refreshPage();
            this.showToast(result.message, 'info');
        } catch (error) { console.error(error); }
    }

    async redo() {
        if (!this.sessionId) return;
        try {
            const r = await fetch(`/api/pdf/${this.sessionId}/redo`, { method: 'POST' });
            const result = await r.json();
            if (result.success) this.refreshPage();
            this.showToast(result.message, 'info');
        } catch (error) { console.error(error); }
    }

    /* ========================================
       ZOOM & NAVIGATION
       ======================================== */
    refreshPage() {
        clearTimeout(this._zoomTimer);
        this.imageVersion++;
        this.loadPage(this.currentPage);
    }

    setZoom(newZoom) {
        newZoom = Math.max(0.25, Math.min(3.0, newZoom));
        if (Math.abs(newZoom - this.zoom) < 0.001) return;
        this.zoom = newZoom;
        this.updateZoomLevel();
        if (!this.sessionId) return;
        this.applyVisualZoom();
        this.scheduleRender();
    }

    applyVisualZoom() {
        const container = document.querySelector('.pdf-page-container');
        if (!container || !this.renderZoom || this.renderZoom < 0.001) return;
        const factor = this.zoom / this.renderZoom;
        container.style.zoom = factor;
    }

    scheduleRender() {
        clearTimeout(this._zoomTimer);
        this._zoomTimer = setTimeout(() => this.performRender(), 300);
    }

    async performRender() {
        const gen = ++this.renderGen;
        const pageNumber = this.currentPage;

        try {
            const viewerContent = this.$('viewer-content');

            const container = document.createElement('div');
            container.className = 'pdf-page-container';

            const img = document.createElement('img');
            img.src = `/api/pdf/${this.sessionId}/page/${pageNumber}?zoom=${this.zoom}&v=${this.imageVersion}`;
            img.alt = `Page ${pageNumber}`;
            container.appendChild(img);

            await new Promise((resolve, reject) => {
                img.onload = resolve;
                img.onerror = () => reject(new Error('Failed to load image'));
            });

            if (gen !== this.renderGen) return;

            this.renderZoom = this.zoom;
            this._baseWidth = img.naturalWidth;
            this._baseHeight = img.naturalHeight;

            viewerContent.innerHTML = '';
            viewerContent.appendChild(container);

            await this.loadTextOverlay(pageNumber, container, img);

        } catch (error) {
            console.error('Error performing render:', error);
        }
    }

    zoomIn() { this.setZoom(this.zoom + 0.25); }
    zoomOut() { this.setZoom(this.zoom - 0.25); }

    fitWidth() {
        const w = this.$('viewer-content').clientWidth - 64;
        this.setZoom(w / 595);
    }

    fitPage() {
        const c = this.$('viewer-content');
        if (this.isMobile) {
            this.setZoom((c.clientWidth - 16) / 595);
        } else {
            const zx = (c.clientWidth - 64) / 595;
            const zy = (c.clientHeight - 64) / 842;
            this.setZoom(Math.min(zx, zy));
        }
    }

    updateZoomLevel() {
        const pct = Math.round(this.zoom * 100) + '%';
        this.$('zoom-level').textContent = pct;
    }

    prevPage() { if (this.currentPage > 1) this.loadPage(this.currentPage - 1); }
    nextPage() { if (this.currentPage < this.totalPages) this.loadPage(this.currentPage + 1); }

    updatePageInfo() {
        this.$('page-info').textContent = `${this.currentPage} / ${this.totalPages}`;
        const mInfo = this.$('m-page-info');
        if (mInfo) mInfo.textContent = `${this.currentPage} / ${this.totalPages}`;
    }

    updateThumbnailHighlight() {
        document.querySelectorAll('.page-thumb').forEach(item => {
            const isActive = parseInt(item.dataset.page) === this.currentPage;
            item.classList.toggle('current', isActive);
            if (isActive) item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        });
    }

    /* ========================================
       FIND & REPLACE
       ======================================== */
    async findAllAcrossPages() {
        if (!this.sessionId) return;

        const searchText = this.$('find-input').value.trim();
        if (!searchText) {
            this.$('find-count').textContent = '';
            return;
        }

        try {
            const response = await fetch(`/api/pdf/${this.sessionId}/find-across-pages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ search_text: searchText, case_sensitive: false })
            });

            if (!response.ok) throw new Error('Search failed');

            const result = await response.json();
            this.findResults = result.occurrences;
            this.$('find-count').textContent = result.total_count > 0
                ? `${result.total_count} of ${result.total_count}`
                : 'No matches';
            this.$('find-pages-count').textContent = `(${this.totalPages})`;

        } catch (error) {
            console.error(error);
        }
    }

    async replaceSelectedOccurrences() {
        if (!this.findResults || this.findResults.length === 0) return;
        const newText = this.$('replace-input').value;
        if (!newText) { this.showToast('Enter replacement text', 'warning'); return; }
        await this.replaceOccurrences(this.findResults, newText);
    }

    async replaceAllOccurrences() {
        if (!this.findResults || this.findResults.length === 0) return;
        const newText = this.$('replace-input').value;
        if (!newText) { this.showToast('Enter replacement text', 'warning'); return; }
        await this.replaceOccurrences(this.findResults, newText);
    }

    async replaceOccurrences(occurrences, newText) {
        if (!this.sessionId || occurrences.length === 0) return;

        this.showLoading(`Replacing ${occurrences.length} occurrences...`);

        try {
            let count = 0;
            const byPage = {};
            for (const occ of occurrences) {
                if (!byPage[occ.page_number]) byPage[occ.page_number] = [];
                byPage[occ.page_number].push(occ);
            }

            for (const [pageNum, occs] of Object.entries(byPage)) {
                for (const occ of occs) {
                    const r = await fetch(`/api/pdf/${this.sessionId}/replace-text`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            page_number: parseInt(pageNum),
                            original_text: occ.text,
                            new_text: newText,
                            bbox: occ.bbox
                        })
                    });
                    if (r.ok) count++;
                }
            }

            this.showToast(`Replaced ${count} occurrence${count !== 1 ? 's' : ''}`, 'success');
            this.refreshPage();
            await this.findAllAcrossPages();

        } catch (error) {
            this.showToast(error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    /* ========================================
       HELPERS
       ======================================== */
    parsePageRange(str) {
        const pages = [];
        for (const part of str.split(',')) {
            if (part.includes('-')) {
                const [s, e] = part.split('-').map(Number);
                for (let i = s; i <= e; i++) {
                    if (i >= 1 && i <= this.totalPages) pages.push(i);
                }
            } else {
                const p = parseInt(part);
                if (p >= 1 && p <= this.totalPages) pages.push(p);
            }
        }
        return [...new Set(pages)].sort((a, b) => a - b);
    }

    rgbToHex(rgb) {
        if (!rgb || !Array.isArray(rgb)) return '#000000';
        return '#' + rgb.map(v => Math.round(v * 255).toString(16).padStart(2, '0')).join('');
    }

    hexToRgb(hex) {
        const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
        return m ? [parseInt(m[1], 16) / 255, parseInt(m[2], 16) / 255, parseInt(m[3], 16) / 255] : [0, 0, 0];
    }

    esc(text) {
        const d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }

    $(id) { return document.getElementById(id); }

    /* ========================================
       UI STATES
       ======================================== */
    showLoading(message = 'Processing...') {
        this.$('loading-text').textContent = message;
        this.$('loading-overlay').classList.add('active');
    }

    hideLoading() {
        this.$('loading-overlay').classList.remove('active');
    }

    showToast(message, type = 'info') {
        const container = this.$('toast-container');
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icons = {
            success: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>',
            error: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
            warning: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
            info: '<svg class="toast-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>'
        };

        toast.innerHTML = `${icons[type] || icons.info}<span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 200);
        }, 3000);
    }
    /* ========================================
       MOBILE INITIALIZATION
       ======================================== */
    initMobile() {
        this.setupMobileToolbar();
        this.setupMobileTopBar();
        this.setupSheetOverlay();
        this.setupMobileEditSheet();
        this.setupMobileFindSheet();
        this.setupMobilePagesSheet();
        this.setupMobileFooterSheet();
        this.setupMobilePageNumbersSheet();
        this.setupMobileExportSheet();
        this.setupMobileImagePicker();
        this.setupPinchZoom();
        this.setupViewportHeight();
    }

    setupViewportHeight() {
        const setVH = () => {
            const vh = window.visualViewport ? window.visualViewport.height : window.innerHeight;
            document.documentElement.style.setProperty('--vh', `${vh * 0.01}px`);
        };
        setVH();
        if (window.visualViewport) {
            window.visualViewport.addEventListener('resize', setVH);
        }
        window.addEventListener('resize', setVH);
    }

    /* ========================================
       MOBILE TOP BAR
       ======================================== */
    setupMobileTopBar() {
        this.$('m-back').addEventListener('click', () => {
            if (this.sessionId) this.closePDF();
        });
        this.$('m-undo').addEventListener('click', () => this.undo());
        this.$('m-redo').addEventListener('click', () => this.redo());
        this.$('m-export-btn').addEventListener('click', () => this.openSheet('m-export-sheet'));
    }

    closePDF() {
        if (this.sessionId) {
            fetch(`/api/pdf/${this.sessionId}`, { method: 'DELETE' }).catch(() => {});
            this.sessionId = null;
        }
        this.$('editor').classList.remove('active');
        this.$('emptyState').style.display = '';
        this.deselectText();
        this.closeSheet();
    }

    /* ========================================
       MOBILE TOOLBAR
       ======================================== */
    setupMobileToolbar() {
        document.querySelectorAll('.m-tool-btn[data-mtool]').forEach(btn => {
            btn.addEventListener('click', () => {
                const tool = btn.dataset.mtool;
                document.querySelectorAll('.m-tool-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                switch (tool) {
                    case 'select': this.deselectText(); break;
                    case 'find': this.openSheet('m-find-sheet'); break;
                    case 'pages': this.openMobilePagesSheet(); break;
                    case 'more': this.openSheet('m-tools-sheet'); break;
                }
            });
        });

        document.querySelectorAll('.m-sheet-item[data-maction]').forEach(item => {
            item.addEventListener('click', () => {
                this.closeSheet();
                setTimeout(() => {
                    switch (item.dataset.maction) {
                        case 'smart-footer': this.openSheet('m-footer-sheet'); break;
                        case 'page-numbers': this.openSheet('m-pagenum-sheet'); break;
                        case 'insert-image': this.$('m-image-input').click(); break;
                    }
                }, 100);
            });
        });
    }

    /* ========================================
       BOTTOM SHEET MANAGEMENT
       ======================================== */
    openSheet(sheetId) {
        if (this.activeSheet === sheetId) return;
        this.closeSheet();
        this.activeSheet = sheetId;
        this.$('m-sheet-overlay').classList.add('active');
        const sheet = this.$(sheetId);
        requestAnimationFrame(() => sheet.classList.add('open'));
    }

    closeSheet() {
        if (!this.activeSheet) return;
        const sheet = this.$(this.activeSheet);
        if (sheet) sheet.classList.remove('open');
        this.$('m-sheet-overlay').classList.remove('active');
        this.activeSheet = null;
    }

    setupSheetOverlay() {
        this.$('m-sheet-overlay').addEventListener('click', () => this.closeSheet());
    }

    /* ========================================
       MOBILE TEXT EDITING
       ======================================== */
    setupMobileEditSheet() {
        this.$('m-edit-cancel').addEventListener('click', () => {
            this.deselectText();
        });

        this.$('m-edit-apply').addEventListener('click', () => {
            this.applyMobileEdit();
        });

        this.$('m-scope')?.addEventListener?.('change', () => {});
    }

    openMobileEditSheet(block) {
        this.$('m-edit-current').textContent = block.text;
        this.$('m-edit-font').textContent = block.font_name || '—';
        this.$('m-edit-size').value = Math.round(block.font_size);
        this.$('m-edit-color').value = this.rgbToHex(block.color);
        this.$('m-edit-new').value = block.text;
        this.$('m-edit-apply').disabled = false;

        this.openSheet('m-edit-sheet');

        setTimeout(() => {
            const input = this.$('m-edit-new');
            input.focus();
            input.select();
        }, 350);
    }

    async applyMobileEdit() {
        if (!this.selectedBlock) return;

        const newText = this.$('m-edit-new').value;
        const scope = document.querySelector('input[name="m-scope"]:checked')?.value || 'current';
        const fontSize = parseFloat(this.$('m-edit-size').value);
        const color = this.$('m-edit-color').value;

        if (!newText.trim()) {
            this.showToast('Please enter replacement text', 'warning');
            return;
        }

        this.closeSheet();
        this.deselectText();
        this.showLoading('Applying changes...');

        try {
            let endpoint, body;

            if (scope === 'all') {
                endpoint = `/api/pdf/${this.sessionId}/replace-footer-all`;
                body = { search_text: this.selectedBlock?.text || newText, new_text: newText, case_sensitive: false };
            } else {
                endpoint = `/api/pdf/${this.sessionId}/replace-text`;
                body = {
                    page_number: this.currentPage,
                    original_text: this.selectedBlock.text,
                    new_text: newText,
                    bbox: this.selectedBlock.bbox,
                    font_size: fontSize,
                    color: this.hexToRgb(color)
                };
            }

            const response = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to apply changes');
            }

            const result = await response.json();
            this.showToast(result.message || 'Changes applied', 'success');
            this.refreshPage();
        } catch (error) {
            this.showToast(error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    /* ========================================
       MOBILE FIND & REPLACE
       ======================================== */
    setupMobileFindSheet() {
        this.$('m-find-input').addEventListener('input', () => this.mFindAcrossPages());
        this.$('m-find-close').addEventListener('click', () => this.closeSheet());
        this.$('m-replace-toggle').addEventListener('click', () => {
            const sec = this.$('m-replace-section');
            const btn = this.$('m-replace-toggle');
            const isOpen = sec.classList.toggle('open');
            btn.classList.toggle('active', isOpen);
        });
        this.$('m-replace-one').addEventListener('click', () => this.mReplaceSelected());
        this.$('m-replace-all-m').addEventListener('click', () => this.mReplaceAll());
    }

    async mFindAcrossPages() {
        if (!this.sessionId) return;
        const searchText = this.$('m-find-input').value.trim();
        if (!searchText) {
            this.$('m-find-count').textContent = '';
            this.$('m-find-results').textContent = '';
            return;
        }

        try {
            const response = await fetch(`/api/pdf/${this.sessionId}/find-across-pages`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ search_text: searchText, case_sensitive: false })
            });
            if (!response.ok) throw new Error('Search failed');
            const result = await response.json();
            this.mFindResults = result.occurrences;
            this.mFindIndex = result.total_count > 0 ? 0 : -1;
            this.$('m-find-count').textContent = result.total_count > 0
                ? `${this.mFindIndex + 1}/${result.total_count}`
                : 'No matches';

            if (result.total_count > 0 && result.occurrences[0]) {
                this.$('m-find-results').textContent = `Page ${result.occurrences[0].page_number}`;
            } else {
                this.$('m-find-results').textContent = '';
            }
        } catch (error) {
            console.error(error);
        }
    }

    async mReplaceSelected() {
        if (!this.mFindResults.length) return;
        const newText = this.$('m-replace-input').value;
        if (!newText) { this.showToast('Enter replacement text', 'warning'); return; }
        if (this.mFindIndex >= 0 && this.mFindIndex < this.mFindResults.length) {
            const occ = this.mFindResults[this.mFindIndex];
            await this.replaceOccurrences([occ], newText);
            await this.mFindAcrossPages();
        }
    }

    async mReplaceAll() {
        if (!this.mFindResults.length) return;
        const newText = this.$('m-replace-input').value;
        if (!newText) { this.showToast('Enter replacement text', 'warning'); return; }
        await this.replaceOccurrences(this.mFindResults, newText);
        this.$('m-find-count').textContent = '';
        this.$('m-find-results').textContent = '';
    }

    /* ========================================
       MOBILE PAGES SHEET
       ======================================== */
    setupMobilePagesSheet() {}

    openMobilePagesSheet() {
        const grid = this.$('m-pages-grid');
        grid.innerHTML = '';

        for (let i = 1; i <= this.totalPages; i++) {
            const thumb = document.createElement('div');
            thumb.className = 'm-page-thumb' + (i === this.currentPage ? ' current' : '');

            const box = document.createElement('div');
            box.className = 'm-page-thumb-box';

            const img = document.createElement('img');
            img.src = `/api/pdf/${this.sessionId}/page/${i}/thumbnail`;
            img.alt = `Page ${i}`;
            img.loading = 'lazy';

            const num = document.createElement('div');
            num.className = 'm-page-thumb-num';
            num.textContent = i;

            box.appendChild(img);
            thumb.appendChild(box);
            thumb.appendChild(num);

            thumb.addEventListener('click', () => {
                this.loadPage(i);
                this.closeSheet();
            });

            grid.appendChild(thumb);
        }

        this.openSheet('m-pages-sheet');
    }

    /* ========================================
       MOBILE SMART FOOTER
       ======================================== */
    setupMobileFooterSheet() {
        this.$('m-detect-footer').addEventListener('click', () => this.mDetectFooters());
        this.$('m-footer-apply').addEventListener('click', () => this.mApplyFooterReplace());
        this.$('m-footer-cancel').addEventListener('click', () => {
            this.$('m-footer-edit').style.display = 'none';
            this.$('m-footer-results').innerHTML = '';
            this.$('m-detect-footer').style.display = '';
        });
    }

    async mDetectFooters() {
        if (!this.sessionId) return;
        this.showLoading('Detecting footers...');

        try {
            const response = await fetch(`/api/pdf/${this.sessionId}/smart-footer/detect`, {
                method: 'POST'
            });
            if (!response.ok) throw new Error('Detection failed');
            const data = await response.json();
            this.hideLoading();

            const container = this.$('m-footer-results');
            container.innerHTML = '';
            this.$('m-detect-footer').style.display = 'none';

            if (!data.elements || data.elements.length === 0) {
                container.innerHTML = '<p style="color:var(--text-tertiary);font-size:13px;margin-top:12px;">No footers detected.</p>';
                return;
            }

            data.elements.forEach(el => {
                const item = document.createElement('div');
                item.className = 'm-footer-item';
                item.innerHTML = `
                    <div class="m-footer-item-text">${this.esc(el.text)}</div>
                    <div class="m-footer-item-pages">p. ${(el.pages || []).length || '?'}</div>
                `;
                item.addEventListener('click', () => {
                    this.$('m-footer-original').textContent = el.text;
                    this.$('m-footer-new').value = el.text;
                    this.$('m-footer-edit').style.display = '';
                    this._selectedFooterElement = el;
                });
                container.appendChild(item);
            });
        } catch (error) {
            this.hideLoading();
            this.showToast(error.message, 'error');
        }
    }

    async mApplyFooterReplace() {
        if (!this._selectedFooterElement || !this.sessionId) return;
        const newText = this.$('m-footer-new').value;
        if (!newText.trim()) {
            this.showToast('Enter replacement text', 'warning');
            return;
        }

        this.closeSheet();
        this.showLoading('Replacing footer...');

        try {
            const response = await fetch(`/api/pdf/${this.sessionId}/smart-footer/replace`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    element: this._selectedFooterElement,
                    new_text: newText,
                    pages: null
                })
            });
            if (!response.ok) throw new Error('Replace failed');
            const result = await response.json();
            this.showToast(result.message || 'Footer replaced', 'success');
            this.refreshPage();
            this.$('m-footer-edit').style.display = 'none';
            this.$('m-footer-results').innerHTML = '';
            this.$('m-detect-footer').style.display = '';
        } catch (error) {
            this.showToast(error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    /* ========================================
       MOBILE PAGE NUMBERS
       ======================================== */
    setupMobilePageNumbersSheet() {
        this.$('m-pn-apply').addEventListener('click', () => this.mApplyPageNumbers());
        this.$('m-pn-cancel').addEventListener('click', () => this.closeSheet());
    }

    async mApplyPageNumbers() {
        if (!this.sessionId) return;

        const formatStr = this.$('m-pn-format').value;
        const position = this.$('m-pn-position').value;
        const startAt = parseInt(this.$('m-pn-start').value) || 1;

        this.closeSheet();
        this.showLoading('Adding page numbers...');

        try {
            const response = await fetch(`/api/pdf/${this.sessionId}/page-numbers/add`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    format_str: formatStr,
                    position: position,
                    start_at: startAt
                })
            });
            if (!response.ok) throw new Error('Failed to add page numbers');
            const result = await response.json();
            this.showToast(result.message || 'Page numbers added', 'success');
            this.refreshPage();
        } catch (error) {
            this.showToast(error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    /* ========================================
       MOBILE EXPORT
       ======================================== */
    setupMobileExportSheet() {
        this.$('m-export-confirm').addEventListener('click', () => {
            this.closeSheet();
            this.exportPDF();
        });
    }

    /* ========================================
       MOBILE IMAGE PICKER
       ======================================== */
    setupMobileImagePicker() {
        this.$('m-image-input').addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file || !this.sessionId) return;
            e.target.value = '';

            this.showLoading('Inserting image...');

            try {
                const formData = new FormData();
                formData.append('file', file);

                const uploadResp = await fetch(`/api/pdf/${this.sessionId}/image/upload`, {
                    method: 'POST', body: formData
                });
                if (!uploadResp.ok) throw new Error('Image upload failed');
                const uploadData = await uploadResp.json();

                const insertResp = await fetch(`/api/pdf/${this.sessionId}/image/insert`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: new URLSearchParams({
                        image_path: uploadData.image_path,
                        page_number: this.currentPage,
                        x: 100, y: 100,
                        apply_to_all: 'false'
                    })
                });
                if (!insertResp.ok) throw new Error('Image insert failed');
                this.showToast('Image inserted', 'success');
                this.refreshPage();
            } catch (error) {
                this.showToast(error.message, 'error');
            } finally {
                this.hideLoading();
            }
        });
    }

    /* ========================================
       PINCH ZOOM
       ======================================== */
    setupPinchZoom() {
        const container = this.$('viewer-container');
        let initialDistance = 0;
        let initialZoom = 1;
        let lastTap = 0;

        container.addEventListener('touchstart', (e) => {
            if (e.touches.length === 2) {
                e.preventDefault();
                initialDistance = this.getTouchDistance(e.touches);
                initialZoom = this.zoom;
            } else if (e.touches.length === 1) {
                const now = Date.now();
                if (now - lastTap < 300) {
                    e.preventDefault();
                    this.setZoom(this.zoom > 1.0 ? 1.0 : 2.0);
                }
                lastTap = now;
            }
        }, { passive: false });

        container.addEventListener('touchmove', (e) => {
            if (e.touches.length === 2) {
                e.preventDefault();
                const currentDistance = this.getTouchDistance(e.touches);
                const scale = currentDistance / initialDistance;
                this.setZoom(initialZoom * scale);
            }
        }, { passive: false });
    }

    getTouchDistance(touches) {
        const dx = touches[0].clientX - touches[1].clientX;
        const dy = touches[0].clientY - touches[1].clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }
}

const editor = new PDFFooterEditor();
