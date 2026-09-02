import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { promisify } from "node:util";
import vm from "node:vm";
import { parseSessionDocument } from "./core/detect.ts";
import { basename, parseJsonl } from "./core/jsonl.ts";
import { buildSessionViewerHtml } from "./html.ts";
import { resolveOpenBrowserCommand } from "./open-browser.ts";

const execFileAsync = promisify(execFile);

function parse(text: string) {
  const { records } = parseJsonl(text);
  return parseSessionDocument(records, "fixture.jsonl");
}

// html.ts's --raw/--blank embed modes ship a second, browser-only
// re-implementation of session parsing (it can't import the TS importers
// directly -- there's no bundler in this zero-dependency skill). That
// duplication has drifted from the source of truth before; extract the actual
// shipped client script and run its pure helpers (parseRaw, highlight, ...)
// directly (no DOM needed -- they're plain data transforms) so a future edit
// to one side without the other fails a test instead of shipping silently.
function extractClientScript(): {
  parseRaw: (
    text: string,
    name?: string,
  ) => { format: string; title: string; meta: Record<string, unknown>; events: any[]; warnings: string[] };
  statusFromOutput: (output: unknown, exitCode?: number) => string;
  customToolResultStatus: (raw: unknown, output: unknown) => string;
  inferHomePath: (doc: unknown) => string;
  highlight: (text: unknown) => string;
  inlineMarkdown: (text: unknown) => string;
  state: { query: string; homePath: string };
} {
  const html = buildSessionViewerHtml(null, { embedMode: "blank" });
  const openMarker = "<script>\n(() => {\n";
  const openIndex = html.lastIndexOf(openMarker);
  assert.notEqual(openIndex, -1, "expected to find the client script in generated HTML");
  const bodyStart = openIndex + openMarker.length;
  const boundaryMarker = "const render = () => {";
  const boundaryIndex = html.indexOf(boundaryMarker, bodyStart);
  assert.notEqual(boundaryIndex, -1, "expected the parse/render helpers to precede render in the client script");
  const snippet = html.slice(bodyStart, boundaryIndex);
  // Only `state`'s initializer touches a browser global before the boundary
  // (localStorage.getItem, for the persisted theme/view-mode); the extracted
  // helpers are otherwise plain data transforms with no DOM access.
  const sandbox: Record<string, unknown> = { localStorage: { getItem: () => null, setItem: () => {} } };
  vm.runInNewContext(
    `${snippet}\nglobalThis.__snapshot = { parseRaw, statusFromOutput, customToolResultStatus, inferHomePath, highlight, inlineMarkdown, state };`,
    sandbox,
  );
  return sandbox.__snapshot as ReturnType<typeof extractClientScript>;
}

// The CLI merges parseJsonl warnings into the document (session-viewer.ts);
// use the same pipeline when comparing warnings against the client parser.
function parseWithJsonlWarnings(text: string) {
  const { records, warnings } = parseJsonl(text);
  const doc = parseSessionDocument(records, "fixture.jsonl");
  doc.warnings.unshift(...warnings);
  return doc;
}

// Server and client intentionally differ in event-id prefixes; parity tests
// compare the rendered substance of each event instead. Array.from rebuilds
// the array in the test realm -- vm-created arrays fail deepStrictEqual's
// prototype check otherwise.
function eventShape(doc: { events: any[] }) {
  return Array.from(doc.events, (event) => ({
    kind: event.kind,
    role: event.role,
    title: event.title,
    text: event.text,
    status: event.status,
    timestamp: event.timestamp,
  }));
}

test("basename returns the last non-empty path segment", () => {
  assert.equal(basename("dir/session.jsonl"), "session.jsonl");
  assert.equal(basename("C:\\logs\\session.jsonl"), "session.jsonl");
  assert.equal(basename("dir/"), "dir");
  assert.equal(basename("/"), undefined);
  assert.equal(basename(undefined), undefined);
});

test("opens hostile Windows paths without a command shell", () => {
  for (const filePath of [
    "C:\\Reports\\session & calc.exe.html",
    "C:\\Reports\\session | whoami.html",
    "C:\\Reports\\%COMSPEC%.html",
    "C:\\Reports\\session ^& echo injected.html",
  ]) {
    assert.deepEqual(resolveOpenBrowserCommand("win32", filePath), {
      executable: "explorer.exe",
      args: [filePath],
    });
  }
});

test("parses Codex rollout tool calls and outputs", () => {
  const doc = parse(
    [
      JSON.stringify({
        timestamp: "2026-05-25T10:00:00Z",
        type: "session_meta",
        payload: { id: "codex-session", cwd: "/tmp/project" },
      }),
      JSON.stringify({
        timestamp: "2026-05-25T10:00:01Z",
        type: "response_item",
        payload: {
          type: "message",
          role: "assistant",
          content: [{ type: "output_text", text: "hello" }],
        },
      }),
      JSON.stringify({
        timestamp: "2026-05-25T10:00:02Z",
        type: "response_item",
        payload: {
          type: "function_call",
          name: "functions.exec_command",
          call_id: "call-1",
          arguments: JSON.stringify({ cmd: "pwd" }),
        },
      }),
      JSON.stringify({
        timestamp: "2026-05-25T10:00:03Z",
        type: "response_item",
        payload: {
          type: "function_call_output",
          call_id: "call-1",
          output: "Process exited with code 0\nOutput:\n/tmp/project",
        },
      }),
    ].join("\n"),
  );
  assert.equal(doc.format, "codex");
  assert.equal(
    doc.events.some((event) => event.kind === "tool_call"),
    true,
  );
  assert.equal(
    doc.events.some((event) => event.kind === "tool_result" && event.status === "ok"),
    true,
  );
});

