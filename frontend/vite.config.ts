import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: "0.0.0.0",
    port: 7173,
    proxy: {
      "/api": {
        target: "http://localhost:7273",
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: "dist",
  },
});
