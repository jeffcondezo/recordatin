(function () {
    'use strict';

    var SW_URL = '/paciente/sw.js';
    var SUBSCRIBE_URL = '/paciente/api/push/subscribe/';
    var UNSUBSCRIBE_URL = '/paciente/api/push/unsubscribe/';
    var STORAGE_KEY = 'recordatin_alarmas_activas';
    var ALARMA_AUDIO = '/static/paciente/audio/alarma.wav';

    var dataEl = document.getElementById('recordatorios-data');
    var vapidEl = document.getElementById('vapid-public-key');
    var btnActivar = document.getElementById('btn-activar-alarmas');
    var statusEl = document.getElementById('alarma-status');

    var recordatorios = [];
    var notified = new Set();
    var timeouts = [];
    var pollId = null;

    if (dataEl) {
        try {
            recordatorios = JSON.parse(dataEl.textContent);
        } catch (e) {
            recordatorios = [];
        }
    }

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

    function playAlarma() {
        if (navigator.vibrate) {
            navigator.vibrate([300, 100, 300, 100, 300]);
        }
        try {
            var audio = new Audio(ALARMA_AUDIO);
            audio.volume = 1;
            audio.play().catch(function () {});
        } catch (e) {}
    }

    function showLocalNotification(item) {
        if (!('Notification' in window) || Notification.permission !== 'granted') {
            playAlarma();
            return;
        }
        var title = 'Recordatin — Es hora de su medicina';
        var body = item.nombre + ' (' + item.dosis + ')';
        var n = new Notification(title, {
            body: body,
            icon: '/static/paciente/img/icon-192.png',
            badge: '/static/paciente/img/badge-96.png',
            tag: 'toma-' + item.id,
            requireInteraction: true,
            vibrate: [300, 100, 300],
        });
        n.onclick = function () {
            window.location.href = '/paciente/medicamentos/hoy/';
        };
        playAlarma();
    }

    function fireReminder(item) {
        var key = item.id + '-' + (item.fecha || '') + '-' + item.hora;
        if (notified.has(key)) return;
        notified.add(key);
        showLocalNotification(item);
    }

    function checkRemindersPoll() {
        if (document.hidden) return;
        var now = Date.now();
        recordatorios.forEach(function (item) {
            if (!item.at_ms) return;
            if (now >= item.at_ms && now < item.at_ms + 60000) {
                fireReminder(item);
            }
        });
    }

    function scheduleForegroundTimers() {
        timeouts.forEach(clearTimeout);
        timeouts = [];
        var now = Date.now();
        recordatorios.forEach(function (item) {
            if (!item.at_ms) return;
            var delay = item.at_ms - now;
            if (delay > 0 && delay < 24 * 60 * 60 * 1000) {
                var tid = setTimeout(function () {
                    fireReminder(item);
                }, delay);
                timeouts.push(tid);
            }
        });
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
                    setStatus('No se pudo registrar el servicio de alarmas.', true);
                    return;
                }
                return subscribePush(reg).then(function (sub) {
                    return postJson(SUBSCRIBE_URL, sub.toJSON());
                }).then(function (res) {
                    if (res && res.ok) {
                        localStorage.setItem(STORAGE_KEY, '1');
                        setStatus('Alarmas activadas en este celular. Añada la app a la pantalla de inicio para mejor resultado.');
                        updateCardState(true);
                        scheduleForegroundTimers();
                        startPoll();
                    } else {
                        setStatus('No se pudo guardar la suscripción. Intente de nuevo.', true);
                    }
                });
            }).catch(function () {
                setStatus('Error al activar alarmas. Use Chrome o Edge actualizado.', true);
            });
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

    function startPoll() {
        if (pollId) return;
        pollId = setInterval(checkRemindersPoll, 15000);
        checkRemindersPoll();
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
                scheduleForegroundTimers();
                startPoll();
                setStatus('Alarmas activas en este celular.');
            }
        }).catch(function () {});
    }

    if ('serviceWorker' in navigator) {
        registerServiceWorker().catch(function () {});
    }

    if (navigator.serviceWorker) {
        navigator.serviceWorker.addEventListener('message', function (event) {
            if (event.data && event.data.type === 'ALARMA_PUSH') {
                playAlarma();
            }
        });
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

    if (recordatorios.length && Notification.permission === 'granted') {
        scheduleForegroundTimers();
        startPoll();
    }
})();
