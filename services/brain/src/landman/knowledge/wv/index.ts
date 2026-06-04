// WV Knowledge Index — Texhoma Namespace Only
// Hard wall: this namespace never bleeds to amara_core, eqt, or 1890

export * from './wv-counties.js';
export * from './wv-mineral-law.js';
export * from './wv-title-standards.js';

export const WV_NAMESPACE_GUARD = {
  namespace:         'texhoma',
  owner:             'texhoma_only',
  contract:          '52446',
  bleedProtection:   true,
  allowedNamespaces: ['texhoma'],
  blockedNamespaces: ['amara_core', 'eqt', '1890'],
  installedDate:     new Date().toISOString(),
} as const;
