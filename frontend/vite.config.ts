import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/health": "http://localhost:8001",
      "/settings": "http://localhost:8001",
      "/vocab": "http://localhost:8001",
      "/sessions": "http://localhost:8001",
      "/transcripts": "http://localhost:8001",
      "/audio": "http://localhost:8001",
      "/search": "http://localhost:8001",
      "/upload": "http://localhost:8001",
      "/transcribe": "http://localhost:8001",
      "/embed": "http://localhost:8001",
      "/summarize": "http://localhost:8001"
    }
  }
});
