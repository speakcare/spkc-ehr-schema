import { isTabUrlPermitted, isUrlPermitted } from '../utils/hosts';

interface Session {
    domain: string;
    userId: string;
    startTime: Date; // the actual start time when the session was created
    userActivitySeen: boolean; // Flag to indicate if user activity has been seen - used to determine session start
    lastActivityTime: Date | null;
}
    
function calcSessionKey(userId: string, domain: string): string {
  return `${userId}@${domain}`;
}

  
//*****************************************************/
// Session Management Functions
// All other functions should access the activeSessions 
// table through these functions
//*****************************************************/  
let activeSessions: Record<string, Session> = {};
let activeSessionsInitialized = false;

// Load active sessions from storage
export async function getActiveSessionsFromLocalStorage(): Promise<Record<string, Session>> {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get('activeSessions', (result) => {
      if (chrome.runtime.lastError) {
        console.error('Failed to load active sessions from local storage:', chrome.runtime.lastError);
        reject(chrome.runtime.lastError);
      } else {
        resolve(result.activeSessions || {});
      }
    });
  });
}

// Save active sessions to storage
export async function saveActiveSessionsToLocalStorage(): Promise<void> {
  return new Promise((resolve, reject) => {
    chrome.storage.local.set({ activeSessions }, () => {
      if (chrome.runtime.lastError) {
        console.error('Failed to save active sessions to local storage:', chrome.runtime.lastError);
        reject(chrome.runtime.lastError);
      } else {
        resolve();
      }
    });
  });
}
  // Load active sessions from local storage
async function loadActiveSessions(): Promise<void> {
  activeSessions = await getActiveSessionsFromLocalStorage();
  console.log('Loaded active sessions:', activeSessions);
}

export async function initializeSessionManager() {
  console.log('Initializing session manager...');
  await loadActiveSessions(); // Load active sessions into memory
  activeSessionsInitialized = true;
  console.log('Session manager initialized.');
}

function getActiveSession(sessionKey: string): Session | undefined {
  if (!activeSessionsInitialized) {
    console.warn(`Attempted to access activeSessions before initialization. sessionKey: ${sessionKey}`);
    return undefined; // Indicate that `activeSessions` is not ready
  }
  return activeSessions[sessionKey];
}

function createNewSession(
  domain: string,
  userId: string = ''
): string | null {
  if (!activeSessionsInitialized) {
    console.warn('Attempted to create a new session before activeSessions initialization.');
    return null;
  }

  const newSession: Session = {
    domain,
    userId,
    startTime: new Date(),
    userActivitySeen: false,
    lastActivityTime: null,
  };
  const sessionKey = calcSessionKey(userId, domain);
  activeSessions[sessionKey] = newSession;
  console.log(`New session created for sessionKey: ${sessionKey}`, newSession);

  return sessionKey;
}
  
  
function deleteActiveSession(sessionKey: string): boolean {
  if (!activeSessionsInitialized) {
    console.warn('Attempted to delete a session before activeSessions initialization.');
    return false;
  }

  if (!activeSessions[sessionKey]) {
    console.warn(`No session found for sessionKey: ${sessionKey}. Deletion skipped.`);
    return false;
  }

  delete activeSessions[sessionKey];
  console.log(`Session deleted for sessionKey: ${sessionKey}`);
  return true;
}
  

async function terminateSession(sessionKey: string) {
  const session = getActiveSession(sessionKey);

  if (!session) {
    console.warn(`No active session found for sessionKey: ${sessionKey}`);
    return;
  }

  const endTime = session.lastActivityTime || new Date();
  const duration = endTime.getTime() - session.startTime.getTime();
  
  logEvent(
    session.domain,
    'session_ended',
    endTime,
    session.userId,
    duration // Calculated duration
  );

  const success = deleteActiveSession(sessionKey);
  if (success) {
    console.log(`Session successfully deleted for sessionKey: ${sessionKey}`);
    await saveActiveSessionsToLocalStorage(); // Persist the updated sessions
  } else {
    console.warn(`Failed to delete session for sessionKey: ${sessionKey}`);
  }
}

  
export async function logEvent(
  domain: string,
  event: 'session_started' | 'session_ended',
  timestamp: Date,
  userId: string,
  duration: number = 0, // Default to 0 for session_started
  extraData?: Record<string, any>
) {
  const eventLog = {
    domain,
    event,
    timestamp: timestamp.toISOString(),
    userId,
    duration,
    ...extraData, // Auxiliary metadata
  };

  try {
    const logs = await getSessionLogs();
    logs.push(eventLog); // Append the new log event
    await saveSessionLogs(logs);
    console.log('Event logged:', eventLog);
  } catch (error) {
    console.error('Failed to log event:', error);
  }
}


