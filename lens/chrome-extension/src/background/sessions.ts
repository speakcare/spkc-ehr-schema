export abstract class ActiveSession {
  userId: string;
  orgId: string;
  startTime: Date; // the actual start time when the session was created
  userActivitySeen: boolean; // Flag to indicate if user activity has been seen - used to determine session start
  lastActivityTime: Date | null;
  _expirationTimer?: NodeJS.Timeout; // Non-enumerable property for the timer

  constructor(
    userId: string,
    orgId: string,
    startTime: Date,
    userActivitySeen: boolean = false,
    lastActivityTime: Date | null = null,
  ) {
    this.userId = userId;
    this.orgId = orgId;
    this.startTime = startTime;
    this.userActivitySeen = userActivitySeen;
    this.lastActivityTime = lastActivityTime;
    this._expirationTimer = undefined;
  }
  duration(): number {
    return this.lastActivityTime ? (this.lastActivityTime.getTime() - this.startTime.getTime())/1000 : 0;
  }
  abstract getSessionKey(): string;
}


export interface UserSessionDTO {
    userId: string;
    orgId: string;
    startTime: Date; // Use string to represent date in ISO format
    userActivitySeen: boolean;
    lastActivityTime: Date | null;
}
  
export interface ChartSessionDTO {
    userId: string;
    orgId: string;
    chartType: string;
    chartName: string
    startTime: string; // Use string to represent date in ISO format
    userActivitySeen: boolean;
    lastActivityTime: string | null;
}


export class UserSession extends ActiveSession {

  static calcSessionKey(userId: string, orgId: string): string {
    return `${userId}@${orgId}`;
  }
  getSessionKey(): string {
    return UserSession.calcSessionKey(this.userId, this.orgId);
  }

  static serialize(session: UserSession): UserSessionDTO {
    return {
      userId: session.userId,
      orgId: session.orgId,
      startTime: session.startTime,//.toISOString(),
      userActivitySeen: session.userActivitySeen,
      lastActivityTime: session.lastActivityTime ? session.lastActivityTime : null,// .toISOString() : null,
    };
  }
}

export class ChartSession extends ActiveSession {
  chartType: string;
  chartName: string;

  constructor(
    userId: string,
    orgId: string,
    startTime: Date,
    chartType: string,
    chartName: string,
    userActivitySeen: boolean = false,
    lastActivityTime: Date | null = null,
  ) {
    super(userId, orgId, startTime, userActivitySeen, lastActivityTime);
    this.chartType = chartType;
    this.chartName = chartName;
  }

  static calcSessionKey(userId: string, orgId: string, chartType: string, chartName: string): string {
    return `${userId}@${orgId}-${chartType}-${chartName}`;
  }
  getSessionKey(): string {
    return ChartSession.calcSessionKey(this.userId, this.orgId, this.chartType, this.chartName);
  }

  static serialize(session: ChartSession): ChartSessionDTO {
    return {
      userId: session.userId,
      orgId: session.orgId,
      chartType: session.chartType,
      chartName: session.chartName,
      startTime: session.startTime.toISOString(),
      userActivitySeen: session.userActivitySeen,
      lastActivityTime: session.lastActivityTime ? session.lastActivityTime.toISOString() : null,
    };
  }
}  
