import type { PortalDriver } from '../types.js';
import { texasFileDriver } from './texasfile.js';

const registry: Record<string, PortalDriver> = {
  texasfile: texasFileDriver,
  // Add a county-clerk-direct driver here (same PortalDriver shape) and
  // point PORTAL_NAME at its key to search a clerk's own records site
  // instead of TexasFile.
};

export function getPortalDriver(name: string): PortalDriver {
  const driver = registry[name];
  if (!driver) {
    throw new Error(`Unknown PORTAL_NAME "${name}". Known portals: ${Object.keys(registry).join(', ')}`);
  }
  return driver;
}
