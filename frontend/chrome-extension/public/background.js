// background.js
chrome.runtime.onInstalled.addListener(() => {
    console.log("Extension installed");
  });

  
chrome.tabs.onUpdated.addListener(function (tabId, changeInfo, tab) {
    if (tab.url && tab.url.includes('https://airtable.com/appRFbM7KJ2QwCDb6/')) {
      // Enable the popup (action) if the user is on the specified Airtable page
      chrome.action.enable(tabId);
    } else {
      // Disable the popup if the user is not on the specified Airtable page
      chrome.action.disable(tabId);
    }
  });
  
  // Also listen for when the tab changes (e.g., user switches between tabs)
  chrome.tabs.onActivated.addListener(function (activeInfo) {
    chrome.tabs.get(activeInfo.tabId, function (tab) {
      if (tab.url && tab.url.includes('https://airtable.com/appRFbM7KJ2QwCDb6/')) {
        chrome.action.enable(activeInfo.tabId);
      } else {
        chrome.action.disable(activeInfo.tabId);
      }
    });
  });