test("hides encrypted Codex reasoning items", () => {
  const doc = parse(
    [
      JSON.stringify({
        timestamp: "2026-05-25T10:00:00Z",
        type: "session_meta",
        payload: { id: "codex-session" },
      }),
      JSON.stringify({
        timestamp: "2026-05-25T10:00:01Z",
        type: "response_item",
        payload: {
          type: "reasoning",
          id: "rs_1",
          encrypted_content: "gAAAAABhidden",
          summary: [],
        },
      }),
      JSON.stringify({
        timestamp: "2026-05-25T10:00:02Z",
        type: "response_item",
        payload: {
          type: "message",
          role: "assistant",
          content: [{ type: "output_text", text: "visible" }],
        },
      }),
    ].join("\n"),
  );
  assert.equal(
    doc.events.some((event) => event.kind === "reasoning"),
    false,
  );
  assert.equal(
    doc.events
      .map((event) => event.text)
      .join("\n")
      .includes("encrypted"),
    false,
  );
});

test("collapses Codex turn-aborted markers into one concise event", () => {
  const doc = parse(
    [
      JSON.stringify({
        timestamp: "2026-05-25T10:00:00Z",
        type: "session_meta",
        payload: { id: "codex-session" },
      }),
      JSON.stringify({
        timestamp: "2026-05-25T10:00:01Z",
        type: "response_item",
        payload: {
          type: "message",
          role: "user",
          content: [
            {
              type: "input_text",
              text: [
                "<turn_aborted>",
                "The user interrupted the previous turn on purpose. Any running unified exec processes may still be running in the background.",
                "</turn_aborted>",
              ].join("\n"),
            },
          ],
        },
      }),
      JSON.stringify({
        timestamp: "2026-05-25T10:00:02Z",
        type: "event_msg",
        payload: {
          type: "turn_aborted",
          reason: "interrupted",
          duration_ms: 277039,
        },
      }),
    ].join("\n"),
  );
  assert.equal(doc.events.filter((event) => event.title === "Turn aborted").length, 1);
  assert.equal(
    doc.events.some((event) => event.kind === "message"),
    false,
  );
  assert.equal(doc.events[0]?.text, "Turn aborted by user.");
});

test("keeps Codex turn-aborted-shaped messages without event rows", () => {
  const marker = "<turn_aborted>\nExample only.\n</turn_aborted>";
  const doc = parse(
    [
      JSON.stringify({
        timestamp: "2026-05-25T10:00:00Z",
        type: "session_meta",
        payload: { id: "codex-session" },
      }),
      JSON.stringify({
        timestamp: "2026-05-25T10:00:01Z",
        type: "response_item",
        payload: {
          type: "message",
          role: "user",
          content: [{ type: "input_text", text: marker }],
        },
      }),
    ].join("\n"),
  );
  assert.equal(doc.events.length, 1);
  assert.equal(doc.events[0]?.kind, "message");
  assert.equal(doc.events[0]?.text, marker);
});

test("warns when a Codex session produces zero events", () => {
  const doc = parse(
    JSON.stringify({
      timestamp: "2026-05-25T10:00:00Z",
      type: "session_meta",
      payload: { id: "codex-session" },
    }),
  );
  assert.equal(doc.format, "codex");
  assert.equal(doc.events.length, 0);
  assert.ok(doc.warnings.includes("no Codex message events found"));
});

test("collapses memory citations into memory notes", () => {
  const citation = [
    "<oai-mem-citation>",
    "<citation_entries>",
    "MEMORY.md:89-97|note=[checked prior transcript-import context]",
    "</citation_entries>",
    "<rollout_ids>",
    "019e5515-7528-7393-80a4-d7a70dcb8e37",
    "</rollout_ids>",
    "</oai-mem-citation>",
  ].join("\n");
  const doc = parse(
    [
      JSON.stringify({
        timestamp: "2026-05-25T10:00:00Z",
        type: "session_meta",
        payload: { id: "codex-session" },
      }),
      JSON.stringify({
        timestamp: "2026-05-25T10:00:01Z",
        type: "response_item",
        payload: {
          type: "message",
          role: "assistant",
          content: [{ type: "output_text", text: `Done.\n\n${citation}` }],
        },
      }),
    ].join("\n"),
  );
  assert.equal(doc.events.length, 2);
  assert.equal(doc.events[0]?.kind, "message");
  assert.equal(doc.events[0]?.text, "Done.");
  assert.equal(doc.events[1]?.kind, "memory");
  assert.equal(doc.events[1]?.title, "Memory note");
  assert.equal(doc.events[1]?.text.includes("<oai-mem-citation>"), true);
});

