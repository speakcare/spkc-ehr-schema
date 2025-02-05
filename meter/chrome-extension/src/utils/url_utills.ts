import { Tab } from '../types';  


export function getPageUrl(): string {
  return window.location.href;
}

export function getPagePath(): string {
    return window.location.pathname;
}

const permittedUrlPatterns = [
    /^https?:\/\/usnpint\.pointclickcare\.com\/.*/, // Matches "https://usnpint.pointclickcare.com"
    /^https?:\/\/www[0-9]{2}\.pointclickcare\.com\/.*/ // Matches "https://www01.pointclickcare.com", "https://www99.pointclickcare.com"
  ];
  

  export function isUrlPermitted(url: string): boolean {
    if (!url) return false;
    return permittedUrlPatterns.some((pattern) => pattern.test(url));
  }
  
  export function isTabUrlPermitted(tab: Tab): boolean {
    if (!tab.url) return false; 
    const url = new URL(tab.url);
    return url && isUrlPermitted(url.href);
  }

  // Helper function to get a cookie value from a specific URL
export async function getCookieValueFromUrl(cookieName: string, url: string): Promise<string | null> {
  return new Promise((resolve, reject) => {
    chrome.cookies.get({ url, name: cookieName }, (cookie) => {
      if (chrome.runtime.lastError) {
        console.error(`Failed to get cookie ${cookieName} from ${url}:`, chrome.runtime.lastError.message);
        reject(chrome.runtime.lastError);
        return;
      }
      resolve(cookie?.value || null);
    });
  });
}

export async function getCookieFromUrl(cookieName: string, url: string): Promise<chrome.cookies.Cookie | null> {
  return new Promise((resolve, reject) => {
    chrome.cookies.get({ url, name: cookieName }, (cookie) => {
      if (chrome.runtime.lastError) {
        console.error(`Failed to get cookie ${cookieName} from ${url}:`, chrome.runtime.lastError.message);
        reject(chrome.runtime.lastError);
        return;
      }
      resolve(cookie|| null);
    });
  });
}

