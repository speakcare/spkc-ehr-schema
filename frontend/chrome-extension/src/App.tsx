import React, { useEffect, useState } from 'react';
import axios from 'axios';

const apiBaseUrl = process.env.REACT_APP_SPEAKCARE_API_BASE_URL;

interface AudioDevice {
  name: string;
  index: string;
}

const App: React.FC = () => {
  const [tables, setTables] = useState<string[]>([]);
  const [devices, setDevices] = useState<AudioDevice[]>([]);
  const [selectedTable, setSelectedTable] = useState<string>('');
  const [selectedDevice, setSelectedDevice] = useState<string>('');

  // Fetch EMR tables
  useEffect(() => {
    axios.get(`${apiBaseUrl}/api/table-names`)
      .then(response => {
        setTables(response.data.table_names);  // Accessing the array inside the object
      })
      .catch(error => console.error("Error fetching tables:", error));
  }, []);

  // Fetch audio devices
  useEffect(() => {
    axios.get(`${apiBaseUrl}/api/audio-devices`)
      .then(response => setDevices(response.data))
      .catch(error => console.error("Error fetching devices:", error));
  }, []);

  // Handle "Start Listening" button click
  const startListening = () => {
    const audioDeviceIndex = parseInt(selectedDevice, 10);
    axios.post(`${apiBaseUrl}/api/process-audio`, {
      table_name: selectedTable,
      audio_device: audioDeviceIndex
    })
    .then(response => {
      console.log("Audio processing started:", response.data);
    })
    .catch(error => {
      console.error("Error starting audio processing:", error);
    });
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
        <label htmlFor="device-select">Select Audio Device:</label>
        <select id="device-select" value={selectedDevice} onChange={e => setSelectedDevice(e.target.value)}>
          <option value="">Select a device</option>
          {devices.map((device, index) => (
            <option key={index} value={device.index}>{device.name}</option>
          ))}
        </select>
      </div>

      <button onClick={startListening} disabled={!selectedTable || !selectedDevice}>
        Start Listening
      </button>
    </div>
  );
};

export default App;

