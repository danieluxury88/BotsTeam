// Report viewer page logic

let currentReportPath = '';
let currentHtmlPath = '';
let currentPdfPath = '';
let currentReportMarkdown = '';
let currentImprovedMarkdown = '';
let currentTranslatedMarkdown = '';
let currentTargetLanguage = 'de';
let pendingViewerAction = '';
let activeReportJob = '';

function setReportbotActionsAvailability(enabled) {
    const improveBtn = document.getElementById('improve-report-btn');
    if (improveBtn) {
        improveBtn.disabled = !enabled || Boolean(activeReportJob);
    }

    const translateBtn = document.getElementById('translate-report-btn');
    if (translateBtn) {
        translateBtn.disabled = !enabled || Boolean(activeReportJob);
    }
}

function setReportJobStatus(message = '', tone = 'active') {
    const statusEl = document.getElementById('report-job-status');
    if (!statusEl) return;

    if (!message) {
        statusEl.textContent = '';
        statusEl.dataset.tone = '';
        statusEl.classList.add('hidden');
        return;
    }

    statusEl.textContent = message;
    statusEl.dataset.tone = tone;
    statusEl.classList.remove('hidden');
}

function setActionButtonState(buttonId, idleLabel, busyLabel, isBusy) {
    const button = document.getElementById(buttonId);
    if (!button) return;
    button.textContent = isBusy ? busyLabel : idleLabel;
    button.disabled = isBusy || !currentReportMarkdown;
}

function setReportJob(jobName, isBusy, message = '', tone = 'active') {
    activeReportJob = isBusy ? jobName : '';
    setReportbotActionsAvailability(Boolean(currentReportMarkdown));
    setActionButtonState('improve-report-btn', '✨ Improve with ReportBot', '⏳ Improving...', isBusy && jobName === 'improve');
    setActionButtonState('translate-report-btn', '🌐 Translate with ReportBot', '⏳ Translating...', isBusy && jobName === 'translate');
    setReportJobStatus(message, tone);
}

