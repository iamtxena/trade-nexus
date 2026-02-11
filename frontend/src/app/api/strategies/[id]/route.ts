import { createServiceRoleClient } from '@/lib/supabase/server';
import { auth } from '@clerk/nextjs/server';
import { type NextRequest, NextResponse } from 'next/server';

import type { Database } from '@/types/database';
import type { Strategy } from '@/types/strategies';

type StrategyUpdate = Database['public']['Tables']['strategies']['Update'];

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

export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { id } = await params;
    const supabase = await createServiceRoleClient();
    const { data, error } = await supabase
      .from('strategies')
      .select('*')
      .eq('id', id)
      .eq('user_id', userId)
      .single();

    if (error) {
      const status = error.code === 'PGRST116' ? 404 : 500;
      return NextResponse.json({ error: error.message }, { status });
    }

    return NextResponse.json(toStrategy(data as StrategyRow));
  } catch (error) {
    console.error('Strategy GET error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 },
    );
  }
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { id } = await params;
    const body = await request.json();

    const updates: StrategyUpdate = {};
    if (body.name !== undefined) updates.name = body.name;
    if (body.code !== undefined) updates.code = body.code;
    if (body.backtestResults !== undefined) updates.backtest_results = body.backtestResults;
    if (body.isActive !== undefined) updates.is_active = body.isActive;

    if (Object.keys(updates).length === 0) {
      return NextResponse.json({ error: 'No valid fields to update' }, { status: 400 });
    }

    const supabase = await createServiceRoleClient();
    const { data, error } = await supabase
      .from('strategies')
      .update(updates)
      .eq('id', id)
      .eq('user_id', userId)
      .select()
      .single();

    if (error) {
      const status = error.code === 'PGRST116' ? 404 : 500;
      return NextResponse.json({ error: error.message }, { status });
    }

    return NextResponse.json(toStrategy(data as StrategyRow));
  } catch (error) {
    console.error('Strategy PATCH error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 },
    );
  }
}

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  try {
    const { userId } = await auth();
    if (!userId) {
      return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
    }

    const { id } = await params;
    const supabase = await createServiceRoleClient();
    const { error } = await supabase.from('strategies').delete().eq('id', id).eq('user_id', userId);

    if (error) {
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return new NextResponse(null, { status: 204 });
  } catch (error) {
    console.error('Strategy DELETE error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Internal server error' },
      { status: 500 },
    );
  }
}
