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
  
  // Log an event to storage
export async function logEvent(
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

  try {
    const logs = await getSessionLogs();
    logs.push(eventLog);
    await saveSessionLogs(logs);
    console.log('Event logged:', eventLog);
  } catch (error) {
    console.error('Failed to log event:', error);
  }
}

// Helper to get all session logs from storage
export async function getSessionLogs(): Promise<any[]> {
  return new Promise((resolve) => {
    chrome.storage.local.get('session_logs', (result) => {
      resolve(result.session_logs || []);
    });
  });
}


// Helper to save session logs to storage
async function saveSessionLogs(logs: any[]): Promise<void> {
  return new Promise((resolve, reject) => {
    chrome.storage.local.set({ session_logs: logs }, () => {
      if (chrome.runtime.lastError) {
        reject(chrome.runtime.lastError);
      } else {
        resolve();
      }
    });
  });
}


const debouncedUpdates: Record<string, NodeJS.Timeout> = {};

export function updateLastActivity(subdomain: string, timestamp: Date) {
  const session = activeSessions[subdomain];
  if (!session) {
    console.warn(`No active session found for subdomain: ${subdomain}`);
    return;
  }

  session.lastActivityTime = timestamp;
  console.log(`Updated last activity time for ${subdomain}: ${timestamp}`);

  // Debounce the persistence
  if (debouncedUpdates[subdomain]) {
    clearTimeout(debouncedUpdates[subdomain]);
  }

  debouncedUpdates[subdomain] = setTimeout(() => {
    persistLastActivity(subdomain, timestamp);
  }, 3000); // Delay of 3 seconds
}
  
// Immediately flush updates for a specific subdomain
async function flushPendingUpdate(subdomain: string) {
  if (debouncedUpdates[subdomain]) {
    clearTimeout(debouncedUpdates[subdomain]);
    delete debouncedUpdates[subdomain];
  }
  const session = activeSessions[subdomain];
  if (session && session.lastActivityTime) {
    await persistLastActivity(subdomain, session.lastActivityTime);
  }
}



// Function to persist the last activity time
async function persistLastActivity(subdomain: string, timestamp: Date) {
  const logs = await getSessionLogs();
  const session = logs.find((log) => log.subdomain === subdomain && log.event === 'session_started');
  if (session) {
    session.lastActivityTime = timestamp.toISOString();
    await saveSessionLogs(logs);
    console.log(`Persisted last activity time for ${subdomain}: ${timestamp}`);
  }
}




function getSubdomainForTab(tabId: number): Promise<string | null> {
  return new Promise((resolve) => {
    chrome.tabs.get(tabId, (tab) => {
      if (chrome.runtime.lastError || !tab.url) {
        console.warn(`Failed to get tab information for tabId: ${tabId}`);
        resolve(null);
        return;
      }

      try {
        const url = new URL(tab.url);
        resolve(url.hostname); // Directly return the hostname
      } catch (err) {
        console.error(`Error parsing URL for tabId: ${tabId}`, err);
        resolve(null);
      }
    });
  });
}

const tabSubdomains: Record<number, string> = {};

chrome.tabs.onRemoved.addListener(async (tabId) => {
  console.log(`Tab closed: ${tabId}`);
  
  // Find the subdomain associated with the tab (if needed)
  //const subdomain = await getSubdomainForTab(tabId); // Implement as needed
  const subdomain = tabSubdomains[tabId];
  
  if (subdomain) {
    await flushPendingUpdate(subdomain);
    console.log(`Flushed lastActivityTime for ${subdomain} before tab closed.`);
  }
  // Remove the tab from the map
  delete tabSubdomains[tabId];
});

chrome.tabs.onUpdated.addListener(async (tabId, changeInfo, tab) => {
  if (changeInfo.status === 'loading' && tab.url) {
    console.log(`Tab navigation detected: ${tabId}`);
    
    const subdomain = await getSubdomainForTab(tabId);
    
    if (subdomain) {
      tabSubdomains[tabId] = subdomain;
      await flushPendingUpdate(subdomain);
      console.log(`Flushed lastActivityTime for ${subdomain} before navigation.`);
    }
  }
});

