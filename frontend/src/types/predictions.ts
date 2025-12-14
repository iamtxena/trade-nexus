export type PredictionType = 'price' | 'volatility' | 'sentiment' | 'trend';

export interface Prediction {
  id: string;
  userId: string;
  symbol: string;
  predictionType: PredictionType;
  value: PredictionValue;
  confidence: number;
  createdAt: string;
}

export interface PredictionValue {
  predicted: number;
  upper?: number;
  lower?: number;
  timeframe: string;
  features?: Record<string, number>;
}

export interface PredictionRequest {
  symbol: string;
  predictionType: PredictionType;
  timeframe: string;
  features?: Record<string, number>;
}

export interface PricePrediction extends Prediction {
  predictionType: 'price';
  value: {
    predicted: number;
    upper: number;
    lower: number;
    timeframe: string;
  };
}

export interface VolatilityPrediction extends Prediction {
  predictionType: 'volatility';
  value: {
    predicted: number;
    timeframe: string;
    historicalAvg: number;
  };
}

export interface SentimentPrediction extends Prediction {
  predictionType: 'sentiment';
  value: {
    predicted: number;
    timeframe: string;
    sources: {
      news: number;
      social: number;
      onchain?: number;
    };
  };
}

export interface TrendPrediction extends Prediction {
  predictionType: 'trend';
  value: {
    predicted: number;
    timeframe: string;
    direction: 'bullish' | 'bearish' | 'neutral';
    strength: number;
  };
}
