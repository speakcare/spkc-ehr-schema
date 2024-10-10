import React, { useEffect, useState } from 'react';
import { Container, FormControl, InputLabel, MenuItem, Select, Button, Typography, SelectChangeEvent } from '@mui/material';
import AudioRecorder from './components/AudioRecorder';
import axios from 'axios';
import './App.css';


const apiBaseUrl = process.env.REACT_APP_SPEAKCARE_API_BASE_URL;

const App: React.FC = () => {
  const [tables, setTables] = useState<string[]>([]);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [selectedTable, setSelectedTable] = useState<string>('');
  const audioType = 'audio/webm; codecs=opus';
  const audioFileName = 'recording.webm';

  // Fetch EMR tables
  useEffect(() => {
    axios.get(`${apiBaseUrl}/api/table-names`)
      .then(response => {
        setTables(response.data.table_names);
      })
      .catch(error => console.error("Error fetching tables:", error));
  }, []);

  const handleTableChange = (event: SelectChangeEvent<string>) => {
    setSelectedTable(event.target.value as string);
  };

  const updateEmr = async () => {
    if (!audioBlob || !selectedTable) {
      console.error('Please select a chart and make a recording first.');
      return;
    }
  
    const formData = new FormData();
    formData.append('audio_file', audioBlob, audioFileName ?? 'recording.webm'); // Append the audio file with a filename
    formData.append('table_name', selectedTable); // Append the table name
  
    try {
      const response = await axios.post(`${apiBaseUrl}/api/process-audio2`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setAudioBlob(null);
      console.log('Response from backend:', response.data);
    } catch (error) {
      console.error('Error sending data to backend:', error);
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
        onAudioBlobReady={(blob) => setAudioBlob(blob)} 
      />

      <Button 
        variant="contained" 
        color="primary" 
        fullWidth 
        onClick={updateEmr} 
        sx={{ marginTop: 3 }}
        disabled={!audioBlob || !selectedTable}
      >
        Update EHR
      </Button>
    </Container>
  );
};

export default App;