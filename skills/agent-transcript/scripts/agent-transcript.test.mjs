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

test("render drops Claude-format tool_result blocks and counts nested tool_use calls", () => {
  const dir = tempDir();
  const session = path.join(dir, "session.jsonl");
  writeJsonl(session, [
    { type: "user", message: { role: "user", content: [{ type: "text", text: "Fix the login bug." }] } },
    {
      type: "assistant",
      message: {
        role: "assistant",
        content: [
          { type: "text", text: "Searching for the failing code." },
          { type: "tool_use", name: "Bash", input: { command: "rg loginBug src/" } },
        ],
      },
    },
    {
      type: "user",
      message: {
        role: "user",
        content: [{ type: "tool_result", content: [{ type: "text", text: "db_password=hunter2secretvalue" }] }],
      },
    },
  ]);

  const output = run(["render", "--session", session]);
  assert.doesNotMatch(output, /hunter2secretvalue/);
  assert.match(output, /tool summary/);
  assert.match(output, /1 read/);
  assert.match(output, /raw tool outputs dropped: 1/);
  assert.match(output, /"toolCalls":1/);
  assert.match(output, /Searching for the failing code\./);
});

test("render lengthens the fence when transcript text contains backtick runs", () => {
  const dir = tempDir();
  const session = path.join(dir, "session.jsonl");
  writeJsonl(session, [
    {
      type: "response_item",
      payload: { role: "user", content: [{ type: "text", text: "Fence break attempt:\n````markdown\ninjected\n````" }] },
    },
  ]);

  const output = run(["render", "--session", session]);
  assert.match(output, /^`{5}text$/m, "opening fence must outgrow the content's 4-backtick run");
  assert.match(output, /^`{5}$/m, "closing fence must match the widened opening fence");
});

test("render keeps ISO dates and long ids but still redacts phone numbers", () => {
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
            text: "Deadline is 2026-07-29 for issue 1234567890; call +1 (555) 123-4567, 555-123-4567, 5551234567, or 07123456789.",
          },
        ],
      },
    },
  ]);

  const output = run(["render", "--session", session]);
  assert.match(output, /2026-07-29/);
  assert.match(output, /1234567890/);
  assert.match(output, /\[REDACTED_PHONE\]/);
  assert.doesNotMatch(output, /555/);
});

test("render keeps short dialogue that merely mentions AGENTS.md", () => {
  const dir = tempDir();
  const session = path.join(dir, "session.jsonl");
  writeJsonl(session, [
    {
      type: "response_item",
      payload: {
        role: "user",
        content: [{ type: "text", text: "Please add a build section to AGENTS.md and fix the failing test." }],
      },
    },
    {
      type: "response_item",
      payload: { role: "assistant", content: [{ type: "text", text: "<INSTRUCTIONS> full policy dump here" }] },
    },
  ]);

  const output = run(["render", "--session", session]);
  assert.match(output, /add a build section to AGENTS\.md/);
  assert.match(output, /\[instructions recap omitted/);
});

test("render counts every redaction match, not just rules fired", () => {
  const dir = tempDir();
  const session = path.join(dir, "session.jsonl");
  writeJsonl(session, [
    {
      type: "response_item",
      payload: { role: "user", content: [{ type: "text", text: "Mail one@example.com and two@example.com." }] },
    },
  ]);

  const output = run(["render", "--session", session]);
  assert.match(output, /"redactions":2/);
});

test("render keeps the newest turns of an oversized session and marks the gap", () => {
  const dir = tempDir();
  const session = path.join(dir, "session.jsonl");
  const rows = [];
  for (let i = 0; i < 12500; i++) {
    rows.push({ type: "response_item", payload: { role: "user", content: [{ type: "text", text: `turn-${i}` }] } });
  }
  writeJsonl(session, rows);

  const output = run(["render", "--session", session]);
  assert.match(output, /"sessionLinesOmitted":500/);
  assert.match(output, /transcript truncated to 50000 chars; middle omitted/);
  assert.match(output, /turn-12499/, "newest turn must survive both line and char truncation");
  assert.match(output, /turn-0\b/, "opening turn must survive both line and char truncation");
});

test("dangling value flags fail with a usage error instead of misbehaving", () => {
  const dir = tempDir();
  const session = path.join(dir, "session.jsonl");
  writeJsonl(session, [
    { type: "response_item", payload: { role: "user", content: [{ type: "text", text: "Fix the bug." }] } },
  ]);

  const maxChars = runFailure(["render", "--session", session, "--max-chars"]);
  assert.match(maxChars.stderr, /--max-chars requires a numeric value/);
  const cwd = runFailure(["find", "--query", "anything-here", "--cwd"]);
  assert.match(cwd.stderr, /--cwd requires a value/);
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

test("append-body strips stray markers instead of splicing later content", () => {
  const dir = tempDir();
  const session = path.join(dir, "session.jsonl");
  const body = path.join(dir, "body.md");
  writeJsonl(session, [
    { type: "response_item", payload: { role: "user", content: [{ type: "text", text: "New scoped work." }] } },
  ]);
  fs.writeFileSync(body, "# PR\n\n<!-- agent-transcript:end -->\nreal body content\n<!-- agent-transcript:start -->\n");

  const output = run(["append-body", "--body", body, "--session", session]);
  assert.match(output, /real body content/);
  assert.equal((output.match(/agent-transcript:start/g) || []).length, 1);
  assert.equal((output.match(/agent-transcript:end/g) || []).length, 1);
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

test("html scores equal headRefName and branch values only once", () => {
  const dir = tempDir();
  const sessionsDir = path.join(dir, "sessions");
  fs.mkdirSync(sessionsDir, { recursive: true });
  const session = path.join(sessionsDir, "session.jsonl");
  writeJsonl(session, [
    { type: "response_item", payload: { role: "user", content: [{ type: "text", text: "branch-marker" }] } },
  ]);
  const prsFile = path.join(dir, "prs.json");
  fs.writeFileSync(
    prsFile,
    JSON.stringify([
      {
        title: "x",
        url: "https://example.invalid/pr/1",
        number: 1,
        headRefName: "branch-marker",
        branch: "branch-marker",
      },
    ]),
  );

  const output = run(["html", "--prs", prsFile, "--root", sessionsDir, "--min-score", "5"]);
  assert.match(output, /No local session match found\./);
  assert.doesNotMatch(output, /branch-marker/);
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
