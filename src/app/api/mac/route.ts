import { NextRequest, NextResponse } from 'next/server';
import { execFile } from 'child_process';
import { promisify } from 'util';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const execFileAsync = promisify(execFile);

// Each entry is a function that builds a safe AppleScript string from validated params.
// Input sanitisation: only alphanumerics, spaces, dots, slashes, hyphens, underscores allowed.
const SAFE_PATTERN = /^[\w\s.\-/]+$/;

function sanitise(value: string): string {
  if (!SAFE_PATTERN.test(value)) {
    throw new Error(`Unsafe characters in parameter: "${value}"`);
  }
  return value.replace(/"/g, '\\"');
}

type ActionBuilder = (params: Record<string, string>) => string;

const ACTION_SCRIPTS: Record<string, ActionBuilder> = {
  open_app: ({ app }) =>
    `tell application "${sanitise(app)}" to activate`,

  quit_app: ({ app }) =>
    `tell application "${sanitise(app)}" to quit`,

  open_url: ({ url }) => {
    if (!/^https?:\/\/[\w\-./]+$/.test(url)) throw new Error('Invalid URL');
    return `open location "${url}"`;
  },

  type_text: ({ text }) => {
    const safe = text.replace(/[^a-zA-Z0-9 .,!?'-]/g, '');
    return (
      `tell application "System Events" to keystroke "${safe.replace(/"/g, '\\"')}"`
    );
  },

  press_key: ({ key }) => {
    const allowedKeys = ['return', 'tab', 'escape', 'space', 'delete', 'left', 'right', 'up', 'down'];
    if (!allowedKeys.includes(key.toLowerCase())) throw new Error(`Key not allowed: ${key}`);
    return `tell application "System Events" to key code "${sanitise(key)}"`;
  },

  take_screenshot: () =>
    `do shell script "screencapture -x /tmp/amara_screenshot.png"`,

  show_notification: ({ title, message }) =>
    `display notification "${sanitise(message)}" with title "${sanitise(title)}"`,

  get_frontmost_app: () =>
    `tell application "System Events" to get name of first application process whose frontmost is true`,

  set_volume: ({ level }) => {
    const vol = parseInt(level, 10);
    if (isNaN(vol) || vol < 0 || vol > 100) throw new Error('Volume must be 0–100');
    return `set volume output volume ${vol}`;
  },
};

interface MacRequestBody {
  action: string;
  params?: Record<string, string>;
}

function isEnabled(): boolean {
  return process.env.ENABLE_MAC_AUTOMATION === 'true';
}

function isAuthorised(request: NextRequest): boolean {
  const secret = process.env.MAC_AUTOMATION_SECRET?.trim();
  if (!secret) return false;
  return request.headers.get('x-mac-secret') === secret;
}

export async function POST(request: NextRequest) {
  if (!isEnabled()) {
    return NextResponse.json({ error: 'Mac automation is not enabled' }, { status: 403 });
  }

  if (!isAuthorised(request)) {
    return NextResponse.json({ error: 'Unauthorised' }, { status: 401 });
  }

  try {
    const body = (await request.json()) as Partial<MacRequestBody>;
    const action = body.action?.trim();

    if (!action) {
      return NextResponse.json({ error: 'No action provided' }, { status: 400 });
    }

    const builder = ACTION_SCRIPTS[action];
    if (!builder) {
      return NextResponse.json(
        { error: `Unknown action "${action}". Allowed: ${Object.keys(ACTION_SCRIPTS).join(', ')}` },
        { status: 400 },
      );
    }

    const params = body.params ?? {};
    const script = builder(params);

    const { stdout } = await execFileAsync('/usr/bin/osascript', ['-e', script], {
      timeout: 10_000,
    });

    return NextResponse.json({ ok: true, result: stdout.trim() });
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Mac automation failed';
    return NextResponse.json({ error: message }, { status: 500 });
  }
}
