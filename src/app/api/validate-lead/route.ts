import { NextRequest, NextResponse } from 'next/server';
import { validateLead } from '@/lib/lead-validator';
import type { ValidateLeadRequestBody } from '@/types';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as Partial<ValidateLeadRequestBody>;

    if (!body.lead || typeof body.lead !== 'object') {
      return NextResponse.json(
        { error: 'Request body must contain a "lead" object' },
        { status: 400 },
      );
    }

    const result = validateLead(body.lead);

    return NextResponse.json(result, { status: result.valid ? 200 : 422 });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Lead validation failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
