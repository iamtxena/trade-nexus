import { NextRequest, NextResponse } from 'next/server';
import { auth } from '@clerk/nextjs/server';
import { createServiceRoleClient } from '@/lib/supabase/server';

import type { Json } from '@/types/database';
import type { Strategy } from '@/types/strategies';

type StrategyRow = {
  id: string;
  user_id: string;
  name: string;
  code: string;
  backtest_results: unknown;
  is_active: boolean;
  created_at: string;
};

function toStrategy(row: StrategyRow): Strategy {
  return {
    id: row.id,
    userId: row.user_id,
    name: row.name,
    code: row.code,
    backtestResults: row.backtest_results as Strategy['backtestResults'],
    isActive: row.is_active,
    createdAt: row.created_at,
  };
}

export async function GET() {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const supabase = await createServiceRoleClient();
    const { data, error } = await supabase
      .from('strategies')
      .select('*')
      .eq('user_id', userId)
      .order('created_at', { ascending: false });

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json((data as StrategyRow[]).map(toStrategy));
  } catch (error) {
    console.error('Strategies GET error:', error);
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

    if (!body.name || typeof body.name !== 'string') {
      return NextResponse.json({ error: 'name is required' }, { status: 400 });
    }
    if (!body.code || typeof body.code !== 'string') {
      return NextResponse.json({ error: 'code is required' }, { status: 400 });
    }

    const supabase = await createServiceRoleClient();
    const { data, error } = await supabase
      .from('strategies')
      .insert({
        user_id: userId,
        name: body.name as string,
        code: body.code as string,
        backtest_results: (body.backtestResults ?? null) as Json | null,
        is_active: (body.isActive ?? false) as boolean,
      })
      .select()
      .single();

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json(toStrategy(data as StrategyRow));
  } catch (error) {
    console.error('Strategies POST error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 },
    );
  }
}
