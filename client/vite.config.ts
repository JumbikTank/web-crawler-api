import { defineConfig } from "vite";
import { tanstackStart } from "@tanstack/react-start/plugin/vite";
import react from "@vitejs/plugin-react";
import { nitro } from "nitro/vite";

export default defineConfig({
  server: { port: Number(process.env.CLIENT_PORT || 3000), strictPort: true },
  plugins: [tanstackStart(), nitro(), react()],
});
