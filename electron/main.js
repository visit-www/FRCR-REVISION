/**
 * FRCR Examiner - Electron Main Process
 * Manages Flask backend and Electron window
 */

const { app, BrowserWindow, Menu, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const os = require('os');
const fs = require('fs');

let mainWindow;
let flaskProcess = null;
const FLASK_PORT = 5000;
const FLASK_URL = `http://localhost:${FLASK_PORT}`;
const APP_NAME = 'FRCR Examiner';

/**
 * Start Flask backend server
 */
function startFlaskServer() {
  return new Promise((resolve, reject) => {
    try {
      // Get the correct app path (works in both dev and packaged app)
      const appPath = app.isPackaged 
        ? process.resourcesPath 
        : path.join(__dirname, '..');
      
      let flaskExecutable;
      let spawnArgs = [];
      
      if (app.isPackaged) {
        // Use bundled PyInstaller executable
        const isWindows = process.platform === 'win32';
        const exeName = isWindows ? 'flask_server.exe' : 'flask_server';
        
        // Try multiple possible locations for the bundled executable
        const possiblePaths = [
          path.join(appPath, 'flask_server', exeName),  // Standard location
          path.join(appPath, 'resources', 'flask_server', exeName),  // Resources folder
          path.join(appPath, exeName),  // Direct in resources
        ];
        
        flaskExecutable = null;
        for (const possiblePath of possiblePaths) {
          if (fs.existsSync(possiblePath)) {
            flaskExecutable = possiblePath;
            break;
          }
        }
        
        // Check if bundled executable exists, fallback to Python if not
        if (!flaskExecutable) {
          console.warn('⚠️ Bundled Flask executable not found, falling back to system Python');
          const pythonCmd = isWindows ? 'python' : 'python3';
          const appPyPath = path.join(appPath, 'app.py');
          flaskExecutable = pythonCmd;
          spawnArgs = [appPyPath];
        }
      } else {
        // Development mode: use system Python
        const isPythonWindows = process.platform === 'win32';
        const pythonCmd = isPythonWindows ? 'python' : 'python3';
        flaskExecutable = pythonCmd;
        spawnArgs = [path.join(appPath, 'app.py')];
      }

      // Spawn Flask process
      flaskProcess = spawn(flaskExecutable, spawnArgs, {
        cwd: appPath,
        stdio: ['ignore', 'pipe', 'pipe'],
        detached: false,
      });

      let isReady = false;

      // Monitor Flask output
      flaskProcess.stdout.on('data', (data) => {
        const output = data.toString();
        console.log(`[Flask] ${output}`);

        // Check if Flask started successfully
        if (!isReady && output.includes('Running on')) {
          isReady = true;
          console.log('✅ Flask server started successfully');
          resolve();
        }
      });

      flaskProcess.stderr.on('data', (data) => {
        console.error(`[Flask Error] ${data}`);
      });

      flaskProcess.on('error', (err) => {
        console.error('Failed to start Flask:', err);
        reject(err);
      });

      flaskProcess.on('exit', (code, signal) => {
        console.log(`Flask process exited with code ${code}`);
      });

      // Timeout if Flask doesn't start within 10 seconds
      setTimeout(() => {
        if (!isReady) {
          console.warn('⚠️ Flask taking longer to start, continuing anyway...');
          resolve();
        }
      }, 10000);
    } catch (err) {
      console.error('Error spawning Flask:', err);
      reject(err);
    }
  });
}

/**
 * Create Electron window
 */
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    webPreferences: {
      preload: app.isPackaged
        ? path.join(process.resourcesPath, 'electron', 'preload.js')
        : path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
    },
    icon: app.isPackaged 
      ? path.join(process.resourcesPath, 'assets', 'icon.png')
      : path.join(__dirname, '../assets/icon.png'),
  });

  // Load Flask backend (always use localhost in packaged app)
  const startUrl = process.env.ELECTRON_START_URL || FLASK_URL;
  mainWindow.loadURL(startUrl);

  // Open DevTools in development
  if (process.env.DEBUG_ELECTRON === 'true') {
    mainWindow.webContents.openDevTools();
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Create application menu
  createMenu();
}

/**
 * Create application menu
 */
function createMenu() {
  const template = [
    {
      label: APP_NAME,
      submenu: [
        { label: `About ${APP_NAME}`, role: 'about' },
        { type: 'separator' },
        { label: 'Preferences', accelerator: 'CmdOrCtrl+,', click: () => { /* TODO */ } },
        { type: 'separator' },
        { label: 'Exit', accelerator: 'CmdOrCtrl+Q', click: () => app.quit() },
      ],
    },
    {
      label: 'Edit',
      submenu: [
        { label: 'Undo', accelerator: 'CmdOrCtrl+Z', role: 'undo' },
        { label: 'Redo', accelerator: 'CmdOrCtrl+Shift+Z', role: 'redo' },
        { type: 'separator' },
        { label: 'Cut', accelerator: 'CmdOrCtrl+X', role: 'cut' },
        { label: 'Copy', accelerator: 'CmdOrCtrl+C', role: 'copy' },
        { label: 'Paste', accelerator: 'CmdOrCtrl+V', role: 'paste' },
      ],
    },
    {
      label: 'View',
      submenu: [
        { label: 'Reload', accelerator: 'CmdOrCtrl+R', click: () => mainWindow.reload() },
        { label: 'Full Screen', accelerator: 'F11', role: 'togglefullscreen' },
        { type: 'separator' },
        { label: 'Developer Tools', accelerator: 'CmdOrCtrl+Shift+I', click: () => mainWindow.webContents.openDevTools() },
      ],
    },
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

/**
 * IPC Handlers
 */
ipcMain.handle('get-app-info', () => ({
  name: APP_NAME,
  version: app.getVersion(),
  platform: process.platform,
  flaskUrl: FLASK_URL,
}));

ipcMain.handle('get-user-data-path', () => {
  return app.getPath('userData');
});

ipcMain.handle('open-database-folder', () => {
  const dataPath = path.join(app.getPath('userData'), '../FRCR_EXAMINER');
  // Create folder if it doesn't exist
  if (!fs.existsSync(dataPath)) {
    fs.mkdirSync(dataPath, { recursive: true });
  }
  return dataPath;
});

/**
 * App lifecycle
 */
app.on('ready', async () => {
  try {
    console.log('Starting FRCR Examiner...');
    
    // Start Flask backend
    await startFlaskServer();
    
    // Create window
    createWindow();
  } catch (err) {
    console.error('Failed to start app:', err);
    app.quit();
  }
});

app.on('window-all-closed', () => {
  // Kill Flask process on macOS and Windows
  if (flaskProcess) {
    flaskProcess.kill();
  }
  app.quit();
});

app.on('activate', () => {
  // On macOS, re-create window when dock icon is clicked
  if (mainWindow === null) {
    createWindow();
  }
});

app.on('quit', () => {
  // Cleanup Flask process
  if (flaskProcess) {
    try {
      process.kill(-flaskProcess.pid); // Kill process group
    } catch (e) {
      flaskProcess.kill();
    }
  }
});

/**
 * Handle uncaught exceptions
 */
process.on('uncaughtException', (error) => {
  console.error('Uncaught Exception:', error);
});

module.exports = { startFlaskServer };
