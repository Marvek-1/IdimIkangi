import { useEffect, useState, useCallback } from 'react';

export interface BackendSignal {
  signal_id: string;
  pair: string;
  ts: string;
  side: 'LONG' | 'SHORT';
  entry: number;
  stop_loss: number;
  take_profit: number;
  score: number;
  regime: string;
  reason_trace: any;
  outcome?: string;
}

export function useSignalsSSE(url: string = '/api/stream') {
  const [signals, setSignals] = useState<BackendSignal[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchInitialSignals = useCallback(async () => {
    try {
      const response = await fetch('/api/signals');
      if (response.ok) {
        const data = await response.json();
        if (data.signals) {
          setSignals(data.signals);
        }
      }
    } catch (err) {
      console.error('Failed to fetch initial signals:', err);
    }
  }, []);

  useEffect(() => {
    fetchInitialSignals();

    let eventSource: EventSource | null = null;
    let reconnectTimeout: any;

    const connect = () => {
      console.log('Attempting SSE connection to:', url);
      eventSource = new EventSource(url);

      eventSource.onopen = () => {
        setIsConnected(true);
        setError(null);
        console.log('SSE connected');
      };

      eventSource.addEventListener('new_signal', (event: MessageEvent) => {
        try {
          const newSignal: BackendSignal = JSON.parse(event.data);
          setSignals((prev: BackendSignal[]) => {
            // Avoid duplicates
            if (prev.some((s: BackendSignal) => s.signal_id === newSignal.signal_id)) {
              return prev;
            }
            return [newSignal, ...prev].slice(0, 100);
          });
        } catch (err) {
          console.error('Failed to parse signal from SSE:', err);
        }
      });

      eventSource.onerror = (err) => {
        console.error('SSE error:', err);
        setIsConnected(false);
        setError('Connection lost – reconnecting...');
        
        if (eventSource) {
          eventSource.close();
        }
        
        // Reconnect after 3 seconds
        reconnectTimeout = setTimeout(connect, 3000);
      };
    };

    connect();

    return () => {
      if (eventSource) {
        eventSource.close();
      }
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout);
      }
    };
  }, [url, fetchInitialSignals]);

  return { signals, isConnected, error };
}
