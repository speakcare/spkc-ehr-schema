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
  