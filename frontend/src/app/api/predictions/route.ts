import { NextRequest, NextResponse } from 'next/server';
import { auth } from '@clerk/nextjs/server';
import { createServiceRoleClient } from '@/lib/supabase/server';

import type { Json } from '@/types/database';
import type { Prediction, PredictionType } from '@/types/predictions';

type PredictionRow = {
  id: string;
  user_id: string;
  symbol: string;
  prediction_type: string;
  value: unknown;
  confidence: number;
  created_at: string;
};

const VALID_PREDICTION_TYPES: PredictionType[] = ['price', 'volatility', 'sentiment', 'trend'];

function toPrediction(row: PredictionRow): Prediction {
  return {
    id: row.id,
    userId: row.user_id,
    symbol: row.symbol,
    predictionType: row.prediction_type as Prediction['predictionType'],
    value: row.value as Prediction['value'],
    confidence: row.confidence,
    createdAt: row.created_at,
  };
}

export async function GET(request: NextRequest) {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { searchParams } = new URL(request.url);
    const symbol = searchParams.get('symbol');

    const supabase = await createServiceRoleClient();
    let query = supabase
      .from('predictions')
      .select('*')
      .eq('user_id', userId)
      .order('created_at', { ascending: false });

    if (symbol) {
      query = query.eq('symbol', symbol);
    }

    const { data, error } = await query;

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json((data as PredictionRow[]).map(toPrediction));
  } catch (error) {
    console.error('Predictions GET error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 },
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const body = await request.json();

    if (!body.symbol || typeof body.symbol !== 'string') {
      return NextResponse.json({ error: 'symbol is required' }, { status: 400 });
    }
    if (!body.predictionType || !VALID_PREDICTION_TYPES.includes(body.predictionType)) {
      return NextResponse.json(
        { error: `predictionType must be one of: ${VALID_PREDICTION_TYPES.join(', ')}` },
        { status: 400 },
      );
    }
    if (!body.timeframe || typeof body.timeframe !== 'string') {
      return NextResponse.json({ error: 'timeframe is required' }, { status: 400 });
    }

    const value: Json = {
      predicted: 0,
      timeframe: body.timeframe as string,
      ...(body.features ? { features: body.features } : {}),
    };

    const supabase = await createServiceRoleClient();
    const { data, error } = await supabase
      .from('predictions')
      .insert({
        user_id: userId,
        symbol: body.symbol as string,
        prediction_type: body.predictionType as string,
        value,
        confidence: 0,
      })
      .select()
      .single();

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json(toPrediction(data as PredictionRow));
  } catch (error) {
    console.error('Predictions POST error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 },
    );
  }
}
