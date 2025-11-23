import { format } from 'date-fns';
import type { Trade } from '../types';

interface TradesTableProps {
  trades: Trade[];
}

export const TradesTable: React.FC<TradesTableProps> = ({ trades }) => {
  return (
    <div className="card">
      <h2 className="text-xl font-bold mb-4">Recent Trades</h2>

      {trades.length === 0 ? (
        <div className="text-center text-gray-400 py-10">
          No trades yet
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="border-b border-gray-700">
              <tr>
                <th className="text-left py-3 px-4">Time</th>
                <th className="text-left py-3 px-4">Ticker</th>
                <th className="text-center py-3 px-4">Type</th>
                <th className="text-right py-3 px-4">Quantity</th>
                <th className="text-right py-3 px-4">Price</th>
                <th className="text-right py-3 px-4">Total Value</th>
                <th className="text-right py-3 px-4">Realized P&L</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade) => {
                const totalValue = trade.quantity * trade.price;
                return (
                  <tr key={trade.id} className="border-b border-gray-800 hover:bg-gray-700">
                    <td className="py-3 px-4 text-sm text-gray-400">
                      {format(new Date(trade.timestamp), 'MMM dd, HH:mm:ss')}
                    </td>
                    <td className="py-3 px-4 font-semibold">{trade.ticker}</td>
                    <td className="text-center py-3 px-4">
                      <span className={trade.signal_type === 'BUY' ? 'badge-buy' : 'badge-sell'}>
                        {trade.signal_type}
                      </span>
                    </td>
                    <td className="text-right py-3 px-4">{trade.quantity}</td>
                    <td className="text-right py-3 px-4">${trade.price.toFixed(2)}</td>
                    <td className="text-right py-3 px-4">${totalValue.toFixed(2)}</td>
                    <td className={`text-right py-3 px-4 ${
                      trade.realized_pnl === undefined || trade.realized_pnl === null
                        ? 'text-gray-500'
                        : trade.realized_pnl >= 0
                        ? 'positive'
                        : 'negative'
                    }`}>
                      {trade.realized_pnl !== undefined && trade.realized_pnl !== null
                        ? `$${trade.realized_pnl.toFixed(2)}`
                        : '-'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
