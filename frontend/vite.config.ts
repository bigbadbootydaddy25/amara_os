import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/parcels":   { target: "http://localhost:3001", changeOrigin: true },
      "/assistant": { target: "http://localhost:3001", changeOrigin: true },
      "/amara":     { target: "http://localhost:3001", changeOrigin: true },
      "/pipeline":  { target: "http://localhost:3001", changeOrigin: true },
      "/health":    { target: "http://localhost:3001", changeOrigin: true },
    },
  },
});
