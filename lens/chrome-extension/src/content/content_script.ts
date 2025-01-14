
import { BackgroundMessage, BackgroundResponse, PageLoadMessage, UserInputMessage, PageLoadResponse, UserInputResponse } from "../types";

let lastMessageSentTime: number = Date.now();

async function sendMessageToBackground(message: BackgroundMessage) {
  try {
    // Send the message to the background script
    chrome.runtime.sendMessage(message, (response: BackgroundResponse) => {
      if (chrome.runtime.lastError) {
        console.error('Error sending message:', chrome.runtime.lastError.message);
      } else if (response?.success) {
        // Update the last message sent time
        lastMessageSentTime = Date.now();
        console.log(`Message sent successfully for username:`, response);
      } else {
        console.warn('Failed to send message:', response?.error);
      }
    });
  } catch (err) {
    console.error('Exception: message failed:', err);
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

function debounceAndThrottleMessage(message: any, debounceDelay: number, throttleDelay: number) {
  debounceAndThrottle(() => {
    sendMessageToBackground(message);
  }, debounceDelay, throttleDelay);
}

 // let pageLoadTime = new Date().toISOString();
let pageLoadTime = '' // empty unil the page load message is sent
const inputHandler = (event: Event) => {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement;
  if (!target) return;
  if (!pageLoadTime) return; // avoid race condition where pageLoadTime is not set yet
  const userInputMessage: UserInputMessage = {
    type: 'user_input',
    input: target.value,
    inputType: target instanceof HTMLTextAreaElement ? 'textarea' : 'text',
    username: getUsername() || '',
    timestamp: new Date().toISOString(),
  };
  debounceAndThrottleMessage(userInputMessage, 300, 5000);
};

// Add click event listener for buttons
const clickHandler = (event: Event) => {
  const target = event.target as HTMLElement;
  if (!target) return;
  if (!pageLoadTime) return; // avoid race condition where pageLoadTime is not set yet

  if (target instanceof HTMLButtonElement || 
    (target instanceof HTMLInputElement && (target.type === 'button' || target.type === 'submit' || target.type === 'reset'))) 
  { //only catch button clicks

    const username = getUsername() || '';
    const userInputMessage: UserInputMessage = {
      type: 'user_input',
      input: target.innerText || target.value,
      inputType: 'button',
      username: username,
      timestamp: new Date().toISOString(),
    };  
    debounceAndThrottleMessage(userInputMessage, 300, 5000);
  }

};


// Add change event listener
const changeHandler = (event: Event) => {
  const target = event.target as HTMLElement;
  if (!target) return;
  if (!pageLoadTime) return; // avoid race condition where pageLoadTime is not set yet

  const username = getUsername() || '';
  const userInputMessage: UserInputMessage = {
    type: 'user_input',
    input: '',
    inputType: 'other',
    username: username,
    timestamp: new Date().toISOString(),
  };
  if (target instanceof HTMLInputElement) {
    if (target.type === 'checkbox') {
      userInputMessage.input = target.checked.toString();
      userInputMessage.inputType = 'checkbox';
    } else if (target.type === 'radio') {
      userInputMessage.input = target.value;
      userInputMessage.inputType = 'radio';
    } else {
      userInputMessage.input = target.value;
      userInputMessage.inputType = 'text';
    }
  } else if (target instanceof HTMLSelectElement) {
    if (target.multiple) {
      const selectedOptions = Array.from(target.selectedOptions).map(option => option.value);
      userInputMessage.input = selectedOptions.join(', ');
      userInputMessage.inputType = 'multiselect';
    } else {
      userInputMessage.input = target.value;
      userInputMessage.inputType = 'dropdown';
    }
  } else if (target instanceof HTMLTextAreaElement) {
    userInputMessage.input = target.value;
    userInputMessage.inputType = 'textarea';
  } else {
    // Handle other cases safely
    if ('value' in target) {
      userInputMessage.input = (target as HTMLInputElement).value;
    } else {
      userInputMessage.input = '';
    }
    userInputMessage.inputType = 'other';
  }
  debounceAndThrottleMessage(userInputMessage, 300, 5000);

};

// Utility to extract the username from the DOM
function getUsername(): string | null {
  // get the username from the userLabel element
  const userLabelElement = document.querySelector('.userLabel');
  return userLabelElement ? userLabelElement.textContent?.trim() || null : null;
}


function notifyPageLoaded() {
  const username = getUsername();
  if (username) {
    let currentTime = new Date().toISOString();
    const pageLoadMessage: PageLoadMessage = { type: 'page_load', username, pageStartTime: currentTime };
    console.log('sending pageLoadMessage:', pageLoadMessage);
    sendMessageToBackground(pageLoadMessage);
    pageLoadTime = currentTime;
  } else {
    console.warn('Username not found in the DOM during page load.');
  }
}

function setupUserActivityTracking() {
    // Remmove existing event listeners in case they were added by previous loading of the script
  document.removeEventListener('input', inputHandler);
  document.removeEventListener('change', changeHandler);
  document.removeEventListener('change', clickHandler);

  // Attach new event listeners
  document.addEventListener('input', inputHandler);
  document.addEventListener('change', changeHandler);
  document.addEventListener('click', clickHandler);
}


notifyPageLoaded();
setupUserActivityTracking();


console.log('Content script initialized or re-initialized');