test("keeps quoted memory citation examples in transcript text", () => {
  const citation = "<oai-mem-citation>example</oai-mem-citation>";
  const doc = parse(
    [
      JSON.stringify({
        timestamp: "2026-05-25T10:00:00Z",
        type: "session_meta",
        payload: { id: "codex-session" },
      }),
      JSON.stringify({
        timestamp: "2026-05-25T10:00:01Z",
        type: "response_item",
        payload: {
          type: "message",
          role: "user",
          content: [{ type: "input_text", text: `Please render ${citation} literally.` }],
        },
      }),
    ].join("\n"),
  );
  assert.equal(doc.events.length, 1);
  assert.equal(doc.events[0]?.kind, "message");
  assert.equal(doc.events[0]?.text.includes(citation), true);
});

test("only splits trailing memory citation footers", () => {
  const quoted = "<oai-mem-citation>quoted</oai-mem-citation>";
  const footer = "<oai-mem-citation>footer</oai-mem-citation>";
  const doc = parse(
    [
      JSON.stringify({
        timestamp: "2026-05-25T10:00:00Z",
        type: "session_meta",
        payload: { id: "codex-session" },
      }),
      JSON.stringify({
        timestamp: "2026-05-25T10:00:01Z",
        type: "response_item",
        payload: {
          type: "message",
          role: "assistant",
          content: [
            { type: "output_text", text: `Quoted example: ${quoted}\n\nDone.\n\n${footer}` },
          ],
        },
      }),
    ].join("\n"),
  );
  assert.equal(doc.events.length, 2);
  assert.equal(doc.events[0]?.text.includes(quoted), true);
  assert.equal(doc.events[0]?.text.includes(footer), false);
  assert.equal(doc.events[1]?.kind, "memory");
  assert.equal(doc.events[1]?.text, footer);
});

test("renders Codex image blocks as message attachments", () => {
  const image = "data:image/png;base64,iVBORw0KGgo=";
  const doc = parse(
    [
      JSON.stringify({
        timestamp: "2026-05-25T10:00:00Z",
        type: "session_meta",
        payload: { id: "codex-session" },
      }),
      JSON.stringify({
        timestamp: "2026-05-25T10:00:01Z",
        type: "response_item",
        payload: {
          type: "message",
          role: "user",
          content: [
            { type: "input_text", text: "<image name=[Image #1]>" },
            { type: "input_image", image_url: { url: image }, detail: "high" },
            { type: "input_text", text: "</image>" },
            { type: "input_text", text: "[Image #1] can we show the image?" },
          ],
        },
      }),
    ].join("\n"),
  );
  const event = doc.events.find((item) => item.kind === "message");
  assert.equal(event?.text, "can we show the image?");
  assert.equal(event?.images?.length, 1);
  assert.equal(event?.images?.[0]?.src, image);
  assert.equal(event?.images?.[0]?.detail, "high");
});

test("keeps literal image tags when no image block exists", () => {
  const doc = parse(
    [
      JSON.stringify({
        timestamp: "2026-05-25T10:00:00Z",
        type: "session_meta",
        payload: { id: "codex-session" },
      }),
      JSON.stringify({
        timestamp: "2026-05-25T10:00:01Z",
        type: "response_item",
        payload: {
          type: "message",
          role: "assistant",
          content: [{ type: "output_text", text: 'Use <image href="x.png"></image> in XML.' }],
        },
      }),
    ].join("\n"),
  );
  assert.equal(
    doc.events.find((item) => item.kind === "message")?.text,
    'Use <image href="x.png"></image> in XML.',
  );
});

test("keeps literal image tags beside image attachments", () => {
  const image = "data:image/png;base64,iVBORw0KGgo=";
  const doc = parse(
    [
      JSON.stringify({
        timestamp: "2026-05-25T10:00:00Z",
        type: "session_meta",
        payload: { id: "codex-session" },
      }),
      JSON.stringify({
        timestamp: "2026-05-25T10:00:01Z",
        type: "response_item",
        payload: {
          type: "message",
          role: "user",
          content: [
            { type: "input_image", image_url: image },
            { type: "input_text", text: 'Use <image href="x.png"></image> in XML.' },
          ],
        },
      }),
    ].join("\n"),
  );
  const event = doc.events.find((item) => item.kind === "message");
  assert.equal(event?.text, 'Use <image href="x.png"></image> in XML.');
  assert.equal(event?.images?.[0]?.src, image);
});

test("parses Claude Code tool use and result blocks", () => {
  const doc = parse(
    [
      JSON.stringify({ type: "summary", summary: "Fix parser" }),
      JSON.stringify({
        type: "assistant",
        timestamp: "2026-05-25T10:00:00Z",
        message: {
          role: "assistant",
          content: [
            { type: "text", text: "running ls" },
            { type: "tool_use", id: "toolu-1", name: "Bash", input: { command: "ls" } },
          ],
        },
      }),
      JSON.stringify({
        type: "user",
        timestamp: "2026-05-25T10:00:01Z",
        message: {
          role: "user",
          content: [{ type: "tool_result", tool_use_id: "toolu-1", content: "ok" }],
        },
      }),
    ].join("\n"),
  );
  assert.equal(doc.format, "claude");
  assert.equal(doc.title, "Fix parser");
  assert.equal(doc.events.filter((event) => event.kind === "tool_call").length, 1);
  assert.equal(doc.events.filter((event) => event.kind === "tool_result").length, 1);
});

