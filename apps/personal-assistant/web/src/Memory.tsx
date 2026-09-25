import { useEffect, useState } from "react";
import { getMemory } from "./api";
import { Markdown } from "./Markdown";

export function Memory({ onError }: { onError: (e: unknown) => void }) {
  const [memory, setMemory] = useState<string | null>(null);
  const refresh = () => getMemory().then(setMemory).catch(onError);
  useEffect(() => { refresh(); }, []); // once, on mount

  return (
    <section>
      <h3>
        What I remember <button className="link" onClick={refresh}>refresh</button>
      </h3>
      {memory ? (
        <div className="memory"><Markdown text={memory} /></div>
      ) : (
        <p className="muted small">
          Nothing summarized yet. I already use what you've told me recently, in every conversation;
          the kernel writes it up here once there's enough to summarize.
        </p>
      )}
    </section>
  );
}
