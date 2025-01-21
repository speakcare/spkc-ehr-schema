//import { isTabUrlPermitted, isUrlPermitted } from '../utils/hosts';
import { ActiveSession, PageLoadMessage, PageLoadResponse, UserInputMessage, 
        UserInputResponse, ActiveSessionsGetMessage, ActiveSessionsResponse,
        SessionTimeoutGetMessage, SessionTimeoutGetResponse, SessionTimeoutSetMessage, SessionTimeoutSetResponse  } from '../types/index.d';
import { logSessionEvent } from './session_log';
import { getCookieValueFromUrl } from '../utils/url_utills';
    
function calcSessionKey(userId: string, orgId: string): string {
  return `${userId}@${orgId}`;
}

  
//*****************************************************/
// Session Management Functions
// All other functions should access the activeSessions 
// table through these functions
//*****************************************************/  
let activeSessions: Record<string, ActiveSession> = {};
let activeSessionsInitialized = false;


// configrations
const defaultSessionTimeout = 180; // 3 minutes
let sessionTimeoutConfig = defaultSessionTimeout; // 3 minutes
const minSessionDuration = 1000 // 1 second

// Set session timeout and store it in local storage
export async function setSessionTimeout(timeout: number): Promise<void> {
  sessionTimeoutConfig = timeout;
  return new Promise((resolve, reject) => {
    chrome.storage.local.set({ sessionTimeout: sessionTimeoutConfig }, () => {
      if (chrome.runtime.lastError) {
        console.error('Failed to save session timeout to local storage:', chrome.runtime.lastError);
        reject(chrome.runtime.lastError);
      } else {
        resolve();
      }
    });
  });
}

// Get session timeout (synchronous)
export function getSessionTimeout(): number {
  return sessionTimeoutConfig;
}

// Load session timeout from local storage
export async function loadSessionTimeout(): Promise<number> {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get('sessionTimeout', (result) => {
      if (chrome.runtime.lastError) {
        console.error('Failed to load session timeout from local storage:', chrome.runtime.lastError);
        reject(chrome.runtime.lastError);
      } else {
        console.log('Loaded session timeout from local storage:', result.sessionTimeout || sessionTimeoutConfig);
        resolve(result.sessionTimeout || sessionTimeoutConfig);
      }
    });
  });
}


// Handle message request for timeout change
export async function handleSessionTimeoutSet(message: SessionTimeoutSetMessage, sendResponse: (response: SessionTimeoutSetResponse) => void): Promise<void> {
  try {
    console.log('Setting session timeout:', message.timeout);
    await setSessionTimeout(message.timeout);
    sendResponse({ type: 'session_timeout_set_response', success: true });
    console.log('Session timeout set successfully to:.', message.timeout);
  } catch (error) {
    console.error('Failed to set session timeout:', error);
    sendResponse({ type: 'session_timeout_set_response', success: false, error: 'Failed to set session timeout' });
  }
}

// Handle message get request for timeout
export async function handleSessionTimeoutGet(message: SessionTimeoutGetMessage, sendResponse: (response: SessionTimeoutGetResponse) => void): Promise<void> {
  try {
    const timeout = await getSessionTimeout();
    console.log('Getting session timeout:', timeout);
    sendResponse({ type: 'session_timeout_get_response', success: true, timeout });
  } catch (error) {
    console.error('Failed to get session timeout:', error);
    sendResponse({ type: 'session_timeout_get_response', success: false, timeout: null, error: 'Failed to get session timeout' });
  }
}

// Initialize session timeout from local storage
export async function initializeSessionTimeout(): Promise<void> {
  try {
    sessionTimeoutConfig = await loadSessionTimeout();
    console.log('Session timeout initialized:', sessionTimeoutConfig);
  } catch (error) {
    sessionTimeoutConfig = defaultSessionTimeout;
    console.error('Failed to initialize session timeout:', error);
  }
}