test("keeps Claude thinking content blocks", () => {
  const doc = parse(
    [
      JSON.stringify({
        type: "assistant",
        timestamp: "2026-05-25T10:00:00Z",
        message: {
          role: "assistant",
          content: [{ type: "thinking", content: "visible thinking" }],
        },
      }),
    ].join("\n"),
  );
  assert.equal(doc.format, "claude");
  assert.equal(doc.events.filter((event) => event.kind === "reasoning").length, 1);
  assert.equal(doc.events.find((event) => event.kind === "reasoning")?.text, "visible thinking");
});

test("parses Pi/OpenClaw message and tool result entries", () => {
  const doc = parse(
    [
      JSON.stringify({
        type: "session",
        id: "openclaw-session",
        timestamp: "2026-05-25T10:00:00Z",
      }),
      JSON.stringify({
        type: "message",
        id: "m1",
        message: {
          role: "assistant",
          content: [
            { type: "text", text: "I will check." },
            { type: "toolCall", id: "call-1", name: "read", arguments: { path: "a.ts" } },
          ],
        },
      }),
      JSON.stringify({
        type: "message",
        id: "m2",
        message: {
          role: "toolResult",
          toolCallId: "call-1",
          toolName: "read",
          content: [{ type: "text", text: "contents" }],
        },
      }),
    ].join("\n"),
  );
  assert.equal(doc.format, "pi-openclaw");
  assert.equal(
    doc.events.some((event) => event.kind === "message" && event.text.includes("check")),
    true,
  );
  assert.equal(
    doc.events.some((event) => event.kind === "tool_call"),
    true,
  );
  assert.equal(
    doc.events.some((event) => event.kind === "tool_result"),
    true,
  );
});

test("keeps Pi/OpenClaw numeric message timestamps", () => {
  const doc = parse(
    JSON.stringify({
      type: "message",
      id: "m1",
      message: { role: "assistant", timestamp: 1748165000000, content: [{ type: "text", text: "ok" }] },
    }),
  );
  assert.equal(doc.format, "pi-openclaw");
  assert.equal(doc.events[0]?.timestamp, "2025-05-25T09:23:20.000Z");
});

test("drops out-of-range Pi/OpenClaw numeric message timestamps", () => {
  for (const timestamp of [1e300, Number.NaN, Number.POSITIVE_INFINITY, -8.64e15 - 1]) {
    const doc = parse(
      JSON.stringify({
        type: "message",
        id: "m1",
        message: { role: "assistant", timestamp, content: [{ type: "text", text: "ok" }] },
      }),
    );
    assert.equal(doc.format, "pi-openclaw");
    assert.equal(doc.events.length, 1);
    assert.equal(doc.events[0]?.timestamp, undefined);
  }
});

test("parses Pi/OpenClaw direct image data blocks", () => {
  const doc = parse(
    [
      JSON.stringify({
        type: "session",
        id: "openclaw-session",
      }),
      JSON.stringify({
        type: "message",
        id: "m1",
        message: {
          role: "user",
          content: [
            { type: "image", data: "iVBORw0KGgo=", mimeType: "image/png" },
            { type: "text", text: "screenshot" },
          ],
        },
      }),
    ].join("\n"),
  );
  const event = doc.events.find((item) => item.kind === "message");
  assert.equal(event?.text, "screenshot");
  assert.equal(event?.images?.[0]?.src, "data:image/png;base64,iVBORw0KGgo=");
});

test("keeps Pi/OpenClaw relative media URL image-only turns", () => {
  const doc = parse(
    [
      JSON.stringify({
        type: "session",
        id: "openclaw-session",
      }),
      JSON.stringify({
        type: "message",
        id: "m1",
        message: {
          role: "user",
          content: [{ type: "image", url: "/api/chat/media/image-1.png" }],
        },
      }),
    ].join("\n"),
  );
  const event = doc.events.find((item) => item.kind === "message");
  assert.equal(event?.text, "");
  assert.equal(event?.images?.[0]?.src, "/api/chat/media/image-1.png");
});

test("keeps Pi/OpenClaw protocol-relative media URL image-only turns", () => {
  const doc = parse(
    [
      JSON.stringify({
        type: "session",
        id: "openclaw-session",
      }),
      JSON.stringify({
        type: "message",
        id: "m1",
        message: {
          role: "user",
          content: [{ type: "image", url: "//cdn.example.test/photo.webp" }],
        },
      }),
    ].join("\n"),
  );
  const event = doc.events.find((item) => item.kind === "message");
  assert.equal(event?.text, "");
  assert.equal(event?.images?.[0]?.src, "//cdn.example.test/photo.webp");
});

test("keeps Pi/OpenClaw bare relative media path image-only turns", () => {
  const doc = parse(
    [
      JSON.stringify({
        type: "session",
        id: "openclaw-session",
      }),
      JSON.stringify({
        type: "message",
        id: "m1",
        message: {
          role: "user",
          content: [{ type: "image", url: "media/inbound/photo.png" }],
        },
      }),
    ].join("\n"),
  );
  const event = doc.events.find((item) => item.kind === "message");
  assert.equal(event?.text, "");
  assert.equal(event?.images?.[0]?.src, "media/inbound/photo.png");
});

test("rejects active-scheme image URLs", () => {
  const doc = parse(
    [
      JSON.stringify({
        type: "session",
        id: "openclaw-session",
      }),
      JSON.stringify({
        type: "message",
        id: "m1",
        message: {
          role: "user",
          content: [{ type: "image", url: "javascript:alert(1).png" }],
        },
      }),
    ].join("\n"),
  );
  assert.equal(doc.events.length, 0);
});

