import React, { useState, useEffect } from 'react';
import { SessionLog } from '../types';
import { getSessionLogs } from '../background/session_manager';  

const App: React.FC = () => {
  const [logs, setLogs] = useState<SessionLog[]>([]);
  const [filter, setFilter] = useState('');


  useEffect(() => {
    const fetchLogs = async () => {
        const savedLogs = await getSessionLogs();
        console.log('Fetched logs:', savedLogs); // Debugging
        //setLogs(savedLogs);
        setLogs(savedLogs.map(log => ({ ...log, userId: log.userId || '' })));
    };

    fetchLogs();
  }, []);

  //const filteredLogs = logs.filter(log => log.userId.includes(filter));
  const filteredLogs = logs.filter(log => log.userId && log.userId.includes(filter));


  return (
    <div>
      <h1>Session Logs</h1>
      <input
        type="text"
        placeholder="Filter by username"
        value={filter}
        onChange={e => setFilter(e.target.value)}
      />
      <table>
        <thead>
          <tr>
            <th>Username</th>
            <th>Start Time</th>
            <th>Last Edit Time</th>
            <th>Duration</th>
          </tr>
        </thead>
        <tbody>
          {filteredLogs.map((log, index) => (
            <tr key={index}>
              <td>{log.userId}</td>
              <td>{new Date(log.startTime).toLocaleString()}</td>
              <td>
                {log.lastActivityTime
                  ? new Date(log.lastActivityTime).toLocaleString()
                  : 'N/A'}
              </td>
              <td>
                {log.duration
                  ? `${(log.duration / 1000).toFixed(2)} seconds`
                  : 'In Progress'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default App;
