import { execSync } from 'child_process';

// Mac computer control via AppleScript + shell
// Requires macOS — no-ops gracefully on other platforms

function isMac(): boolean {
  return process.platform === 'darwin';
}

export function runAppleScript(script: string): string {
  if (!isMac()) {
    console.warn('[mac-controller] AppleScript not available on this platform — skipping');
    return '';
  }
  try {
    return execSync(`osascript -e '${script.replace(/'/g, "'\\''")}' 2>&1`).toString().trim();
  } catch (err) {
    console.error('[mac-controller] AppleScript error:', err);
    return '';
  }
}

export function openUrl(url: string): void {
  if (isMac()) {
    execSync(`open "${url}"`);
  } else {
    console.warn(`[mac-controller] Would open URL: ${url}`);
  }
}

export function sendNotification(title: string, message: string): void {
  if (isMac()) {
    runAppleScript(
      `display notification "${message.replace(/"/g, '\\"')}" with title "${title.replace(/"/g, '\\"')}"`,
    );
  } else {
    console.log(`[NOTIFICATION] ${title}: ${message}`);
  }
}

export function speakText(text: string): void {
  if (isMac()) {
    runAppleScript(`say "${text.replace(/"/g, '\\"')}"`);
  } else {
    console.log(`[SPEAK] ${text}`);
  }
}
