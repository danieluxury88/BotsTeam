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

    function init() {
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
            examples: Array.from(document.querySelectorAll('[data-voice-example]')),
        };

        if (!elements.section) {
            return;
        }

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
        });

        elements.startBtn?.addEventListener('click', startListening);
        elements.stopBtn?.addEventListener('click', stopListening);
        elements.submitBtn?.addEventListener('click', submitTranscript);
        elements.clearBtn?.addEventListener('click', clearTranscript);
        elements.transcriptInput?.addEventListener('input', syncActionButtons);

        elements.examples.forEach((button) => {
            button.addEventListener('click', () => {
                elements.transcriptInput.value = button.dataset.voiceExample || '';
                elements.transcriptInput.focus();
                syncActionButtons();
            });
        });
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
            elements.startBtn.disabled = listening || !recognitionSupported;
        }
        if (elements.stopBtn) {
            elements.stopBtn.disabled = !listening;
        }
        if (elements.submitBtn) {
            elements.submitBtn.disabled = !hasTranscript;
        }
        if (elements.clearBtn) {
            elements.clearBtn.disabled = !hasTranscript && !listening;
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
        elements.transcriptInput.value = '';
        updateIdleState();
        renderResult({
            kind: 'idle',
            message: recognitionSupported
                ? 'Transcript cleared. Start listening again or type a command manually.'
                : 'Transcript cleared. Enter a command manually to test the routing flow.',
        });
    }

    async function submitTranscript() {
        const transcript = elements.transcriptInput.value.trim();
        if (!transcript) {
            setStatus('Enter or record a command first.', 'warning');
            return;
        }

        setStatus('Routing command through the orchestrator...', 'live');
        renderLoadingResult('Dispatching the transcript to the dashboard API...');

        const result = await API.executeVoiceCommand({
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
            return;
        }

        setStatus('Command processed. Review the routed result below.', 'ready');
        renderResult(result.data || { kind: 'error', error: 'Empty response from server.' });
    }

    function renderLoadingResult(message) {
        if (!elements.result) {
            return;
        }
        elements.result.innerHTML = `
            <div class="voice-result-card voice-result-card-loading">
                <div class="voice-result-kicker">Voice Router</div>
                <p class="voice-result-message">${Utils.escapeHtml(message)}</p>
            </div>
        `;
    }

    function renderResult(payload) {
        if (!elements.result) {
            return;
        }

        const transcript = payload.transcript
            ? `<div class="voice-result-transcript"><span class="voice-label">Transcript</span><p>${Utils.escapeHtml(payload.transcript)}</p></div>`
            : '';

        if (payload.kind === 'idle') {
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

            const reportPreview = payload.result.markdown_report
                ? `<pre class="voice-report-preview">${Utils.escapeHtml(payload.result.markdown_report)}</pre>`
                : '';

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

        elements.result.innerHTML = `
            <div class="voice-result-card voice-result-card-error">
                <div class="voice-result-kicker">Routing Issue</div>
                ${transcript}
                <p class="voice-result-message">${Utils.escapeHtml(payload.error || 'The command could not be completed.')}</p>
                ${payload.explanation ? `<p class="voice-result-explanation">${Utils.escapeHtml(payload.explanation)}</p>` : ''}
            </div>
        `;
    }

    return { init };
})();

window.VoiceCommand = VoiceCommand;
