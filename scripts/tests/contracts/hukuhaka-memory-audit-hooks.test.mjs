import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(fileURLToPath(new URL("../../..", import.meta.url)));
const PLUGIN = path.join(ROOT, "marketplace", "hukuhaka-memory-audit");
const HOOK = path.join(PLUGIN, "scripts", "memory_pressure_hook.py");
const HOOKS = path.join(PLUGIN, "hooks", "codex.json");

function withFixture(callback) {
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), "hukuhaka-memory-audit-"));
  const codexHome = path.join(fixtureRoot, "codex-home");
  const memoryRoot = path.join(codexHome, "memories");
  const pluginData = path.join(fixtureRoot, "plugin-data");
  fs.mkdirSync(memoryRoot, { recursive: true });
  try {
    callback({ codexHome, memoryRoot, pluginData });
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
}

function runHook({ codexHome, pluginData, source = "startup" }) {
  return spawnSync("python3", [HOOK, "--host", "codex"], {
    input: `${JSON.stringify({
      hook_event_name: "SessionStart",
      source,
    })}\n`,
    env: {
      ...process.env,
      CODEX_HOME: codexHome,
      PLUGIN_DATA: pluginData,
      PATH: process.env.PATH,
    },
    encoding: "utf8",
  });
}

function writeHotSummary(memoryRoot) {
  const summary = Array.from({ length: 200 }, (_, index) => `line ${index + 1}`).join("\n");
  fs.writeFileSync(path.join(memoryRoot, "memory_summary.md"), summary);
  return summary;
}

function state(pluginData) {
  return JSON.parse(
    fs.readFileSync(path.join(pluginData, "memory-pressure-state.json"), "utf8"),
  );
}

test("plugin registers one startup-or-resume SessionStart warning hook", () => {
  const definition = JSON.parse(fs.readFileSync(HOOKS, "utf8"));
  assert.deepEqual(Object.keys(definition.hooks), ["SessionStart"]);
  assert.equal(definition.hooks.SessionStart.length, 1);
  assert.equal(definition.hooks.SessionStart[0].matcher, "^(startup|resume)$");
  assert.equal(definition.hooks.SessionStart[0].hooks.length, 1);
  assert.equal(
    definition.hooks.SessionStart[0].hooks[0].command,
    'python3 "${PLUGIN_ROOT}/scripts/memory_pressure_hook.py" --host codex',
  );
  const codex = JSON.parse(fs.readFileSync(path.join(PLUGIN, ".codex-plugin/plugin.json"), "utf8"));
  assert.equal(codex.hooks, "./hooks/codex.json");
  assert.equal(fs.existsSync(path.join(PLUGIN, "hooks/hooks.json")), false);
});

test("Claude memory audit uses editable native memory and native size feedback", () => {
  const claude = JSON.parse(fs.readFileSync(path.join(PLUGIN, ".claude-plugin/plugin.json"), "utf8"));
  assert.equal(claude.version, "0.2.1");
  assert.equal(claude.hooks, undefined);
  assert.equal(fs.existsSync(path.join(PLUGIN, "hooks/claude.json")), false);
  const adapter = fs.readFileSync(path.join(PLUGIN, "skills/memory-audit/references/hosts/claude.md"), "utf8");
  assert.match(adapter, /editable MEMORY.md index and topic files/);
  assert.match(adapter, /After approval of the exact proposal/);
  assert.match(adapter, /No custom Claude memory-pressure hook is installed/);
  assert.match(adapter, /200-line and 25 KB/);
  const codex = fs.readFileSync(path.join(PLUGIN, "skills/memory-audit/references/hosts/codex.md"), "utf8");
  assert.match(codex, /Never manually edit its\s+summaries, indexes, rollout summaries/);
  assert.match(codex, /report submission/);
});

test("below-threshold memory emits nothing and creates no state", () => {
  withFixture(({ codexHome, memoryRoot, pluginData }) => {
    fs.writeFileSync(path.join(memoryRoot, "memory_summary.md"), "small summary\n");
    fs.writeFileSync(path.join(memoryRoot, "MEMORY.md"), "small index\n");

    const result = runHook({ codexHome, pluginData });

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, "");
    assert.equal(fs.existsSync(pluginData), false);
  });
});

test("memory measurement does not follow symlinked files", () => {
  withFixture(({ codexHome, memoryRoot, pluginData }) => {
    const external = path.join(path.dirname(memoryRoot), "external-summary.md");
    fs.writeFileSync(external, Buffer.alloc(25 * 1024));
    fs.symlinkSync(external, path.join(memoryRoot, "memory_summary.md"));

    const result = runHook({ codexHome, pluginData });

    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout, "");
    assert.equal(fs.existsSync(pluginData), false);
  });
});

