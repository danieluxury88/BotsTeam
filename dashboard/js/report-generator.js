// Report generation modal — select bots, configure options, run, and display results
const ReportGenerator = {
    _projectName: null,

    openModal(projectName) {
        try {
            this._projectName = projectName;
            const project = allProjects.find(p => p.id === projectName);
            if (!project) {
                alert(`Project "${projectName}" not found. Try refreshing the page.`);
                return;
            }

            const modal = document.getElementById('report-modal');
            if (!modal) {
                alert('Report modal not found in page. Please refresh.');
                return;
            }

            document.getElementById('report-modal-title').textContent = `Generate Reports: ${project.name}`;

            // Reset form
            const form = document.getElementById('report-form');
            if (form) form.reset();
            document.getElementById('rg-gitbot').checked = true;
            document.getElementById('report-error').textContent = '';

            // Enable/disable pmbot based on integration
            const pmbotCheckbox = document.getElementById('rg-pmbot');
            const pmbotHint = document.getElementById('rg-pmbot-hint');
            const hasPmIntegration = project.gitlab_id || project.github_repo;
            pmbotCheckbox.disabled = !hasPmIntegration;
            pmbotCheckbox.checked = false;
            pmbotHint.textContent = hasPmIntegration
                ? (project.gitlab_id ? `GitLab #${project.gitlab_id}` : `GitHub: ${project.github_repo}`)
                : 'No GitLab/GitHub integration configured';

            // Show form, hide progress/results
            document.getElementById('rg-form-section').hidden = false;
            document.getElementById('rg-progress-section').hidden = true;
            document.getElementById('rg-results-section').hidden = true;

            modal.hidden = false;
        } catch (err) {
            console.error('ReportGenerator.openModal error:', err);
            alert('Failed to open report generator: ' + err.message);
        }
    },

    closeModal() {
        const modal = document.getElementById('report-modal');
        if (modal) modal.hidden = true;
        this._projectName = null;
    },

    async handleSubmit(event) {
        event.preventDefault();
        const errorEl = document.getElementById('report-error');
        errorEl.textContent = '';

        // Collect selected bots
        const bots = [];
        if (document.getElementById('rg-gitbot').checked) bots.push('gitbot');
        if (document.getElementById('rg-qabot').checked) bots.push('qabot');
        if (document.getElementById('rg-pmbot').checked) bots.push('pmbot');

        if (bots.length === 0) {
            errorEl.textContent = 'Select at least one bot.';
            return;
        }

        const options = { bots };

        const since = document.getElementById('rg-since').value.trim();
        const until = document.getElementById('rg-until').value.trim();
        if (since) options.since = since;
        if (until) options.until = until;

        if (bots.includes('pmbot')) {
            options.pmbot_mode = document.getElementById('rg-pmbot-mode').value;
        }

        // Disable submit button and show progress
        const submitBtn = event.target.querySelector('button[type="submit"]');
        if (submitBtn) submitBtn.disabled = true;

        this._showProgress(bots);

        try {
            const result = await API.generateReports(this._projectName, options);

            if (result.error) {
                this._showError(result.error);
                return;
            }

            this._showResults(result.data);
        } catch (err) {
            console.error('ReportGenerator.handleSubmit error:', err);
            this._showError(err.message || 'Unexpected error');
        } finally {
            if (submitBtn) submitBtn.disabled = false;
        }
    },

    _showProgress(bots) {
        document.getElementById('rg-form-section').hidden = true;
        document.getElementById('rg-progress-section').hidden = false;
        document.getElementById('rg-results-section').hidden = true;

        const botNames = bots.map(b => {
            const info = CONFIG.BOTS.find(x => x.id === b);
            return info ? info.name : b;
        });
        document.getElementById('rg-progress-message').textContent =
            `Running ${botNames.join(', ')}... This may take a minute.`;
    },

    _showResults(data) {
        document.getElementById('rg-progress-section').hidden = true;
        document.getElementById('rg-results-section').hidden = false;

        const container = document.getElementById('rg-results-list');
        const entries = Object.entries(data.results || {});

        if (entries.length === 0) {
            container.innerHTML = '<p>No results returned.</p>';
            document.getElementById('rg-results-summary').textContent = '';
            return;
        }

        container.innerHTML = entries.map(([bot, info]) => {
            const isError = info.status === 'error' || info.status === 'failed';
            const statusClass = isError ? 'bot-result-error' : 'bot-result-success';
            const icon = isError ? '&#10060;' : '&#9989;';
            const botInfo = CONFIG.BOTS.find(b => b.id === bot);
            const botName = botInfo ? botInfo.name : bot;
            return `
                <div class="bot-result ${statusClass}">
                    <span class="bot-result-icon">${icon}</span>
                    <div class="bot-result-body">
                        <strong>${Utils.escapeHtml(botName)}</strong>
                        <p>${Utils.escapeHtml(info.summary || '')}</p>
                    </div>
                </div>
            `;
        }).join('');

        document.getElementById('rg-results-summary').textContent =
            `${data.completed} succeeded, ${data.failed} failed`;
    },

    _showError(msg) {
        document.getElementById('rg-progress-section').hidden = true;
        document.getElementById('rg-results-section').hidden = false;

        const container = document.getElementById('rg-results-list');
        container.innerHTML = `
            <div class="bot-result bot-result-error">
                <span class="bot-result-icon">&#10060;</span>
                <div class="bot-result-body">
                    <strong>Error</strong>
                    <p>${Utils.escapeHtml(msg)}</p>
                </div>
            </div>
        `;
        document.getElementById('rg-results-summary').textContent = '';
    },

    backToForm() {
        document.getElementById('rg-form-section').hidden = false;
        document.getElementById('rg-progress-section').hidden = true;
        document.getElementById('rg-results-section').hidden = true;
    }
};

// Close report modal on Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        const modal = document.getElementById('report-modal');
        if (modal && !modal.hidden) {
            ReportGenerator.closeModal();
        }
    }
});

// Close report modal on backdrop click
document.addEventListener('click', (e) => {
    if (e.target.id === 'report-modal') {
        ReportGenerator.closeModal();
    }
});

window.ReportGenerator = ReportGenerator;
