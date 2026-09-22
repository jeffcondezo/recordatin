(function () {
    'use strict';

    var SW_URL = '/paciente/sw.js';
    var SUBSCRIBE_URL = '/paciente/api/push/subscribe/';
    var UNSUBSCRIBE_URL = '/paciente/api/push/unsubscribe/';
    var STORAGE_KEY = 'recordatin_alarmas_activas';
    var ALARMA_AUDIO = '/static/paciente/audio/alarma.wav';
    var ACTION_TYPE = 'TOMA_MEDICINA';

    var dataEl = document.getElementById('recordatorios-data');
    var vapidEl = document.getElementById('vapid-public-key');
    var btnActivar = document.getElementById('btn-activar-alarmas');
    var statusEl = document.getElementById('alarma-status');
    var hintEl = document.querySelector('.alarma-hint');

    var recordatorios = [];
    var notified = new Set();
    var timeouts = [];
    var pollId = null;
    var nativeListenerReady = false;

    if (dataEl) {
        try {
            recordatorios = JSON.parse(dataEl.textContent);
        } catch (e) {
            recordatorios = [];
        }
    }

    function getCapacitor() {
        return window.Capacitor || window.capacitor || null;
    }

    function isNativeApp() {
        try {
            var Cap = getCapacitor();
            if (!Cap) return false;
            if (typeof Cap.isNativePlatform === 'function' && Cap.isNativePlatform()) {
                return true;
            }
            if (typeof Cap.getPlatform === 'function') {
                var p = Cap.getPlatform();
                return p === 'android' || p === 'ios';
            }
            // WebView de la APK a veces expone Capacitor antes de isNativePlatform.
            return !!(Cap.isPluginAvailable || Cap.registerPlugin || Cap.Plugins);
        } catch (e) {
            return false;
        }
    }

    var _localNotificationsPlugin = null;

    function nativeLocalNotifications() {
        if (_localNotificationsPlugin) {
            return _localNotificationsPlugin;
        }
        try {
            var Cap = getCapacitor();
            if (!Cap) return null;
            if (Cap.Plugins && Cap.Plugins.LocalNotifications) {
                _localNotificationsPlugin = Cap.Plugins.LocalNotifications;
                return _localNotificationsPlugin;
            }
            // Con server.url remoto no viene el JS del plugin; hay que registrarlo en el bridge.
            if (typeof Cap.registerPlugin === 'function') {
                _localNotificationsPlugin = Cap.registerPlugin('LocalNotifications');
                return _localNotificationsPlugin;
            }
            if (typeof Cap.plugin === 'function') {
                _localNotificationsPlugin = Cap.plugin('LocalNotifications');
                return _localNotificationsPlugin;
            }
        } catch (e) {
            return null;
        }
        return null;
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
            body: JSON.stringify(body || {}),
        }).then(function (r) {
            return r.json().catch(function () {
                return { ok: r.ok };
            });
        });
    }

    function marcarTomaApi(tomaId) {
        return fetch('/paciente/medicamentos/' + tomaId + '/tomar-api/', {
            method: 'POST',
            credentials: 'include',
            headers: {
                'Accept': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
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

    function ensureNativeListeners() {
        var LN = nativeLocalNotifications();
        if (!LN || nativeListenerReady) {
            return Promise.resolve();
        }
        nativeListenerReady = true;
        return LN.registerActionTypes({
            types: [{
                id: ACTION_TYPE,
                actions: [
                    { id: 'tomar', title: 'Ya lo tomé', foreground: true },
                    { id: 'abrir', title: 'Abrir', foreground: true },
                ],
            }],
        }).then(function () {
            LN.addListener('localNotificationActionPerformed', function (event) {
                var extra = (event.notification && event.notification.extra) || {};
                var tomaId = extra.tomaId;
                var action = event.actionId;
                if (action === 'tomar' && tomaId) {
                    marcarTomaApi(tomaId).finally(function () {
                        window.location.href = '/paciente/medicamentos/hoy/';
                    });
                } else {
                    window.location.href = '/paciente/medicamentos/hoy/';
                }
            });
            LN.addListener('localNotificationReceived', function () {
                playAlarma();
            });
        }).catch(function () {});
    }

    function scheduleNativeAlarms() {
        var LN = nativeLocalNotifications();
        if (!LN) {
            return Promise.resolve(false);
        }

        return ensureNativeListeners().then(function () {
            return LN.getPending();
        }).then(function (pending) {
            var list = (pending && pending.notifications) || [];
            if (!list.length) {
                return null;
            }
            return LN.cancel({ notifications: list.map(function (n) {
                return { id: n.id };
            }) });
        }).then(function () {
            var now = Date.now();
            var notifications = [];
            recordatorios.forEach(function (item) {
                if (!item.at_ms || !item.id) return;
                if (item.at_ms <= now) return;
                // ID numérico estable por toma (requerido por Android).
                var nid = parseInt(item.id, 10);
                if (!nid) return;
                notifications.push({
                    id: nid,
                    title: 'Recordatin — Es hora de su medicina',
                    body: item.nombre + ' (' + item.dosis + ')',
                    schedule: {
                        at: new Date(item.at_ms).toISOString(),
                        allowWhileIdle: true,
                    },
                    actionTypeId: ACTION_TYPE,
                    extra: {
                        tomaId: String(item.id),
                        url: '/paciente/medicamentos/hoy/',
                    },
                });
            });
            if (!notifications.length) {
                return true;
            }
            return LN.schedule({ notifications: notifications }).then(function () {
                return true;
            });
        }).catch(function () {
            return false;
        });
    }

    function requestNativePermissions() {
        var LN = nativeLocalNotifications();
        if (!LN) {
            return Promise.resolve(false);
        }
        return LN.requestPermissions().then(function (perm) {
            var display = perm && (perm.display || perm.granted);
            return display === 'granted' || display === true;
        }).catch(function () {
            return false;
        });
    }

    function activarAlarmasNativas() {
        return requestNativePermissions().then(function (ok) {
            if (!ok) {
                setStatus('Debe permitir notificaciones (y alarmas exactas, si Android lo pide).', true);
                return;
            }
            return scheduleNativeAlarms().then(function (scheduled) {
                localStorage.setItem(STORAGE_KEY, '1');
                updateCardState(true);
                scheduleForegroundTimers();
                startPoll();
                if (scheduled) {
                    setStatus('Alarmas del teléfono activadas. Sonarán aunque la app esté cerrada.');
                } else {
                    setStatus('Permiso concedido, pero no se pudieron programar. Intente de nuevo.', true);
                }
            });
        });
    }

    function activarAlarmasWeb() {
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

    function activarAlarmas() {
        // En la APK el WebView NO tiene Notification del navegador; hay que usar el plugin nativo.
        if (isNativeApp() || getCapacitor()) {
            var LN = nativeLocalNotifications();
            if (!LN) {
                setStatus(
                    'No se pudo conectar con las alarmas del teléfono. Cierre la app, ábrala de nuevo e intente otra vez. Si sigue igual, reinstale el APK.',
                    true,
                );
                return Promise.resolve();
            }
            return activarAlarmasNativas();
        }
        return activarAlarmasWeb();
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
        if (isNativeApp() || getCapacitor()) {
            if (localStorage.getItem(STORAGE_KEY) === '1') {
                updateCardState(true);
                setStatus('Alarmas del teléfono activas.');
                scheduleNativeAlarms();
                scheduleForegroundTimers();
                startPoll();
            }
            return;
        }
        if (typeof Notification === 'undefined' || Notification.permission !== 'granted') return;
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

    // Esperar un instante: el bridge de Capacitor a veces se inyecta después del script.
    function whenCapacitorReady(cb) {
        if (getCapacitor()) {
            cb();
            return;
        }
        var tries = 0;
        var timer = setInterval(function () {
            tries += 1;
            if (getCapacitor() || tries > 20) {
                clearInterval(timer);
                cb();
            }
        }, 100);
    }

    whenCapacitorReady(function () {
        if (isNativeApp() || getCapacitor()) {
            if (hintEl) {
                hintEl.innerHTML = 'En la app instalada, pulse el botón para programar las <strong>alarmas del teléfono</strong> (más precisas que el navegador).';
            }
        } else if ('serviceWorker' in navigator) {
            registerServiceWorker().catch(function () {});
        }

        if (localStorage.getItem(STORAGE_KEY) === '1' || (!isNativeApp() && typeof Notification !== 'undefined' && Notification.permission === 'granted')) {
            initExistingSubscription();
        }

        if (recordatorios.length && localStorage.getItem(STORAGE_KEY) === '1') {
            if (isNativeApp() || getCapacitor()) {
                scheduleNativeAlarms();
            }
            scheduleForegroundTimers();
            startPoll();
        }
    });

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
})();
