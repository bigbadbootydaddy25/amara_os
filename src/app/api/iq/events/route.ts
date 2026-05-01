import { NextRequest } from 'next/server';
import { subscribeToIQEvents, getCurrentIQ } from '@/lib/iq/iq-engine';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

// SSE endpoint — frontend subscribes here for real-time IQ events
export async function GET(_request: NextRequest) {
  const encoder = new TextEncoder();
  let unsubscribe: (() => void) | null = null;

  const stream = new ReadableStream({
    async start(controller) {
      const currentIQ = await getCurrentIQ();
      // Send current IQ immediately on connect
      controller.enqueue(encoder.encode(`data: ${JSON.stringify({ type: 'IQ_CURRENT', iq: currentIQ })}\n\n`));

      unsubscribe = subscribeToIQEvents((payload) => {
        try {
          controller.enqueue(encoder.encode(payload));
        } catch {
          unsubscribe?.();
        }
      });
    },
    cancel() {
      unsubscribe?.();
    },
  });

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
}
