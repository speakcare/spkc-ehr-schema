import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useState, useEffect } from 'react';
const App = () => {
    const [logs, setLogs] = useState([]);
    const [filter, setFilter] = useState('');
    useEffect(() => {
        const savedLogs = JSON.parse(localStorage.getItem('session_logs') || '[]');
        setLogs(savedLogs);
    }, []);
    const filteredLogs = logs.filter(log => log.userId.includes(filter));
    return (_jsxs("div", { children: [_jsx("h1", { children: "Session Logs" }), _jsx("input", { type: "text", placeholder: "Filter by username", value: filter, onChange: e => setFilter(e.target.value) }), _jsxs("table", { children: [_jsx("thead", { children: _jsxs("tr", { children: [_jsx("th", { children: "Username" }), _jsx("th", { children: "Start Time" }), _jsx("th", { children: "Last Edit Time" }), _jsx("th", { children: "Duration" })] }) }), _jsx("tbody", { children: filteredLogs.map((log, index) => (_jsxs("tr", { children: [_jsx("td", { children: log.userId }), _jsx("td", { children: new Date(log.startTime).toLocaleString() }), _jsx("td", { children: log.lastActivityTime
                                        ? new Date(log.lastActivityTime).toLocaleString()
                                        : 'N/A' }), _jsx("td", { children: log.duration
                                        ? `${(log.duration / 1000).toFixed(2)} seconds`
                                        : 'In Progress' })] }, index))) })] })] }));
};
export default App;
