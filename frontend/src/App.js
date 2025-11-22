import React from 'react';
import './App.css';

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1>🚀 SentimentEdge</h1>
        <p>Real-Time Market Sentiment Trading Bot</p>
        <div style={{marginTop: '2rem', textAlign: 'left', maxWidth: '600px'}}>
          <h2>Status: Placeholder Mode</h2>
          <p>Dashboard will be implemented in Phase 12</p>
          <h3>Planned Features:</h3>
          <ul>
            <li>Live P&L Chart</li>
            <li>Current Positions Table</li>
            <li>Recent Trades</li>
            <li>Sentiment Charts</li>
            <li>Trading Signals Feed</li>
          </ul>
          <p style={{marginTop: '2rem', fontSize: '0.9rem', opacity: 0.7}}>
            API Status: <a href="http://localhost:8000/health" target="_blank" rel="noopener noreferrer">Check API Health</a>
          </p>
        </div>
      </header>
    </div>
  );
}

export default App;
