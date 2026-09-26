import { deleteConversation, type Conversation } from "./api";

type Props = {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string | null) => void;
  onChanged: () => void;
  onError: (e: unknown) => void;
};

export function Conversations({ conversations, activeId, onSelect, onChanged, onError }: Props) {
  async function remove(id: string) {
    if (!confirm("Delete this conversation?")) return;
    try {
      await deleteConversation(id);
      if (id === activeId) onSelect(null);
      onChanged();
    } catch (e) {
      onError(e);
    }
  }

  return (
    <nav className="conversations">
      <button className="new" onClick={() => onSelect(null)}>+ New chat</button>
      <ul>
        {conversations.map((c) => (
          <li key={c.id} className={c.id === activeId ? "active" : ""}>
            <button className="title" onClick={() => onSelect(c.id)} title={c.title ?? ""}>
              {c.title || "Untitled"}
              <span className="muted">{new Date(c.last_active_at).toLocaleString()}</span>
            </button>
            <button className="delete" aria-label="Delete conversation" onClick={() => remove(c.id)}>×</button>
          </li>
        ))}
      </ul>
      {conversations.length === 0 && <p className="muted pad">No conversations yet.</p>}
    </nav>
  );
}
