import React, { useEffect, useState, useRef } from 'react';
import { Container, FormControl, InputLabel, MenuItem, Select, Button, Typography, SelectChangeEvent, CircularProgress, Checkbox, ListItemText } from '@mui/material';
import AudioRecorder from './components/AudioRecorder'; 

import axios from 'axios';
import './App.css';
import { dispatchVisibilityChangeEvent, saveState, loadState, blobToBase64, base64ToBlob } from './utils';
import { extractAssessmentSectionFormFields, sendSaveRequest} from './pcc-utils'


const apiBaseUrl = process.env.REACT_APP_SPEAKCARE_API_BASE_URL;
const isExtension = process.env.REACT_APP_IS_EXTENSION === 'true';
console.log('Running in extension mode:', isExtension);

const App: React.FC = () => {
  const [tables, setTables] = useState<string[]>([]);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const [ehrUpdating, setEhrUpdating] = useState<boolean>(false);
  const [recordingTime, setRecordingTime] = useState<number>(0);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const audioType = 'audio/webm; codecs=opus';
  const audioFileName = 'recording.webm';

  // update state on mount
  useEffect(() => {
    // Load saved state on mount
    loadState('appState', async (savedState: any) => {
      if (savedState) {
        setSelectedTables(savedState.selectedTables || []);
      }
      if (savedState.audioBlob) {
        const blob = base64ToBlob(savedState.audioBlob, audioType);
        setAudioBlob(blob);
      }
      if (savedState.recordingTime) {
        setRecordingTime(savedState.recordingTime);
      }
    });

    // Fetch EMR tables
    axios.get(`${apiBaseUrl}/api/table-names`)
      .then(response => {
        setTables(response.data.table_names);
      })
      .catch(error => console.error("Error fetching tables:", error));
  }, []);

  // Save state whenever it changes
  useEffect(() => {
    const save = async () => {
      if (audioBlob) {
        const audioBlobBase64 = await blobToBase64(audioBlob);
        saveState('appState', {
          selectedTables,
          audioBlob: audioBlobBase64,
          recordingTime,
        });
      } else {
        saveState('appState', {
          selectedTables,
        });
      }
    };
    save();
  }, [selectedTables, audioBlob]);


  const handleTableChange = (event: SelectChangeEvent<string[]>) => {
    const value = event.target.value;
    setSelectedTables(typeof value === 'string' ? value.split(',') : value);
  };

  const updateDemoEhr = async () => {
    if (!audioBlob || !selectedTables) {
      console.error('Please select a chart and make a recording first.');
      return;
    }
  
    const formData = new FormData();
    formData.append('audio_file', audioBlob, audioFileName ?? 'recording.webm'); // Append the audio file with a filename
      // Append each table name to the form data
    selectedTables.forEach((table) => {
      formData.append('table_name', table);
    });
    //formData.append('table_name', selectedTable); // Append the table name
    setEhrUpdating(true);
    try {
      const response = await axios.post(`${apiBaseUrl}/api/process-audio`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setAudioBlob(null);
      setRecordingTime(0);
      console.log('Response from backend:', response.data);
      if (isExtension) {
        // refresh the EHR page so we can see the new data
        console.log('Dispatching visibility change event to current tab');
        dispatchVisibilityChangeEvent();
      }
    } catch (error) {
      console.error('Error sending data to backend:', error);
    }
    setEhrUpdating(false);
  };

  const updatePcc = async () => {
    setLoading(true);
    setMessage(null);

    try {
      // Extract form fields from the current page
      const extractedFields = await extractAssessmentSectionFormFields();
      console.log('Extracted Fields:', extractedFields);

      // Add static data to formData
      const formData = {
        ...extractedFields,
        lastUpdateField: 'Cust_G_14',
        Cust_G_14: 'Test message from Chrome extension',
        ackCust_G_14: 'Y',
      };

      // Send the save request
      const response = await sendSaveRequest(formData);
      console.log('Response:', response);
      setMessage('Data submitted successfully!');
    } catch (error) {
      console.error('Error:', error);
      if (error instanceof Error) {
        setMessage(`Error: ${error.message}`);
      } else {
        setMessage('An unknown error occurred.');
      }
    } finally {
      setLoading(false);
    }
  };
  

  return (
    <Container maxWidth="sm" sx={{ marginTop: 4 }}>
      {/* Flexbox Container for Logo and Title */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', marginBottom: '15px',marginTop: '-20px'}}>
        <img 
          src={`${process.env.PUBLIC_URL}/images/speakcare-logo-128.png`} 
          alt="SpeakCare Logo" 
          style={{ width: '150px', marginRight: '50px', marginBottom: '-30px' }} // Add margin to space between logo and text
        />
        <Typography variant="h6" gutterBottom sx={{ paddingTop: '6px',  textAlign: 'center', color: 'primary.main', fontWeight: 550}}>
         You do the care, we will do the rest
        </Typography>
      </div>

      <FormControl fullWidth sx={{ marginBottom: 3 }}>
        <InputLabel>Chart Selection</InputLabel>
        <Select 
          multiple
          value={selectedTables} 
          onChange={handleTableChange} 
          renderValue={(selected) => selected.join(', ')}
          label="Chart Selection">
          {tables.map((table) => (
            <MenuItem key={table} value={table}>
            <Checkbox checked={selectedTables.indexOf(table) > -1} />
            <ListItemText primary={table} />
          </MenuItem>
          ))}
        </Select>
      </FormControl>

      <AudioRecorder 
        audioType={audioType}
        setAudioBlob={setAudioBlob}
        recordingTime={recordingTime}
        setRecordingTime={setRecordingTime}
        initialAudioBlob={audioBlob}
      />

      <Button 
        variant="contained" 
        color="primary" 
        fullWidth 
        onClick={updateDemoEhr} 
        sx={{ marginTop: 3 }}
        disabled={!audioBlob || selectedTables.length === 0 || ehrUpdating}
      >
        {ehrUpdating ? <CircularProgress size={24} /> : 'Update EHR'}
      </Button>
      <Button 
          variant="outlined" 
          color="secondary" 
          fullWidth 
          onClick={updatePcc} 
          sx={{ marginTop: 2 }}
        >
          {loading ? <CircularProgress size={24} /> : 'Save to PCC EHR'}
      </Button>
      {/* Feedback Message */}
      {message && <Typography variant="body1">{message}</Typography>}

    </Container>
  );
 
};

export default App;