test("keeps Pi/OpenClaw message-level media path image-only turns", () => {
  const doc = parse(
    [
      JSON.stringify({
        type: "session",
        id: "openclaw-session",
      }),
      JSON.stringify({
        type: "message",
        id: "m1",
        message: {
          role: "user",
          content: "",
          MediaPaths: ["/tmp/a.png"],
          MediaTypes: ["image/png"],
        },
      }),
    ].join("\n"),
  );
  const event = doc.events.find((item) => item.kind === "message");
  assert.equal(event?.text, "");
  assert.equal(event?.images?.[0]?.src, "/tmp/a.png");
});

test("keeps Pi/OpenClaw message-level media URL image-only turns", () => {
  const doc = parse(
    [
      JSON.stringify({
        type: "session",
        id: "openclaw-session",
      }),
      JSON.stringify({
        type: "message",
        id: "m1",
        message: {
          role: "user",
          content: "",
          MediaUrls: ["https://example.com/photo.png"],
          MediaUrl: "https://example.com/photo.png",
          MediaTypes: ["image/png"],
        },
      }),
    ].join("\n"),
  );
  const event = doc.events.find((item) => item.kind === "message");
  assert.equal(event?.text, "");
  assert.equal(event?.images?.length, 1);
  assert.equal(event?.images?.[0]?.src, "https://example.com/photo.png");
});

test("keeps Pi/OpenClaw media refs aligned with media types", () => {
  const doc = parse(
    [
      JSON.stringify({
        type: "session",
        id: "openclaw-session",
      }),
      JSON.stringify({
        type: "message",
        id: "m1",
        message: {
          role: "user",
          content: "",
          MediaPaths: ["", "/tmp/photo.png"],
          MediaUrls: ["https://cdn.example/audio.mp3", "/tmp/photo.png"],
          MediaTypes: ["audio/mpeg", "image/png"],
        },
      }),
    ].join("\n"),
  );
  const event = doc.events.find((item) => item.kind === "message");
  assert.equal(event?.images?.length, 1);
  assert.equal(event?.images?.[0]?.src, "/tmp/photo.png");
  assert.equal(event?.images?.[0]?.detail, "image/png");
});

test("does not apply shifted Pi/OpenClaw media types to earlier refs", () => {
  const doc = parse(
    [
      JSON.stringify({
        type: "session",
        id: "openclaw-session",
      }),
      JSON.stringify({
        type: "message",
        id: "m1",
        message: {
          role: "user",
          content: "",
          MediaPaths: ["audio.bin", "photo.bin"],
          MediaTypes: ["image/png"],
        },
      }),
    ].join("\n"),
  );
  assert.equal(doc.events.length, 0);
});

test("rejects active-scheme Pi/OpenClaw message-level media refs", () => {
  const doc = parse(
    [
      JSON.stringify({
        type: "session",
        id: "openclaw-session",
      }),
      JSON.stringify({
        type: "message",
        id: "m1",
        message: {
          role: "user",
          content: "",
          MediaPath: "javascript:alert(1).png",
          MediaType: "image/png",
        },
      }),
    ].join("\n"),
  );
  assert.equal(doc.events.length, 0);
});

test("keeps Windows Pi/OpenClaw message-level image paths", () => {
  const doc = parse(
    [
      JSON.stringify({
        type: "session",
        id: "openclaw-session",
      }),
      JSON.stringify({
        type: "message",
        id: "m1",
        message: {
          role: "user",
          content: "",
          MediaPath: "C:\\OpenClaw QA\\photo.png",
          MediaType: "image/png",
        },
      }),
    ].join("\n"),
  );
  const event = doc.events.find((item) => item.kind === "message");
  assert.equal(event?.images?.[0]?.src, "C:\\OpenClaw QA\\photo.png");
});

test("parses Pi/OpenClaw tool result image blocks", () => {
  const doc = parse(
    [
      JSON.stringify({
        type: "session",
        id: "openclaw-session",
      }),
      JSON.stringify({
        type: "message",
        id: "m1",
        message: {
          role: "toolResult",
          toolCallId: "call-1",
          content: [
            { type: "image", data: "iVBORw0KGgo=", mimeType: "image/png" },
            { type: "text", text: "generated" },
          ],
        },
      }),
    ].join("\n"),
  );
  const event = doc.events.find((item) => item.kind === "tool_result");
  assert.equal(event?.text, "generated");
  assert.equal(event?.images?.[0]?.src, "data:image/png;base64,iVBORw0KGgo=");
});

test("keeps visible Pi/OpenClaw thinking blocks", () => {
  const doc = parse(
    [
      JSON.stringify({
        type: "session",
        id: "openclaw-session",
      }),
      JSON.stringify({
        type: "message",
        id: "m1",
        message: {
          role: "assistant",
          content: [{ type: "thinking", thinking: "visible reasoning" }],
        },
      }),
    ].join("\n"),
  );
  assert.equal(doc.format, "pi-openclaw");
  assert.equal(doc.events.filter((event) => event.kind === "reasoning").length, 1);
  assert.equal(doc.events.find((event) => event.kind === "reasoning")?.text, "visible reasoning");
});

