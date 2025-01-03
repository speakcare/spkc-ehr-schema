interface Session {
    userId: string;
    startTime: Date;
    lastActivityTime: Date | null;
  }
  
  const activeSessions: Record<string, Session> = {};
  
  export function manageSession(cookie: chrome.cookies.Cookie) {
    const subdomain = cookie.domain;
    if (cookie.name === 'JSESSIONID') {
      handleLogin(subdomain);
    } else if (cookie.name === 'last_org') {
      const userId = cookie.value;
      if (userId) {
        handleUserIdChange(subdomain, userId);
      }
    }
  }
  
  function handleLogin(subdomain: string) {
    if (activeSessions[subdomain]) {
      terminateSession(subdomain);
    }
  
    activeSessions[subdomain] = {
      userId: '',
      startTime: new Date(),
      lastActivityTime: null,
    };
    logEvent(subdomain, 'session_started', activeSessions[subdomain].startTime);
  }
  
  function handleUserIdChange(subdomain: string, userId: string) {
    if (!activeSessions[subdomain]) return;
  
    activeSessions[subdomain].userId = userId;
  }
  
  function terminateSession(subdomain: string) {
    const session = activeSessions[subdomain];
    if (!session) return;
  
    const endTime = session.lastActivityTime || new Date();
    const duration = endTime.getTime() - session.startTime.getTime();
  
    logEvent(subdomain, 'session_ended', endTime, { duration });
  
    delete activeSessions[subdomain];
  }
  
  export function logEvent(
    subdomain: string,
    event: string,
    timestamp: Date,
    extraData?: Record<string, any>
  ) {
    const eventLog = {
      subdomain,
      event,
      timestamp: timestamp.toISOString(),
      ...extraData,
    };
  
    const logs = JSON.parse(localStorage.getItem('session_logs') || '[]');
    logs.push(eventLog);
    localStorage.setItem('session_logs', JSON.stringify(logs));
  }
  