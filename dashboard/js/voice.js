// Dashboard voice command module
const VoiceCommand = (() => {
    const LANGUAGE_OPTIONS = {
        auto: {
            label: 'Auto',
            speechLocale: navigator.language || 'es-CO',
            hint: 'Uses your browser locale for recognition. Spanish is recommended for best results.',
        },
        'es-CO': {
            label: 'Español (CO)',
            speechLocale: 'es-CO',
            hint: 'Best option for Spanish-first commands in Latin American pronunciation.',
        },
        'es-ES': {
            label: 'Español (ES)',
            speechLocale: 'es-ES',
            hint: 'Spanish recognition tuned closer to Spain pronunciation.',
        },
        'en-US': {
            label: 'English (US)',
            speechLocale: 'en-US',
            hint: 'Use this if you plan to speak commands in English.',
        },
    };

    const EXAMPLES = [
        'Quiero revisar mis tareas',
        'Analiza mi journal',
        'Get gitbot report for demo',
    ];

    let elements = {};
    let recognition = null;
    let recognitionSupported = false;
    let listening = false;
    let lastSpeechText = '';
    let processing = false;
    let processingTimer = null;
    let processingStartedAt = 0;
    let currentJobId = '';
    let currentPollTimer = null;

    async function init() {
        elements = {
            section: document.getElementById('voice-command-module'),
            startBtn: document.getElementById('voice-start-btn'),
            stopBtn: document.getElementById('voice-stop-btn'),
            submitBtn: document.getElementById('voice-submit-btn'),
            clearBtn: document.getElementById('voice-clear-btn'),
            transcriptInput: document.getElementById('voice-transcript-input'),
            languageSelect: document.getElementById('voice-language-select'),
            status: document.getElementById('voice-status'),
            helper: document.getElementById('voice-language-hint'),
            result: document.getElementById('voice-result'),
            outputProvider: document.getElementById('voice-output-provider'),
            outputVoice: document.getElementById('voice-output-voice'),
            outputRate: document.getElementById('voice-output-rate'),
            outputAutoplay: document.getElementById('voice-output-autoplay'),
            examples: Array.from(document.querySelectorAll('[data-voice-example]')),
        };

        if (!elements.section) {
            return;
        }

        await initSpeechOutput();
        recognitionSupported = Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
        if (recognitionSupported) {
            createRecognition();
        }

        bindEvents();
        updateLanguageHint();
        updateIdleState();
        renderResult({
            kind: 'idle',
            message: recognitionSupported
                ? 'Tap Start Listening and speak a command. You can also type or edit the transcript before sending it.'
                : 'Your browser does not expose Web Speech recognition here. Type a command manually and send it to the orchestrator.',
        });
    }

    function bindEvents() {
        elements.languageSelect?.addEventListener('change', () => {
            updateLanguageHint();
            if (recognition) {
                recognition.lang = getSpeechLocale();
            }
            refreshVoiceChoices();
        });

        elements.startBtn?.addEventListener('click', startListening);
        elements.stopBtn?.addEventListener('click', stopListening);
        elements.submitBtn?.addEventListener('click', submitTranscript);
        elements.clearBtn?.addEventListener('click', clearTranscript);
        elements.transcriptInput?.addEventListener('input', syncActionButtons);
        elements.outputProvider?.addEventListener('change', onProviderChange);
        elements.outputVoice?.addEventListener('change', onVoiceChange);
        elements.outputRate?.addEventListener('change', onRateChange);
        elements.outputAutoplay?.addEventListener('change', onAutoplayChange);
        elements.result?.addEventListener('click', handleResultActions);

        elements.examples.forEach((button) => {
            button.addEventListener('click', () => {
                elements.transcriptInput.value = button.dataset.voiceExample || '';
                elements.transcriptInput.focus();
                syncActionButtons();
            });
        });
    }

    async function initSpeechOutput() {
        if (!window.VoiceOutputService) {
            return;
        }

        const state = await window.VoiceOutputService.init();
        window.VoiceOutputService.subscribe((nextState) => {
            syncVoiceOutputControls(nextState);
            if (nextState.event === 'speech-start') {
                setStatus('Reading the routed reply aloud...', 'live');
            } else if (nextState.event === 'speech-stop') {
                setStatus('Voice playback stopped.', 'ready');
            } else if (nextState.event === 'speech-error') {
                setStatus(nextState.error || 'Voice playback failed.', 'error');
            } else if (nextState.event === 'speech-end' && !listening) {
                setStatus('Reply playback finished.', 'ready');
            }
        });
        syncVoiceOutputControls(state);
    }

    function createRecognition() {
        const RecognitionCtor = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new RecognitionCtor();
        recognition.lang = getSpeechLocale();
        recognition.interimResults = true;
        recognition.continuous = false;
        recognition.maxAlternatives = 1;

        recognition.addEventListener('start', () => {
            listening = true;
            setStatus('Listening for your command...', 'live');
            elements.section?.setAttribute('data-voice-state', 'listening');
            syncActionButtons();
        });

        recognition.addEventListener('result', (event) => {
            let finalTranscript = '';
            let interimTranscript = '';

            for (let index = event.resultIndex; index < event.results.length; index += 1) {
                const result = event.results[index];
                const transcript = result[0]?.transcript || '';
                if (result.isFinal) {
                    finalTranscript += transcript;
                } else {
                    interimTranscript += transcript;
                }
            }

            const currentValue = finalTranscript || interimTranscript;
            if (currentValue) {
                elements.transcriptInput.value = currentValue.trim();
                syncActionButtons();
            }

            if (interimTranscript) {
                setStatus('Capturing speech…', 'live');
            }
        });

        recognition.addEventListener('error', (event) => {
            listening = false;
            elements.section?.setAttribute('data-voice-state', 'error');

            const messages = {
                'not-allowed': 'Microphone permission was denied by the browser.',
                'service-not-allowed': 'Microphone access is blocked for this page.',
                'audio-capture': 'No microphone was detected. You can still type the command manually.',
                'no-speech': 'No speech was detected. Try again in a quieter room or type the command.',
                'network': 'Speech recognition failed due to a network issue.',
                'aborted': 'Listening stopped.',
            };

            setStatus(messages[event.error] || `Speech recognition error: ${event.error}`, 'error');
            syncActionButtons();
        });

        recognition.addEventListener('end', () => {
            listening = false;
            elements.section?.setAttribute('data-voice-state', 'ready');
            if (elements.transcriptInput.value.trim()) {
                setStatus('Transcript ready. Review it and send when you want.', 'ready');
            } else {
                updateIdleState();
            }
            syncActionButtons();
        });
    }

    function getSpeechLocale() {
        const selected = elements.languageSelect?.value || 'auto';
        return (LANGUAGE_OPTIONS[selected] || LANGUAGE_OPTIONS.auto).speechLocale;
    }

    function getSelectedLanguage() {
        return elements.languageSelect?.value || 'auto';
    }

    function updateLanguageHint() {
        const selected = getSelectedLanguage();
        const option = LANGUAGE_OPTIONS[selected] || LANGUAGE_OPTIONS.auto;
        if (elements.helper) {
            elements.helper.textContent = option.hint;
        }
    }

    function setStatus(message, tone = 'idle') {
        if (!elements.status) {
            return;
        }
        elements.status.textContent = message;
        elements.status.dataset.tone = tone;
    }

    function updateIdleState() {
        const locale = getSelectedLanguage() === 'auto' ? getSpeechLocale() : getSelectedLanguage();
        if (recognitionSupported) {
            setStatus(`Ready for voice input. Current recognition locale: ${locale}.`, 'idle');
        } else {
            setStatus('Voice recognition is unavailable here. Use the transcript box as a manual fallback.', 'warning');
        }
        syncActionButtons();
    }

    function syncActionButtons() {
        const hasTranscript = Boolean(elements.transcriptInput?.value.trim());
        if (elements.startBtn) {
            elements.startBtn.disabled = listening || processing || !recognitionSupported;
        }
        if (elements.stopBtn) {
            elements.stopBtn.disabled = !listening || processing;
        }
        if (elements.submitBtn) {
            elements.submitBtn.disabled = !hasTranscript || processing;
        }
        if (elements.clearBtn) {
            elements.clearBtn.disabled = processing || (!hasTranscript && !listening);
        }
        if (elements.languageSelect) {
            elements.languageSelect.disabled = processing;
        }
        if (elements.outputProvider) {
            elements.outputProvider.disabled = processing || elements.outputProvider.options.length <= 1;
        }
        if (elements.outputVoice) {
            elements.outputVoice.disabled = processing || elements.outputVoice.options.length <= 1;
        }
        if (elements.outputRate) {
            elements.outputRate.disabled = processing;
        }
        if (elements.outputAutoplay) {
            elements.outputAutoplay.disabled = processing;
        }
    }

    function startListening() {
        if (!recognitionSupported || !recognition || listening) {
            return;
        }

        recognition.lang = getSpeechLocale();
        elements.transcriptInput.value = '';
        renderLoadingResult('Listening for a spoken command...');

        try {
            recognition.start();
        } catch (error) {
            setStatus(`Could not start listening: ${error.message}`, 'error');
        }
    }

    function stopListening() {
        if (recognition && listening) {
            recognition.stop();
        }
    }

    function clearTranscript() {
        if (listening) {
            stopListening();
        }
        stopPolling();
        elements.transcriptInput.value = '';
        updateIdleState();
        renderResult({
            kind: 'idle',
            message: recognitionSupported
                ? 'Transcript cleared. Start listening again or type a command manually.'
                : 'Transcript cleared. Enter a command manually to test the routing flow.',
        });
        lastSpeechText = '';
    }

    async function submitTranscript() {
        const transcript = elements.transcriptInput.value.trim();
        if (!transcript) {
            setStatus('Enter or record a command first.', 'warning');
            return;
        }

        stopPolling();
        startProcessingState();
        setStatus('Routing command through the orchestrator. This can take a while if a bot needs AI processing.', 'live');
        renderLoadingResult(
            'Processing your command...',
            'Waiting for the orchestrator and selected bot to finish. Keep this tab open.'
        );

        try {
            const result = await API.startVoiceCommandJob({
                transcript,
                locale: getSpeechLocale(),
                source: 'dashboard-web-speech',
            });

            if (result.error) {
                setStatus(`Voice command failed: ${result.error}`, 'error');
                renderResult({
                    kind: 'error',
                    error: result.error,
                    transcript,
                });
                stopProcessingState();
                return;
            }

            const jobId = result.data?.job_id;
            if (!jobId) {
                setStatus('Voice command failed: no job ID was returned by the server.', 'error');
                renderResult({
                    kind: 'error',
                    error: 'The server accepted the command but did not return a job ID.',
                    transcript,
                });
                stopProcessingState();
                return;
            }

            currentJobId = jobId;
            setStatus('Voice command accepted. Waiting for the orchestrator result...', 'live');
            await pollVoiceCommandJob(jobId, transcript);
        } catch (error) {
            setStatus(`Voice command failed: ${error.message || error}`, 'error');
            renderResult({
                kind: 'error',
                error: error.message || String(error),
                transcript,
            });
            stopProcessingState();
        }
    }

    function renderLoadingResult(message, detail = '') {
        if (!elements.result) {
            return;
        }
        elements.result.innerHTML = `
            <div class="voice-result-card voice-result-card-loading">
                <div class="voice-result-kicker">Voice Router</div>
                <div class="voice-processing-indicator" aria-hidden="true">
                    <span class="voice-processing-dot"></span>
                    <span class="voice-processing-dot"></span>
                    <span class="voice-processing-dot"></span>
                </div>
                <p class="voice-result-message">${Utils.escapeHtml(message)}</p>
                ${detail ? `<p class="voice-result-explanation">${Utils.escapeHtml(detail)}</p>` : ''}
                <p class="voice-processing-elapsed" id="voice-processing-elapsed">Elapsed: 0s</p>
            </div>
        `;
    }

    function startProcessingState() {
        processing = true;
        processingStartedAt = Date.now();
        elements.section?.setAttribute('data-voice-state', 'processing');
        syncActionButtons();
        if (processingTimer) {
            window.clearInterval(processingTimer);
        }
        processingTimer = window.setInterval(updateProcessingElapsed, 1000);
        updateProcessingElapsed();
    }

    function stopProcessingState() {
        processing = false;
        elements.section?.setAttribute('data-voice-state', listening ? 'listening' : 'ready');
        if (processingTimer) {
            window.clearInterval(processingTimer);
            processingTimer = null;
        }
        syncActionButtons();
    }

    function stopPolling() {
        currentJobId = '';
        if (currentPollTimer) {
            window.clearTimeout(currentPollTimer);
            currentPollTimer = null;
        }
    }

    function updateProcessingElapsed() {
        const elapsedNode = document.getElementById('voice-processing-elapsed');
        if (!elapsedNode || !processingStartedAt) {
            return;
        }
        const seconds = Math.max(0, Math.round((Date.now() - processingStartedAt) / 1000));
        let suffix = 'Working on AI routing and bot execution.';
        if (seconds >= 30) {
            suffix = 'Still processing. Long-running bot requests can take over a minute.';
        }
        if (seconds >= 60) {
            suffix = 'This is taking longer than usual. The request is still active unless it times out.';
        }
        elapsedNode.textContent = `Elapsed: ${seconds}s. ${suffix}`;
    }

    async function pollVoiceCommandJob(jobId, transcript) {
        const pollInterval = CONFIG.UI.VOICE_COMMAND_POLL_INTERVAL_MS || 2000;

        while (currentJobId === jobId) {
            const result = await API.getVoiceCommandJob(jobId);
            if (result.error) {
                setStatus(`Voice command failed: ${result.error}`, 'error');
                renderResult({
                    kind: 'error',
                    error: result.error,
                    transcript,
                });
                stopPolling();
                stopProcessingState();
                return;
            }

            const job = result.data || {};
            const stageMessage = job.message || 'Processing voice command...';

            if (job.status === 'queued' || job.status === 'running') {
                setStatus(stageMessage, 'live');
                renderLoadingResult(
                    'Processing your command...',
                    stageMessage,
                );
                await waitForNextPoll(pollInterval);
                continue;
            }

            stopPolling();
            stopProcessingState();

            if (job.status === 'completed' && job.result) {
                setStatus('Command processed. Review the routed result below.', 'ready');
                const payload = job.result;
                renderResult(payload);

                if (payload.kind === 'bot_result' && payload.result) {
                    lastSpeechText = buildReplySpeech(payload);
                    if (elements.outputAutoplay?.checked) {
                        playReply(lastSpeechText);
                    }
                } else {
                    lastSpeechText = '';
                }
                return;
            }

            setStatus(`Voice command failed: ${job.error || 'Unknown error.'}`, 'error');
            renderResult({
                kind: 'error',
                error: job.error || job.result?.error || 'The background voice command failed.',
                transcript,
                explanation: job.result?.explanation,
            });
            return;
        }
    }

    function waitForNextPoll(delayMs) {
        return new Promise((resolve) => {
            currentPollTimer = window.setTimeout(() => {
                currentPollTimer = null;
                resolve();
            }, delayMs);
        });
    }

    function renderResult(payload) {
        if (!elements.result) {
            return;
        }

        const transcript = payload.transcript
            ? `<div class="voice-result-transcript"><span class="voice-label">Transcript</span><p>${Utils.escapeHtml(payload.transcript)}</p></div>`
            : '';

        if (payload.kind === 'idle') {
            lastSpeechText = '';
            elements.result.innerHTML = `
                <div class="voice-result-card">
                    <div class="voice-result-kicker">Voice Router</div>
                    <p class="voice-result-message">${Utils.escapeHtml(payload.message || '')}</p>
                    <div class="voice-example-row">
                        ${EXAMPLES.map((example) => `<button class="voice-example-pill" type="button" data-voice-example="${Utils.escapeHtml(example)}">${Utils.escapeHtml(example)}</button>`).join('')}
                    </div>
                </div>
            `;
            elements.examples = Array.from(elements.result.querySelectorAll('[data-voice-example]'));
            elements.examples.forEach((button) => {
                button.addEventListener('click', () => {
                    elements.transcriptInput.value = button.dataset.voiceExample || '';
                    syncActionButtons();
                });
            });
            return;
        }

        if (payload.kind === 'project_list') {
            lastSpeechText = '';
            const projects = (payload.projects || []).map((project) => `
                <li class="voice-project-item">
                    <strong>${Utils.escapeHtml(project.name)}</strong>
                    <span>${Utils.escapeHtml(project.scope || 'team')}</span>
                </li>
            `).join('');

            elements.result.innerHTML = `
                <div class="voice-result-card">
                    <div class="voice-result-kicker">Project Match</div>
                    ${transcript}
                    <p class="voice-result-message">${Utils.escapeHtml(payload.explanation || `Found ${payload.count || 0} project(s).`)}</p>
                    <ul class="voice-project-list">${projects}</ul>
                </div>
            `;
            return;
        }

        if (payload.kind === 'bot_result' && payload.result) {
            const status = payload.result.status || 'unknown';
            const artifacts = payload.result.artifacts || {};
            const actions = [];

            if (artifacts.md) {
                actions.push(`
                    <button class="btn btn-secondary" type="button"
                        onclick="viewReportWithFormats('${Utils.escapeHtml(artifacts.md)}', '${Utils.escapeHtml(artifacts.html || '')}', '${Utils.escapeHtml(artifacts.pdf || '')}')">
                        Open Report
                    </button>
                `);
            }

            if (artifacts.pdf) {
                actions.push(`
                    <a class="btn btn-primary" href="${Utils.escapeHtml(artifacts.pdf)}" target="_blank" rel="noopener">
                        Open PDF
                    </a>
                `);
            }

            actions.unshift(`
                <button class="btn btn-success" type="button" data-voice-action="play-reply">
                    Play Reply
                </button>
            `);
            actions.unshift(`
                <button class="btn btn-secondary" type="button" data-voice-action="stop-reply">
                    Stop Voice
                </button>
            `);

            const reportPreview = payload.result.markdown_report
                ? `<pre class="voice-report-preview">${Utils.escapeHtml(payload.result.markdown_report)}</pre>`
                : '';

            lastSpeechText = buildReplySpeech(payload);
            elements.result.innerHTML = `
                <div class="voice-result-card">
                    <div class="voice-result-header">
                        <div>
                            <div class="voice-result-kicker">Routed Bot Result</div>
                            <h3 class="voice-result-title">${Utils.escapeHtml(payload.result.bot_name || 'bot')} for ${Utils.escapeHtml(payload.result.project_name || 'project')}</h3>
                        </div>
                        <span class="voice-status-badge status-${Utils.escapeHtml(status)}">${Utils.escapeHtml(status)}</span>
                    </div>
                    ${transcript}
                    <p class="voice-result-message">${Utils.escapeHtml(payload.result.summary || '')}</p>
                    ${payload.explanation ? `<p class="voice-result-explanation">${Utils.escapeHtml(payload.explanation)}</p>` : ''}
                    ${actions.length ? `<div class="voice-result-actions">${actions.join('')}</div>` : ''}
                    ${reportPreview}
                </div>
            `;
            return;
        }

        lastSpeechText = '';
        elements.result.innerHTML = `
            <div class="voice-result-card voice-result-card-error">
                <div class="voice-result-kicker">Routing Issue</div>
                ${transcript}
                <p class="voice-result-message">${Utils.escapeHtml(payload.error || 'The command could not be completed.')}</p>
                ${payload.explanation ? `<p class="voice-result-explanation">${Utils.escapeHtml(payload.explanation)}</p>` : ''}
            </div>
        `;
    }

    function handleResultActions(event) {
        const action = event.target.closest('[data-voice-action]');
        if (!action) {
            return;
        }

        if (action.dataset.voiceAction === 'play-reply') {
            playReply(lastSpeechText);
        } else if (action.dataset.voiceAction === 'stop-reply') {
            window.VoiceOutputService?.stop();
        }
    }

    async function playReply(text) {
        const reply = (text || '').trim();
        if (!reply) {
            setStatus('There is no routed reply available to read aloud yet.', 'warning');
            return;
        }

        const result = await window.VoiceOutputService?.speak(reply, {
            locale: getSpeechLocale(),
        });
        if (result && result.ok === false) {
            setStatus(result.error || 'Voice playback failed.', 'error');
        }
    }

    async function onProviderChange() {
        if (!window.VoiceOutputService || !elements.outputProvider) {
            return;
        }
        await window.VoiceOutputService.setProvider(elements.outputProvider.value);
        await refreshVoiceChoices();
    }

    function onVoiceChange() {
        if (!window.VoiceOutputService || !elements.outputVoice) {
            return;
        }
        window.VoiceOutputService.updateSettings({ voiceURI: elements.outputVoice.value });
    }

    function onRateChange() {
        if (!window.VoiceOutputService || !elements.outputRate) {
            return;
        }
        window.VoiceOutputService.updateSettings({ rate: Number(elements.outputRate.value) });
    }

    function onAutoplayChange() {
        if (!window.VoiceOutputService || !elements.outputAutoplay) {
            return;
        }
        window.VoiceOutputService.updateSettings({ autoPlayReplies: elements.outputAutoplay.checked });
    }

    async function refreshVoiceChoices() {
        if (!window.VoiceOutputService) {
            return;
        }
        await window.VoiceOutputService.refreshVoices();
    }

    function syncVoiceOutputControls(state) {
        if (!elements.outputProvider || !elements.outputVoice || !elements.outputRate || !elements.outputAutoplay) {
            return;
        }

        const providers = state.providers || [];
        const providerOptions = providers.map((provider) => `
            <option value="${Utils.escapeHtml(provider.id)}" ${provider.supported ? '' : 'disabled'}>
                ${Utils.escapeHtml(provider.label)}${provider.supported ? '' : ' (Unavailable)'}
            </option>
        `).join('');
        elements.outputProvider.innerHTML = providerOptions;
        elements.outputProvider.value = state.settings.provider || CONFIG.VOICE_OUTPUT.DEFAULT_PROVIDER;
        elements.outputProvider.disabled = providers.length <= 1;

        const locale = getSpeechLocale();
        const voices = rankVisibleVoices(state.voices || [], locale);
        const voiceOptions = ['<option value="">Auto-select best natural voice</option>']
            .concat(voices.map((voice) => `
                <option value="${Utils.escapeHtml(voice.voiceURI)}">${Utils.escapeHtml(voice.name)} (${Utils.escapeHtml(voice.lang)})</option>
            `))
            .join('');
        elements.outputVoice.innerHTML = voiceOptions;
        elements.outputVoice.value = state.settings.voiceURI || '';
        elements.outputVoice.disabled = !voices.length;

        elements.outputRate.value = String(state.settings.rate ?? CONFIG.VOICE_OUTPUT.DEFAULT_RATE);
        elements.outputAutoplay.checked = Boolean(state.settings.autoPlayReplies);
    }

    function rankVisibleVoices(voices, locale) {
        const base = (locale || 'es').split('-')[0].toLowerCase();
        return [...voices]
            .filter((voice) => {
                const lang = (voice.lang || '').toLowerCase();
                return lang.startsWith(base) || lang.startsWith('en');
            })
            .sort((left, right) => scoreVoice(right, locale, base) - scoreVoice(left, locale, base));
    }

    function scoreVoice(voice, locale, base) {
        const lang = (voice.lang || '').toLowerCase();
        const name = (voice.name || '').toLowerCase();
        let score = 0;

        if (lang === locale.toLowerCase()) {
            score += 100;
        }
        if (lang.startsWith(base)) {
            score += 60;
        }
        if (voice.default) {
            score += 10;
        }
        (CONFIG.VOICE_OUTPUT.NATURAL_VOICE_HINTS || []).forEach((hint, index) => {
            if (name.includes(hint)) {
                score += 25 - index;
            }
        });
        return score;
    }

    function buildReplySpeech(payload) {
        const parts = [];
        const result = payload.result || {};
        const locale = getSpeechLocale();

        if (result.bot_name && result.project_name) {
            if (locale.toLowerCase().startsWith('es')) {
                parts.push(`Aqui esta la respuesta de ${result.bot_name} para ${result.project_name}.`);
            } else {
                parts.push(`Here is the ${result.bot_name} reply for ${result.project_name}.`);
            }
        }
        if (result.summary) {
            parts.push(result.summary);
        }
        if (payload.explanation) {
            parts.push(payload.explanation);
        }

        const cleanedReport = stripMarkdown(result.markdown_report || '');
        if (cleanedReport) {
            parts.push(cleanedReport);
        }

        return parts
            .join(' ')
            .replace(/\s+/g, ' ')
            .trim()
            .slice(0, CONFIG.VOICE_OUTPUT.MAX_REPLY_CHARS);
    }

    function stripMarkdown(markdown) {
        const cleaned = markdown
            .replace(/```[\s\S]*?```/g, ' ')
            .replace(/`([^`]+)`/g, '$1')
            .replace(/^#{1,6}\s+/gm, '')
            .replace(/\*\*([^*]+)\*\*/g, '$1')
            .replace(/\*([^*]+)\*/g, '$1')
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '$1')
            .replace(/^\s*[-*+]\s+/gm, '')
            .replace(/^\s*\d+\.\s+/gm, '')
            .replace(/\|/g, ' ')
            .replace(/\n+/g, ' ')
            .trim();

        return cleaned.slice(0, Math.min(cleaned.length, CONFIG.VOICE_OUTPUT.MAX_REPLY_CHARS));
    }

    return { init };
})();

window.VoiceCommand = VoiceCommand;
