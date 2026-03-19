// Report viewer page logic

let currentReportPath = '';
let currentHtmlPath = '';
let currentPdfPath = '';
let currentReportMarkdown = '';
let currentImprovedMarkdown = '';
let pendingViewerAction = '';

function setImproveAvailability(enabled) {
    const improveBtn = document.getElementById('improve-report-btn');
    if (improveBtn) {
        improveBtn.disabled = !enabled;
    }
}

async function initReportViewer() {
    UI.initTheme();
    await API.getBots();

    const params = new URLSearchParams(window.location.search);
    currentReportPath = params.get('path') || '';
    currentHtmlPath = params.get('html') || '';
    currentPdfPath = params.get('pdf') || '';
    pendingViewerAction = params.get('action') || '';

    if (!currentReportPath) {
        showError('No report specified. Use ?path=reports/...');
        return;
    }

    // Extract metadata from path: reports/{project}/{bot}/{filename}
    const parts = currentReportPath.replace(/^reports\//, '').split('/');
    if (parts.length === 3 || (parts.length === 4 && parts[0] === 'personal')) {
        const offset = parts[0] === 'personal' ? 1 : 0;
        const project = parts[offset];
        const bot = parts[offset + 1];
        const filename = parts[offset + 2];
        const botInfo = CONFIG.BOTS.find((b) => b.id === bot);
        const botLabel = botInfo ? `${botInfo.icon} ${botInfo.name}` : bot;

        const metaEl = document.getElementById('report-meta');
        if (metaEl) {
            metaEl.innerHTML = `
                <span class="meta-item">📁 ${Utils.escapeHtml(project)}</span>
                <span class="meta-sep">•</span>
                <span class="meta-item">${botLabel}</span>
                <span class="meta-sep">•</span>
                <span class="meta-item">📄 ${Utils.escapeHtml(filename)}</span>
            `;
        }

        document.title = `${project} - ${bot} Report - DevBots Dashboard`;
    }

    initImproveModal();
    renderReportActions(currentReportPath, currentHtmlPath, currentPdfPath);
    await loadReport(currentReportPath);
}

async function loadReport(path) {
    const contentEl = document.getElementById('report-content');
    if (!contentEl) return;

    try {
        const markdown = await API.getReport(path);

        if (!markdown) {
            showError('Report not found or could not be loaded.');
            return;
        }

        currentReportMarkdown = markdown;
        contentEl.innerHTML = renderMarkdown(markdown);
        setImproveAvailability(true);
        if (pendingViewerAction === 'improve') {
            pendingViewerAction = '';
            await openImproveModal();
        }

    } catch (error) {
        console.error('Error loading report:', error);
        showError('Failed to load report.');
        setImproveAvailability(false);
    }
}

function renderMarkdown(markdown) {
    marked.setOptions({
        breaks: true,
        gfm: true,
    });
    return marked.parse(markdown || '');
}

function showError(message) {
    const contentEl = document.getElementById('report-content');
    if (contentEl) {
        UI.showError(contentEl, message);
    }
}

function renderReportActions(reportPath, htmlPath, pdfPath) {
    const actionsEl = document.getElementById('report-actions');
    if (!actionsEl) return;

    const actions = [
        `<button class="btn btn-secondary" id="improve-report-btn" type="button" ${currentReportMarkdown ? '' : 'disabled'}>✨ Improve with ReportBot</button>`,
        `<a class="btn btn-secondary" href="${Utils.escapeHtml(reportPath)}" target="_blank" rel="noopener">Open Markdown</a>`
    ];

    if (htmlPath) {
        actions.push(
            `<a class="btn btn-secondary" href="${Utils.escapeHtml(htmlPath)}" target="_blank" rel="noopener">Open HTML</a>`
        );
    }

    if (pdfPath) {
        actions.push(
            `<a class="btn btn-primary" href="${Utils.escapeHtml(pdfPath)}" target="_blank" rel="noopener">Open PDF</a>`
        );
    } else {
        actions.push(
            `<button class="btn btn-primary" id="export-report-btn" type="button">Export PDF</button>`
        );
    }

    actionsEl.innerHTML = actions.join('');

    const improveBtn = document.getElementById('improve-report-btn');
    if (improveBtn) {
        improveBtn.addEventListener('click', openImproveModal);
    }

    const exportBtn = document.getElementById('export-report-btn');
    if (exportBtn) {
        exportBtn.addEventListener('click', async () => {
            exportBtn.disabled = true;
            exportBtn.textContent = 'Exporting...';
            const result = await API.exportReport(reportPath);
            if (result.error) {
                alert(`Export failed: ${result.error}`);
                exportBtn.disabled = false;
                exportBtn.textContent = 'Export PDF';
                return;
            }

            if (result.data?.errors?.length) {
                alert(`Export completed with warnings:\n${result.data.errors.join('\n')}`);
            }

            const nextHtml = result.data?.artifacts?.html || htmlPath;
            const nextPdf = result.data?.artifacts?.pdf || pdfPath;
            renderReportActions(reportPath, nextHtml, nextPdf);
            if (nextPdf) {
                window.open(nextPdf, '_blank', 'noopener');
            }
        });
    }
}

function initImproveModal() {
    const modal = document.getElementById('report-improve-modal');
    const closeBtn = document.getElementById('report-improve-close');
    const cancelBtn = document.getElementById('report-improve-cancel');
    const saveBtn = document.getElementById('report-improve-save');

    if (!modal || !closeBtn || !cancelBtn || !saveBtn) return;

    closeBtn.addEventListener('click', closeImproveModal);
    cancelBtn.addEventListener('click', closeImproveModal);
    saveBtn.addEventListener('click', saveImprovedReport);
    modal.addEventListener('click', (event) => {
        if (event.target === modal) {
            closeImproveModal();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !modal.classList.contains('hidden')) {
            closeImproveModal();
        }
    });
}

function setImproveError(message = '') {
    const errorEl = document.getElementById('report-improve-error');
    if (!errorEl) return;

    if (message) {
        errorEl.textContent = message;
        errorEl.classList.remove('hidden');
    } else {
        errorEl.textContent = '';
        errorEl.classList.add('hidden');
    }
}

async function openImproveModal() {
    const modal = document.getElementById('report-improve-modal');
    const loadingEl = document.getElementById('report-improve-loading');
    const originalEl = document.getElementById('report-improve-original');
    const previewEl = document.getElementById('report-improve-preview');
    const saveBtn = document.getElementById('report-improve-save');

    if (!modal || !loadingEl || !originalEl || !previewEl || !saveBtn) return;

    currentImprovedMarkdown = '';
    setImproveError('');
    saveBtn.disabled = true;
    saveBtn.textContent = 'Save Improved Report';
    originalEl.innerHTML = renderMarkdown(currentReportMarkdown || '_Empty report._');
    previewEl.innerHTML = '';
    loadingEl.style.display = 'block';
    modal.classList.remove('hidden');

    const result = await API.improveReport(currentReportPath);
    loadingEl.style.display = 'none';

    if (result.error) {
        setImproveError(result.error);
        return;
    }

    currentImprovedMarkdown = result.data?.improved || '';
    previewEl.innerHTML = renderMarkdown(currentImprovedMarkdown || '_No content returned._');
    saveBtn.disabled = !currentImprovedMarkdown.trim();
}

function closeImproveModal() {
    const modal = document.getElementById('report-improve-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
    currentImprovedMarkdown = '';
    setImproveError('');
}

async function saveImprovedReport() {
    const saveBtn = document.getElementById('report-improve-save');
    if (!saveBtn || !currentImprovedMarkdown.trim()) return;

    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
    setImproveError('');

    const result = await API.saveImprovedReport(currentReportPath, currentImprovedMarkdown);
    if (result.error) {
        setImproveError(result.error);
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save Improved Report';
        return;
    }

    const nextPath = result.data?.artifacts?.md;
    if (nextPath) {
        window.location.href = `report.html?path=${encodeURIComponent(nextPath)}`;
        return;
    }

    closeImproveModal();
    window.location.reload();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initReportViewer);
} else {
    initReportViewer();
}
