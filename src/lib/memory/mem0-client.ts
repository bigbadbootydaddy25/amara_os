import MemoryClient from 'mem0ai';

let client: MemoryClient | null = null;

const USER_ID = 'scott_schufford';

export function getMemoryClient(): MemoryClient | null {
  const apiKey = process.env.MEM0_API_KEY?.trim();
  if (!apiKey) return null;

  if (!client) {
    client = new MemoryClient({ apiKey });
  }
  return client;
}

export { USER_ID };
