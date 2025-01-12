import React, { useState, useEffect } from 'react';
import { SessionLogEvent, ActiveSession, ActiveSessionsResponse, SessionsLogsGetResponse, SessionsLogsClearResponse  } from '../types';
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
  Tabs,
  Tab,
} from '@mui/material';

const App: React.FC = () => {
  const [logs, setLogs] = useState<SessionLogEvent[]>([]);
  const [activeSessions, setActiveSessions] = useState<ActiveSession[]>([]);
  const [view, setView] = useState<'session_log' | 'active_sessions'>('session_log');
  const [filters, setFilters] = useState({
    username: '',
    orgId: '',
    dateFrom: '',
    dateTo: '',
    eventType: '',
  });

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
        console.error('Failed to fetch session logs:', response.error);
      }
    } catch (error) {
      console.error('Error fetching session logs:', error);
    }
  };


  const fetchActiveSessions = async () => {
    try {
      const response = await new Promise<ActiveSessionsResponse>((resolve, reject) => {
        console.debug('Sending active_sessions_get message');
        chrome.runtime.sendMessage({ type: 'active_sessions_get' }, (response: ActiveSessionsResponse) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            console.debug('Received active_sessions_response:', response);
            resolve(response);
          }
        });
      });
      if (response.success) {
        const activeSessions = response.activeSessions.map(session => ({
          ...session,
          startTime: new Date(session.startTime),
          lastActivityTime: session.lastActivityTime ? new Date(session.lastActivityTime) : null,
        }));
        setActiveSessions(activeSessions);
      } else {
        console.error('Failed to fetch active sessions:', response.error);
      }  
    } catch (error) {
      console.error('Error fetching active sessions:', error);
    }
  };


  // Fetch data on mount
  useEffect(() => {
    fetchLogs();
    fetchActiveSessions();

    const interval = setInterval(() => {
      fetchLogs();
      fetchActiveSessions();
    }, 3000);

    return () => clearInterval(interval); // Cleanup interval on component unmount
  }, []);

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
        console.error('Failed to clear session logs:', response.error);
      }
    } catch (error) {
      console.error('Error clearing session logs:', error);
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
        </Toolbar>
      </AppBar>

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
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Timestamp</TableCell>
                    <TableCell>Event</TableCell>
                    <TableCell>Username</TableCell>
                    <TableCell>Duration</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {filteredLogs.map((log, index) => (
                    <TableRow key={index}>
                      <TableCell>{new Date(log.eventTime).toLocaleString()}</TableCell>
                      <TableCell>{log.event}</TableCell>
                      <TableCell>{log.username}</TableCell>
                      <TableCell>{log.duration ? `${(log.duration / 1000).toFixed(2)} seconds` : 'In Progress'}</TableCell>
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
            <TableContainer component={Paper}>
              <Table>
                <TableHead>
                  <TableRow>
                    <TableCell>Start Time</TableCell>
                    <TableCell>Username</TableCell>
                    <TableCell>Last Activity Time</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {activeSessions.map((session, index) => (
                    <TableRow key={index}>
                      <TableCell>{new Date(session.startTime).toLocaleString()}</TableCell>
                      <TableCell>{`${session.userId}@${session.orgId}`}</TableCell>
                      <TableCell>
                        {session.lastActivityTime
                          ? new Date(session.lastActivityTime).toLocaleString()
                          : 'N/A'}
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
