import { jsx as _jsx } from "react/jsx-runtime";
import './styles.css';
//import ReactDOM from 'react-dom';
import ReactDOM from 'react-dom/client';
import App from './App';
const rootElement = document.getElementById('root');
const root = ReactDOM.createRoot(rootElement); // Use createRoot instead of render
root.render(_jsx(App, {}));
