import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { fetchPositions, fetchTrades, fetchPerformance } from './services/api';
import { useWebSocket } from './hooks/useWebSocket';
import { PnLChart } from './components/PnLChart';
import { PositionsTable } from './components/PositionsTable';
import { TradesTable } from './components/TradesTable';
import { SentimentChart } from './components/SentimentChart';
import { SignalsFeed } from './components/SignalsFeed';
import type { Position, Trade, Signal, Performance, WebSocketMessage } from './types';

function App() {
  const [liveSignals, setLiveSignals] = useState<Signal[]>([]);
  const [livePerformance, setLivePerformance] = useState<Performance | null>(null);

  // Fetch initial data
  const { data: positions = [], refetch: refetchPositions } = useQuery<Position[]>({
    queryKey: ['positions'],
    queryFn: fetchPositions,
    refetchInterval: 10000,
  });

  const { data: trades = [], refetch: refetchTrades } = useQuery<Trade[]>({
    queryKey: ['trades'],
    queryFn: () => fetchTrades(50),
    refetchInterval: 10000,
  });

  const { data: performance } = useQuery<Performance>({
    queryKey: ['performance'],
    queryFn: fetchPerformance,
    refetchInterval: 10000,
  });

  // Get unique tickers from positions and recent trades for sentiment chart
  const uniqueTickers = Array.from(
    new Set([
      ...positions.map(p => p.ticker),
      ...trades.slice(0, 10).map(t => t.ticker),
      'AAPL', 'TSLA', 'GME', // Default tickers
    ])
  ).slice(0, 10);

  // WebSocket message handler
  const handleWebSocketMessage = useCallback((message: WebSocketMessage) => {
    if (message.type === 'signal') {
      const signal = message.data as Signal;
      setLiveSignals(prev => [signal, ...prev].slice(0, 50));

      // Refetch positions and trades when we get a new signal
      refetchPositions();
      refetchTrades();
    } else if (message.type === 'performance') {
      setLivePerformance(message.data as Performance);
    } else if (message.type === 'position_update') {
      refetchPositions();
    }
  }, [refetchPositions, refetchTrades]);

  // Connect to WebSocket
  const { isConnected, error: wsError } = useWebSocket(handleWebSocketMessage);

  // Use live performance if available, otherwise use fetched performance
  const displayPerformance = livePerformance || performance;

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      {/* Header */}
      <header className="bg-gray-800 border-b border-gray-700 py-4 px-6">
        <div className="max-w-7xl mx-auto flex justify-between items-center">
          <div>
            <h1 className="text-2xl font-bold text-primary">SentimentEdge</h1>
            <p className="text-sm text-gray-400">Algorithmic Trading Dashboard</p>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className={`w-2 h-2 rounded-full ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className="text-sm text-gray-400">
                {isConnected ? 'Live' : 'Disconnected'}
              </span>
            </div>
            {wsError && (
              <span className="text-sm text-red-400">{wsError}</span>
            )}
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6">
        {/* Performance Stats */}
        {displayPerformance && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="stat-card">
              <div className="text-sm text-gray-400 mb-1">Total P&L</div>
              <div className={`text-2xl font-bold ${displayPerformance.total_pnl >= 0 ? 'positive' : 'negative'}`}>
                ${displayPerformance.total_pnl.toFixed(2)}
              </div>
            </div>
            <div className="stat-card">
              <div className="text-sm text-gray-400 mb-1">Daily P&L</div>
              <div className={`text-2xl font-bold ${displayPerformance.daily_pnl >= 0 ? 'positive' : 'negative'}`}>
                ${displayPerformance.daily_pnl.toFixed(2)}
              </div>
            </div>
            <div className="stat-card">
              <div className="text-sm text-gray-400 mb-1">Win Rate</div>
              <div className="text-2xl font-bold">{(displayPerformance.win_rate * 100).toFixed(1)}%</div>
              <div className="text-xs text-gray-400 mt-1">
                {displayPerformance.winning_trades}W / {displayPerformance.losing_trades}L
              </div>
            </div>
            <div className="stat-card">
              <div className="text-sm text-gray-400 mb-1">Total Trades</div>
              <div className="text-2xl font-bold">{displayPerformance.total_trades}</div>
              {displayPerformance.sharpe_ratio !== null && (
                <div className="text-xs text-gray-400 mt-1">
                  Sharpe: {displayPerformance.sharpe_ratio.toFixed(2)}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Main Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 mb-6">
          <div className="lg:col-span-2">
            <PnLChart trades={trades} />
          </div>
          <div>
            <SignalsFeed signals={liveSignals} maxSignals={10} />
          </div>
        </div>

        {/* Positions */}
        <div className="mb-6">
          <PositionsTable positions={positions} />
        </div>

        {/* Sentiment Chart */}
        {uniqueTickers.length > 0 && (
          <div className="mb-6">
            <SentimentChart tickers={uniqueTickers} />
          </div>
        )}

        {/* Trades History */}
        <div className="mb-6">
          <TradesTable trades={trades} />
        </div>
      </main>

      {/* Footer */}
      <footer className="bg-gray-800 border-t border-gray-700 py-4 px-6 mt-12">
        <div className="max-w-7xl mx-auto text-center text-sm text-gray-400">
          <p>SentimentEdge © 2025 | Paper Trading Only | Not Financial Advice</p>
        </div>
      </footer>
    </div>
  );
}

export default App;
