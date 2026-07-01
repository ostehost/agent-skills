import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";

const script = path.resolve("skills/agent-transcript/scripts/agent-transcript");

function tempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), "agent-transcript-test-"));
}

function writeJsonl(file, rows) {
  fs.writeFileSync(file, `${rows.map((row) => JSON.stringify(row)).join("\n")}\n`);
}

function run(args, options = {}) {
  return execFileSync(process.execPath, [script, ...args], {
    cwd: path.resolve("."),
    encoding: "utf8",
    ...options,
  });
}

function runFailure(args, options = {}) {
  try {
    run(args, options);
  } catch (error) {
    if (error.status == null) throw error;
    return { status: error.status, stderr: error.stderr || "" };
  }
  throw new Error(`expected command to fail: ${args.join(" ")}`);
}

test("render redacts common secrets and local identifiers", () => {
  const dir = tempDir();
  const session = path.join(dir, "session.jsonl");
  writeJsonl(session, [
    {
      type: "response_item",
      payload: {
        role: "user",
        content: [
          {
            type: "text",
            text: "Use /Users/ahmed/project, email person@example.com, and header Bearer abcdefghijklmnopqrstuvwxyz123456.",
          },
        ],
      },
    },
    { type: "response_item", payload: { role: "assistant", content: [{ type: "text", text: "Done." }] } },
  ]);

  const output = run(["render", "--session", session]);
  assert.match(output, /\[LOCAL_PATH\]/);
  assert.match(output, /\[REDACTED_EMAIL\]/);
  assert.match(output, /\[REDACTED_AUTH_HEADER\]/);
  assert.doesNotMatch(output, /person@example\.com/);
  assert.doesNotMatch(output, /abcdefghijklmnopqrstuvwxyz123456/);
});

test("render drops raw tool outputs but keeps a compact tool summary", () => {
  const dir = tempDir();
  const session = path.join(dir, "session.jsonl");
  writeJsonl(session, [
    { type: "response_item", payload: { role: "user", content: [{ type: "text", text: "Run tests." }] } },
    {
      type: "response_item",
      payload: { type: "function_call", name: "exec_command", arguments: JSON.stringify({ cmd: "rg foo" }) },
    },
    {
      type: "response_item",
      payload: { type: "function_call_output", output: "raw output with sk-abcdefghijklmnopqrstuvwxyz123456" },
    },
  ]);

  const output = run(["render", "--session", session]);
  assert.match(output, /tool summary/);
  // Exercises the JSON.parse + shellFamily("rg foo") path, not the catch-fallback
  // (a bare-string `arguments` value would hit the fallback and also read "execute").
  assert.match(output, /1 read/);
  assert.doesNotMatch(output, /raw output/);
  assert.doesNotMatch(output, /sk-abcdefghijklmnopqrstuvwxyz123456/);
});

test("append-body replaces an existing transcript section", () => {
  const dir = tempDir();
  const session = path.join(dir, "session.jsonl");
  const body = path.join(dir, "body.md");
  writeJsonl(session, [
    { type: "response_item", payload: { role: "user", content: [{ type: "text", text: "New scoped work." }] } },
    { type: "response_item", payload: { role: "assistant", content: [{ type: "text", text: "Implemented." }] } },
  ]);
  fs.writeFileSync(
    body,
    "# PR\n\n<!-- agent-transcript:start -->\nold transcript\n<!-- agent-transcript:end -->\n"
  );

  const output = run(["append-body", "--body", body, "--session", session]);
  assert.match(output, /# PR/);
  assert.match(output, /New scoped work/);
  assert.doesNotMatch(output, /old transcript/);
  assert.equal((output.match(/agent-transcript:start/g) || []).length, 1);
});

test("render fails closed when a redaction-missed secret marker survives into the transcript", () => {
  const dir = tempDir();
  const session = path.join(dir, "session.jsonl");
  writeJsonl(session, [
    { type: "response_item", payload: { role: "user", content: [{ type: "text", text: "Fix the bug." }] } },
  ]);

  // The --title header is redact()ed for display but was never covered by the
  // fail-closed unsafe() check before this test was added: unsafe()'s pattern for
  // bare GITHUB_TOKEN mentions has no matching redact() rule, so it should trip
  // the gate rather than land silently in the transcript.
  const { status, stderr } = runFailure(["render", "--session", session, "--title", "rotate leaked GITHUB_TOKEN"]);
  assert.notEqual(status, 0);
  assert.match(stderr, /unsafe transcript after redaction/);
});

test("render still succeeds when the title contains a value redact() safely handles", () => {
  const dir = tempDir();
  const session = path.join(dir, "session.jsonl");
  writeJsonl(session, [
    { type: "response_item", payload: { role: "user", content: [{ type: "text", text: "Fix the bug." }] } },
  ]);

  // The header safety check must run on the *redacted* title/url, not the raw
  // value -- otherwise ordinary PII that redact() handles fine (an email here)
  // would incorrectly trip the fail-closed gate.
  const output = run(["render", "--session", session, "--title", "contact person@example.com about this"]);
  assert.match(output, /\[REDACTED_EMAIL\]/);
  assert.doesNotMatch(output, /person@example\.com/);
});

test("html command omits an unsafe record's markdown instead of embedding it", () => {
  const dir = tempDir();
  const sessionsDir = path.join(dir, "sessions");
  fs.mkdirSync(sessionsDir, { recursive: true });
  const session = path.join(sessionsDir, "session.jsonl");
  writeJsonl(session, [
    { type: "response_item", payload: { role: "user", content: [{ type: "text", text: "Fix the bug." }] } },
  ]);

  const prsFile = path.join(dir, "prs.json");
  fs.writeFileSync(
    prsFile,
    JSON.stringify([{ title: "rotate leaked GITHUB_TOKEN", url: "https://example.com/pr/1", number: 1 }])
  );

  // --min-score 0 sidesteps the query/session term-matching heuristic (irrelevant
  // to this test) so the single fixture session is always the chosen candidate.
  const output = run(["html", "--prs", prsFile, "--root", sessionsDir, "--min-score", "0"]);
  assert.match(output, /unsafe transcript after redaction/);
  assert.doesNotMatch(output, /Fix the bug\./);
});

test("find scores sessions by query term matches", () => {
  const dir = tempDir();
  const root = path.join(dir, "root");
  fs.mkdirSync(root, { recursive: true });
  const session = path.join(root, "session.jsonl");
  writeJsonl(session, [
    { type: "response_item", payload: { role: "user", content: [{ type: "text", text: "debugging the frobnicator widget" }] } },
  ]);

  const output = run(["find", "--query", "frobnicator widget", "--root", root, "--since-days", "3650"]);
  const results = JSON.parse(output);
  assert.equal(results.length, 1);
  assert.equal(results[0].file, session);
  assert.ok(results[0].score > 0);
});
