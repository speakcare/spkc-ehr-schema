import { initializeSessionManager, handleUserInput, handlePageLoad, 
        handleUserSessionsGet, handleUserSessionTimeoutGet, 
        handleUserSessionTimeoutSet, handleTabRemove } from './session_manager';
import {  PageLoadMessage, PageLoadResponse, UserInputMessage, 
          UserInputResponse, SessionsGetMessage, SessionsResponse,
          SessionTimeoutGetMessage, SessionTimeoutGetResponse, SessionTimeoutSetMessage, SessionTimeoutSetResponse } from '../types/messages';
import { UserSessionDTO } from './sessions'
import { handleSessionsLogsGet, handleSessionsLogsClear } from './session_log';
import { initializePanelManager } from './panel_manager';
import { BasicResponse } from '../types';
import { SessionsLogsGetMessage, SessionsLogsGetResponse, SessionsLogsClearMessage, SessionsLogsClearResponse } from './session_log';
import { DailyUsage } from './daily_usage';
import { Logger } from '../utils/logger';
//import { BackgroundMessage, BackgroundResponse } from '../types';


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
                       SessionsLogsClearMessage | SessionTimeoutSetMessage | SessionTimeoutGetMessage;
export type BackgroundResponse =  PageLoadResponse | UserInputResponse | SessionsResponse | SessionsLogsGetResponse | 
                         SessionsLogsClearResponse | SessionTimeoutSetResponse | SessionTimeoutGetResponse;



self.addEventListener('activate', () => {
  logger.log('activated at', new Date().toISOString());
});
self.addEventListener('message', (event) => {
  logger.log('message received in background script:', event.data);
});
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
      case 'page_load':
        handlePageLoad(message, sender, sendResponse);
        return true;

      case 'user_input':
        handleUserInput(message, sender, sendResponse);
        return true;

      case 'sessions_get':
        handleUserSessionsGet(message, sendResponse);
        return true;

      case 'session_logs_get':
        handleSessionsLogsGet(message, sendResponse);
        return true;

      case 'session_logs_clear':
        handleSessionsLogsClear(message, sendResponse);
        return true;

      case 'session_timeout_get':
        handleUserSessionTimeoutGet(message, sendResponse);
        return true;
      
      case 'session_timeout_set':
        handleUserSessionTimeoutSet(message, sendResponse);
        return true;

      default:
        logger.warn('Unknown message type:', message);
    }
  }
);

chrome.tabs.onRemoved.addListener(async (tabId) => {
  handleTabRemove(tabId);  
});



