import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [
    react(),
    {
      name: 'redirect-base',
      configureServer(server) {
        server.middlewares.use((req, _res, next) => {
          if (req.url === '/companyResearch') {
            req.url = '/companyResearch/';
          }
          next();
        });
      },
    },
  ],
  base: '/companyResearch/',
  optimizeDeps: {
    exclude: ["lucide-react"],
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
  server: {
    port: 3004,
    strictPort: true,
    host: true,
  },
});
