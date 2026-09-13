/* Service worker — alarmas push Recordatin */
var DEFAULT_URL = '/paciente/medicamentos/hoy/';
var ICON = '/static/paciente/img/logo.jpeg';

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
    var options = {
        body: payload.body || '',
        icon: payload.icon || ICON,
        badge: payload.badge || ICON,
        tag: payload.tag || 'recordatin-alarma',
        vibrate: payload.vibrate || [300, 100, 300, 100, 300],
        requireInteraction: true,
        data: {
            url: payload.url || DEFAULT_URL,
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
    var url = (event.notification.data && event.notification.data.url) || DEFAULT_URL;
    event.waitUntil(
        self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (clientList) {
            for (var i = 0; i < clientList.length; i++) {
                var client = clientList[i];
                if (client.url.indexOf('/paciente/') !== -1 && 'focus' in client) {
                    return client.focus();
                }
            }
            if (self.clients.openWindow) {
                return self.clients.openWindow(url);
            }
        })
    );
});

self.addEventListener('install', function (event) {
    self.skipWaiting();
});

self.addEventListener('activate', function (event) {
    event.waitUntil(self.clients.claim());
});