test("CLI writes a one-file HTML export", async () => {
  const dir = await fs.mkdtemp(path.join(os.tmpdir(), "session-viewer-"));
  const input = path.join(dir, "session.jsonl");
  const output = path.join(dir, "session.html");
  await fs.writeFile(
    input,
    JSON.stringify({
      timestamp: "2026-05-25T10:00:00Z",
      type: "session_meta",
      payload: { id: "codex-session", cwd: dir },
    }) +
      "\n" +
      JSON.stringify({
        timestamp: "2026-05-25T10:00:01Z",
        type: "response_item",
        payload: {
          type: "message",
          role: "assistant",
          content: [{ type: "output_text", text: "exported" }],
        },
      }) +
      "\n",
    "utf8",
  );
  await execFileAsync(process.execPath, [
    "skills/session-viewer/scripts/session-viewer.ts",
    input,
    "--out",
    output,
  ]);
  const html = await fs.readFile(output, "utf8");
  assert.match(html, /Session Viewer/);
  assert.match(html, /viewer-payload/);
  const payload = /<script id="viewer-payload" type="application\/json">([^<]*)<\/script>/u.exec(
    html,
  )?.[1];
  assert.ok(payload);
  assert.equal(JSON.parse(payload).kind, "normalized");
});

// Event ids become DOM `id=` attributes and the sidebar jumps by
// getElementById (html.ts), so a collision silently scrolls to the wrong block.
// Both parsers and both browser-only format branches must keep them unique.
test("both parsers give every event a unique id when one record holds two thinking blocks", () => {
  const fixtures = [
    [
      "Claude",
      JSON.stringify({
        type: "assistant",
        uuid: "e1",
        message: {
          role: "assistant",
          content: [
            { type: "thinking", thinking: "first thought" },
            { type: "thinking", thinking: "second thought" },
          ],
        },
      }),
    ],
    [
      "Pi/OpenClaw",
      [
        JSON.stringify({ type: "session", id: "openclaw-session" }),
        JSON.stringify({
          type: "message",
          id: "m1",
          message: {
            role: "assistant",
            content: [
              { type: "thinking", thinking: "first thought" },
              { type: "thinking", thinking: "second thought" },
            ],
          },
        }),
      ].join("\n"),
    ],
  ] as const;
  const { parseRaw } = extractClientScript();
  for (const [format, record] of fixtures) {
    for (const [side, doc] of [["server", parse(record)], ["client", parseRaw(record, "fixture.jsonl")]] as const) {
      const reasoning = doc.events.filter((event: any) => event.kind === "reasoning");
      assert.equal(reasoning.length, 2, `${format} ${side} should emit both thinking blocks`);
      const ids = doc.events.map((event: any) => event.id);
      assert.equal(new Set(ids).size, ids.length, `${format} ${side} emitted duplicate event ids: ${ids.join(", ")}`);
    }
  }
});

test("client-side raw parser excludes tool_result blocks from merged Claude message text", () => {
  const { parseRaw } = extractClientScript();
  const doc = parseRaw(
    JSON.stringify({
      type: "user",
      message: {
        role: "user",
        content: [
          { type: "text", text: "please continue" },
          { type: "tool_result", tool_use_id: "call1", content: "SECRET_TOOL_OUTPUT" },
        ],
      },
    }),
  );
  assert.equal(doc.format, "claude");
  const message = doc.events.find((event: any) => event.kind === "message");
  assert.equal(message?.text, "please continue");
  assert.doesNotMatch(message?.text ?? "", /SECRET_TOOL_OUTPUT/);
  const result = doc.events.find((event: any) => event.kind === "tool_result");
  assert.equal(result?.text, "SECRET_TOOL_OUTPUT");
});

test("client-side raw parser derives Codex function_call_output status from the process exit code", () => {
  const { parseRaw } = extractClientScript();
  const doc = parseRaw(
    [
      JSON.stringify({ type: "session_meta", payload: { id: "x" } }),
      JSON.stringify({
        type: "response_item",
        payload: { type: "function_call_output", call_id: "c1", output: "Process exited with code 0" },
      }),
      JSON.stringify({
        type: "response_item",
        payload: { type: "function_call_output", call_id: "c2", output: "Process exited with code 1" },
      }),
    ].join("\n"),
  );
  const results = doc.events.filter((event: any) => event.kind === "tool_result");
  assert.equal(results.find((event: any) => event.callId === "c1")?.status, "ok");
  assert.equal(results.find((event: any) => event.callId === "c2")?.status, "error");
});

test("client-side raw parser reads reasoning summary text from either field name", () => {
  const { parseRaw } = extractClientScript();
  const doc = parseRaw(
    [
      JSON.stringify({ type: "session_meta", payload: { id: "x" } }),
      JSON.stringify({
        type: "response_item",
        payload: { type: "reasoning", summary: [{ summary: "design approach" }] },
      }),
    ].join("\n"),
  );
  const reasoning = doc.events.find((event: any) => event.kind === "reasoning");
  assert.equal(reasoning?.text, "design approach");
});

// --- Parity regressions: the client parseRaw must mirror the server importers. ---

const abortMarkerText = [
  "<turn_aborted>",
  "The user interrupted the previous turn on purpose. Any running unified exec processes may still be running in the background.",
  "</turn_aborted>",
].join("\n");

