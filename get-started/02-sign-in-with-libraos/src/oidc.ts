// Sign in with LibraOS: OpenID Connect Authorization Code flow with PKCE,
// written out by hand so every step is visible. A real app can use any
// certified OIDC client library instead; the steps are the same.

const CLIENT_ID = import.meta.env.VITE_LIBRAOS_CLIENT_ID ?? "signin-example";
// Must equal the registered redirect_uri exactly: scheme, host, port, path.
const REDIRECT_URI = `${location.origin}/callback`;

export type Tokens = { access_token: string; id_token: string; expires_in: number };

// PKCE: a one-time secret (verifier) stays in this tab; only its SHA-256
// (challenge) goes to the kernel. At the token step we prove we hold it, so a
// stolen authorization code is useless to anyone else.
function randomString(bytes = 32): string {
  return base64url(crypto.getRandomValues(new Uint8Array(bytes)));
}
function base64url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}
async function challengeFor(verifier: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(verifier));
  return base64url(new Uint8Array(digest));
}

// Step 1: send the browser to the kernel's sign-in page.
export async function signIn(): Promise<void> {
  const verifier = randomString(), state = randomString(16), nonce = randomString(16);
  sessionStorage.setItem("pkce", JSON.stringify({ verifier, state, nonce }));
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    response_type: "code",
    scope: "openid profile email",
    state, // echoed back: proves the callback answers OUR request
    nonce, // copied into the id_token: proves the token was minted for it
    code_challenge: await challengeFor(verifier),
    code_challenge_method: "S256",
  });
  location.assign(`/oauth/authorize?${params}`);
}

// Step 2: the kernel redirects back to /callback?code=…&state=…
// Trade the code (plus the PKCE verifier) for tokens.
export async function handleCallback(url: URL): Promise<Tokens> {
  const saved = JSON.parse(sessionStorage.getItem("pkce") ?? "null");
  sessionStorage.removeItem("pkce"); // single use, whatever happens next
  const code = url.searchParams.get("code");
  if (!saved || !code || url.searchParams.get("state") !== saved.state) {
    throw new Error("Sign-in response did not match a request from this tab. Try again.");
  }
  const res = await fetch("/oauth/token", {
    method: "POST",
    // Form-encoded, not JSON: the kernel reads this grant from form fields.
    body: new URLSearchParams({
      grant_type: "authorization_code",
      code,
      client_id: CLIENT_ID,
      redirect_uri: REDIRECT_URI,
      code_verifier: saved.verifier,
    }),
  });
  const tokens = await res.json();
  if (!res.ok) throw new Error(`Token exchange failed: ${tokens.error ?? res.status}`);
  if (decodeJwt(tokens.id_token).nonce !== saved.nonce) throw new Error("id_token nonce mismatch");
  return tokens;
}

// Reads a JWT's claims for display. This does NOT verify the signature: a
// backend that trusts an id_token must check it against /.well-known/jwks.json.
export function decodeJwt(jwt: string): Record<string, unknown> {
  const b64 = jwt.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(b64), (c) => c.charCodeAt(0))));
}

// Step 3: ask the kernel who the token belongs to.
export async function userinfo(accessToken: string): Promise<Record<string, unknown>> {
  const res = await fetch("/oauth/userinfo", { headers: { Authorization: `Bearer ${accessToken}` } });
  if (!res.ok) throw new Error(`userinfo: HTTP ${res.status}`);
  return res.json();
}

// Signing out has two halves: forget our tokens, and end the kernel's own
// sign-in session. Skip the second and the next "Sign in" succeeds silently.
export function signOut(): void {
  sessionStorage.removeItem("tokens");
  location.assign("/oauth/logout?post_logout_redirect_uri=/");
}
