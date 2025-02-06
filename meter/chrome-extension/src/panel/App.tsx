import React, { useState, useEffect } from 'react';
import { ActiveSession, ChartSession, UserSession, UserSessionDTO, ChartSessionDTO } from '../background/sessions';
import { SessionsGetResponse,  SessionTimeoutGetResponse, SessionTimeoutSetResponse } from '../background/session_messages'  
import { SessionLogEvent,  SessionsLogsGetResponse, SessionsLogsClearResponse, } from '../background/session_log';
import {
  AppBar,
  Toolbar,
  Typography,
  Button,
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Select,
  MenuItem,
  Paper,
  Dialog,
  DialogActions,
  DialogContent,
  DialogContentText,
  DialogTitle,
  IconButton,
} from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import { makeStyles } from '@mui/styles';
import { Logger } from '../utils/logger';
import { DailyUsage, DailyUsageGetMessage, DailyUsageGetResponse, 
         DailyUsageClearMessage, DailyUsageClearResponse, DailyUsageDTO } from '../background/daily_usage';

const useStyles = makeStyles({
  tableContainer: {
    maxHeight: 'calc(100vh - 280px)', // Default height
    overflow: 'auto',
  },
});

const appLogger = new Logger('Meter panel');

const App: React.FC = () => {
  const classes = useStyles();
  const [logs, setLogs] = useState<SessionLogEvent[]>([]);
  const [userSessions, setUserSessions] = useState<UserSession[]>([]);
  const [chartSessions, setChartSessions] = useState<ChartSession[]>([]);
  const [dailyUsages, setDailyUsages] = useState<DailyUsage[]>([]);
  const [view, setView] = useState<'session_log' | 'active_sessions' | 'daily_usage'>('session_log');
  const [userSessionTimeout, setUserSessionTimeout] = useState<number>(180); // Default to 3 minutes
  const [candidateUserSessionTimeout, setCandidateUserSessionTimeout] = useState<number>(180); // Local state for new timeout
  const [chartSessionTimeout, setChartSessionTimeout] = useState<number>(180); // Default to 3 minutes
  const [candidateChartSessionTimeout, setCandidateChartSessionTimeout] = useState<number>(180); // Local state for new timeout
  const [sessionLogfilters, setSessionLogFilters] = useState({
    username: '',
    fromDate: '',
    toDate: '',
    eventType: '',
  });
  const [dailyUsagefilters, setDailyUsageFilters] = useState({
    username: '',
    fromDate: '',
    toDate: '',
  });

  const [settingsOpen, setSettingsOpen] = useState(false);

  // Fetch logs and active sessions
  const fetchLogs = async () => {
    try {
      const response = await new Promise<SessionsLogsGetResponse>((resolve, reject) => {
        chrome.runtime.sendMessage({ type: 'session_logs_get' }, (response: SessionsLogsGetResponse) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            resolve(response);
          }
        });
      });
  
      if (response.success) {
        setLogs(response.sessionLogs);
      } else {
        appLogger.error('Failed to fetch session logs:', response.error);
      }
    } catch (error) {
      appLogger.error('Error fetching session logs:', error);
    }
  };


  const fetchUserSessions = async () => {
    try {
      const response = await new Promise<SessionsGetResponse>((resolve, reject) => {
        appLogger.debug('Sending user_sessions_get message');
        chrome.runtime.sendMessage({ type: 'user_sessions_get' }, (response: SessionsGetResponse) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            appLogger.debug('Received user_sessions_response:', response);
            resolve(response);
          }
        });
      });
      if (response.success) {
        const sessions: UserSession[] = response.sessions.map((sessionDTO: UserSessionDTO) => 
          UserSession.deserialize(sessionDTO)
        );
        setUserSessions(sessions);
      } else {
        appLogger.error('Failed to fetch user sessions:', response.error);
      }  
    } catch (error) {
      appLogger.error('Error fetching user sessions:', error);
    }
  };

  const fetchChartSessions = async () => {
    try {
      const response = await new Promise<SessionsGetResponse>((resolve, reject) => {
        appLogger.debug('Sending chart_sessions_get message');
        chrome.runtime.sendMessage({ type: 'chart_sessions_get' }, (response: SessionsGetResponse) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            appLogger.debug('Received chart_sessions_response:', response);
            resolve(response);
          }
        });
      });
      if (response.success) {
        const sessions: ChartSession[] = response.sessions.map((sessionDTO: ChartSessionDTO) => 
          ChartSession.deserialize(sessionDTO)
        );
        setChartSessions(sessions);
      } else {
        appLogger.error('Failed to fetch chart sessions:', response.error);
      }  
    } catch (error) {
      appLogger.error('Error fetching chart sessions:', error);
    }
  };

  // Function to get session timeout
  const fetchUserSessionTimeout = async () => {
    try {
      const response = await new Promise<SessionTimeoutGetResponse>((resolve, reject) => {
        chrome.runtime.sendMessage({ type: 'user_session_timeout_get' }, (response: SessionTimeoutGetResponse) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            resolve(response);
          }
        });
      });

      if (response.success) {
        if (response.timeout) {
          setUserSessionTimeout(response.timeout);
          setCandidateUserSessionTimeout(response.timeout); // Initialize local state
        }
        else {
          appLogger.error('Failed to fetch user session timeout. Got null response: ', response.error);
        }
      } else {
        appLogger.error('Failed to fetch user session timeout:', response.error);
      }
    } catch (error) {
      appLogger.error('Error fetching user session timeout:', error);
    }
  };

  const fetchChartSessionTimeout = async () => {
    try {
      const response = await new Promise<SessionTimeoutGetResponse>((resolve, reject) => {
        chrome.runtime.sendMessage({ type: 'chart_session_timeout_get' }, (response: SessionTimeoutGetResponse) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            resolve(response);
          }
        });
      });

      if (response.success) {
        if (response.timeout) {
          setChartSessionTimeout(response.timeout);
          setCandidateChartSessionTimeout(response.timeout); // Initialize local state
        }
        else {
          appLogger.error('Failed to fetch chart session timeout. Got null response: ', response.error);
        }
      } else {
        appLogger.error('Failed to fetch chart session timeout:', response.error);
      }
    } catch (error) {
      appLogger.error('Error fetching chart session timeout:', error);
    }
  };

  // Function to set session timeout
  const updateUserSessionTimeout = async (timeout: number) => {
    try {
      const response = await new Promise<SessionTimeoutSetResponse>((resolve, reject) => {
        chrome.runtime.sendMessage({ type: 'user_session_timeout_set', timeout }, (response: SessionTimeoutSetResponse) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            resolve(response);
          }
        });
      });

      if (response.success) {
        setUserSessionTimeout(timeout);
      } else {
        appLogger.error('Failed to set session timeout:', response.error);
      }
    } catch (error) {
      appLogger.error('Error setting session timeout:', error);
    }
  };

  const updateChartSessionTimeout = async (timeout: number) => {
    try {
      const response = await new Promise<SessionTimeoutSetResponse>((resolve, reject) => {
        chrome.runtime.sendMessage({ type: 'chart_session_timeout_set', timeout }, (response: SessionTimeoutSetResponse) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            resolve(response);
          }
        });
      });

      if (response.success) {
        setChartSessionTimeout(timeout);
      } else {
        appLogger.error('Failed to set chart session timeout:', response.error);
      }
    } catch (error) {
      appLogger.error('Error setting chart session timeout:', error);
    }
  };

  const fetchDailyUsages = async () => {
    try {
      const response = await new Promise<DailyUsageGetResponse>((resolve, reject) => {
        appLogger.debug('Sendin daily_usage_get message');
        chrome.runtime.sendMessage({ type: 'daily_usage_get' }, (response: DailyUsageGetResponse) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            appLogger.debug('Received daily_usage_get_responset:', response);
            resolve(response);
          }
        });
      });
      if (response.success) {
        const dailyUsages: DailyUsage[] = response.dailyUsages.map((dto: DailyUsageDTO) => 
          DailyUsage.deserialize(dto)
        );
        setDailyUsages(dailyUsages);
      } else {
        appLogger.error('Failed to fetch daily usages:', response.error);
      }  
    } catch (error) {
      appLogger.error('Error fetching daily usages:', error);
    }
  };


  // Fetch data on mount
  useEffect(() => {
    fetchLogs();
    fetchUserSessions();
    fetchChartSessions();
    fetchUserSessionTimeout();
    fetchChartSessionTimeout();
    fetchDailyUsages();
  
    const interval = setInterval(() => {
      fetchLogs();
      fetchUserSessions();
      fetchChartSessions();
      fetchDailyUsages();
    }, 3000);

    return () => clearInterval(interval); // Cleanup interval on component unmount
  }, []);

   // Handle settings dialog open/close
   const handleSettingsOpen = () => {
    setSettingsOpen(true);
  };

  const handleSettingsClose = () => {
    setSettingsOpen(false);
    updateUserSessionTimeout(candidateUserSessionTimeout); // Update session timeout when dialog is closed
    updateChartSessionTimeout(candidateChartSessionTimeout);
  };

  // Handle session timeout change
  const handleUserSessionTimeoutChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newTimeout = parseInt(event.target.value, 10);
    if (!isNaN(newTimeout)) {
      setCandidateUserSessionTimeout(newTimeout); // Update the state immediately
    } else {
      setCandidateUserSessionTimeout(0); // Optionally handle invalid input gracefully
    }
  };

  const handleChartSessionTimeoutChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newTimeout = parseInt(event.target.value, 10);
    if (!isNaN(newTimeout)) {
      setCandidateChartSessionTimeout(newTimeout); // Update the state immediately
    } else {
      setCandidateChartSessionTimeout(0); // Optionally handle invalid input gracefully
    }
  };


  // Filter logs
  const filteredLogs = logs.filter(log => {
    const { username, fromDate: dateFrom, toDate: dateTo, eventType } = sessionLogfilters;
    const matchesUsername = !username || log.username?.includes(username);
    const matchesEventType = !eventType || log.event === eventType;
    const matchesDateFrom = !dateFrom || new Date(log.eventTime) >= new Date(dateFrom);
    const matchesDateTo = !dateTo || new Date(log.eventTime) <= new Date(dateTo);
    return matchesUsername && matchesEventType && matchesDateFrom && matchesDateTo;
  });

  const filteredDaily = dailyUsages.filter(usage => {
    const { username, fromDate: dateFrom, toDate: dateTo} = dailyUsagefilters;
    const matchesUsername = !username || usage.getUsername()?.includes(username);
    const matchesDateFrom = !dateFrom || new Date(usage.getDate()) >= new Date(dateFrom);
    const matchesDateTo = !dateTo || new Date(usage.getDate()) <= new Date(dateTo);
    return matchesUsername && matchesDateFrom && matchesDateTo;
  });

  // Clear logs
  const handleClearLogs = async () => {
    try {
      const response = await new Promise<SessionsLogsClearResponse>((resolve, reject) => {
        chrome.runtime.sendMessage({ type: 'session_logs_clear' }, (response: SessionsLogsClearResponse) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            resolve(response);
          }
        });
      });
  
      if (response.success) {
        setLogs([]);
      } else {
        appLogger.error('Failed to clear session logs:', response.error);
      }
    } catch (error) {
      appLogger.error('Error clearing session logs:', error);
    }
  };

  // Clear daily usages
  const handleClearDailyUsage = async () => {
    try {
      const response = await new Promise<DailyUsageClearResponse>((resolve, reject) => {
        chrome.runtime.sendMessage({ type: 'daily_usage_clear' }, (response: DailyUsageClearResponse) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            resolve(response);
          }
        });
      });
  
      if (response.success) {
        setDailyUsages([]);
      } else {
        appLogger.error('Failed to clear daily usages:', response.error);
      }
    } catch (error) {
      appLogger.error('Error clearing daily usages:', error);
    }
  };

  interface Sortable {
    getDate: () => string;
    getStartTime: () => Date;
  }

  const sortByStartTime = (a: Sortable, b: Sortable): number => {
    const startTimeA = a.getStartTime() || new Date(0); // Use epoch time for empty start times
    const startTimeB = b.getStartTime() || new Date(0); // Use epoch time for empty start times
    if (startTimeA < startTimeB) return -1;
    if (startTimeA > startTimeB) return 1;
    return 0;  
  };

  const formatDuration = (seconds: number): string => {
    seconds = Math.floor(seconds); // Round down to the nearest integer
    const days = Math.floor(seconds / (24 * 3600));
    seconds %= 24 * 3600;
    const hours = Math.floor(seconds / 3600);
    seconds %= 3600;
    const minutes = Math.floor(seconds / 60);
    seconds %= 60;
  
    const daysStr = days > 0 ? `${days}d ` : '';
    const hoursStr = hours > 0 ? `${hours.toString().padStart(2, '0')}:` : '00:';
    const minutesStr = minutes > 0 ? `${minutes.toString().padStart(2, '0')}:` : '00:';
    const secondsStr = seconds > 0 ? `${seconds.toString().padStart(2, '0')}` : '00';
  
    return `${daysStr}${hoursStr}${minutesStr}${secondsStr}`;
  };

  return (
    <Box>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            EHR Usage Meter
          </Typography>
          {/* Dropdown for View Selection */}
          <Select
            value={view}
            onChange={e => setView(e.target.value as 'session_log' | 'active_sessions')}
            sx={{ color: 'white', backgroundColor: 'transparent', border: 'none' }}
          >
            <MenuItem value="session_log">Session Log</MenuItem>
            <MenuItem value="active_sessions">Active Sessions</MenuItem>
            <MenuItem value="daily_usage">Daily Usage</MenuItem>
          </Select>
          <IconButton color="inherit" onClick={handleSettingsOpen}>
            <SettingsIcon />
          </IconButton>
        </Toolbar>
      </AppBar>

      {/* Settings Dialog */}
      <Dialog open={settingsOpen} onClose={handleSettingsClose}>
        <DialogTitle>Settings</DialogTitle>
        <DialogContent>
          <DialogContentText>
            Set the session timeout (in seconds):
          </DialogContentText>
          <TextField
            autoFocus
            margin="dense"
            label="User Session Timeout"
            type="number"
            fullWidth
            value={candidateUserSessionTimeout || ''}
            onChange={handleUserSessionTimeoutChange}
          />
          <TextField
            autoFocus
            margin="dense"
            label="Chart Session Timeout"
            type="number"
            fullWidth
            value={candidateChartSessionTimeout || ''}
            onChange={handleChartSessionTimeoutChange}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleSettingsClose} color="primary">
            Close
          </Button>
        </DialogActions>
      </Dialog>

      {/* Main Content */}
      <Box p={3}>
        {view === 'session_log' && (
          <Box>
            <Typography variant="h6" gutterBottom>
              Session Log
            </Typography>
            {/* Filters */}
            <Box display="flex" gap={0.5} flexWrap="wrap" mb={2}>
              <TextField
                label="From"
                type="date"
                InputLabelProps={{ shrink: true }}
                value={sessionLogfilters.fromDate}
                onChange={e => setSessionLogFilters({ ...sessionLogfilters, fromDate: e.target.value })}
                size="small"
                sx={{ minWidth: 100 }}
              />
              <TextField
                label="To"
                type="date"
                InputLabelProps={{ shrink: true }}
                value={sessionLogfilters.toDate}
                onChange={e => setSessionLogFilters({ ...sessionLogfilters, toDate: e.target.value })}
                size="small"
                sx={{ minWidth: 100 }}
              />
              <TextField
                label="Username"
                value={sessionLogfilters.username}
                onChange={e => setSessionLogFilters({ ...sessionLogfilters, username: e.target.value })}
                size="small"
                sx={{ minWidth: 100 }}
              />
              <Select
                value={sessionLogfilters.eventType}
                onChange={e => setSessionLogFilters({ ...sessionLogfilters, eventType: e.target.value })}
                displayEmpty
                size="small"
                sx={{ minWidth: 100 }}
              >
                <MenuItem value="">All Events</MenuItem>
                <MenuItem value="session_started">Session Started</MenuItem>
                <MenuItem value="session_ended">Session Ended</MenuItem>
                <MenuItem value="session_ongoing">Session Ongoing</MenuItem>
              </Select>
              <Button
                variant="contained"
                color="secondary"
                onClick={handleClearLogs}
                size="small"
                sx={{ padding: '4px 8px', minWidth: '80px' }}
              >
                Clear Logs
              </Button>
            </Box>

            {/* Session Log Table */}
            <TableContainer component={Paper} className={classes.tableContainer}>
              <Table stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ backgroundColor: '#f5f5f5'  }}>Timestamp</TableCell>
                    <TableCell sx={{ backgroundColor: '#f5f5f5'  }}>Event</TableCell>
                    <TableCell sx={{ backgroundColor: '#f5f5f5'  }}>Username</TableCell>
                    <TableCell sx={{ backgroundColor: '#f5f5f5'  }}>Duration</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredLogs.map((log, index) => (
                    <TableRow key={index}>
                      <TableCell>{new Date(log.eventTime).toLocaleString()}</TableCell>
                      <TableCell>{log.event}</TableCell>
                      <TableCell>{log.username}</TableCell>
                      <TableCell>{log.duration ? formatDuration((log.duration / 1000)) : ''}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}

        {view === 'active_sessions' && (
          <Box>
            <Box>
              <Typography variant="h6" gutterBottom>
                User Sessions
              </Typography>
              {/* Active Sessions Table */}
              <TableContainer component={Paper} className={classes.tableContainer}>
                <Table stickyHeader sx={{ fontSize: '0.875rem' }}>
                  <TableHead>
                    <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                      <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5'  }}>Start Time</TableCell>
                      <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5'  }}>Username</TableCell>
                      <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5'  }}>Last Activity Time</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {userSessions.map((session, index) => (
                      <TableRow key={index}>
                        <TableCell sx={{ fontSize: '0.875rem' }}>{session.getStartTime().toLocaleString()}</TableCell>
                        <TableCell sx={{ fontSize: '0.875rem' }}>{session.getUsername()}</TableCell>
                        <TableCell sx={{ fontSize: '0.875rem' }}>
                          {session.getLastActivityTime()?.toLocaleString() || 'N/A'}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>

            <Box mt={4}>
              <Typography variant="h6" gutterBottom>
                Chart Sessions
              </Typography>
              <TableContainer component={Paper} className={classes.tableContainer}>
                <Table stickyHeader sx={{ fontSize: '0.875rem' }}>
                  <TableHead>
                    <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                      <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5'   }}>Start Time</TableCell>
                      <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5'   }}>Username</TableCell>
                      <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5'   }}>Chart Type</TableCell>
                      <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5'   }}>Chart Name</TableCell>
                      <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5'   }}>Last Activity Time</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {chartSessions.map((session, index) => (
                      <TableRow key={index}>
                        <TableCell sx={{ fontSize: '0.875rem' }}>{session.getStartTime().toLocaleString()}</TableCell>
                        <TableCell sx={{ fontSize: '0.875rem' }}>{session.getUsername()}</TableCell>
                        <TableCell sx={{ fontSize: '0.875rem' }}>{session.getChartType()}</TableCell>
                        <TableCell sx={{ fontSize: '0.875rem' }}>{session.getChartName()}</TableCell>
                        <TableCell sx={{ fontSize: '0.875rem' }}>{session.getLastActivityTime()?.toLocaleString() || 'N/A'}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>            
          </Box>
        )}

        {view === 'daily_usage' && (
          <Box>
            {/* Filters */}
            <Box mb={2}>
              <TextField
                label="From Date"
                type="date"
                value={dailyUsagefilters.fromDate}
                onChange={e => setDailyUsageFilters({ ...dailyUsagefilters, fromDate: e.target.value })}
                size="small"
                sx={{ marginRight: 2 }}
                InputLabelProps={{ shrink: true }}
              />
              <TextField
                label="To Date"
                type="date"
                value={dailyUsagefilters.toDate}
                onChange={e => setDailyUsageFilters({ ...dailyUsagefilters, toDate: e.target.value })}
                size="small"
                sx={{ marginRight: 2 }}
                InputLabelProps={{ shrink: true }}
              />
              <TextField
                label="Username"
                value={dailyUsagefilters.username}
                onChange={e => setDailyUsageFilters({ ...dailyUsagefilters, username: e.target.value })}
                size="small"
                sx={{ marginRight: 2 }}
              />
              <Button
                variant="contained"
                color="secondary"
                onClick={handleClearDailyUsage}
                size="small"
                sx={{ padding: '4px 8px', minWidth: '80px' }}
              >
                Clear Daily Report
              </Button>
            </Box>

            {/* User Daily Usage Table */}
            <Typography variant="h6" gutterBottom>
              User Daily Usage
            </Typography>
            <TableContainer component={Paper} className={classes.tableContainer}>
              <Table stickyHeader sx={{ fontSize: '0.875rem' }}>
                <TableHead>
                  <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                    <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5' }}>Date</TableCell>
                    <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5' }}>Username</TableCell>
                    <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5' }}>Start Time</TableCell>
                    <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5' }}>Duration</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredDaily
                    .filter(usage => usage.getType() === 'UserSession')
                    .sort(sortByStartTime)
                    .map((usage, index) => (
                      <TableRow key={index}>
                        <TableCell sx={{ fontSize: '0.875rem' }}>{usage.getDate()}</TableCell>
                        <TableCell sx={{ fontSize: '0.875rem' }}>{ActiveSession.getUsername(usage.getFields().userId, usage.getFields().orgId)}</TableCell>
                        <TableCell sx={{ fontSize: '0.875rem' }}>{usage.getStartTime().toLocaleTimeString()}</TableCell>
                        <TableCell sx={{ fontSize: '0.875rem' }}>{formatDuration(usage.getDuration())}</TableCell>
                      </TableRow>
                    ))}
                </TableBody>
              </Table>
            </TableContainer>

            {/* Chart Daily Usage Table */}
            <Box mt={4}>
              <Typography variant="h6" gutterBottom>
                Chart Daily Usage
              </Typography>
              <TableContainer component={Paper} className={classes.tableContainer}>
                <Table stickyHeader sx={{ fontSize: '0.875rem' }}>
                  <TableHead>
                    <TableRow sx={{ backgroundColor: '#f5f5f5' }}>
                      <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5' }}>Date</TableCell>
                      <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5' }}>Username</TableCell>
                      <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5' }}>Chart Type</TableCell>
                      <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5' }}>Chart Name</TableCell>
                      <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5' }}>Start Time</TableCell>
                      <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5' }}>Duration</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {filteredDaily
                      .filter(usage => usage.getType() === 'ChartSession')
                      .sort(sortByStartTime)
                      .map((usage, index) => (
                        <TableRow key={index}>
                          <TableCell sx={{ fontSize: '0.875rem' }}>{usage.getDate()}</TableCell>
                          <TableCell sx={{ fontSize: '0.875rem' }}>{ActiveSession.getUsername(usage.getFields().userId, usage.getFields().orgId)}</TableCell>
                          <TableCell sx={{ fontSize: '0.875rem' }}>{usage.getFields().chartType}</TableCell>
                          <TableCell sx={{ fontSize: '0.875rem' }}>{usage.getFields().chartName}</TableCell>
                          <TableCell sx={{ fontSize: '0.875rem' }}>{usage.getStartTime().toLocaleTimeString()}</TableCell>
                          <TableCell sx={{ fontSize: '0.875rem' }}>{formatDuration(usage.getDuration())}</TableCell>
                        </TableRow>
                      ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </Box>
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default App;
