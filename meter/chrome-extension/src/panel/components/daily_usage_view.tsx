import React from 'react';
import { ActiveSession } from '../../background/sessions';
import { Box, Typography, TextField, Button, TableContainer, Paper, Table, TableHead, TableRow, TableCell, TableBody } from '@mui/material';
import { sortByTime, TimeSortable, formatDuration } from '../../utils/time_utils';

interface DailyUsageViewProps {
  dailyUsagefilters: {
    fromDate: string;
    toDate: string;
    username: string;
  };
  setDailyUsageFilters: (filters: { fromDate: string; toDate: string; username: string }) => void;
  filteredDaily: any[];
  handleClearDailyUsage: () => void;
  classes: any;
}

const DailyUsageView: React.FC<DailyUsageViewProps> = ({ dailyUsagefilters, setDailyUsageFilters, filteredDaily, handleClearDailyUsage, classes }) => {
  return (
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
              .sort(sortByTime('getStartTime'))
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
                .sort(sortByTime('getStartTime'))
                .map((usage, index) => (
                  <TableRow key={index}>
                    <TableCell sx={{ fontSize: '0.875rem' }}>{usage.getDate()}</TableCell>
                    <TableCell sx={{ fontSize: '0.875rem' }}>{usage.getUsername() /*ActiveSession.getUsername(usage.getFields().userId, usage.getFields().orgId)*/}</TableCell>
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
  );
};

export default DailyUsageView;