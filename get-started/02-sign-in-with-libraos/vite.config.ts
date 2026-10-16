import { defineConfig, loadEnv } from "vite";

// The browser only ever talks to this dev server. Requests for the kernel's
// sign-in endpoints are forwarded to it, so the app and the kernel share one
// origin, exactly like a production deployment behind a single reverse proxy.
// See README "Why a proxy?".
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  const kernel = env.LIBRA_OS_URL || "http://localhost:8900";
  // Must match the redirect_uri registered for this client, port included.
  // PORT=5178 npm run dev (or PORT in .env) moves it; then register
  // signin-example=http://localhost:5178/callback in get-started/.env too.
  const port = Number(env.PORT) || 5173;
  const proxy = { "/oauth": kernel };
  return {
    server: { port, strictPort: true, proxy },
    preview: { port, strictPort: true, proxy },
  };
});
