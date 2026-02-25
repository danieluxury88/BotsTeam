// Report generation modal — select bots, configure options, run, and display results
const ReportGenerator = {
    _projectName: null,

    // Build the bot checkbox list from CONFIG.BOTS for the given project scope.
    _renderBotList(project) {
        const isPersonal = project.scope === 'personal';
        const scopeBots = CONFIG.BOTS.filter(b =>
            b.scope === (isPersonal ? 'personal' : 'team') || b.scope === 'both'
        );

        if (scopeBots.length === 0) {
            return '<p class="form-hint">No bots available for this project type.</p>';
        }

        const legend = isPersonal ? '👤 Personal Bots' : '👥 Team Bots';
        const items = scopeBots.map(bot => {
            const cbId = `rg-bot-${bot.id}`;
            let enabled = true;
            let hint = '';
            let checked = true;

            if (isPersonal && bot.requires_field) {
                const value = project[bot.requires_field];
                enabled = !!value;
                checked = !!value;
                hint = value ? value : `No ${bot.requires_field} configured`;
            } else if (bot.id === 'pmbot') {
                const hasPmIntegration = project.gitlab_id || project.github_repo;
                enabled = !!hasPmIntegration;
                checked = false;
                hint = hasPmIntegration
                    ? (project.gitlab_id ? `GitLab #${project.gitlab_id}` : `GitHub: ${project.github_repo}`)
                    : 'No GitLab/GitHub integration configured';
            }

            return `
                <label class="checkbox-label">
                    <input type="checkbox" id="${cbId}"
                        ${checked ? 'checked' : ''}
                        ${enabled ? '' : 'disabled'}>
                    ${Utils.escapeHtml(bot.icon)} ${Utils.escapeHtml(bot.name)} — ${Utils.escapeHtml(bot.description)}
                    ${hint ? `<span class="form-hint">${Utils.escapeHtml(hint)}</span>` : ''}
                </label>`;
        }).join('');

        return `
            <fieldset class="form-fieldset">
                <legend>${legend}</legend>
                <div class="checkbox-group">${items}</div>
            </fieldset>`;
    },

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

            // Reset form and render bot checkboxes from registry
            const form = document.getElementById('report-form');
            if (form) form.reset();
            document.getElementById('report-error').textContent = '';

            const botList = document.getElementById('rg-bot-list');
            if (botList) botList.innerHTML = this._renderBotList(project);

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

        // Collect all checked bot checkboxes dynamically
        const bots = CONFIG.BOTS
            .filter(b => {
                const cb = document.getElementById(`rg-bot-${b.id}`);
                return cb && cb.checked;
            })
            .map(b => b.id);

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
            return info ? `${info.icon} ${info.name}` : b;
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
            const botName = botInfo ? `${botInfo.icon} ${botInfo.name}` : bot;
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
