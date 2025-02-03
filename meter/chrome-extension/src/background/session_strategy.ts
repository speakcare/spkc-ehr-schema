import { PageLoadMessage, PageLoadResponse, UserInputMessage, UserInputResponse } from '../types/messages';
import { ActiveSession, ChartSession, UserSession, SessionType } from './sessions';

export interface SessionStrategy {
    handlePageLoad(message: PageLoadMessage, sender: chrome.runtime.MessageSender, sendResponse: (response: PageLoadResponse) => void): Promise<void>;
    handleUserInput(message: UserInputMessage, sender: chrome.runtime.MessageSender, sendResponse: (response: UserInputResponse) => void): Promise<void>;
    calcSessionKey(userId: string, orgId: string, additionalParams: any): string;
    getSessionType(): SessionType;
    serializeSession(session: ActiveSession): any;
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
  
    // Other session-specific methods...
  }