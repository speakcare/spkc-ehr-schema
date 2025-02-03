export enum SessionType {
  UserSession = 'UserSession',
  ChartSession = 'ChartSession',
}

export abstract class ActiveSession {
  protected userId: string;
  protected orgId: string;
  protected startTime: Date; // the actual start time when the session was created
  protected activitySeen: boolean; // Flag to indicate if user activity has been seen - used to determine session start
  protected lastActivityTime: Date | null;
  private _expirationTimer?: NodeJS.Timeout; // Non-enumerable property for the timer

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
    this.activitySeen = userActivitySeen;
    this.lastActivityTime = lastActivityTime;
    this._expirationTimer = undefined;

    // Define _expirationTimer as a non-enumerable property
    Object.defineProperty(this, '_expirationTimer', {
                    enumerable: false,
                    configurable: true,
                    writable: true,
                    value: undefined // Initialize with undefined
                  });
  }
  duration(): number {
    return this.lastActivityTime ? (this.lastActivityTime.getTime() - this.startTime.getTime())/1000 : 0;
  }

  // Getters and setters
  getUserId(): string {
    return this.userId;
  }
  getOrgId(): string {
    return this.orgId;
  }
  getStartTime(): Date {
    return this.startTime;
  }
  getActivitySeen(): boolean {
    return this.activitySeen;
  }
  setActivitySeen(userActivitySeen: boolean): void {
    this.activitySeen = userActivitySeen;
  }

  getLastActivityTime(): Date | null {
    return this.lastActivityTime;
  }
  setLastActivityTime(lastActivityTime: Date): void {
    this.lastActivityTime = lastActivityTime;
  }
  setExpirationTimer(timer: NodeJS.Timeout): void {
    this.clearExpirationTimer();
    this._expirationTimer = timer;
  }
  clearExpirationTimer(): void {
    if (this._expirationTimer) {
      clearTimeout(this._expirationTimer);
      delete this._expirationTimer;
      this._expirationTimer = undefined;
    }
  }


  abstract getSessionKey(): string;
  abstract getIdentifierFields(): { [key: string]: any };
  abstract getType(): SessionType;
  abstract serialize(): any;
}


export interface UserSessionDTO {
    userId: string;
    orgId: string;
    startTime: string; 
    userActivitySeen: boolean;
    lastActivityTime: string | null;
}
  
export interface ChartSessionDTO {
    userId: string;
    orgId: string;
    chartType: string;
    chartName: string
    startTime: string; 
    userActivitySeen: boolean;
    lastActivityTime: string | null;
}


export class UserSession extends ActiveSession {

  static calcSessionKey(userId: string, orgId: string, additionalParams: any = {}): string {
    // we don't use the additionalParams here but they are required for generic function signature
    return `${userId}@${orgId}`;
  }
  getSessionKey(): string {
    return UserSession.calcSessionKey(this.userId, this.orgId);
  }
  getIdentifierFields(): { [key: string]: any } {
    return {
      userId: this.userId,
      orgId: this.orgId,
    };
  }
  getType(): SessionType {
    return SessionType.UserSession;
  }

  serialize(): any {
    return {
      userId: this.userId,
      orgId: this.orgId,
      startTime: this.startTime.toISOString(),
      userActivitySeen: this.activitySeen,
      lastActivityTime: this.lastActivityTime?.toISOString() || null,// this.lastActivityTime : null,// .toISOString() : null,
    };
  }

  static serialize(session: UserSession): UserSessionDTO {
    return session.serialize();
  }
  
  static deserialize(dto: UserSessionDTO): UserSession {
    return new UserSession(
      dto.userId,
      dto.orgId,
      new Date(dto.startTime),
      dto.userActivitySeen,
      dto.lastActivityTime ? new Date(dto.lastActivityTime) : null
    );
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

  static calcSessionKey(userId: string, orgId: string, additionalParams: any = {}): string {
    const { chartType, chartName } = additionalParams;
    return `${userId}@${orgId}-${chartType}-${chartName}`;
  }
  
  // static calcSessionKey(userId: string, orgId: string, chartType: string, chartName: string): string {
  //   return `${userId}@${orgId}-${chartType}-${chartName}`;
  // }
  getSessionKey(): string {
    return ChartSession.calcSessionKey(this.userId, this.orgId, 
                                      {chartType: this.chartType, chartName: this.chartName});
  }

  getIdentifierFields(): { [key: string]: any } {
    return {
      userId: this.userId,
      orgId: this.orgId,
      chartType: this.chartType,
      chartName: this.chartName,
    };
  }
  getType(): SessionType {
    return SessionType.ChartSession;
  }

  serialize(): any {
    return {
      userId: this.userId,
      orgId: this.orgId,
      startTime: this.startTime.toISOString(),
      chartType: this.chartType,
      chartName: this.chartName,
      userActivitySeen: this.activitySeen,
      lastActivityTime: this.lastActivityTime ? this.lastActivityTime.toISOString() : null,
    };
  }

  static serialize(session: ChartSession): ChartSessionDTO {
    return session.serialize();
  }
}  
