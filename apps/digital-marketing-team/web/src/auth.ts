const CLIENT_ID = import.meta.env.VITE_LIBRAOS_CLIENT_ID ?? "digital-marketing-team";
const REDIRECT_URI = `${location.origin}/callback`;

type Tokens = { access_token: string; refresh_token?: string };
const load = (): Tokens | null => JSON.parse(sessionStorage.getItem("tokens") ?? "null");
const save = (tokens: Tokens | null) =>
  tokens ? sessionStorage.setItem("tokens", JSON.stringify(tokens)) : sessionStorage.removeItem("tokens");

export const isSignedIn = () => load() !== null;
const base64url = (bytes: Uint8Array) =>
  btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const random = (n = 32) => base64url(crypto.getRandomValues(new Uint8Array(n)));

export async function signIn(): Promise<void> {
  const verifier = random();
  const state = random(16);
  sessionStorage.setItem("pkce", JSON.stringify({ verifier, state }));
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    response_type: "code",
    state,
    scope: "openid profile email offline_access",
    code_challenge: base64url(new Uint8Array(digest)),
    code_challenge_method: "S256",
  });
  location.assign(`/oauth/authorize?${params}`);
}

async function tokenRequest(form: Record<string, string>): Promise<Tokens> {
  const response = await fetch("/oauth/token", { method: "POST", body: new URLSearchParams(form) });
  const body = await response.json();
  if (!response.ok) throw new Error(`Sign-in failed: ${body.error ?? response.status}`);
  return body;
}

export async function completeSignIn(url: URL): Promise<void> {
  const pending = JSON.parse(sessionStorage.getItem("pkce") ?? "null");
  sessionStorage.removeItem("pkce");
  const code = url.searchParams.get("code");
  if (!pending || !code || url.searchParams.get("state") !== pending.state) {
    throw new Error("Sign-in response did not match this tab. Try again.");
  }
  save(await tokenRequest({
    grant_type: "authorization_code",
    code,
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    code_verifier: pending.verifier,
  }));
}

let refreshing: Promise<boolean> | null = null;
function refresh(): Promise<boolean> {
  refreshing ??= (async () => {
    const refreshToken = load()?.refresh_token;
    if (!refreshToken) return false;
    try {
      save(await tokenRequest({ grant_type: "refresh_token", refresh_token: refreshToken, client_id: CLIENT_ID }));
      return true;
    } catch {
      save(null);
      return false;
    }
  })().finally(() => { refreshing = null; });
  return refreshing;
}

export class SignedOut extends Error {}

export async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const attempt = () => fetch(path, {
    ...init,
    headers: { ...init.headers, Authorization: `Bearer ${load()?.access_token}` },
  });
  let response = await attempt();
  if (response.status === 401 && await refresh()) response = await attempt();
  if (response.status === 401) {
    save(null);
    throw new SignedOut();
  }
  return response;
}

export async function signOut(): Promise<void> {
  const refreshToken = load()?.refresh_token;
  save(null);
  if (refreshToken) {
    await fetch("/oauth/revoke", { method: "POST", body: new URLSearchParams({ token: refreshToken }) }).catch(() => {});
  }
  location.assign("/oauth/logout?post_logout_redirect_uri=/");
}
