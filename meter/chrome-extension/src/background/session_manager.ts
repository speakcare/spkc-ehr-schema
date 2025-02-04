import { BasicResponse } from '../types';
//import { UserSession, UserSessionDTO } from './sessions';
//import { logSessionEvent } from './session_log';
import { getCookieValueFromUrl } from '../utils/url_utills';
import { DailyUsage } from './daily_usage';
import { DebounceThrottle } from '../utils/debounce';
import { Logger } from '../utils/logger';
    

import { PageLoadMessage, PageLoadResponse, UserInputMessage, UserInputResponse, 
        SessionsGetMessage, SessionsResponse, 
        SessionTimeoutSetMessage, SessionTimeoutSetResponse, 
        SessionTimeoutGetMessage, SessionTimeoutGetResponse } from '../types/messages';
import { SessionStrategy, UserSessionStrategy, ChartSessionStrategy } from './session_strategy';
import { LocalStorage } from '../utils/local_stroage'; //'../utils/local_storage';
import { SessionFactory } from './session_factory'; //'./session_factory';
import { ActiveSession } from './sessions';
import { SessionType } from './sessions';


export class SessionManager {
  private managerName: string;
  private sessionFactory: SessionFactory;
  private sessionStrategy: SessionStrategy;
  private sessionsLocalStorage: LocalStorage;
  private sessionTimeoutLocalStorage: LocalStorage;
  private sessions: Record<string, ActiveSession> = {};
  private tabIdToSessionKeyMap: Record<number, string> = {}; //
  private sessionsLoaded = false;
  private debouncedUpdates: DebounceThrottle;// = new DebounceThrottle(3000, 10000);
  private sessionTimeoutConfig = 180; // Default to 3 minutes
  private readonly minSessionDuration = 1000; // 1 second
  private logger: Logger;

  constructor(
    sessionStrategy: SessionStrategy, 
    managerName: string,
    debounceDelay: number = 3000,
    debounceMaxDelay: number = 10000,
    sessionTimeout: number = 180
  ) {
    this.managerName = managerName;
    const localStorageKey = managerName+':local_storage';
    this.sessionFactory = new SessionFactory();
    this.sessionsLocalStorage = new LocalStorage(localStorageKey);
    this.sessionTimeoutLocalStorage = new LocalStorage(localStorageKey+':session_timeout');
    this.sessionStrategy = sessionStrategy;
    this.debouncedUpdates = new DebounceThrottle(debounceDelay, debounceMaxDelay);
    this.sessionTimeoutConfig = sessionTimeout;
    this.logger = new Logger(managerName);
  }

  // Private Methods

  // Session Timeout Management
  private async setSessionTimeout(timeout: number): Promise<void> {
    this.sessionTimeoutConfig = timeout;
    await this.sessionTimeoutLocalStorage.setItem(timeout);
  }


  private getSessionTimeout(): number {
    return this.sessionTimeoutConfig;
  }

  private async loadSessionTimeout(): Promise<number> {
    const timeout = await this.sessionTimeoutLocalStorage.getItem();
    this.sessionTimeoutConfig = timeout || this.sessionTimeoutConfig;
    return this.sessionTimeoutConfig;
  }

  private async initializeSessionTimeout(): Promise<void> {
    try {
      this.sessionTimeoutConfig = await this.loadSessionTimeout();
      this.logger.log('Session timeout initialized:', this.sessionTimeoutConfig);
    } catch (error) {
      this.sessionTimeoutConfig = 180; // Default to 3 minutes
      this.logger.error('Failed to initialize session timeout:', error);
    }
  }

  // Active Session Management
  private async getSessionsFromLocalStorage(): Promise<Record<string, ActiveSession>> {
    const activeSessions = await this.sessionsLocalStorage.getItem();
    const sessions: Record<string, ActiveSession> = {};
    for (const key in activeSessions) {
      if (activeSessions.hasOwnProperty(key)) {
        const sessionDTO = activeSessions[key];
        sessions[key] = this.sessionFactory.createSession(this.sessionStrategy.getSessionType(), sessionDTO);
      }
    }
    return sessions;
  }

  private async saveSessionsToLocalStorage(): Promise<void> {
    const sessionsToSave = Object.fromEntries(
      Object.entries(this.sessions).map(([key, session]) => [key, session.serialize()])
    );
    await this.sessionsLocalStorage.setItem(sessionsToSave);
  }

  private async loadActiveSessions(): Promise<void> {
    this.sessions = await this.getSessionsFromLocalStorage();
    this.logger.log('Loaded active sessions:', this.sessions);
  }

  // Session Operations
  public getAllSessions(): Record<string, ActiveSession> | undefined {
    if (!this.sessionsLoaded) {
      this.logger.warn('Attempted to access activeSessions before initialization.');
      return undefined;
    }
    return this.sessions;
  }


  private getSession(sessionKey: string): ActiveSession | undefined {
    if (!this.sessionsLoaded) {
      this.logger.warn(`Attempted to access activeSessions before initialization. sessionKey: ${sessionKey}`);
      return undefined;
    }
    return this.sessions[sessionKey];
  }

