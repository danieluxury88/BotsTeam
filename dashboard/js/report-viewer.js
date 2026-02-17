// Report viewer page logic

async function initReportViewer() {
    UI.initTheme();

    const params = new URLSearchParams(window.location.search);
    const reportPath = params.get('path');

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

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initReportViewer);
} else {
    initReportViewer();
}
