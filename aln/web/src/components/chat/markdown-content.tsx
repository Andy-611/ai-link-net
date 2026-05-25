import { Fragment, type ReactNode } from "react";

import { cn } from "@/lib/utils";

interface MarkdownContentProps {
  content: string;
  className?: string;
}

type MarkdownBlock =
  | { kind: "code"; language?: string; lines: string[] }
  | { kind: "heading"; level: 1 | 2 | 3 | 4 | 5 | 6; text: string }
  | { kind: "blockquote"; lines: string[] }
  | { kind: "list"; ordered: boolean; items: string[] }
  | { kind: "table"; headers: string[]; rows: string[][] }
  | { kind: "paragraph"; lines: string[] }
  | { kind: "hr" };

const HEADING_RE = /^(#{1,6})\s+(.+)$/;
const HR_RE = /^(-{3,}|\*{3,}|_{3,})\s*$/;
const ORDERED_LIST_RE = /^\d+\.\s+(.+)$/;
const UNORDERED_LIST_RE = /^[-*+]\s+(.+)$/;
const LINK_RE = /^\[([^\]]+)\]\(([^)]+)\)$/;
const INLINE_TOKEN_RE = /(`[^`]+`)|(\*\*[^*]+\*\*)|(~~[^~]+~~)|(\*[^*\n]+\*)|(\[[^\]]+\]\([^)]+\))/g;
const TABLE_SEPARATOR_CELL_RE = /^:?-{3,}:?$/;

function parseTableRow(line: string): string[] | null {
  const trimmed = line.trim();
  if (!trimmed.includes("|")) return null;
  const normalized = trimmed.replace(/^\|/, "").replace(/\|$/, "");
  const cells = normalized.split("|").map((cell) => cell.trim());
  if (cells.length < 2) return null;
  return cells;
}

function isTableSeparatorLine(line: string, expectedColumns: number): boolean {
  const cells = parseTableRow(line);
  if (!cells || cells.length !== expectedColumns) return false;
  return cells.every((cell) => TABLE_SEPARATOR_CELL_RE.test(cell));
}

function isTableStart(lines: string[], index: number): boolean {
  if (index + 1 >= lines.length) return false;
  const headers = parseTableRow(lines[index]);
  if (!headers) return false;
  return isTableSeparatorLine(lines[index + 1], headers.length);
}

function isBlockBoundary(line: string): boolean {
  const trimmed = line.trim();
  if (!trimmed) return true;
  if (trimmed.startsWith("```")) return true;
  if (HEADING_RE.test(trimmed)) return true;
  if (HR_RE.test(trimmed)) return true;
  if (ORDERED_LIST_RE.test(trimmed)) return true;
  if (UNORDERED_LIST_RE.test(trimmed)) return true;
  return trimmed.startsWith(">");
}

function parseBlocks(content: string): MarkdownBlock[] {
  const blocks: MarkdownBlock[] = [];
  const lines = content.replace(/\r\n?/g, "\n").split("\n");
  let index = 0;

  while (index < lines.length) {
    const rawLine = lines[index];
    const trimmed = rawLine.trim();

    if (!trimmed) {
      index += 1;
      continue;
    }

    if (trimmed.startsWith("```")) {
      const language = trimmed.slice(3).trim() || undefined;
      index += 1;
      const codeLines: string[] = [];
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        codeLines.push(lines[index]);
        index += 1;
      }
      if (index < lines.length && lines[index].trim().startsWith("```")) {
        index += 1;
      }
      blocks.push({ kind: "code", language, lines: codeLines });
      continue;
    }

    const headingMatch = trimmed.match(HEADING_RE);
    if (headingMatch) {
      const level = headingMatch[1].length as 1 | 2 | 3 | 4 | 5 | 6;
      blocks.push({ kind: "heading", level, text: headingMatch[2].trim() });
      index += 1;
      continue;
    }

    if (HR_RE.test(trimmed)) {
      blocks.push({ kind: "hr" });
      index += 1;
      continue;
    }

    if (isTableStart(lines, index)) {
      const headers = parseTableRow(lines[index]) ?? [];
      index += 2; // skip header + separator
      const rows: string[][] = [];
      while (index < lines.length) {
        const row = parseTableRow(lines[index]);
        if (!row || row.length !== headers.length) break;
        rows.push(row);
        index += 1;
      }
      blocks.push({ kind: "table", headers, rows });
      continue;
    }

    if (trimmed.startsWith(">")) {
      const quoteLines: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith(">")) {
        quoteLines.push(lines[index].replace(/^\s*>\s?/, ""));
        index += 1;
      }
      blocks.push({ kind: "blockquote", lines: quoteLines });
      continue;
    }

    if (ORDERED_LIST_RE.test(trimmed) || UNORDERED_LIST_RE.test(trimmed)) {
      const ordered = ORDERED_LIST_RE.test(trimmed);
      const items: string[] = [];
      const matcher = ordered ? ORDERED_LIST_RE : UNORDERED_LIST_RE;
      while (index < lines.length) {
        const listLine = lines[index].trim();
        const match = listLine.match(matcher);
        if (!match) break;
        items.push(match[1]);
        index += 1;
      }
      blocks.push({ kind: "list", ordered, items });
      continue;
    }

    const paragraphLines: string[] = [];
    while (
      index < lines.length &&
      !isBlockBoundary(lines[index]) &&
      !isTableStart(lines, index)
    ) {
      paragraphLines.push(lines[index]);
      index += 1;
    }
    blocks.push({ kind: "paragraph", lines: paragraphLines });
  }

  return blocks;
}