  private createSession(orgId: string = '', userId: string = '', startTime: Date, additionalParams: any = {}): string | null {
    if (!this.sessionsLoaded) {
      this.logger.warn('Attempted to create a new session before activeSessions initialization.');
      return null;
    }

    const newSession = this.sessionFactory.createSession(this.sessionStrategy.getSessionType(), {
      userId,
      orgId,
      startTime,
      ...additionalParams
    });

    const sessionKey = newSession.getSessionKey();
    this.sessions[sessionKey] = newSession;
    DailyUsage.reportSession(newSession);
    this.logger.log(`New session created for sessionKey: ${sessionKey}`, newSession);

    return sessionKey;
  }

  private deleteActiveSession(sessionKey: string): boolean {
    if (!this.sessionsLoaded) {
      this.logger.warn('Attempted to delete a session before activeSessions initialization.');
      return false;
    }

    if (!this.sessions[sessionKey]) {
      this.logger.warn(`No session found for sessionKey: ${sessionKey}. Deletion skipped.`);
      return false;
    }

    delete this.sessions[sessionKey];
    this.logger.log(`Session deleted for sessionKey: ${sessionKey}`);
    return true;
  }

  private async reportToSessionLog(
    event: 'session_started' | 'session_ended' | 'session_onging', 
    eventTime: Date,
    logTime: Date,
    username: string,
    duration: number = 0, // Default to 0 for session_started
    extraData?: Record<string, any> 
  ) {
    this.sessionStrategy.reportToSessionLog(event, eventTime, logTime, username, duration, extraData);
  }

  private async terminateSession(sessionKey: string) {
    const session = this.getSession(sessionKey);

    if (!session) {
      this.logger.warn(`No active session found for sessionKey: ${sessionKey}`);
      return;
    }

    if (session.getLastActivityTime() != null) {
      const endTime = session.getLastActivityTime() || new Date();
      const sessionDuration = endTime.getTime() - session.getStartTime().getTime();
      const duration = sessionDuration ? sessionDuration : this.minSessionDuration;
      const username = `${session.getUserId()}@${session.getOrgId()}`;
      this.reportToSessionLog('session_ended',endTime, endTime, username, duration);
      //logSessionEvent('session_ended', endTime, endTime, username, duration);
    }
    session.clearExpirationTimer();
    DailyUsage.closeSession(session);

    for (const tabId in this.tabIdToSessionKeyMap) {
      if (this.tabIdToSessionKeyMap.hasOwnProperty(tabId)) {
        if (this.tabIdToSessionKeyMap[tabId] === sessionKey) {
          delete this.tabIdToSessionKeyMap[tabId];
        }
      }
    }

    const success = this.deleteActiveSession(sessionKey);

    if (success) {
      this.logger.log(`Session successfully deleted for sessionKey: ${sessionKey}`);
      await this.saveSessionsToLocalStorage();
    } else {
      this.logger.warn(`Failed to delete session for sessionKey: ${sessionKey}`);
    }
  }

  // This should be stragegy specific
  private async handleNewSession(orgId: string, userId: string, startTime: Date, additionalParams: any = {}): Promise<string | null> {
    if (!userId || !orgId) {
      this.logger.warn(`handleNewSession called with no userId ${userId}, or orgId ${orgId}`);
      return null;
    }

    const sessionKey = this.sessionStrategy.calcSessionKey(userId, orgId, additionalParams);
    //const sessionKey = UserSession.calcSessionKey(userId, orgId);
    const session = this.getSession(sessionKey);
    if (session) {
      this.logger.log(`Session already exists for sessionKey: ${sessionKey}.`);
      return sessionKey;
    }
    const newSessionKey = this.createSession(orgId, userId, startTime, additionalParams);
    if (!newSessionKey) {
      this.logger.error('Failed to create a new session.');
      return null;
    }
    const newSession = this.getSession(newSessionKey);
    if (newSession) {
      this.logger.log('Session successfully created:', newSession);
      await this.saveSessionsToLocalStorage();
      return newSessionKey;
    } else {
      this.logger.error('Failed to create a new session.');
      return null;
    }
  }

  private setSessionExpirationTimer(sessionKey: string, expirationTimeout: number = 180) {
    const session = this.getSession(sessionKey);
    if (!session) {
      this.logger.warn(`setSessionTimer - No active session found for sessionKey: ${sessionKey}`);
      return;
    }

    const expirationTimer = setTimeout(() => {
      this.logger.log(`Session expired for sessionKey: ${sessionKey}`);
      this.terminateSession(sessionKey);
    }, expirationTimeout * 1000);

    session.setExpirationTimer(expirationTimer);
  }

