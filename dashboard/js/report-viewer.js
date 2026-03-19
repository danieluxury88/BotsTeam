// Report viewer page logic

async function initReportViewer() {
    UI.initTheme();

    const params = new URLSearchParams(window.location.search);
    const reportPath = params.get('path');
    const htmlPath = params.get('html');
    const pdfPath = params.get('pdf');

    if (!reportPath) {
        showError('No report specified. Use ?path=reports/...');
        return;
    }

    // Extract metadata from path: reports/{project}/{bot}/{filename}
    const parts = reportPath.replace(/^reports\//, '').split('/');
    if (parts.length === 3) {
        const [project, bot, filename] = parts;
        const botInfo = CONFIG.BOTS.find(b => b.id === bot);
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

    renderReportActions(reportPath, htmlPath, pdfPath);
    await loadReport(reportPath);
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

        // Configure marked for safe rendering
        marked.setOptions({
            breaks: true,
            gfm: true,
        });

        // Render markdown to HTML
        contentEl.innerHTML = marked.parse(markdown);

    } catch (error) {
        console.error('Error loading report:', error);
        showError('Failed to load report.');
    }
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

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initReportViewer);
} else {
    initReportViewer();
}