// Helper to get all session logs from storage
export async function getSessionLogs(): Promise<any[]> {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get('session_logs', (result) => {
      if (chrome.runtime.lastError) {
        console.error('Failed to get session logs from local storage', chrome.runtime.lastError);
        reject(chrome.runtime.lastError);
      } else {
        resolve(result.session_logs || []);
      }
    });
  });
}


// Helper to save session logs to storage
async function saveSessionLogs(logs: any[]): Promise<void> {
  return new Promise((resolve, reject) => {
    chrome.storage.local.set({ session_logs: logs }, () => {
      if (chrome.runtime.lastError) {
        console.error('Failed to save session logs to local storage:', chrome.runtime.lastError);
        reject(chrome.runtime.lastError);
      } else {
        resolve();
      }
    });
  });
}


async function handleNewSession(domain: string, /*sessionId?: string,*/ userId: string): Promise<string | null> {

  if (!domain || !userId) {
    console.warn(`handleNewSession called with no domain ${domain} or no userId ${userId}`);
    return null;
  }

  // If the session already exists, update the userId if provided
  const sessionKey = calcSessionKey(userId, domain);
  const session = getActiveSession(sessionKey);
  if (session) {
    console.log(`Session already exists for sessionKey: ${sessionKey}.`);
    if (session.userId !== userId || session.domain !== domain) {
      // this should never happen
      console.warn(`Session for sessionKey: ${sessionKey} found with different userId: ${session.userId} or different domain: ${session.domain}`);
      // recover this
      session.domain = domain;
      session.userId = userId;
      console.log(`Updated userId for domain: ${domain} to ${userId}`);
      await saveActiveSessionsToLocalStorage();
    }
    return sessionKey;
  }
  const newSessionKey = createNewSession(/*sessionId,*/ domain, userId || '');
  if (!newSessionKey) {
    console.error('Failed to create a new session.');
    return null;
  }
  const newSession = getActiveSession(newSessionKey);
  if (newSession) {
    console.log('Session successfully created:', newSession);
    await saveActiveSessionsToLocalStorage(); // Persist the updated sessions
    return newSessionKey; 
  } else {
    console.error('Failed to create a new session.');
    return null;
  }    
}



const debouncedUpdates: Record<string, NodeJS.Timeout> = {};
export function updateLastActivity(sessionKey: string, timestamp: Date) {
  console.log(`Updating last activity for sessionKey: ${sessionKey} at ${timestamp}`);

  const session = getActiveSession(sessionKey);
  if (!session) {
    console.warn(`No active session found for sessionKey: ${sessionKey}`);
    return;
  }
  if (!session.userActivitySeen) {
    // mark first activity time - we log the session start only once there is activity otherwise the session is not considered started
    session.userActivitySeen = true;
    logEvent(session.domain, 'session_started', session.startTime, session.userId || '');
  }
  session.lastActivityTime = timestamp; // Update in memory
  // Debounce the persistence
  if (debouncedUpdates[sessionKey]) {
    clearTimeout(debouncedUpdates[sessionKey]);
  }

  debouncedUpdates[sessionKey] = setTimeout(() => {
    persistLastActivity(sessionKey, timestamp);
  }, 3000); // Delay of 3 seconds
}

  
// Immediately flush updates for a specific sessionKey
async function flushPendingUpdate(sessionKey: string) {
  if (debouncedUpdates[sessionKey]) {
    clearTimeout(debouncedUpdates[sessionKey]);
    delete debouncedUpdates[sessionKey];
  }
  const session = getActiveSession(sessionKey);
  if (session && session.lastActivityTime) {
    await persistLastActivity(sessionKey, session.lastActivityTime); // Persist latest in-memory state
    console.log(`Flushed last activity time for sessionKey ${sessionKey}`);
  } else {
    console.warn(`No active session found for sessionKey: ${sessionKey}`);
  }
}


