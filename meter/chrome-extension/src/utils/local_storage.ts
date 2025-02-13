export class LocalStorage {
    private key: string;
  
    constructor(key: string) {
      this.key = key;
    }
  
    private getPrefixedKey(subKey: string): string {
      return `${this.key}:${subKey}`;
    }

    async getSingleItem(): Promise<any> {
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
  
    async setSingleItem(value: any): Promise<void> {
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

    async getItems(subKeys: string[]): Promise<any> {
      const keys = subKeys.map(subKey => this.getPrefixedKey(subKey));
      return new Promise((resolve, reject) => {
        chrome.storage.local.get(keys, (result) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            const prefixedResult: { [key: string]: any } = {};
            subKeys.forEach(subKey => {
              prefixedResult[subKey] = result[this.getPrefixedKey(subKey)];
            });
            resolve(prefixedResult);
          }
        });
      });
    }

    async setItems(items: { [subKey: string]: any }): Promise<void> {
      const prefixedItems: { [key: string]: any } = {};
      Object.keys(items).forEach(subKey => {
        prefixedItems[this.getPrefixedKey(subKey)] = items[subKey];
      });
      return new Promise((resolve, reject) => {
        chrome.storage.local.set(prefixedItems, () => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            resolve();
          }
        });
      });
    }
  }

  