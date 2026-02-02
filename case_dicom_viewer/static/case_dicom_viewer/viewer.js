/**
 * Case DICOM Viewer - Cornerstone.js v4.x Integration
 * Features: Stack scroll (mouse wheel), zoom, pan, window/level, annotations
 * v10: Slider at ~2% loaded; global cache per plan; cache indicator on plan switch
 */
(function () {
  "use strict";

  // External module references (set after libraries load)
  var cornerstone = null;
  var cornerstoneTools = null;
  var cornerstoneWebImageLoader = null;
  var cornerstoneMath = null;

  // Viewer state
  var _element = null;
  var _stackConfig = null;
  var _currentPlan = null;
  var _currentIndex = 0;
  var _imageIds = [];
  var _onSliceChange = null;
  var _onCacheProgress = null;
  var _onAllCached = null;
  var _onSliderReady = null;
  var _isAdmin = false;
  var _annotations = {}; // { planName: { imageIndex: [annotations] } }
  var _preloadedImages = {};
  var _panModeActive = false;
  var _keyboardListener = null;
  var _keyboardContainer = null;
  var _fullscreenContainer = null;

  /**
   * Initialize external modules - call after libraries are loaded
   */
  function initExternalModules() {
    cornerstone = window.cornerstone;
    cornerstoneTools = window.cornerstoneTools;
    cornerstoneWebImageLoader = window.cornerstoneWebImageLoader;
    cornerstoneMath = window.cornerstoneMath;

    if (!cornerstone || !cornerstoneTools) {
      console.warn("[CaseDicomViewer] Cornerstone libraries not loaded");
      return false;
    }

    // Initialize cornerstone-tools with external modules
    cornerstoneTools.external.cornerstone = cornerstone;
    cornerstoneTools.external.Hammer = window.Hammer;
    if (cornerstoneMath) {
      cornerstoneTools.external.cornerstoneMath = cornerstoneMath;
    }

    // Configure and register web image loader
    if (cornerstoneWebImageLoader) {
      if (cornerstoneWebImageLoader.external) {
        cornerstoneWebImageLoader.external.cornerstone = cornerstone;
      }
      
      // Create a wrapper that strips the webImage: prefix before calling the loader
      // The cornerstone loader receives full imageId (webImage:https://...) but the 
      // cornerstoneWebImageLoader.loadImage expects just the URL
      var originalLoadImage = cornerstoneWebImageLoader.loadImage || 
                              (cornerstoneWebImageLoader.webImageLoader && cornerstoneWebImageLoader.webImageLoader.loadImage);
      
      if (originalLoadImage) {
        var webImageLoader = function(imageId) {
          // Strip the webImage: prefix to get the actual URL
          var url = imageId;
          if (imageId.indexOf('webImage:') === 0) {
            url = imageId.substring(9); // Remove 'webImage:' (9 chars)
          }
          return originalLoadImage(url);
        };
        cornerstone.registerImageLoader('webImage', webImageLoader);
        console.log("[CaseDicomViewer] Registered webImage loader with prefix stripper");
      } else {
        console.warn("[CaseDicomViewer] Could not find loadImage function in cornerstoneWebImageLoader");
      }
    } else {
      console.warn("[CaseDicomViewer] cornerstoneWebImageLoader not available");
    }

    // Initialize cornerstone-tools
    cornerstoneTools.init({
      showSVGCursors: true,
      globalToolSyncEnabled: false,
    });

    console.log("[CaseDicomViewer] External modules initialized");
    return true;
  }

  /**
   * Convert relative URL to absolute
   */
  function toAbsoluteUrl(url) {
    if (!url) return url;
    if (url.indexOf("http://") === 0 || url.indexOf("https://") === 0) return url;
    var origin = window.location ? window.location.origin : "";
    return origin + (url.indexOf("/") === 0 ? url : "/" + url);
  }

  /**
   * Count how many images in current stack are cached
   */
  function getCachedCount() {
    if (!_imageIds.length) return 0;
    var n = 0;
    for (var i = 0; i < _imageIds.length; i++) {
      if (_preloadedImages[_imageIds[i]]) n++;
    }
    return n;
  }

  /**
   * Preload full stack in background and report progress (for cache indicator).
   * Skips images already in _preloadedImages (global cache per imageId).
   */
  function preloadFullStack() {
    if (!cornerstone || !_element || !_imageIds.length) return;
    var total = _imageIds.length;
    var batchSize = 8;
    var index = 0;
    var sliderReadyFired = false;
    var readyThreshold = Math.max(1, Math.ceil(total * 0.02)); // ~2%

    function reportProgress() {
      var cached = getCachedCount();
      if (_onCacheProgress) _onCacheProgress(cached, total);
      if (!sliderReadyFired && cached >= readyThreshold && _onSliderReady) {
        sliderReadyFired = true;
        _onSliderReady();
      }
      if (cached >= total && _onAllCached) _onAllCached();
    }

    reportProgress();

    function loadNextBatch() {
      var end = Math.min(index + batchSize, total);
      var pending = 0;
      for (var i = index; i < end; i++) {
        var imageId = _imageIds[i];
        if (_preloadedImages[imageId]) continue;
        pending++;
        (function (id) {
          cornerstone.loadImage(id).then(
            function () {
              _preloadedImages[id] = true;
              reportProgress();
              pending--;
              if (pending === 0) scheduleNext();
            },
            function () {
              pending--;
              if (pending === 0) scheduleNext();
            }
          );
        })(imageId);
      }
      if (pending === 0 && end < total) scheduleNext();
      else if (end >= total) reportProgress();
      index = end;
    }

    function scheduleNext() {
      if (index < total) setTimeout(loadNextBatch, 30);
      else reportProgress();
    }

    loadNextBatch();
  }

  /**
   * Preload images in background for smooth scrolling
   */
  function preloadImages(imageIds, priority) {
    if (!cornerstone || !imageIds || !imageIds.length) return;
    
    var loadBatch = function (startIdx, batchSize) {
      for (var i = startIdx; i < Math.min(startIdx + batchSize, imageIds.length); i++) {
        var imageId = imageIds[i];
        if (!_preloadedImages[imageId]) {
          cornerstone.loadImage(imageId).then(
            function (image) {
              _preloadedImages[image.imageId] = true;
            },
            function () { /* Ignore preload errors */ }
          );
        }
      }
      // Continue loading in batches
      if (startIdx + batchSize < imageIds.length) {
        setTimeout(function () {
          loadBatch(startIdx + batchSize, batchSize);
        }, 50);
      }
    };

    // Start preloading in batches of 5
    loadBatch(0, priority ? 10 : 5);
  }

  /**
   * Display a specific slice
   */
  function displaySlice(index) {
    if (!_element || !_imageIds.length || index < 0 || index >= _imageIds.length) return;
    _currentIndex = index;
    var imageId = _imageIds[_currentIndex];

    cornerstone.loadImage(imageId).then(
      function (image) {
        cornerstone.displayImage(_element, image);
        _preloadedImages[imageId] = true;

        // Update stack tool state
        var stackState = cornerstoneTools.getToolState(_element, "stack");
        if (stackState && stackState.data && stackState.data.length) {
          stackState.data[0].currentImageIdIndex = _currentIndex;
        }

        // Notify slice change
        if (_onSliceChange) {
          _onSliceChange(_currentIndex + 1, _imageIds.length);
        }

        // Preload nearby images
        var nearbyIds = [];
        for (var i = Math.max(0, _currentIndex - 5); i <= Math.min(_imageIds.length - 1, _currentIndex + 10); i++) {
          if (i !== _currentIndex) {
            nearbyIds.push(_imageIds[i]);
          }
        }
        preloadImages(nearbyIds, true);
      },
      function (err) {
        console.warn("[CaseDicomViewer] Failed to load image:", imageId, err);
      }
    );
  }

  /**
   * Set up stack for current plan
   */
  function setupStack(imageUrls) {
    if (!_element || !cornerstone) return;

    // Convert URLs to absolute paths with webImage: prefix
    var raw = Array.isArray(imageUrls) ? imageUrls.slice() : [];
    _imageIds = raw.map(function (url) {
      var absUrl = toAbsoluteUrl(url);
      // Add webImage: prefix for cornerstone-web-image-loader
      return absUrl.indexOf("webImage:") === 0 ? absUrl : "webImage:" + absUrl;
    });

    // Clear previous stack state
    var stackState = cornerstoneTools.getToolState(_element, "stack");
    if (stackState && stackState.data) {
      stackState.data = [];
    }

    // Add new stack state
    cornerstoneTools.addStackStateManager(_element, ["stack"]);
    cornerstoneTools.addToolState(_element, "stack", {
      imageIds: _imageIds,
      currentImageIdIndex: 0,
    });

    _currentIndex = 0;
    // Keep _preloadedImages global: do not clear so switching plans reuses cached images

    // Display first image
    if (_imageIds.length) {
      displaySlice(0);
    }
  }

  /**
   * Add viewing tools
   */
  function addTools() {
    if (!cornerstoneTools) return;

    // Stack scroll (mouse wheel)
    cornerstoneTools.addTool(cornerstoneTools.StackScrollMouseWheelTool);
    cornerstoneTools.setToolActive("StackScrollMouseWheel", {});

    // Window/Level (left mouse button)
    cornerstoneTools.addTool(cornerstoneTools.WwwcTool);
    cornerstoneTools.setToolActive("Wwwc", { mouseButtonMask: 1 });

    // Zoom (right mouse button)
    cornerstoneTools.addTool(cornerstoneTools.ZoomTool);
    cornerstoneTools.setToolActive("Zoom", { mouseButtonMask: 2 });

    // Pan (middle mouse button)
    cornerstoneTools.addTool(cornerstoneTools.PanTool);
    cornerstoneTools.setToolActive("Pan", { mouseButtonMask: 4 });

    // Zoom with touch pinch
    cornerstoneTools.addTool(cornerstoneTools.ZoomTouchPinchTool);
    cornerstoneTools.setToolActive("ZoomTouchPinch", {});

    // Pan with touch
    cornerstoneTools.addTool(cornerstoneTools.PanMultiTouchTool);
    cornerstoneTools.setToolActive("PanMultiTouch", {});

    console.log("[CaseDicomViewer] Tools added: StackScrollMouseWheel, Wwwc, Zoom, Pan");
  }

  /**
   * Add annotation tools (admin only)
   */
  function addAnnotationTools() {
    if (!cornerstoneTools || !_isAdmin) return;

    // Arrow annotation
    cornerstoneTools.addTool(cornerstoneTools.ArrowAnnotateTool);

    // Freehand ROI
    cornerstoneTools.addTool(cornerstoneTools.FreehandRoiTool);

    // Text marker
    cornerstoneTools.addTool(cornerstoneTools.TextMarkerTool, {
      configuration: {
        markers: ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"],
        current: "A",
        ascending: true,
        loop: true,
      },
    });

    // Length measurement
    cornerstoneTools.addTool(cornerstoneTools.LengthTool);

    // Elliptical ROI
    cornerstoneTools.addTool(cornerstoneTools.EllipticalRoiTool);

    console.log("[CaseDicomViewer] Annotation tools added for admin");
  }

  /**
   * Set active annotation tool
   */
  function setActiveAnnotationTool(toolName) {
    if (!cornerstoneTools || !_isAdmin) return;

    // Deactivate current viewing tool on left button
    cornerstoneTools.setToolPassive("Wwwc");

    // Activate annotation tool
    cornerstoneTools.setToolActive(toolName, { mouseButtonMask: 1 });
    console.log("[CaseDicomViewer] Active annotation tool:", toolName);
  }

  /**
   * Reset to viewing mode (deactivate annotations)
   */
  function resetToViewingMode() {
    if (!cornerstoneTools) return;

    // Deactivate annotation tools
    var annotationTools = ["ArrowAnnotate", "FreehandRoi", "TextMarker", "Length", "EllipticalRoi"];
    annotationTools.forEach(function (tool) {
      try {
        cornerstoneTools.setToolPassive(tool);
      } catch (e) { /* Tool might not exist */ }
    });

    // Reactivate Wwwc or Pan on left button depending on pan mode
    if (_panModeActive) {
      cornerstoneTools.setToolPassive("Wwwc");
      cornerstoneTools.setToolActive("Pan", { mouseButtonMask: 1 });
    } else {
      cornerstoneTools.setToolPassive("Pan");
      cornerstoneTools.setToolActive("Wwwc", { mouseButtonMask: 1 });
    }
    console.log("[CaseDicomViewer] Reset to viewing mode");
  }

  /**
   * Set pan mode: when true, left-drag pans; when false, left-drag is window/level
   */
  function setPanMode(active) {
    if (!cornerstoneTools) return;
    _panModeActive = !!active;
    cornerstoneTools.setToolPassive("Wwwc");
    cornerstoneTools.setToolPassive("Pan");
    if (_panModeActive) {
      cornerstoneTools.setToolActive("Pan", { mouseButtonMask: 1 });
    } else {
      cornerstoneTools.setToolActive("Wwwc", { mouseButtonMask: 1 });
    }
    console.log("[CaseDicomViewer] Pan mode:", _panModeActive);
  }

  /**
   * Pan viewport by delta (pixels)
   */
  function panBy(dx, dy) {
    if (!_element || !cornerstone) return;
    try {
      var vp = cornerstone.getViewport(_element);
      vp.translation = vp.translation || { x: 0, y: 0 };
      vp.translation.x += dx;
      vp.translation.y += dy;
      cornerstone.setViewport(_element, vp);
    } catch (e) { console.warn("[CaseDicomViewer] panBy:", e); }
  }

  /**
   * Attach keyboard zoom/pan (+, -, arrow keys). Call with element that should receive focus.
   */
  function attachKeyboardNavigation(containerEl) {
    if (_keyboardListener) return;
    var el = containerEl || _element;
    if (!el) return;
    _keyboardContainer = el;
    _keyboardListener = function (e) {
      if (!_element || !cornerstone) return;
      var tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : "";
      if (tag === "input" || tag === "textarea" || tag === "select") return;
      var key = e.key;
      if (key === "+" || key === "=") {
        e.preventDefault();
        window.CaseDicomViewer.zoomIn();
      } else if (key === "-") {
        e.preventDefault();
        window.CaseDicomViewer.zoomOut();
      } else if (key === "ArrowLeft") {
        e.preventDefault();
        panBy(20, 0);
      } else if (key === "ArrowRight") {
        e.preventDefault();
        panBy(-20, 0);
      } else if (key === "ArrowUp") {
        e.preventDefault();
        panBy(0, 20);
      } else if (key === "ArrowDown") {
        e.preventDefault();
        panBy(0, -20);
      }
    };
    el.addEventListener("keydown", _keyboardListener);
    el.setAttribute("tabindex", "0");
    if (el.focus) el.focus();
  }

  function detachKeyboardNavigation(containerEl) {
    var el = containerEl || _keyboardContainer || _element;
    if (el && _keyboardListener) {
      el.removeEventListener("keydown", _keyboardListener);
      _keyboardListener = null;
      _keyboardContainer = null;
    }
  }

  /**
   * Toggle fullscreen on a container (default: viewer parent)
   */
  function toggleFullscreen(containerId) {
    var el = containerId ? document.getElementById(containerId) : (_element && _element.parentElement);
    if (!el) return false;
    if (!document.fullscreenElement) {
      _fullscreenContainer = el;
      el.requestFullscreen && el.requestFullscreen();
      return true;
    } else {
      document.exitFullscreen && document.exitFullscreen();
      _fullscreenContainer = null;
      return false;
    }
  }

  function isFullscreen() {
    return !!(document.fullscreenElement);
  }

  /**
   * Resize Cornerstone viewport (call after fullscreen change or container resize)
   */
  function resizeViewport() {
    if (!_element || !cornerstone) return;
    try {
      cornerstone.resize(_element);
    } catch (e) {
      console.warn("[CaseDicomViewer] resize:", e);
    }
  }

  var _fullscreenChangeHandler = null;

  function attachFullscreenResize(containerEl) {
    if (_fullscreenChangeHandler) return;
    _fullscreenChangeHandler = function () {
      if (!document.fullscreenElement) {
        _fullscreenContainer = null;
      }
      resizeViewport();
      setTimeout(resizeViewport, 50);
      setTimeout(resizeViewport, 150);
      setTimeout(resizeViewport, 400);
      if (document.fullscreenElement) {
        setTimeout(resizeViewport, 100);
        setTimeout(resizeViewport, 300);
      }
    };
    document.addEventListener("fullscreenchange", _fullscreenChangeHandler);
    document.addEventListener("webkitfullscreenchange", _fullscreenChangeHandler);
  }

  function detachFullscreenResize() {
    if (!_fullscreenChangeHandler) return;
    document.removeEventListener("fullscreenchange", _fullscreenChangeHandler);
    document.removeEventListener("webkitfullscreenchange", _fullscreenChangeHandler);
    _fullscreenChangeHandler = null;
  }

  /**
   * Get all annotations for current image
   */
  function getAnnotationsForImage() {
    if (!_element || !cornerstoneTools) return [];

    var annotations = [];
    var toolTypes = ["ArrowAnnotate", "FreehandRoi", "TextMarker", "Length", "EllipticalRoi"];

    toolTypes.forEach(function (toolType) {
      var state = cornerstoneTools.getToolState(_element, toolType);
      if (state && state.data && state.data.length) {
        state.data.forEach(function (data) {
          annotations.push({
            toolType: toolType,
            data: JSON.parse(JSON.stringify(data)), // Deep copy
          });
        });
      }
    });

    return annotations;
  }

  /**
   * Export all annotations for saving
   */
  function exportAnnotations() {
    var result = {};
    
    if (_currentPlan && _imageIds.length) {
      if (!result[_currentPlan]) {
        result[_currentPlan] = {};
      }
      var annotations = getAnnotationsForImage();
      if (annotations.length) {
        result[_currentPlan][_currentIndex] = annotations;
      }
    }

    return result;
  }

  /**
   * Load annotations from saved data
   */
  function loadAnnotations(annotationData) {
    _annotations = annotationData || {};
    console.log("[CaseDicomViewer] Annotations loaded");
  }

  /**
   * Apply annotations for current image
   */
  function applyAnnotationsForImage() {
    if (!_element || !cornerstoneTools || !_currentPlan) return;

    var planAnnotations = _annotations[_currentPlan];
    if (!planAnnotations) return;

    var imageAnnotations = planAnnotations[_currentIndex];
    if (!imageAnnotations || !imageAnnotations.length) return;

    imageAnnotations.forEach(function (ann) {
      try {
        cornerstoneTools.addToolState(_element, ann.toolType, ann.data);
      } catch (e) {
        console.warn("[CaseDicomViewer] Failed to apply annotation:", e);
      }
    });

    cornerstone.updateImage(_element);
    console.log("[CaseDicomViewer] Applied", imageAnnotations.length, "annotations for image", _currentIndex);
  }

  /**
   * Clear all annotations from current image
   */
  function clearAnnotations() {
    if (!_element || !cornerstoneTools) return;

    var toolTypes = ["ArrowAnnotate", "FreehandRoi", "TextMarker", "Length", "EllipticalRoi"];
    toolTypes.forEach(function (toolType) {
      cornerstoneTools.clearToolState(_element, toolType);
    });

    cornerstone.updateImage(_element);
    console.log("[CaseDicomViewer] Annotations cleared");
  }

  // Public API
  window.CaseDicomViewer = {
    /**
     * Initialize the viewer
     * @param {string} containerId - DOM element ID for the viewer
     * @param {object} stackConfig - { planName: [imageUrls] }
     * @param {object} options - { isAdmin: boolean, annotations: object }
     * @returns {boolean} - true if Cornerstone initialized, false for fallback
     */
    init: function (containerId, stackConfig, options) {
      options = options || {};
      _isAdmin = options.isAdmin || false;

      // Initialize external modules
      if (!initExternalModules()) {
        console.log("[CaseDicomViewer] Falling back to img viewer");
        return false;
      }

      var el = document.getElementById(containerId);
      if (!el) {
        console.warn("[CaseDicomViewer] Container not found:", containerId);
        return false;
      }

      // Clean up previous viewer
      this.destroy();

      _element = el;
      _stackConfig = stackConfig || {};

      // Get first plan
      var planNames = Object.keys(_stackConfig);
      if (!planNames.length) {
        console.warn("[CaseDicomViewer] No plans in stack config");
        return false;
      }

      _currentPlan = planNames[0];
      var urls = _stackConfig[_currentPlan] || [];

      if (!urls.length) {
        console.warn("[CaseDicomViewer] No images in plan:", _currentPlan);
        return false;
      }

      try {
        // Enable cornerstone on element
        el.style.display = "";
        cornerstone.enable(el);

        // Add tools
        addTools();
        if (_isAdmin) {
          addAnnotationTools();
        }

        // Load annotations if provided
        if (options.annotations) {
          loadAnnotations(options.annotations);
        }

        // Set up stack
        setupStack(urls);

        // Start full-stack preload in background (reports progress for cache indicator)
        setTimeout(function () {
          preloadFullStack();
        }, 800);

        // Update slice counter whenever an image is rendered (covers wheel scroll and any navigation)
        function syncSliceCounter() {
          var stackState = cornerstoneTools.getToolState(_element, "stack");
          if (stackState && stackState.data && stackState.data[0]) {
            var idx = stackState.data[0].currentImageIdIndex;
            if (typeof idx === "number" && idx >= 0 && idx < _imageIds.length) {
              _currentIndex = idx;
              if (_onSliceChange) {
                _onSliceChange(_currentIndex + 1, _imageIds.length);
              }
            }
          }
        }

        el.addEventListener("cornerstoneimagerendered", function () {
          syncSliceCounter();
        });

        // Listen for stack scroll events (v4 may use different property names)
        el.addEventListener("cornerstonestackscroll", function (e) {
          var eventData = e.detail || {};
          var idx = eventData.newImageIdIndex ?? eventData.imageIdIndex ?? eventData.newIndex;
          if (typeof idx === "number" && idx >= 0 && idx < _imageIds.length) {
            _currentIndex = idx;
            if (_onSliceChange) {
              _onSliceChange(_currentIndex + 1, _imageIds.length);
            }
          } else {
            syncSliceCounter();
          }
        });

        attachFullscreenResize(el.parentElement || el);
        console.log("[CaseDicomViewer] Initialized with", urls.length, "images in plan:", _currentPlan);
        return true;
      } catch (e) {
        console.error("[CaseDicomViewer] Init failed:", e);
        this.destroy();
        return false;
      }
    },

    /**
     * Switch to a different plan. Preserves global image cache; starts preload for new plan.
     */
    loadStack: function (planName, imageUrls) {
      if (!_element || !cornerstone) return;
      _currentPlan = planName;
      setupStack(imageUrls || _stackConfig[planName] || []);
      // Report cache progress for current plan and preload remaining images
      setTimeout(function () { preloadFullStack(); }, 100);
    },

    /**
     * Start background preload for current stack (e.g. after plan switch). Safe to call multiple times.
     */
    startPreload: function () {
      preloadFullStack();
    },

    /**
     * Navigate to specific slice
     */
    setSliceIndex: function (index) {
      if (!_imageIds.length) return;
      var i = Math.max(0, Math.min(index, _imageIds.length - 1));
      displaySlice(i);
    },

    /**
     * Get current slice index (0-based)
     */
    getCurrentIndex: function () {
      return _currentIndex;
    },

    /**
     * Get total image count
     */
    getImageCount: function () {
      return _imageIds.length;
    },

    /**
     * Register slice change callback
     */
    onSliceChange: function (cb) {
      _onSliceChange = typeof cb === "function" ? cb : null;
    },

    /**
     * Set active annotation tool (admin only)
     */
    setAnnotationTool: function (toolName) {
      setActiveAnnotationTool(toolName);
    },

    /**
     * Reset to viewing mode
     */
    resetToViewingMode: function () {
      resetToViewingMode();
    },

    /**
     * Get annotations for saving
     */
    getAnnotations: function () {
      return exportAnnotations();
    },

    /**
     * Clear all annotations
     */
    clearAnnotations: function () {
      clearAnnotations();
    },

    /**
     * Reset view (zoom, pan, window/level)
     */
    resetView: function () {
      if (!_element || !cornerstone) return;
      cornerstone.reset(_element);
    },

    /**
     * Fit image to viewport
     */
    fitToWindow: function () {
      if (!_element || !cornerstone) return;
      cornerstone.fitToWindow(_element);
    },

    /**
     * Toggle pan mode (left-drag pans when true, window/level when false)
     */
    setPanMode: function (active) {
      setPanMode(active);
    },

    /**
     * Pan viewport by delta (pixels)
     */
    panBy: function (dx, dy) {
      panBy(dx, dy);
    },

    /**
     * Attach keyboard zoom/pan to a container (+, -, arrows). Pass container element or id.
     */
    attachKeyboard: function (containerElOrId) {
      var el = typeof containerElOrId === "string" ? document.getElementById(containerElOrId) : containerElOrId;
      attachKeyboardNavigation(el);
    },

    /**
     * Toggle fullscreen for viewer container. Pass optional container element id.
     */
    toggleFullscreen: function (containerId) {
      return toggleFullscreen(containerId);
    },

    isFullscreen: function () {
      return isFullscreen();
    },

    /**
     * Resize viewport (e.g. after fullscreen or container size change)
     */
    resize: function () {
      resizeViewport();
    },

    /**
     * Zoom in (scale *= 1.25)
     */
    zoomIn: function () {
      if (!_element || !cornerstone) return;
      try {
        var vp = cornerstone.getViewport(_element);
        vp.scale = (vp.scale || 1) * 1.25;
        if (vp.scale > 50) vp.scale = 50;
        cornerstone.setViewport(_element, vp);
      } catch (e) {
        console.warn("[CaseDicomViewer] zoomIn:", e);
      }
    },

    /**
     * Zoom out (scale /= 1.25)
     */
    zoomOut: function () {
      if (!_element || !cornerstone) return;
      try {
        var vp = cornerstone.getViewport(_element);
        vp.scale = (vp.scale || 1) / 1.25;
        if (vp.scale < 0.1) vp.scale = 0.1;
        cornerstone.setViewport(_element, vp);
      } catch (e) {
        console.warn("[CaseDicomViewer] zoomOut:", e);
      }
    },

    /**
     * Cache progress: get cached count (for UI indicator)
     */
    getCachedCount: function () {
      return getCachedCount();
    },

    /**
     * Register cache progress callback (cached, total)
     */
    onCacheProgress: function (cb) {
      _onCacheProgress = typeof cb === "function" ? cb : null;
    },

    /**
     * Register callback when all images in stack are cached
     */
    onAllCached: function (cb) {
      _onAllCached = typeof cb === "function" ? cb : null;
    },

    /**
     * Register callback when slider can be used (e.g. ~2% of current stack cached)
     */
    onSliderReady: function (cb) {
      _onSliderReady = typeof cb === "function" ? cb : null;
    },

    /**
     * Clean up viewer
     */
    destroy: function () {
      detachFullscreenResize();
      detachKeyboardNavigation();
      if (_element && cornerstone) {
        try {
          cornerstone.disable(_element);
        } catch (e) {
          console.warn("[CaseDicomViewer] Destroy error:", e);
        }
        _element = null;
      }
      _fullscreenContainer = null;
      _keyboardListener = null;
      _keyboardContainer = null;
      _panModeActive = false;
      _stackConfig = null;
      _currentPlan = null;
      _currentIndex = 0;
      _imageIds = [];
      _onSliceChange = null;
      _onCacheProgress = null;
      _onAllCached = null;
      _onSliderReady = null;
      _annotations = {};
      _preloadedImages = {};
    },

    /**
     * Check if viewer is active
     */
    isActive: function () {
      return _element !== null;
    },

    /**
     * Check if admin mode
     */
    isAdmin: function () {
      return _isAdmin;
    },
  };

  console.log("[CaseDicomViewer] viewer.js v10 loaded (slider at 2%%, global cache, cache indicator per plan)");
})();
