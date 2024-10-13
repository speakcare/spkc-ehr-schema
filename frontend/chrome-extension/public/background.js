// background.js

const validUrlPatterns = [
  /^https?:\/\/.*\.pointclickcare\.com\/.*/, // Matches URLs like "https://*.pointclickcare.com"
  /^https:\/\/airtable\.com\/appRFbM7KJ2QwCDb6\/.*/ // Matches the Airtable URL pattern
];


chrome.runtime.onInstalled.addListener(() => {
  console.log("Extension installed");
  initializeTabs();
});
  
chrome.runtime.onStartup.addListener(() => {
  initializeTabs();
});
  
function initializeTabs() {
  chrome.tabs.query({}, function (tabs) {
    tabs.forEach((tab) => {
      if (tab.url && validUrlPatterns.some(pattern => pattern.test(tab.url))) {
        chrome.action.enable(tab.id);
      } else {
        chrome.action.disable(tab.id);
      }
    });
  });
}

  
// Function to enable or disable the popup action based on the tab's URL
function updateActionForTab(tab) {
  if (tab.url && validUrlPatterns.some(pattern => pattern.test(tab.url))) {
    console.log(`Enabling action for tab ID: ${tab.id}, URL: ${tab.url}`);
    chrome.action.enable(tab.id);
  } else {
    console.log(`Disabling action for tab ID: ${tab.id}, URL: ${tab.url}`);
    chrome.action.disable(tab.id);
  }
}

chrome.tabs.onUpdated.addListener(function (tabId, changeInfo, tab) {
    // Ensure we only proceed when the page has fully loaded
    if (changeInfo.status === 'complete') {
      updateActionForTab(tab);
    }
  });
  
  // Also listen for when the tab changes (e.g., user switches between tabs)
chrome.tabs.onActivated.addListener(function (activeInfo) {
  chrome.tabs.get(activeInfo.tabId, function (tab) {
    updateActionForTab(tab);
  });
});





