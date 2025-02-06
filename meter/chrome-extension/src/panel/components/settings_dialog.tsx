import React from 'react';
import { Dialog, DialogActions, DialogContent, DialogContentText, DialogTitle, TextField, Button } from '@mui/material';

interface SettingsDialogProps {
  open: boolean;
  onClose: () => void;
  userSessionTimeout: number;
  chartSessionTimeout: number;
  onUserSessionTimeoutChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onChartSessionTimeoutChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
}

const SettingsDialog: React.FC<SettingsDialogProps> = ({
  open,
  onClose,
  userSessionTimeout,
  chartSessionTimeout,
  onUserSessionTimeoutChange,
  onChartSessionTimeoutChange,
}) => {
  return (
    <Dialog open={open} onClose={onClose}>
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
          value={userSessionTimeout || ''}
          onChange={onUserSessionTimeoutChange}
        />
        <TextField
          autoFocus
          margin="dense"
          label="Chart Session Timeout"
          type="number"
          fullWidth
          value={chartSessionTimeout || ''}
          onChange={onChartSessionTimeoutChange}
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} color="primary">
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default SettingsDialog;