export async function persistLastActivity(sessionKey: string, timestamp: Date) {
  const session = getActiveSession(sessionKey);

  if (session) {
    session.lastActivityTime = timestamp;
    await saveActiveSessionsToLocalStorage(); // Persist updated table
    console.log(`Persisted last activity time for sessionKey ${sessionKey}: ${timestamp}`);
  } else {
    console.warn(`Session not found for sessionKey ${sessionKey}. Unable to persist last activity.`);
  }
}


// Helper function to get a cookie value from a specific URL

async function getCookieValueFromUrl(cookieName: string, url: string): Promise<string | null> {
  return new Promise((resolve, reject) => {
    chrome.cookies.get({ url, name: cookieName }, (cookie) => {
      if (chrome.runtime.lastError) {
        console.error(`Failed to get cookie ${cookieName} from ${url}:`, chrome.runtime.lastError.message);
        reject(chrome.runtime.lastError);
        return;
      }
      resolve(cookie?.value || null);
    });
  });
}

async function getCookieFromUrl(cookieName: string, url: string): Promise<chrome.cookies.Cookie | null> {
  return new Promise((resolve, reject) => {
    chrome.cookies.get({ url, name: cookieName }, (cookie) => {
      if (chrome.runtime.lastError) {
        console.error(`Failed to get cookie ${cookieName} from ${url}:`, chrome.runtime.lastError.message);
        reject(chrome.runtime.lastError);
        return;
      }
      resolve(cookie|| null);
    });
  });
}

/**************************/
// Event Listeners & Handlers
/**************************/

const tabSessionKey: Record<number, string> = {}; // Maps tabId to domain

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (!tab.url) {
    console.log(`Ignoring tab update for tabId: ${tabId} with no url.`);
    return;
  }
  const isPermitted = isUrlPermitted(tab.url);
  const thisTabSessionKey = tabSessionKey[tabId];

  if (changeInfo.status === 'loading' && tab.url) {
    console.log(`Tab started loading: ${tab.url} (tabId: ${tabId})`);
    
    if (thisTabSessionKey) {
      await flushPendingUpdate(thisTabSessionKey);
      console.log(`Flushed pending updates for sessionKey: ${thisTabSessionKey} before navigation.`);
    }
    if (!isPermitted && thisTabSessionKey) {
      // navigating away from a previously allowed url
      console.log(`URL not allowed: ${tab.url}. remove this tab session.`);
      delete tabSessionKey[tabId]; // Remove the mapping
    }
  }

  if (changeInfo.status === 'complete' && tab.url) {
    console.log(`Tab finished loading: ${tab.url} (tabId: ${tabId})`);

    // Refresh session context
    if (isPermitted) {
      const cookieUserId = await getCookieValueFromUrl('last_org', tab.url);
      if (cookieUserId) {
        const url = new URL(tab.url);
        const domain = url.hostname;
        const sessionKey = calcSessionKey(cookieUserId, domain);
        const session = getActiveSession(sessionKey);
        if (session) {
          // Session already exists, only update the sessionId mapping to this tab
          tabSessionKey[tabId] = sessionKey; // Update session mapping
          console.log(`Updated sessionKey for tabId ${tabId} to ${sessionKey}`);
        }
        else {
          // No active session yet, create a new session
          console.log(`Creating new session for tabId ${tabId} with domain ${domain} and userId ${cookieUserId}`);
          const newSessionKey = await handleNewSession(domain, /*cookieSessionId,*/ cookieUserId);
          if (newSessionKey) {
             tabSessionKey[tabId] = newSessionKey; // Update session mapping
          }
          else {
            console.error('chrome.tabs.onUpdated: Failed to create a new session.');
          }
        }
      } 
      else if (tabSessionKey[tabId]) {
        // this tab was previously on active session key but no longer is, so we remove the session
        console.warn(`No userId cookie found. for tabId ${tabId}. Removing mapping.`);
        delete tabSessionKey[tabId];
      }
    }
    else if (tabSessionKey[tabId]) {
      // note allowed but there is still a sessionid on this tab - remove it
      console.log(`URL not allowed: ${tab.url}. remove this tab sessionKey.`);
      delete tabSessionKey[tabId]; // Remove the
    }
  }
});