function setModalLoadingState(prefix, isBusy, message) {
    const loadingEl = document.getElementById(`${prefix}-loading`);
    const saveBtn = document.getElementById(`${prefix}-save`);
    const cancelBtn = document.getElementById(`${prefix}-cancel`);
    const closeBtn = document.getElementById(`${prefix}-close`);
    const languageSelect = document.getElementById('report-translate-language');

    if (loadingEl) {
        const label = loadingEl.querySelector('span');
        if (label && message) {
            label.textContent = message;
        }
        loadingEl.classList.toggle('hidden', !isBusy);
    }

    if (saveBtn && isBusy) {
        saveBtn.disabled = true;
    }
    if (cancelBtn) {
        cancelBtn.disabled = isBusy;
    }
    if (closeBtn) {
        closeBtn.disabled = isBusy;
    }
    if (prefix === 'report-translate' && languageSelect) {
        languageSelect.disabled = isBusy;
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
    initTranslateModal();
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
        setReportbotActionsAvailability(true);
        if (pendingViewerAction === 'improve') {
            pendingViewerAction = '';
            await openImproveModal();
        }

    } catch (error) {
        console.error('Error loading report:', error);
        showError('Failed to load report.');
        setReportbotActionsAvailability(false);
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
        `<button class="btn btn-secondary" id="translate-report-btn" type="button" ${currentReportMarkdown ? '' : 'disabled'}>🌐 Translate with ReportBot</button>`,
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

    const translateBtn = document.getElementById('translate-report-btn');
    if (translateBtn) {
        translateBtn.addEventListener('click', openTranslateModal);
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
    modal.classList.remove('hidden');
    setModalLoadingState('report-improve', true, '⏳ ReportBot is improving the report...');
    setReportJob('improve', true, 'Improving report draft...');

    const result = await API.improveReport(currentReportPath);
    setModalLoadingState('report-improve', false);
    setReportJob('', false);

    if (result.error) {
        setReportJobStatus(`Improve failed: ${result.error}`, 'error');
        setImproveError(result.error);
        return;
    }

    currentImprovedMarkdown = result.data?.improved || '';
    previewEl.innerHTML = renderMarkdown(currentImprovedMarkdown || '_No content returned._');
    saveBtn.disabled = !currentImprovedMarkdown.trim();
    setReportJobStatus('Improve draft ready.');
}

function closeImproveModal() {
    const modal = document.getElementById('report-improve-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
    currentImprovedMarkdown = '';
    setImproveError('');
    setModalLoadingState('report-improve', false);
    if (activeReportJob === 'improve') {
        setReportJob('', false);
    }
}

function initTranslateModal() {
    const modal = document.getElementById('report-translate-modal');
    const closeBtn = document.getElementById('report-translate-close');
    const cancelBtn = document.getElementById('report-translate-cancel');
    const saveBtn = document.getElementById('report-translate-save');
    const languageSelect = document.getElementById('report-translate-language');

    if (!modal || !closeBtn || !cancelBtn || !saveBtn || !languageSelect) return;

    closeBtn.addEventListener('click', closeTranslateModal);
    cancelBtn.addEventListener('click', closeTranslateModal);
    saveBtn.addEventListener('click', saveTranslatedReport);
    languageSelect.addEventListener('change', async () => {
        currentTargetLanguage = languageSelect.value || 'de';
        if (!modal.classList.contains('hidden')) {
            await loadTranslationPreview();
        }
    });
    modal.addEventListener('click', (event) => {
        if (event.target === modal) {
            closeTranslateModal();
        }
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !modal.classList.contains('hidden')) {
            closeTranslateModal();
        }
    });
}

function setTranslateError(message = '') {
    const errorEl = document.getElementById('report-translate-error');
    if (!errorEl) return;

    if (message) {
        errorEl.textContent = message;
        errorEl.classList.remove('hidden');
    } else {
        errorEl.textContent = '';
        errorEl.classList.add('hidden');
    }
}

async function openTranslateModal() {
    const modal = document.getElementById('report-translate-modal');
    const originalEl = document.getElementById('report-translate-original');
    const languageSelect = document.getElementById('report-translate-language');

    if (!modal || !originalEl || !languageSelect) return;

    currentTranslatedMarkdown = '';
    currentTargetLanguage = languageSelect.value || 'de';
    setTranslateError('');
    originalEl.innerHTML = renderMarkdown(currentReportMarkdown || '_Empty report._');
    modal.classList.remove('hidden');
    await loadTranslationPreview();
}

async function loadTranslationPreview() {
    const loadingEl = document.getElementById('report-translate-loading');
    const previewEl = document.getElementById('report-translate-preview');
    const saveBtn = document.getElementById('report-translate-save');

    if (!loadingEl || !previewEl || !saveBtn) return;

    currentTranslatedMarkdown = '';
    saveBtn.disabled = true;
    saveBtn.textContent = 'Save Translated Report';
    previewEl.innerHTML = '';
    setTranslateError('');
    setModalLoadingState('report-translate', true, '⏳ ReportBot is translating the report...');
    setReportJob('translate', true, `Translating report to ${currentTargetLanguage.toUpperCase()}...`);

    const result = await API.translateReport(currentReportPath, currentTargetLanguage);
    setModalLoadingState('report-translate', false);
    setReportJob('', false);

    if (result.error) {
        setReportJobStatus(`Translation failed: ${result.error}`, 'error');
        setTranslateError(result.error);
        return;
    }

    currentTranslatedMarkdown = result.data?.translated || '';
    currentTargetLanguage = result.data?.target_language || currentTargetLanguage;
    previewEl.innerHTML = renderMarkdown(currentTranslatedMarkdown || '_No content returned._');
    saveBtn.disabled = !currentTranslatedMarkdown.trim();
    setReportJobStatus(`Translation draft ready (${currentTargetLanguage.toUpperCase()}).`);
}

function closeTranslateModal() {
    const modal = document.getElementById('report-translate-modal');
    if (modal) {
        modal.classList.add('hidden');
    }
    currentTranslatedMarkdown = '';
    setTranslateError('');
    setModalLoadingState('report-translate', false);
    if (activeReportJob === 'translate') {
        setReportJob('', false);
    }
}

async function saveImprovedReport() {
    const saveBtn = document.getElementById('report-improve-save');
    if (!saveBtn || !currentImprovedMarkdown.trim()) return;

    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
    setImproveError('');
    setModalLoadingState('report-improve', true, '⏳ Saving improved report...');
    setReportJob('improve', true, 'Saving improved report...');

    const result = await API.saveImprovedReport(currentReportPath, currentImprovedMarkdown);
    if (result.error) {
        setImproveError(result.error);
        setReportJobStatus(`Save failed: ${result.error}`, 'error');
        setModalLoadingState('report-improve', false);
        setReportJob('', false);
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

async function saveTranslatedReport() {
    const saveBtn = document.getElementById('report-translate-save');
    if (!saveBtn || !currentTranslatedMarkdown.trim()) return;

    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
    setTranslateError('');
    setModalLoadingState('report-translate', true, '⏳ Saving translated report and exporting PDF...');
    setReportJob('translate', true, `Saving ${currentTargetLanguage.toUpperCase()} translation and exporting PDF...`);

    const result = await API.saveTranslatedReport(
        currentReportPath,
        currentTranslatedMarkdown,
        currentTargetLanguage,
    );
    if (result.error) {
        setTranslateError(result.error);
        setReportJobStatus(`Save failed: ${result.error}`, 'error');
        setModalLoadingState('report-translate', false);
        setReportJob('', false);
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save Translated Report';
        return;
    }

    const nextPath = result.data?.artifacts?.md;
    const nextHtml = result.data?.artifacts?.html || '';
    const nextPdf = result.data?.artifacts?.pdf || '';
    if (nextPath) {
        const params = new URLSearchParams({ path: nextPath });
        if (nextHtml) params.set('html', nextHtml);
        if (nextPdf) params.set('pdf', nextPdf);
        window.location.href = `report.html?${params.toString()}`;
        return;
    }

    closeTranslateModal();
    window.location.reload();
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initReportViewer);
} else {
    initReportViewer();
}
