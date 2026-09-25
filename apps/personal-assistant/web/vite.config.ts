import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// The browser talks only to this server; kernel paths are forwarded to the
// kernel, so the app and the kernel share one origin (as they would behind a
// single reverse proxy in production). That keeps sign-out's redirect back to
// the app working. See README "How it works".
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const kernel = env.LIBRAOS_URL || "http://localhost:8900";
  const proxy = { "/oauth": kernel, "/v1": kernel, "/api": kernel };
  return {
    plugins: [react()],
    // The port is part of the registered redirect_uri, so never drift from it.
    server: { port: 5180, strictPort: true, proxy },
    preview: { port: 5180, strictPort: true, proxy },
  };
});
