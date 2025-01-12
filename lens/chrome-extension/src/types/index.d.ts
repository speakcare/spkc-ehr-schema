// Global type definitions


  export type SessionLogEvent = {
    domain: string
    event : 'session_started' | 'session_ended' | 'session_onging',
    eventTime: string,
    logTime: string,
    username: string,
    duration: number,
  }

  export interface ActiveSession {
    domain: string;
    userId: string;
    orgId: string;
    startTime: Date; // the actual start time when the session was created
    userActivitySeen: boolean; // Flag to indicate if user activity has been seen - used to determine session start
    lastActivityTime: Date | null;
}

  export interface Tab {
    id: number;
    url?: string;
  }

interface BackgroundResponse {
    success: boolean;
    error?: string;
}
  
  // Define all message types
interface PageLoadMessage {
  type: 'page_load';
  username: string;
  pageStartTime: string;
}

interface PageLoadResponse extends BackgroundResponse {
  type: 'page_load_response';
}

interface UserInputMessage {
  type: 'user_input';
  input: string;
  inputType: 'text' | 'textarea' | 'checkbox' | 'radio' | 'dropdown' | 'multiselect' | 'button' | 'other';
  username: string;
  timestamp: string;
  pageStartTime: string;
}

interface UserInputResponse extends BackgroundResponse {
  type: 'user_input_response';
}

interface ActiveSessionsGetMessage {
  type: 'active_sessions_get';
}

interface ActiveSessionsResponse extends BackgroundResponse {
  type: 'active_sessions_get_response';
  activeSessions: ActiveSession[];
}

interface SessionsLogsGetMessage {
  type: 'session_logs_get';
}

interface SessionsLogsGetResponse extends BackgroundResponse {
  type: 'session_logs_get_response';
  sessionLogs: SessionLogEvent[];
}

interface SessionsLogsClearMessage {
  type: 'session_logs_clear';
}

interface SessionsLogsClearResponse extends BackgroundResponse {
  type: 'session_logs_clear_response';
}


type BackgroundMessage = PageLoadMessage | UserInputMessage | ActiveSessionsGetMessage | SessionsLogsGetMessage | SessionsLogsClearMessage;
type BackgroundResponse =  PageLoadResponse | UserInputResponse | ActiveSessionsResponse | SessionsLogsGetResponse | SessionsLogsClearResponse;