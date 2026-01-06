/**
 * Preload Script - Secure IPC Bridge
 * Provides safe communication between renderer and main process
 */

const { contextBridge, ipcRenderer } = require('electron');

// Expose limited APIs to renderer process
contextBridge.exposeInMainWorld('electron', {
  // App info
  getAppInfo: () => ipcRenderer.invoke('get-app-info'),
  
  // User data paths
  getUserDataPath: () => ipcRenderer.invoke('get-user-data-path'),
  openDatabaseFolder: () => ipcRenderer.invoke('open-database-folder'),
  
  // Platform detection
  platform: process.platform,
  isWindows: process.platform === 'win32',
  isMac: process.platform === 'darwin',
  isLinux: process.platform === 'linux',
});

console.log('✅ Preload script loaded - Electron APIs available');
