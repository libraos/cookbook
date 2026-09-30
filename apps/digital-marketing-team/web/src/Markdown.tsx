import ReactMarkdown from "react-markdown";
import remarkBreaks from "remark-breaks";
import remarkGfm from "remark-gfm";

// Synthesized reports wrap each task output in an H2 and may preserve the
// task's original H1/H2 headings. Shift those nested headings down so the
// rendered document keeps one H1 and a valid hierarchy.
export function normalizeReportMarkdown(text: string): string {
  const lines = text.replace(/\r\n?/g, "\n").split("\n");
  let foundDocumentTitle = false;
  let insideTaskOutput = false;

  return lines.map((line, index) => {
    const heading = /^(#{1,6})\s+(.+)$/.exec(line);
    if (!heading) return line;

    const level = heading[1].length;
    if (level === 1 && !foundDocumentTitle) {
      foundDocumentTitle = true;
      return line;
    }

    let nextContent = "";
    for (let next = index + 1; next < lines.length; next += 1) {
      if (lines[next].trim()) {
        nextContent = lines[next].trim();
        break;
      }
    }
    const taskWrapper = level === 2 && /^_Prepared by\b/.test(nextContent);
    if (taskWrapper) {
      insideTaskOutput = true;
      return line;
    }

    if (insideTaskOutput) {
      return `${"#".repeat(Math.min(6, level + 2))} ${heading[2]}`;
    }
    return level === 1 ? `## ${heading[2]}` : line;
  }).join("\n");
}

export function Markdown({ text }: { text: string }) {
  return <div className="markdown"><ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>{normalizeReportMarkdown(text)}</ReactMarkdown></div>;
}
