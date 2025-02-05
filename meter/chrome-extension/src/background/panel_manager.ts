import { isTabUrlPermitted  } from '../utils/url_utills';
import { Tab } from '../types';
import { Logger } from '../utils/logger';

interface SidePanelOptions {
    tabId?: number;
    path?: string;
    enabled: boolean;
  }
  

const logger = new Logger('PanelManager');
export async function initializePanelManager() {
    logger.log('Setting up side panel behavior...');
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })
        .then(() => logger.log("Toolbar action button linked to side panel."))
        .catch((error) => logger.error("Error linking action button to side panel:", error));

    logger.log('Initializing panel manager...');

    logger.debug(`Meter side panel starting disabled by default`);
    
    const options: chrome.sidePanel.PanelOptions = { 
      enabled: false,
    }

    await chrome.sidePanel.setOptions(options);
    await chrome.action.setTitle({ title: "SpeakCare Meter panel not activated"});

    chrome.tabs.onActivated.addListener(async (activeInfo) => {
        chrome.tabs.get(activeInfo.tabId, async (tab) => {
            if (tab.id !== undefined) {
                const tabId = tab.id;
                logger.debug(`tabs.onActivated tab.id ${tabId}`);
                await updateSidePanelForTab({ id: tabId, url: tab.url });
            }
        });
    });
    chrome.tabs.onUpdated.addListener(async (tabId, info, tab) => {
        if (!tab.url || tab.id === undefined) return;
        logger.debug(`tabs.onUpdated tab.id ${tabId}`);
        await updateSidePanelForTab({ id: tab.id, url: tab.url });
    });
    logger.log('Panel manager initialized.');
}

async function updateSidePanelForTab(tab: Tab): Promise<void> {
  const tabId = tab.id;
  logger.debug(`updateSidePanelForTab tab.id ${tabId}`);
  const isValid = isTabUrlPermitted(tab);
  if (isValid) {
    const options: chrome.sidePanel.PanelOptions = {
      tabId,
      path: 'panel.html',
      enabled: true
    };
    await chrome.sidePanel.setOptions(options);
    logger.debug(`side panel enabled for tab.id ${tabId} url ${tab.url}`);
  } else {
    logger.debug(`disabling side panel for tab.id ${tabId} url ${tab.url}`);
    const options: SidePanelOptions = {
      tabId,
      enabled: false
    };
    await chrome.sidePanel.setOptions(options);
    await chrome.action.setTitle({ title: "not active on this tab", tabId: tabId });
    logger.debug(`side panel disabled for tab.id ${tabId}`);
  }
}
