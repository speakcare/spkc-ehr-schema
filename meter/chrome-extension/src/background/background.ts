export function initServiceWoker() {
  self.addEventListener('activate', () => {
      console.log('activated at', new Date().toISOString());
    });
  console.log('Activate event listener added');
  self.addEventListener('message', (event) => {
    console.log('message received in background script:', event.data);
  });
  console.log('Message event listener added');    console.log('Service workers initialized');
}

initServiceWoker();

import { initializeSessionManager, handleUserInput, handlePageLoad, 
        handleUserSessionsGet, handleChartSessionsGet, 
        handleUserSessionTimeoutGet, handleUserSessionTimeoutSet,
        handleChartSessionTimeoutGet, handleChartSessionTimeoutSet,
        handleTabRemove } from './session_manager';
import {  PageLoadMessage, PageLoadResponse, UserInputMessage, 
          UserInputResponse, SessionsGetMessage, SessionsGetResponse,
          SessionTimeoutGetMessage, SessionTimeoutGetResponse, SessionTimeoutSetMessage, SessionTimeoutSetResponse } from './session_messages';
import { handleSessionsLogsGet, handleSessionsLogsClear } from './session_log';
import { initializePanelManager } from './panel_manager';
import { SessionsLogsGetMessage, SessionsLogsGetResponse, SessionsLogsClearMessage, SessionsLogsClearResponse } from './session_log';
import { DailyUsage, handleDailyUsageGet, handleDailyUsageClear, DailyUsageGetMessage, DailyUsageClearMessage, 
         DailyUsageGetResponse, DailyUsageClearResponse} from './daily_usage';
import { Logger } from '../utils/logger';


// TBD - Inject content script into matching tabs

// chrome.runtime.onInstalled.addListener(() => {
//   logger.log('SpeakCare Lens Extension installed or updated. Injecting scripts into matching tabs...');
//   chrome.tabs.query({ url: '*://*.pointclickcare.com/*' }, (tabs) => {
//     tabs.forEach((tab) => {
//       chrome.scripting.executeScript({
//         target: { tabId: tab.id! },
//         files: ['content.bundle.js'],
//       }, () => {
//         if (chrome.runtime.lastError) {
//           logger.error(`Failed to inject script into tab ${tab.id}: ${chrome.runtime.lastError.message}`);
//         } else {
//           logger.log(`Content script injected into tab ${tab.id}`);
//         }
//       });
//     });
//   });
// });

const logger = new Logger('Background script');

export type BackgroundMessage = PageLoadMessage | UserInputMessage | SessionsGetMessage | SessionsLogsGetMessage | 
                                SessionsLogsClearMessage | SessionTimeoutSetMessage | SessionTimeoutGetMessage |
                                DailyUsageGetMessage | DailyUsageClearMessage;
export type BackgroundResponse =  PageLoadResponse | UserInputResponse | SessionsGetResponse | SessionsLogsGetResponse | 
                                  SessionsLogsClearResponse | SessionTimeoutSetResponse | SessionTimeoutGetResponse |
                                  DailyUsageGetResponse | DailyUsageClearResponse;




logger.log('loaded at', new Date().toISOString());


// Initialize the panel manager and session manager
await initializePanelManager();
await DailyUsage.initialize();
await initializeSessionManager();

logger.log('sesssion manager initialized at', new Date().toISOString());

chrome.runtime.onMessage.addListener(
  (
    message: BackgroundMessage, // The message object
    sender: chrome.runtime.MessageSender, // Sender details
    sendResponse: (response: BackgroundResponse) => void // Response callback
  ): boolean | void => {
    logger.debug('Message received in background script:', message);
    switch (message.type) {
      // Sesseion manager user activity messages
      case 'page_load':
        handlePageLoad(message, sender, sendResponse);
        return true;

      case 'user_input':
        handleUserInput(message, sender, sendResponse);
        return true;

      // Session manager sessions messages
      case 'user_sessions_get':
        handleUserSessionsGet(message, sendResponse);
        return true;
      
      case 'chart_sessions_get':
        handleChartSessionsGet(message, sendResponse);
        return true;

      // Session manager session timeout messages
      case 'user_session_timeout_get':
        handleUserSessionTimeoutGet(message, sendResponse);
        return true;
      
      case 'user_session_timeout_set':
        handleUserSessionTimeoutSet(message, sendResponse);
        return true;

      case 'chart_session_timeout_get':
        handleChartSessionTimeoutGet(message, sendResponse);
        return true;
      
      case 'chart_session_timeout_set':
        handleChartSessionTimeoutSet(message, sendResponse);
        return true;
  
      // Sessions logs messages
      case 'session_logs_get':
        handleSessionsLogsGet(message, sendResponse);
        return true;

      case 'session_logs_clear':
        handleSessionsLogsClear(message, sendResponse);
        return true;

      // Daily usage messages
      case 'daily_usage_get':
        handleDailyUsageGet(message, sendResponse);
        return true;
      
      case 'daily_usage_clear':
        handleDailyUsageClear(message, sendResponse);
        return true;
        
      default:
        logger.warn('Unknown message type:', message);
    }
  }
);

chrome.tabs.onRemoved.addListener(async (tabId) => {
  handleTabRemove(tabId);  
});



