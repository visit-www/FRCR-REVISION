/**
 * Case DICOM Viewer - Cornerstone3D integration
 *
 * TODO: Load @cornerstonejs/core, @cornerstonejs/tools, cornerstone-web-image-loader
 * Init viewport, stack scroll, zoom, pan, window/level
 */
(function () {
  "use strict";
  console.log("[CaseDicomViewer] viewer.js loaded (stub)");
  window.CaseDicomViewer = {
    init: function (containerId, stackConfig) {
      console.log("[CaseDicomViewer] init", containerId, stackConfig);
    },
    loadStack: function (planName, imageUrls) {
      console.log("[CaseDicomViewer] loadStack", planName, imageUrls?.length);
    },
    destroy: function () {
      console.log("[CaseDicomViewer] destroy");
    },
  };
})();
