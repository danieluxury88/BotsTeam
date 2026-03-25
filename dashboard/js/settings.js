// Settings page controller
const Settings = {
    _current: null,
    _modelWasAutoFilled: false,
    _providerModelPresets: {
        anthropic: ['claude-haiku-4-5-20251001', 'claude-sonnet-4-5-20250929'],
        openai: ['gpt-4o-mini', 'gpt-4o', 'gpt-4.1-mini', 'gpt-4.1'],
        gemini: ['gemini-2.0-flash', 'gemini-2.0-flash-lite', 'gemini-1.5-pro'],
    },
    _wrongModelPrefixes: {
        anthropic: ['gpt-', 'o1', 'o3', 'gemini-'],
        openai: ['claude-', 'gemini-'],
        gemini: ['claude-', 'gpt-', 'o1', 'o3'],
    },

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
        const provider = s.provider || 'anthropic';
        document.getElementById('field-provider').value = provider;
        document.getElementById('field-model').value = s.model || '';
        document.getElementById('field-openai-base-url').value = s.openai_base_url || '';
        this._modelWasAutoFilled = false;
        this._providerModelPresets = {
            ...this._providerModelPresets,
            ...(s.provider_model_presets || {}),
        };

        this._updateKeyIndicator('anthropic', s.anthropic_key_set);
        this._updateKeyIndicator('openai', s.openai_key_set);
        this._updateKeyIndicator('gemini', s.gemini_key_set);

        const botModels = s.bot_models || {};
        document.querySelectorAll('[data-bot-model]').forEach(input => {
            input.value = botModels[input.dataset.botModel] || '';
        });

        this._updateProviderHints(provider);
        this._updateModelOptions(provider, s.model || '', s.provider_default_model || '', this._providerModelPresets);
        this._updateModelWarning(provider, s.model || '');
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

    _updateModelOptions(provider, currentModel, providerDefaultModel, providerModelPresets) {
        const presetSelect = document.getElementById('field-model-preset');
        const datalist = document.getElementById('field-model-suggestions');
        const help = document.getElementById('field-model-help');
        if (!presetSelect || !datalist || !help) return;

        const presets = providerModelPresets[provider] || [];
        const resolvedDefaultModel = providerDefaultModel || presets[0] || '';

        presetSelect.innerHTML = '<option value="">Choose a suggested model…</option>';
        datalist.innerHTML = '';
        presets.forEach(model => {
            const option = document.createElement('option');
            option.value = model;
            option.textContent = model;
            presetSelect.appendChild(option);

            const suggestion = document.createElement('option');
            suggestion.value = model;
            datalist.appendChild(suggestion);
        });

        presetSelect.value = presets.includes(currentModel) ? currentModel : '';
        help.textContent = resolvedDefaultModel
            ? `Default for ${provider} is ${resolvedDefaultModel}. Leave the field blank to use that default.`
            : 'Pick a provider-specific model or type a custom one.';
    },

    _getModelWarning(provider, model) {
        const normalizedProvider = (provider || '').trim().toLowerCase();
        const normalizedModel = (model || '').trim().toLowerCase();
        if (!normalizedProvider || !normalizedModel) return '';

        const wrongPrefixes = this._wrongModelPrefixes[normalizedProvider] || [];
        const isMismatch = wrongPrefixes.some(prefix => normalizedModel.startsWith(prefix));
        if (!isMismatch) return '';

        return `Model "${model}" does not look valid for provider "${provider}". Choose a ${provider}-compatible model before saving.`;
    },

    _updateModelWarning(provider, model) {
        const warningEl = document.getElementById('field-model-warning');
        if (!warningEl) return;

        const message = this._getModelWarning(provider, model);
        warningEl.textContent = message;
        warningEl.hidden = !message;
    },

    _maybeSwitchModelForProvider(nextProvider) {
        const providerField = document.getElementById('field-provider');
        const modelField = document.getElementById('field-model');
        if (!providerField || !modelField || !this._current) return;

        const previousProvider = this._current.provider || 'anthropic';
        const previousDefault = this._current.provider_default_model || '';
        const currentValue = modelField.value.trim();
        const nextDefault = (this._providerModelPresets[nextProvider] || [])[0] || '';
        const shouldReplace = !currentValue || currentValue === previousDefault || this._modelWasAutoFilled;

        this._updateProviderHints(nextProvider);
        this._updateModelOptions(
            nextProvider,
            shouldReplace ? nextDefault : currentValue,
            nextDefault,
            this._providerModelPresets,
        );

        if (shouldReplace && nextDefault) {
            modelField.value = nextDefault;
            this._modelWasAutoFilled = true;
        }

        providerField.value = nextProvider;
        this._updateModelWarning(nextProvider, modelField.value.trim());
    },

    _bindEvents() {
        document.getElementById('field-provider').addEventListener('change', e => {
            this._maybeSwitchModelForProvider(e.target.value);
        });

        document.getElementById('field-model').addEventListener('input', () => {
            this._modelWasAutoFilled = false;
            const provider = document.getElementById('field-provider').value;
            const presetSelect = document.getElementById('field-model-preset');
            const modelValue = document.getElementById('field-model').value.trim();
            if (presetSelect) {
                const matchesPreset = Array.from(presetSelect.options).some(option => option.value === modelValue);
                presetSelect.value = matchesPreset ? modelValue : '';
            }
            this._updateModelWarning(provider, modelValue);
        });

        document.getElementById('field-model-preset').addEventListener('change', e => {
            const selectedModel = e.target.value.trim();
            if (!selectedModel) return;
            document.getElementById('field-model').value = selectedModel;
            this._modelWasAutoFilled = false;
            this._updateModelWarning(document.getElementById('field-provider').value, selectedModel);
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
        this._populate(result.data);
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
