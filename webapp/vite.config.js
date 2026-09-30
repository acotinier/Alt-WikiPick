import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// `npm run dev` : interface sur :5173, appels /api relayés vers le serveur local (python -m server, :8000).
// `npm run dev:mock` : aucune API, données de démonstration (src/lib/mock.js).
export default defineConfig({
  plugins: [svelte()],
  server: { proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false } } },
  build: { target: 'es2022', cssCodeSplit: true, sourcemap: false, chunkSizeWarningLimit: 120 },
});
