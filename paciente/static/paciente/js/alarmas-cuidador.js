(function () {
    'use strict';

    var SW_URL = '/paciente/sw.js';
    var SUBSCRIBE_URL = '/paciente/api/cuidador/push/subscribe/';
    var STORAGE_KEY = 'recordatin_cuidador_alarmas';

    var vapidEl = document.getElementById('vapid-public-key');
    var btnActivar = document.getElementById('btn-activar-alarmas');
    var statusEl = document.getElementById('alarma-status');

    function getCookie(name) {
        var match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'));
        return match ? decodeURIComponent(match[2]) : '';
    }

    function setStatus(msg, isError) {
        if (!statusEl) return;
        statusEl.textContent = msg;
        statusEl.classList.toggle('alarma-status-error', !!isError);
    }

    function urlBase64ToUint8Array(base64String) {
        var padding = '='.repeat((4 - (base64String.length % 4)) % 4);
        var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
        var raw = window.atob(base64);
        var arr = new Uint8Array(raw.length);
        for (var i = 0; i < raw.length; i++) {
            arr[i] = raw.charCodeAt(i);
        }
        return arr;
    }

    function postJson(url, body) {
        return fetch(url, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            credentials: 'same-origin',
            body: JSON.stringify(body),
        }).then(function (r) {
            return r.json().catch(function () {
                return { ok: r.ok };
            });
        });
    }

    function registerServiceWorker() {
        if (!('serviceWorker' in navigator)) {
            return Promise.resolve(null);
        }
        return navigator.serviceWorker.register(SW_URL, { scope: '/paciente/' });
    }

    function subscribePush(registration) {
        var vapidKey = vapidEl ? JSON.parse(vapidEl.textContent) : '';
        if (!vapidKey || !registration.pushManager) {
            return Promise.reject(new Error('Push no disponible'));
        }
        return registration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(vapidKey),
        });
    }

    function updateCardState(active) {
        var card = document.getElementById('alarma-card');
        if (!card) return;
        card.classList.toggle('alarma-card-activa', active);
        if (btnActivar) {
            btnActivar.hidden = active;
        }
    }

    function activarAlarmas() {
        if (!('Notification' in window)) {
            setStatus('Su navegador no admite notificaciones.', true);
            return Promise.resolve();
        }
        return Notification.requestPermission().then(function (perm) {
            if (perm !== 'granted') {
                setStatus('Debe permitir notificaciones en Ajustes del celular.', true);
                return;
            }
            return registerServiceWorker().then(function (reg) {
                if (!reg) {
                    setStatus('No se pudo registrar el servicio de alertas.', true);
                    return;
                }
                return subscribePush(reg).then(function (sub) {
                    return postJson(SUBSCRIBE_URL, sub.toJSON());
                }).then(function (res) {
                    if (res && res.ok) {
                        localStorage.setItem(STORAGE_KEY, '1');
                        setStatus('Alertas activadas. Recibirá avisos si olvida registrar una medicina.');
                        updateCardState(true);
                    } else {
                        setStatus('No se pudo guardar la suscripción. Intente de nuevo.', true);
                    }
                });
            }).catch(function () {
                setStatus('Error al activar alertas. Use Chrome o Edge actualizado.', true);
            });
        });
    }

    function initExistingSubscription() {
        if (Notification.permission !== 'granted') return;
        registerServiceWorker().then(function (reg) {
            if (!reg || !reg.pushManager) return;
            return reg.pushManager.getSubscription();
        }).then(function (sub) {
            if (sub) {
                localStorage.setItem(STORAGE_KEY, '1');
                updateCardState(true);
                setStatus('Alertas activas en este celular.');
            }
        }).catch(function () {});
    }

    if ('serviceWorker' in navigator) {
        registerServiceWorker().catch(function () {});
    }

    if (btnActivar) {
        btnActivar.addEventListener('click', function () {
            btnActivar.disabled = true;
            activarAlarmas().finally(function () {
                btnActivar.disabled = false;
            });
        });
    }

    if (localStorage.getItem(STORAGE_KEY) === '1' || Notification.permission === 'granted') {
        initExistingSubscription();
    }
})();