  // Activity Updates
  private updateLastActivity(sessionKey: string, timestamp: Date) {
    this.logger.log(`Updating last activity for sessionKey: ${sessionKey} at ${timestamp}`);

    const session = this.getSession(sessionKey);
    if (!session) {
      this.logger.warn(`No active session found for sessionKey: ${sessionKey}`);
      return;
    }
    if (!session.getActivitySeen()) {
      session.setActivitySeen(true);
      const username = `${session.getUserId()}@${session.getOrgId()}`;
      const now = new Date();
      this.logger.log(`Initial user activity detected on ${sessionKey} at ${timestamp}. Logging session start.`);
      this.reportToSessionLog('session_started', session.getStartTime(), now, username);
      //logSessionEvent('session_started', session.getStartTime(), now, username);
    }
    session.setLastActivityTime(timestamp);
    DailyUsage.reportSession(session);
    this.setSessionExpirationTimer(sessionKey, this.getSessionTimeout());
    this.debouncedUpdates.debounce(() => {
      this.persistLastActivity(sessionKey);
    });
  }

  private async flushPendingUpdate(sessionKey: string) {
    const session = this.getSession(sessionKey);
    const lastActivityTime = session?.getLastActivityTime();
    if (session && lastActivityTime) {
      await this.persistLastActivity(sessionKey);
      this.logger.log(`Flushed last activity time for sessionKey ${sessionKey}`);
    } else {
      this.logger.warn(`No active session found for sessionKey: ${sessionKey}`);
    }
  }

  private async persistLastActivity(sessionKey: string) {
    const session = this.getSession(sessionKey);

    if (session) {
      await this.saveSessionsToLocalStorage();
      this.logger.log(`Persisted last activity time for sessionKey ${sessionKey}`);
    } else {
      this.logger.warn(`Session not found for sessionKey ${sessionKey}. Unable to persist last activity.`);
    }
  }

  // This should be stragegy specific
  private async findOrCreateSession(
    tabId: number,
    sender: chrome.runtime.MessageSender,
    userId: string,
    orgCode: string,
    startTime: Date,
    additionalParams: any = {},
    sendResponse: (response?: any) => void
  
  ): Promise<string | null> {
    const senderTabUrl = sender.tab?.url || '';
    const url = new URL(senderTabUrl);
    const domain = url.hostname;
   
    if (!userId || !orgCode) {
      this.logger.warn(`findOrCreateSession called with no userId ${userId}, or orgCode ${orgCode}`);
      sendResponse({ success: false, error: 'No userId or orgCode provided' });
      return null;
    }
    const { chartType, chartName } = additionalParams;
    let sessionKey = this.sessionStrategy.calcSessionKey(userId, orgCode, { chartType, chartName });
    //let sessionKey = UserSession.calcSessionKey(userId, orgCode);
    const session = this.getSession(sessionKey);
    if (!session) {
      // no session yet, create a new one
      this.logger.log(`findOrCreateSession did not find sesssion for key ${sessionKey}. Creating a new session.`);
      const newSessionKey = await this.handleNewSession(orgCode, userId, startTime, additionalParams);
      if (newSessionKey) {
        sessionKey = newSessionKey;
        this.setSessionExpirationTimer(sessionKey, this.getSessionTimeout());
      } else { 
        this.logger.error('chrome.runtime.onMessage: Failed to create a new session.');
        sendResponse({ success: false, error: 'Failed to create a new session' });
        return null;
      }
    }
    return sessionKey;
  }

  private processUserInputMessage(
    message: any,
    sessionKey: string,
    sendResponse: (response?: any) => void
  ) {
    // Check for valid message type
    if (message.type !== 'user_input') {
      this.logger.warn(`processUserInputMessage called with invalid message type: ${message.type}`);
      sendResponse({ success: false, error: 'Invalid message type' });
      return;
    }
    this.logger.log(`User activity detected on ${sessionKey} at ${message.timestamp}`);
    this.updateLastActivity(sessionKey, new Date(message.timestamp));
  
    // Explicitly respond to the message
    sendResponse({ success: true, message });
  }

  /*
  * public functions
  */
  public async initializeSessionManager(): Promise<void> {
    this.logger.log('Initializing session manager...');
    await this.loadActiveSessions();
    this.sessionsLoaded = true;
    const sessions = this.getAllSessions();
    for (const key in sessions) {
      if (sessions.hasOwnProperty(key)) {
        const session = sessions[key];
        this.terminateSession(key);
      }
    }
    await this.initializeSessionTimeout();
    this.logger.log('Session manager initialized.');
  }


  /*
  * Event Handlers
  */
  public async onTabRemove(tabId: number) {
    this.logger.log(`${this.managerName}: Tab ${tabId} closed`);
    const sessionKey = this.tabIdToSessionKeyMap[tabId];
    if (sessionKey) {
      await this.flushPendingUpdate(sessionKey);
      this.logger.log(`Flushed pending updates for sessionKey: ${sessionKey} on tab close.`);
      delete this.tabIdToSessionKeyMap[tabId];
    } else {
      // not a registered tab
      this.logger.debug(`No sessionKey found for tabId: ${tabId}`);
    }
  }

