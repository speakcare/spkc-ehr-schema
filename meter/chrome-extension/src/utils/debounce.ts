export class DebounceThrottle {
    private debounceDelay: number;
    private throttleDelay: number;
    private debounceTimer: NodeJS.Timeout | null = null;
    private lastExecuteTime: number = 0;
  
    constructor(debounceDelay: number, throttleDelay: number) {
      this.debounceDelay = debounceDelay;
      this.throttleDelay = throttleDelay;
    }
  
    public debounce(callback: () => void) {
      const now = Date.now();
  
      if (this.debounceTimer) {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = null;
      }
  
      // Throttle: Execute the callback if `throttleDelay` has passed since the last execution
      if (now - this.lastExecuteTime >= this.throttleDelay) {
        callback();
        this.lastExecuteTime = now;
        return;
      }
  
      // Debounce: Delay execution until user stops interacting
      this.debounceTimer = setTimeout(() => {
        callback();
        this.lastExecuteTime = Date.now();
      }, this.debounceDelay);
    }
    public clearTimer() {
      if (this.debounceTimer) {
        clearTimeout(this.debounceTimer);
        this.debounceTimer = null;
      }
    }
  }