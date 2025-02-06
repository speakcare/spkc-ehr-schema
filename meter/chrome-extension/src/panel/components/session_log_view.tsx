import React from 'react';
import { Box, Typography, TextField, Select, MenuItem, Button, TableContainer, Paper, Table, TableHead, TableRow, TableCell, TableBody } from '@mui/material';
import { formatDuration } from '../../utils/time_utils';

interface SessionLogFilters {
  fromDate: string;
  toDate: string;
  username: string;
  eventType: string;
}

interface SessionLogViewProps {
  sessionLogfilters: SessionLogFilters;
  setSessionLogFilters: (filters: SessionLogFilters) => void;
  filteredLogs: Array<{ eventTime: string; event: string; username: string; duration?: number }>;
  handleClearLogs: () => void;
}

const SessionLogView: React.FC<SessionLogViewProps> = ({ sessionLogfilters, setSessionLogFilters, filteredLogs, handleClearLogs }) => {
  return (
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
      <TableContainer component={Paper}>
        <Table stickyHeader>
          <TableHead>
            <TableRow>
              <TableCell sx={{ backgroundColor: '#f5f5f5' }}>Timestamp</TableCell>
              <TableCell sx={{ backgroundColor: '#f5f5f5' }}>Event</TableCell>
              <TableCell sx={{ backgroundColor: '#f5f5f5' }}>Username</TableCell>
              <TableCell sx={{ backgroundColor: '#f5f5f5' }}>Duration</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredLogs.map((log, index) => (
              <TableRow key={index}>
                <TableCell>{new Date(log.eventTime).toLocaleString()}</TableCell>
                <TableCell>{log.event}</TableCell>
                <TableCell>{log.username}</TableCell>
                <TableCell>{log.duration ? formatDuration(log.duration / 1000) : ''}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default SessionLogView;