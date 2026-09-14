/* Vista previa local de la notificación con botón «Ya lo tomé» (sin Web Push). */
(function () {
    var SW_URL = '/paciente/sw.js';
    var ICON = '/static/paciente/img/icon-192.png';
    var BADGE = '/static/paciente/img/badge-96.png';
    var btn = document.getElementById('btn-ver-notif-demo');
    var statusEl = document.getElementById('notif-demo-status');

    if (!btn) {
        return;
    }

    function setStatus(msg, isError) {
        if (!statusEl) return;
        statusEl.textContent = msg || '';
        statusEl.classList.toggle('text-error', !!isError);
    }

    function showPreview(reg) {
        return reg.showNotification('Recordatin — Prueba', {
            body: 'Así se verá la alarma. Pulse «Ya lo tomé» para probar el botón.',
            icon: ICON,
            badge: BADGE,
            tag: 'recordatin-prueba-local',
            requireInteraction: true,
            vibrate: [300, 100, 300],
            actions: [{ action: 'tomar', title: 'Ya lo tomé' }],
            data: {
                url: '/paciente/perfil/',
                tomaId: null,
                demo: true,
            },
        });
    }

    btn.addEventListener('click', function () {
        btn.disabled = true;
        setStatus('Preparando aviso…');

        if (!('Notification' in window) || !('serviceWorker' in navigator)) {
            setStatus('Este navegador no admite notificaciones con botones.', true);
            btn.disabled = false;
            return;
        }

        var permPromise = Notification.permission === 'granted'
            ? Promise.resolve('granted')
            : Notification.requestPermission();

        permPromise.then(function (perm) {
            if (perm !== 'granted') {
                setStatus('Debe permitir notificaciones para ver la vista previa.', true);
                btn.disabled = false;
                return;
            }
            return navigator.serviceWorker.register(SW_URL, { scope: '/paciente/' })
                .then(function (reg) {
                    return navigator.serviceWorker.ready.then(function () {
                        return showPreview(reg);
                    });
                })
                .then(function () {
                    setStatus('Aviso mostrado. Ábralo en la barra de notificaciones y pulse «Ya lo tomé».');
                });
        }).catch(function () {
            setStatus('No se pudo mostrar el aviso. Intente otra vez.', true);
        }).finally(function () {
            btn.disabled = false;
        });
    });
})();