test("client codex branch mirrors server turn_context, event_msg, unknown items, roles, and abort dedup", () => {
  const abortUser = JSON.stringify({
    type: "response_item",
    payload: { type: "message", role: "user", content: [{ type: "input_text", text: abortMarkerText }] },
  });
  const abortEvent = JSON.stringify({ type: "event_msg", payload: { type: "turn_aborted" } });
  const text = [
    JSON.stringify({ type: "session_meta", payload: { id: "codex-session" } }),
    JSON.stringify({ type: "turn_context", payload: { cwd: "/tmp/x", model: "gpt-5" } }),
    JSON.stringify({
      type: "response_item",
      payload: { type: "message", role: "user", content: [{ type: "input_text", text: "hello" }] },
    }),
    JSON.stringify({ type: "event_msg", payload: { type: "task_started" } }),
    JSON.stringify({ type: "event_msg", payload: { type: "agent_message", message: "working on it" } }),
    JSON.stringify({ type: "response_item", payload: { type: "ghost_item", data: "x" } }),
    JSON.stringify({
      type: "response_item",
      payload: { type: "message", role: "system", content: [{ type: "input_text", text: "system note" }] },
    }),
    JSON.stringify({
      type: "response_item",
      payload: { type: "message", role: "developer", content: [{ type: "input_text", text: "dev note" }] },
    }),
    abortUser,
    abortEvent,
    abortUser,
    abortEvent,
    JSON.stringify({ type: "event_msg" }),
    JSON.stringify({ type: "response_item", payload: "oops" }),
  ].join("\n");
  const server = parseWithJsonlWarnings(text);
  const { parseRaw } = extractClientScript();
  const client = parseRaw(text, "fixture.jsonl");
  assert.equal(server.format, "codex");
  assert.equal(client.format, "codex");
  assert.deepEqual(eventShape(client as any), eventShape(server));
  assert.deepEqual(Array.from(client.warnings), server.warnings);
  assert.deepEqual(server.warnings, ["line 14: response_item without object payload"]);
  const titles = server.events.map((event) => event.title);
  assert.ok(titles.includes("turn context"));
  assert.ok(titles.includes("event: agent_message"));
  assert.ok(titles.includes("response item: ghost_item"));
  assert.equal(server.events.filter((event) => event.title === "Turn aborted").length, 1);
  assert.equal(client.events.filter((event: any) => event.title === "Turn aborted").length, 1);
  const systemRoles = server.events.filter((event) => event.kind === "system").map((event) => event.role);
  assert.deepEqual(systemRoles, [undefined, "system", "developer"]);
});

test("client claude branch mirrors server summary meta and top-level text fallback", () => {
  const text = [
    JSON.stringify({ type: "summary", summary: "Session about parsers" }),
    JSON.stringify({
      type: "user",
      timestamp: "2026-05-25T10:00:00Z",
      message: { role: "user", content: [{ type: "text", text: "hi" }] },
    }),
    JSON.stringify({ type: "system", timestamp: "2026-05-25T10:00:01Z", text: "top-level system note" }),
    JSON.stringify({ type: "system", content: "string content system" }),
  ].join("\n");
  const server = parseWithJsonlWarnings(text);
  const { parseRaw } = extractClientScript();
  const client = parseRaw(text, "fixture.jsonl");
  assert.equal(server.format, "claude");
  assert.equal(client.format, "claude");
  assert.equal(server.title, "Session about parsers");
  assert.equal(client.title, "Session about parsers");
  assert.deepEqual(eventShape(client as any), eventShape(server));
  // Server-side kind regression: system records must not be labeled "message".
  const systems = server.events.filter((event) => event.kind === "system").map((event) => event.text);
  assert.deepEqual(systems, ["top-level system note", "string content system"]);
});

test("client pi branch mirrors server system kind, entry events, and timestamp fallbacks", () => {
  const text = [
    JSON.stringify({ type: "session", id: "openclaw-session", timestamp: "2026-01-01T00:00:00Z" }),
    JSON.stringify({
      type: "message",
      id: "m1",
      createdAt: "2026-01-02T00:00:00Z",
      message: { role: "system", content: "sys prompt" },
    }),
    JSON.stringify({
      type: "message",
      id: "m2",
      message: { role: "user", content: "hi", timestamp: 1767312000000 },
    }),
    JSON.stringify({ type: "custom", id: "x1", updatedAt: "2026-01-03T00:00:00Z", note: "hello" }),
    JSON.stringify({ type: "label", id: "L1" }),
  ].join("\n");
  const server = parseWithJsonlWarnings(text);
  const { parseRaw } = extractClientScript();
  const client = parseRaw(text, "fixture.jsonl");
  assert.equal(server.format, "pi-openclaw");
  assert.equal(client.format, "pi-openclaw");
  assert.deepEqual(eventShape(client as any), eventShape(server));
  assert.deepEqual(
    Array.from(client.events, (event: any) => event.id),
    server.events.map((event) => event.id),
  );
  const shapes = eventShape(server);
  assert.deepEqual(shapes.map((event) => [event.kind, event.title, event.timestamp]), [
    ["system", "system", "2026-01-02T00:00:00Z"],
    ["message", "user", new Date(1767312000000).toISOString()],
    ["event", "entry: custom", "2026-01-03T00:00:00Z"],
  ]);
});

