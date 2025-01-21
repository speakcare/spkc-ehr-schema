// Global type definitions


  export type SessionLogEvent = {
    event : 'session_started' | 'session_ended' | 'session_onging',
    eventTime: string,
    logTime: string,
    username: string,
    duration: number,
  }

  export interface ActiveSession {
    userId: string;
    orgId: string;
    startTime: Date; // the actual start time when the session was created
    userActivitySeen: boolean; // Flag to indicate if user activity has been seen - used to determine session start
    lastActivityTime: Date | null;
    _expirationTimer?: NodeJS.Timeout; // Non-enumerable property for the timer
}

  export interface Tab {
    id: number;
    url?: string;
  }

interface BasicResponse {
    success: boolean;
    error?: string;
}
  
  // Define all message types
interface PageEventMessage {
  username: string;
  orgCode: string;
  timestamp: string;
  chartType: string;
  chartName: string;
}

interface PageLoadMessage extends PageEventMessage {
  type: 'page_load';
  pageStartTime: string;
}

interface PageLoadResponse extends BasicResponse {
  type: 'page_load_response';
}

interface UserInputMessage extends PageEventMessage {
  type: 'user_input';
  input: string;
  inputType: 'text' | 'textarea' | 'checkbox' | 'radio' | 'dropdown' | 'multiselect' | 'button' | 'other';
}

interface UserInputResponse extends BasicResponse {
  type: 'user_input_response';
}

interface ActiveSessionsGetMessage {
  type: 'active_sessions_get';
}

interface ActiveSessionsResponse extends BasicResponse {
  type: 'active_sessions_get_response';
  activeSessions: ActiveSession[];
}

interface SessionsLogsGetMessage {
  type: 'session_logs_get';
}

interface SessionsLogsGetResponse extends BasicResponse {
  type: 'session_logs_get_response';
  sessionLogs: SessionLogEvent[];
}

interface SessionsLogsClearMessage {
  type: 'session_logs_clear';
}

interface SessionsLogsClearResponse extends BasicResponse {
  type: 'session_logs_clear_response';
}

// Message interfaces for session timeout
interface SessionTimeoutSetMessage {
  type: 'session_timeout_set';
  timeout: number;
}

interface SessionTimeoutSetResponse extends BasicResponse {
  type: 'session_timeout_set_response';
}

interface SessionTimeoutGetMessage {
  type: 'session_timeout_get';
}

interface SessionTimeoutGetResponse extends BasicResponse {
  type: 'session_timeout_get_response';
  timeout: number | null;
}


type BackgroundMessage = PageLoadMessage | UserInputMessage | ActiveSessionsGetMessage | SessionsLogsGetMessage | 
                         SessionsLogsClearMessage | SessionTimeoutSetMessage | SessionTimeoutGetMessage;
type BackgroundResponse =  PageLoadResponse | UserInputResponse | ActiveSessionsResponse | SessionsLogsGetResponse | 
                           SessionsLogsClearResponse | SessionTimeoutSetResponse | SessionTimeoutGetResponse;