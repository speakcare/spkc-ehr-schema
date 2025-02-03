import { BasicResponse } from '.';
import { UserSessionDTO } from '../background/sessions';


/*****************************************************/
// Session maanger messages and responses
//*****************************************************/
// Define all message types
export interface PageEventMessage {
    username: string;
    orgCode: string;
    timestamp: string;
    chartType: string;
    chartName: string;
  }
  
  export interface PageLoadMessage extends PageEventMessage {
    type: 'page_load';
    pageStartTime: string;
  }
  
  export interface PageLoadResponse extends BasicResponse {
    type: 'page_load_response';
  }
  
  export interface UserInputMessage extends PageEventMessage {
    type: 'user_input';
    input: string;
    inputType: 'text' | 'textarea' | 'checkbox' | 'radio' | 'dropdown' | 'multiselect' | 'button' | 'other';
  }
  
  export interface UserInputResponse extends BasicResponse {
    type: 'user_input_response';
  }
  
  export interface SessionsGetMessage {
    type: 'sessions_get';
  }
  
  export interface SessionsResponse extends BasicResponse {
    type: 'sessions_get_response';
    //userSessions: UserSessionDTO[];
    sessions: any[];
  }
  
  
  // Message interfaces for session timeout
  export interface SessionTimeoutSetMessage {
    type: 'session_timeout_set';
    timeout: number;
  }
  
  export interface SessionTimeoutSetResponse extends BasicResponse {
    type: 'session_timeout_set_response';
  }
  
  export interface SessionTimeoutGetMessage {
    type: 'session_timeout_get';
  }
  
  export interface SessionTimeoutGetResponse extends BasicResponse {
    type: 'session_timeout_get_response';
    timeout: number | null;
  }