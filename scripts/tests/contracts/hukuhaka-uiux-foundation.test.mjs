import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(fileURLToPath(new URL("../../..", import.meta.url)));
const PLUGIN = path.join(ROOT, "marketplace", "hukuhaka-uiux-foundation");
const SKILL_ROOT = path.join(PLUGIN, "skills", "uiux-foundation");
const REFERENCES = [
  "application.md",
  "design-principles.md",
  "design-review.md",
  "design-system.md",
  "experience-design.md",
  "synchronization.md",
  "verification.md",
  "visual-design.md",
];

function read(relativePath) {
  return fs.readFileSync(path.join(SKILL_ROOT, relativePath), "utf8");
}

function links(text) {
  return [...text.matchAll(/\[[^\]]+\]\(([^)]+)\)/g)].map((match) => match[1]);
}

test("Skill metadata preserves the canonical invocation and implicit eligibility", () => {
  const skill = read("SKILL.md");
  const frontmatter = skill.match(/^---\n([\s\S]*?)\n---/)?.[1] ?? "";
  const metadata = read("agents/openai.yaml");
  const manifest = JSON.parse(fs.readFileSync(path.join(PLUGIN, ".codex-plugin/plugin.json"), "utf8"));

  assert.match(frontmatter, /^name:\s*uiux-foundation$/m);
  assert.match(frontmatter, /^description:\s*\S.+$/m);
  assert.doesNotMatch(metadata, /allow_implicit_invocation:\s*false/);
  assert.match(metadata, /\$uiux-foundation/);
  assert.match(manifest.interface.defaultPrompt, /\$uiux-foundation/);
  assert.equal(manifest.skills, "./skills/");
  assert.equal(manifest.hooks, undefined);
  assert.doesNotMatch(skill, /\$\{CLAUDE_PLUGIN_ROOT\}|!`|allowed-tools:/);
});

test("The topic router exposes every packaged reference without orphaned outlines", () => {
  const packaged = fs.readdirSync(path.join(SKILL_ROOT, "references"))
    .filter((name) => name.endsWith(".md")).sort();
  assert.deepEqual(packaged, REFERENCES);
  const routed = links(read("SKILL.md"))
    .filter((target) => target.startsWith("references/"))
    .map((target) => target.slice("references/".length)).sort();
  assert.deepEqual(routed, REFERENCES);

  for (const name of REFERENCES) {
    const content = read("references/" + name);
    assert.doesNotMatch(content, /^> Outline only\./m, name + " is still a scaffold");
    assert.ok(links(content).some((target) => target.startsWith("https://")),
      name + " has no supporting source link");
  }
});

test("All reference links resolve inside the distributable Skill or use valid HTTPS URLs", () => {
  const root = fs.realpathSync(SKILL_ROOT);
  const visited = new Set();
  const pending = ["SKILL.md"];
  while (pending.length) {
    const relative = pending.pop();
    if (visited.has(relative)) continue;
    visited.add(relative);
    for (const link of links(read(relative))) {
      if (link.startsWith("https://")) {
        assert.equal(new URL(link).protocol, "https:");
        continue;
      }
      const target = path.resolve(SKILL_ROOT, path.dirname(relative), link.split("#")[0]);
      assert.ok(fs.existsSync(target), relative + " has a broken link: " + link);
      const real = fs.realpathSync(target);
      assert.ok(real.startsWith(root + path.sep), relative + " escapes the Skill: " + link);
      assert.ok(fs.statSync(real).isFile(), link + " is not a file");
      const resolved = path.relative(SKILL_ROOT, real);
      if (resolved.endsWith(".md")) pending.push(resolved);
    }
  }
  assert.deepEqual([...visited].sort(), [
    "SKILL.md", ...REFERENCES.map((name) => "references/" + name),
  ].sort());
});
