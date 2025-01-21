import { UserDailyUsage, UserSession } from "../types";

let dailyUsages: Record<string, UserDailyUsage> = {};

function getDateString(date: Date): string {
    return date.toISOString().split('T')[0];
}

function calcUserDailyKey(userId: string, orgId: string, startTime: Date): string {
    // get the date part of the startDate string
    let date = getDateString(startTime)
    return `${date}:${userId}@${orgId}`;
}

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

export function printUserDaylies(): void {
    console.log('User daylies:', dailyUsages);
}

(globalThis as any).printUserDaylies = printUserDaylies;
