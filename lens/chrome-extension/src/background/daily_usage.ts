import { create } from '@mui/material/styles/createTransitions';
import { ActiveSession, ChartSession, UserSession, SessionType } from './sessions'



function getDateString(date: Date): string {
    return date.toISOString().split('T')[0];
}

/**
 * DailyUsage class
 * This class is both an abstract class of different types of daily reports that has different properties
 */
export class DailyUsage {
    private date: string;
    private type: SessionType;
    private fields: { [key: string]: any };
    private currentSessionDuration: number
    private totalDuration: number;
    private static dailyUsages: Record<string, DailyUsage> = {};
    constructor(
        session: ActiveSession
    ) {
        this.date = getDateString(session.getStartTime());
        this.fields = session.getIdentifierFields();
        this.type = session.getType();
        this.currentSessionDuration = session.duration();
        this.totalDuration = 0;
    }

    // Object methods
    getKey(): string {
        return DailyUsage.calculateKey(this.date, this.fields);
    }

    // private object methods
    private updateCurrentSession(session: ActiveSession): void {
        this.currentSessionDuration = session.duration();
    }

    // Static functions to manage daily usage objects
    static calculateKey(date: string, fields: { [key: string]: any }): string {
        return `${date}:${Object.values(fields).join('_')}`
    }

    static calcKeyFromSession(session: ActiveSession): string {
        return DailyUsage.calculateKey(getDateString(session.getStartTime()), session.getIdentifierFields());
    }
    
    static getDailyUsageByKey(key: string): DailyUsage | null {
        return DailyUsage.dailyUsages[key] || null;
    }
    static getDailyUsageBySession(session: ActiveSession): DailyUsage | null {
        return this.getDailyUsageByKey(this.calcKeyFromSession(session));
    }

    static updateSession(session: ActiveSession): void {
        const key = DailyUsage.calcKeyFromSession(session);
        let dailyUsage = DailyUsage.getDailyUsageByKey(key);
        if (dailyUsage) {
            dailyUsage.updateCurrentSession(session);
        }
        else { // no daily yet
            dailyUsage = DailyUsage.createDailyUsage(session);
            DailyUsage.addDailyUsage(dailyUsage);
        }
        return;
    }

    static closeSession(session: ActiveSession): void {
        const key = DailyUsage.calcKeyFromSession(session);
        let dailyUsage = DailyUsage.getDailyUsageByKey(key);
        if (dailyUsage) {
            dailyUsage.totalDuration += dailyUsage.currentSessionDuration;
            dailyUsage.currentSessionDuration = 0;
        }
        return;
    }

    static getAllDailyUsages(): Record<string, DailyUsage> {
        return DailyUsage.dailyUsages;
    }

    // Private static functions
    private static addDailyUsage(dailyUsage: DailyUsage): void {
        DailyUsage.dailyUsages[dailyUsage.getKey()] = dailyUsage;
    }

    private static createDailyUsage(session: ActiveSession): DailyUsage {
        return new DailyUsage(session);
    }


}


function getAllDailyUsages(): Record<string, DailyUsage> {
    return DailyUsage.getAllDailyUsages();
}

export function printUserDailies(): void {
    console.log('User daylies:', DailyUsage.getAllDailyUsages());
}

(globalThis as any).printUserDailies = printUserDailies;
