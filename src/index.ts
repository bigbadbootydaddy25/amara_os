/**
 * Buyer Intelligence Engine — Entry Point
 */

import 'dotenv/config';
import express from 'express';
import { router } from './api/routes';

const app = express();
const PORT = process.env['PORT'] ? parseInt(process.env['PORT'], 10) : 3000;

app.use(express.json());

// Health check
app.get('/health', (_req, res) => {
  res.json({ status: 'ok', service: 'buyer-intelligence-engine', ts: new Date().toISOString() });
});

app.use('/api/v1', router);

// Global error handler
app.use((err: Error, _req: express.Request, res: express.Response, _next: express.NextFunction) => {
  console.error('[error]', err.message, err.stack);
  res.status(500).json({ error: 'Internal server error' });
});

app.listen(PORT, () => {
  console.log(`[buyer-intelligence-engine] listening on :${PORT}`);
});

export default app;
