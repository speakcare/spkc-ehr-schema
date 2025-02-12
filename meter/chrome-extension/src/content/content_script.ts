
import { BackgroundMessage, BackgroundResponse } from '../background/background' 
import { PageLoadMessage, InputType, UserInputMessage, PageEventMessage } from '../background/session_messages'
import { parseChart, ChartInfo } from './ehr/pointclickcare/pcc_chart_parser'
import { DebounceThrottle } from '../utils/debounce';
import { Logger } from '../utils/logger';
import { getPagePath, getPageUrl } from '../utils/url_utills';

const debounceDelay = 300; 
const throttleDelay = 5000; 

const debounceThrottleInstance = new DebounceThrottle(debounceDelay, throttleDelay);

const logger = new Logger('Content script');

const pageInfo = {
  lastMessageSentTime: Date.now(),
  pageLoadTime: '',
  chartInfo: null as ChartInfo | null,
  initialized: false,
  debouncer: null as DebounceThrottle | null,
}

function initPageInfo() {
  pageInfo.chartInfo = parseChart();
  if (!pageInfo.chartInfo) {
    logger.debug('initPageInfo: chart parser not supported for url', getPageUrl());
    pageInfo.initialized = false;
    return;
  }
  pageInfo.lastMessageSentTime = Date.now();
  pageInfo.pageLoadTime = '';
  pageInfo.debouncer = new DebounceThrottle(debounceDelay, throttleDelay);
  pageInfo.initialized = true;
}

function notifyPageLoaded() {
  if (!pageInfo.initialized) {
    logger.debug('notifyPageLoaded: pageInfo not initialized. url', getPageUrl());
    return;
  }
  const pageLoadMessage = createPageLoadMessage();
  if (pageLoadMessage) {
    sendMessageToBackground(pageLoadMessage);
    pageInfo.pageLoadTime = pageLoadMessage.pageStartTime;
  }
  else {
    logger.log('notifyPageLoaded: page event message not created for path:', getPagePath());
  }
}



async function sendMessageToBackground(message: BackgroundMessage) {
  try {
    // Send the message to the background script
    logger.log('Sending message:', message);
    chrome.runtime.sendMessage(message, (response: BackgroundResponse) => {
      if (chrome.runtime.lastError) {
        logger.error('Error sending message:', chrome.runtime.lastError.message);
      } else if (response?.success) {
        // Update the last message sent time
        pageInfo.lastMessageSentTime = Date.now();
        logger.log(`Message sent successfully for username:`, response);
      } else {
        logger.warn('Reciever responded with error:', message, response?.error);
      }
    });
  } catch (err) {
    logger.error('Exception: message failed:', message, err);
  }
}

function debounceAndThrottleMessage(message: any) {
  if (!pageInfo.debouncer) {
    logger.warn('debounceAndThrottleMessage: debouncer not initialized');
    return;
  }
  pageInfo.debouncer.debounce(() => {
    sendMessageToBackground(message);
  });
}

function createPageEventMessage(): PageEventMessage | null {
  if (!pageInfo.chartInfo) {
    logger.warn('createPageEventMessage: pageInfo.chartInfo is null');
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
  inputType: InputType,
): UserInputMessage | null {

  const userInputMessage = createPageEventMessage();
  if (!userInputMessage) {
    logger.log('createUserInputMessage: page event message not created for path:', getPagePath());
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
    logger.log('createPageLoadMessage: page event message not created for path:', getPagePath());
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
    logger.debug('inputHandler: pageInfo not initialized. url', getPageUrl());
    return;
  }
  const target = event.target as HTMLInputElement | HTMLTextAreaElement;
  if (!target) return;
  if (!pageInfo.pageLoadTime) return; // avoid race condition where pageLoadTime is not set yet

  const userInputMessage = createUserInputMessage(target.value, target instanceof HTMLTextAreaElement ? 'textarea' : 'text');
  if (userInputMessage) {
    debounceAndThrottleMessage(userInputMessage);
  }
};

// Add click event listener for buttons
const clickHandler = (event: Event) => {
  if (!pageInfo.initialized) {
    logger.debug('clickHandler: pageInfo not initialized. url', getPageUrl());
    return;
  }
  const target = event.target as HTMLElement;
  if (!target) return;
  if (!pageInfo.pageLoadTime) return; // avoid race condition where pageLoadTime is not set yet

  logger.info('clickHandler event:', event);
  let userInput: string = '';
  let inputType: InputType = undefined;

  const buttonElement = target.closest('button, input[type="button"], input[type="submit"], input[type="reset"]');
  const anchorElement = target.closest('a');
  const headingElement = target.closest('h1, h2, h3, h4, h5, h6');

  if (buttonElement) {
    userInput = (buttonElement as HTMLElement).innerText || (buttonElement as HTMLInputElement).value;
    inputType = 'button';
  } else if (anchorElement) {
    userInput = anchorElement.innerText || anchorElement.getAttribute('data-value') || '';
    inputType = 'link';
  } else if (headingElement) {
    userInput = (headingElement as HTMLElement).innerText;
    inputType = 'heading';
  } else {
    // Traverse up the DOM tree to find the nearest ancestor that matches the desired selectors
    let parentElement = target.parentElement;
    while (parentElement) {
      if (parentElement instanceof HTMLAnchorElement) {
        userInput = parentElement.innerText || parentElement.getAttribute('data-value') || '';
        inputType = 'link';
        break;
      } else if (parentElement instanceof HTMLButtonElement || 
        (parentElement instanceof HTMLInputElement && (parentElement.type === 'button' || parentElement.type === 'submit' || parentElement.type === 'reset'))) {
        userInput = parentElement.innerText || (parentElement as HTMLInputElement).value;
        inputType = 'button';
        break;
      } else if (parentElement instanceof HTMLHeadingElement) {
        userInput = parentElement.innerText;
        inputType = 'heading';
        break;
      }
      parentElement = parentElement.parentElement;
    }

    if (!parentElement) {
      logger.info('clickHandler: event type:', event.type, 'target not handled:', target);
    }
  }
  
  // if it is a handled case
  if (userInput !== '') {
    const userInputMessage = createUserInputMessage(userInput, inputType);
    if (userInputMessage) {
      debounceAndThrottleMessage(userInputMessage);
    }
  }

};


// Add change event listener
const changeHandler = (event: Event) => {
  if (!pageInfo.initialized) {
    logger.debug('changeHandler: pageInfo not initialized. url', getPageUrl());
    return;
  }
  const target = event.target as HTMLElement;
  if (!target) return;
  if (!pageInfo.pageLoadTime) return; // avoid race condition where pageLoadTime is not set yet

  const userInputMessage = createUserInputMessage('', 'other');
  if (!userInputMessage) {
    logger.log('changeHandler: page event message not created for path:', getPagePath());
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
  debounceAndThrottleMessage(userInputMessage);

};


function setupUserActivityTracking() {
    // Remmove existing event listeners in case they were added by previous loading of the script
  document.removeEventListener('input', inputHandler);
  document.removeEventListener('change', changeHandler);
  document.removeEventListener('click', clickHandler);

  // Attach new event listeners
  document.addEventListener('input', inputHandler);
  document.addEventListener('change', changeHandler);
  // Removed click handler as it was reporting activity on some button clicks that are not user input (e.g. cancel, close, etc.)
  document.addEventListener('click', clickHandler);
}

initPageInfo();
notifyPageLoaded();
setupUserActivityTracking();


logger.log('initialized or re-initialized');
