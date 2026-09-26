import { useEffect, useRef, useState } from "react";
import { listDocuments, uploadDocument, type Doc } from "./api";

export function Documents({ onError }: { onError: (e: unknown) => void }) {
  const [docs, setDocs] = useState<Doc[]>([]);
  const [uploading, setUploading] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  const refresh = () => listDocuments().then(setDocs).catch(onError);
  useEffect(() => { refresh(); }, []); // once, on mount

  async function upload(files: FileList | null) {
    if (!files?.length) return;
    setUploading(true);
    try {
      for (const f of Array.from(files)) await uploadDocument(f);
      await refresh();
    } catch (e) {
      onError(e);
    } finally {
      setUploading(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <section>
      <h3>My documents</h3>
      <p className="muted small">Only you can search these. Indexing takes a few seconds after upload.</p>
      <ul className="docs">
        {docs.map((d) => <li key={d.name}>{d.name}</li>)}
        {docs.length === 0 && <li className="muted">None yet.</li>}
      </ul>
      <input ref={input} type="file" hidden multiple accept=".txt,.md,.pdf,.docx" onChange={(e) => upload(e.target.files)} />
      <button onClick={() => input.current?.click()} disabled={uploading}>
        {uploading ? "Uploading…" : "Upload"}
      </button>
    </section>
  );
}
