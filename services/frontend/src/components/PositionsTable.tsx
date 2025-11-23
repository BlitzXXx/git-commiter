import { format } from 'date-fns';
import type { Position } from '../types';

interface PositionsTableProps {
  positions: Position[];
}

export const PositionsTable: React.FC<PositionsTableProps> = ({ positions }) => {
  const totalUnrealizedPnL = positions.reduce((sum, pos) => sum + pos.unrealized_pnl, 0);

  return (
    <div className="card">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-bold">Open Positions</h2>
        <div className="text-sm">
          <span className="text-gray-400">Total Unrealized P&L: </span>
          <span className={totalUnrealizedPnL >= 0 ? 'positive' : 'negative'}>
            ${totalUnrealizedPnL.toFixed(2)} ({positions.length} positions)
          </span>
        </div>
      </div>

      {positions.length === 0 ? (
        <div className="text-center text-gray-400 py-10">
          No open positions
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b border-gray-700">
              <tr>
                <th className="text-left py-3 px-4">Ticker</th>
                <th className="text-right py-3 px-4">Quantity</th>
                <th className="text-right py-3 px-4">Entry Price</th>
                <th className="text-right py-3 px-4">Current Price</th>
                <th className="text-right py-3 px-4">Unrealized P&L</th>
                <th className="text-right py-3 px-4">Return %</th>
                <th className="text-right py-3 px-4">Opened At</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((position) => (
                <tr key={position.id} className="border-b border-gray-800 hover:bg-gray-700">
                  <td className="py-3 px-4 font-semibold">{position.ticker}</td>
                  <td className="text-right py-3 px-4">{position.quantity}</td>
                  <td className="text-right py-3 px-4">${position.entry_price.toFixed(2)}</td>
                  <td className="text-right py-3 px-4">${position.current_price.toFixed(2)}</td>
                  <td className={`text-right py-3 px-4 ${position.unrealized_pnl >= 0 ? 'positive' : 'negative'}`}>
                    ${position.unrealized_pnl.toFixed(2)}
                  </td>
                  <td className={`text-right py-3 px-4 ${position.unrealized_pnl_pct >= 0 ? 'positive' : 'negative'}`}>
                    {position.unrealized_pnl_pct >= 0 ? '+' : ''}{position.unrealized_pnl_pct.toFixed(2)}%
                  </td>
                  <td className="text-right py-3 px-4 text-sm text-gray-400">
                    {format(new Date(position.opened_at), 'MMM dd, HH:mm:ss')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
