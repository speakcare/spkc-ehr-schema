import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Container, Button, CircularProgress, Typography, SelectChangeEvent, FormControl, InputLabel, Select, MenuItem, Checkbox, ListItemText, IconButton, Box } from '@mui/material';
import AudioRecorder from './components/AudioRecorder';
import AudioButtons from './components/AudioButtons';
import { dispatchVisibilityChangeEvent, saveState, loadState, blobToBase64, base64ToBlob, reloadCurrentTab } from './utils';
import { extractAssessmentSectionFormFields, sendRequestToTabUrl} from './pcc-utils';
import { generatePccFormData } from './pcc-forms';

declare global {
  interface Window {
    showSaveFilePicker: (options: { suggestedName: string; types: { description: string; accept: { [key: string]: string[] } }[] }) => Promise<FileSystemFileHandle>;
    FileSystemFileHandle: {
      createWritable: () => Promise<FileSystemWritableFileStream>;
    };
  }
}

const apiBaseUrl = process.env.REACT_APP_SPEAKCARE_API_BASE_URL;
const isExtension = process.env.REACT_APP_IS_EXTENSION === 'true';
console.log('Running in extension mode:', isExtension);

const App: React.FC = () => {
  const [tables, setTables] = useState<string[]>([]);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [selectedTables, setSelectedTables] = useState<string[]>([]);
  const [ehrUpdating, setEhrUpdating] = useState<boolean>(false);
  const [pccUpdating, setPccUpdating] = useState<boolean>(false);
  const [recordingTime, setRecordingTime] = useState<number>(0);
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

  const handleDeleteAudio = () => {
    setAudioBlob(null);
    setRecordingTime(0);
  };

  const updateDemoEhr = async () => {
    if (!audioBlob || !selectedTables) {
      console.error('Please select a chart and make a recording first.');
      return;
    }
  
    const formData = new FormData();
    formData.append('audio_file', audioBlob, audioFileName ?? 'recording.webm');
    selectedTables.forEach((table) => {
      formData.append('table_name', table);
    });
 
    setEhrUpdating(true);
    try {
      const response = await axios.post(`${apiBaseUrl}/api/process-audio`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
  
      console.log('Response from backend:', response.data);
      if (isExtension) {
        console.log('Dispatching visibility change event to current tab');
        dispatchVisibilityChangeEvent();
      }
    } catch (error) {
      console.error('Error sending data to backend:', error);
    }
    setEhrUpdating(false);
  };

  const updatePccFallRisk = async () => {
    setPccUpdating(true);
    setMessage(null);
    try {
      // Extract form fields from the current page
      const extractedFields = await extractAssessmentSectionFormFields();
      console.log('Extracted Fields:', extractedFields);

      // Make API call to process audio without updating EMR
      const formData = new FormData();
      formData.append('audio_file', audioBlob!, audioFileName ?? 'recording.webm');
      formData.append('table_name', 'Fall Risk Screen');
      formData.append('update_emr', 'false');

      console.log('Making API call to process audio...');
      console.debug('FormData entries:');
      for (let pair of formData.entries()) {
        console.debug(pair[0] + ': ' + pair[1]);
      }
     
      const response = await axios.post(`${apiBaseUrl}/api/process-audio`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      console.log('API call completed');
      console.debug('Response from backend:', response.data);
      console.debug('Response type:', typeof response.data);
      console.debug('Response keys:', Object.keys(response.data));

      // Generate PCC form data from the response
      console.log('Generating PCC form data...');
      const pccFormData = generatePccFormData(response.data);
      console.log('PCC form data generated:', pccFormData);

      // Combine extracted fields with PCC form data
      const finalFormData = {
        ...extractedFields,
        ...pccFormData
      };

      // Send the save request
      const saveResponse = await sendRequestToTabUrl(finalFormData);
      console.debug('Response:', saveResponse);
      setMessage('Data submitted successfully!');
      // Reload the current tab to see the changes
      reloadCurrentTab();
    } catch (error) {
      console.error('Error:', error);
      if (error instanceof Error) {
        setMessage(`Error: ${error.message}`);
      } else {
        setMessage('An unknown error occurred.');
      }
    } finally {
      setPccUpdating(false);
    }
  };
  
  const handleSaveAudio = async () => {
    if (!audioBlob) return;
    
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: 'speakcare-recording.webm',
        types: [{
          description: 'WebM Audio File',
          accept: {
            'audio/webm': ['.webm']
          }
        }]
      });
      
      const writable = await handle.createWritable();
      await writable.write(audioBlob);
      await writable.close();
      setMessage(`Audio file saved successfully as "${handle.name}"`);
    } catch (err) {
      console.error('Error saving file:', err);
      // Fallback to the old method if showSaveFilePicker is not supported
      const url = URL.createObjectURL(audioBlob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'speakcare-recording.webm';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setMessage(`Audio file speakcare-recording.webm downloaded to downloads folder`);
    }
  };

  const handleLoadAudio = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file && (file.type === 'audio/webm' || file.type === 'audio/webm; codecs=opus' || file.name.endsWith('.webm'))) {
      setAudioBlob(file);
      
      // Calculate audio duration
      try {
        const arrayBuffer = await file.arrayBuffer();
        const audioContext = new (window.AudioContext || (window as any).webkitAudioContext)();
        const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);
        const durationInSeconds = Math.round(audioBuffer.duration);
        setRecordingTime(durationInSeconds);
        setMessage(`Audio file ${file.name} loaded successfully! Duration: ${durationInSeconds} seconds`);
      } catch (error) {
        console.error('Error calculating audio duration:', error);
        setRecordingTime(0);
        setMessage(`Audio file ${file.name} loaded successfully! (Duration calculation failed)`);
      }
    } else {
      setMessage('Please select a valid .webm audio file');
    }
  };

  return (
    <Container maxWidth="sm" sx={{ marginTop: 4, height: '100vh', padding: 2 }}>
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
        setMessage={setMessage}
      />

      <AudioButtons
        audioBlob={audioBlob}
        audioType={audioType}
        onSave={handleSaveAudio}
        onLoad={handleLoadAudio}
      />

      <Button 
        variant="contained" 
        color="primary" 
        fullWidth 
        onClick={updateDemoEhr} 
        sx={{ marginTop: 3 }}
        disabled={!audioBlob || selectedTables.length === 0 || ehrUpdating}
      >
        {ehrUpdating ? <CircularProgress size={24} /> : 'Update Demo EHR'}
      </Button>


      <Button 
          variant="outlined" 
          color="secondary" 
          fullWidth 
          onClick={updatePccFallRisk} 
          sx={{ 
            marginTop: 2, 
            color: 'black',
            backgroundColor: 'teal',
            borderColor: 'teal',
            fontWeight: 'bold',
            '&:hover': {
              borderColor: 'teal',
              backgroundColor: 'rgba(0, 128, 128, 0.8)',
            },
            '&.Mui-disabled': {
              color: 'gray',
              backgroundColor: 'lightgray',
              borderColor: 'lightgray',
            }
          }}
          disabled={!audioBlob || pccUpdating}
        >
          {pccUpdating ? <CircularProgress size={24} /> : 'Update PointClickCare'}
      </Button>
      {/* Feedback Message */}
      {message && <Typography variant="body1" sx={{ marginTop: 2 }}>{message}</Typography>}

    </Container>
  );
 
};

export default App;