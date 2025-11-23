import { useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { format } from 'date-fns';
import { useQuery } from '@tanstack/react-query';
import { fetchSentiment } from '../services/api';

interface SentimentChartProps {
  tickers: string[];
}

export const SentimentChart: React.FC<SentimentChartProps> = ({ tickers }) => {
  const [selectedTicker, setSelectedTicker] = useState<string>(tickers[0] || 'AAPL');
  const [timeWindow, setTimeWindow] = useState<string>('5min');

  const { data: sentimentData = [], isLoading } = useQuery({
    queryKey: ['sentiment', selectedTicker, timeWindow],
    queryFn: () => fetchSentiment(selectedTicker, timeWindow, 100),
    enabled: !!selectedTicker,
    refetchInterval: 30000, // Refetch every 30 seconds
  });

  const chartData = sentimentData.map((d) => ({
    ...d,
    displayTime: format(new Date(d.timestamp), 'HH:mm'),
  }));

  return (
    <div className="card">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold">Sentiment Analysis</h2>
        <div className="flex gap-2">
          <select
            value={selectedTicker}
            onChange={(e) => setSelectedTicker(e.target.value)}
            className="bg-gray-700 text-white px-3 py-1 rounded border border-gray-600 focus:outline-none focus:border-primary"
          >
            {tickers.map((ticker) => (
              <option key={ticker} value={ticker}>
                {ticker}
              </option>
            ))}
          </select>
          <select
            value={timeWindow}
            onChange={(e) => setTimeWindow(e.target.value)}
            className="bg-gray-700 text-white px-3 py-1 rounded border border-gray-600 focus:outline-none focus:border-primary"
          >
            <option value="1min">1 min</option>
            <option value="5min">5 min</option>
            <option value="15min">15 min</option>
            <option value="1h">1 hour</option>
          </select>
        </div>
      </div>

      {isLoading ? (
        <div className="text-center text-gray-400 py-10">
          Loading sentiment data...
        </div>
      ) : chartData.length === 0 ? (
        <div className="text-center text-gray-400 py-10">
          No sentiment data available for {selectedTicker}
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
            <XAxis
              dataKey="displayTime"
              stroke="#9ca3af"
              style={{ fontSize: '12px' }}
            />
            <YAxis
              yAxisId="sentiment"
              domain={[-1, 1]}
              stroke="#9ca3af"
              style={{ fontSize: '12px' }}
            />
            <YAxis
              yAxisId="mentions"
              orientation="right"
              stroke="#9ca3af"
              style={{ fontSize: '12px' }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1f2937',
                border: '1px solid #374151',
                borderRadius: '8px',
              }}
              formatter={(value: number, name: string) => {
                if (name === 'Avg Sentiment' || name === 'Weighted Sentiment') {
                  return [value.toFixed(3), name];
                }
                return [value, name];
              }}
              labelFormatter={(label) => `Time: ${label}`}
            />
            <Legend />
            <Line
              yAxisId="sentiment"
              type="monotone"
              dataKey="avg_sentiment"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              name="Avg Sentiment"
            />
            <Line
              yAxisId="sentiment"
              type="monotone"
              dataKey="weighted_sentiment"
              stroke="#10b981"
              strokeWidth={2}
              dot={false}
              name="Weighted Sentiment"
            />
            <Line
              yAxisId="mentions"
              type="monotone"
              dataKey="mention_count"
              stroke="#f59e0b"
              strokeWidth={2}
              dot={false}
              name="Mentions"
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
};
