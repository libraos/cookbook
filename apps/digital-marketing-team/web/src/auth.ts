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

// crypto.subtle is unavailable on plain-HTTP remote origins even though
// crypto.getRandomValues remains available. The cookbook is commonly opened
// from another machine during a local demo, so keep PKCE enabled and compute
// SHA-256 locally in that environment instead of making the sign-in button a
// silent no-op. HTTPS and localhost continue to use the browser implementation.
function sha256(input: Uint8Array): Uint8Array {
  const constants = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
  ];
  const bitLength = input.length * 8;
  const paddedLength = Math.ceil((input.length + 9) / 64) * 64;
  const data = new Uint8Array(paddedLength);
  data.set(input);
  data[input.length] = 0x80;
  const view = new DataView(data.buffer);
  view.setUint32(paddedLength - 4, bitLength >>> 0);
  view.setUint32(paddedLength - 8, Math.floor(bitLength / 0x100000000));
  const state = new Uint32Array([0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19]);
  const words = new Uint32Array(64);
  const rotate = (value: number, amount: number) => (value >>> amount) | (value << (32 - amount));
  for (let offset = 0; offset < paddedLength; offset += 64) {
    for (let i = 0; i < 16; i++) words[i] = view.getUint32(offset + i * 4);
    for (let i = 16; i < 64; i++) {
      const s0 = rotate(words[i - 15], 7) ^ rotate(words[i - 15], 18) ^ (words[i - 15] >>> 3);
      const s1 = rotate(words[i - 2], 17) ^ rotate(words[i - 2], 19) ^ (words[i - 2] >>> 10);
      words[i] = (words[i - 16] + s0 + words[i - 7] + s1) >>> 0;
    }
    let [a, b, c, d, e, f, g, h] = state;
    for (let i = 0; i < 64; i++) {
      const upperE = rotate(e, 6) ^ rotate(e, 11) ^ rotate(e, 25);
      const choose = (e & f) ^ (~e & g);
      const t1 = (h + upperE + choose + constants[i] + words[i]) >>> 0;
      const upperA = rotate(a, 2) ^ rotate(a, 13) ^ rotate(a, 22);
      const majority = (a & b) ^ (a & c) ^ (b & c);
      const t2 = (upperA + majority) >>> 0;
      h = g; g = f; f = e; e = (d + t1) >>> 0; d = c; c = b; b = a; a = (t1 + t2) >>> 0;
    }
    state[0] = (state[0] + a) >>> 0; state[1] = (state[1] + b) >>> 0;
    state[2] = (state[2] + c) >>> 0; state[3] = (state[3] + d) >>> 0;
    state[4] = (state[4] + e) >>> 0; state[5] = (state[5] + f) >>> 0;
    state[6] = (state[6] + g) >>> 0; state[7] = (state[7] + h) >>> 0;
  }
  const output = new Uint8Array(32);
  const outputView = new DataView(output.buffer);
  state.forEach((word, index) => outputView.setUint32(index * 4, word));
  return output;
}

export async function signIn(): Promise<void> {
  const verifier = random();
  const state = random(16);
  sessionStorage.setItem("pkce", JSON.stringify({ verifier, state }));
  const verifierBytes = new TextEncoder().encode(verifier);
  const digest = crypto.subtle
    ? new Uint8Array(await crypto.subtle.digest("SHA-256", verifierBytes))
    : sha256(verifierBytes);
  const params = new URLSearchParams({
    client_id: CLIENT_ID,
    redirect_uri: REDIRECT_URI,
    response_type: "code",
    state,
    scope: "openid profile email offline_access",
    code_challenge: base64url(digest),
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
