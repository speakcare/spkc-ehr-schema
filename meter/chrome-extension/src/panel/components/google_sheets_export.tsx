import { GoogleOAuth } from '../../auth/google_oauth';
import { GoogleSheetsAPI } from '../../apis/google_sheets';
import { Logger } from '../../utils/logger';
import React, { useState, useEffect } from 'react';
import { Dialog, DialogActions, DialogContent, DialogTitle, TextField, Button, Typography, CircularProgress } from '@mui/material';
import { LocalStorage } from '../../utils/local_storage';




export class GoogleSheetsWriter {

    private googleAuth: GoogleOAuth | null;
    private googleSheets: GoogleSheetsAPI | null;
    private logger: Logger;
    private clientId: string;
    private spreadsheetId: string;

    constructor(clientId: string, spreadsheetId: string) {
        this.logger = new Logger('Export');
        this.googleAuth = null; // new GoogleOAuth(clientId, 'https://www.googleapis.com/auth/spreadsheets','Export');
        this.spreadsheetId = spreadsheetId;
        this.clientId = clientId;
        this.googleSheets = null;
    }
    
    async init() {
        this.googleAuth = new GoogleOAuth(this.clientId, 'https://www.googleapis.com/auth/spreadsheets','Export');
        if (!this.googleAuth) {
            this.logger.error('Google Auth failed to initialized.');
            throw new Error('Google Auth failed to initialize.');
        }
        await this.googleAuth.init();
        const tokenValid = await this.googleAuth.isTokenValid();
  
        if (!tokenValid) {
            this.logger.log('Token is invalid or expired.');
            await this.googleAuth.authenticate();
            this.logger.log('Authenticated with Google OAuth. Access token:', this.googleAuth.getAccessToken());
        }
        else {
            this.logger.log('Reusing valid token:', this.googleAuth.getAccessToken());
        }
        const token = this.googleAuth.getAccessToken();
        this.googleSheets = new GoogleSheetsAPI(token, this.spreadsheetId);
    }
    
    async sheetWriter(sheetName: string, data: string[][]): Promise<void> {
        if (!this.googleSheets) {
            this.logger.error('Google Sheets API not initialized.');
            throw new Error('Google Sheets API not initialized.');
        }
        else if (!this.googleAuth) {
            this.logger.error('Google Auth not initialized.');
            throw new Error('Google Auth not initialized.');
        }
        else if (!this.googleAuth.isTokenValid()) {
            this.logger.error('Google Auth token is invalid.');
            throw new Error('Google Auth token is invalid.');
        }

        try {
            await this.googleSheets.createSheet(sheetName);
        } catch (error) {
            this.logger.error(`Error creating sheet: ${sheetName}`, error);
            throw new Error(`Error creating sheet ${sheetName}: ${String(error)}`);
        }
        try {
            await this.googleSheets.writeToSheet(sheetName, data);
        } catch (error) {
            this.logger.error(`Error writing data to sheet ${sheetName}:`, error);
            throw new Error(`Error writing data ${sheetName}: ${String(error)}`);
        }
    }
}

interface SheetData {
  sheetName: string;
  data: any[][];
}