  public async handleSessionTimeoutSet(
    message: SessionTimeoutSetMessage, 
    sendResponse: (response: SessionTimeoutSetResponse) => void): Promise<void> 
  {
    try {
      this.logger.log('Setting session timeout:', message.timeout);
      await this.setSessionTimeout(message.timeout);
      sendResponse({ type: 'session_timeout_set_response', success: true });
      this.logger.log('Session timeout set successfully to:.', message.timeout);
    } catch (error) {
      this.logger.error('Failed to set session timeout:', error);
      sendResponse({ type: 'session_timeout_set_response', success: false, error: 'Failed to set session timeout' });
    }
  }

  public async handleSessionTimeoutGet(
    message: SessionTimeoutGetMessage, 
    sendResponse: (response: SessionTimeoutGetResponse) => void): Promise<void> 
  {
    try {
      const timeout = await this.getSessionTimeout();
      this.logger.log('Getting session timeout:', timeout);
      sendResponse({ type: 'session_timeout_get_response', success: true, timeout });
    } catch (error) {
      this.logger.error('Failed to get session timeout:', error);
      sendResponse({ type: 'session_timeout_get_response', success: false, timeout: null, error: 'Failed to get session timeout' });
    }
  }

  // This may need to be stragegy specific
  public async handleSessionsGet(
    message: SessionsGetMessage, 
    sendResponse: (response: SessionsResponse) => void): Promise<void> 
  {
    try {
      const sessionsRecord = this.getAllSessions();
      if (sessionsRecord) {
        const sessionsArray: ActiveSession[] = Object.values(sessionsRecord); 
        const sessionsDTO = sessionsArray.map(session => this.sessionStrategy.serializeSession(session));
        //const sessionsDTO = sessionsArray.map(UserSession.serialize);     
        sendResponse({ type: 'sessions_get_response', success: true, sessions: sessionsDTO });
      } else {
        this.logger.warn('handleActiveSessionsGet: Active sessions are not initialized.');
        sendResponse({ type: 'sessions_get_response', success: false, error: 'Active sessions are not initialized', sessions: [] });
      }
    } catch (error) {
      this.logger.error('handleActiveSessionsGet: Unexpected error:', error);
      sendResponse({ type: 'sessions_get_response', success: false, error: 'Failed to retrieve active sessions', sessions: [] });
    }
  }

  public async handlePageLoad(
    message: PageLoadMessage, 
    sender: chrome.runtime.MessageSender, 
    sendResponse: (response: PageLoadResponse) => void): Promise<void> 
  {
    const { username, pageStartTime } = message;
    const tabId = sender.tab?.id;
  
    if (tabId === undefined) {
      this.logger.error('handlePageLoad: tabId is undefined.');
      sendResponse({ type: 'page_load_response', success: false, error: 'tabId is undefined' });
      return;
    }
  
    try {
      const sessionKey = await this.findOrCreateSession(tabId, sender, message.username, 
                                                        message.orgCode, new Date(pageStartTime), 
                                                        {chartType: message.chartType, chartName: message.chartName},
                                                        sendResponse);
  
      if (sessionKey) {
        this.tabIdToSessionKeyMap[tabId] = sessionKey;
        sendResponse({ type: 'page_load_response', success: true });
      } else {
        this.logger.error(`handlePageLoad: Failed to find or create session for username ${username}.`);
        if (this.tabIdToSessionKeyMap[tabId]) {
          delete this.tabIdToSessionKeyMap[tabId]; // Remove invalid session
        }
        sendResponse({ type: 'page_load_response', success: false, error: 'Failed to create a new session' });
      }
    } catch (error) {
      this.logger.error(`handlePageLoad: Unexpected error for tabId ${tabId}:`, error);
      sendResponse({ type: 'page_load_response', success: false, error: 'An unexpected error occurred' });
    }
  }

  public async handleUserInput(
    message: UserInputMessage, 
    sender: chrome.runtime.MessageSender, 
    sendResponse: (response: UserInputResponse) => void): Promise<boolean> 
  {
  
    const tabId = sender.tab?.id;
    if (tabId === undefined) {
      this.logger.error('handleUserInput: tabId is undefined.');
      sendResponse({ type: 'user_input_response', success: false, error: 'tabId is undefined' });
      return false;
    }
  
    let sessionKeyFromTab = this.tabIdToSessionKeyMap[tabId];
    if (sessionKeyFromTab) {
      // Optimistic synchronous flow
      this.processUserInputMessage(message, sessionKeyFromTab, sendResponse);
      return false; // No need to keep the message channel open
    } else {
      this.logger.log(`No sessionKey found for tabId: ${tabId}. Searching for it in session table.`);
  
      try {
        // Fallback: Retrieve sessionId asynchronously
        const sessionKey = await this.findOrCreateSession(tabId, sender, message.username, message.orgCode, new Date(message.timestamp), 
                                                          {chartType: message.chartType, chartName: message.chartName},
                                                          sendResponse);
        if (sessionKey) {
          this.tabIdToSessionKeyMap[tabId] = sessionKey;
          this.processUserInputMessage(message, sessionKey, sendResponse);
        } else {
          this.logger.error(`handleUserInput: Failed to find or create session for username ${message.username}.`);
          sendResponse({ type: 'user_input_response', success: false, error: 'Failed to create a new session' });
        }
      } catch (error) {
        this.logger.error(`handleUserInput: Unexpected error for tabId ${tabId}:`, error);
        sendResponse({ type: 'user_input_response', success: false, error: 'An unexpected error occurred' });
      }
  
      // Return true to keep the message channel open for asynchronous handling
      return true;
    }
  }
  

 

