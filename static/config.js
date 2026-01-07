// API Configuration - Points to local Flask backend
// This file tells the frontend where to send API requests

const API_BASE_URL = (() => {
  // If running locally (localhost/127.0.0.1), use local Flask
  if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
    return 'http://localhost:5000';
  }
  
  // If running on Vercel, use localhost (still the local machine running Flask)
  // You can also set FLASK_BACKEND_URL in your environment if needed
  if (window.location.hostname.includes('vercel.app')) {
    // For local network access, use: http://192.168.1.X:5000 (replace X with your IP)
    // For remote access via ngrok, use the ngrok URL: https://xxxx-xxxx-xxxx-xxxx.ngrok.io
    return process.env.REACT_APP_FLASK_BACKEND || 'http://localhost:5000';
  }
  
  return 'http://localhost:5000';
})();

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = { API_BASE_URL };
}