interface GoogleSheetsExportProps {
    open: boolean;
    onClose: () => void;
    OAuthClientId: string;
    sheetsData: SheetData[];
    spreadsheetId: string;
    onSpreadsheetIdChange: (newSpreadsheetId: string) => void;  
  }
  
  const GoogleSheetsExport: React.FC<GoogleSheetsExportProps> = ({ 
    open, 
    onClose, 
    OAuthClientId, 
    sheetsData,
    spreadsheetId,
    onSpreadsheetIdChange
   }) => {
    const [candidateSpreadsheetId, setCandidateSpreadsheetId] = useState<string>('');
    const [error, setError] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [isSpreadsheetIdInvalid, setIsSpreadsheetIdInvalid] = useState<boolean>(false);
    const [isEditing, setIsEditing] = useState<boolean>(false);
    const [isExporting, setIsExporting] = useState<boolean>(false);
    const logger = new Logger('GoogleSheetsExport');
  
    useEffect(() => {
      setCandidateSpreadsheetId(spreadsheetId);
    }, [spreadsheetId]);
  
    const handleClose = async () => {
      onClose();
    };
  
    const toggleSpreadsheetIdEdit = () => {
      logger.debug('Toggle editing mode:', isEditing, 'Spreadsheet ID:', spreadsheetId.slice(-5), 'Candidate:', candidateSpreadsheetId.slice(-5));
      if (isEditing && (candidateSpreadsheetId !== spreadsheetId)) {
        logger.debug('Spreadsheet ID changed:', candidateSpreadsheetId.slice(-5));
        onSpreadsheetIdChange(candidateSpreadsheetId);
      }
      setIsEditing(!isEditing);
      setError(null);
      setSuccessMessage(null);
      setIsSpreadsheetIdInvalid(false);
    }
    
    const handleExport = async () => {
      setError(null);
      setSuccessMessage(null);
      setIsSpreadsheetIdInvalid(false);
      setIsExporting(true);
  
      if (!candidateSpreadsheetId) {
        setError('Spreadsheet ID is required.');
        setIsSpreadsheetIdInvalid(true);
        logger.error('Spreadsheet ID is required.');
        setIsExporting(false);
        return;
      }
  
      console.log('Exporting to Google Sheets with ID:', candidateSpreadsheetId);
      const gsWriter = new GoogleSheetsWriter(OAuthClientId, candidateSpreadsheetId);
  
      try {
        await gsWriter.init();
  
        for (const sheet of sheetsData) {
          try {
            await gsWriter.sheetWriter(sheet.sheetName, sheet.data);
            logger.log('Export to sheet:', sheet.sheetName, 'data:', sheet.data);
          } catch (error) {
            logger.error(`Error exporting data to sheet ${sheet.sheetName}:`, error);
            if ((error as Error).message.includes('Requested entity was not found')) {
              setError('Spreadsheet ID not found.');
              setIsSpreadsheetIdInvalid(true);
            } else {
              setError(`Error exporting data to sheet ${sheet.sheetName}: ${(error as Error).message}`);
            }
            setIsExporting(false);
            return;
          }
        }
        setSuccessMessage('Export finished successfully.');
      } catch (error) {
        logger.error('Error initializing Google Sheets Writer:', error);
        if ((error as Error).message.includes('Spreadsheet ID not found')) {
          setError('Spreadsheet ID not found.');
          setIsSpreadsheetIdInvalid(true);
        } else {
          setError(`Error initializing Google Sheets Writer: ${(error as Error).message}`);
        }
        setIsExporting(false);
        return;
      }
      setIsExporting(false);
    };
  
    return (
      <Dialog open={open} onClose={handleClose}>
        <DialogTitle>Export to Google Sheets</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Spreadsheet ID"
            type="text"
            fullWidth
            value={candidateSpreadsheetId}
            onChange={(e) => setCandidateSpreadsheetId(e.target.value)}
            error={isSpreadsheetIdInvalid}
            helperText={isSpreadsheetIdInvalid ? 'Invalid Spreadsheet ID' : ''}
            InputProps={{
              readOnly: !isEditing,
            }}
            disabled={!isEditing}
          />
          <Button onClick={() => toggleSpreadsheetIdEdit()} color="primary">
            {isEditing ? 'Save' : 'Edit'}
          </Button>
          {error && <Typography color="error">{error}</Typography>}
          {successMessage && <Typography color="primary">{successMessage}</Typography>}
          {isExporting && <CircularProgress />}
        </DialogContent>
        <DialogActions>
          <Button onClick={handleClose} color="primary">
            Close
          </Button>
          <Button onClick={handleExport} color="primary">
            Export
          </Button>
        </DialogActions>
      </Dialog>
    );
  };
  
  export default GoogleSheetsExport;