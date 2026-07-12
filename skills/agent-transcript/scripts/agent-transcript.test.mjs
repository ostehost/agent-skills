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
            text: [
              "Use /Users/ahmed/project and /home/lin/project,",
              "email person@example.com, header Bearer abcdefghijklmnopqrstuvwxyz123456,",
              "and https://example.com/callback?token=secret-value.",
            ].join(" "),
          },
        ],
      },
    },
    { type: "response_item", payload: { role: "assistant", content: [{ type: "text", text: "Done." }] } },
  ]);

  const output = run(["render", "--session", session]);
  assert.match(output, /\[LOCAL_PATH\]/);
  assert.match(output, /\[LINUX_HOME_PATH\]/);
  assert.match(output, /\[REDACTED_EMAIL\]/);
  assert.match(output, /\[REDACTED_AUTH_HEADER\]/);
  assert.match(output, /token=\[REDACTED\]/);
  assert.doesNotMatch(output, /person@example\.com/);
  assert.doesNotMatch(output, /abcdefghijklmnopqrstuvwxyz123456/);
  assert.doesNotMatch(output, /secret-value/);
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

test("render fails closed when an unsafe title survives redaction", () => {
  const dir = tempDir();
  const session = path.join(dir, "session.jsonl");
  const output = path.join(dir, "transcript.md");
  writeJsonl(session, [
    { type: "response_item", payload: { role: "user", content: [{ type: "text", text: "Fix the bug." }] } },
  ]);

  const { status, stderr } = runFailure([
    "render",
    "--session",
    session,
    "--title",
    "rotate leaked GITHUB_TOKEN",
    "--out",
    output,
  ]);
  assert.notEqual(status, 0);
  assert.match(stderr, /unsafe transcript after redaction/);
  assert.equal(fs.existsSync(output), false, "unsafe output must not be written");
});

test("render redacts safe title and URL values before checking them", () => {
  const dir = tempDir();
  const session = path.join(dir, "session.jsonl");
  writeJsonl(session, [
    { type: "response_item", payload: { role: "user", content: [{ type: "text", text: "Fix the bug." }] } },
  ]);

  const output = run([
    "render",
    "--session",
    session,
    "--title",
    "contact person@example.com",
    "--url",
    "https://example.com/pr/1?access_token=secret-value",
  ]);
  assert.match(output, /\[REDACTED_EMAIL\]/);
  assert.match(output, /access_token=\[REDACTED\]/);
  assert.doesNotMatch(output, /person@example\.com|secret-value/);
});

test("html omits unsafe record markdown instead of embedding it", () => {
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

  const output = run(["html", "--prs", prsFile, "--root", sessionsDir, "--min-score", "0"]);
  assert.match(output, /unsafe transcript after redaction/);
  assert.doesNotMatch(output, /Fix the bug\./);
});

test("find scans CLAUDE_CONFIG_DIR projects and labels them as Claude", () => {
  const dir = tempDir();
  const home = tempDir();
  const projectDir = path.join(dir, "projects", "-tmp-agent-transcript");
  fs.mkdirSync(projectDir, { recursive: true });
  const session = path.join(projectDir, "11111111-2222-4333-8444-555555555555.jsonl");
  writeJsonl(session, [
    { type: "user", message: { role: "user", content: "claude-config-dir-marker" } },
    { type: "assistant", message: { role: "assistant", content: "Done." } },
  ]);

  const output = run(["find", "--query", "claude-config-dir-marker", "--since-days", "1", "--max-files", "20"], {
    env: { ...process.env, HOME: home, CLAUDE_CONFIG_DIR: `${dir}${path.sep}` },
  });
  const matches = JSON.parse(output);

  assert.equal(matches.length, 1);
  assert.equal(matches[0].file, session);
  assert.equal(matches[0].agent, "claude");
});

test("find labels explicit roots under trailing-slash CLAUDE_CONFIG_DIR as Claude", () => {
  const dir = tempDir();
  const home = tempDir();
  const projectRoot = path.join(dir, "projects");
  const projectDir = path.join(projectRoot, "-tmp-agent-transcript");
  fs.mkdirSync(projectDir, { recursive: true });
  const session = path.join(projectDir, "22222222-3333-4444-8555-666666666666.jsonl");
  writeJsonl(session, [
    { type: "user", message: { role: "user", content: "claude-config-dir-explicit-root-marker" } },
    { type: "assistant", message: { role: "assistant", content: "Done." } },
  ]);

  const output = run(
    [
      "find",
      "--query",
      "claude-config-dir-explicit-root-marker",
      "--since-days",
      "1",
      "--max-files",
      "20",
      "--root",
      projectRoot,
    ],
    { env: { ...process.env, HOME: home, CLAUDE_CONFIG_DIR: `${dir}${path.sep}` } }
  );
  const matches = JSON.parse(output);

  assert.equal(matches.length, 1);
  assert.equal(matches[0].file, session);
  assert.equal(matches[0].agent, "claude");
});
