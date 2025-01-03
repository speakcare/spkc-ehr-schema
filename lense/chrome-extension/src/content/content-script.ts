
const observer = new MutationObserver(() => {
    chrome.runtime.sendMessage({ type: 'dom_change', timestamp: new Date().toISOString() });
  });
  
  observer.observe(document.body, {
    childList: true,
    subtree: true,
    attributes: true,
    characterData: true,
  });
  
  console.log('Content script loaded and observing DOM changes.');
  