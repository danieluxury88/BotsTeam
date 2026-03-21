// Replaceable dashboard speech output service
const VoiceOutputService = (() => {
    const providers = new Map();
    const listeners = new Set();

    let settings = null;
    let activeProvider = null;
    let initialized = false;
    let speaking = false;

    function registerProvider(id, provider) {
        providers.set(id, provider);
    }

    function subscribe(listener) {
        listeners.add(listener);
        listener(getState());
        return () => listeners.delete(listener);
    }

    function notify(event = {}) {
        const payload = { ...getState(), ...event };
        listeners.forEach((listener) => listener(payload));
    }

    function loadSettings() {
        const raw = localStorage.getItem(CONFIG.STORAGE.VOICE_OUTPUT);
        const defaults = {
            provider: CONFIG.VOICE_OUTPUT.DEFAULT_PROVIDER,
            voiceURI: '',
            rate: CONFIG.VOICE_OUTPUT.DEFAULT_RATE,
            autoPlayReplies: CONFIG.VOICE_OUTPUT.AUTO_PLAY_REPLIES,
        };

        if (!raw) {
            return defaults;
        }

        try {
            return { ...defaults, ...JSON.parse(raw) };
        } catch (error) {
            console.warn('Could not parse voice output settings:', error);
            return defaults;
        }
    }

    function saveSettings() {
        localStorage.setItem(CONFIG.STORAGE.VOICE_OUTPUT, JSON.stringify(settings));
    }

    async function init() {
        if (initialized) {
            return getState();
        }

        settings = loadSettings();
        registerBuiltInProviders();
        activeProvider = providers.get(settings.provider) || providers.get(CONFIG.VOICE_OUTPUT.DEFAULT_PROVIDER) || null;

        if (activeProvider?.init) {
            await activeProvider.init();
        }

        initialized = true;
        notify();
        return getState();
    }

    function registerBuiltInProviders() {
        if (providers.has('browser')) {
            return;
        }
        registerProvider('browser', createBrowserSpeechProvider());
    }

    function getState() {
        const provider = activeProvider || providers.get(settings?.provider || CONFIG.VOICE_OUTPUT.DEFAULT_PROVIDER) || null;
        return {
            initialized,
            supported: Boolean(provider?.isSupported?.()),
            speaking,
            settings: { ...(settings || {}) },
            providers: Array.from(providers.entries()).map(([id, item]) => ({
                id,
                label: item.label || id,
                supported: Boolean(item.isSupported?.()),
            })),
            voices: provider?.listVoices?.() || [],
        };
    }

    async function setProvider(id) {
        if (!providers.has(id)) {
            return;
        }

        if (speaking) {
            stop();
        }

        settings.provider = id;
        activeProvider = providers.get(id);
        if (activeProvider?.init) {
            await activeProvider.init();
        }
        saveSettings();
        notify();
    }

    async function updateSettings(partial) {
        const nextProvider = partial.provider;
        if (nextProvider && nextProvider !== settings.provider) {
            const remaining = { ...partial };
            delete remaining.provider;
            await setProvider(nextProvider);
            settings = { ...settings, ...remaining };
            saveSettings();
            notify();
            return;
        }
        settings = { ...settings, ...partial };
        saveSettings();
        notify();
    }

    async function refreshVoices() {
        if (activeProvider?.refreshVoices) {
            await activeProvider.refreshVoices();
            notify();
        }
    }

    async function speak(text, options = {}) {
        if (!text || !text.trim()) {
            return { ok: false, error: 'Nothing to read.' };
        }

        if (!activeProvider) {
            return { ok: false, error: 'No speech provider configured.' };
        }

        if (!activeProvider.isSupported()) {
            return { ok: false, error: `${activeProvider.label || 'Speech output'} is not supported in this browser.` };
        }

        if (speaking) {
            stop();
        }

        speaking = true;
        notify({ event: 'speech-start' });

        try {
            const result = await activeProvider.speak(text, {
                ...options,
                voiceURI: options.voiceURI ?? settings.voiceURI,
                rate: options.rate ?? settings.rate,
            });
            return result;
        } catch (error) {
            notify({ event: 'speech-error', error: error.message || String(error) });
            return { ok: false, error: error.message || String(error) };
        } finally {
            speaking = false;
            notify({ event: 'speech-end' });
        }
    }

    function stop() {
        if (activeProvider?.stop) {
            activeProvider.stop();
        }
        speaking = false;
        notify({ event: 'speech-stop' });
    }

    function createBrowserSpeechProvider() {
        let voiceEntries = [];
        let voicesLoaded = false;
        let voiceLoadPromise = null;
        let currentUtterance = null;

        async function initProvider() {
            await loadVoices();
        }

        async function refresh() {
            voicesLoaded = false;
            voiceEntries = [];
            voiceLoadPromise = null;
            await loadVoices();
        }

        function isSupported() {
            return Boolean(window.speechSynthesis && window.SpeechSynthesisUtterance);
        }

        function listVoices() {
            return voiceEntries.map((entry) => entry.meta);
        }

        function stopProvider() {
            currentUtterance = null;
            window.speechSynthesis?.cancel();
        }

        async function speakWithBrowser(text, options) {
            await loadVoices();

            const utterance = new SpeechSynthesisUtterance(text);
            const locale = options.locale || navigator.language || 'es-CO';
            const voice = selectVoice(locale, options.voiceURI);

            utterance.lang = voice?.lang || locale;
            utterance.voice = voice || null;
            utterance.rate = clampRate(options.rate);
            utterance.pitch = 1;
            currentUtterance = utterance;

            return new Promise((resolve, reject) => {
                utterance.addEventListener('end', () => {
                    currentUtterance = null;
                    resolve({
                        ok: true,
                        provider: 'browser',
                        voiceURI: voice?.voiceURI || '',
                        voiceName: voice?.name || '',
                    });
                });
                utterance.addEventListener('error', (event) => {
                    currentUtterance = null;
                    reject(new Error(event.error || 'Speech playback failed.'));
                });

                window.speechSynthesis.cancel();
                window.speechSynthesis.speak(utterance);
            });
        }

        function selectVoice(locale, requestedVoiceURI = '') {
            if (!voiceEntries.length) {
                return null;
            }

            if (requestedVoiceURI) {
                const exact = voiceEntries.find((entry) => entry.meta.voiceURI === requestedVoiceURI);
                if (exact) {
                    return exact.voice;
                }
            }

            const targetBase = locale.split('-')[0].toLowerCase();
            const ranked = [...voiceEntries].sort(
                (left, right) => rankVoice(right.meta, locale, targetBase) - rankVoice(left.meta, locale, targetBase)
            );
            return ranked[0]?.voice || null;
        }

        function rankVoice(voice, locale, targetBase) {
            const lang = (voice.lang || '').toLowerCase();
            const name = (voice.name || '').toLowerCase();
            let score = 0;

            if (lang === locale.toLowerCase()) {
                score += 120;
            }
            if (lang.startsWith(targetBase)) {
                score += 80;
            }
            if (voice.default) {
                score += 15;
            }

            const naturalHints = CONFIG.VOICE_OUTPUT.NATURAL_VOICE_HINTS || [];
            naturalHints.forEach((hint, index) => {
                if (name.includes(hint)) {
                    score += 40 - index;
                }
            });

            if (name.includes('google')) {
                score += 18;
            }
            if (name.includes('microsoft')) {
                score += 22;
            }
            if (name.includes('online')) {
                score += 12;
            }

            return score;
        }

        function clampRate(rate) {
            const parsed = Number(rate);
            if (Number.isNaN(parsed)) {
                return CONFIG.VOICE_OUTPUT.DEFAULT_RATE;
            }
            return Math.min(1.4, Math.max(0.75, parsed));
        }

        async function loadVoices() {
            if (!isSupported()) {
                voiceEntries = [];
                return voiceEntries;
            }

            if (voicesLoaded) {
                return voiceEntries;
            }

            if (voiceLoadPromise) {
                return voiceLoadPromise;
            }

            voiceLoadPromise = new Promise((resolve) => {
                const synth = window.speechSynthesis;

                function captureVoices() {
                    const rawVoices = synth.getVoices() || [];
                    if (!rawVoices.length) {
                        return false;
                    }

                    voiceEntries = rawVoices.map((voice) => ({
                        voice,
                        meta: {
                            voiceURI: voice.voiceURI,
                            name: voice.name,
                            lang: voice.lang,
                            default: voice.default,
                        },
                    }));
                    voicesLoaded = true;
                    resolve(voiceEntries);
                    return true;
                }

                if (captureVoices()) {
                    return;
                }

                const timeout = window.setTimeout(() => {
                    synth.removeEventListener('voiceschanged', handleVoicesChanged);
                    voiceEntries = [];
                    voicesLoaded = true;
                    resolve(voiceEntries);
                }, 1500);

                function handleVoicesChanged() {
                    if (!captureVoices()) {
                        return;
                    }
                    window.clearTimeout(timeout);
                    synth.removeEventListener('voiceschanged', handleVoicesChanged);
                }

                synth.addEventListener('voiceschanged', handleVoicesChanged);
            });

            return voiceLoadPromise;
        }

        return {
            id: 'browser',
            label: 'Browser Voice',
            init: initProvider,
            refreshVoices: refresh,
            isSupported,
            listVoices,
            speak: speakWithBrowser,
            stop: stopProvider,
        };
    }

    return {
        init,
        subscribe,
        registerProvider,
        getState,
        setProvider,
        updateSettings,
        refreshVoices,
        speak,
        stop,
    };
})();

window.VoiceOutputService = VoiceOutputService;
