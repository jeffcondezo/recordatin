/* Service worker — alarmas push Recordatin */
var DEFAULT_URL = '/paciente/medicamentos/hoy/';
var ICON = '/static/paciente/img/icon-192.png';
var BADGE = '/static/paciente/img/badge-96.png';

function openOrFocus(url) {
    return self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (clientList) {
        for (var i = 0; i < clientList.length; i++) {
            var client = clientList[i];
            if (client.url.indexOf('/paciente/') !== -1 && 'focus' in client) {
                return client.focus().then(function (focused) {
                    if (focused && 'navigate' in focused) {
                        return focused.navigate(url);
                    }
                    return focused;
                });
            }
        }
        if (self.clients.openWindow) {
            return self.clients.openWindow(url);
        }
    });
}

function getCsrfToken() {
    if (!self.cookieStore) {
        return Promise.resolve(null);
    }
    return self.cookieStore.get('csrftoken').then(function (c) {
        return c ? c.value : null;
    }).catch(function () {
        return null;
    });
}

function marcarTomaDesdeNotif(tomaId) {
    var apiUrl = '/paciente/medicamentos/' + tomaId + '/tomar-api/';
    var fallbackUrl = '/paciente/medicamentos/' + tomaId + '/tomar-notif/';

    return getCsrfToken().then(function (csrf) {
        var headers = { 'Accept': 'application/json' };
        if (csrf) {
            headers['X-CSRFToken'] = csrf;
        }
        return fetch(apiUrl, {
            method: 'POST',
            credentials: 'include',
            headers: headers,
        }).then(function (res) {
            if (res.ok) {
                return res.json().catch(function () { return { ok: true }; });
            }
            return openOrFocus(fallbackUrl);
        }).catch(function () {
            return openOrFocus(fallbackUrl);
        });
    });
}

self.addEventListener('push', function (event) {
    if (!event.data) {
        return;
    }
    var payload = {};
    try {
        payload = event.data.json();
    } catch (e) {
        payload = { title: 'Recordatin', body: event.data.text() };
    }

    var title = payload.title || 'Recordatin — Es hora de su medicina';
    var actions = payload.actions || [];
    if ((!actions || !actions.length) && (payload.tomaId || payload.demo)) {
        actions = [{ action: 'tomar', title: 'Ya lo tomé' }];
    }

    var options = {
        body: payload.body || '',
        icon: payload.icon || ICON,
        badge: payload.badge || BADGE,
        tag: payload.tag || 'recordatin-alarma',
        vibrate: payload.vibrate || [300, 100, 300, 100, 300],
        requireInteraction: true,
        actions: actions,
        data: {
            url: payload.url || DEFAULT_URL,
            tomaId: payload.tomaId || null,
            demo: !!payload.demo,
        },
    };

    event.waitUntil(
        self.registration.showNotification(title, options).then(function () {
            return self.clients.matchAll({ type: 'window', includeUncontrolled: true });
        }).then(function (clients) {
            clients.forEach(function (client) {
                client.postMessage({
                    type: 'ALARMA_PUSH',
                    title: title,
                    body: options.body,
                });
            });
        })
    );
});

self.addEventListener('notificationclick', function (event) {
    event.notification.close();
    var data = event.notification.data || {};
    var url = data.url || DEFAULT_URL;

    if (event.action === 'tomar') {
        event.waitUntil(
            (function () {
                if (data.demo || !data.tomaId) {
                    return self.registration.showNotification('Recordatin — Prueba', {
                        body: 'En una alarma real, aquí se registraría que ya tomó su medicina.',
                        icon: ICON,
                        badge: BADGE,
                        tag: 'recordatin-prueba-ok',
                    }).then(function () {
                        return openOrFocus(url);
                    });
                }
                return marcarTomaDesdeNotif(data.tomaId).then(function () {
                    return self.registration.showNotification('Recordatin', {
                        body: 'Registramos que tomó su medicina. ¡Muy bien!',
                        icon: ICON,
                        badge: BADGE,
                        tag: 'recordatin-toma-ok',
                    }).then(function () {
                        return openOrFocus('/paciente/medicamentos/hoy/');
                    });
                });
            })()
        );
        return;
    }

    event.waitUntil(openOrFocus(url));
});

self.addEventListener('install', function (event) {
    self.skipWaiting();
});

self.addEventListener('activate', function (event) {
    event.waitUntil(self.clients.claim());
});
