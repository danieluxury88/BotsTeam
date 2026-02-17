// Bots page logic

function viewReport(path) {
    window.location.href = `report.html?path=${encodeURIComponent(path)}`;
}

async function initBots() {
    UI.initTheme();

    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => loadBots());
    }

    await loadBots();
}

async function loadBots() {
    const grid = document.getElementById('bots-grid');
    if (!grid) return;

    UI.showLoading(grid);

    try {
        const [reportsData, dashboardData] = await Promise.all([
            API.getReportsIndex(),
            API.getDashboard()
        ]);

        const reports = (reportsData && reportsData.reports) ? reportsData.reports : [];

        const html = CONFIG.BOTS.map(bot => {
            const botReports = reports.filter(r => r.bot === bot.id);
            const lastReport = botReports[0] || null;
            const successCount = botReports.filter(r => r.status === 'success').length;

            return renderBotCard(bot, botReports.length, lastReport, successCount);
        }).join('');

        grid.innerHTML = html;
    } catch (error) {
        console.error('Error loading bots:', error);
        UI.showError(grid, 'Failed to load bot status');
    }
}

function renderBotCard(bot, totalReports, lastReport, successCount) {
    const statusClass = lastReport ? 'status-active' : 'status-idle';
    const statusText = lastReport ? 'Active' : 'No reports';

    return `
        <article class="card bot-card">
            <div class="card-header">
                <h3 class="card-title">${bot.icon} ${Utils.escapeHtml(bot.name)}</h3>
                <span class="card-status ${statusClass}">${statusText}</span>
            </div>
            <div class="card-body">
                <p class="card-description">${Utils.escapeHtml(bot.description)}</p>
                <ul class="card-meta">
                    <li>Total reports: ${totalReports}</li>
                    <li>Successful: ${successCount}</li>
                    <li>Last run: ${Utils.formatDate(lastReport ? lastReport.timestamp : null)}</li>
                </ul>
            </div>
            <div class="card-actions">
                <a href="reports.html?bot=${encodeURIComponent(bot.id)}" class="btn btn-primary">
                    View Reports
                </a>
            </div>
        </article>
    `;
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initBots);
} else {
    initBots();
}