  // place reserved for strategy specific handlkers methods

  // async handlePageLoad(message: PageLoadMessage, sender: chrome.runtime.MessageSender, sendResponse: (response: PageLoadResponse) => void): Promise<void> {
  //   await this.sessionStrategy.handlePageLoad(message, sender, sendResponse);
  // }

  // async handleUserInput(message: UserInputMessage, sender: chrome.runtime.MessageSender, sendResponse: (response: UserInputResponse) => void): Promise<void> {
  //   await this.sessionStrategy.handleUserInput(message, sender, sendResponse);
  // }
}

// const userSessionManager = SessionManagerFactory.createSessionManager(SessionType.UserSession, 'userSessions');
// const chartSessionManager = SessionManagerFactory.createSessionManager(SessionType.ChartSession, 'chartSessions');

const userSessionManager = new SessionManager(new UserSessionStrategy(), 'user_sessions', 3000, 10000, 180);
const chartSessionManager = new SessionManager(new ChartSessionStrategy(), 'chart_sessions', 3000, 10000, 60);

export async function initializeSessionManager() {
  await userSessionManager.initializeSessionManager();
  await chartSessionManager.initializeSessionManager();
}

// Message Handlers

// User activity events - used for all session managers
export async function handlePageLoad(
  message: PageLoadMessage, 
  sender: chrome.runtime.MessageSender, 
  sendResponse: (response: PageLoadResponse) => void): Promise<void> 
{
  await userSessionManager.handlePageLoad(message, sender, sendResponse);
  await chartSessionManager.handlePageLoad(message, sender, sendResponse);
}
export async function handleUserInput(
  message: UserInputMessage, 
  sender: chrome.runtime.MessageSender, 
  sendResponse: (response: UserInputResponse) => void): Promise<void> 
{
  await userSessionManager.handleUserInput(message, sender, sendResponse);
  await chartSessionManager.handleUserInput(message, sender, sendResponse);
}

// Configuration requests - must be per type of session maanger
// Handle message set request for timeout
export async function handleUserSessionTimeoutSet(
  message: SessionTimeoutSetMessage, 
  sendResponse: (response: SessionTimeoutSetResponse) => void): Promise<void> 
{
  userSessionManager.handleSessionTimeoutSet(message, sendResponse);
}

// // Handle message get request for timeout
export async function handleUserSessionTimeoutGet(
  message: SessionTimeoutGetMessage, 
  sendResponse: (response: SessionTimeoutGetResponse) => void): Promise<void> 
{
  userSessionManager.handleSessionTimeoutGet(message, sendResponse);
}

// Session get - must be per type of session manager
export async function handleUserSessionsGet(
  message: SessionsGetMessage, 
  sendResponse: (response: SessionsResponse) => void): Promise<void> 
{
  userSessionManager.handleSessionsGet(message, sendResponse);
}

export async function handleTabRemove(tabId: number) {
  userSessionManager.onTabRemove(tabId);
  chartSessionManager.onTabRemove(tabId);
}


//*****************************************************/
// Debug functions
//*****************************************************/  
export function getAllUserSessions(): Record<string, ActiveSession> | undefined {
  return userSessionManager.getAllSessions();
}

export function getAllChartSessions(): Record<string, ActiveSession> | undefined {
  return chartSessionManager.getAllSessions();
}

(globalThis as any).getAllUserSessions = getAllUserSessions;
(globalThis as any).getAllChartSessions = getAllChartSessions;



// let userSessions: Record<string, UserSession> = {};
// let activeSessionsInitialized = false;


// // configrations
// const defaultSessionTimeout = 180; // 3 minutes
// let sessionTimeoutConfig = defaultSessionTimeout; // 3 minutes
// const minSessionDuration = 1000 // 1 second

// // Set session timeout and store it in local storage
// export async function setSessionTimeout(timeout: number): Promise<void> {
//   sessionTimeoutConfig = timeout;
//   return new Promise((resolve, reject) => {
//     chrome.storage.local.set({ sessionTimeout: sessionTimeoutConfig }, () => {
//       if (chrome.runtime.lastError) {
//         this.logger.error('Failed to save session timeout to local storage:', chrome.runtime.lastError);
//         reject(chrome.runtime.lastError);
//       } else {
//         resolve();
//       }
//     });
//   });
// }

