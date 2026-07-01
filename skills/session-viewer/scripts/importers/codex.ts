import {
  assignScalarMeta,
  compactText,
  firstText,
  imageAttachmentsFromContent,
  isRecord,
  pretty,
  reasoningEvent,
  resolveTitle,
  stringValue,
  textFromContentBlocks,
  toolCallEvent,
  toolResultEvent,
} from "../core/jsonl.ts";
import type { JsonlRecord, SessionDocument, SessionEvent, SessionImporter } from "../core/types.ts";

function payloadOf(record: JsonlRecord): Record<string, unknown> | undefined {
  return isRecord(record.value) && isRecord(record.value.payload)
    ? record.value.payload
    : undefined;
}

function timestampOf(record: JsonlRecord): string | undefined {
  return isRecord(record.value) ? stringValue(record.value.timestamp) : undefined;
}

function statusFromOutput(output: string): "ok" | "error" | "unknown" {
  const match = /Process exited with code\s+(-?\d+)/u.exec(output);
  if (!match) {
    return "unknown";
  }
  return match[1] === "0" ? "ok" : "error";
}

function isTurnAbortedText(text: string): boolean {
  const trimmed = text.trim();
  return (
    /^<turn_aborted>[\s\S]*<\/turn_aborted>$/u.test(trimmed) &&
    trimmed.includes("The user interrupted the previous turn on purpose.") &&
    trimmed.includes("Any running unified exec processes may still be running in the background.")
  );
}

function turnAbortedEvent(id: string, timestamp: string | undefined, raw: unknown): SessionEvent {
  return {
    id,
    kind: "event",
    title: "Turn aborted",
    text: "Turn aborted by user.",
    timestamp,
    raw,
  };
}

function eventFromResponseItem(
  record: JsonlRecord,
  payload: Record<string, unknown>,
): SessionEvent | null {
  const type = stringValue(payload.type);
  const id = `codex-${record.line}`;
  if (!type) {
    return null;
  }

  if (type === "message") {
    const role = stringValue(payload.role) ?? "unknown";
    const phase = stringValue(payload.phase);
    const images = imageAttachmentsFromContent(payload.content);
    const text = textFromContentBlocks(payload.content);
    if (!text && images.length === 0) {
      return null;
    }
    return {
      id,
      kind: role === "developer" || role === "system" ? "system" : "message",
      role,
      title: `${role}${phase ? ` [${phase}]` : ""}`,
      text,
      images: images.length ? images : undefined,
      timestamp: timestampOf(record),
      raw: payload,
    };
  }

  if (type === "reasoning") {
    const summary = Array.isArray(payload.summary)
      ? compactText(
          payload.summary.map((item) =>
            isRecord(item) ? firstText(item, ["text", "summary"]) : undefined,
          ),
        )
      : "";
    const content = textFromContentBlocks(payload.content);
    const text = compactText([summary, content]);
    if (!text) {
      return null;
    }
    return reasoningEvent({ id, title: "reasoning", text, timestamp: timestampOf(record), raw: payload });
  }

  if (type === "function_call") {
    const name = stringValue(payload.name) ?? "function_call";
    const callId = stringValue(payload.call_id);
    return toolCallEvent({
      id,
      title: `tool call: ${name}`,
      argsText: pretty(payload.arguments),
      timestamp: timestampOf(record),
      callId,
      toolName: name,
      status: "running",
      raw: payload,
    });
  }

  if (type === "function_call_output") {
    const callId = stringValue(payload.call_id);
    const output = pretty(payload.output);
    return toolResultEvent({
      id,
      title: callId ? `tool result: ${callId}` : "tool result",
      text: output,
      timestamp: timestampOf(record),
      callId,
      status: statusFromOutput(output),
      raw: payload,
    });
  }

  if (type === "custom_tool_call") {
    const name = stringValue(payload.name) ?? "custom_tool_call";
    const callId = stringValue(payload.call_id);
    const status = stringValue(payload.status);
    return toolCallEvent({
      id,
      title: `custom tool call: ${name}${status ? ` [${status}]` : ""}`,
      argsText: pretty(payload.input),
      timestamp: timestampOf(record),
      callId,
      toolName: name,
      status: status === "failed" ? "error" : status === "completed" ? "ok" : "running",
      raw: payload,
    });
  }

  if (type === "custom_tool_call_output") {
    const callId = stringValue(payload.call_id);
    const output = pretty(payload.output);
    return toolResultEvent({
      id,
      title: callId ? `custom tool result: ${callId}` : "custom tool result",
      text: output,
      timestamp: timestampOf(record),
      callId,
      status: output.toLowerCase().includes("error") ? "error" : "unknown",
      raw: payload,
    });
  }

  if (type === "web_search_call") {
    return toolCallEvent({
      id,
      title: "web search",
      argsText: pretty(payload),
      timestamp: timestampOf(record),
      toolName: "web_search",
      status: "unknown",
      raw: payload,
    });
  }

  return {
    id,
    kind: "event",
    title: `response item: ${type}`,
    text: pretty(payload),
    timestamp: timestampOf(record),
    raw: payload,
  };
}

export const codexImporter: SessionImporter = {
  format: "codex",
  detect(records) {
    return records.some((record) => {
      if (!isRecord(record.value)) {
        return false;
      }
      return record.value.type === "session_meta" || record.value.type === "response_item";
    });
  },
  parse(records, sourcePath) {
    const warnings: string[] = [];
    const meta: SessionDocument["meta"] = {};
    const events: SessionEvent[] = [];

    for (const record of records) {
      if (!isRecord(record.value)) {
        continue;
      }
      const recordType = stringValue(record.value.type);
      if (recordType === "session_meta") {
        const payload = payloadOf(record);
        if (payload) {
          assignScalarMeta(meta, payload);
        }
        continue;
      }
      if (recordType === "turn_context") {
        const payload = payloadOf(record);
        events.push({
          id: `codex-${record.line}`,
          kind: "system",
          title: "turn context",
          text: pretty(payload ?? record.value),
          timestamp: timestampOf(record),
          raw: record.value,
        });
        continue;
      }
      if (recordType === "event_msg") {
        const payload = payloadOf(record);
        if (!payload) {
          continue;
        }
        const type = stringValue(payload.type) ?? "event";
        if (type === "task_started" || type === "task_complete") {
          continue;
        }
        if (type === "turn_aborted") {
          const previous = events.at(-1);
          if (
            previous?.kind === "message" &&
            previous.role === "user" &&
            isTurnAbortedText(previous.text)
          ) {
            events.pop();
          }
          if (events.at(-1)?.title !== "Turn aborted") {
            events.push(turnAbortedEvent(`codex-${record.line}`, timestampOf(record), payload));
          }
          continue;
        }
        events.push({
          id: `codex-${record.line}`,
          kind: "event",
          title: `event: ${type}`,
          text: firstText(payload, ["message", "text"]) ?? pretty(payload),
          timestamp: timestampOf(record),
          raw: payload,
        });
        continue;
      }
      if (recordType !== "response_item") {
        continue;
      }
      const payload = payloadOf(record);
      if (!payload) {
        warnings.push(`line ${record.line}: response_item without object payload`);
        continue;
      }
      const event = eventFromResponseItem(record, payload);
      if (event) {
        events.push(event);
      }
    }

    if (events.length === 0) {
      warnings.push("no Codex message events found");
    }

    const title = resolveTitle(stringValue(meta.id), sourcePath, "Codex session");
    return {
      format: "codex",
      title,
      sourcePath,
      meta,
      events,
      warnings,
    };
  },
};