chrome.tabs.onRemoved.addListener(async (tabId) => {
  console.log(`Tab closed: ${tabId}`);

  const sessionKey = tabSessionKey[tabId];
  if (sessionKey) {
    await flushPendingUpdate(sessionKey);
    console.log(`Flushed pending updates for sessionKey: ${sessionKey} on tab close.`);
  } else {
    console.warn(`No sessionKey found for tabId: ${tabId}`);
  }

  delete tabSessionKey[tabId]; // Cleanup mapping for the closed tab
});


chrome.runtime.onMessage.addListener((
  message: any,
  sender: chrome.runtime.MessageSender,
  sendResponse: (response?: any) => void
): boolean | void => {
  console.log('Received message from content script:', message);

  // Check for valid message type
  if (message.type !== 'user_input') {
    console.warn(`Invalid message type: ${message.type}`);
    sendResponse({ success: false, error: 'Invalid message type' });
    return;
  }

  // Check for sender's tabId
  const tabId = sender.tab?.id;
  if (!tabId) {
    console.warn('Message received without a valid tabId. Cannot process.');
    sendResponse({ success: false, error: 'Missing tabId' });
    return;
  }

  // Attempt to fetch sessionId from the tabSessionId map
  let sessionKey = tabSessionKey[tabId];
  if (!sessionKey) {
    // Optimistic synchronous flow
    processUserInputMessage(message, sessionKey,/*sessionId,*/ sendResponse);
  }
  else { // no sessionKey found for this tab 
    console.warn(`No sessionKey found for tabId: ${tabId}. Attempting fallback to cookie.`);

    // Fallback: Retrieve sessionId asynchronously
    (async () => {
      const senderTabUrl = sender.tab?.url || '';
      const url = new URL(senderTabUrl);
      const domain = url.hostname;
      const userIdFromCookie = await getCookieValueFromUrl('last_org', senderTabUrl);
      if (!userIdFromCookie) {
        console.warn('Failed to recover userId from cookie.');
        sendResponse({ success: false, error: 'userId not found' });
        return;
      }
      console.log(`Recovered userId ${userIdFromCookie} from cookie for tabId ${tabId}`);
      sessionKey = calcSessionKey(userIdFromCookie, domain);
      tabSessionKey[tabId] = sessionKey; // Update tabSessionKey map

      // Process the message with the resolved sessionId
      processUserInputMessage(message, sessionKey, sendResponse);
    })();
    // Return true to keep the message channel open for asynchronous handling
    return true;
  }
});


// Shared function to process user input messages
function processUserInputMessage(
  message: any,
  //sender: chrome.runtime.MessageSender,
  sessionKey: string,
  sendResponse: (response?: any) => void
) {
  // Check for valid message type
  if (message.type !== 'user_input') {
    console.warn(`processUserInputMessage called with invalid message type: ${message.type}`);
    sendResponse({ success: false, error: 'Invalid message type' });
    return;
  }
  console.log(`DOM change detected on ${sessionKey} at ${message.timestamp}`);
  updateLastActivity(sessionKey, new Date(message.timestamp));

  // Explicitly respond to the message
  sendResponse({ success: true, message });
}

// function getdomainForTab(tabId: number): Promise<string | null> {
//   return new Promise((resolve) => {
//     chrome.tabs.get(tabId, (tab) => {
//       if (chrome.runtime.lastError || !tab.url) {
//         console.warn(`Failed to get tab information for tabId: ${tabId}`);
//         resolve(null);
//         return;
//       }

//       try {
//         const url = new URL(tab.url);
//         resolve(url.hostname); // Directly return the hostname
//       } catch (err) {
//         console.error(`Error parsing URL for tabId: ${tabId}`, err);
//         resolve(null);
//       }
//     });
//   });
// }

