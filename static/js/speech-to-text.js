/**
 * Speech-to-Text mic button — Web Speech API wrapper.
 *
 * Usage:
 *   <button class="btn-dictate" data-target="myTextareaId">🎤</button>
 *   Then call initDictation() once after DOM ready.
 *
 * Or programmatically: attachDictation('myTextareaId', btnElement)
 */
(function() {
    'use strict';

    var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    // Track active recognition instance globally (only one mic at a time)
    var _activeRecognition = null;
    var _activeBtn = null;
    var _restartTimer = null;

    /**
     * Attach dictation to a button → textarea pair.
     */
    function attachDictation(targetId, btn) {
        if (!SpeechRecognition) {
            btn.title = 'Speech recognition not supported in this browser';
            btn.disabled = true;
            btn.style.opacity = '0.4';
            return;
        }

        btn.addEventListener('click', function() {
            // If this button is already active, stop
            if (_activeBtn === btn) {
                stopDictation();
                return;
            }
            // If another mic is active, stop it first
            if (_activeRecognition) {
                stopDictation();
            }
            startDictation(targetId, btn);
        });
    }

    function startDictation(targetId, btn) {
        var textarea = document.getElementById(targetId);
        if (!textarea) return;

        var recognition = new SpeechRecognition();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'en-GB';

        var finalTranscript = '';
        var interimDiv = null;

        // Create interim display below textarea
        interimDiv = document.createElement('div');
        interimDiv.className = 'dictation-interim';
        interimDiv.innerHTML = '<i class="fas fa-microphone me-1"></i><span class="dictation-interim-text">Listening...</span>';
        textarea.parentNode.insertBefore(interimDiv, textarea.nextSibling);

        recognition.onresult = function(event) {
            var interim = '';
            for (var i = event.resultIndex; i < event.results.length; i++) {
                var transcript = event.results[i][0].transcript;
                if (event.results[i].isFinal) {
                    finalTranscript += transcript;
                    // Append to textarea
                    var current = textarea.value;
                    var sep = current && !current.match(/[\s\n]$/) ? ' ' : '';
                    textarea.value = current + sep + transcript.trim();
                    // Trigger input event for any listeners (auto-resize, live update, etc.)
                    textarea.dispatchEvent(new Event('input', { bubbles: true }));
                    finalTranscript = '';
                } else {
                    interim += transcript;
                }
            }
            // Show interim text
            var span = interimDiv.querySelector('.dictation-interim-text');
            if (span) span.textContent = interim || 'Listening...';
        };

        recognition.onerror = function(event) {
            if (event.error === 'no-speech') {
                // Silence timeout — restart
                restartDictation(targetId, btn, recognition, interimDiv);
                return;
            }
            if (event.error === 'aborted') return; // Manual stop
            console.warn('Speech recognition error:', event.error);
            stopDictation();
        };

        recognition.onend = function() {
            // Auto-restart if still in active mode (browser cuts off after ~60s)
            if (_activeBtn === btn) {
                restartDictation(targetId, btn, recognition, interimDiv);
            }
        };

        recognition.start();
        _activeRecognition = recognition;
        _activeBtn = btn;

        // Visual feedback
        btn.classList.add('dictation-active');
        btn.title = 'Click to stop dictation';
    }

    function restartDictation(targetId, btn, oldRecognition, interimDiv) {
        // Clear any pending restart
        if (_restartTimer) clearTimeout(_restartTimer);

        // Only restart if still the active button
        if (_activeBtn !== btn) return;

        _restartTimer = setTimeout(function() {
            if (_activeBtn !== btn) return;
            try {
                var textarea = document.getElementById(targetId);
                if (!textarea) { stopDictation(); return; }

                var recognition = new SpeechRecognition();
                recognition.continuous = true;
                recognition.interimResults = true;
                recognition.lang = 'en-GB';

                recognition.onresult = oldRecognition.onresult;
                recognition.onerror = oldRecognition.onerror;
                recognition.onend = function() {
                    if (_activeBtn === btn) {
                        restartDictation(targetId, btn, recognition, interimDiv);
                    }
                };

                recognition.start();
                _activeRecognition = recognition;
            } catch (e) {
                console.warn('Failed to restart dictation:', e);
                stopDictation();
            }
        }, 300);
    }

    function stopDictation() {
        if (_restartTimer) { clearTimeout(_restartTimer); _restartTimer = null; }
        if (_activeRecognition) {
            try { _activeRecognition.abort(); } catch (e) {}
            _activeRecognition = null;
        }
        if (_activeBtn) {
            _activeBtn.classList.remove('dictation-active');
            _activeBtn.title = 'Click to dictate';
            _activeBtn = null;
        }
        // Remove all interim displays
        document.querySelectorAll('.dictation-interim').forEach(function(el) { el.remove(); });
    }

    /**
     * Auto-init: find all buttons with class="btn-dictate" and data-target="elementId"
     */
    function initDictation() {
        document.querySelectorAll('.btn-dictate[data-target]').forEach(function(btn) {
            attachDictation(btn.dataset.target, btn);
        });
    }

    // Expose globally
    window.initDictation = initDictation;
    window.attachDictation = attachDictation;
    window.stopDictation = stopDictation;

    // Auto-init on DOMContentLoaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initDictation);
    } else {
        initDictation();
    }
})();
