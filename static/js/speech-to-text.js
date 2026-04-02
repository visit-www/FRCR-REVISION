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

    // Detect standalone PWA mode
    var _isStandalone = window.matchMedia('(display-mode: standalone)').matches
        || window.navigator.standalone === true;

    // Track active recognition instance globally (only one mic at a time)
    var _activeRecognition = null;
    var _activeBtn = null;
    var _restartTimer = null;
    var _micPermissionGranted = false;

    /**
     * Show a temporary toast message near the button
     */
    function _showToast(btn, message, isError) {
        var toast = document.createElement('div');
        toast.className = 'dictation-toast' + (isError ? ' dictation-toast-error' : '');
        toast.textContent = message;
        // Position near the button
        btn.parentNode.style.position = btn.parentNode.style.position || 'relative';
        btn.parentNode.appendChild(toast);
        setTimeout(function() { toast.remove(); }, 4000);
    }

    /**
     * Request microphone permission explicitly.
     * In standalone PWAs, the Speech API often fails silently without this.
     */
    function _requestMicPermission() {
        if (_micPermissionGranted) return Promise.resolve(true);
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            return Promise.resolve(true); // Can't pre-request, let Speech API try
        }
        return navigator.mediaDevices.getUserMedia({ audio: true })
            .then(function(stream) {
                // Stop the stream immediately — we just needed the permission
                stream.getTracks().forEach(function(t) { t.stop(); });
                _micPermissionGranted = true;
                return true;
            })
            .catch(function(err) {
                console.warn('Microphone permission denied:', err.name);
                return false;
            });
    }

    /**
     * Attach dictation to a button → textarea pair.
     */
    function attachDictation(targetId, btn) {
        if (!SpeechRecognition) {
            btn.title = 'Speech recognition not supported in this browser';
            btn.disabled = true;
            btn.style.opacity = '0.4';
            // In standalone PWA on iOS, show why it's disabled
            if (_isStandalone) {
                btn.title = 'Dictation not available in installed app — open in browser';
            }
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

            // Request mic permission first, then start
            _requestMicPermission().then(function(granted) {
                if (!granted) {
                    _showToast(btn, 'Microphone permission denied — check browser settings', true);
                    return;
                }
                startDictation(targetId, btn);
            });
        });
    }

    function startDictation(targetId, btn) {
        var textarea = document.getElementById(targetId);
        if (!textarea) return;

        var recognition;
        try {
            recognition = new SpeechRecognition();
        } catch (e) {
            _showToast(btn, 'Speech recognition unavailable — try opening in browser', true);
            return;
        }
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
            if (event.error === 'not-allowed') {
                _showToast(btn, 'Microphone access blocked — check app permissions', true);
                stopDictation();
                return;
            }
            if (event.error === 'service-not-allowed' || event.error === 'network') {
                _showToast(btn, 'Speech service unavailable — try opening in browser', true);
                stopDictation();
                return;
            }
            console.warn('Speech recognition error:', event.error);
            _showToast(btn, 'Dictation error: ' + event.error, true);
            stopDictation();
        };

        recognition.onend = function() {
            // Auto-restart if still in active mode (browser cuts off after ~60s)
            if (_activeBtn === btn) {
                restartDictation(targetId, btn, recognition, interimDiv);
            }
        };

        try {
            recognition.start();
        } catch (e) {
            console.warn('Failed to start speech recognition:', e);
            _showToast(btn, 'Could not start dictation — try opening in browser', true);
            if (interimDiv) interimDiv.remove();
            return;
        }

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
