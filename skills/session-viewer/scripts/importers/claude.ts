import {
  compactText,
  firstText,
  imageAttachmentsFromContent,
  isRecord,
  messageEvent,
  pretty,
  reasoningEvent,
  resolveTitle,
  stringValue,
  textFromContentBlocks,
  toolCallEvent,
  toolResultEvent,
} from "../core/jsonl.ts";
import type { JsonlRecord, SessionDocument, SessionEvent, SessionImporter } from "../core/types.ts";

function timestampOf(value: Record<string, unknown>): string | undefined {
  return firstText(value, ["timestamp", "created_at", "updated_at"]);
}

function parseContentBlocks(
  recordId: string,
  content: unknown,
  timestamp: string | undefined,
  fallbackRole: string,
): SessionEvent[] {
  if (typeof content === "string") {
    return content.trim()
      ? [
          {
            id: recordId,
            kind: "message",
            role: fallbackRole,
            title: fallbackRole,
            text: content.trim(),
            timestamp,
          },
        ]
      : [];
  }
  if (!Array.isArray(content)) {
    return [];
  }

  const events: SessionEvent[] = [];
  const textParts: string[] = [];
  const images = imageAttachmentsFromContent(content);
  let textIndex = 0;

  for (const block of content) {
    if (!isRecord(block)) {
      continue;
    }
    const type = stringValue(block.type);
    if (type === "text") {
      const text = stringValue(block.text);
      if (text) {
        textParts.push(text);
      }
      continue;
    }
    if (type === "thinking") {
      const text = firstText(block, ["thinking", "text", "content"]);
      if (!text) {
        continue;
      }
      events.push(
        reasoningEvent({
          id: `${recordId}-thinking-${textIndex++}`,
          title: "thinking",
          text,
          timestamp,
          raw: block,
        }),
      );
      continue;
    }
    if (type === "tool_use") {
      const name = stringValue(block.name) ?? "tool_use";
      events.push(
        toolCallEvent({
          id: `${recordId}-tool-${textIndex++}`,
          title: `tool call: ${name}`,
          argsText: pretty(block.input),
          timestamp,
          callId: stringValue(block.id),
          toolName: name,
          status: "running",
          raw: block,
        }),
      );
      continue;
    }
    if (type === "tool_result") {
      const images = imageAttachmentsFromContent(block.content);
      const text =
        textFromContentBlocks(block.content) ||
        (images.length ? "" : pretty(block.content ?? block));
      events.push(
        toolResultEvent({
          id: `${recordId}-result-${textIndex++}`,
          title: stringValue(block.tool_use_id)
            ? `tool result: ${stringValue(block.tool_use_id)}`
            : "tool result",
          text,
          images,
          timestamp,
          callId: stringValue(block.tool_use_id),
          status: block.is_error === true ? "error" : "ok",
          raw: block,
        }),
      );
      continue;
    }
    const text = textFromContentBlocks([block]);
    if (text) {
      textParts.push(text);
    }
  }

  const merged = messageEvent({
    id: `${recordId}-text`,
    kind: "message",
    role: fallbackRole,
    title: fallbackRole,
    text: compactText(textParts),
    images,
    timestamp,
  });
  if (merged) {
    events.unshift(merged);
  }
  return events;
}

export const claudeImporter: SessionImporter = {
  format: "claude",
  detect(records) {
    return records.some((record) => {
      if (!isRecord(record.value)) {
        return false;
      }
      const type = record.value.type;
      const message = isRecord(record.value.message) ? record.value.message : undefined;
      return (
        type === "summary" ||
        type === "user" ||
        type === "assistant" ||
        message?.role === "user" ||
        message?.role === "assistant"
      );
    });
  },
  parse(records, sourcePath) {
    const meta: SessionDocument["meta"] = {};
    const events: SessionEvent[] = [];
    const warnings: string[] = [];

    for (const record of records) {
      if (!isRecord(record.value)) {
        continue;
      }
      const type = stringValue(record.value.type);
      const timestamp = timestampOf(record.value);
      if (type === "summary") {
        const summary = firstText(record.value, ["summary", "text"]);
        if (summary) {
          meta.summary = summary;
        }
        continue;
      }

      const message = isRecord(record.value.message) ? record.value.message : record.value;
      const role = stringValue(message.role) ?? type ?? "event";
      const content = message.content;
      const parsedEvents = parseContentBlocks(`claude-${record.line}`, content, timestamp, role);
      if (parsedEvents.length > 0) {
        events.push(...parsedEvents.map((event) => ({ ...event, raw: event.raw ?? record.value })));
        continue;
      }

      const text = firstText(record.value, ["text", "content"]);
      if (text) {
        events.push({
          id: `claude-${record.line}`,
          kind: role === "system" ? "system" : "message",
          role,
          title: role,
          text,
          timestamp,
          raw: record.value,
        });
      }
    }

    if (events.length === 0) {
      warnings.push("no Claude message events found");
    }

    const title = resolveTitle(stringValue(meta.summary), sourcePath, "Claude session");
    return {
      format: "claude",
      title,
      sourcePath,
      meta,
      events,
      warnings,
    };
  },
};
