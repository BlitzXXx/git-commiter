import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { format } from 'date-fns';
import type { Trade } from '../types';

interface PnLChartProps {
  trades: Trade[];
}

interface ChartDataPoint {
  timestamp: string;
  cumulative_pnl: number;
  displayTime: string;
}

export const PnLChart: React.FC<PnLChartProps> = ({ trades }) => {
  // Calculate cumulative P&L from trades
  const chartData: ChartDataPoint[] = trades
    .filter(t => t.realized_pnl !== undefined)
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .reduce((acc: ChartDataPoint[], trade) => {
      const prevPnL = acc.length > 0 ? acc[acc.length - 1].cumulative_pnl : 0;
      const newPnL = prevPnL + (trade.realized_pnl || 0);

      acc.push({
        timestamp: trade.timestamp,
        cumulative_pnl: newPnL,
        displayTime: format(new Date(trade.timestamp), 'HH:mm'),
      });

      return acc;
    }, []);

  return (
    <div className="card">
      <h2 className="text-xl font-bold mb-4">Cumulative P&L</h2>
      {chartData.length === 0 ? (
        <div className="text-center text-gray-400 py-10">
          No trades with realized P&L yet
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
              stroke="#9ca3af"
              style={{ fontSize: '12px' }}
              tickFormatter={(value) => `$${value.toFixed(2)}`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1f2937',
                border: '1px solid #374151',
                borderRadius: '8px',
              }}
              formatter={(value: number) => [`$${value.toFixed(2)}`, 'P&L']}
              labelFormatter={(label) => `Time: ${label}`}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="cumulative_pnl"
              stroke="#3b82f6"
              strokeWidth={2}
              dot={false}
              name="Cumulative P&L"
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  );
};
