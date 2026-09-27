import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const kernel = env.LIBRAOS_URL || "http://localhost:8900";
  const proxy = { "/oauth": kernel, "/agents": kernel, "/api": kernel };
  return {
    plugins: [react()],
    server: { port: 5181, strictPort: true, proxy },
    preview: { port: 5181, strictPort: true, proxy },
  };
});
