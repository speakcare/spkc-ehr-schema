
let lastMessageSentTime: number = Date.now();
async function sendMessageToBackground(message: any) {
  try {

    // Send the message to the background script
    chrome.runtime.sendMessage(message, (response) => {
      if (chrome.runtime.lastError) {
        console.error('Error sending message:', chrome.runtime.lastError.message);
      } else if (response?.success) {
        // Update the last message sent time
        lastMessageSentTime = Date.now();
        console.log(`Message sent successfully:`, response.message);
      } else {
        console.warn('Failed to enrich and send message:', response?.error);
      }
    });

  } catch (err) {
    console.error('Failed to send message:', err);
  }
}


let debounceTimer: NodeJS.Timeout | null = null;
function debounceAndThrottle(callback: () => void, debounceDelay: number, throttleDelay: number) {
  const now = Date.now();

  if (debounceTimer) {
    clearTimeout(debounceTimer);
    debounceTimer = null;
  }
  
  // Throttle: Send an event if `throttleDelay` has passed since the last event
  if (now - lastMessageSentTime >= throttleDelay) {
    callback();
    return;
  }
  // Debounce: Delay execution until user stops interacting
  debounceTimer = setTimeout(callback, debounceDelay);
}

 // let pageLoadTime = new Date().toISOString();
let pageLoadTime = '' // empty unil the page load message is sent
const inputHandler = (event: Event) => {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement;
  if (!target) return;
  if (!pageLoadTime) return; // avoid race condition where pageLoadTime is not set yet

  debounceAndThrottle(() => {
    sendMessageToBackground({
      type: 'user_input',
      timestamp: new Date().toISOString(),
      inputType: target instanceof HTMLTextAreaElement ? 'textarea' : 'text',
      value: target.value,
      pageLoadTime: pageLoadTime,
    });
  }, 300, 5000);
};


// Add change event listener
const changeHandler = (event: Event) => {
  const target = event.target as HTMLElement;
  if (!target) return;
  if (!pageLoadTime) return; // avoid race condition where pageLoadTime is not set yet

  const username = getUsername();
  const userInputMessage = {
    type: 'user_input',
    timestamp: new Date().toISOString(),
    username: username,
    pageLoadTime: pageLoadTime,
  };

  debounceAndThrottle(() => {
    if (target instanceof HTMLInputElement) {
      if (target.type === 'checkbox') {
        const checkboxMessage = {
          ...userInputMessage,
          inputType: 'checkbox',
          value: target.checked,
        };
        sendMessageToBackground(checkboxMessage);
        // sendMessageWithTimestamp({
        //   type: 'user_input',
        //   timestamp: new Date().toISOString(),
        //   inputType: 'checkbox',
        //   value: target.checked,
        // });
      } else if (target.type === 'radio') {
        const radioMessage = {
          ...userInputMessage,
          inputType: 'radio',
          value: target.value,
        };
        sendMessageToBackground(radioMessage);
        // sendMessageWithTimestamp({
        //   type: 'user_input',
        //   timestamp: new Date().toISOString(),
        //   inputType: 'radio',
        //   value: target.value,
        // });
      }
    } else if (target instanceof HTMLSelectElement) {
      const dropdownMessage = {
        ...userInputMessage,
        inputType: 'dropdown',
        value: target.value,
      };
      sendMessageToBackground(dropdownMessage);
      // sendMessageWithTimestamp({
      //   type: 'user_input',
      //   timestamp: new Date().toISOString(),
      //   inputType: 'dropdown',
      //   value: target.value,
      // });
    }
  }, 300, 5000);
};


// Utility to extract the username from the DOM
function getUsername(): string | null {
  // get the username from the userLabel element
  const userLabelElement = document.querySelector('.userLabel');
  return userLabelElement ? userLabelElement.textContent?.trim() || null : null;
}

// Notify the background script when the page is loaded
function notifyPageLoaded() {
  const username = getUsername();
  if (username) {
    let currentTime = new Date().toISOString();
    chrome.runtime.sendMessage({ type: 'page_loaded', username, currentTime });
    pageLoadTime = currentTime;
    console.log(`Page loaded message sent with username: ${username}`);
  } else {
    console.warn('Username not found in the DOM during page load.');
  }
}
function setupUserActivityTracking() {
    // Remmove existing event listeners in case they were added by previous loading of the script
  document.removeEventListener('input', inputHandler);
  document.removeEventListener('change', changeHandler);

  // Attach new event listeners
  document.addEventListener('input', inputHandler);
  document.addEventListener('change', changeHandler);
}


notifyPageLoaded();
setupUserActivityTracking();

// // Remmove existing event listeners in case they were added by previous loading of the script
// document.removeEventListener('input', inputHandler);
// document.removeEventListener('change', changeHandler);

// // Attach new event listeners
// document.addEventListener('input', inputHandler);
// document.addEventListener('change', changeHandler);

console.log('Content script initialized or re-initialized');
