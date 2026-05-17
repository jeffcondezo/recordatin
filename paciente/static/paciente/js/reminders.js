(function () {
    const dataEl = document.getElementById('recordatorios-data');
    if (!dataEl) return;

    let recordatorios;
    try {
        recordatorios = JSON.parse(dataEl.textContent);
    } catch (e) {
        return;
    }

    if (!recordatorios.length || !('Notification' in window)) return;

    const notified = new Set();

    function checkReminders() {
        const now = new Date();
        const currentTime = now.getHours().toString().padStart(2, '0') + ':' +
            now.getMinutes().toString().padStart(2, '0');

        recordatorios.forEach(function (item) {
            const key = item.id + '-' + currentTime;
            if (item.hora === currentTime && !notified.has(key)) {
                notified.add(key);
                new Notification('Recordatin — Toma de medicamento', {
                    body: item.nombre + ' (' + item.dosis + ')',
                    icon: undefined,
                    tag: 'toma-' + item.id,
                });
            }
        });
    }

    if (Notification.permission === 'granted') {
        setInterval(checkReminders, 60000);
        checkReminders();
    } else if (Notification.permission !== 'denied') {
        Notification.requestPermission().then(function (permission) {
            if (permission === 'granted') {
                setInterval(checkReminders, 60000);
                checkReminders();
            }
        });
    }
})();