// // Get session timeout (synchronous)
// export function getSessionTimeout(): number {
//   return sessionTimeoutConfig;
// }

// // Load session timeout from local storage
// export async function loadSessionTimeout(): Promise<number> {
//   return new Promise((resolve, reject) => {
//     chrome.storage.local.get('sessionTimeout', (result) => {
//       if (chrome.runtime.lastError) {
//         this.logger.error('Failed to load session timeout from local storage:', chrome.runtime.lastError);
//         reject(chrome.runtime.lastError);
//       } else {
//         this.logger.log('Loaded session timeout from local storage:', result.sessionTimeout || sessionTimeoutConfig);
//         resolve(result.sessionTimeout || sessionTimeoutConfig);
//       }
//     });
//   });
// }



//   try {
//     this.logger.log('Setting session timeout:', message.timeout);
//     await setSessionTimeout(message.timeout);
//     sendResponse({ type: 'session_timeout_set_response', success: true });
//     this.logger.log('Session timeout set successfully to:.', message.timeout);
//   } catch (error) {
//     this.logger.error('Failed to set session timeout:', error);
//     sendResponse({ type: 'session_timeout_set_response', success: false, error: 'Failed to set session timeout' });
//   }
// }



// // Initialize session timeout from local storage
// export async function initializeSessionTimeout(): Promise<void> {
//   try {
//     sessionTimeoutConfig = await loadSessionTimeout();
//     this.logger.log('Session timeout initialized:', sessionTimeoutConfig);
//   } catch (error) {
//     sessionTimeoutConfig = defaultSessionTimeout;
//     this.logger.error('Failed to initialize session timeout:', error);
//   }
// }

// export async function getUserSessionsFromLocalStorage(): Promise<Record<string, UserSession>> {
//   return new Promise((resolve, reject) => {
//     chrome.storage.local.get('activeSessions', (result) => {
//       if (chrome.runtime.lastError) {
//         this.logger.error('Failed to load active sessions from local storage:', chrome.runtime.lastError);
//         reject(chrome.runtime.lastError);
//       } else {
//         const activeSessions = result.activeSessions || {};
//         const userSessions: Record<string, UserSession> = {};
//         for (const key in activeSessions) {
//           if (activeSessions.hasOwnProperty(key)) {
//             const sessionDTO = activeSessions[key];
//             userSessions[key] = UserSession.deserialize(sessionDTO);
//           }
//         }
//         resolve(userSessions);
//       }
//     });
//   });
// }

// // Save active sessions to storage
// export async function saveActiveSessionsToLocalStorage(): Promise<void> {
//   return new Promise((resolve, reject) => {
//     const sessionsToSave = Object.fromEntries(
//       Object.entries(userSessions).map(([key, session]) => [
//         key, session.serialize(),
//       ])
//     );
//     chrome.storage.local.set({ activeSessions: sessionsToSave }, () => {
//       if (chrome.runtime.lastError) {
//         this.logger.error('Failed to save active sessions to local storage:', chrome.runtime.lastError);
//         reject(chrome.runtime.lastError);
//       } else {
//         resolve();
//       }
//     });
//   });
// }
//   // Load active sessions from local storage
// async function loadActiveSessions(): Promise<void> {
//   userSessions = await getUserSessionsFromLocalStorage();
//   this.logger.log('Loaded active sessions:', userSessions);
// }

// export async function initializeSessionManager() {
//   this.logger.log('Initializing session manager...');
//   await loadActiveSessions();
//   activeSessionsInitialized = true;
//   const sessions = getAllUserSessions(); // Load active sessions into memory
//   // terminate all sessions on startup
//   // we do this to enusre all sessions had session_ended event logged for the previous session
//   for (const key in sessions) {
//     if (sessions.hasOwnProperty(key)) {
//       const session = sessions[key];
//       terminateSession(key);
//     }
//   }
//   initializeSessionTimeout(); // Load session timeout from local storage

//   this.logger.log('Session manager initialized.');
// }



// function getUserSession(sessionKey: string): UserSession | undefined {
//   if (!activeSessionsInitialized) {
//     this.logger.warn(`Attempted to access activeSessions before initialization. sessionKey: ${sessionKey}`);
//     return undefined; // Indicate that `activeSessions` is not ready
//   }
//   return userSessions[sessionKey];
// }


//   try {
//     const userSessionsRecord = getAllUserSessions();
//     if (userSessionsRecord) {
//       const userSessionsArray: UserSession[] = Object.values(userSessionsRecord); 
//       const userSessionsDTO = userSessionsArray.map(UserSession.serialize);     
//       sendResponse({ type: 'user_sessions_get_response', success: true, userSessions: userSessionsDTO });
//     } else {
//       this.logger.warn('handleActiveSessionsGet: Active sessions are not initialized.');
//       sendResponse({ type: 'user_sessions_get_response', success: false, error: 'Active sessions are not initialized', userSessions: [] });
//     }
//   } catch (error) {
//     this.logger.error('handleActiveSessionsGet: Unexpected error:', error);
//     sendResponse({ type: 'user_sessions_get_response', success: false, error: 'Failed to retrieve active sessions', userSessions: [] });
//   }
// }

