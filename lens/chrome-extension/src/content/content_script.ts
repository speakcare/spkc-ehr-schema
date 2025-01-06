
// Extend the Window interface to include the hasInitialized property
interface Window {
  hasInitialized?: boolean;
}

let lastMessageSentTime: number = Date.now();

function sendMessageWithTimestamp(message: any) {
  chrome.runtime.sendMessage(message, () => {
    if (chrome.runtime.lastError) {
      console.error("Error sending message:", chrome.runtime.lastError);
    }
  });

  // Update the timestamp after sending the message
  lastMessageSentTime = Date.now();
  console.log(`Message sent at ${lastMessageSentTime}:`, message);
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

const inputHandler = (event: Event) => {
  const target = event.target as HTMLInputElement | HTMLTextAreaElement;
  if (!target) return;

  debounceAndThrottle(() => {
    sendMessageWithTimestamp({
      type: 'user_input',
      timestamp: new Date().toISOString(),
      inputType: target instanceof HTMLTextAreaElement ? 'textarea' : 'text',
      value: target.value,
    });
  }, 300, 5000);
};


// Add change event listener
const changeHandler = (event: Event) => {
  const target = event.target as HTMLElement;
  if (!target) return;

  debounceAndThrottle(() => {
    if (target instanceof HTMLInputElement) {
      if (target.type === 'checkbox') {
        sendMessageWithTimestamp({
          type: 'user_input',
          timestamp: new Date().toISOString(),
          inputType: 'checkbox',
          value: target.checked,
        });
      } else if (target.type === 'radio') {
        sendMessageWithTimestamp({
          type: 'user_input',
          timestamp: new Date().toISOString(),
          inputType: 'radio',
          value: target.value,
        });
      }
    } else if (target instanceof HTMLSelectElement) {
      sendMessageWithTimestamp({
        type: 'user_input',
        timestamp: new Date().toISOString(),
        inputType: 'dropdown',
        value: target.value,
      });
    }
  }, 300, 5000);
};


// Ensure only one instance of listeners
if (window.hasInitialized) {
  console.log('Cleaning up stale listeners');
  // Remove any existing listeners
  document.removeEventListener('input', inputHandler);
  document.removeEventListener('change', changeHandler);
} else {
  document.addEventListener('input', inputHandler);
  document.addEventListener('change', changeHandler);

  console.log('Content script initialized');
  window.hasInitialized = true;
}

