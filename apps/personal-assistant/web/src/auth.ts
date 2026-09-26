// Sign in with LibraOS (OIDC Authorization Code + PKCE). The step-by-step
// version with explanations is get-started/02-sign-in-with-libraos; this file
// adds what a longer-lived app needs: refresh tokens and a fetch wrapper.

const CLIENT_ID = import.meta.env.VITE_LIBRAOS_CLIENT_ID ?? "personal-assistant";
const REDIRECT_URI = `${location.origin}/callback`;

type Tokens = { access_token: string; refresh_token?: string };

// Tokens live in sessionStorage: they survive a reload but not closing the tab.
const load = (): Tokens | null => JSON.parse(sessionStorage.getItem("tokens") ?? "null");
const save = (t: Tokens | null) =>
  t ? sessionStorage.setItem("tokens", JSON.stringify(t)) : sessionStorage.removeItem("tokens");

export const isSignedIn = () => load() !== null;

const base64url = (b: Uint8Array) =>
  btoa(String.fromCharCode(...b)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const random = (n = 32) => base64url(crypto.getRandomValues(new Uint8Array(n)));

export async function signIn(): Promise<void> {
  const verifier = random(), state = random(16);
  sessionStorage.setItem("pkce", JSON.stringify({ verifier, state }));
  const challenge = base64url(new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier))));
  const params = new URLSearchParams({
    client_id: CLIENT_ID, redirect_uri: REDIRECT_URI, response_type: "code", state,
    // offline_access asks for a refresh token, so the app outlives the
    // one-hour access token without sending the user back to sign in.
    scope: "openid profile email offline_access",
    code_challenge: challenge, code_challenge_method: "S256",
  });
  location.assign(`/oauth/authorize?${params}`);
}

export async function completeSignIn(url: URL): Promise<void> {
  const saved = JSON.parse(sessionStorage.getItem("pkce") ?? "null");
  sessionStorage.removeItem("pkce");
  const code = url.searchParams.get("code");
  if (!saved || !code || url.searchParams.get("state") !== saved.state) throw new Error("Sign-in response did not match this tab. Try again.");
  save(await tokenRequest({ grant_type: "authorization_code", code, client_id: CLIENT_ID, redirect_uri: REDIRECT_URI, code_verifier: saved.verifier }));
}

async function tokenRequest(form: Record<string, string>): Promise<Tokens> {
  const res = await fetch("/oauth/token", { method: "POST", body: new URLSearchParams(form) });
  const body = await res.json();
  if (!res.ok) throw new Error(`Sign-in failed: ${body.error ?? res.status}`);
  return body;
}

// Refresh tokens rotate: each one works once. Several requests can hit a 401
// together, so they share one refresh instead of burning the token in a race.
let refreshing: Promise<boolean> | null = null;
function refresh(): Promise<boolean> {
  refreshing ??= (async () => {
    const rt = load()?.refresh_token;
    if (!rt) return false;
    try {
      save(await tokenRequest({ grant_type: "refresh_token", refresh_token: rt, client_id: CLIENT_ID }));
      return true;
    } catch {
      save(null);
      return false;
    }
  })().finally(() => (refreshing = null));
  return refreshing;
}

export class SignedOut extends Error {}

// fetch() with the user's bearer token, refreshing it once on a 401.
export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const attempt = () =>
    fetch(path, { ...init, headers: { ...init.headers, Authorization: `Bearer ${load()?.access_token}` } });
  let res = await attempt();
  if (res.status === 401 && (await refresh())) res = await attempt();
  if (res.status === 401) {
    save(null);
    throw new SignedOut();
  }
  return res;
}

export async function signOut(): Promise<void> {
  const rt = load()?.refresh_token;
  save(null);
  // Revoke the refresh token, then end the kernel's sign-in session (a
  // cookie only the kernel can clear) and come back to the app.
  if (rt) await fetch("/oauth/revoke", { method: "POST", body: new URLSearchParams({ token: rt }) }).catch(() => {});
  location.assign("/oauth/logout?post_logout_redirect_uri=/");
}
