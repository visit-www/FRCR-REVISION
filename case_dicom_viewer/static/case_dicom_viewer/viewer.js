/**
 * Case DICOM Viewer - Cornerstone.js v4.x Integration
 * Features: Stack scroll (mouse wheel), zoom, pan, window/level, annotations
 * v15: Register annotation tools for all users; read-only rendering for students
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
  var _annotationsVisible = true;
  var _preloadedImages = {};
  var _preloadRunId = 0;
  var _panModeActive = false;
  var _lastAnnotationIndex = -1; // Tracks last image index where annotations were applied/cleared
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

    // Set Cornerstone image cache to 2GB for session-long retention of multiple plans
    try {
      if (cornerstone.imageLoader && cornerstone.imageLoader.imageCache) {
        var cache = cornerstone.imageLoader.imageCache;
        if (typeof cache.setMaximumSizeBytes === 'function') {
          cache.setMaximumSizeBytes(2 * 1024 * 1024 * 1024);
          console.log("[CaseDicomViewer] Image cache set to 2GB");
        }
      }
    } catch (e) {
      console.warn("[CaseDicomViewer] Could not set image cache size:", e);
    }

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
   * Build center-first index order: center slice first, then center±1, center±2, etc.
   * Slices with anatomy (typically toward center) load before black/empty edge slices.
   */
  function centerFirstOrder(total) {
    var order = [];
    var center = Math.floor((total - 1) / 2);
    order.push(center);
    for (var d = 1; d <= Math.max(center, total - 1 - center); d++) {
      if (center - d >= 0) order.push(center - d);
      if (center + d < total) order.push(center + d);
    }
    return order;
  }

  /**
   * Preload full stack in background and report progress (for cache indicator).
   * Uses center-first order so slices with anatomy load before black edge slices.
   * Skips images already in _preloadedImages (global cache per imageId).
   * Ignores results if user switched plan (runId check).
   */
  function preloadFullStack() {
    if (!cornerstone || !_element || !_imageIds.length) return;
    var runId = _preloadRunId;
    var total = _imageIds.length;
    var order = centerFirstOrder(total);
    var batchSize = 4;
    var orderIndex = 0;
    var sliderReadyFired = false;
    var readyThreshold = Math.max(1, Math.ceil(total * 0.02)); // ~2%

    function reportProgress() {
      if (runId !== _preloadRunId) return;
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
      if (runId !== _preloadRunId) return;
      var end = Math.min(orderIndex + batchSize, order.length);
      var pending = 0;
      for (var j = orderIndex; j < end; j++) {
        var i = order[j];
        var imageId = _imageIds[i];
        if (_preloadedImages[imageId]) continue;
        pending++;
        (function (id) {
          cornerstone.loadImage(id).then(
            function () {
              if (runId !== _preloadRunId) return;
              _preloadedImages[id] = true;
              reportProgress();
              pending--;
              if (pending === 0) scheduleNext();
            },
            function () {
              if (runId !== _preloadRunId) return;
              pending--;
              if (pending === 0) scheduleNext();
            }
          );
        })(imageId);
      }
      if (pending === 0 && end < order.length) scheduleNext();
      else if (end >= order.length) reportProgress();
      orderIndex = end;
    }

    function scheduleNext() {
      if (runId !== _preloadRunId) return;
      if (orderIndex < order.length) setTimeout(loadNextBatch, 150);
      else reportProgress();
    }

    loadNextBatch();
  }

  /**
   * Preload images in background for smooth scrolling.
   * Ignores results if user switched plan (runId check).
   */
  function preloadImages(imageIds, priority) {
    if (!cornerstone || !imageIds || !imageIds.length) return;
    var runId = _preloadRunId;

    var loadBatch = function (startIdx, batchSize) {
      if (runId !== _preloadRunId) return;
      for (var i = startIdx; i < Math.min(startIdx + batchSize, imageIds.length); i++) {
        var imageId = imageIds[i];
        if (!_preloadedImages[imageId]) {
          cornerstone.loadImage(imageId).then(
            function (image) {
              if (runId !== _preloadRunId) return;
              _preloadedImages[image.imageId] = true;
            },
            function () { /* Ignore preload errors */ }
          );
        }
      }
      if (runId !== _preloadRunId) return;
      if (startIdx + batchSize < imageIds.length) {
        setTimeout(function () {
          loadBatch(startIdx + batchSize, batchSize);
        }, 50);
      }
    };

    loadBatch(0, priority ? 10 : 5);
  }

  /**
   * Display a specific slice
   */
  function displaySlice(index) {
    if (!_element || !_imageIds.length || index < 0 || index >= _imageIds.length) return;

    // Save admin annotations from previous image before switching
    if (_isAdmin && _lastAnnotationIndex >= 0 && _lastAnnotationIndex !== index && _annotationsVisible) {
      saveCurrentAnnotationsToCache(_lastAnnotationIndex);
    }

    _currentIndex = index;
    var imageId = _imageIds[_currentIndex];

    cornerstone.loadImage(imageId).then(
      function (image) {
        // Update stack tool state
        var stackState = cornerstoneTools.getToolState(_element, "stack");
        if (stackState && stackState.data && stackState.data.length) {
          stackState.data[0].currentImageIdIndex = _currentIndex;
        }

        cornerstone.displayImage(_element, image);
        _preloadedImages[imageId] = true;

        // Apply annotations for this image
        _lastAnnotationIndex = _currentIndex;
        if (_annotationsVisible) {
          applyAnnotationsForImage();
        } else {
          clearAnnotations();
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

    _preloadRunId += 1;

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
    _lastAnnotationIndex = -1;
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
   * Add annotation tools. For admin: tools can be activated for drawing.
   * For students: tools are set to "enabled" (render-only, no interaction).
   */
  function addAnnotationTools() {
    if (!cornerstoneTools) return;

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

    // For non-admin: enable tools for rendering only (students see saved annotations)
    if (!_isAdmin) {
      var readOnlyTools = ["ArrowAnnotate", "FreehandRoi", "TextMarker", "Length", "EllipticalRoi"];
      readOnlyTools.forEach(function (tool) {
        cornerstoneTools.setToolEnabled(tool);
      });
    }

    console.log("[CaseDicomViewer] Annotation tools added" + (_isAdmin ? " for admin" : " (read-only)"));
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
   * Attach keyboard: Z=zoom, P=pan, W=window, Page Up/Down=scroll, Numpad Left/Right=plan.
   * Call with element that should receive focus (e.g. viewer wrapper).
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
      var loc = e.location;
      /* Change series/plan: Numpad Left/Right (location 3) or Ctrl+Arrow Left/Right */
      var numpadLeft = (key === "ArrowLeft" || key === "Left") && (loc === 3 || e.ctrlKey);
      var numpadRight = (key === "ArrowRight" || key === "Right") && (loc === 3 || e.ctrlKey);
      if (numpadLeft) {
        e.preventDefault();
        document.dispatchEvent(new CustomEvent("caseDicomViewerPrevPlan"));
        return;
      }
      if (numpadRight) {
        e.preventDefault();
        document.dispatchEvent(new CustomEvent("caseDicomViewerNextPlan"));
        return;
      }
      /* Z = zoom (fit to window), P = pan mode, W = window/level mode */
      if (key === "z" || key === "Z") {
        e.preventDefault();
        if (window.CaseDicomViewer) window.CaseDicomViewer.fitToWindow();
        return;
      }
      if (key === "p" || key === "P") {
        e.preventDefault();
        e.stopPropagation();
        if (window.CaseDicomViewer) window.CaseDicomViewer.setPanMode(true);
        return;
      }
      if (key === "w" || key === "W") {
        e.preventDefault();
        if (window.CaseDicomViewer) window.CaseDicomViewer.setPanMode(false);
        return;
      }
      /* Page Down / Page Up = scroll slices */
      if (key === "PageDown") {
        e.preventDefault();
        if (_imageIds.length && _currentIndex < _imageIds.length - 1) {
          displaySlice(_currentIndex + 1);
        }
        return;
      }
      if (key === "PageUp") {
        e.preventDefault();
        if (_imageIds.length && _currentIndex > 0) {
          displaySlice(_currentIndex - 1);
        }
        return;
      }
      /* + / - = zoom in/out */
      if (key === "+" || key === "=") {
        e.preventDefault();
        if (window.CaseDicomViewer) window.CaseDicomViewer.zoomIn();
        return;
      }
      if (key === "-") {
        e.preventDefault();
        if (window.CaseDicomViewer) window.CaseDicomViewer.zoomOut();
        return;
      }
      /* Arrow keys (non-numpad) = pan */
      if (key === "ArrowLeft") {
        e.preventDefault();
        panBy(20, 0);
        return;
      }
      if (key === "ArrowRight") {
        e.preventDefault();
        panBy(-20, 0);
        return;
      }
      if (key === "ArrowUp") {
        e.preventDefault();
        panBy(0, 20);
        return;
      }
      if (key === "ArrowDown") {
        e.preventDefault();
        panBy(0, -20);
        return;
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
   * Resize Cornerstone viewport (call after fullscreen change or container resize).
   * Cornerstone reads the viewport element's offsetWidth/offsetHeight and resizes
   * the canvas.cornerstone-canvas to match. If the viewport hasn't been laid out
   * yet (e.g. right after fullscreen enter), the canvas stays small.
   */
  function resizeViewport() {
    if (!_element || !cornerstone) return;
    try {
      cornerstone.resize(_element);
    } catch (e) {
      console.warn("[CaseDicomViewer] resize:", e);
    }
  }

  /**
   * Force viewport (and thus canvas) to match wrapper size in pixels, then resize.
   * Used when not in fullscreen (e.g. window resize).
   */
  function resizeViewportToWrapper() {
    if (!_element || !cornerstone) return;
    var wrapperEl = document.getElementById("imageStackViewerWrapper");
    if (!wrapperEl) {
      resizeViewport();
      return;
    }
    var w = wrapperEl.clientWidth;
    var h = wrapperEl.clientHeight;
    if (w > 0 && h > 0) {
      _element.style.width = w + "px";
      _element.style.height = h + "px";
    }
    resizeViewport();
  }

  var _fullscreenChangeHandler = null;

  function attachFullscreenResize(containerEl) {
    if (_fullscreenChangeHandler) return;
    var wrapperEl = document.getElementById("imageStackViewerWrapper");
    var exitFullscreenBtn = document.getElementById("imageStackExitFullscreenBtn");
    _fullscreenChangeHandler = function () {
      var exited = !document.fullscreenElement;
      if (exited) {
        _fullscreenContainer = null;
        if (exitFullscreenBtn) exitFullscreenBtn.style.display = "none";
        var planOverlay = document.getElementById("imageStackFullscreenPlanOverlay");
        var toolbarOverlay = document.getElementById("imageStackFullscreenOverlay");
        if (planOverlay) {
          planOverlay.style.display = "none";
          planOverlay.classList.remove("image-stack-fullscreen-overlay-visible");
          planOverlay.classList.add("d-none");
        }
        if (toolbarOverlay) {
          toolbarOverlay.style.display = "none";
          toolbarOverlay.classList.remove("image-stack-fullscreen-overlay-visible");
          toolbarOverlay.classList.add("d-none");
        }
        if (wrapperEl) {
          wrapperEl.style.width = "";
          wrapperEl.style.height = "";
          wrapperEl.style.maxWidth = "";
        }
        if (_element) {
          _element.style.width = "";
          _element.style.height = "";
        }
        requestAnimationFrame(function () {
          requestAnimationFrame(function () {
            resizeViewport();
            setTimeout(resizeViewport, 150);
            setTimeout(resizeViewport, 400);
          });
        });
      } else {
        /* Fullscreen: show top-left plan overlay and bottom toolbar overlay */
        if (exitFullscreenBtn) exitFullscreenBtn.style.display = "block";
        var planOverlay = document.getElementById("imageStackFullscreenPlanOverlay");
        var toolbarOverlay = document.getElementById("imageStackFullscreenOverlay");
        if (planOverlay) {
          planOverlay.classList.remove("d-none");
          planOverlay.classList.add("image-stack-fullscreen-overlay-visible");
          planOverlay.style.display = "flex";
        }
        if (toolbarOverlay) {
          toolbarOverlay.classList.remove("d-none");
          toolbarOverlay.classList.add("image-stack-fullscreen-overlay-visible");
          toolbarOverlay.style.display = "flex";
        }
        requestAnimationFrame(function () {
          requestAnimationFrame(function () {
            resizeViewportToWrapper();
            setTimeout(resizeViewportToWrapper, 50);
            setTimeout(resizeViewportToWrapper, 150);
          });
        });
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
    // Deep-copy existing annotations to preserve all images/plans
    var result = {};
    for (var plan in _annotations) {
      result[plan] = {};
      for (var idx in _annotations[plan]) {
        result[plan][idx] = _annotations[plan][idx];
      }
    }

    // Update current image's annotations from live cornerstone state
    if (_currentPlan && _imageIds.length) {
      if (!result[_currentPlan]) {
        result[_currentPlan] = {};
      }
      var annotations = getAnnotationsForImage();
      if (annotations.length) {
        result[_currentPlan][_currentIndex] = annotations;
      } else {
        delete result[_currentPlan][_currentIndex];
      }
      // Clean up empty plan
      if (Object.keys(result[_currentPlan]).length === 0) {
        delete result[_currentPlan];
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

    // Clear existing annotations from element first (prevents stale annotations persisting)
    var toolTypes = ["ArrowAnnotate", "FreehandRoi", "TextMarker", "Length", "EllipticalRoi"];
    toolTypes.forEach(function (toolType) {
      cornerstoneTools.clearToolState(_element, toolType);
    });

    var planAnnotations = _annotations[_currentPlan];
    // Fallback: if plan name doesn't match but there's only one plan in annotations, use it
    if (!planAnnotations) {
      var annKeys = Object.keys(_annotations);
      if (annKeys.length === 1) {
        planAnnotations = _annotations[annKeys[0]];
      }
    }
    if (!planAnnotations) {
      cornerstone.updateImage(_element);
      return;
    }

    var imageAnnotations = planAnnotations[_currentIndex];
    if (!imageAnnotations || !imageAnnotations.length) {
      cornerstone.updateImage(_element);
      return;
    }

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

  /**
   * Save current image's live cornerstone tool state into _annotations cache.
   * Called before switching images so admin-drawn annotations are preserved.
   */
  function saveCurrentAnnotationsToCache(indexOverride) {
    if (!_element || !cornerstoneTools || !_currentPlan) return;
    var idx = (typeof indexOverride === "number") ? indexOverride : _currentIndex;
    var annotations = getAnnotationsForImage();
    if (!_annotations[_currentPlan]) _annotations[_currentPlan] = {};
    if (annotations.length) {
      _annotations[_currentPlan][idx] = annotations;
    } else {
      delete _annotations[_currentPlan][idx];
    }
  }

  /**
   * Handle image index change: save previous annotations, clear old, apply new.
   * Called from cornerstoneimagerendered to handle both displaySlice() and mouse wheel scroll.
   * Uses _lastAnnotationIndex guard to prevent re-entrant calls from cornerstone.updateImage().
   */
  function handleImageChanged() {
    if (_currentIndex === _lastAnnotationIndex) return;

    // Save annotations from previous image (still in tool state until we clear)
    if (_isAdmin && _lastAnnotationIndex >= 0 && _currentPlan && _annotationsVisible) {
      saveCurrentAnnotationsToCache(_lastAnnotationIndex);
    }

    _lastAnnotationIndex = _currentIndex;

    // Apply annotations for new image (clears old ones first internally)
    if (_annotationsVisible) {
      applyAnnotationsForImage();
    } else {
      clearAnnotations();
    }
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
        addAnnotationTools();

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

        // Listen for stack scroll events — handle annotations for mouse wheel navigation
        el.addEventListener("cornerstonestackscroll", function (e) {
          var eventData = e.detail || {};
          var idx = eventData.newImageIdIndex ?? eventData.imageIdIndex ?? eventData.newIndex;
          if (typeof idx === "number" && idx >= 0 && idx < _imageIds.length) {
            // Save admin annotations from previous image
            if (_isAdmin && _lastAnnotationIndex >= 0 && _lastAnnotationIndex !== idx && _annotationsVisible) {
              saveCurrentAnnotationsToCache(_lastAnnotationIndex);
            }
            _currentIndex = idx;
            _lastAnnotationIndex = idx;
            // Apply annotations for new image
            if (_annotationsVisible) {
              applyAnnotationsForImage();
            } else {
              clearAnnotations();
            }
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
      // Report cache progress for current plan and preload remaining images (minimal delay for responsive plan switch)
      setTimeout(function () { preloadFullStack(); }, 50);
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
     * Show or hide annotations (student toggle; does not delete data)
     */
    setAnnotationsVisible: function (visible) {
      var wasVisible = _annotationsVisible;
      _annotationsVisible = !!visible;
      // Save current annotations before clearing (admin workflow)
      if (wasVisible && !visible && _isAdmin) {
        saveCurrentAnnotationsToCache();
      }
      _lastAnnotationIndex = -1; // Force re-apply on next render
      if (_element && _imageIds.length) displaySlice(_currentIndex);
    },

    toggleAnnotationsVisible: function () {
      // Save current annotations before toggling off (admin workflow)
      if (_annotationsVisible && _isAdmin) {
        saveCurrentAnnotationsToCache();
      }
      _annotationsVisible = !_annotationsVisible;
      _lastAnnotationIndex = -1; // Force re-apply on next render
      if (_element && _imageIds.length) displaySlice(_currentIndex);
      return _annotationsVisible;
    },

    getAnnotationsVisible: function () {
      return _annotationsVisible;
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
      try {
        document.dispatchEvent(new CustomEvent("caseDicomViewerPanModeChange", { detail: { active: !!active } }));
      } catch (err) {}
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
      _lastAnnotationIndex = -1;
      _preloadedImages = {};
      _preloadRunId = 0;
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

  console.log("[CaseDicomViewer] viewer.js v15 loaded (annotation tools for all users)");
})();
