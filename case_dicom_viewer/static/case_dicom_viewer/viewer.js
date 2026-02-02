/**
 * Case DICOM Viewer - Cornerstone stack (2D) integration
 * Plan tabs, stack scroll (mouse wheel), zoom, pan. Uses proxy URLs for CORS.
 */
(function () {
  "use strict";

  var cornerstone = typeof window.cornerstone !== "undefined" ? window.cornerstone : null;
  var cornerstoneTools = typeof window.cornerstoneTools !== "undefined" ? window.cornerstoneTools : null;
  var cornerstoneWebImageLoader = typeof window.cornerstoneWebImageLoader !== "undefined" ? window.cornerstoneWebImageLoader : null;

  var _element = null;
  var _stackConfig = null;
  var _currentPlan = null;
  var _currentIndex = 0;
  var _imageIds = [];
  var _onSliceChange = null;

  function configured() {
    if (!cornerstone || !cornerstoneTools) return false;
    if (cornerstoneWebImageLoader && cornerstoneWebImageLoader.external) {
      cornerstoneWebImageLoader.external.cornerstone = cornerstone;
    }
    return true;
  }

  function ensureStackState() {
    if (!_element || !cornerstoneTools) return;
    try {
      var hasManager = cornerstoneTools.getToolState(_element, "stack") !== undefined;
      if (!hasManager) cornerstoneTools.addStackStateManager(_element, ["stack"]);
    } catch (e) {
      console.warn("[CaseDicomViewer] ensureStackState", e);
    }
  }

  function displaySlice(index) {
    if (!_element || !_imageIds.length || index < 0 || index >= _imageIds.length) return;
    _currentIndex = index;
    var imageId = _imageIds[_currentIndex];
    cornerstone.loadImage(imageId).then(
      function (image) {
        cornerstone.displayImage(_element, image);
        if (_onSliceChange) _onSliceChange(_currentIndex + 1, _imageIds.length);
      },
      function (err) {
        console.warn("[CaseDicomViewer] loadImage failed", imageId, err);
      }
    );
  }

  function toAbsoluteUrl(url) {
    if (!url) return url;
    if (url.indexOf("http://") === 0 || url.indexOf("https://") === 0) return url;
    var origin = (typeof window !== "undefined" && window.location && window.location.origin) ? window.location.origin : "";
    return origin + (url.indexOf("/") === 0 ? url : "/" + url);
  }

  function setStack(imageUrls) {
    if (!_element || !cornerstone) return;
    var raw = Array.isArray(imageUrls) ? imageUrls.slice() : [];
    _imageIds = raw.map(toAbsoluteUrl);
    ensureStackState();
    cornerstoneTools.addToolState(_element, "stack", {
      imageIds: _imageIds,
      currentImageIdIndex: 0,
    });
    _currentIndex = 0;
    if (_imageIds.length) displaySlice(0);
  }

  window.CaseDicomViewer = {
    init: function (containerId, stackConfig) {
      if (!configured()) {
        console.log("[CaseDicomViewer] Cornerstone not available; using img fallback");
        return false;
      }
      var el = document.getElementById(containerId);
      if (!el) return false;
      this.destroy();
      _element = el;
      _stackConfig = stackConfig || {};
      var planNames = Object.keys(_stackConfig);
      _currentPlan = planNames[0];
      var urls = _stackConfig[_currentPlan];
      if (urls && urls.length) {
        el.style.display = "";
        var imgEl = document.getElementById("imageStackImg");
        if (imgEl) imgEl.style.display = "none";
        cornerstone.enable(el, { renderer: "canvas" });
        cornerstoneTools.mouseInputTool.enable(el);
        cornerstoneTools.touchInputTool.enable(el);
        cornerstoneTools.addTool(cornerstoneTools.StackScrollMouseWheelTool);
        cornerstoneTools.addTool(cornerstoneTools.ZoomTool);
        cornerstoneTools.addTool(cornerstoneTools.PanTool);
        cornerstoneTools.addTool(cornerstoneTools.WwwcTool);
        cornerstoneTools.setToolActive("StackScrollMouseWheel", {});
        cornerstoneTools.setToolActive("Zoom", { mouseButtonMask: 2 });
        cornerstoneTools.setToolActive("Pan", { mouseButtonMask: 4 });
        cornerstoneTools.setToolActive("Wwwc", { mouseButtonMask: 1 });
        setStack(urls);
      }
      return true;
    },

    loadStack: function (planName, imageUrls) {
      if (!_element || !cornerstone) return;
      _currentPlan = planName;
      setStack(imageUrls);
    },

    setSliceIndex: function (index) {
      if (!_imageIds.length) return;
      var i = Math.max(0, Math.min(index, _imageIds.length - 1));
      ensureStackState();
      var state = cornerstoneTools.getToolState(_element, "stack");
      if (state && state.data && state.data[0]) {
        state.data[0].currentImageIdIndex = i;
      }
      displaySlice(i);
    },

    getCurrentIndex: function () {
      return _currentIndex;
    },

    getImageCount: function () {
      return _imageIds.length;
    },

    onSliceChange: function (cb) {
      _onSliceChange = typeof cb === "function" ? cb : null;
    },

    destroy: function () {
      if (_element && cornerstone) {
        try {
          cornerstone.disable(_element);
        } catch (e) {
          console.warn("[CaseDicomViewer] destroy", e);
        }
        _element = null;
      }
      _stackConfig = null;
      _currentPlan = null;
      _currentIndex = 0;
      _imageIds = [];
      _onSliceChange = null;
    },
  };

  console.log("[CaseDicomViewer] viewer.js loaded");
})();
