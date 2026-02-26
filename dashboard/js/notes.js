// Notes page — view, create, edit, and delete markdown notes per project
'use strict';

(function () {
    // ── State ─────────────────────────────────────────────────────────────────
    let currentProject = null;
    let currentFilename = null;
    let notes = [];
    let improvedContent = null;
    let isDirty = false;

    // ── DOM refs ──────────────────────────────────────────────────────────────
    const projectSelect  = document.getElementById('project-select');
    const btnNewNote     = document.getElementById('btn-new-note');
    const btnAnalyse     = document.getElementById('btn-analyse');
    const notesList      = document.getElementById('notes-list');
    const notesCount     = document.getElementById('notes-count');
    const notesEmptyState = document.getElementById('notes-empty-state');
    const notesFilename  = document.getElementById('notes-filename');
    const unsavedDot     = document.getElementById('unsaved-dot');
    const btnSave        = document.getElementById('btn-save');
    const btnImprove     = document.getElementById('btn-improve');
    const editor         = document.getElementById('notes-editor');
    const preview        = document.getElementById('notes-preview');

    // New note modal
    const newNoteModal   = document.getElementById('new-note-modal');
    const newNoteName    = document.getElementById('new-note-name');
    const newNoteError   = document.getElementById('new-note-error');
    const newNoteConfirm = document.getElementById('new-note-confirm');
    const newNoteCancel  = document.getElementById('new-note-cancel');
    const newNoteClose   = document.getElementById('new-note-close');

    // Improve modal
    const improveModal   = document.getElementById('improve-modal');
    const improveOriginal = document.getElementById('improve-original');
    const improvePreview  = document.getElementById('improve-preview');
    const improveLoading  = document.getElementById('improve-loading');
    const improveAccept   = document.getElementById('improve-accept');
    const improveCancel   = document.getElementById('improve-cancel');
    const improveClose    = document.getElementById('improve-close');

    // ── Markdown helpers ──────────────────────────────────────────────────────
    function renderMarkdown(md) {
        if (!md || !md.trim()) return '<p class="notes-preview-empty">Nothing to preview yet.</p>';
        if (typeof marked === 'undefined') return `<pre>${Utils.escapeHtml(md)}</pre>`;
        marked.setOptions({ breaks: true, gfm: true });
        return marked.parse(md);
    }

    function updatePreview() {
        preview.innerHTML = renderMarkdown(editor.value);
    }

    // ── Dirty state ───────────────────────────────────────────────────────────
    function setDirty(val) {
        isDirty = val;
        unsavedDot.classList.toggle('hidden', !val);
        btnSave.disabled = !val;
    }

    // ── Project population ────────────────────────────────────────────────────
    async function loadProjects() {
        const data = await API.getProjects();
        const projects = (data && data.projects) ? data.projects : [];
        projectSelect.innerHTML = '<option value="">Select a project…</option>';
        projects.forEach(p => {
            const opt = document.createElement('option');
            opt.value = p.name;
            opt.textContent = `${p.scope === 'personal' ? '👤' : '👥'} ${p.name}`;
            projectSelect.appendChild(opt);
        });

        // Restore last selection from localStorage
        const saved = localStorage.getItem('notes-project');
        if (saved && projects.find(p => p.name === saved)) {
            projectSelect.value = saved;
            await selectProject(saved);
        }
    }

    async function selectProject(projectName) {
        if (!projectName) {
            currentProject = null;
            currentFilename = null;
            notes = [];
            renderNoteList([]);
            clearEditor();
            btnNewNote.disabled = true;
            btnAnalyse.disabled = true;
            return;
        }
        currentProject = projectName;
        btnNewNote.disabled = false;
        btnAnalyse.disabled = false;
        localStorage.setItem('notes-project', projectName);
        await loadNotes();
    }

    // ── Notes list ────────────────────────────────────────────────────────────
    async function loadNotes() {
        if (!currentProject) return;
        const data = await API.listNotes(currentProject);
        notes = (data && data.notes) ? data.notes : [];
        renderNoteList(notes);

        // Re-select current note if still present
        if (currentFilename && notes.find(n => n.filename === currentFilename)) {
            highlightNote(currentFilename);
        } else if (notes.length > 0 && !currentFilename) {
            // Auto-select first note
            await selectNote(notes[0].filename);
        }
    }

    function renderNoteList(noteItems) {
        notesList.innerHTML = '';
        notesCount.textContent = noteItems.length ? `${noteItems.length} note${noteItems.length === 1 ? '' : 's'}` : '';

        if (noteItems.length === 0) {
            const li = document.createElement('li');
            li.className = 'notes-list-empty';
            li.id = 'notes-empty-state';
            li.textContent = currentProject ? 'No notes yet. Click "+ New Note" to create one.' : 'Select a project to view notes.';
            notesList.appendChild(li);
            return;
        }

        noteItems.forEach(note => {
            const li = document.createElement('li');
            li.className = 'note-item';
            li.dataset.filename = note.filename;
            if (note.filename === currentFilename) li.classList.add('active');

            const modDate = note.modified ? new Date(note.modified * 1000).toLocaleDateString() : '';

            li.innerHTML = `
                <span class="note-item-icon">📄</span>
                <div class="note-item-info">
                    <div class="note-item-name" title="${Utils.escapeHtml(note.filename)}">${Utils.escapeHtml(note.filename)}</div>
                    <div class="note-item-date">${modDate}</div>
                </div>
                <button class="note-item-delete" data-filename="${Utils.escapeHtml(note.filename)}" title="Delete note" aria-label="Delete ${Utils.escapeHtml(note.filename)}">🗑</button>
            `;

            li.addEventListener('click', async (e) => {
                if (e.target.classList.contains('note-item-delete')) return;
                if (isDirty && !confirmDiscard()) return;
                await selectNote(note.filename);
            });

            li.querySelector('.note-item-delete').addEventListener('click', async (e) => {
                e.stopPropagation();
                await deleteNote(note.filename);
            });

            notesList.appendChild(li);
        });
    }

    function highlightNote(filename) {
        notesList.querySelectorAll('.note-item').forEach(li => {
            li.classList.toggle('active', li.dataset.filename === filename);
        });
    }

    // ── Select / edit a note ──────────────────────────────────────────────────
    async function selectNote(filename) {
        if (!currentProject) return;
        const data = await API.getNote(currentProject, filename);
        if (!data) {
            UI.showError('Failed to load note.');
            return;
        }
        currentFilename = filename;
        highlightNote(filename);

        editor.value = data.content || '';
        editor.disabled = false;
        updatePreview();
        setDirty(false);

        notesFilename.textContent = filename;
        notesFilename.classList.remove('placeholder');
        btnSave.disabled = true;
        btnImprove.disabled = false;
    }

    function clearEditor() {
        currentFilename = null;
        editor.value = '';
        editor.disabled = true;
        preview.innerHTML = '<p class="notes-preview-empty">Preview will appear here as you type.</p>';
        notesFilename.textContent = 'No note selected';
        notesFilename.classList.add('placeholder');
        btnSave.disabled = true;
        btnImprove.disabled = true;
        setDirty(false);
    }

    function confirmDiscard() {
        return window.confirm('You have unsaved changes. Discard them?');
    }

    // ── Save ──────────────────────────────────────────────────────────────────
    async function saveNote() {
        if (!currentProject || !currentFilename) return;
        btnSave.disabled = true;
        btnSave.textContent = 'Saving…';
        const result = await API.updateNote(currentProject, currentFilename, editor.value);
        btnSave.textContent = 'Save';
        if (result.error) {
            UI.showError(`Save failed: ${result.error}`);
            btnSave.disabled = false;
            return;
        }
        setDirty(false);
        await loadNotes(); // refresh sidebar dates
    }

    // ── Create note ───────────────────────────────────────────────────────────
    function openNewNoteModal() {
        newNoteName.value = '';
        newNoteError.style.display = 'none';
        newNoteModal.classList.remove('hidden');
        newNoteName.focus();
    }

    function closeNewNoteModal() {
        newNoteModal.classList.add('hidden');
    }

    async function confirmCreateNote() {
        const name = newNoteName.value.trim();
        if (!name) {
            newNoteError.textContent = 'Please enter a filename.';
            newNoteError.style.display = 'block';
            return;
        }
        newNoteConfirm.disabled = true;
        newNoteConfirm.textContent = 'Creating…';
        const result = await API.createNote(currentProject, name, '');
        newNoteConfirm.disabled = false;
        newNoteConfirm.textContent = 'Create';
        if (result.error) {
            newNoteError.textContent = result.error;
            newNoteError.style.display = 'block';
            return;
        }
        closeNewNoteModal();
        await loadNotes();
        await selectNote(result.data.filename);
    }

    // ── Delete note ───────────────────────────────────────────────────────────
    async function deleteNote(filename) {
        if (!window.confirm(`Delete "${filename}"? This cannot be undone.`)) return;
        const result = await API.deleteNote(currentProject, filename);
        if (result.error) {
            UI.showError(`Delete failed: ${result.error}`);
            return;
        }
        if (currentFilename === filename) {
            clearEditor();
            currentFilename = null;
        }
        await loadNotes();
    }

    // ── Improve with AI ───────────────────────────────────────────────────────
    async function openImproveModal() {
        if (!currentProject || !currentFilename) return;

        improvedContent = null;
        improveAccept.disabled = true;
        improveOriginal.textContent = editor.value || '(empty)';
        improvePreview.innerHTML = '';
        improveLoading.style.display = 'block';
        improveModal.classList.remove('hidden');

        const result = await API.improveNote(currentProject, currentFilename);
        improveLoading.style.display = 'none';

        if (result.error) {
            improvePreview.innerHTML = `<span style="color:var(--color-error)">${Utils.escapeHtml(result.error)}</span>`;
            return;
        }

        improvedContent = result.data.improved;
        improvePreview.innerHTML = renderMarkdown(improvedContent);
        improveAccept.disabled = false;
    }

    function closeImproveModal() {
        improveModal.classList.add('hidden');
        improvedContent = null;
    }

    function acceptImprovement() {
        if (!improvedContent) return;
        editor.value = improvedContent;
        updatePreview();
        setDirty(true);
        closeImproveModal();
    }

    // ── Analyse notes ─────────────────────────────────────────────────────────
    async function analyseNotes() {
        if (!currentProject) return;
        btnAnalyse.disabled = true;
        btnAnalyse.textContent = '🤖 Running…';
        const result = await API._mutate(
            `${CONFIG.API.PROJECTS_API}/${encodeURIComponent(currentProject)}/reports`,
            'POST',
            { bots: ['notebot'] }
        );
        btnAnalyse.disabled = false;
        btnAnalyse.textContent = '🤖 Analyse Notes';
        if (result.error) {
            UI.showError(`Analysis failed: ${result.error}`);
            return;
        }
        const botResult = result.data && result.data.results && result.data.results.notebot;
        if (botResult && botResult.status === 'success') {
            alert(`✅ NoteBot analysis complete!\n\n${botResult.summary}\n\nView the full report in the Reports page.`);
        } else if (botResult) {
            alert(`⚠️ NoteBot finished with status "${botResult.status}":\n${botResult.summary}`);
        }
    }

    // ── Event listeners ───────────────────────────────────────────────────────
    projectSelect.addEventListener('change', () => selectProject(projectSelect.value));

    editor.addEventListener('input', () => {
        updatePreview();
        if (!isDirty) setDirty(true);
    });

    // Ctrl+S / Cmd+S to save
    editor.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            e.preventDefault();
            if (!btnSave.disabled) saveNote();
        }
    });

    btnSave.addEventListener('click', saveNote);
    btnImprove.addEventListener('click', openImproveModal);
    btnNewNote.addEventListener('click', openNewNoteModal);
    btnAnalyse.addEventListener('click', analyseNotes);

    newNoteConfirm.addEventListener('click', confirmCreateNote);
    newNoteCancel.addEventListener('click', closeNewNoteModal);
    newNoteClose.addEventListener('click', closeNewNoteModal);
    newNoteName.addEventListener('keydown', (e) => { if (e.key === 'Enter') confirmCreateNote(); });

    // Close new-note modal on overlay click
    newNoteModal.addEventListener('click', (e) => { if (e.target === newNoteModal) closeNewNoteModal(); });

    improveAccept.addEventListener('click', acceptImprovement);
    improveCancel.addEventListener('click', closeImproveModal);
    improveClose.addEventListener('click', closeImproveModal);
    improveModal.addEventListener('click', (e) => { if (e.target === improveModal) closeImproveModal(); });

    document.getElementById('refresh-btn').addEventListener('click', async () => {
        if (currentProject) await loadNotes();
    });

    // Warn on page leave if unsaved
    window.addEventListener('beforeunload', (e) => {
        if (isDirty) {
            e.preventDefault();
            e.returnValue = '';
        }
    });

    // ── Theme toggle ──────────────────────────────────────────────────────────
    const themeToggle = document.getElementById('theme-toggle');
    if (themeToggle && typeof UI !== 'undefined') {
        UI.initTheme();
        themeToggle.addEventListener('click', () => UI.toggleTheme());
    }

    // ── Init ──────────────────────────────────────────────────────────────────
    async function init() {
        await loadProjects();
    }

    init();
})();
