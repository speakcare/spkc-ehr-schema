import { initializeSessionManager, handleUserInput, handlePageLoad, 
        handleUserSessionsGet, handleUserSessionTimeoutGet, handleUserSessionTimeoutSet } from './session_manager';
import {  PageLoadMessage, PageLoadResponse, UserInputMessage, 
          UserInputResponse, SessionsGetMessage, SessionsResponse,
          SessionTimeoutGetMessage, SessionTimeoutGetResponse, SessionTimeoutSetMessage, SessionTimeoutSetResponse } from '../types/messages';
import { UserSessionDTO } from './sessions'
import { handleSessionsLogsGet, handleSessionsLogsClear } from './session_log';
import { initializePanelManager } from './panel_manager';
import { BasicResponse } from '../types';
import { SessionsLogsGetMessage, SessionsLogsGetResponse, SessionsLogsClearMessage, SessionsLogsClearResponse } from './session_log';
import { DailyUsage } from './daily_usage';
//import { BackgroundMessage, BackgroundResponse } from '../types';


// TBD - Inject content script into matching tabs

// chrome.runtime.onInstalled.addListener(() => {
//   console.log('SpeakCare Lens Extension installed or updated. Injecting scripts into matching tabs...');
//   chrome.tabs.query({ url: '*://*.pointclickcare.com/*' }, (tabs) => {
//     tabs.forEach((tab) => {
//       chrome.scripting.executeScript({
//         target: { tabId: tab.id! },
//         files: ['content.bundle.js'],
//       }, () => {
//         if (chrome.runtime.lastError) {
//           console.error(`Failed to inject script into tab ${tab.id}: ${chrome.runtime.lastError.message}`);
//         } else {
//           console.log(`Content script injected into tab ${tab.id}`);
//         }
//       });
//     });
//   });
// });


export type BackgroundMessage = PageLoadMessage | UserInputMessage | SessionsGetMessage | SessionsLogsGetMessage | 
                       SessionsLogsClearMessage | SessionTimeoutSetMessage | SessionTimeoutGetMessage;
export type BackgroundResponse =  PageLoadResponse | UserInputResponse | SessionsResponse | SessionsLogsGetResponse | 
                         SessionsLogsClearResponse | SessionTimeoutSetResponse | SessionTimeoutGetResponse;



self.addEventListener('activate', () => {
  console.log('Background script activated at', new Date().toISOString());
});
self.addEventListener('message', (event) => {
  console.log('Message received in background script:', event.data);
});
console.log('Background script loaded at', new Date().toISOString());


// Initialize the panel manager and session manager
await initializePanelManager();
await DailyUsage.initialize();
await initializeSessionManager();

console.log('Background script sesssion manager initialized at', new Date().toISOString());

chrome.runtime.onMessage.addListener(
  (
    message: BackgroundMessage, // The message object
    sender: chrome.runtime.MessageSender, // Sender details
    sendResponse: (response: BackgroundResponse) => void // Response callback
  ): boolean | void => {
    console.debug('Message received in background script:', message);
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
        console.warn('Unknown message type:', message);
    }
  }
);



