const activeSessions = {};
export function manageSession(cookie) {
    const subdomain = cookie.domain;
    if (cookie.name === 'JSESSIONID') {
        handleLogin(subdomain);
    }
    else if (cookie.name === 'last_org') {
        const userId = cookie.value;
        if (userId) {
            handleUserIdChange(subdomain, userId);
        }
    }
}
function handleLogin(subdomain) {
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
function handleUserIdChange(subdomain, userId) {
    if (!activeSessions[subdomain])
        return;
    activeSessions[subdomain].userId = userId;
}
function terminateSession(subdomain) {
    const session = activeSessions[subdomain];
    if (!session)
        return;
    const endTime = session.lastActivityTime || new Date();
    const duration = endTime.getTime() - session.startTime.getTime();
    logEvent(subdomain, 'session_ended', endTime, { duration });
    delete activeSessions[subdomain];
}
export function logEvent(subdomain, event, timestamp, extraData) {
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
