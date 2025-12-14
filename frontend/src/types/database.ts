export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

export interface Database {
  public: {
    Tables: {
      predictions: {
        Row: {
          id: string;
          user_id: string;
          symbol: string;
          prediction_type: string;
          value: Json;
          confidence: number;
          created_at: string;
        };
        Insert: {
          id?: string;
          user_id: string;
          symbol: string;
          prediction_type: string;
          value: Json;
          confidence: number;
          created_at?: string;
        };
        Update: {
          id?: string;
          user_id?: string;
          symbol?: string;
          prediction_type?: string;
          value?: Json;
          confidence?: number;
          created_at?: string;
        };
      };
      agent_runs: {
        Row: {
          id: string;
          user_id: string;
          agent_type: string;
          input: Json;
          output: Json | null;
          status: string;
          created_at: string;
          completed_at: string | null;
        };
        Insert: {
          id?: string;
          user_id: string;
          agent_type: string;
          input: Json;
          output?: Json | null;
          status?: string;
          created_at?: string;
          completed_at?: string | null;
        };
        Update: {
          id?: string;
          user_id?: string;
          agent_type?: string;
          input?: Json;
          output?: Json | null;
          status?: string;
          created_at?: string;
          completed_at?: string | null;
        };
      };
      strategies: {
        Row: {
          id: string;
          user_id: string;
          name: string;
          code: string;
          backtest_results: Json | null;
          is_active: boolean;
          created_at: string;
        };
        Insert: {
          id?: string;
          user_id: string;
          name: string;
          code: string;
          backtest_results?: Json | null;
          is_active?: boolean;
          created_at?: string;
        };
        Update: {
          id?: string;
          user_id?: string;
          name?: string;
          code?: string;
          backtest_results?: Json | null;
          is_active?: boolean;
          created_at?: string;
        };
      };
    };
    Views: Record<string, never>;
    Functions: Record<string, never>;
    Enums: Record<string, never>;
  };
}
