/**
 * Speech-to-Text mic button — Web Speech API wrapper.
 *
 * Usage:
 *   <button class="btn-dictate" data-target="myTextareaId">🎤</button>
 *   Then call initDictation() once after DOM ready.
 *
 * Or programmatically: attachDictation('myTextareaId', btnElement)
 *
 * Voice commands:
 *   Pages can register commands via registerVoiceCommands({ 'finalise': fn, ... })
 *   User says "command finalise" → fn() is called instead of inserting text.
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
    var _activeTextarea = null;
    var _restartTimer = null;
    var _micPermissionGranted = false;
    var _cursorPos = null; // Saved cursor position for insert-at-cursor

    // Voice command registry: { 'keyword': { fn: Function, label: 'Display Name' } }
    var _voiceCommands = {};

    // Command prefixes (case-insensitive matching)
    var _COMMAND_PREFIXES = ['command ', 'hey rad '];

    /**
     * Register voice commands for the current page.
     * @param {Object} commands - { 'keyword': handler } or { 'keyword': { fn, label } }
     */
    function registerVoiceCommands(commands) {
        for (var key in commands) {
            if (!commands.hasOwnProperty(key)) continue;
            var val = commands[key];
            if (typeof val === 'function') {
                _voiceCommands[key.toLowerCase()] = { fn: val, label: key };
            } else {
                _voiceCommands[key.toLowerCase()] = { fn: val.fn, label: val.label || key };
            }
        }
    }

    /**
     * Check if transcript contains a voice command. Returns matched command or null.
     */
    function _matchCommand(transcript) {
        var text = transcript.trim().toLowerCase();
        for (var p = 0; p < _COMMAND_PREFIXES.length; p++) {
            var prefix = _COMMAND_PREFIXES[p];
            if (text.indexOf(prefix) === 0) {
                var action = text.substring(prefix.length).trim();
                // Try exact match first
                if (_voiceCommands[action]) return _voiceCommands[action];
                // Try fuzzy: check if action starts with a registered keyword
                for (var key in _voiceCommands) {
                    if (action.indexOf(key) === 0 || key.indexOf(action) === 0) {
                        return _voiceCommands[key];
                    }
                }
            }
        }
        // Also match bare "stop listening" / "stop dictation" without prefix
        if (text === 'stop listening' || text === 'stop dictation') {
            return { fn: stopDictation, label: 'Stop Dictation' };
        }
        return null;
    }

    /**
     * Show a command feedback toast (green for success, positioned near active btn)
     */
    function _showCommandToast(label) {
        var btn = _activeBtn;
        if (!btn) return;
        var toast = document.createElement('div');
        toast.className = 'dictation-toast dictation-toast-command';
        toast.innerHTML = '<i class="fas fa-bolt me-1"></i>' + label;
        btn.parentNode.style.position = btn.parentNode.style.position || 'relative';
        btn.parentNode.appendChild(toast);
        setTimeout(function() { toast.remove(); }, 2500);
    }

    /**
     * Show a temporary toast message near the button
     */
    function _showToast(btn, message, isError) {
        var toast = document.createElement('div');
        toast.className = 'dictation-toast' + (isError ? ' dictation-toast-error' : '');
        toast.textContent = message;
        btn.parentNode.style.position = btn.parentNode.style.position || 'relative';
        btn.parentNode.appendChild(toast);
        setTimeout(function() { toast.remove(); }, 4000);
    }

    /**
     * Request microphone permission explicitly.
     */
    function _requestMicPermission() {
        if (_micPermissionGranted) return Promise.resolve(true);
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            return Promise.resolve(true);
        }
        return navigator.mediaDevices.getUserMedia({ audio: true })
            .then(function(stream) {
                stream.getTracks().forEach(function(t) { t.stop(); });
                _micPermissionGranted = true;
                return true;
            })
            .catch(function(err) {
                console.warn('Microphone permission denied:', err.name);
                return false;
            });
    }

    // Track last insertion for "scratch that" / "delete" undo
    var _lastInsert = null; // { textarea, start, length }

    /**
     * Built-in dictation text commands — processed BEFORE inserting text.
     * Returns { handled: true } if the transcript was fully consumed,
     * or { handled: false, text: processedText } for normal insertion.
     */
    function _processBuiltInCommands(transcript, textarea) {
        var text = transcript.trim().toLowerCase();

        // "stop listening" / "stop dictation" — end mic
        if (text === 'stop listening' || text === 'stop dictation') {
            stopDictation();
            return { handled: true };
        }

        // "scratch that" / "delete" — remove last inserted text, or selected text
        if (text === 'scratch that' || text === 'delete' || text === 'undo'
            || text === 'delete that' || text === 'remove that') {
            // If there's a selection, remove it
            var selStart = textarea.selectionStart;
            var selEnd = textarea.selectionEnd;
            if (selStart !== selEnd) {
                var before = textarea.value.substring(0, selStart);
                var after = textarea.value.substring(selEnd);
                textarea.value = before + after;
                textarea.selectionStart = textarea.selectionEnd = selStart;
                _cursorPos = selStart;
                textarea.dispatchEvent(new Event('input', { bubbles: true }));
                return { handled: true };
            }
            // Otherwise remove last insertion
            if (_lastInsert && _lastInsert.textarea === textarea) {
                var lStart = _lastInsert.start;
                var lLen = _lastInsert.length;
                var bef = textarea.value.substring(0, lStart);
                var aft = textarea.value.substring(lStart + lLen);
                textarea.value = bef + aft;
                textarea.selectionStart = textarea.selectionEnd = lStart;
                _cursorPos = lStart;
                _lastInsert = null;
                textarea.dispatchEvent(new Event('input', { bubbles: true }));
                return { handled: true };
            }
            return { handled: true }; // Nothing to delete, consume silently
        }

        // "new line" → insert \n
        if (text === 'new line' || text === 'next line') {
            _insertAtCursor(textarea, '\n', true);
            return { handled: true };
        }

        // "new paragraph" / "new para" → insert \n\n
        if (text === 'new paragraph' || text === 'new para' || text === 'next paragraph') {
            _insertAtCursor(textarea, '\n\n', true);
            return { handled: true };
        }

        // "full stop" / "stop" / "period" → insert "."
        if (text === 'full stop' || text === 'stop' || text === 'period') {
            _insertAtCursor(textarea, '.', true);
            return { handled: true };
        }

        if (text === 'comma') {
            _insertAtCursor(textarea, ',', true);
            return { handled: true };
        }

        if (text === 'question mark') {
            _insertAtCursor(textarea, '?', true);
            return { handled: true };
        }

        if (text === 'colon') {
            _insertAtCursor(textarea, ':', true);
            return { handled: true };
        }

        if (text === 'semicolon' || text === 'semi colon') {
            _insertAtCursor(textarea, ';', true);
            return { handled: true };
        }

        if (text === 'dash' || text === 'hyphen') {
            _insertAtCursor(textarea, ' - ', true);
            return { handled: true };
        }

        return { handled: false, text: transcript };
    }

    /**
     * Insert text at cursor position in textarea (or append if no saved position).
     * @param {boolean} raw - if true, insert exactly (no trimming/separator)
     */
    function _insertAtCursor(textarea, text, raw) {
        var pos = _cursorPos !== null ? _cursorPos : textarea.value.length;
        // Clamp to current length (in case text was edited externally)
        if (pos > textarea.value.length) pos = textarea.value.length;

        var before = textarea.value.substring(0, pos);
        var after = textarea.value.substring(pos);

        var insertText;
        if (raw) {
            // Raw mode: insert exactly as given (punctuation, newlines)
            insertText = text;
        } else {
            // Normal mode: trim and add separator
            var sep = before.length > 0 && !before.match(/[\s\n]$/) ? ' ' : '';
            insertText = sep + text.trim();
        }

        textarea.value = before + insertText + after;

        // Update cursor position for next insertion
        var newPos = pos + insertText.length;
        _cursorPos = newPos;

        // Track for "scratch that" undo
        _lastInsert = { textarea: textarea, start: pos, length: insertText.length };

        // Set actual cursor in textarea
        textarea.selectionStart = textarea.selectionEnd = newPos;

        // Trigger input event
        textarea.dispatchEvent(new Event('input', { bubbles: true }));
    }

    /**
     * Attach dictation to a button → textarea pair.
     */
    function attachDictation(targetId, btn) {
        if (!SpeechRecognition) {
            btn.title = _isStandalone
                ? 'Dictation not available in installed app — open in browser'
                : 'Speech recognition not supported in this browser';
            btn.disabled = true;
            btn.style.opacity = '0.4';
            return;
        }

        btn.addEventListener('click', function() {
            if (_activeBtn === btn) {
                stopDictation();
                return;
            }
            if (_activeRecognition) {
                stopDictation();
            }

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

        // Save cursor position at the moment dictation starts
        _activeTextarea = textarea;
        _cursorPos = textarea.selectionStart || textarea.value.length;

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
                    // 1. Check built-in dictation commands (stop, new line, delete, punctuation)
                    var builtin = _processBuiltInCommands(transcript, textarea);
                    if (builtin.handled) continue;

                    // 2. Check page-specific voice commands ("command finalise", etc.)
                    var cmd = _matchCommand(transcript);
                    if (cmd) {
                        _showCommandToast(cmd.label);
                        try { cmd.fn(); } catch (e) {
                            console.warn('Voice command error:', e);
                        }
                        continue;
                    }

                    // 3. Normal text — insert at cursor position
                    _insertAtCursor(textarea, builtin.text);
                } else {
                    interim += transcript;
                }
            }
            var span = interimDiv.querySelector('.dictation-interim-text');
            if (span) span.textContent = interim || 'Listening...';
        };

        recognition.onerror = function(event) {
            if (event.error === 'no-speech') {
                restartDictation(targetId, btn, recognition, interimDiv);
                return;
            }
            if (event.error === 'aborted') return;
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

        btn.classList.add('dictation-active');
        btn.title = 'Click to stop dictation';
    }

    function restartDictation(targetId, btn, oldRecognition, interimDiv) {
        if (_restartTimer) clearTimeout(_restartTimer);
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
        _activeTextarea = null;
        _cursorPos = null;
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
    window.registerVoiceCommands = registerVoiceCommands;

    // Auto-init on DOMContentLoaded
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initDictation);
    } else {
        initDictation();
    }
})();
