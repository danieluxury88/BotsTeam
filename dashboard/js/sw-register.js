// Service Worker Registration
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/service-worker.js')
            .then((registration) => {
                console.log('Service Worker registered:', registration.scope);
                
                registration.addEventListener('updatefound', () => {
                    const newWorker = registration.installing;
                    if (newWorker) {
                        newWorker.addEventListener('statechange', () => {
                            if (newWorker.state === 'installed') {
                                if (navigator.serviceWorker.controller) {
                                    console.log('New content available; please refresh.');
                                } else {
                                    console.log('Content is now available offline.');
                                }
                            }
                        });
                    }
                });
            })
            .catch((error) => {
                console.error('Service Worker registration failed:', error);
            });
    });
    
    // Listen for messages from service worker
    navigator.serviceWorker.addEventListener('message', (event) => {
        if (event.data && event.data.type === 'SKIP_WAITING') {
            navigator.serviceWorker.ready.then((registration) => {
                registration.waiting.postMessage({ type: 'SKIP_WAITING' });
            });
        }
    });
}
