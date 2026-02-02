/**
 * Case DICOM Viewer - Cornerstone.js v4.x Integration
 * Features: Stack scroll (mouse wheel), zoom, pan, window/level, annotations
 * Self-hosted libraries for reliable API compatibility
 * v4: Full Cornerstone v4.x integration with annotations support
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
  var _isAdmin = false;
  var _annotations = {}; // { planName: { imageIndex: [annotations] } }
  var _preloadedImages = {};

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

    // Configure web image loader
    if (cornerstoneWebImageLoader && cornerstoneWebImageLoader.external) {
      cornerstoneWebImageLoader.external.cornerstone = cornerstone;
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
    _preloadedImages = {};

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

    // Reactivate Wwwc on left button
    cornerstoneTools.setToolActive("Wwwc", { mouseButtonMask: 1 });
    console.log("[CaseDicomViewer] Reset to viewing mode");
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

        // Listen for image rendered to apply annotations
        el.addEventListener("cornerstoneimagerendered", function () {
          // Apply any saved annotations for this image
          // Note: This would need debouncing for production
        });

        // Listen for scroll events to update slice counter
        el.addEventListener("cornerstonestackscroll", function (e) {
          var eventData = e.detail;
          if (eventData && typeof eventData.newImageIdIndex !== "undefined") {
            _currentIndex = eventData.newImageIdIndex;
            if (_onSliceChange) {
              _onSliceChange(_currentIndex + 1, _imageIds.length);
            }
          }
        });

        console.log("[CaseDicomViewer] Initialized with", urls.length, "images in plan:", _currentPlan);
        return true;
      } catch (e) {
        console.error("[CaseDicomViewer] Init failed:", e);
        this.destroy();
        return false;
      }
    },

    /**
     * Switch to a different plan
     */
    loadStack: function (planName, imageUrls) {
      if (!_element || !cornerstone) return;
      _currentPlan = planName;
      setupStack(imageUrls || _stackConfig[planName] || []);
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
     * Clean up viewer
     */
    destroy: function () {
      if (_element && cornerstone) {
        try {
          cornerstone.disable(_element);
        } catch (e) {
          console.warn("[CaseDicomViewer] Destroy error:", e);
        }
        _element = null;
      }
      _stackConfig = null;
      _currentPlan = null;
      _currentIndex = 0;
      _imageIds = [];
      _onSliceChange = null;
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

  console.log("[CaseDicomViewer] viewer.js v4 loaded (self-hosted Cornerstone)");
})();
