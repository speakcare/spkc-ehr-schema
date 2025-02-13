import { BasicResponse } from '../types';
import { UserSessionDTO } from './sessions';


/*****************************************************/
// Session manager messages and responses
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

export type InputType = 'text' | 'textarea' | 'checkbox' | 'radio' | 'dropdown' | 'multiselect' | 'button' | 'link' | 'heading' | 'other' | undefined;

export interface UserInputMessage extends PageEventMessage {
type: 'user_input';
input: string;
inputType: InputType;
}

export interface UserInputResponse extends BasicResponse {
type: 'user_input_response';
}

export interface SessionsGetMessage {
type: 'user_sessions_get' | 'chart_sessions_get';
}

export interface SessionsGetResponse extends BasicResponse {
type: 'sessions_get_response';
sessions: any[];
}


/* Message interfaces for session timeout */
export interface SessionTimeoutSetMessage {
type: 'user_session_timeout_set' | 'chart_session_timeout_set';
timeout: number;
}

export interface SessionTimeoutSetResponse extends BasicResponse {
type: 'session_timeout_set_response';
}

export interface SessionTimeoutGetMessage {
type: 'user_session_timeout_get' | 'chart_session_timeout_get';
}

export interface SessionTimeoutGetResponse extends BasicResponse {
type: 'session_timeout_get_response';
timeout: number | null;
}

