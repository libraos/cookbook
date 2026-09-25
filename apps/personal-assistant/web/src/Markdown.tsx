import ReactMarkdown from "react-markdown";

// Agents answer in Markdown. react-markdown renders it without ever injecting
// raw HTML, so a reply can't smuggle markup into the page.
//
// Safety net for citations: retrieved documents reach the model labelled with
// their internal storage path (users/<id>/my-documents/file.txt). The agent is
// told to cite file names only; if one slips through, show just the file name.
const STORAGE_PATH = /\busers\/[0-9a-f-]{36}\/(?:[^\s/)]+\/)*([^\s/)]+)/g;

export function Markdown({ text }: { text: string }) {
  return (
    <div className="md">
      <ReactMarkdown>{text.replace(STORAGE_PATH, "$1")}</ReactMarkdown>
    </div>
  );
}
