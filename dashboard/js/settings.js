// Settings page controller
const Settings = {
    _current: null,

    async init() {
        this._current = await API.getSettings();
        if (!this._current) {
            this._showError('Could not load settings from server.');
            return;
        }
        this._populate(this._current);
        this._bindEvents();
    },

    _populate(s) {
        document.getElementById('field-provider').value = s.provider || 'anthropic';
        document.getElementById('field-model').value = s.model || '';
        document.getElementById('field-openai-base-url').value = s.openai_base_url || '';

        this._updateKeyIndicator('anthropic', s.anthropic_key_set);
        this._updateKeyIndicator('openai', s.openai_key_set);
        this._updateKeyIndicator('gemini', s.gemini_key_set);

        const botModels = s.bot_models || {};
        document.querySelectorAll('[data-bot-model]').forEach(input => {
            input.value = botModels[input.dataset.botModel] || '';
        });

        this._updateProviderHints(s.provider || 'anthropic');
    },

    _updateKeyIndicator(provider, isSet) {
        const indicator = document.getElementById(`key-indicator-${provider}`);
        if (!indicator) return;
        if (isSet) {
            indicator.textContent = '✓ Key set';
            indicator.className = 'key-indicator key-indicator--set';
        } else {
            indicator.textContent = 'Not set';
            indicator.className = 'key-indicator key-indicator--unset';
        }
    },

    _updateProviderHints(provider) {
        document.querySelectorAll('[data-provider-hint]').forEach(el => {
            el.hidden = el.dataset.providerHint !== provider;
        });
    },

    _bindEvents() {
        document.getElementById('field-provider').addEventListener('change', e => {
            this._updateProviderHints(e.target.value);
        });

        document.querySelectorAll('.key-toggle').forEach(btn => {
            btn.addEventListener('click', () => {
                const input = document.getElementById(btn.dataset.target);
                if (!input) return;
                const isPassword = input.type === 'password';
                input.type = isPassword ? 'text' : 'password';
                btn.textContent = isPassword ? '🙈' : '👁';
            });
        });

        document.getElementById('settings-form').addEventListener('submit', async e => {
            e.preventDefault();
            await this._save();
        });
    },

    async _save() {
        const btn = document.getElementById('save-btn');
        const errorEl = document.getElementById('form-error');
        const successEl = document.getElementById('form-success');

        errorEl.hidden = true;
        successEl.hidden = true;
        btn.disabled = true;
        btn.textContent = 'Saving…';

        const botModels = {};
        document.querySelectorAll('[data-bot-model]').forEach(input => {
            botModels[input.dataset.botModel] = input.value.trim();
        });

        const body = {
            provider:        document.getElementById('field-provider').value,
            model:           document.getElementById('field-model').value.trim(),
            openai_base_url: document.getElementById('field-openai-base-url').value.trim(),
            bot_models:      botModels,
        };

        // Only include API keys if the user typed something (empty = don't overwrite)
        const anthropicKey = document.getElementById('field-anthropic-key').value.trim();
        const openaiKey    = document.getElementById('field-openai-key').value.trim();
        const geminiKey    = document.getElementById('field-gemini-key').value.trim();
        if (anthropicKey) body.anthropic_key = anthropicKey;
        if (openaiKey)    body.openai_key    = openaiKey;
        if (geminiKey)    body.gemini_key    = geminiKey;

        const result = await API.updateSettings(body);

        btn.disabled = false;
        btn.textContent = 'Save Settings';

        if (result.error) {
            errorEl.textContent = result.error;
            errorEl.hidden = false;
            return;
        }

        // Clear key fields after a successful save and refresh indicators
        document.getElementById('field-anthropic-key').value = '';
        document.getElementById('field-openai-key').value = '';
        document.getElementById('field-gemini-key').value = '';

        this._current = result.data;
        this._updateKeyIndicator('anthropic', result.data.anthropic_key_set);
        this._updateKeyIndicator('openai',    result.data.openai_key_set);
        this._updateKeyIndicator('gemini',    result.data.gemini_key_set);

        successEl.hidden = false;
        setTimeout(() => { successEl.hidden = true; }, 4000);
    },

    _showError(msg) {
        const el = document.getElementById('form-error');
        el.textContent = msg;
        el.hidden = false;
    },
};

document.addEventListener('DOMContentLoaded', async () => {
    if (typeof renderHeaderNavigation === 'function') renderHeaderNavigation();
    if (typeof UI !== 'undefined' && typeof UI.initTheme === 'function') UI.initTheme();
    await Settings.init();
});
