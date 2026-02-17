// Activity page logic

function viewReport(path) {
    window.open(path, '_blank');
}

async function initActivity() {
    UI.initTheme();

    const refreshBtn = document.getElementById('refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => loadActivity());
    }

    await loadActivity();
}

async function loadActivity() {
    const list = document.getElementById('activity-list');
    if (!list) return;

    UI.showLoading(list);

    try {
        const data = await API.getReportsIndex();

        if (!data || !data.reports || data.reports.length === 0) {
            UI.showEmpty(list, 'No activity yet. Run bots to generate reports.');
            return;
        }

        // Reports are already sorted by timestamp (most recent first) from generate_data.py
        const html = data.reports.map(report =>
            Components.renderReportItem(report)
        ).join('');

        list.innerHTML = html;
    } catch (error) {
        console.error('Error loading activity:', error);
        UI.showError(list, 'Failed to load activity feed');
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initActivity);
} else {
    initActivity();
}