// export function manageSession(cookie: chrome.cookies.Cookie) {
  //   if (cookie.name === 'JSESSIONID') {
  //     handleLogin(cookie.value, cookie.domain);
  //   } else if (cookie.name === 'last_org') {
  //     handleUserIdChange(cookie.domain);
  //   }
  // }
  
  // function handleLogin(sessionId: string, domain: string) {
  //   if (activeSessions[sessionId]) {
  //     console.log(`Session already exists for sessionId: ${sessionId}. Ignoring login event.`);
  //     return; // Skip processing
  //   }
  
  //   // Create a new session
  //   activeSessions[sessionId] = {
  //     sessionId,
  //     domain,
  //     userId: '',
  //     startTime: new Date(),
  //     lastActivityTime: null,
  //   };
  
  //   logEvent(domain, 'session_started', activeSessions[sessionId].startTime, {
  //     sessionId,
  //   });
  // }


  // async function handleLogin(sessionId: string, domain: string) {
  //   const activeSessions = await getActiveSessions();
  
  //   if (activeSessions[sessionId]) {
  //     console.log(`Session already exists for sessionId: ${sessionId}. Ignoring login event.`);
  //     return; // Skip processing
  //   }
  
  //   activeSessions[sessionId] = {
  //     sessionId,
  //     domain,
  //     userId: '',
  //     startTime: new Date(),
  //     lastActivityTime: null,
  //   };
  
  //   await saveActiveSessions(activeSessions); // Persist the updated table
  //   logEvent(
  //     domain,
  //     'session_started',
  //     new Date(),
  //     sessionId,
  //     userId
  //   );

  //   logEvent(domain, 'session_started', activeSessions[sessionId].startTime, {
  //     sessionId,
  //   });
  // }
  
  // function handleUserIdChange(domain: string) {
  //   // Retrieve the sessionId from the JSESSIONID cookie
  //   chrome.cookies.get(
  //     { url: `https://${domain}`, name: 'JSESSIONID' },
  //     (cookie) => {
  //       if (!cookie || !cookie.value) {
  //         console.warn(`No JSESSIONID cookie found for domain: ${domain}`);
  //         return;
  //       }
  
  //       const sessionId = cookie.value;
  //       const session = activeSessions[sessionId];
  //       if (!session) {
  //         console.warn(`No active session found for sessionId: ${sessionId}`);
  //         return;
  //       }
  
  //       // Retrieve the userId from the last_org cookie
  //       chrome.cookies.get(
  //         { url: `https://${domain}`, name: 'last_org' },
  //         (userCookie) => {
  //           if (userCookie && userCookie.value) {
  //             session.userId = userCookie.value;
  
  //             logEvent(domain, 'session_started', session.startTime, {
  //               sessionId,
  //               userId: session.userId,
  //             });
  //           }
  //         }
  //       );
  //     }
  //   );
  // }
  
  // function terminateSession(sessionId: string) {
  //   const session = activeSessions[sessionId];
  //   if (!session) return;
  
  //   const endTime = session.lastActivityTime || new Date();
  //   const duration = endTime.getTime() - session.startTime.getTime();
  
  //   logEvent(session.domain, 'session_ended', endTime, {
  //     sessionId: session.sessionId,
  //     userId: session.userId,
  //     duration,
  //   });
  
  //   delete activeSessions[sessionId];
  // }
  
  // Log an event to storage
// export async function logEvent(
//   domain: string,
//   event: string,
//   timestamp: Date,
//   extraData?: Record<string, any>
// ) {
//   const eventLog = {
//     domain,
//     event,
//     timestamp: timestamp.toISOString(),
//     ...extraData,
//   };

//   try {
//     const logs = await getSessionLogs();
//     logs.push(eventLog);
//     await saveSessionLogs(logs);
//     console.log('Event logged:', eventLog);
//   } catch (error) {
//     console.error('Failed to log event:', error);
//   }
// }

// export function updateLastActivity(domain: string, timestamp: Date) {
//   const session = activeSessions[domain];
//   if (!session) {
//     console.warn(`No active session found for domain: ${domain}`);
//     return;
//   }

//   session.lastActivityTime = timestamp;
//   console.log(`Updated last activity time for ${domain}: ${timestamp}`);

//   // Debounce the persistence
//   if (debouncedUpdates[domain]) {
//     clearTimeout(debouncedUpdates[domain]);
//   }

//   debouncedUpdates[domain] = setTimeout(() => {
//     persistLastActivity(domain, timestamp);
//   }, 3000); // Delay of 3 seconds
// }

// Function to persist the last activity time
// async function persistLastActivity(sessionId: string, timestamp: Date) {
//   const logs = await getSessionLogs();
//   const session = logs.find(
//     (log) => log.event === 'session_started' && log.sessionId === sessionId
//   );

//   if (session) {
//     session.lastActivityTime = timestamp.toISOString();
//     await saveSessionLogs(logs);
//     console.log(`Persisted last activity time for sessionId ${sessionId}: ${timestamp}`);
//   }
// }