test("client renders unknown-format rows and per-line parse warnings like the server", () => {
  const text = ['{"note":"mystery"}', "[1,2]", "{oops"].join("\n");
  const server = parseWithJsonlWarnings(text);
  const { parseRaw } = extractClientScript();
  const client = parseRaw(text, "fixture.jsonl");
  assert.equal(server.format, "unknown");
  assert.equal(client.format, "unknown");
  assert.deepEqual(
    Array.from(client.events, (event: any) => [event.id, event.kind, event.title, event.text]),
    server.events.map((event) => [event.id, event.kind, event.title, event.text]),
  );
  assert.equal(server.events.length, 2);
  assert.equal(server.events[0]?.title, "raw line 1");
  assert.deepEqual(Array.from(client.warnings), server.warnings);
  assert.equal(server.warnings.length, 2);
  assert.match(server.warnings[0] ?? "", /^line 3: invalid JSON: /u);
  assert.equal(server.warnings[1], "unknown session format; rendered raw JSONL rows");
});

test("codex tool-result statuses prefer structured exit codes and anchored/conservative markers", () => {
  const text = [
    JSON.stringify({ type: "session_meta", payload: { id: "codex-session" } }),
    JSON.stringify({
      type: "response_item",
      payload: {
        type: "function_call_output",
        call_id: "c1",
        output: JSON.stringify({
          output: "the phrase Process exited with code 1 appears quoted here",
          metadata: { exit_code: 0 },
        }),
      },
    }),
    JSON.stringify({
      type: "response_item",
      payload: {
        type: "function_call_output",
        call_id: "c2",
        output: "Log says 'Process exited with code 1' earlier today, all fine",
      },
    }),
    JSON.stringify({
      type: "response_item",
      payload: { type: "function_call_output", call_id: "c3", output: "Process exited with code 2\ndetails" },
    }),
    JSON.stringify({
      type: "response_item",
      payload: { type: "function_call_output", call_id: "c4", output: "tail output\nProcess exited with code 0" },
    }),
    JSON.stringify({
      type: "response_item",
      payload: {
        type: "custom_tool_call_output",
        call_id: "c5",
        output: "Compiled successfully; zero error handling issues found",
      },
    }),
    JSON.stringify({
      type: "response_item",
      payload: { type: "custom_tool_call_output", call_id: "c6", output: "Error: could not open file" },
    }),
    JSON.stringify({
      type: "response_item",
      payload: { type: "custom_tool_call_output", call_id: "c7", output: JSON.stringify({ error: "boom" }) },
    }),
  ].join("\n");
  const expected: Record<string, string> = {
    c1: "ok",
    c2: "unknown",
    c3: "error",
    c4: "ok",
    c5: "unknown",
    c6: "error",
    c7: "error",
  };
  const server = parse(text);
  const { parseRaw } = extractClientScript();
  const client = parseRaw(text, "fixture.jsonl");
  for (const [side, doc] of [["server", server], ["client", client]] as const) {
    for (const [callId, status] of Object.entries(expected)) {
      const event = doc.events.find((item: any) => item.callId === callId);
      assert.equal(event?.status, status, `${side} status for ${callId}`);
    }
  }
});

test("server keeps text from unknown content-block types like the client", () => {
  const text = [
    JSON.stringify({ type: "session_meta", payload: { id: "codex-session" } }),
    JSON.stringify({
      type: "response_item",
      payload: {
        type: "message",
        role: "assistant",
        content: [
          { type: "output_text", text: "ok" },
          { type: "refusal_text", text: "declined" },
          { type: "future_text", input: "from-input" },
        ],
      },
    }),
  ].join("\n");
  const server = parse(text);
  const { parseRaw } = extractClientScript();
  const client = parseRaw(text, "fixture.jsonl");
  assert.equal(server.events.find((event) => event.kind === "message")?.text, "ok\n\ndeclined\n\nfrom-input");
  assert.equal(client.events.find((event: any) => event.kind === "message")?.text, "ok\n\ndeclined\n\nfrom-input");
});

test("search highlighting never splits HTML entities", () => {
  const { highlight, inlineMarkdown, state } = extractClientScript();
  state.query = "amp";
  assert.equal(highlight("amplifier & speaker"), "<mark>amp</mark>lifier &amp; speaker");
  assert.equal(inlineMarkdown("amplifier & speaker"), "<mark>amp</mark>lifier &amp; speaker");
  state.query = "quot";
  assert.equal(highlight('a "quoted" word'), "a &quot;<mark>quot</mark>ed&quot; word");
  state.query = "lt.";
  assert.equal(highlight("result: a < b. lt. done"), "result: a &lt; b. <mark>lt.</mark> done");
  state.query = "gt;";
  assert.equal(highlight("x > y"), "x &gt; y");
  state.query = "";
});

test("inferHomePath does not cross whitespace when matching home directories", () => {
  const { inferHomePath } = extractClientScript();
  assert.equal(inferHomePath({ meta: {}, events: [{ text: "check /Users/bob and stuff" }] }), "/Users/bob");
  assert.equal(inferHomePath({ meta: {}, events: [{ text: "cwd is /home/worker/repo today" }] }), "/home/worker");
  assert.equal(inferHomePath({ meta: { cwd: "/Users/alice/projects/app" }, events: [] }), "/Users/alice");
});
