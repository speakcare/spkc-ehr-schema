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
// // Define the interface for the saved state
// export interface ExtensionState {
//   selectedTable: string;
//   audioBlob?: string | null;
// }

export const blobToBase64 = (blob: Blob): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64data = reader.result as string;
      resolve(base64data);
    };
    reader.onerror = (error) => reject(error);
    reader.readAsDataURL(blob);
  });
};

export const base64ToBlob = (base64: string, contentType = 'audio/webm; codecs=opus'): Blob => {
  const byteCharacters = atob(base64.split(',')[1]);
  const byteNumbers = new Array(byteCharacters.length);
  for (let i = 0; i < byteCharacters.length; i++) {
    byteNumbers[i] = byteCharacters.charCodeAt(i);
  }
  const byteArray = new Uint8Array(byteNumbers);
  return new Blob([byteArray], { type: contentType });
};

export const saveState = (key: string, state: any) => {
  if (typeof chrome !== 'undefined' && chrome.storage) {
    chrome.storage.local.set({ [key]: state }, () => {
      console.log(`State saved under key: ${key}`);
    });
  }
};

export const loadState = (key: string, callback: (state: any) => void) => {
  if (typeof chrome !== 'undefined' && chrome.storage) {
    chrome.storage.local.get([key], (result) => {
      if (result[key]) {
        callback(result[key]);
      }
    });
  }
};
