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