test("hot summary emits one English warning without changing memory", () => {
  withFixture(({ codexHome, memoryRoot, pluginData }) => {
    const summary = writeHotSummary(memoryRoot);

    const first = runHook({ codexHome, pluginData });

    assert.equal(first.status, 0, first.stderr);
    const payload = JSON.parse(first.stdout);
    assert.match(payload.systemMessage, /^Codex memory pressure:/);
    assert.match(payload.systemMessage, /25 KiB or 200 lines/);
    assert.match(payload.systemMessage, /\$memory-audit/);
    assert.equal(fs.readFileSync(path.join(memoryRoot, "memory_summary.md"), "utf8"), summary);
    assert.deepEqual(state(pluginData), { version: 1, tier: "hot" });

    const second = runHook({ codexHome, pluginData, source: "resume" });
    assert.equal(second.status, 0, second.stderr);
    assert.equal(second.stdout, "");
  });
});

test("cold index emits its own warning and hot escalation emits once", () => {
  withFixture(({ codexHome, memoryRoot, pluginData }) => {
    fs.writeFileSync(path.join(memoryRoot, "MEMORY.md"), Buffer.alloc(1024 * 1024));

    const cold = runHook({ codexHome, pluginData });

    assert.equal(cold.status, 0, cold.stderr);
    assert.match(JSON.parse(cold.stdout).systemMessage, /1 MiB or rollout summaries/);
    assert.deepEqual(state(pluginData), { version: 1, tier: "cold" });

    writeHotSummary(memoryRoot);
    const hot = runHook({ codexHome, pluginData, source: "resume" });
    assert.equal(hot.status, 0, hot.stderr);
    assert.match(JSON.parse(hot.stdout).systemMessage, /25 KiB or 200 lines/);
    assert.deepEqual(state(pluginData), { version: 1, tier: "hot" });

    const repeated = runHook({ codexHome, pluginData, source: "resume" });
    assert.equal(repeated.status, 0, repeated.stderr);
    assert.equal(repeated.stdout, "");
  });
});

test("three hundred rollout files trigger cold pressure", () => {
  withFixture(({ codexHome, memoryRoot, pluginData }) => {
    const rollouts = path.join(memoryRoot, "rollout_summaries");
    fs.mkdirSync(rollouts);
    for (let index = 0; index < 300; index += 1) {
      fs.writeFileSync(path.join(rollouts, `${index}.md`), "");
    }

    const result = runHook({ codexHome, pluginData });

    assert.equal(result.status, 0, result.stderr);
    assert.match(JSON.parse(result.stdout).systemMessage, /300 files/);
    assert.deepEqual(state(pluginData), { version: 1, tier: "cold" });
  });
});

test("returning below threshold resets suppression for later growth", () => {
  withFixture(({ codexHome, memoryRoot, pluginData }) => {
    writeHotSummary(memoryRoot);
    assert.notEqual(runHook({ codexHome, pluginData }).stdout, "");

    fs.writeFileSync(path.join(memoryRoot, "memory_summary.md"), "small again\n");
    const recovered = runHook({ codexHome, pluginData, source: "resume" });
    assert.equal(recovered.status, 0, recovered.stderr);
    assert.equal(recovered.stdout, "");
    assert.deepEqual(state(pluginData), { version: 1, tier: "none" });

    writeHotSummary(memoryRoot);
    const regrown = runHook({ codexHome, pluginData, source: "resume" });
    assert.match(JSON.parse(regrown.stdout).systemMessage, /\$memory-audit/);
  });
});

test("malformed state recovers and compact sources do not run", () => {
  withFixture(({ codexHome, memoryRoot, pluginData }) => {
    writeHotSummary(memoryRoot);
    fs.mkdirSync(pluginData);
    fs.writeFileSync(path.join(pluginData, "memory-pressure-state.json"), "not json\n");

    const compact = runHook({ codexHome, pluginData, source: "compact" });
    assert.equal(compact.status, 0, compact.stderr);
    assert.equal(compact.stdout, "");
    assert.equal(
      fs.readFileSync(path.join(pluginData, "memory-pressure-state.json"), "utf8"),
      "not json\n",
    );

    const startup = runHook({ codexHome, pluginData });
    assert.match(JSON.parse(startup.stdout).systemMessage, /Codex memory pressure/);
    assert.deepEqual(state(pluginData), { version: 1, tier: "hot" });
  });
});
