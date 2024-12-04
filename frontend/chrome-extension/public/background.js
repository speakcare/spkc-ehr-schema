// background.js

const validUrlPatterns = [
  /^https?:\/\/.*\.pointclickcare\.com\/.*/, // Matches URLs like "https://*.pointclickcare.com"
  /^https:\/\/airtable\.com\/appRFbM7KJ2QwCDb6\/.*/ // Matches the Airtable URL pattern
];


chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true })
    .then(() => console.log("Toolbar action button linked to side panel."))
    .catch((error) => console.error("Error linking action button to side panel:", error));

  

function isTabValid(tab) {
  if (!tab.url) return false; 
  const url = new URL(tab.url);
  return url && validUrlPatterns.some((pattern) => pattern.test(url ));
}

async function updateSidePanelForTab(tab) {
  console.log(`SpeakCare side panel: updateSidePanelForTab called for tab`, tab);
  const tabId = tab.id
  console.log(`SpeakCare side panel: tabs.onActivated tab.id ${tabId}`);
  const isValid = isTabValid(tab);
  if(isValid) {
    await chrome.sidePanel.setOptions({
      tabId,
      path: 'index.html',
      enabled: true
    });
    console.log(`SpeakCare side panel: side panel enabled for tab.id ${tabId}`);
  } else {
    console.log(`SpeakCare side panel: disabling side panel for tab.id ${tabId} url ${tab.url}`);
    // Disables the side panel on all other sites
    await chrome.sidePanel.setOptions({
      tabId,
      enabled: false
    });
    // change the title for this tab
    chrome.action.setTitle({ title: "SpeakCare panel not active on this tab", tabId: tabId });
    // change the icons to inactive for this tab
    chrome.action.setIcon({
      path: {
        16: "icons/speakcare-icon-inactive-16.png",
        48: "icons/speakcare-icon-inactive-48.png",
        128: "icons/speakcare-icon-inactive-128.png"
      },
      tabId: tabId, 
    });    
    console.log(`SpeakCare side panel: side panel disabled for tab.id ${tabId}`);
  }
}

// // Listen for tab activations
chrome.tabs.onActivated.addListener(async (activeInfo) => {
  chrome.tabs.get(activeInfo.tabId, async (tab) => {
    const tabId = tab.id
    console.log(`SpeakCare side panel: tabs.onActivated tab.id ${tabId}`);
    await updateSidePanelForTab(tab);
  });
});


chrome.tabs.onUpdated.addListener(async (tabId, info, tab) => {
  if (!tab.url) return;
  console.log(`SpeakCare side panel: tabs.onUpdated tab.id ${tabId}`);
  await updateSidePanelForTab(tab);
});





