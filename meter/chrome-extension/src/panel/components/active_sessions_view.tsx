import React from 'react';
import { Box, Typography, TableContainer, Paper, Table, TableHead, TableRow, TableCell, TableBody } from '@mui/material';
import { UserSession, ChartSession } from '../../background/sessions';


interface ActiveSessionsViewProps {
  userSessions: UserSession[];
  chartSessions: ChartSession[];
  classes: {
    tableContainer: string;
  };
}

const ActiveSessionsView: React.FC<ActiveSessionsViewProps> = ({ userSessions, chartSessions, classes }) => {
  return (
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
                <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5' }}>Start Time</TableCell>
                <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5' }}>Username</TableCell>
                <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5' }}>Last Activity Time</TableCell>
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
                <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5' }}>Start Time</TableCell>
                <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5' }}>Username</TableCell>
                <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5' }}>Chart Type</TableCell>
                <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5' }}>Chart Name</TableCell>
                <TableCell sx={{ fontSize: '0.875rem', backgroundColor: '#f5f5f5' }}>Last Activity Time</TableCell>
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
  );
};

export default ActiveSessionsView;