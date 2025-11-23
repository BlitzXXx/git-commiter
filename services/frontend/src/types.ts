export interface Position {
  id: number;
  ticker: string;
  quantity: number;
  entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_pct: number;
  opened_at: string;
}

export interface Trade {
  id: number;
  ticker: string;
  signal_type: 'BUY' | 'SELL';
  quantity: number;
  price: number;
  timestamp: string;
  realized_pnl?: number;
  position_id?: number;
}

export interface SentimentData {
  ticker: string;
  timestamp: string;
  avg_sentiment: number;
  weighted_sentiment: number;
  mention_count: number;
  sentiment_std: number;
  sentiment_momentum: number;
}

export interface Signal {
  ticker: string;
  signal_type: 'BUY' | 'SELL';
  timestamp: string;
  avg_sentiment: number;
  mention_count: number;
  current_price: number;
  reasoning: string;
}

export interface Performance {
  total_pnl: number;
  daily_pnl: number;
  win_rate: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  avg_win: number;
  avg_loss: number;
  sharpe_ratio: number;
}

export interface WebSocketMessage {
  type: 'signal' | 'performance' | 'position_update';
  data: Signal | Performance | Position;
}
