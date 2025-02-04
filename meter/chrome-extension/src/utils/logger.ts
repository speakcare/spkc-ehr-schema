export class Logger {
    private name: string;
    constructor(name: string) {
        this.name = name;
    }

    log(message?: any, ...optionalParams: any[]): void {
        console.log(`${this.name}:`, message, ...optionalParams);
    }
    error(message?: any, ...optionalParams: any[]): void {
        console.error(`${this.name}:`, message, ...optionalParams);
    }
    warn(message?: any, ...optionalParams: any[]): void {
        console.warn(`${this.name}:`, message, ...optionalParams);
    }
    info(message?: any, ...optionalParams: any[]): void {
        console.info(`${this.name}:`, message, ...optionalParams);
    }
    debug(message?: any, ...optionalParams: any[]): void {
        console.debug(`${this.name}:`, message, ...optionalParams);
    }
}