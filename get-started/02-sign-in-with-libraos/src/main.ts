import { decodeJwt, handleCallback, signIn, signOut, userinfo, type Tokens } from "./oidc";

const app = document.getElementById("app")!;
const show = (html: string) => (app.innerHTML = html);
const escapeHtml = (s: string) => s.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" })[c]!);
const json = (v: unknown) => `<pre>${escapeHtml(JSON.stringify(v, null, 2))}</pre>`;

async function main() {
  const url = new URL(location.href);

  // Back from the kernel with an authorization code.
  if (url.pathname === "/callback") {
    if (url.searchParams.has("error")) throw new Error(`Sign-in refused: ${url.searchParams.get("error")}`);
    const tokens = await handleCallback(url);
    // sessionStorage keeps the demo simple: tokens die with the tab. See the
    // README for where tokens should live in a production app.
    sessionStorage.setItem("tokens", JSON.stringify(tokens));
    history.replaceState(null, "", "/"); // drop ?code from the address bar
  }

  const tokens: Tokens | null = JSON.parse(sessionStorage.getItem("tokens") ?? "null");
  if (!tokens) {
    show(`<p>You are signed out.</p><button class="primary" id="in">Sign in with LibraOS</button>`);
    document.getElementById("in")!.onclick = () => signIn();
    return;
  }

  const me = await userinfo(tokens.access_token).catch(() => null);
  if (!me) {
    // Expired (access tokens last one hour) or the kernel restarted.
    sessionStorage.removeItem("tokens");
    return main();
  }
  show(`
    <p>Signed in as <strong>${escapeHtml(String(me.name || me.email))}</strong>.
       <button id="out">Sign out</button></p>
    <h3>GET /oauth/userinfo</h3>${json(me)}
    <h3>id_token claims</h3>${json(decodeJwt(tokens.id_token))}
  `);
  document.getElementById("out")!.onclick = () => signOut();
}

main().catch((err) => {
  show(`<p class="error">${escapeHtml(String(err.message ?? err))}</p><p><a href="/">Start over</a></p>`);
});
