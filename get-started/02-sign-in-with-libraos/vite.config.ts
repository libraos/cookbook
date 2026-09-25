import { defineConfig, loadEnv } from "vite";

// The browser only ever talks to this dev server. Requests for the kernel's
// sign-in endpoints are forwarded to it, so the app and the kernel share one
// origin, exactly like a production deployment behind a single reverse proxy.
// See README "Why a proxy?".
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const kernel = env.LIBRAOS_URL || "http://localhost:8900";
  const proxy = { "/oauth": kernel };
  return {
    // Must match the redirect_uri registered for this client, port included.
    server: { port: 5173, strictPort: true, proxy },
    preview: { port: 5173, strictPort: true, proxy },
  };
});
