import { BasicResponse } from '../types';
import { Logger } from '../utils/logger';


export type SessionLogEvent = {
  event : 'session_started' | 'session_ended' | 'session_onging',
  eventTime: string,
  logTime: string,
  username: string,
  duration: number,
}

const consoleLogger = new Logger('SessionLog');

export async function logSessionEvent(
  event: 'session_started' | 'session_ended' | 'session_onging',
  eventTime: Date,
  logTime: Date,
  username: string,
  duration: number = 0, // Default to 0 for session_started
  extraData?: Record<string, any>
) {

  const sessionEvent: SessionLogEvent = {
      event: event, 
      eventTime: eventTime.toISOString(), 
      logTime: logTime.toISOString(),
      username, duration
    } 

  const eventLog = {
    ...sessionEvent,
    ...extraData, // Auxiliary metadata
  };

  try {
    const logs = await getSessionLogs();
    logs.push(eventLog); // Append the new log event
    await saveSessionLogs(logs);
    consoleLogger.log('Event logged:', eventLog);
  } catch (error) {
    consoleLogger.error('Failed to log event:', error);
  }
}


// Helper to get all session logs from storage
export async function getSessionLogs(): Promise<any[]> {
  return new Promise((resolve, reject) => {
    chrome.storage.local.get('session_logs', (result) => {
      if (chrome.runtime.lastError) {
        consoleLogger.error('Failed to get session logs from local storage', chrome.runtime.lastError);
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
        consoleLogger.error('Failed to save session logs to local storage:', chrome.runtime.lastError);
        reject(chrome.runtime.lastError);
      } else {
        resolve();
      }
    });
  });
}

export async function clearSessionLogs(): Promise<void> {
  return new Promise((resolve, reject) => {
    chrome.storage.local.remove('session_logs', () => {
      if (chrome.runtime.lastError) {
        consoleLogger.error('Failed to clear session logs from local storage:', chrome.runtime.lastError);
        reject(chrome.runtime.lastError);
      } else {
        resolve();
      }
    });
  });
}


export async function handleSessionsLogsGet(message: SessionsLogsGetMessage, sendResponse: (response: SessionsLogsGetResponse) => void): Promise<void> {
  try {
    const sessionLogs = await getSessionLogs();
    sendResponse({ type: 'session_logs_get_response', success: true, sessionLogs });
  } catch (error) {
    consoleLogger.error('handleActiveSessionsGet: Unexpected error:', error);
    sendResponse({ type: 'session_logs_get_response', success: false, error: 'Failed to retrieve session logs', sessionLogs: [] });
  }
}

export async function handleSessionsLogsClear(message: SessionsLogsClearMessage, sendResponse: (response: SessionsLogsClearResponse) => void): Promise<void> {
    try {
      await clearSessionLogs();
      sendResponse({ type: 'session_logs_clear_response', success: true });
    } catch (error) {
      consoleLogger.error('handleSessionsLogsClear: Unexpected error:', error);
      sendResponse({ type: 'session_logs_clear_response', success: false, error: 'Failed to clear session logs' });
    }
}


/***********************************
 * Session log messages
 **********************************/
export interface SessionsLogsGetMessage {
  type: 'session_logs_get';
}

export interface SessionsLogsGetResponse extends BasicResponse {
  type: 'session_logs_get_response';
  sessionLogs: SessionLogEvent[];
}

export interface SessionsLogsClearMessage {
  type: 'session_logs_clear';
}

export interface SessionsLogsClearResponse extends BasicResponse {
  type: 'session_logs_clear_response';
}



