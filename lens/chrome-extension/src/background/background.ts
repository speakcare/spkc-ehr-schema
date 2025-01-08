import { initializeSessionManager } from './session_manager';
import { Tab } from '../types/index.d';
import { isTabUrlPermitted, isUrlPermitted, isDomainPermitted } from '../utils/hosts';


console.log('Setting up side panel behavior...');
chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })
    .then(() => console.log("Toolbar action button linked to side panel."))
    .catch((error) => console.error("Error linking action button to side panel:", error));


interface SidePanelOptions {
  tabId: number;
  path?: string;
  enabled: boolean;
}

async function updateSidePanelForTab(tab: Tab): Promise<void> {
  // console.log(`SpeakCare Lens side panel: updateSidePanelForTab called for tab`, tab);
  const tabId = tab.id;
  console.log(`SpeakCare Lens side panel: updateSidePanelForTab tab.id ${tabId}`);
  const isValid = isTabUrlPermitted(tab);
  if (isValid) {
    const options: SidePanelOptions = {
      tabId,
      path: 'panel.html',
      enabled: true
    };
    await chrome.sidePanel.setOptions(options);
    console.log(`SpeakCare Lens side panel: side panel enabled for tab.id ${tabId} url ${tab.url}`);
  } else {
    console.log(`SpeakCare Lens side panel: disabling side panel for tab.id ${tabId} url ${tab.url}`);
    const options: SidePanelOptions = {
      tabId,
      enabled: false
    };
    await chrome.sidePanel.setOptions(options);
    await chrome.action.setTitle({ title: "SpeakCare Lens panel not active on this tab", tabId: tabId });
    console.log(`SpeakCare Lens side panel: side panel disabled for tab.id ${tabId}`);
  }
}

// // Listen for tab activations
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  chrome.tabs.get(activeInfo.tabId, async (tab) => {
    if (tab.id !== undefined) {
      const tabId = tab.id;
      console.log(`SpeakCare Lens side panel: tabs.onActivated tab.id ${tabId}`);
      await updateSidePanelForTab({ id: tabId, url: tab.url });
    }
  });
});


chrome.tabs.onUpdated.addListener(async (tabId, info, tab) => {
  if (!tab.url || tab.id === undefined) return;
  console.log(`SpeakCare side panel: tabs.onUpdated tab.id ${tabId}`);
  await updateSidePanelForTab({ id: tab.id, url: tab.url });
});

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

await initializeSessionManager();
console.log('Background script sesssion manager initialized at', new Date().toISOString());

