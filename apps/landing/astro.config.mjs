import { defineConfig } from 'astro/config';
import react from '@astrojs/react';
import { fileURLToPath, URL } from 'node:url';

// The @saleha/* workspace packages are consumed straight from their
// TypeScript sources rather than a built dist/, so Vite has to be told
// how to resolve them -- the same aliasing apps/desktop's vite.config.ts
// already does.
export default defineConfig({
  integrations: [react()],
  output: 'static',
  vite: {
    resolve: {
      alias: {
        '@saleha/core': fileURLToPath(new URL('../../packages/core/src/index.ts', import.meta.url)),
        '@saleha/ui': fileURLToPath(new URL('../../packages/ui/src/index.ts', import.meta.url)),
      },
    },
  },
});

