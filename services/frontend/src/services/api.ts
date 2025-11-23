import axios from 'axios';
import type { Position, Trade, SentimentData, Performance } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 10000,
});

export const fetchPositions = async (): Promise<Position[]> => {
  const response = await api.get('/positions');
  return response.data;
};

export const fetchTrades = async (limit = 50, ticker?: string): Promise<Trade[]> => {
  const params = new URLSearchParams();
  params.append('limit', limit.toString());
  if (ticker) {
    params.append('ticker', ticker);
  }
  const response = await api.get(`/trades?${params.toString()}`);
  return response.data;
};

export const fetchSentiment = async (
  ticker: string,
  window = '5min',
  limit = 100
): Promise<SentimentData[]> => {
  const params = new URLSearchParams();
  params.append('window', window);
  params.append('limit', limit.toString());
  const response = await api.get(`/sentiment/${ticker}?${params.toString()}`);
  return response.data;
};

export const fetchPerformance = async (): Promise<Performance> => {
  const response = await api.get('/performance');
  return response.data;
};

export const checkHealth = async (): Promise<{ status: string }> => {
  const response = await api.get('/health');
  return response.data;
};
