import { Dropbox, type files } from 'dropbox';
import { env } from '../config/env.js';

let client: Dropbox | undefined;

/**
 * Returns a shared Dropbox SDK client. Prefers a long-lived access token;
 * falls back to the app-key/secret + refresh-token flow so the token can be
 * rotated without redeploying. Throws with a clear message if neither is
 * configured — callers should check env.missingCredentialsFor('dropbox')
 * first if they want to fail a single agent run instead of the process.
 */
export function getDropboxClient(): Dropbox {
  if (client) return client;

  const accessToken = env.dropbox.accessToken();
  const refreshToken = env.dropbox.refreshToken();
  const appKey = env.dropbox.appKey();
  const appSecret = env.dropbox.appSecret();

  if (accessToken) {
    client = new Dropbox({ accessToken });
  } else if (refreshToken && appKey && appSecret) {
    client = new Dropbox({ refreshToken, clientId: appKey, clientSecret: appSecret });
  } else {
    throw new Error(
      'Dropbox is not configured. Set DROPBOX_ACCESS_TOKEN, or DROPBOX_REFRESH_TOKEN + DROPBOX_APP_KEY + DROPBOX_APP_SECRET.',
    );
  }
  return client;
}

export interface DropboxEntryInfo {
  path: string;
  name: string;
  rev?: string;
  contentHash?: string;
  size?: number;
}

/** Lists files (non-recursive by default) directly under a Dropbox folder path. */
export async function listFolder(folderPath: string, recursive = false): Promise<DropboxEntryInfo[]> {
  const dbx = getDropboxClient();
  const entries: DropboxEntryInfo[] = [];

  let response = await dbx.filesListFolder({ path: folderPath, recursive });
  for (;;) {
    for (const entry of response.result.entries) {
      if (entry['.tag'] === 'file') {
        const file = entry as files.FileMetadataReference;
        entries.push({
          path: file.path_lower ?? file.path_display ?? `${folderPath}/${file.name}`,
          name: file.name,
          rev: file.rev,
          contentHash: file.content_hash,
          size: file.size,
        });
      }
    }
    if (!response.result.has_more) break;
    response = await dbx.filesListFolderContinue({ cursor: response.result.cursor });
  }
  return entries;
}

/** Ensures a folder exists (no-op if it's already there). */
export async function ensureFolder(folderPath: string): Promise<void> {
  const dbx = getDropboxClient();
  try {
    await dbx.filesCreateFolderV2({ path: folderPath });
  } catch (err) {
    const summary = (err as { error?: { error_summary?: string } })?.error?.error_summary ?? '';
    if (!summary.includes('path/conflict')) throw err;
  }
}

/** Downloads a file's binary content as a Buffer. */
export async function downloadFile(path: string): Promise<Buffer> {
  const dbx = getDropboxClient();
  const response = await dbx.filesDownload({ path });
  const result = response.result as files.FileMetadata & { fileBinary?: Buffer; fileBlob?: Blob };
  if (result.fileBinary) return result.fileBinary;
  if (result.fileBlob) return Buffer.from(await result.fileBlob.arrayBuffer());
  throw new Error(`Dropbox download for ${path} returned no binary content`);
}

/** Uploads a small-to-medium file (<150MB), overwriting any existing file at the path. */
export async function uploadFile(path: string, content: Buffer): Promise<void> {
  const dbx = getDropboxClient();
  await dbx.filesUpload({ path, contents: content, mode: { '.tag': 'overwrite' }, mute: true });
}
