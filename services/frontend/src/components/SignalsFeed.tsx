import { format } from 'date-fns';
import type { Signal } from '../types';

interface SignalsFeedProps {
  signals: Signal[];
  maxSignals?: number;
}

export const SignalsFeed: React.FC<SignalsFeedProps> = ({ signals, maxSignals = 20 }) => {
  const displaySignals = signals.slice(0, maxSignals);

  return (
    <div className="card">
      <h2 className="text-xl font-bold mb-4">Live Signals Feed</h2>

      {displaySignals.length === 0 ? (
        <div className="text-center text-gray-400 py-10">
          No signals yet. Waiting for trading opportunities...
        </div>
      ) : (
        <div className="space-y-3 max-h-[600px] overflow-y-auto">
          {displaySignals.map((signal, index) => (
            <div
              key={`${signal.ticker}-${signal.timestamp}-${index}`}
              className={`p-4 rounded-lg border ${
                signal.signal_type === 'BUY'
                  ? 'bg-green-900/20 border-green-700'
                  : 'bg-red-900/20 border-red-700'
              }`}
            >
              <div className="flex justify-between items-start mb-2">
                <div className="flex items-center gap-3">
                  <span className="text-xl font-bold">{signal.ticker}</span>
                  <span className={signal.signal_type === 'BUY' ? 'badge-buy' : 'badge-sell'}>
                    {signal.signal_type}
                  </span>
                </div>
                <div className="text-sm text-gray-400">
                  {format(new Date(signal.timestamp), 'HH:mm:ss')}
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4 mb-2 text-sm">
                <div>
                  <span className="text-gray-400">Price: </span>
                  <span className="font-semibold">${signal.current_price.toFixed(2)}</span>
                </div>
                <div>
                  <span className="text-gray-400">Sentiment: </span>
                  <span className={`font-semibold ${
                    signal.avg_sentiment > 0.5 ? 'text-green-400' :
                    signal.avg_sentiment < -0.5 ? 'text-red-400' :
                    'text-gray-400'
                  }`}>
                    {signal.avg_sentiment.toFixed(3)}
                  </span>
                </div>
                <div>
                  <span className="text-gray-400">Mentions: </span>
                  <span className="font-semibold">{signal.mention_count}</span>
                </div>
              </div>

              <div className="text-sm text-gray-300">
                <span className="text-gray-400">Reasoning: </span>
                {signal.reasoning}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
