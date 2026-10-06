import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const kernel = env.LIBRAOS_URL || "http://localhost:8900";
  const proxy = { "/oauth": kernel, "/agents": kernel, "/api": kernel };
  return {
    plugins: [react()],
    // The console imports the shared mission client from ../../shared.
    server: { port: 5182, strictPort: true, proxy, fs: { allow: ["../.."] } },
    preview: { port: 5182, strictPort: true, proxy },
  };
});
