import React, { useEffect, useState, useRef } from 'react';
import { Container, FormControl, InputLabel, MenuItem, Select, Button, Typography, SelectChangeEvent, CircularProgress } from '@mui/material';
import AudioRecorder from './components/AudioRecorder'; 

import axios from 'axios';
import './App.css';
import { dispatchVisibilityChangeEvent, saveState, loadState, blobToBase64, base64ToBlob  } from './utils';


const apiBaseUrl = process.env.REACT_APP_SPEAKCARE_API_BASE_URL;
const isExtension = process.env.REACT_APP_IS_EXTENSION === 'true';
console.log('Running in extension mode:', isExtension);

const App: React.FC = () => {
  const [tables, setTables] = useState<string[]>([]);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [selectedTable, setSelectedTable] = useState<string>('');
  const [ehrUpdating, setEhrUpdating] = useState<boolean>(false);
  const [recordingTime, setRecordingTime] = useState<number>(0);
  const audioType = 'audio/webm; codecs=opus';
  const audioFileName = 'recording.webm';

  // update state on mount
  useEffect(() => {
    // Load saved state on mount
    loadState('appState', async (savedState: any) => {
      if (savedState) {
        setSelectedTable(savedState.selectedTable || '');
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
          selectedTable,
          audioBlob: audioBlobBase64,
          recordingTime,
        });
      } else {
        saveState('appState', {
          selectedTable,
        });
      }
    };
    save();
  }, [selectedTable, audioBlob]);

  const handleTableChange = (event: SelectChangeEvent<string>) => {
    setSelectedTable(event.target.value as string);
  };

  const updateEhr = async () => {
    if (!audioBlob || !selectedTable) {
      console.error('Please select a chart and make a recording first.');
      return;
    }
  
    const formData = new FormData();
    formData.append('audio_file', audioBlob, audioFileName ?? 'recording.webm'); // Append the audio file with a filename
    formData.append('table_name', selectedTable); // Append the table name
    setEhrUpdating(true);
    try {
      const response = await axios.post(`${apiBaseUrl}/api/process-audio2`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setAudioBlob(null);
      setRecordingTime(0);
      console.log('Response from backend:', response.data);
      if (isExtension) {
        // refresh the EHR page so we can see the new data
        dispatchVisibilityChangeEvent();
      }
    } catch (error) {
      console.error('Error sending data to backend:', error);
    }
    setEhrUpdating(false);
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
        <Select value={selectedTable} onChange={handleTableChange} label="Chart Selection">
          {tables.map((table) => (
            <MenuItem key={table} value={table}>
              {table}
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
        onClick={updateEhr} 
        sx={{ marginTop: 3 }}
        disabled={!audioBlob || !selectedTable || ehrUpdating}
      >
        {ehrUpdating ? <CircularProgress size={24} /> : 'Update EHR'}
      </Button>
    </Container>
  );
};

export default App;