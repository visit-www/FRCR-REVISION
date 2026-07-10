/**
 * Onboarding Tour — Interactive step-by-step guide
 *
 * Highlights real DOM elements with a spotlight overlay and tooltip.
 * Tracks completion in localStorage; can be re-triggered from dashboard.
 *
 * Usage:
 *   new OnboardingTour(steps, { storageKey: 'key', notifyServer: true })
 */

class OnboardingTour {
    constructor(steps, options) {
        options = options || {};
        this.STORAGE_KEY = options.storageKey || 'radinsights_tour_seen';
        this.notifyServer = options.notifyServer !== false;  // default true
        this.currentStep = 0;
        this.overlay = null;
        this.tooltip = null;
        this.spotlight = null;
        this.active = false;
        this.steps = steps || [];
    }

    /** Has user already seen the tour? */
    hasSeen() {
        try { return localStorage.getItem(this.STORAGE_KEY) === 'true'; } catch (e) { return false; }
    }

    /** Mark tour as seen */
    markSeen() {
        try { localStorage.setItem(this.STORAGE_KEY, 'true'); } catch (e) {}
        if (this.notifyServer) {
            fetch('/api/tour/complete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                credentials: 'include'
            }).catch(function() {});
        }
    }

    /** Start the tour */
    start() {
        if (this.active) return;
        this.active = true;
        this.currentStep = 0;
        this._createOverlay();
        this._showStep();
    }

    /** Stop the tour */
    stop() {
        if (!this.active) return;
        this.active = false;
        this._removeOverlay();
        this.markSeen();
    }

    /** Build overlay DOM */
    _createOverlay() {
        var self = this;

        // Backdrop
        this.overlay = document.createElement('div');
        this.overlay.className = 'tour-overlay';
        this.overlay.addEventListener('click', function(e) {
            if (e.target === self.overlay) self.stop();
        });

        // Spotlight cut-out
        this.spotlight = document.createElement('div');
        this.spotlight.className = 'tour-spotlight';

        // Tooltip
        this.tooltip = document.createElement('div');
        this.tooltip.className = 'tour-tooltip';

        document.body.appendChild(this.overlay);
        document.body.appendChild(this.spotlight);
        document.body.appendChild(this.tooltip);

        // Prevent background scroll
        document.body.style.overflow = 'hidden';
    }

    /** Remove overlay DOM */
    _removeOverlay() {
        if (this.overlay) this.overlay.remove();
        if (this.spotlight) this.spotlight.remove();
        if (this.tooltip) this.tooltip.remove();
        this.overlay = null;
        this.spotlight = null;
        this.tooltip = null;
        document.body.style.overflow = '';
    }

    /** Display current step */
    _showStep() {
        var step = this.steps[this.currentStep];
        var total = this.steps.length;
        var self = this;

        // Progress dots
        var dots = '';
        for (var i = 0; i < total; i++) {
            dots += '<span class="tour-dot' + (i === this.currentStep ? ' active' : '') + '"></span>';
        }

        // Buttons
        var prevBtn = this.currentStep > 0
            ? '<button class="tour-btn tour-btn-secondary" data-tour-action="prev"><i class="fas fa-chevron-left me-1"></i>Back</button>'
            : '';

        var nextLabel = this.currentStep === total - 1
            ? '<i class="fas fa-check me-1"></i>Finish'
            : 'Next<i class="fas fa-chevron-right ms-1"></i>';

        var nextBtn = '<button class="tour-btn tour-btn-primary" data-tour-action="next">' + nextLabel + '</button>';
        var skipBtn = this.currentStep < total - 1
            ? '<button class="tour-btn tour-btn-skip" data-tour-action="skip">Skip tour</button>'
            : '';

        this.tooltip.innerHTML =
            '<div class="tour-tooltip-header">' +
                '<div class="tour-tooltip-icon"><i class="' + step.icon + '"></i></div>' +
                '<div class="tour-tooltip-step">' + (this.currentStep + 1) + ' / ' + total + '</div>' +
            '</div>' +
            '<h4 class="tour-tooltip-title">' + step.title + '</h4>' +
            '<p class="tour-tooltip-text">' + step.text + '</p>' +
            '<div class="tour-tooltip-dots">' + dots + '</div>' +
            '<div class="tour-tooltip-actions">' +
                '<div>' + skipBtn + '</div>' +
                '<div class="d-flex gap-2">' + prevBtn + nextBtn + '</div>' +
            '</div>';

        // Wire up actions
        this.tooltip.querySelectorAll('[data-tour-action]').forEach(function(btn) {
            btn.addEventListener('click', function(e) {
                var action = e.currentTarget.getAttribute('data-tour-action');
                if (action === 'next') self._next();
                else if (action === 'prev') self._prev();
                else if (action === 'skip') self.stop();
            });
        });

        // Position spotlight and tooltip
        if (step.selector) {
            var el = document.querySelector(step.selector);
            var elRect = el ? el.getBoundingClientRect() : null;
            // Check element exists AND is visible (hidden elements have zero dimensions)
            if (el && elRect && elRect.width > 0 && elRect.height > 0) {
                // Allow scroll so we can scroll to element
                document.body.style.overflow = '';
                el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                setTimeout(function() {
                    document.body.style.overflow = 'hidden';
                    self._positionAt(el, step.position);
                }, 400);
            } else {
                this._positionCenter();
            }
        } else {
            this._positionCenter();
        }
    }

    /** Position spotlight + tooltip around a target element */
    _positionAt(el, position) {
        var rect = el.getBoundingClientRect();
        var pad = 10;
        var margin = 16;

        // Show spotlight (absolute position for box-shadow cutout)
        this.spotlight.style.display = 'block';
        this.spotlight.style.top = (rect.top - pad + window.scrollY) + 'px';
        this.spotlight.style.left = (rect.left - pad) + 'px';
        this.spotlight.style.width = (rect.width + pad * 2) + 'px';
        this.spotlight.style.height = (rect.height + pad * 2) + 'px';

        // Show tooltip with fixed positioning (viewport-relative, immune to overflow:hidden)
        this.tooltip.style.position = 'fixed';
        this.tooltip.style.display = 'block';
        this.tooltip.classList.remove('tour-tooltip-center');
        var tooltipRect = this.tooltip.getBoundingClientRect();

        var tooltipTop;
        var tooltipLeft = Math.max(margin, Math.min(
            rect.left + rect.width / 2 - tooltipRect.width / 2,
            window.innerWidth - tooltipRect.width - margin
        ));

        if (position === 'bottom') {
            tooltipTop = rect.bottom + pad + 12;
            // Flip to top if tooltip goes below viewport
            if (tooltipTop + tooltipRect.height > window.innerHeight - margin) {
                tooltipTop = rect.top - tooltipRect.height - pad - 12;
            }
        } else if (position === 'top') {
            tooltipTop = rect.top - tooltipRect.height - pad - 12;
            // Flip to bottom if tooltip goes above viewport
            if (tooltipTop < margin) {
                tooltipTop = rect.bottom + pad + 12;
            }
        }

        // Final clamp: keep tooltip fully within viewport
        tooltipTop = Math.max(margin, Math.min(tooltipTop, window.innerHeight - tooltipRect.height - margin));

        this.tooltip.style.top = tooltipTop + 'px';
        this.tooltip.style.left = tooltipLeft + 'px';
    }

    /** Center tooltip (for welcome/finish steps) */
    _positionCenter() {
        this.spotlight.style.display = 'none';
        this.tooltip.style.position = '';  // Reset so .tour-tooltip-center CSS takes over
        this.tooltip.style.display = 'block';
        this.tooltip.classList.add('tour-tooltip-center');
        this.tooltip.style.top = '';
        this.tooltip.style.left = '';
    }

    _next() {
        if (this.currentStep < this.steps.length - 1) {
            this.currentStep++;
            this._showStep();
        } else {
            this.stop();
        }
    }

    _prev() {
        if (this.currentStep > 0) {
            this.currentStep--;
            this._showStep();
        }
    }
}
