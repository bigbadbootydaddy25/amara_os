import fs from 'fs';
import path from 'path';
import type { Buyer, Property } from '@/types/real-estate';

const DATA_DIR = path.join(process.cwd(), '.amara-data');

function ensureDir() {
  if (!fs.existsSync(DATA_DIR)) {
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
}

function readJson<T>(file: string, fallback: T): T {
  ensureDir();
  const filePath = path.join(DATA_DIR, file);
  if (!fs.existsSync(filePath)) return fallback;
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf-8')) as T;
  } catch {
    return fallback;
  }
}

function writeJson<T>(file: string, data: T): void {
  ensureDir();
  fs.writeFileSync(path.join(DATA_DIR, file), JSON.stringify(data, null, 2), 'utf-8');
}

// ── Buyers ──────────────────────────────────────────────────

export function getBuyers(): Buyer[] {
  return readJson<Buyer[]>('buyers.json', []);
}

export function saveBuyers(buyers: Buyer[]): void {
  writeJson('buyers.json', buyers);
}

export function upsertBuyer(buyer: Buyer): void {
  const buyers = getBuyers();
  const idx = buyers.findIndex((b) => b.id === buyer.id);
  if (idx >= 0) {
    buyers[idx] = buyer;
  } else {
    buyers.push(buyer);
  }
  saveBuyers(buyers);
}

export function deleteBuyer(id: string): void {
  saveBuyers(getBuyers().filter((b) => b.id !== id));
}

// ── Properties ──────────────────────────────────────────────

export function getProperties(): Property[] {
  return readJson<Property[]>('properties.json', []);
}

export function saveProperties(properties: Property[]): void {
  writeJson('properties.json', properties);
}

export function upsertProperty(property: Property): void {
  const properties = getProperties();
  const idx = properties.findIndex((p) => p.id === property.id);
  if (idx >= 0) {
    properties[idx] = property;
  } else {
    properties.push(property);
  }
  saveProperties(properties);
}

export function deleteProperty(id: string): void {
  saveProperties(getProperties().filter((p) => p.id !== id));
}

export function getPropertyById(id: string): Property | undefined {
  return getProperties().find((p) => p.id === id);
}
