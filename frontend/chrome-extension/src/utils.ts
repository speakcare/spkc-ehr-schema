export function refreshCurrentTab(): void {
    if (typeof chrome !== 'undefined' && chrome.tabs) {
      chrome.tabs.query({ active: true, currentWindow: true }, (tabs: chrome.tabs.Tab[]) => {
        if (tabs.length > 0 && tabs[0].id !== undefined) {
          chrome.tabs.reload(tabs[0].id);
        }
      });
    }
  }


export function dispatchVisibilityChangeEvent(): void {
    if (typeof chrome !== 'undefined' && chrome.scripting) {
        // Get the current active tab
        chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (tabs.length > 0 && tabs[0].id !== undefined) {
            const activeTabId = tabs[0].id;
    
            // Inject and execute script to dispatch visibility change
            chrome.scripting.executeScript(
            {
                target: { tabId: activeTabId },
                func: () => {
                // This function runs in the page context
                document.dispatchEvent(new Event('visibilitychange'));
                },
            },
            () => {
                console.log('Visibility event dispatched to current tab');
            }
            );
        }
        });
    }
}