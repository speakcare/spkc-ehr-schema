export class LocalStorage {
    private key: string;
  
    constructor(key: string) {
      this.key = key;
    }
  
    async getItem(): Promise<any> {
      return new Promise((resolve, reject) => {
        chrome.storage.local.get(this.key, (result) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            resolve(result[this.key]);
          }
        });
      });
    }
  
    async setItem(value: any): Promise<void> {
      return new Promise((resolve, reject) => {
        chrome.storage.local.set({ [this.key]: value }, () => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            resolve();
          }
        });
      });
    }
  }