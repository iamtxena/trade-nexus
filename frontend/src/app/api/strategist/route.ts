import { type NextRequest, NextResponse } from 'next/server';
import { auth } from '@clerk/nextjs/server';

import { streamStrategist } from '@/lib/ai/strategist';

export async function POST(request: NextRequest) {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const body = await request.json();

    const assetClasses = Array.isArray(body.assetClasses) ? body.assetClasses : undefined;
    const capital = typeof body.capital === 'number' && body.capital > 0 ? body.capital : undefined;
    const maxPositionPct =
      typeof body.maxPositionPct === 'number' && body.maxPositionPct > 0 && body.maxPositionPct <= 100
        ? body.maxPositionPct
        : undefined;
    const maxDrawdownPct =
      typeof body.maxDrawdownPct === 'number' && body.maxDrawdownPct > 0 && body.maxDrawdownPct <= 100
        ? body.maxDrawdownPct
        : undefined;

    const result = streamStrategist({ assetClasses, capital, maxPositionPct, maxDrawdownPct });
    return result.toTextStreamResponse();
  } catch (error) {
    console.error('Strategist API error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 },
    );
  }
}
