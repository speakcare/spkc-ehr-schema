import { GoogleOAuth } from "../auth/google_oauth";
import { Logger } from '../utils/logger';



export class GoogleSheetsAPI {
    private accessToken: string;
    private spreadsheetId: string;
    private logger: Logger;
    constructor(_accessToken: string, _spreadsheetId: string) {
        this.accessToken = _accessToken;
        this.spreadsheetId = _spreadsheetId;
        this.logger = new Logger('GoogleSheets');
    }

    async writeToSheet(sheetName: string, data: string[][]): Promise<void> {
      const range = `${sheetName}!A1`;
      try {
        const response = await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${this.spreadsheetId}/values/${range}?valueInputOption=RAW`, {
          method: 'PUT',
          headers: {
            'Authorization': `Bearer ${this.accessToken}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({ values: data })
        });
    
        const responseData = await response.json();
    
        if (!response.ok) {
          throw new Error(responseData.error?.message || 'Failed to write to sheet');
        }
    
        this.logger.log('Data written successfully:', responseData);
    
      } catch (error) {
        this.logger.error(`Error writing to sheet: ${sheetName}`, error);
        throw new Error(`Error writing to sheet: ${sheetName}. ${error}`);
      }
    }
    
    async createSheet(sheetName: string): Promise<boolean> {
      try {
        const response = await fetch(`https://sheets.googleapis.com/v4/spreadsheets/${this.spreadsheetId}:batchUpdate`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${this.accessToken}`,
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            requests: [{
              addSheet: {
                properties: { title: `${sheetName}` }
              }
            }]
          })
        });
    
        const data = await response.json();
    
        if (!response.ok) {
          throw new Error(data.error?.message || 'Failed to create sheet');
        }
    
        this.logger.log(`${sheetName} created successfully.`);
        return true;
    
      } catch (error) {
        this.logger.error(`Error creating new sheet: ${sheetName}`, error);
        throw new Error(`Error creating new sheet: ${sheetName}. ${error}`);
      }
    }
    
}


export async function testGoogleSheets() {
  const googleAuth = new GoogleOAuth(
    '289656832978-c3bu3104fjasceu6utpihs065tdig833', 
    'https://www.googleapis.com/auth/spreadsheets', 
    'GoogleSheets'
  );

  const spreadsheetId = '1KHjVFQ-sQmyfI3GM4W5jdmu0k4tAXeQ2EpIcLMMLlY4';
  await googleAuth.init();
  const tokenValid = await googleAuth.isTokenValid();
  
  if (!tokenValid) {
    console.log('Token is invalid or expired.');
    await googleAuth.authenticate();
  }

  const token = googleAuth.getAccessToken();
  console.log('Token:', token);

  const googleSheets = new GoogleSheetsAPI(token, spreadsheetId);

  const data = [
    ['Name', 'Age'],
    ['Alice', '25'],
    ['Bob', '30']
  ];

  const sheetCreated = await googleSheets.createSheet('TestSheet');
  if (sheetCreated) {
    await googleSheets.writeToSheet('TestSheet', data);
  } else {
    console.error('Sheet creation failed, aborting data write.');
  }
}

