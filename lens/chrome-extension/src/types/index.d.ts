// Global type definitions

export type SessionLog = {
    userId: string;
    startTime: string;
    lastActivityTime?: string;
    duration?: number; // Duration in milliseconds
  };

  export interface Tab {
    id: number;
    url?: string;
  }
  