import { isTabUrlPermitted  } from '../utils/url_utills';
import { Tab } from '../types';

interface SidePanelOptions {
    tabId?: number;
    path?: string;
    enabled: boolean;
  }
  

export async function initializePanelManager() {
    console.log('Setting up side panel behavior...');
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })
        .then(() => console.log("Toolbar action button linked to side panel."))
        .catch((error) => console.error("Error linking action button to side panel:", error));

    console.log('Initializing panel manager...');

    console.log(`SpeakCare Meter side panel starting disabled by default`);
    
    const options: chrome.sidePanel.PanelOptions = { 
      enabled: false,
    }

    await chrome.sidePanel.setOptions(options);
    await chrome.action.setTitle({ title: "SpeakCare Meter panel not activated"});

    chrome.tabs.onActivated.addListener(async (activeInfo) => {
        chrome.tabs.get(activeInfo.tabId, async (tab) => {
            if (tab.id !== undefined) {
                const tabId = tab.id;
                console.debug(`SpeakCare Meter side panel: tabs.onActivated tab.id ${tabId}`);
                await updateSidePanelForTab({ id: tabId, url: tab.url });
            }
        });
    });
    chrome.tabs.onUpdated.addListener(async (tabId, info, tab) => {
        if (!tab.url || tab.id === undefined) return;
        console.debug(`SpeakCare side panel: tabs.onUpdated tab.id ${tabId}`);
        await updateSidePanelForTab({ id: tab.id, url: tab.url });
    });
    console.log('Panel manager initialized.');
}

async function updateSidePanelForTab(tab: Tab): Promise<void> {
  const tabId = tab.id;
  console.debug(`SpeakCare Meter side panel: updateSidePanelForTab tab.id ${tabId}`);
  const isValid = isTabUrlPermitted(tab);
  if (isValid) {
    const options: chrome.sidePanel.PanelOptions = {
      tabId,
      path: 'panel.html',
      enabled: true
    };
    await chrome.sidePanel.setOptions(options);
    console.debug(`SpeakCare Meter side panel: side panel enabled for tab.id ${tabId} url ${tab.url}`);
  } else {
    console.debug(`SpeakCare Meter side panel: disabling side panel for tab.id ${tabId} url ${tab.url}`);
    const options: SidePanelOptions = {
      tabId,
      enabled: false
    };
    await chrome.sidePanel.setOptions(options);
    await chrome.action.setTitle({ title: "SpeakCare Meter panel not active on this tab", tabId: tabId });
    console.debug(`SpeakCare Meter side panel: side panel disabled for tab.id ${tabId}`);
  }
}
