import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { completeSignIn } from "./auth";
import "./styles.css";

// The kernel sends the browser back to /callback?code=… after sign-in.
// Finish that exchange before rendering anything.
async function boot() {
  const url = new URL(location.href);
  let error: string | null = null;
  if (url.pathname === "/callback") {
    try {
      if (url.searchParams.has("error")) throw new Error(`Sign-in refused: ${url.searchParams.get("error")}`);
      await completeSignIn(url);
    } catch (e) {
      error = (e as Error).message;
    }
    history.replaceState(null, "", "/");
  }
  createRoot(document.getElementById("root")!).render(
    <StrictMode>
      <App initialError={error} />
    </StrictMode>,
  );
}
boot();
