(function () {
    'use strict';

    var CHIME_URL = '/static/paciente/audio/confirmacion.wav';
    var MENSAJE_VOZ = '¡Medicamento registrado!';
    var STORAGE_KEY = 'recordatin_toma_pendiente';

    function vibrarConfirmacion() {
        if (navigator.vibrate) {
            navigator.vibrate([100, 50, 150]);
        }
    }

    function reproducirChime() {
        try {
            var audio = new Audio(CHIME_URL);
            audio.volume = 1;
            return audio.play().catch(function () {});
        } catch (e) {
            return Promise.resolve();
        }
    }

    function hablarRegistrado() {
        if (!('speechSynthesis' in window)) {
            return;
        }
        try {
            window.speechSynthesis.cancel();
            var utterance = new SpeechSynthesisUtterance(MENSAJE_VOZ);
            utterance.lang = 'es-MX';
            utterance.rate = 0.92;
            utterance.pitch = 1;
            utterance.volume = 1;

            var voces = window.speechSynthesis.getVoices();
            for (var i = 0; i < voces.length; i++) {
                if (voces[i].lang && voces[i].lang.indexOf('es') === 0) {
                    utterance.voice = voces[i];
                    break;
                }
            }
            window.speechSynthesis.speak(utterance);
        } catch (e) {}
    }

    function feedbackCompleto() {
        vibrarConfirmacion();
        reproducirChime().then(function () {
            hablarRegistrado();
        });
        anunciarAccesible(MENSAJE_VOZ);
    }

    function anunciarAccesible(texto) {
        var live = document.getElementById('toma-confirm-live');
        if (!live) {
            return;
        }
        live.textContent = '';
        window.setTimeout(function () {
            live.textContent = texto;
        }, 50);
    }

    function hayMensajeRegistro() {
        return !!document.querySelector('.messages .alert-success, .messages .alert-warning');
    }

    function initFormularios() {
        document.querySelectorAll('.med-form').forEach(function (form) {
            form.addEventListener('submit', function () {
                var btn = form.querySelector('button[type="submit"]');
                if (btn && btn.disabled) {
                    return;
                }
                try {
                    sessionStorage.setItem(STORAGE_KEY, '1');
                } catch (e) {}
                vibrarConfirmacion();
                if (btn) {
                    btn.disabled = true;
                    btn.setAttribute('aria-busy', 'true');
                    btn.textContent = 'Registrando…';
                }
            });
        });
    }

    function initPostRedirect() {
        var pendiente = false;
        try {
            pendiente = sessionStorage.getItem(STORAGE_KEY) === '1';
            if (pendiente) {
                sessionStorage.removeItem(STORAGE_KEY);
            }
        } catch (e) {}

        if (hayMensajeRegistro()) {
            feedbackCompleto();
            return;
        }

        if (pendiente) {
            vibrarConfirmacion();
            anunciarAccesible('Enviando registro…');
        }
    }

    if (window.speechSynthesis) {
        window.speechSynthesis.getVoices();
        window.speechSynthesis.onvoiceschanged = function () {
            window.speechSynthesis.getVoices();
        };
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function () {
            initFormularios();
            initPostRedirect();
        });
    } else {
        initFormularios();
        initPostRedirect();
    }
})();
