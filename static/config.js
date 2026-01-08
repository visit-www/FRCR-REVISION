// API Configuration - Points to local Flask backend
// This file tells the frontend where to send API requests

const API_BASE_URL = (() => {
  // If running locally (localhost/127.0.0.1), use local Flask
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return 'http://localhost:5000';
  }
  
  // If running on Vercel deployment, use the same origin (API routes are on same domain)
  if (window.location.hostname.includes('vercel.app')) {
    return window.location.origin; // Use current domain for API calls
  }
  
  // Default fallback
  return window.location.origin;
})();

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { API_BASE_URL };
}
