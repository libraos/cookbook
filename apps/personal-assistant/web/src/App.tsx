import { useCallback, useEffect, useState } from "react";
import { isSignedIn, signIn, signOut, SignedOut } from "./auth";
import { getMe, listConversations, type Conversation, type Me } from "./api";
import { Chat } from "./Chat";
import { Conversations } from "./Conversations";
import { Documents } from "./Documents";
import { Memory } from "./Memory";

export function App({ initialError }: { initialError: string | null }) {
  const [signedIn, setSignedIn] = useState(isSignedIn());
  const [me, setMe] = useState<Me | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  // Bumped when the user opens a conversation or starts a new one, so the
  // chat pane starts fresh. Saving a new chat changes activeId but not this.
  const [paneKey, setPaneKey] = useState(0);
  const open = (id: string | null) => { setActiveId(id); setPaneKey((k) => k + 1); };
  const [error, setError] = useState(initialError);

  // Any call can discover the session has ended; fall back to the sign-in screen.
  const onError = useCallback((e: unknown) => {
    if (e instanceof SignedOut) setSignedIn(false);
    else setError((e as Error).message);
  }, []);

  const refreshConversations = useCallback(
    () => listConversations().then(setConversations).catch(onError),
    [onError],
  );

  useEffect(() => {
    if (!signedIn) return;
    getMe().then(setMe).catch(onError);
    refreshConversations();
  }, [signedIn, onError, refreshConversations]);

  if (!signedIn) {
    return (
      <div className="signin">
        <h1>Personal Assistant</h1>
        <p>Chat with an assistant that knows your documents and remembers you.</p>
        {error && <p className="error">{error}</p>}
        <button className="primary" onClick={() => signIn()}>Sign in with LibraOS</button>
      </div>
    );
  }

  return (
    <div className="layout">
      <header>
        <strong>Personal Assistant</strong>
        <span className="spacer" />
        {me && <span className="muted" title={me.email}>{me.name || me.email}</span>}
        <button onClick={() => signOut()}>Sign out</button>
      </header>
      {error && <div className="banner error" onClick={() => setError(null)}>{error} (dismiss)</div>}
      <Conversations
        conversations={conversations}
        activeId={activeId}
        onSelect={open}
        onChanged={refreshConversations}
        onError={onError}
      />
      <Chat
        key={paneKey}
        conversationId={activeId}
        onSaved={(id) => { setActiveId(id); refreshConversations(); }}
        onError={onError}
      />
      <aside className="side">
        <Documents onError={onError} />
        <Memory onError={onError} />
      </aside>
    </div>
  );
}
