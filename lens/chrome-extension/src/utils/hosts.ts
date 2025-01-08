import { Tab } from '../types/index.d';  

const permittedUrlPatterns = [
    /^https?:\/\/.*\.pointclickcare\.com\/.*/, // Matches URLs like "https://*.pointclickcare.com"
  ];

  export function isUrlPermitted(url: string): boolean {
    if (!url) return false;
    return permittedUrlPatterns.some((pattern) => pattern.test(url));
  }
  
  export function isDomainPermitted(domain: string): boolean {
    if (!domain) return false;
  
    // Construct a URL-like string for the domain
    const constructedUrl = `https://${domain.startsWith('.') ? domain.slice(1) : domain}`;
    return isUrlPermitted(constructedUrl);
  }

  export function isTabUrlPermitted(tab: Tab): boolean {
    if (!tab.url) return false; 
    const url = new URL(tab.url);
    return url && isUrlPermitted(url.href);
  }
