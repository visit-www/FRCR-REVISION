// AJCC TNM Cookie Sync - Popup Script

document.addEventListener('DOMContentLoaded', () => {
  updateStatus();
  
  // Sync button
  document.getElementById('syncBtn').addEventListener('click', async () => {
    const btn = document.getElementById('syncBtn');
    btn.innerHTML = '<span class="spinner"></span> Syncing...';
    btn.disabled = true;
    
    try {
      chrome.runtime.sendMessage({ action: 'syncNow' }, (response) => {
        if (chrome.runtime.lastError) {
          showError(chrome.runtime.lastError.message);
        } else if (response && response.success) {
          updateStatus();
        } else {
          showError(response?.error || 'Sync failed');
        }
        btn.innerHTML = '<span>🔄</span> Sync Cookies Now';
        btn.disabled = false;
      });
    } catch (error) {
      showError(error.message);
      btn.innerHTML = '<span>🔄</span> Sync Cookies Now';
      btn.disabled = false;
    }
  });
  
  // Login button
  document.getElementById('loginBtn').addEventListener('click', () => {
    chrome.runtime.sendMessage({ action: 'openAJCC' }, () => {
      if (chrome.runtime.lastError) {
        console.error(chrome.runtime.lastError);
      }
      window.close();
    });
  });
});

function updateStatus() {
  try {
    chrome.runtime.sendMessage({ action: 'getStatus' }, (status) => {
      if (chrome.runtime.lastError) {
        showError('Extension error: ' + chrome.runtime.lastError.message);
        return;
      }
      if (!status) {
        showError('Could not get status');
        return;
      }
      renderStatus(status);
    });
  } catch (error) {
    showError('Could not check status');
  }
}

function renderStatus(status) {
  const card = document.getElementById('statusCard');
  const icon = document.getElementById('statusIcon');
  const text = document.getElementById('statusText');
  const detail = document.getElementById('statusDetail');
  
  if (status.isLoggedIn && status.cookieCount > 0) {
    card.className = 'status-card success';
    icon.textContent = '✅';
    text.textContent = 'Authenticated';
    
    let detailText = `${status.cookieCount} cookies synced`;
    if (status.lastSync) {
      const ago = Math.round((Date.now() - status.lastSync) / 1000);
      if (ago < 60) {
        detailText += ` • ${ago}s ago`;
      } else if (ago < 3600) {
        detailText += ` • ${Math.round(ago / 60)}m ago`;
      } else {
        detailText += ` • ${Math.round(ago / 3600)}h ago`;
      }
    }
    detail.textContent = detailText;
  } else if (status.cookieCount > 0) {
    card.className = 'status-card warning';
    icon.textContent = '⚠️';
    text.textContent = 'Partial Authentication';
    detail.textContent = `${status.cookieCount} cookies found, may need to re-login`;
  } else {
    card.className = 'status-card error';
    icon.textContent = '❌';
    text.textContent = 'Not Authenticated';
    detail.textContent = 'Please log in to AJCC';
  }
}

function showError(message) {
  const card = document.getElementById('statusCard');
  const icon = document.getElementById('statusIcon');
  const text = document.getElementById('statusText');
  const detail = document.getElementById('statusDetail');
  
  card.className = 'status-card error';
  icon.textContent = '❌';
  text.textContent = 'Error';
  detail.textContent = message;
}