// function createNewUserSession(
//   orgId: string = '',
//   userId: string = '',
//   startTime: Date,
// ): string | null {
//   if (!activeSessionsInitialized) {
//     this.logger.warn('Attempted to create a new session before activeSessions initialization.');
//     return null;
//   }

//   const newSession = new UserSession(
//     userId, 
//     orgId,
//     startTime/*: startTime ?? new Date(),*/
//   );
  
//   const sessionKey = newSession.getSessionKey() // UserSession.calcSessionKey(userId, orgId);
//   userSessions[sessionKey] = newSession;
//   DailyUsage.reportSession(newSession);
//   this.logger.log(`New session created for sessionKey: ${sessionKey}`, newSession);

//   return sessionKey;
// }
  
  
// function deleteActiveSession(sessionKey: string): boolean {
//   if (!activeSessionsInitialized) {
//     this.logger.warn('Attempted to delete a session before activeSessions initialization.');
//     return false;
//   }

//   if (!userSessions[sessionKey]) {
//     this.logger.warn(`No session found for sessionKey: ${sessionKey}. Deletion skipped.`);
//     return false;
//   }

//   delete userSessions[sessionKey];
//   this.logger.log(`Session deleted for sessionKey: ${sessionKey}`);
//   return true;
// }
  

// async function terminateSession(sessionKey: string) {
//   const session = getUserSession(sessionKey);

//   if (!session) {
//     this.logger.warn(`No active session found for sessionKey: ${sessionKey}`);
//     return;
//   }

//   if (session.getLastActivityTime() != null) {
//     // session has started and was reported so we report session end
//     const endTime = session.getLastActivityTime() || new Date();
//     const sessionDuration = endTime.getTime() - session.getStartTime().getTime();
//     const duration = sessionDuration? sessionDuration : minSessionDuration; 
//     const username = `${session.getUserId()}@${session.getOrgId()}`;
//     logSessionEvent(
//       'session_ended',
//       endTime,
//       endTime,
//       username,
//       duration
//     );
//   }
//   session.clearExpirationTimer(); // Clear the session timer

//   // update the daily usage
//   DailyUsage.closeSession(session);

//   // Traverse all the tabId keys in tabIdToSessionKeyMap
//   for (const tabId in tabIdToSessionKeyMap) {
//     if (tabIdToSessionKeyMap.hasOwnProperty(tabId)) {
//       // If the value is the current sessionKey, delete the key from the map
//       if (tabIdToSessionKeyMap[tabId] === sessionKey) {
//         delete tabIdToSessionKeyMap[tabId];
//       }
//     }
//   }

//   const success = deleteActiveSession(sessionKey);

//   if (success) {
//     this.logger.log(`Session successfully deleted for sessionKey: ${sessionKey}`);
//     await saveActiveSessionsToLocalStorage(); // Persist the updated sessions
//   } else {
//     this.logger.warn(`Failed to delete session for sessionKey: ${sessionKey}`);
//   }
// }  

// async function handleNewSession(
//   orgId: string, 
//   userId: string,
//   startTime: Date,
// ): Promise<string | null> {

//   if (!userId || !orgId) {
//     this.logger.warn(`handleNewSession called with no userId ${userId}, or orgId ${orgId}`);
//     return null;
//   }

//   // If the session already exists, update the userId if provided
//   const sessionKey = UserSession.calcSessionKey(userId, orgId);
//   const session = getUserSession(sessionKey);
//   if (session) {
//     this.logger.log(`Session already exists for sessionKey: ${sessionKey}.`);
//     return sessionKey;
//   }
//   const newSessionKey = createNewUserSession(orgId, userId, startTime);
//   if (!newSessionKey) {
//     this.logger.error('Failed to create a new session.');
//     return null;
//   }
//   const newSession = getUserSession(newSessionKey);
//   if (newSession) {
//     this.logger.log('Session successfully created:', newSession);
//     await saveActiveSessionsToLocalStorage(); // Persist the updated sessions
//     return newSessionKey; 
//   } else {
//     this.logger.error('Failed to create a new session.');
//     return null;
//   }    
// }

// function setSessionExpirationTimer(sessionKey: string, expirationTimeout: number = 180) {
//   // Clear any existing timer for the session
//   const session = getUserSession(sessionKey);
//   if (!session) {
//     this.logger.warn(`setSessionTimer - No active session found for sessionKey: ${sessionKey}`);
//     return;
//   }
 
//   // Set a new timer to terminate the session after expirationTimeout 
//   const expirationTimer = setTimeout(() => {
//     this.logger.log(`Session expired for sessionKey: ${sessionKey}`);
//     terminateSession(sessionKey);
//   }, expirationTimeout * 1000);

//   session.setExpirationTimer(expirationTimer);
// }