export async function getActiveSessionsFromLocalStorage(): Promise<Record<string, ActiveSession>> {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get('activeSessions', (result) => {
      if (chrome.runtime.lastError) {
        console.error('Failed to load active sessions from local storage:', chrome.runtime.lastError);
        reject(chrome.runtime.lastError);
      } else {
        const activeSessions = result.activeSessions || {};
        // Convert date strings back to Date objects
        for (const key in activeSessions) {
          if (activeSessions.hasOwnProperty(key)) {
            const session = activeSessions[key];
            session.startTime = new Date(session.startTime);
            if (session.lastActivityTime) {
              session.lastActivityTime = new Date(session.lastActivityTime);
            }
            // Make the _timer property non-enumerable
            Object.defineProperty(session, '_expirationTimer', {
              enumerable: false,
              configurable: true,
              writable: true,
              value: undefined // Initialize with undefined
            });
          }
        }
        resolve(activeSessions);
      }
    });
  });
}

// Save active sessions to storage
export async function saveActiveSessionsToLocalStorage(): Promise<void> {
  return new Promise((resolve, reject) => {
    const sessionsToSave = Object.fromEntries(
      Object.entries(activeSessions).map(([key, session]) => [
        key,
        {
          ...session,
          startTime: session.startTime.toISOString(),
          lastActivityTime: session.lastActivityTime ? session.lastActivityTime.toISOString() : null,
        },
      ])
    );
    chrome.storage.local.set({ activeSessions: sessionsToSave }, () => {
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
  await loadActiveSessions();
  activeSessionsInitialized = true;
  const sessions = getAllActiveSessions(1); // Load active sessions into memory
  // terminate all sessions on startup
  // we do this to enusre all sessions had session_ended event logged for the previous session
  for (const key in sessions) {
    if (sessions.hasOwnProperty(key)) {
      const session = sessions[key];
      terminateSession(key);
    }
  }
  initializeSessionTimeout(); // Load session timeout from local storage

  console.log('Session manager initialized.');
}

export function getAllActiveSessions(index: number): Record<string, ActiveSession> | undefined {
  if (!activeSessionsInitialized) {
    console.warn(`Attempted to access activeSessions before initialization ${index}.`);
    return undefined; // Indicate that `activeSessions` is not ready
  }
  return activeSessions;
}

function getActiveSession(sessionKey: string): ActiveSession | undefined {
  if (!activeSessionsInitialized) {
    console.warn(`Attempted to access activeSessions before initialization. sessionKey: ${sessionKey}`);
    return undefined; // Indicate that `activeSessions` is not ready
  }
  return activeSessions[sessionKey];
}

export async function handleActiveSessionsGet(message: ActiveSessionsGetMessage, sendResponse: (response: ActiveSessionsResponse) => void): Promise<void> {
  try {
    const activeSessionsRecord = getAllActiveSessions(2);
    if (activeSessionsRecord) {
      const activeSessions: ActiveSession[] = Object.values(activeSessionsRecord);      
      sendResponse({ type: 'active_sessions_get_response', success: true, activeSessions });
    } else {
      console.warn('handleActiveSessionsGet: Active sessions are not initialized.');
      sendResponse({ type: 'active_sessions_get_response', success: false, error: 'Active sessions are not initialized', activeSessions: [] });
    }
  } catch (error) {
    console.error('handleActiveSessionsGet: Unexpected error:', error);
    sendResponse({ type: 'active_sessions_get_response', success: false, error: 'Failed to retrieve active sessions', activeSessions: [] });
  }
}

function createNewSession(
  orgId: string = '',
  userId: string = '',
  startTime: Date | undefined,
): string | null {
  if (!activeSessionsInitialized) {
    console.warn('Attempted to create a new session before activeSessions initialization.');
    return null;
  }

  const newSession: ActiveSession = {
    userId,
    orgId,
    startTime: startTime ?? new Date(),
    userActivitySeen: false,
    lastActivityTime: null,
  };

  // Make the _timer property non-enumerable
  Object.defineProperty(newSession, '_expirationTimer', {
    enumerable: false,
    configurable: true,
    writable: true,
  });
  const sessionKey = calcSessionKey(userId, orgId);
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

  if (session.lastActivityTime != null) {
    // session has started and was reported so we report session end
    const endTime = session.lastActivityTime || new Date();
    const sessionDuration = endTime.getTime() - session.startTime.getTime();
    const duration = sessionDuration? sessionDuration : minSessionDuration; 
    const username = `${session.userId}@${session.orgId}`;
    logSessionEvent(
      'session_ended',
      endTime,
      endTime,
      username,
      duration
    );
  }

  if (session._expirationTimer) {
    clearTimeout(session._expirationTimer);
    delete session._expirationTimer;
  }

  // Traverse all the tabId keys in tabIdToSessionKeyMap
  for (const tabId in tabIdToSessionKeyMap) {
    if (tabIdToSessionKeyMap.hasOwnProperty(tabId)) {
      // If the value is the current sessionKey, delete the key from the map
      if (tabIdToSessionKeyMap[tabId] === sessionKey) {
        delete tabIdToSessionKeyMap[tabId];
      }
    }
  }

  const success = deleteActiveSession(sessionKey);

  if (success) {
    console.log(`Session successfully deleted for sessionKey: ${sessionKey}`);
    await saveActiveSessionsToLocalStorage(); // Persist the updated sessions
  } else {
    console.warn(`Failed to delete session for sessionKey: ${sessionKey}`);
  }
}

  

async function handleNewSession(
  orgId: string, 
  userId: string,
  startTime: Date | undefined,
): Promise<string | null> {

  if (!userId || !orgId) {
    console.warn(`handleNewSession called with no userId ${userId}, or orgId ${orgId}`);
    return null;
  }

  // If the session already exists, update the userId if provided
  const sessionKey = calcSessionKey(userId, orgId);
  const session = getActiveSession(sessionKey);
  if (session) {
    console.log(`Session already exists for sessionKey: ${sessionKey}.`);
    return sessionKey;
  }
  const newSessionKey = createNewSession(orgId, userId, startTime);
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

function setSessionExpirationTimer(sessionKey: string, expirationTimeout: number = 180) {
  // Clear any existing timer for the session
  const session = getActiveSession(sessionKey);
  if (!session) {
    console.warn(`setSessionTimer - No active session found for sessionKey: ${sessionKey}`);
    return;
  }
  if (session._expirationTimer) {
    clearTimeout(session._expirationTimer);
  }

  // Set a new timer to terminate the session after 5 minutes
  session._expirationTimer = setTimeout(() => {
    console.log(`Session expired for sessionKey: ${sessionKey}`);
    terminateSession(sessionKey);
  }, expirationTimeout * 1000);
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
    const username = `${session.userId}@${session.orgId}`;
    const now = new Date();
    console.log(`Initial user activity detected on ${sessionKey} at ${timestamp}. Logging session start.`);
    logSessionEvent('session_started', session.startTime, now, username);
  }
  session.lastActivityTime = timestamp; // Update in memory
  setSessionExpirationTimer(sessionKey, getSessionTimeout()); // Reset the session timer
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



/**************************/
// Event Listeners & Handlers
/**************************/

const tabIdToSessionKeyMap: Record<number, string> = {}; // Maps tabId to session key

chrome.tabs.onRemoved.addListener(async (tabId) => {
  console.log(`Tab closed: ${tabId}`);

  // TODO check if I can filter by URL here?
  const sessionKey = tabIdToSessionKeyMap[tabId];
  if (sessionKey) {
    await flushPendingUpdate(sessionKey);
    console.log(`Flushed pending updates for sessionKey: ${sessionKey} on tab close.`);
    delete tabIdToSessionKeyMap[tabId];
  } else {
    // This tab was not of a permitted URL and is not under tracking
    // console.warn(`No sessionKey found for tabId: ${tabId}`);
  }
});

async function findOrCreateSession(
  tabId: number,
  sender: chrome.runtime.MessageSender,
  userId: string,
  startTime: Date,
  sendResponse: (response?: any) => void

): Promise<string | null> {
  const senderTabUrl = sender.tab?.url || '';
  const url = new URL(senderTabUrl);
  const domain = url.hostname;
  const orgIdFromCookie = await getCookieValueFromUrl('last_org', senderTabUrl);

  if (!orgIdFromCookie) {
    console.warn('Failed to recover orgId from cookie.');
    sendResponse({ success: false, error: 'orgId not found' });
    return null;
  }

  console.log(`Got orgId ${orgIdFromCookie} from cookie for tabId ${tabId}`);
  let sessionKey = calcSessionKey(userId, orgIdFromCookie);
  const session = getActiveSession(sessionKey);
  if (!session) {
    // no session yet, create a new one
    console.log(`findOrCreateSession did not find sesssion for key ${sessionKey} 
                user input message for a non existing session. Creating a new session.`);
    const newSessionKey = await handleNewSession(orgIdFromCookie, userId, startTime);
    if (newSessionKey) {
      sessionKey = newSessionKey;
      setSessionExpirationTimer(sessionKey, getSessionTimeout());
    } else { 
      console.error('chrome.runtime.onMessage: Failed to create a new session.');
      sendResponse({ success: false, error: 'Failed to create a new session' });
      return null;
    }
  }
  return sessionKey;
}

export async function handlePageLoad(
  message: PageLoadMessage, 
  sender: chrome.runtime.MessageSender, 
  sendResponse: (response: PageLoadResponse) => void): Promise<void> 
{
  const { username, pageStartTime } = message;
  const tabId = sender.tab?.id;

  if (tabId === undefined) {
    console.error('handlePageLoad: tabId is undefined.');
    sendResponse({ type: 'page_load_response', success: false, error: 'tabId is undefined' });
    return;
  }

  try {
    const sessionKey = await findOrCreateSession(tabId, sender, username, new Date(pageStartTime), sendResponse);

    if (sessionKey) {
      tabIdToSessionKeyMap[tabId] = sessionKey;
      sendResponse({ type: 'page_load_response', success: true });
    } else {
      console.error(`handlePageLoad: Failed to find or create session for username ${username}.`);
      if (tabIdToSessionKeyMap[tabId]) {
        delete tabIdToSessionKeyMap[tabId]; // Remove invalid session
      }
      sendResponse({ type: 'page_load_response', success: false, error: 'Failed to create a new session' });
    }
  } catch (error) {
    console.error(`handlePageLoad: Unexpected error for tabId ${tabId}:`, error);
    sendResponse({ type: 'page_load_response', success: false, error: 'An unexpected error occurred' });
  }
}

export async function handleUserInput(
  message: UserInputMessage, 
  sender: chrome.runtime.MessageSender, 
  sendResponse: (response: UserInputResponse) => void): Promise<boolean> 
{

  const tabId = sender.tab?.id;
  if (tabId === undefined) {
    console.error('handleUserInput: tabId is undefined.');
    sendResponse({ type: 'user_input_response', success: false, error: 'tabId is undefined' });
    return false;
  }

  let sessionKeyFromTab = tabIdToSessionKeyMap[tabId];
  if (sessionKeyFromTab) {
    // Optimistic synchronous flow
    processUserInputMessage(message, sessionKeyFromTab, sendResponse);
    return false; // No need to keep the message channel open
  } else {
    console.log(`No sessionKey found for tabId: ${tabId}. Searching for it in session table.`);

    try {
      // Fallback: Retrieve sessionId asynchronously
      const sessionKey = await findOrCreateSession(tabId, sender, message.username, new Date(message.timestamp), sendResponse);
      if (sessionKey) {
        tabIdToSessionKeyMap[tabId] = sessionKey;
        processUserInputMessage(message, sessionKey, sendResponse);
      } else {
        console.error(`handleUserInput: Failed to find or create session for username ${message.username}.`);
        sendResponse({ type: 'user_input_response', success: false, error: 'Failed to create a new session' });
      }
    } catch (error) {
      console.error(`handleUserInput: Unexpected error for tabId ${tabId}:`, error);
      sendResponse({ type: 'user_input_response', success: false, error: 'An unexpected error occurred' });
    }

    // Return true to keep the message channel open for asynchronous handling
    return true;
  }
}



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
  console.log(`User activity detected on ${sessionKey} at ${message.timestamp}`);
  updateLastActivity(sessionKey, new Date(message.timestamp));

  // Explicitly respond to the message
  sendResponse({ success: true, message });
}


// Exported functions to globnal scope
// Attach the function to the global scope
(globalThis as any).getAllActiveSessions = getAllActiveSessions;
