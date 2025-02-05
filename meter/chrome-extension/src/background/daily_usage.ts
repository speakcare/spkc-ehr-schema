import { ActiveSession, ChartSession, UserSession, SessionType } from './sessions'
import { BasicResponse } from '../types';
import { Logger } from '../utils/logger';
import { LocalStorage } from '../utils/local_stroage';



function getDateString(date: Date): string {
    return date.toISOString().split('T')[0];
}

function getTimeString(date: Date): string {
    return date.toISOString().split('T')[1];
}



/*
* DailyUsageDTO (Data Transfer Object) interface
*/
export interface DailyUsageDTO {
    date: string;
    startTime: string;
    type: SessionType;
    fields: { [key: string]: any };
    currentSessionDuration: number;
    totalDuration: number;
}

/**
 * DailyUsage class
 * This class is both an abstract class of different types of daily reports that has different properties
 */
export class DailyUsage {
    private date: string;
    private startTime: string;
    private type: SessionType;
    private fields: { [key: string]: any };
    private currentSessionDuration: number
    private totalDuration: number;

    private static dailyUsages: Record<string, DailyUsage> = {};
    private static dailyUsagesLoaded: boolean = false;
    private static logger = new Logger('DailyUsage');
    private static localStorage = new LocalStorage('dailyUsages');

     // Overloaded constructor signatures
    constructor(session: ActiveSession);
    constructor(dto: DailyUsageDTO);

    constructor(arg: ActiveSession | DailyUsageDTO) {
        if (arg instanceof ActiveSession) {
            this.date = getDateString(arg.getStartTime());
            this.startTime = getTimeString(arg.getStartTime());
            this.fields = arg.getIdentifierFields();
            this.type = arg.getType();
            this.currentSessionDuration = arg.duration();
            this.totalDuration = 0;
        }
        else {
            this.date = arg.date;
            this.startTime = arg.startTime;
            this.type = arg.type;
            this.fields = arg.fields;
            this.currentSessionDuration = arg.currentSessionDuration;
            this.totalDuration = arg.totalDuration;
        }
    }

    serialize(): DailyUsageDTO {
        return {
            date: this.date,
            startTime: this.startTime,
            type: this.type,
            fields: this.fields,
            currentSessionDuration: this.currentSessionDuration,
            totalDuration: this.totalDuration
        };
    }

    static serialize(dailyUsage: DailyUsage): DailyUsageDTO {
        return dailyUsage.serialize();
    }

    static deserialize(dto: DailyUsageDTO): DailyUsage {
        const dailyUsage = new DailyUsage(dto);
        return dailyUsage;
    }

    // Object methods
    getKey(): string {
        return DailyUsage.calculateKey(this.date, this.fields);
    }

    public getDuration(): number {
        return this.totalDuration + this.currentSessionDuration;
    }
    public getDate(): string {
        return this.date;
    }
    public getStartTime(): string {
        return this.startTime;
    }
    public getType(): SessionType {
        return this.type;
    }
    public getUsername(): string {
        return ActiveSession.getUsername(this.fields.userId, this.fields.orgId);
    }
    public getFields(): { [key: string]: any } {
        return this.fields;
    }
      
    //public 

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

    static reportSession(session: ActiveSession): void {
        if (!DailyUsage.dailyUsagesLoaded) {
            throw new Error('updateSession: Daily usages not loaded yet');
        }
        const key = DailyUsage.calcKeyFromSession(session);
        let dailyUsage = DailyUsage.getDailyUsageByKey(key);
        if (dailyUsage) {
            dailyUsage.updateCurrentSession(session);
        }
        else { // no daily yet
            dailyUsage = DailyUsage.createDailyUsage(session);
            DailyUsage.addDailyUsage(dailyUsage);
        }
        DailyUsage.saveToLocalStorage();
        return;
    }

    static closeSession(session: ActiveSession): void {
        if (!DailyUsage.dailyUsagesLoaded) {
            throw new Error('updateSession: Daily usages not loaded yet');
        }
        const key = DailyUsage.calcKeyFromSession(session);
        let dailyUsage = DailyUsage.getDailyUsageByKey(key);
        if (dailyUsage) {
            dailyUsage.totalDuration += dailyUsage.currentSessionDuration;
            dailyUsage.currentSessionDuration = 0;
        }
        DailyUsage.saveToLocalStorage();
        return;
    }

    static getAllDailyUsages(): Record<string, DailyUsage> {
        if (!DailyUsage.dailyUsagesLoaded) {
            throw new Error('updateSession: Daily usages not loaded yet');
        }
        return DailyUsage.dailyUsages;
    }

    static async clearDailyUsages(): Promise<void> {
        DailyUsage.dailyUsages = {};
        DailyUsage.saveToLocalStorage();
    }

    static getDailyUsagesByType(type: SessionType): Record<string, DailyUsage> {
      if (!DailyUsage.dailyUsagesLoaded) {
        throw new Error('updateSession: Daily usages not loaded yet');
      }
  
      return Object.fromEntries(
        Object.entries(DailyUsage.dailyUsages).filter(([key, usage]) => usage.type === type)
      );
    }

    // Private static functions
    private static addDailyUsage(dailyUsage: DailyUsage): void {
        DailyUsage.dailyUsages[dailyUsage.getKey()] = dailyUsage;
    }