function toSafeHref(rawHref: string): string | null {
  const href = rawHref.trim();
  if (!href) return null;
  if (href.startsWith("http://") || href.startsWith("https://")) return href;
  if (href.startsWith("mailto:")) return href;
  return null;
}

function renderInline(text: string, keyPrefix = ""): ReactNode[] {
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let tokenIndex = 0;

  const pushText = (segment: string): void => {
    if (!segment) return;
    nodes.push(<Fragment key={`${keyPrefix}text-${tokenIndex++}`}>{segment}</Fragment>);
  };

  for (const match of text.matchAll(INLINE_TOKEN_RE)) {
    const token = match[0];
    const start = match.index ?? 0;
    pushText(text.slice(lastIndex, start));

    if (token.startsWith("`")) {
      nodes.push(
        <code
          key={`${keyPrefix}code-${tokenIndex++}`}
          className="px-1.5 py-0.5 rounded bg-black/10 font-mono text-[0.9em]"
        >
          {token.slice(1, -1)}
        </code>,
      );
    } else if (token.startsWith("**")) {
      nodes.push(
        <strong key={`${keyPrefix}strong-${tokenIndex++}`} className="font-semibold">
          {token.slice(2, -2)}
        </strong>,
      );
    } else if (token.startsWith("~~")) {
      nodes.push(
        <del key={`${keyPrefix}del-${tokenIndex++}`} className="line-through opacity-80">
          {token.slice(2, -2)}
        </del>,
      );
    } else if (token.startsWith("*")) {
      nodes.push(
        <em key={`${keyPrefix}em-${tokenIndex++}`} className="italic">
          {token.slice(1, -1)}
        </em>,
      );
    } else {
      const linkMatch = token.match(LINK_RE);
      const label = linkMatch?.[1];
      const href = linkMatch ? toSafeHref(linkMatch[2]) : null;
      if (label && href) {
        nodes.push(
          <a
            key={`${keyPrefix}link-${tokenIndex++}`}
            href={href}
            target="_blank"
            rel="noreferrer noopener"
            className="underline decoration-current/60 underline-offset-2 hover:opacity-80"
          >
            {label}
          </a>,
        );
      } else {
        pushText(token);
      }
    }

    lastIndex = start + token.length;
  }

  pushText(text.slice(lastIndex));
  return nodes;
}

function renderLines(lines: string[]): ReactNode[] {
  return lines.flatMap((line, index) => {
    const nodes = renderInline(line, `L${index}-`);
    if (index === lines.length - 1) return nodes;
    return [...nodes, <br key={`br-${index}`} />];
  });
}

export function MarkdownContent({ content, className }: MarkdownContentProps) {
  const blocks = parseBlocks(content);

  if (blocks.length === 0) {
    return <span className={cn("opacity-70", className)}>(no content)</span>;
  }

  return (
    <div className={cn("break-words", className)}>
      {blocks.map((block, index) => {
        const key = `block-${index}`;

        if (block.kind === "heading") {
          const headingClass = cn(
            "font-semibold tracking-tight",
            block.level <= 2 ? "text-[1rem]" : "text-[0.95rem]",
          );
          return (
            <p key={key} className={headingClass}>
              {renderInline(block.text)}
            </p>
          );
        }

        if (block.kind === "code") {
          return (
            <div key={key} className="rounded-md bg-black/10 p-2 my-1">
              {block.language && (
                <div className="mb-1 text-[10px] uppercase tracking-wide opacity-60">
                  {block.language}
                </div>
              )}
              <pre className="overflow-x-auto whitespace-pre-wrap font-mono text-[12px] leading-relaxed">
                {block.lines.join("\n")}
              </pre>
            </div>
          );
        }

        if (block.kind === "blockquote") {
          return (
            <blockquote key={key} className="border-l-2 border-current/25 pl-3 opacity-90">
              {renderLines(block.lines)}
            </blockquote>
          );
        }

        if (block.kind === "list") {
          const ListTag = block.ordered ? "ol" : "ul";
          const markerClass = block.ordered ? "list-decimal" : "list-disc";
          return (
            <ListTag key={key} className={cn("pl-5 space-y-1", markerClass)}>
              {block.items.map((item, itemIndex) => (
                <li key={`${key}-item-${itemIndex}`}>{renderInline(item)}</li>
              ))}
            </ListTag>
          );
        }

        if (block.kind === "table") {
          return (
            <div key={key} className="my-1 overflow-x-auto">
              <table className="min-w-full border-collapse text-xs">
                <thead>
                  <tr className="border-b border-current/20">
                    {block.headers.map((header, headerIndex) => (
                      <th
                        key={`${key}-head-${headerIndex}`}
                        className="px-2 py-1 text-left font-semibold whitespace-nowrap"
                      >
                        {renderInline(header)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {block.rows.map((row, rowIndex) => (
                    <tr key={`${key}-row-${rowIndex}`} className="border-b border-current/10">
                      {row.map((cell, cellIndex) => (
                        <td
                          key={`${key}-row-${rowIndex}-cell-${cellIndex}`}
                          className="px-2 py-1.5 align-top"
                        >
                          {renderInline(cell)}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }

        if (block.kind === "hr") {
          return <hr key={key} className="my-2 border-current/20" />;
        }

        return (
          <p key={key} className="whitespace-pre-wrap">
            {renderLines(block.lines)}
          </p>
        );
      })}
    </div>
  );
}
