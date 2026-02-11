import { create } from 'zustand';
import { persist } from 'zustand/middleware';

type Theme = 'light' | 'dark' | 'system';

interface SettingsState {
  theme: Theme;
  paperTrading: boolean;
  autoRefresh: boolean;
  refreshInterval: number;
  riskLimits: {
    maxPositionSize: number;
    maxDrawdown: number;
    maxDailyLoss: number;
  };

  // Actions
  setTheme: (theme: Theme) => void;
  setPaperTrading: (enabled: boolean) => void;
  setAutoRefresh: (enabled: boolean) => void;
  setRefreshInterval: (interval: number) => void;
  setRiskLimits: (limits: Partial<SettingsState['riskLimits']>) => void;
}

export const useSettingsStore = create<SettingsState>()(
  persist(
    (set) => ({
      theme: 'system',
      paperTrading: true, // Default to paper trading for safety
      autoRefresh: true,
      refreshInterval: 30000, // 30 seconds
      riskLimits: {
        maxPositionSize: 10, // 10% of portfolio per position
        maxDrawdown: 15, // 15% max drawdown
        maxDailyLoss: 5, // 5% max daily loss
      },

      setTheme: (theme) => set({ theme }),
      setPaperTrading: (paperTrading) => set({ paperTrading }),
      setAutoRefresh: (autoRefresh) => set({ autoRefresh }),
      setRefreshInterval: (refreshInterval) => set({ refreshInterval }),
      setRiskLimits: (limits) =>
        set((state) => ({
          riskLimits: { ...state.riskLimits, ...limits },
        })),
    }),
    {
      name: 'trade-nexus-settings',
    },
  ),
);
