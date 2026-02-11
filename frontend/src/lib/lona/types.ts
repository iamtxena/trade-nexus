export interface LonaRegistrationResponse {
  token: string;
  partner_id: string;
  partner_name: string;
  permissions: string[];
  expires_at: string;
}

export interface LonaStrategyFromDescriptionResponse {
  strategyId: string;
  name: string;
  code: string;
  explanation: string;
}

export interface LonaStrategy {
  id: string;
  name: string;
  description: string;
  version: string;
  version_id: string;
  language: string;
  code: string;
  user_id: string;
  created_at: string;
  updated_at: string;
}

export interface LonaSymbol {
  id: string;
  name: string;
  description: string;
  is_global: boolean;
  data_range: {
    start_timestamp: string | null;
    end_timestamp: string | null;
  } | null;
  frequencies: string[];
  type_metadata: {
    data_type: string;
    exchange: string | null;
    asset_class: string | null;
    quote_currency: string | null;
    column_mapping: Record<string, string | null>;
  } | null;
  created_at: string;
  updated_at: string;
}

export interface LonaBacktestRequest {
  strategy_id: string;
  data_ids: string[];
  start_date: string;
  end_date: string;
  parameters?: Record<string, unknown>[] | null;
  simulation_parameters: {
    initial_cash: number;
    commission_schema: { commission: number; leverage: number };
    buy_on_close: boolean;
  };
}

export interface LonaBacktestResponse {
  report_id: string;
}

export type LonaReportStatusValue = 'PENDING' | 'EXECUTING' | 'PROCESSING' | 'COMPLETED' | 'FAILED';

export interface LonaReportStatus {
  status: LonaReportStatusValue;
  progress: number | null;
}

export interface LonaReport {
  id: string;
  strategy_id: string;
  status: string;
  name: string;
  description: string;
  created_at: string;
  updated_at: string;
  total_stats: Record<string, unknown> | null;
  error: string | null;
}
