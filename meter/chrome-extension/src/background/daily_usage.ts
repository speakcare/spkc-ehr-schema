import { ActiveSession, ChartSession, UserSession, SessionType } from './sessions'



function getDateString(date: Date): string {
    return date.toISOString().split('T')[0];
}



/*
* DailyUsageDTO (Data Transfer Object) interface
*/
interface DailyUsageDTO {
    date: string;
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
    private type: SessionType;
    private fields: { [key: string]: any };
    private currentSessionDuration: number
    private totalDuration: number;

    private static dailyUsages: Record<string, DailyUsage> = {};
    private static dailyUsagesLoaded: boolean = false;

     // Overloaded constructor signatures
    constructor(session: ActiveSession);
    constructor(dto: DailyUsageDTO);

    constructor(arg: ActiveSession | DailyUsageDTO) {
        if (arg instanceof ActiveSession) {
            this.date = getDateString(arg.getStartTime());
            this.fields = arg.getIdentifierFields();
            this.type = arg.getType();
            this.currentSessionDuration = arg.duration();
            this.totalDuration = 0;
        }
        else {
            this.date = arg.date;
            this.type = arg.type;
            this.fields = arg.fields;
            this.currentSessionDuration = arg.currentSessionDuration;
            this.totalDuration = arg.totalDuration;
        }
    }

    serialize(): DailyUsageDTO {
        return {
            date: this.date,
            type: this.type,
            fields: this.fields,
            currentSessionDuration: this.currentSessionDuration,
            totalDuration: this.totalDuration
        };
    }

    static deserialize(dto: DailyUsageDTO): DailyUsage {
        const dailyUsage = new DailyUsage(dto);
        return dailyUsage;
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
        DailyUsage.saveDailyUsagesToLocalStorage();
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
        DailyUsage.saveDailyUsagesToLocalStorage();
        return;
    }

    static getAllDailyUsages(): Record<string, DailyUsage> {
        if (!DailyUsage.dailyUsagesLoaded) {
            throw new Error('updateSession: Daily usages not loaded yet');
        }
        return DailyUsage.dailyUsages;
    }

    // Private static functions
    private static addDailyUsage(dailyUsage: DailyUsage): void {
        DailyUsage.dailyUsages[dailyUsage.getKey()] = dailyUsage;
    }

    private static createDailyUsage(session: ActiveSession): DailyUsage {
        return new DailyUsage(session);
    }

    static async getDailyUsagesFromLocalStorage(): Promise<Record<string, DailyUsage>> {
        return new Promise((resolve, reject) => {
          chrome.storage.local.get('dailyUsages', (result) => {
            if (chrome.runtime.lastError) {
              console.error('Failed to load daily usages from local storage:', chrome.runtime.lastError);
              reject(chrome.runtime.lastError);
            } else {
              const dailyUsages = result.dailyUsages || {};
              const usages: Record<string, DailyUsage> = {};
              for (const key in dailyUsages) {
                if (dailyUsages.hasOwnProperty(key)) {
                  const usageDTO = dailyUsages[key];
                  usages[key] = DailyUsage.deserialize(usageDTO);
                }
              }
              resolve(usages);
            }
          });
        });
      }
      
      static async saveDailyUsagesToLocalStorage(/*dailyUsages: Record<string, DailyUsage>*/): Promise<void> {
        return new Promise((resolve, reject) => {
          const usagesToSave = Object.fromEntries(
            Object.entries(DailyUsage.dailyUsages).map(([key, usage]) => [
              key, usage.serialize(),
            ])
          );
          chrome.storage.local.set({ dailyUsages: usagesToSave }, () => {
            if (chrome.runtime.lastError) {
              console.error('Failed to save daily usages to local storage:', chrome.runtime.lastError);
              reject(chrome.runtime.lastError);
            } else {
              resolve();
            }
          });
        });
      }
      
      // Load active sessions from local storage
      static async loadDailyUsages(): Promise<void> {
        DailyUsage.dailyUsages = await DailyUsage.getDailyUsagesFromLocalStorage();
        DailyUsage.dailyUsagesLoaded = true;
        console.log('Loaded daily usages:', DailyUsage.dailyUsages);
      }

      static async initialize(): Promise<void> {
        console.log('Initializing daily usages...');
        await DailyUsage.loadDailyUsages();
      }
}


function getAllDailyUsages(): Record<string, DailyUsage> {
    return DailyUsage.getAllDailyUsages();
}

export function printUserDailies(): void {
    console.log('User daylies:', DailyUsage.getAllDailyUsages());
}

(globalThis as any).printUserDailies = printUserDailies;