// Listen for DOM change messages from content scripts
// chrome.runtime.onMessage.addListener((
//   message: any,
//   sender: chrome.runtime.MessageSender,
//   sendResponse: (response?: any) => void
// ): boolean | void => {
//     console.log('Received message from content script:', message);
    
//     // Check for sender's tabId
//     const tabId = sender.tab?.id;
//     if (!tabId) {
//       console.warn('Message received without a valid tabId. Cannot process.');
//       sendResponse({ success: false, error: 'Missing tabId' });
//       return;
//     }

//     // Lookup sessionId in tabSessionId
//     const sessionId = tabSessionId[tabId];
    
//     if (!sessionId) {
//       console.warn(`No sessionId found for tabId: ${tabId}`);
//       sendResponse({ success: false, error: 'SessionId not found' });
//       return;
//     }

//     // Enrich the message with sessionId
//     const enrichedMessage = { ...message, sessionId };

//     if (enrichedMessage.type === 'user_input' && sender.tab) {
//       const url = new URL(sender.tab.url || '');
//       const domain = url.hostname;

//       console.log(`DOM change detected on ${domain} sessionId ${sessionId} at ${message.timestamp}`);
//       updateLastActivity(sessionId, new Date(message.timestamp));
//       // Explicitly respond to the message
//       sendResponse({ success: true });

//     } else {
//       console.warn('Unhandled message type:', message.type);
//       sendResponse({ success: false, error: 'Unhandled message type' });
//     }

//     // Return true to indicate that we may respond asynchronously
//     return true;
// });

// chrome.tabs.onRemoved.addListener(async (tabId) => {
//   console.log(`Tab closed: ${tabId}`);
  
//   // Find the domain associated with the tab (if needed)
//   //const domain = await getdomainForTab(tabId); // Implement as needed
//   const domain = tabdomains[tabId];
  
//   if (domain) {
//     await flushPendingUpdate(domain);
//     console.log(`Flushed lastActivityTime for ${domain} before tab closed.`);
//   }
//   // Remove the tab from the map
//   delete tabdomains[tabId];
// });

// chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
//   if (changeInfo.status === 'loading' && tab.url) {
//     console.log(`Tab navigation detected: ${tabId}`);
    
//     const domain = await getdomainForTab(tabId);
    
//     if (domain) {
//       tabdomains[tabId] = domain;
//       await flushPendingUpdate(domain);
//       console.log(`Flushed lastActivityTime for ${domain} before navigation.`);
//     }
//   }
// });

// chrome.runtime.onMessage.addListener((
//   message: any,
//   sender: chrome.runtime.MessageSender,
//   sendResponse: (response?: any) => void
// ): boolean | void => {
//   console.log('Received message from content script:', message);

//   // Check for valid message type
//   if (message.type !== 'user_input') {
//     console.warn(`Invalid message type: ${message.type}`);
//     sendResponse({ success: false, error: 'Invalid message type' });
//     return;
//   }

//   // Check for sender's tabId
//   const tabId = sender.tab?.id;
//   if (!tabId) {
//     console.warn('Message received without a valid tabId. Cannot process.');
//     sendResponse({ success: false, error: 'Missing tabId' });
//     return;
//   }

//   // Attempt to fetch sessionId from the tabSessionId map
//   let sessionId = tabSessionId[tabId];
//   if (!sessionId) {
//     console.warn(`No sessionId found for tabId: ${tabId}. Attempting fallback to cookies.`);

//     // Fallback: Retrieve sessionId from the cookie
//     const url = sender.tab?.url || '';
//     chrome.cookies.get({ url, name: 'JSESSIONID' }, (cookie) => {
//       sessionId = cookie?.value || '';

//       if (!sessionId) {
//         console.warn('Failed to recover sessionId from cookies.');
//         sendResponse({ success: false, error: 'SessionId not found' });
//         return;
//       }

//       console.log(`Recovered sessionId from cookie for tabId ${tabId}`);
//       tabSessionId[tabId] = sessionId; // Update tabSessionId map

//       // Process the message with the resolved sessionId
//       processUserInputMessage(message, sender, sessionId, sendResponse);
//     });

//     // Return true to keep the message channel open for asynchronous cookie retrieval
//     return true;
//   }
//   // Process the message with the sessionId found in tabSessionId
//   processUserInputMessage(message, sender, sessionId, sendResponse);
// });

