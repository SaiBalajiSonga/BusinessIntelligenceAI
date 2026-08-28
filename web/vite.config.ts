import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // the engine runs separately; proxying keeps the app same-origin in dev
    proxy: { "/v1": { target: "http://localhost:8000", changeOrigin: true } },
  },
});
