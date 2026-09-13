(function () {
    'use strict';

    var STORAGE_KEY = 'recordatin_text_size';
    var VALID_SIZES = ['normal', 'large', 'xlarge'];
    var LABELS = {
        normal: 'Normal',
        large: 'Grande',
        muygrande: 'Muy grande',
    };

    function normalizeSize(size) {
        if (size === 'xlarge') {
            return 'xlarge';
        }
        if (size === 'large') {
            return 'large';
        }
        return 'normal';
    }

    function getStoredTextSize() {
        try {
            return normalizeSize(localStorage.getItem(STORAGE_KEY) || 'normal');
        } catch (e) {
            return 'normal';
        }
    }

    function applyTextSize(size) {
        var normalized = normalizeSize(size);
        var root = document.documentElement;
        if (normalized === 'normal') {
            delete root.dataset.textSize;
        } else {
            root.dataset.textSize = normalized;
        }
        try {
            localStorage.setItem(STORAGE_KEY, normalized);
        } catch (e) {}
        updateActiveButtons(normalized);
        return normalized;
    }

    function updateActiveButtons(size) {
        var buttons = document.querySelectorAll('[data-text-size-option]');
        buttons.forEach(function (btn) {
            var option = btn.getAttribute('data-text-size-option');
            var isActive = option === size;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-pressed', isActive ? 'true' : 'false');
        });
    }

    function announceChange(size) {
        var status = document.getElementById('text-size-status');
        if (!status) {
            return;
        }
        var label = size === 'xlarge' ? LABELS.muygrande : LABELS[size] || LABELS.normal;
        status.textContent = 'Tamaño de texto: ' + label;
    }

    function initTextSizeControls() {
        var current = getStoredTextSize();
        applyTextSize(current);

        document.querySelectorAll('[data-text-size-option]').forEach(function (btn) {
            btn.addEventListener('click', function () {
                var size = btn.getAttribute('data-text-size-option');
                applyTextSize(size);
                announceChange(size);
            });
        });
    }

    window.RecordatinTextSize = {
        getStoredTextSize: getStoredTextSize,
        applyTextSize: applyTextSize,
        initTextSizeControls: initTextSizeControls,
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initTextSizeControls);
    } else {
        initTextSizeControls();
    }
})();