    private static createDailyUsage(session: ActiveSession): DailyUsage {
        return new DailyUsage(session);
    }

    private static async getFromLocalStorage(): Promise<Record<string, DailyUsage>> {
      const dtos = await DailyUsage.localStorage.getItem();
      const dailyUsages: Record<string, DailyUsage> = {};
      for (const key in dtos) {
        if (dtos.hasOwnProperty(key)) {
          const dto = dtos[key];
          dailyUsages[key] = DailyUsage.deserialize(dto);;
        }
      }
      return dailyUsages;
    }
  
    private static async saveToLocalStorage(): Promise<void> {
      const dtos = Object.fromEntries(
        Object.entries(DailyUsage.dailyUsages).map(([key, usage]) => [
          key, usage.serialize(),
        ])
      );
      await DailyUsage.localStorage.setItem(dtos);
    }
            
    // Load active sessions from local storage
    static async loadDailyUsages(): Promise<void> {
      DailyUsage.dailyUsages = await DailyUsage.getFromLocalStorage();
      DailyUsage.dailyUsagesLoaded = true;
      DailyUsage.logger.log('Loaded daily usages:', DailyUsage.dailyUsages);
    }

    static async initialize(): Promise<void> {
      DailyUsage.logger.log('Initializing daily usages...');
      await DailyUsage.loadDailyUsages();
    }
    
    // Message handlers
    static async handleDailyUsageGet(
        message: DailyUsageGetMessage, 
        sendResponse: (response: DailyUsageGetResponse) => void): Promise<void> 
      {
        try {
          const dailies = DailyUsage.getAllDailyUsages();
          if (dailies) {
            const dailiesArray: DailyUsage[] = Object.values(dailies); 
            const dtos = dailiesArray.map(daily => daily.serialize());
            sendResponse({ type: 'daily_usage_get_response', success: true, dailyUsages: dtos });
          } else {
            DailyUsage.logger.warn('handleDailyUsageGet: Active sessions are not initialized.');
            sendResponse({ type: 'daily_usage_get_response', success: false, error: 'Active sessions are not initialized', dailyUsages: [] });
          }
        } catch (error) {
          DailyUsage.logger.error('handleDailyUsageGet: Unexpected error:', error);
          sendResponse({ type: 'daily_usage_get_response', success: false, error: 'Failed to retrieve active sessions', dailyUsages: [] });
        }
      }

    static async handleDailyUsageClear(
        message: DailyUsageClearMessage, 
        sendResponse: (response: DailyUsageClearResponse) => void): Promise<void> 
    {
        try {
          await DailyUsage.clearDailyUsages();
          sendResponse({ type: 'daily_usage_clear_response', success: true });
        } catch (error) {
          DailyUsage.logger.error('handleDailyUsageClear: Unexpected error:', error);
          sendResponse({ type: 'daily_usage_clear_response', success: false, error: 'Failed to clear active sessions' });
        }
    }
}

// Debug functions
export function getAllDailies(): Record<string, DailyUsage> {
    return DailyUsage.getAllDailyUsages();
}
export function getUserDailies(): Record<string, DailyUsage> {
    return DailyUsage.getDailyUsagesByType(SessionType.UserSession);
}
export function getChartDailies(): Record<string, DailyUsage> {
    return DailyUsage.getDailyUsagesByType(SessionType.ChartSession);
}
export function prinallDailies(): void {
    console.log('Daily usages:', DailyUsage.getAllDailyUsages());
}
export function printUserDailies(): void {
    console.log('User dailies:', DailyUsage.getDailyUsagesByType(SessionType.UserSession));
}
export function printChartDailies(): void {
    console.log('Chart dailies:', DailyUsage.getDailyUsagesByType(SessionType.ChartSession));
}

export function clearDailies(): void {
    DailyUsage.clearDailyUsages();
}

/***********************************
 * Daily Usage messages
 **********************************/

export interface DailyUsageGetMessage {
  type: 'daily_usage_get';
}
export interface DailyUsageGetResponse extends BasicResponse {
  type: 'daily_usage_get_response';
  dailyUsages: DailyUsageDTO[];
}
export interface DailyUsageClearMessage {
  type: 'daily_usage_clear';
}
export interface DailyUsageClearResponse extends BasicResponse {
  type: 'daily_usage_clear_response';
}

/************************
* Message Handlers
************************/
export async function handleDailyUsageGet(
  message: DailyUsageGetMessage, 
  sendResponse: (response: DailyUsageGetResponse) => void): Promise<void> 
{
  DailyUsage.handleDailyUsageGet(message, sendResponse);
}

export async function handleDailyUsageClear(
  message: DailyUsageClearMessage, 
  sendResponse: (response: DailyUsageClearResponse) => void): Promise<void> 
{
  DailyUsage.handleDailyUsageClear(message, sendResponse);
}

/***********************************
 * Console registrations
 **********************************/
(globalThis as any).getAllDailies = getAllDailies;
(globalThis as any).getUserDailies = getUserDailies;
(globalThis as any).getChartDailies = getChartDailies;
(globalThis as any).prinallDailies = prinallDailies;
(globalThis as any).printUserDailies = printUserDailies;
(globalThis as any).printChartDailies = printChartDailies;