// const debouncedUpdates = new DebounceThrottle(3000, 10000);
// export function updateLastActivity(sessionKey: string, timestamp: Date) {
//   this.logger.log(`Updating last activity for sessionKey: ${sessionKey} at ${timestamp}`);

//   const session = getUserSession(sessionKey);
//   if (!session) {
//     this.logger.warn(`No active session found for sessionKey: ${sessionKey}`);
//     return;
//   }
//   if (!session.getUserActivitySeen()) {
//     // mark first activity time - we log the session start only once there is activity otherwise the session is not considered started
//     session.setUserActivitySeen(true);
//     const username = `${session.getUserId()}@${session.getOrgId()}`;
//     const now = new Date();
//     this.logger.log(`Initial user activity detected on ${sessionKey} at ${timestamp}. Logging session start.`);
//     logSessionEvent('session_started', session.getStartTime(), now, username);
//   }
//   session.setLastActivityTime(timestamp); 
//   DailyUsage.reportSession(session)
//   setSessionExpirationTimer(sessionKey, getSessionTimeout()); // Reset the session timer
//   debouncedUpdates.debounce(() => {
//     persistLastActivity(sessionKey);
//   });
// }


  
// // Immediately flush updates for a specific sessionKey
// async function flushPendingUpdate(sessionKey: string) {
//   const session = getUserSession(sessionKey);
//   const lastActivityTime = session?.getLastActivityTime();
//   if (session && lastActivityTime) {
//     await persistLastActivity(sessionKey); // Persist latest in-memory state
//     this.logger.log(`Flushed last activity time for sessionKey ${sessionKey}`);
//   } else {
//     this.logger.warn(`No active session found for sessionKey: ${sessionKey}`);
//   }
// }


// export async function persistLastActivity(sessionKey: string) {
//   const session = getUserSession(sessionKey);

//   if (session) {
//     await saveActiveSessionsToLocalStorage(); // Persist updated table
//     this.logger.log(`Persisted last activity time for sessionKey ${sessionKey}`);
//   } else {
//     this.logger.warn(`Session not found for sessionKey ${sessionKey}. Unable to persist last activity.`);
//   }
// }



// /**************************/
// // Event Listeners & Handlers
// /**************************/

// const tabIdToSessionKeyMap: Record<number, string> = {}; // Maps tabId to session key



// async function findOrCreateSession(
//   tabId: number,
//   sender: chrome.runtime.MessageSender,
//   userId: string,
//   orgCode: string,
//   startTime: Date,
//   sendResponse: (response?: any) => void

// ): Promise<string | null> {
//   const senderTabUrl = sender.tab?.url || '';
//   const url = new URL(senderTabUrl);
//   const domain = url.hostname;
 
//   let sessionKey = UserSession.calcSessionKey(userId, orgCode);
//   const session = getUserSession(sessionKey);
//   if (!session) {
//     // no session yet, create a new one
//     this.logger.log(`findOrCreateSession did not find sesssion for key ${sessionKey} 
//                 user input message for a non existing session. Creating a new session.`);
//     const newSessionKey = await handleNewSession(orgCode, userId, startTime);
//     if (newSessionKey) {
//       sessionKey = newSessionKey;
//       setSessionExpirationTimer(sessionKey, getSessionTimeout());
//     } else { 
//       this.logger.error('chrome.runtime.onMessage: Failed to create a new session.');
//       sendResponse({ success: false, error: 'Failed to create a new session' });
//       return null;
//     }
//   }
//   return sessionKey;
// }

// export async function handlePageLoad(
//   message: PageLoadMessage, 
//   sender: chrome.runtime.MessageSender, 
//   sendResponse: (response: PageLoadResponse) => void): Promise<void> 
// {
//   const { username, pageStartTime } = message;
//   const tabId = sender.tab?.id;

//   if (tabId === undefined) {
//     this.logger.error('handlePageLoad: tabId is undefined.');
//     sendResponse({ type: 'page_load_response', success: false, error: 'tabId is undefined' });
//     return;
//   }

//   try {
//     const sessionKey = await findOrCreateSession(tabId, sender, message.username, message.orgCode, new Date(pageStartTime), sendResponse);

//     if (sessionKey) {
//       tabIdToSessionKeyMap[tabId] = sessionKey;
//       sendResponse({ type: 'page_load_response', success: true });
//     } else {
//       this.logger.error(`handlePageLoad: Failed to find or create session for username ${username}.`);
//       if (tabIdToSessionKeyMap[tabId]) {
//         delete tabIdToSessionKeyMap[tabId]; // Remove invalid session
//       }
//       sendResponse({ type: 'page_load_response', success: false, error: 'Failed to create a new session' });
//     }
//   } catch (error) {
//     this.logger.error(`handlePageLoad: Unexpected error for tabId ${tabId}:`, error);
//     sendResponse({ type: 'page_load_response', success: false, error: 'An unexpected error occurred' });
//   }
// }




// Exported functions to globnal scope
// Attach the function to the global scope
//(globalThis as any).getAllActiveSessions = getAllUserSessions;
