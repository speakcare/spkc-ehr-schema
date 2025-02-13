import React, { useState, useEffect } from 'react';
import { ChartSession, UserSession, UserSessionDTO, ChartSessionDTO } from '../background/sessions';
import { SessionsGetResponse,  SessionTimeoutGetResponse, SessionTimeoutSetResponse } from '../background/session_messages'  
import { SessionLogEvent,  SessionsLogsGetResponse, SessionsLogsClearResponse, } from '../background/session_log';
import { DailyUsage, DailyUsageGetResponse, DailyUsageClearResponse, DailyUsageDTO } from '../background/daily_usage';
import { AppBar, Toolbar, Typography, Button, Box, Table, TableBody, TableCell, 
         TableContainer, TableHead, TableRow, TextField, Select, MenuItem,
         Paper, Dialog, DialogActions, DialogContent, DialogContentText, 
         DialogTitle, IconButton } from '@mui/material';
import SettingsIcon from '@mui/icons-material/Settings';
import GoogleSheetsIcon from '@mui/icons-material/Google';
import ExportIcon from '@mui/icons-material/SaveAlt';
import { makeStyles } from '@mui/styles';
import { Logger } from '../utils/logger';
import { LocalStorage } from '../utils/local_storage';

import SessionLogView from './components/session_log_view';
import ActiveSessionsView  from './components/active_sessions_view';
import DailyUsageView from './components/daily_usage_view';
import SettingsDialog from './components/settings_dialog';
import GoogleSheetsExport from './components/google_sheets_export';

const OAuthClientId = '289656832978-c3bu3104fjasceu6utpihs065tdig833';
const defaultSpreadsheetId = '1KHjVFQ-sQmyfI3GM4W5jdmu0k4tAXeQ2EpIcLMMLlY4'

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
  const [candidateUserSessionTimeout, setCandidateUserSessionTimeout] = useState<number>(180); // Local state for new timeout
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
  const [exportDialogOpen, setExportDialogOpen] = useState(false);
  const [spreadsheetId, setSpreadsheetId] = useState<string>('');
  const localStorage = new LocalStorage('MeterPanel');

  useEffect(() => {
    const fetchSpreadsheetId = async () => {
      const items = await localStorage.getItems(['spreadsheetId']);
      if (items.spreadsheetId) {
        appLogger.info('Spreadsheet ID found in local storage:', items.spreadsheetId.slice(-5));
        setSpreadsheetId(items.spreadsheetId);
      }
      else {
        setSpreadsheetId(defaultSpreadsheetId);
      }
    };
    fetchSpreadsheetId();
  }, []);

  const handleSpreadsheetIdChange = async (newSpreadsheetId: string) => {
    setSpreadsheetId(newSpreadsheetId);
    await localStorage.setItems( {spreadsheetId: newSpreadsheetId} );
  };

  useEffect(() => {
    if (spreadsheetId) {
      appLogger.info('Spreadsheet ID updated:', spreadsheetId.slice(-5));
    }
  }, [spreadsheetId]);
  

  const prepareExportData = () => {
    const now = new Date().toISOString(); // Current time in GMT ISO representation

    const sessionLogSheetName = `Session log ${now}`;
    const dailyUsageSheetName = `Daily usage ${now}`;
    const chartUsageSheetName = `Chart usage ${now}`;

    const sessionLogData = [
      ['Timestamp', 'Event', 'Username', 'Duration (seconds)'], // Column names
      ...logs.map(log => [
        log.eventTime,
        log.event,
        log.username,
        Math.floor(log.duration/1000),
        // Add other fields as needed
      ])
    ];

    const dailyUsageData = [
      ['Date', 'Username', 'Start Time', 'Duration (seconds)'], // Column names
      ...dailyUsages
        .filter(usage => usage.getType() === 'UserSession')
        .map(usage => [
          usage.getDate(),
          usage.getUsername(),
          usage.getStartTime().toISOString(),
          Math.floor(usage.getDuration()),
        ])
    ];

    const chartUsageData = [
      ['Date', 'Username', 'Chart Type', 'Chart Name', 'Start Time', 'Duration (seconds)'], // Column names
      ...dailyUsages
        .filter(usage => usage.getType() === 'ChartSession')
        .map(usage => [
          usage.getDate(),
          usage.getUsername(),
          usage.getFields().chartType,
          usage.getFields().chartName,
          usage.getStartTime().toISOString(),
          Math.floor(usage.getDuration()),
        ])
    ];

    return [
      { sheetName: sessionLogSheetName, data: sessionLogData },
      { sheetName: dailyUsageSheetName, data: dailyUsageData },
      { sheetName: chartUsageSheetName, data: chartUsageData },
    ];
  };

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
        appLogger.info('User session timeout set successfully:', timeout);
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
        appLogger.info('Chart session timeout set successfully:', timeout);
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

  // Filter daily usages
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
          <IconButton color="inherit" onClick={() => setExportDialogOpen(true)}>
            <ExportIcon />
          </IconButton>
          <IconButton color="inherit" onClick={handleSettingsOpen}>
            <SettingsIcon />
          </IconButton>
        </Toolbar>
      </AppBar>

      {/* Settings Dialog */}
      <SettingsDialog
        open={settingsOpen}
        onClose={handleSettingsClose}
        userSessionTimeout={candidateUserSessionTimeout}
        chartSessionTimeout={candidateChartSessionTimeout}
        onUserSessionTimeoutChange={handleUserSessionTimeoutChange}
        onChartSessionTimeoutChange={handleChartSessionTimeoutChange}
      />
       {/* Google Sheets Export Dialog */}
       <GoogleSheetsExport
        open={exportDialogOpen}
        onClose={() => setExportDialogOpen(false)}
        OAuthClientId={OAuthClientId}
        sheetsData={prepareExportData()}
        spreadsheetId={spreadsheetId}
        onSpreadsheetIdChange={handleSpreadsheetIdChange}
      />
      {/* Main Content */}
      <Box p={3}>
        {view === 'session_log' && (
          <SessionLogView
            sessionLogfilters={sessionLogfilters}
            setSessionLogFilters={setSessionLogFilters}
            filteredLogs={filteredLogs}
            handleClearLogs={handleClearLogs}
          />
        )}
        {view === 'active_sessions' && (
          <ActiveSessionsView
            userSessions={userSessions}
            chartSessions={chartSessions}
            classes={classes}
          />
        )}
        {view === 'daily_usage' && (
          <DailyUsageView
            dailyUsagefilters={dailyUsagefilters}
            setDailyUsageFilters={setDailyUsageFilters}
            filteredDaily={filteredDaily}
            handleClearDailyUsage={handleClearDailyUsage}
            classes={classes}
          />
        )} 
      </Box>
    </Box>
  );
};

export default App;
