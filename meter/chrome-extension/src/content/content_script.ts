
import { BackgroundMessage, BackgroundResponse } from '../background/background' 
import { PageLoadMessage, UserInputMessage, PageEventMessage } from "../background/session_manager";
import { parseChart, ChartInfo, getPagePath, getPageUrl } from "./ehr/pointclickcare/pcc_chart_parser";

const pageInfo = {
  lastMessageSentTime: Date.now(),
  debounceTimer: null as NodeJS.Timeout | null,
  pageLoadTime: '',
  chartInfo: null as ChartInfo | null,
  initialized: false,
}

function initPageInfo() {
  pageInfo.chartInfo = parseChart();
  if (!pageInfo.chartInfo) {
    console.debug('initPageInfo: chart parser not supported for url', getPageUrl());
    pageInfo.initialized = false;
    return;
  }
  pageInfo.lastMessageSentTime = Date.now();
  pageInfo.pageLoadTime = '';
  pageInfo.debounceTimer = null;
  pageInfo.initialized = true;
}

function notifyPageLoaded() {
  if (!pageInfo.initialized) {
    console.debug('notifyPageLoaded: pageInfo not initialized. url', getPageUrl());
    return;
  }
  const pageLoadMessage = createPageLoadMessage();
  if (pageLoadMessage) {
    sendMessageToBackground(pageLoadMessage);
    pageInfo.pageLoadTime = pageLoadMessage.pageStartTime;
  }
  else {
    console.log('notifyPageLoaded: page event message not created for path:', getPagePath());
  }
}



async function sendMessageToBackground(message: BackgroundMessage) {
  try {
    // Send the message to the background script
    console.log('Sending message:', message);
    chrome.runtime.sendMessage(message, (response: BackgroundResponse) => {
      if (chrome.runtime.lastError) {
        console.error('Error sending message:', chrome.runtime.lastError.message);
      } else if (response?.success) {
        // Update the last message sent time
        pageInfo.lastMessageSentTime = Date.now();
        console.log(`Message sent successfully for username:`, response);
      } else {
        console.warn('Reciever responded with error:', message, response?.error);
      }
    });
  } catch (err) {
    console.error('Exception: message failed:', message, err);
  }
}


// let debounceTimer: NodeJS.Timeout | null = null;
function debounceAndThrottle(callback: () => void, debounceDelay: number, throttleDelay: number) {
  const now = Date.now();

  if (pageInfo.debounceTimer) {
    clearTimeout(pageInfo.debounceTimer);
    pageInfo.debounceTimer = null;
  }
  
  // Throttle: Send an event if `throttleDelay` has passed since the last event
  if (now - pageInfo.lastMessageSentTime >= throttleDelay) {
    callback();
    return;
  }
  // Debounce: Delay execution until user stops interacting
  pageInfo.debounceTimer = setTimeout(callback, debounceDelay);
}

function debounceAndThrottleMessage(message: any, debounceDelay: number, throttleDelay: number) {
  debounceAndThrottle(() => {
    sendMessageToBackground(message);
  }, debounceDelay, throttleDelay);
}

function createPageEventMessage(): PageEventMessage | null {
  if (!pageInfo.chartInfo) {
    console.warn('createPageEventMessage: pageInfo.chartInfo is null');
    return null;
  }
  return {
    timestamp: new Date().toISOString(),
    username:  pageInfo.chartInfo?.username || '', 
    chartType: pageInfo.chartInfo?.chartType || '',
    chartName: pageInfo.chartInfo?.chartName || '',
    orgCode: pageInfo.chartInfo?.orgCode || '', 
  };
}

function createUserInputMessage(
  input: string,
  inputType: 'text' | 'textarea' | 'checkbox' | 'radio' | 'dropdown' | 'multiselect' | 'button' | 'other',
): UserInputMessage | null {

  const userInputMessage = createPageEventMessage();
  if (!userInputMessage) {
    console.log('createUserInputMessage: page event message not created for path:', getPagePath());
    return null;
  }

  return {
    ...userInputMessage,
    type: 'user_input',
    input,
    inputType,
  }
}

function createPageLoadMessage(): PageLoadMessage | null{
  const pageLoadMessage = createPageEventMessage();
  if (!pageLoadMessage) {
    console.log('createPageLoadMessage: page event message not created for path:', getPagePath());
    return null;
  }
  return {
    ...pageLoadMessage,
    type: 'page_load',
    pageStartTime: new Date().toISOString(),
  }
}

const inputHandler = (event: Event) => {
  if (!pageInfo.initialized) {
    console.debug('inputHandler: pageInfo not initialized. url', getPageUrl());
    return;
  }
  const target = event.target as HTMLInputElement | HTMLTextAreaElement;
  if (!target) return;
  if (!pageInfo.pageLoadTime) return; // avoid race condition where pageLoadTime is not set yet

  const userInputMessage = createUserInputMessage(target.value, target instanceof HTMLTextAreaElement ? 'textarea' : 'text');
  if (userInputMessage) {
    debounceAndThrottleMessage(userInputMessage, 300, 5000);
  }
};

// Add click event listener for buttons
const clickHandler = (event: Event) => {
  if (!pageInfo.initialized) {
    console.debug('clickHandler: pageInfo not initialized. url', getPageUrl());
    return;
  }
  const target = event.target as HTMLElement;
  if (!target) return;
  if (!pageInfo.pageLoadTime) return; // avoid race condition where pageLoadTime is not set yet

  if (target instanceof HTMLButtonElement || 
    (target instanceof HTMLInputElement && (target.type === 'button' || target.type === 'submit' || target.type === 'reset'))) 
  { //only catch button clicks

    const userInputMessage = createUserInputMessage(target.innerText || target.value, 'button');
    if (userInputMessage) {
      debounceAndThrottleMessage(userInputMessage, 300, 5000);
    }
  }
};


// Add change event listener
const changeHandler = (event: Event) => {
  if (!pageInfo.initialized) {
    console.debug('changeHandler: pageInfo not initialized. url', getPageUrl());
    return;
  }
  const target = event.target as HTMLElement;
  if (!target) return;
  if (!pageInfo.pageLoadTime) return; // avoid race condition where pageLoadTime is not set yet

  const userInputMessage = createUserInputMessage('', 'other');
  if (!userInputMessage) {
    console.log('changeHandler: page event message not created for path:', getPagePath());
    return;
  }
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


function setupUserActivityTracking() {
    // Remmove existing event listeners in case they were added by previous loading of the script
  document.removeEventListener('input', inputHandler);
  document.removeEventListener('change', changeHandler);
  document.removeEventListener('click', clickHandler);

  // Attach new event listeners
  document.addEventListener('input', inputHandler);
  document.addEventListener('change', changeHandler);
  document.addEventListener('click', clickHandler);
}

initPageInfo();
notifyPageLoaded();
setupUserActivityTracking();


console.log('Content script initialized or re-initialized');
