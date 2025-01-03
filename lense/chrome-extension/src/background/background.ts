import { manageSession, logEvent } from '../utils/session_manager';

chrome.cookies.onChanged.addListener((changeInfo) => {
  const { cookie, removed } = changeInfo;

  if (removed) return;

  if (cookie.domain.endsWith('.pointclickcare.com')) {
    manageSession(cookie);
  }
});
