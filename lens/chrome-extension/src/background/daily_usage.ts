import { create } from '@mui/material/styles/createTransitions';
import { ActiveSession, ChartSession, UserSession } from './sessions'


// export function updateUserDaily(session: UserSession, sessionClose: boolean= false): void {
//     return
// }
// import { UserSession } from './session_manager';

function getDateString(date: Date): string {
    return date.toISOString().split('T')[0];
}

export abstract class DailyUsage {
    date: string;
    userId: string;
    orgId: string; 
    currentSessionDuration: number
    totalDuration: number;

    constructor(
        session: ActiveSession
    ) {
        this.date = getDateString(session.startTime)
        this.userId = session.userId;
        this.orgId = session.orgId;
        this.currentSessionDuration = session.duration();
        this.totalDuration = 0;
    }

    static calcKey(sessionKey: string, date: string) {
        return `${date}:${sessionKey}`;
      }
    
    abstract getKey(): string;
    
    static getDailyUsage(key: string): DailyUsage | null {
        return dailyUsages[key] || null;
    }
    static addDailyUsage(dailyUsage: DailyUsage): void {
        dailyUsages[dailyUsage.getKey()] = dailyUsage;
    }

    static isUserSession(session: ActiveSession): session is UserSession {
        return (session as UserSession).getSessionKey !== undefined;
    }
      
    static isChartSession(session: ActiveSession): session is ChartSession {
        return (session as ChartSession).chartType !== undefined && (session as ChartSession).chartName !== undefined;
    }

    static createDailyUsage(session: ActiveSession): DailyUsage {
        if (DailyUsage.isUserSession(session)) {
          return new UserDailyUsage(session);
        } else if (DailyUsage.isChartSession(session)) {
          return new ChartDailyUsage(session);
        } else {
          throw new Error('Unknown session type');
        }
    }

    updateCurrentSession(session: ActiveSession): void {
        this.currentSessionDuration = session.duration();
    }

    static openSession(session: ActiveSession): void {
        const key = DailyUsage.calcKey(session.getSessionKey(), getDateString(session.startTime));
        let dailyUsage = DailyUsage.getDailyUsage(key);
        if (dailyUsage) {
            dailyUsage.updateCurrentSession(session);
        }
        else { // no daily yet
            dailyUsage = DailyUsage.createDailyUsage(session);
            DailyUsage.addDailyUsage(dailyUsage);
        }
        return;
    }
}

export class UserDailyUsage extends DailyUsage {
    constructor(session: UserSession) {
        super(session)
    }
    getKey(): string {
        return DailyUsage.calcKey(UserSession.calcSessionKey(
                                    this.userId, 
                                    this.orgId) , 
                                this.date);
    }
}
export class ChartDailyUsage extends DailyUsage {
    chartType: string;
    chartName: string;

    constructor(session: ChartSession
    ) {
        super(session)
        this.chartType = session.chartType;
        this.chartName = session.chartName;
    }

    getKey(): string {
        return DailyUsage.calcKey(ChartSession.calcSessionKey(
                                    this.userId, 
                                    this.orgId, 
                                    this.chartType, 
                                    this.chartName), 
                                  this.date);
    }

}

//type Usage = UserDailyUsage | ChartDailyUsage;
let dailyUsages: Record<string, DailyUsage> = {};

// let userDailies: Record<string, UserDailyUsage> = {};
// let chartDailies: Record<string, ChartDailyUsage> = {};


// function calcUserDailyKey(userId: string, orgId: string, startTime: Date): string {
//     // get the date part of the startDate string
//     let date = getDateString(startTime)
//     return `${date}:${userId}@${orgId}`;
// }

export function updateUserDaily(session: UserSession, sessionClose: boolean= false): void {

    const key = calcUserDailyKey(session.userId, session.orgId, session.startTime);
    const dailyUsage = dailyUsages[key];
    if (dailyUsage) {
        
        dailyUsage.lastActivityTime = session.lastActivityTime;
        console.log(`updateUserDaily: User ${dailyUsage.userId}@${dailyUsage.orgId} Date ${dailyUsage.date} last activity updated ${dailyUsage.lastActivityTime}`);
        if (sessionClose && dailyUsage.lastActivityTime) {
            // Add the last session duration to the total duration
            dailyUsage.totalDuration += (dailyUsage.lastActivityTime.getTime() - dailyUsage.currentSessionStartTime.getTime()) / 1000;
            console.log(`updateUserDaily closed: User ${dailyUsage.userId}@${dailyUsage.orgId} Date ${dailyUsage.date} total duration updated ${dailyUsage.totalDuration}`);
        }
        if (session.startTime > dailyUsage.currentSessionStartTime) {
            // A new ession has started
            // Update the current session start time to current session start time
            dailyUsage.currentSessionStartTime = session.startTime;
            console.log(`updateUserDaily new session: User ${dailyUsage.userId}@${dailyUsage.orgId} Date ${dailyUsage.date} current session start time updated ${dailyUsage.currentSessionStartTime}`);
        }
    } else {
        const daily = {
            date: getDateString(session.startTime),
            userId: session.userId,
            orgId: session.orgId,
            currentSessionStartTime: session.startTime,
            lastActivityTime: session.lastActivityTime,
            totalDuration: sessionClose && session.lastActivityTime ? (session.lastActivityTime.getTime() - session.startTime.getTime()) / 1000 : 0

        };
        dailyUsages[key] = daily
        console.log(`updateUserDaily: User ${daily.userId}@${daily.orgId} Date ${daily.date} created at ${daily.currentSessionStartTime}`);
    }
}

function getUserDaily(userId: string, orgId: string, startTime: Date): UserDailyUsage | null {
    const key = calcUserDailyKey(userId, orgId, startTime);
    return dailyUsages[key] || null;
}

function getAllUserDaily(): Record<string, UserDailyUsage> {
    return dailyUsages;
}

export function printUserDailies(): void {
    console.log('User daylies:', dailyUsages);
}

(globalThis as any).printUserDailies = printUserDailies;
