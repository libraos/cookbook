import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// The browser talks only to this server; kernel paths are forwarded to the
// kernel, so the app and the kernel share one origin (as they would behind a
// single reverse proxy in production). That keeps sign-out's redirect back to
// the app working. See README "How it works".
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const kernel = env.LIBRA_OS_URL || "http://localhost:8900";
  // The port is part of the registered redirect_uri, so never drift from it.
  // PORT=5188 npm run dev (or PORT in .env) moves it; then register
  // personal-assistant=http://localhost:5188/callback in get-started/.env too.
  const port = Number(env.PORT) || 5180;
  const proxy = { "/oauth": kernel, "/v1": kernel, "/api": kernel };
  return {
    plugins: [react()],
    server: { port, strictPort: true, proxy },
    preview: { port, strictPort: true, proxy },
  };
});
