import 'dotenv/config';

function optional(name: string): string | undefined {
  const value = process.env[name];
  return value && value.trim().length > 0 ? value.trim() : undefined;
}

function required(name: string): string {
  const value = optional(name);
  if (!value) {
    throw new Error(
      `Missing required environment variable: ${name}. Copy .env.example to .env and fill it in.`,
    );
  }
  return value;
}

export const env = {
  databaseUrl: () => required('DATABASE_URL'),

  dropbox: {
    accessToken: () => optional('DROPBOX_ACCESS_TOKEN'),
    refreshToken: () => optional('DROPBOX_REFRESH_TOKEN'),
    appKey: () => optional('DROPBOX_APP_KEY'),
    appSecret: () => optional('DROPBOX_APP_SECRET'),
    sellerPackageRoot: () => optional('DROPBOX_SELLER_PACKAGE_ROOT') ?? '/Title Runsheet/Seller Packages',
    recordedInstrumentsRoot: () =>
      optional('DROPBOX_RECORDED_INSTRUMENTS_ROOT') ?? '/Title Runsheet/Recorded Instruments',
    runsheetExportRoot: () => optional('DROPBOX_RUNSHEET_EXPORT_ROOT') ?? '/Title Runsheet/Runsheets',
    reportExportRoot: () => optional('DROPBOX_REPORT_EXPORT_ROOT') ?? '/Title Runsheet/Reports',
  },

  portal: {
    name: () => optional('PORTAL_NAME') ?? 'texasfile',
    baseUrl: () => optional('PORTAL_BASE_URL') ?? 'https://www.texasfile.com',
    username: () => optional('PORTAL_USERNAME'),
    password: () => optional('PORTAL_PASSWORD'),
    headless: () => (optional('PORTAL_HEADLESS') ?? 'true').toLowerCase() !== 'false',
  },

  defaultTract: {
    state: () => optional('DEFAULT_STATE') ?? 'TX',
    county: () => optional('DEFAULT_COUNTY') ?? 'Howard',
    section: () => optional('DEFAULT_SURVEY_SECTION') ?? '47',
    block: () => optional('DEFAULT_SURVEY_BLOCK') ?? '33',
    township: () => optional('DEFAULT_SURVEY_TOWNSHIP') ?? 'T1S',
  },
};

/**
 * Checks that credentials needed for a given agent are present, without
 * throwing — used to fail a single agent run with a clear message instead of
 * crashing the whole pipeline at import time.
 */
export function missingCredentialsFor(agent: 'dropbox' | 'portal' | 'database'): string[] {
  const missing: string[] = [];
  if (agent === 'database' && !optional('DATABASE_URL')) missing.push('DATABASE_URL');
  if (agent === 'dropbox' && !optional('DROPBOX_ACCESS_TOKEN') && !optional('DROPBOX_REFRESH_TOKEN')) {
    missing.push('DROPBOX_ACCESS_TOKEN or DROPBOX_REFRESH_TOKEN');
  }
  if (agent === 'portal') {
    if (!optional('PORTAL_USERNAME')) missing.push('PORTAL_USERNAME');
    if (!optional('PORTAL_PASSWORD')) missing.push('PORTAL_PASSWORD');
  }
  return missing;
}
