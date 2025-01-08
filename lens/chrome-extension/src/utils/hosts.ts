import { Tab } from '../types/index.d';  

const allowedUrlPatterns = [
    /^https?:\/\/.*\.pointclickcare\.com\/.*/, // Matches URLs like "https://*.pointclickcare.com"
  ];

  export function isUrlAllowed(url: string): boolean {
    if (!url) return false;
    return allowedUrlPatterns.some((pattern) => pattern.test(url));
  }
  
  export function isTabUrlAllowed(tab: Tab): boolean {
    if (!tab.url) return false; 
    const url = new URL(tab.url);
    //return url && validUrlPatterns.some((pattern) => pattern.test(url.href));
    return url && isUrlAllowed(url.href);
  }