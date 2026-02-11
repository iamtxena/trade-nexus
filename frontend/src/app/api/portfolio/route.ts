import { auth } from '@clerk/nextjs/server';
import { NextResponse } from 'next/server';

import type { PortfolioSummary } from '@/hooks/use-portfolio';

export async function GET() {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const portfolio: PortfolioSummary = {
      totalValue: 100000,
      availableBalance: 100000,
      unrealizedPnl: 0,
      unrealizedPnlPercent: 0,
      holdings: [],
    };

    return NextResponse.json(portfolio);
  } catch (error) {
    console.error('Portfolio GET error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 },
    );
  }
}
