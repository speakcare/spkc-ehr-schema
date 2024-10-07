import React, { useEffect, useState } from 'react';
import AudioRecorder from './components/AudioRecorder';
import axios from 'axios';

const apiBaseUrl = process.env.REACT_APP_SPEAKCARE_API_BASE_URL;


const App: React.FC = () => {
  const [tables, setTables] = useState<string[]>([]);
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null);
  const [audioFileName, setAudioFileName] = useState<string | null>(null);
  const [selectedTable, setSelectedTable] = useState<string>('');

  // Fetch EMR tables
  useEffect(() => {
    axios.get(`${apiBaseUrl}/api/table-names`)
      .then(response => {
        setTables(response.data.table_names);  // Accessing the array inside the object
      })
      .catch(error => console.error("Error fetching tables:", error));
  }, []);

  const updateEmr = async (formData: FormData) => {
    try {
      const response = await axios.post(`${apiBaseUrl}/api/process-audio2`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      console.log('Response from backend:', response.data);
    } catch (error) {
      console.error('Error sending data to backend:', error);
    }
  };

  const handleAudioBlobReady = (blob: Blob, fileName: string) => {
    setAudioBlob(blob);
    setAudioFileName(fileName);
  };

  const handleUpdateEMR = () => {
    if (audioBlob && selectedTable && audioFileName) {
      const formData = new FormData();
      formData.append('audio_file', audioBlob, audioFileName);
      formData.append('table_name', selectedTable);
      updateEmr(formData);
      setAudioBlob(null); // Reset the audio blob
    }
  };

  
  return (
    <div>
      <h1>SpeakCare</h1>

      <div>
        <label htmlFor="table-select">Select EMR Chart:</label>
        <select id="table-select" value={selectedTable} onChange={e => setSelectedTable(e.target.value)}>
          <option value="">Select a chart</option>
          {tables.map((table, index) => (
            <option key={index} value={table}>{table}</option>
          ))}
        </select>
      </div>

      <div>
        <h2>Speech Recorder</h2>
        <AudioRecorder onAudioBlobReady={handleAudioBlobReady} />
        <button onClick={handleUpdateEMR} disabled={!audioBlob || !selectedTable}>
          Update EMR
      </button>
      </div>
    </div>
  );
};

export default App;

