import { PageLoadMessage, PageLoadResponse, UserInputMessage, UserInputResponse } from '../types/messages';
import { ActiveSession, ChartSession, UserSession, SessionType } from './sessions';
import { logSessionEvent } from './session_log';
import { Logger } from '../utils/logger';

const logger = new Logger('SessionStrategy');

export interface SessionStrategy {
    handlePageLoad(message: PageLoadMessage, sender: chrome.runtime.MessageSender, sendResponse: (response: PageLoadResponse) => void): Promise<void>;
    handleUserInput(message: UserInputMessage, sender: chrome.runtime.MessageSender, sendResponse: (response: UserInputResponse) => void): Promise<void>;
    calcSessionKey(userId: string, orgId: string, additionalParams: any): string;
    getSessionType(): SessionType;
    serializeSession(session: ActiveSession): any;
    reportToSessionLog(
      event: 'session_started' | 'session_ended' | 'session_onging',
      eventTime: Date,
      logTime: Date,
      username: string,
      duration: number,
      extraData?: Record<string, any>): Promise<void>;
    // Other session-specific methods...
}

export class UserSessionStrategy implements SessionStrategy {
  async handlePageLoad(message: PageLoadMessage, sender: chrome.runtime.MessageSender, sendResponse: (response: PageLoadResponse) => void): Promise<void> {
    // Implementation for UserSession
  }

  async handleUserInput(message: UserInputMessage, sender: chrome.runtime.MessageSender, sendResponse: (response: UserInputResponse) => void): Promise<void> {
    // Implementation for UserSession
  }

  calcSessionKey(userId: string, orgId: string, additionalParams: any): string {
    return UserSession.calcSessionKey(userId, orgId, additionalParams);
  }
  

  getSessionType(): SessionType {
    return SessionType.UserSession;
  }

  serializeSession(session: ActiveSession): any {
    return (session as UserSession).serialize();
  }

  async reportToSessionLog(
      event: 'session_started' | 'session_ended' | 'session_onging',
      eventTime: Date,
      logTime: Date,
      username: string,
      duration: number = 0,
      extraData?: Record<string, any>): Promise<void> {
    logSessionEvent(event, eventTime, logTime, username, duration, extraData);
  }
}


export class ChartSessionStrategy implements SessionStrategy {
    async handlePageLoad(message: PageLoadMessage, sender: chrome.runtime.MessageSender, sendResponse: (response: PageLoadResponse) => void): Promise<void> {
      // Implementation for ChartSession
    }
  
    async handleUserInput(message: UserInputMessage, sender: chrome.runtime.MessageSender, sendResponse: (response: UserInputResponse) => void): Promise<void> {
      // Implementation for ChartSession
    }

    calcSessionKey(userId: string, orgId: string, additionalParams: any): string {
        return ChartSession.calcSessionKey(userId, orgId, additionalParams);
    }
    

    getSessionType(): SessionType {
        return SessionType.ChartSession;
    }

    serializeSession(session: ActiveSession): any {
        return (session as ChartSession).serialize();
    }

    async reportToSessionLog(event: 'session_started' | 'session_ended' | 'session_onging',
      eventTime: Date,
      logTime: Date,
      username: string,
      duration: number = 0,
      extraData?: Record<string, any>): Promise<void> {
      logger.debug('ChartSessionStrategy does not report sessions to event to log:', event);
    }
  
    // Other session-specific methods...
  }