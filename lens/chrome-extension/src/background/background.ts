import { initializeSessionManager } from './session_manager';
import { initializePanelManager } from './panel_manager';


// For now not executing on existing tabs. we can uncomment this later if needed.

// chrome.runtime.onInstalled.addListener(() => {
//   console.log('SpeakCare Lens Extension installed or updated. Injecting scripts into matching tabs...');
//   chrome.tabs.query({ url: '*://*.pointclickcare.com/*' }, (tabs) => {
//     tabs.forEach((tab) => {
//       chrome.scripting.executeScript({
//         target: { tabId: tab.id! },
//         files: ['content.bundle.js'],
//       }, () => {
//         if (chrome.runtime.lastError) {
//           console.error(`Failed to inject script into tab ${tab.id}: ${chrome.runtime.lastError.message}`);
//         } else {
//           console.log(`Content script injected into tab ${tab.id}`);
//         }
//       });
//     });
//   });
// });


console.log('Background script loaded at', new Date().toISOString());
self.addEventListener('activate', () => {
  console.log('Background script activated at', new Date().toISOString());
});
self.addEventListener('message', (event) => {
  console.log('Message received in background script:', event.data);
});

// Initialize the panel manager and session manager
await initializePanelManager();
await initializeSessionManager();
console.log('Background script sesssion manager initialized at', new Date().toISOString());

