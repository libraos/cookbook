# 02 · Sign in with LibraOS

The smallest browser app that signs a person in with LibraOS and shows who
they are. No OIDC library: the whole Authorization Code + PKCE flow is about
60 lines of code in [`src/oidc.ts`](src/oidc.ts), so you can see every step.

```
you ──► app (localhost:5173) ──► LibraOS sign-in page ──► back to /callback?code=…
                                                           │
             app trades the code + PKCE verifier for tokens ┘
             app calls /oauth/userinfo with the access token
```

![Signed in: the userinfo the kernel verified, and the ID token claims](docs/signed-in.png)


## Run it

You need the local kernel from [`../`](../README.md) running (`docker compose up -d`).

```bash
cd get-started/02-sign-in-with-libraos
npm install
npm run dev            # http://localhost:5173
```

Open <http://localhost:5173>, click **Sign in with LibraOS**, and sign in with
the admin email and password from `get-started/.env`. (Or with the demo user
that `apps/personal-assistant/scripts/setup.sh` creates.) You'll see the
`/oauth/userinfo` response and the id_token's claims. **Sign out** ends both
the app's session and the kernel's.

Settings, both optional (copy `.env.example` to `.env`):

| Variable | Default | What it is |
|---|---|---|
| `LIBRAOS_URL` | `http://localhost:8900` | The kernel. Only the dev server uses it. |
| `VITE_LIBRAOS_CLIENT_ID` | `signin-example` | This app's OIDC client id. |

## Step by step

**0. Register the app with the kernel.** A browser app is a *public* OIDC
client: no secret, just an id and the one URL the kernel may send codes to.
`get-started/.env` already has it:

```bash
LIBRA_OS_OIDC_CLIENTS=signin-example=http://localhost:5173/callback,...
```

PKCE is required by default. Restart the kernel after changing this line.

**1. Send the browser to `/oauth/authorize`** (`signIn()`). The app makes three
random values and keeps them in `sessionStorage`:

- a PKCE *verifier*. Only its SHA-256 (the *challenge*) goes in the URL;
- a `state`, which the kernel echoes back, so the app knows the callback
  answers a request it made;
- a `nonce`, which the kernel copies into the id_token.

The kernel shows its sign-in form, then redirects to
`http://localhost:5173/callback?code=…&state=…`.

**2. Trade the code for tokens** (`handleCallback()`). `POST /oauth/token`,
form-encoded, with `grant_type=authorization_code`, `code`, `client_id`,
`redirect_uri` and `code_verifier`. The kernel hashes the verifier and checks it
against the challenge from step 1, so an intercepted code is useless without
this tab's verifier. The response has `access_token` (1 hour), `id_token` and
`expires_in`. Add `offline_access` to the scope to get a `refresh_token` too;
[`apps/personal-assistant`](../../apps/personal-assistant) does that.

**3. Ask who signed in** (`userinfo()`). `GET /oauth/userinfo` with
`Authorization: Bearer <access_token>` returns `sub`, `email`, `name`, `role`,
`roles`, `tenant_id` and `org_id`. Use the access token the same way for every
other kernel API: the kernel then answers as that user, with that user's
permissions.

**4. Sign out** (`signOut()`). Two halves. Forget the tokens, and send the
browser to `/oauth/logout?post_logout_redirect_uri=/`, which ends the kernel's
own sign-in session (an HttpOnly cookie the app can't touch) and redirects back
to the app. Skip the second half and the next **Sign in** goes straight
through without a password.

## Why a proxy?

`vite.config.ts` forwards `/oauth/*` to the kernel, so the browser sees one
origin (`localhost:5173`). That's how you'd deploy it too: the app and the
kernel behind one reverse proxy.

The kernel does allow cross-origin calls (its CORS default is `*`, narrowed with
`LIBRA_OS_CORS_ORIGINS`), so the token and userinfo calls would work directly.
Sign-out is what needs the shared origin: `/oauth/logout` only redirects to a
relative path on its own origin, and returns JSON otherwise. With the proxy,
"its own origin" is the app.

## Gotchas we hit

- **`redirect_uri` must match exactly.** `http://localhost:5173/callback` and
  `http://127.0.0.1:5173/callback` are different clients as far as the kernel is
  concerned, and so are `…:5173` and `…:5173/`. The mismatch surfaces as
  `{"error":"redirect_uri_mismatch"}`. Open the app on `localhost`, and keep
  `strictPort` on so Vite never moves to 5174.
- **The token request is form-encoded.** `client_credentials` also accepts
  JSON (01-first-agent uses it), but `authorization_code` and `refresh_token`
  read form fields only. A JSON body gets `{"error":"invalid_grant"}`, which
  looks like a bad code rather than a bad request.
- **`crypto.subtle` needs a secure context.** `localhost` counts; a LAN IP over
  plain http doesn't, and PKCE fails with `crypto.subtle is undefined`.
- **The id_token is RS256, the access token is HS256.** Verify an id_token
  against `/.well-known/jwks.json`. The access token is only for sending back to
  the kernel; don't try to verify it yourself. This example only *decodes* the
  id_token to display it. On a stock kernel the signing key is ephemeral and
  changes on every restart; set `LIBRA_OS_OIDC_PRIVATE_KEY_FILE` to keep it.
- **`iss` is `LIBRA_OS_PUBLIC_URL`**, whatever URL the browser used.
- **The kernel's sign-in session lasts 10 minutes and is shared.** Its cookie
  is scoped to the host, not the port, so signing in to one localhost app
  signs you in to the others (that's SSO working). Access tokens last 1 hour.
- **Tokens live in `sessionStorage` here** to keep the example short. Any script
  on the page can read them. Production apps usually keep tokens server-side
  (a backend-for-frontend) and give the browser a session cookie.
