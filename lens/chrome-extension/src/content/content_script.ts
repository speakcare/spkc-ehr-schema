
// Extend the Window interface to include the hasInitialized property
// interface Window {
//   hasInitialized?: boolean;
// }



let lastMessageSentTime: number = Date.now();

async function sendMessageWithTimestamp(message: any) {
  try {

    // Send the message to the background script
    chrome.runtime.sendMessage(message, (response) => {
      if (chrome.runtime.lastError) {
        console.error('Error sending message:', chrome.runtime.lastError.message);
      } else if (response?.success) {
        console.log(`Message sent successfully:`, response.enrichedMessage);
      } else {
        console.warn('Failed to enrich and send message:', response?.error);
      }
    });

    console.log(`Message sent at ${new Date().toISOString()}:`, message);
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


// Remmove existing event listeners in case they were added by previous loading of the script
document.removeEventListener('input', inputHandler);
document.removeEventListener('change', changeHandler);

// Attach new event listeners
document.addEventListener('input', inputHandler);
document.addEventListener('change', changeHandler);

console.log('Content script initialized or re-initialized');
