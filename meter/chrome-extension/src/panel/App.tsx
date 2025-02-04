import React, { useState, useEffect } from 'react';
import { UserSession, UserSessionDTO } from '../background/sessions';
import { SessionsResponse,  SessionTimeoutGetResponse, SessionTimeoutSetResponse } from '../types/messages'  
import {  SessionLogEvent,  SessionsLogsGetResponse, SessionsLogsClearResponse, } from '../background/session_log';
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

const useStyles = makeStyles({
  tableContainer: {
    maxHeight: 'calc(100vh - 280px)', // Default height
    overflow: 'auto',
  },
});

const appLogger = new Logger('Meter');

const App: React.FC = () => {
  const classes = useStyles();
  const [logs, setLogs] = useState<SessionLogEvent[]>([]);
  const [userSessions, setUserSessions] = useState<UserSession[]>([]);
  const [view, setView] = useState<'session_log' | 'active_sessions'>('session_log');
  const [sessionTimeout, setSessionTimeout] = useState<number>(180); // Default to 3 minutes
  const [candidateSessionTimeout, setCandidateSessionTimeout] = useState<number>(180); // Local state for new timeout
  const [filters, setFilters] = useState({
    username: '',
    orgId: '',
    dateFrom: '',
    dateTo: '',
    eventType: '',
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
      const response = await new Promise<SessionsResponse>((resolve, reject) => {
        appLogger.debug('Sending user_sessions_get message');
        chrome.runtime.sendMessage({ type: 'sessions_get' }, (response: SessionsResponse) => {
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

  // Function to get session timeout
  const fetchSessionTimeout = async () => {
    try {
      const response = await new Promise<SessionTimeoutGetResponse>((resolve, reject) => {
        chrome.runtime.sendMessage({ type: 'session_timeout_get' }, (response: SessionTimeoutGetResponse) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            resolve(response);
          }
        });
      });

      if (response.success) {
        if (response.timeout) {
          setSessionTimeout(response.timeout);
          setCandidateSessionTimeout(response.timeout); // Initialize local state
        }
        else {
          appLogger.error('Failed to fetch session timeout. Got null response: ', response.error);
        }
      } else {
        appLogger.error('Failed to fetch session timeout:', response.error);
      }
    } catch (error) {
      appLogger.error('Error fetching session timeout:', error);
    }
  };

  // Function to set session timeout
  const updateSessionTimeout = async (timeout: number) => {
    try {
      const response = await new Promise<SessionTimeoutSetResponse>((resolve, reject) => {
        chrome.runtime.sendMessage({ type: 'session_timeout_set', timeout }, (response: SessionTimeoutSetResponse) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            resolve(response);
          }
        });
      });

      if (response.success) {
        setSessionTimeout(timeout);
      } else {
        appLogger.error('Failed to set session timeout:', response.error);
      }
    } catch (error) {
      appLogger.error('Error setting session timeout:', error);
    }
  };


  // Fetch data on mount
  useEffect(() => {
    fetchLogs();
    fetchUserSessions();
    fetchSessionTimeout();

    const interval = setInterval(() => {
      fetchLogs();
      fetchUserSessions();
    }, 3000);

    return () => clearInterval(interval); // Cleanup interval on component unmount
  }, []);

   // Handle settings dialog open/close
   const handleSettingsOpen = () => {
    setSettingsOpen(true);
  };

  const handleSettingsClose = () => {
    setSettingsOpen(false);
    updateSessionTimeout(candidateSessionTimeout); // Update session timeout when dialog is closed
  };

  // Handle session timeout change
  const handleSessionTimeoutChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newTimeout = parseInt(event.target.value, 10);
    if (!isNaN(newTimeout)) {
      setCandidateSessionTimeout(newTimeout); // Update the state immediately
    } else {
      setCandidateSessionTimeout(0); // Optionally handle invalid input gracefully
    }
  };

  // Filter logs
  const filteredLogs = logs.filter(log => {
    const { username, orgId, dateFrom, dateTo, eventType } = filters;
    const matchesUsername = !username || log.username?.includes(username);
    const matchesOrgId = !orgId || log.username?.includes(orgId);
    const matchesEventType = !eventType || log.event === eventType;
    const matchesDateFrom = !dateFrom || new Date(log.eventTime) >= new Date(dateFrom);
    const matchesDateTo = !dateTo || new Date(log.eventTime) <= new Date(dateTo);
    return matchesUsername && matchesOrgId && matchesEventType && matchesDateFrom && matchesDateTo;
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


  return (
    <Box>
      <AppBar position="static">
        <Toolbar>
          <Typography variant="h6" sx={{ flexGrow: 1 }}>
            Session Tracker
          </Typography>
          {/* Dropdown for View Selection */}
          <Select
            value={view}
            onChange={e => setView(e.target.value as 'session_log' | 'active_sessions')}
            sx={{ color: 'white', backgroundColor: 'transparent', border: 'none' }}
          >
            <MenuItem value="session_log">Session Log</MenuItem>
            <MenuItem value="active_sessions">Active Sessions</MenuItem>
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
            label="Session Timeout"
            type="number"
            fullWidth
            value={candidateSessionTimeout || ''}
            onChange={handleSessionTimeoutChange}
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
            <Typography variant="h5" gutterBottom>
              Session Log
            </Typography>
            {/* Filters */}
            <Box display="flex" gap={0.5} flexWrap="wrap" mb={2}>
              <TextField
                label="From"
                type="date"
                InputLabelProps={{ shrink: true }}
                value={filters.dateFrom}
                onChange={e => setFilters({ ...filters, dateFrom: e.target.value })}
                size="small"
                sx={{ minWidth: 100 }}
              />
              <TextField
                label="To"
                type="date"
                InputLabelProps={{ shrink: true }}
                value={filters.dateTo}
                onChange={e => setFilters({ ...filters, dateTo: e.target.value })}
                size="small"
                sx={{ minWidth: 100 }}
              />
              <TextField
                label="Username"
                value={filters.username}
                onChange={e => setFilters({ ...filters, username: e.target.value })}
                size="small"
                sx={{ minWidth: 100 }}
              />
              <TextField
                label="Org ID"
                value={filters.orgId}
                onChange={e => setFilters({ ...filters, orgId: e.target.value })}
                size="small"
                sx={{ minWidth: 100 }}
              />
              <Select
                value={filters.eventType}
                onChange={e => setFilters({ ...filters, eventType: e.target.value })}
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
                    <TableCell>Timestamp</TableCell>
                    <TableCell>Event</TableCell>
                    <TableCell>Username</TableCell>
                    <TableCell>Duration (seconds)</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredLogs.map((log, index) => (
                    <TableRow key={index}>
                      <TableCell>{new Date(log.eventTime).toLocaleString()}</TableCell>
                      <TableCell>{log.event}</TableCell>
                      <TableCell>{log.username}</TableCell>
                      <TableCell>{log.duration ? `${(log.duration / 1000).toFixed(0)}` : ''}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}

        {view === 'active_sessions' && (
          <Box>
            <Typography variant="h5" gutterBottom>
              Active Sessions
            </Typography>
            {/* Active Sessions Table */}
            {/* <TableContainer component={Paper} sx={{ maxHeight: 800, overflow: 'auto' }}> */}
            <TableContainer component={Paper} className={classes.tableContainer}>
              <Table stickyHeader>
                <TableHead>
                  <TableRow>
                    <TableCell>Start Time</TableCell>
                    <TableCell>Username</TableCell>
                    <TableCell>Last Activity Time</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {userSessions.map((session, index) => (
                    <TableRow key={index}>
                      <TableCell>{session.getStartTime().toLocaleString()}</TableCell>
                      <TableCell>{`${session.getUserId()}@${session.getOrgId()}`}</TableCell>
                      <TableCell>
                        {session.getLastActivityTime()?.toLocaleString() || 'N/A'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </Box>
        )}
      </Box>
    </Box>
  );
};

export default App;
