// background.js
chrome.runtime.onInstalled.addListener(() => {
    console.log("Extension installed");
  });

const validUrlPatterns = [
    /^https?:\/\/.*\.pointclickcare\.com\/.*/, // Matches URLs like "https://*.validdomain.com"
    /^https:\/\/airtable\.com\/appRFbM7KJ2QwCDb6\/.*/ // Matches the Airtable URL pattern
];
  
chrome.tabs.onUpdated.addListener(function (tabId, changeInfo, tab) {
    if (tab.url && validUrlPatterns.some(pattern => pattern.test(tab.url))) {
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
      if (tab.url && validUrlPatterns.some(pattern => pattern.test(tab.url))) {
        chrome.action.enable(activeInfo.tabId);
      } else {
        chrome.action.disable(activeInfo.tabId);
      }
    });
  });


