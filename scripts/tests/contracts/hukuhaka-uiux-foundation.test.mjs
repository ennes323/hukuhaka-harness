import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(fileURLToPath(new URL("../../..", import.meta.url)));
const PLUGIN = path.join(ROOT, "marketplace", "hukuhaka-uiux-foundation");
const SKILL_ROOT = path.join(PLUGIN, "skills", "uiux-foundation");

function read(relativePath) {
  return fs.readFileSync(path.join(SKILL_ROOT, relativePath), "utf8");
}

test("natural frontend and UIUX intent selects a bounded portable Skill", () => {
  const skill = read("SKILL.md");
  const frontmatter = skill.match(/^---\n([\s\S]*?)\n---/)?.[1] ?? "";
  const metadata = read("agents/openai.yaml");

  assert.match(frontmatter, /^name:\s*uiux-foundation$/m);
  assert.match(frontmatter, /Use automatically for user-visible frontend and UI\/UX work/);
  assert.match(frontmatter, /design systems/);
  assert.match(frontmatter, /layout or alignment/);
  assert.match(frontmatter, /responsive or accessibility behavior/);
  assert.match(frontmatter, /mockup implementation/);
  assert.match(frontmatter, /backend-only work/);
  assert.match(frontmatter, /non-visual frontend logic/);
  assert.match(frontmatter, /report, deck, and document artifacts/);
  assert.doesNotMatch(metadata, /allow_implicit_invocation:\s*false/);
  assert.match(metadata, /\$uiux-foundation/);
  assert.doesNotMatch(skill, /\$\{CLAUDE_PLUGIN_ROOT\}|!`|allowed-tools:/);
});

test("the lean entrypoint routes only applicable detail", () => {
  const skill = read("SKILL.md");
  const routed = [
    "foundations.md",
    "application.md",
    "synchronization.md",
    "verification.md",
  ];

  for (const reference of routed) {
    assert.match(skill, new RegExp(`references/${reference.replace(".", "\\.")}`));
    assert.ok(fs.existsSync(path.join(SKILL_ROOT, "references", reference)));
  }
  assert.match(skill, /`Create`, `Modify`, `Extend`, `Audit`, or `Parity`/);
  assert.match(skill, /An audit or review does not authorize edits/);
  assert.match(skill, /Do not create `DESIGN\.md`, a token file, or a component kit by default/);
});

test("foundations prompt for complete decisions without fixed style values", () => {
  const foundations = read("references/foundations.md");
  for (const heading of [
    "Visual direction",
    "Color",
    "Typography",
    "Spacing and sizing",
    "Layout and responsiveness",
    "Shape and surface",
    "Interaction and motion",
    "Content and visual assets",
    "Components",
  ]) {
    assert.match(foundations, new RegExp(`^## ${heading}$`, "m"));
  }
  assert.match(foundations, /`established`, `required now`, `conflicting`, and `deferred`/);
  assert.match(foundations, /does not mean inventing every possible token or component/);
  assert.doesNotMatch(foundations, /#[0-9A-Fa-f]{6}|\b(?:8|12|16|24|32)px\b/);
});

test("application and synchronization preserve decision ownership", () => {
  const skill = read("SKILL.md");
  const application = read("references/application.md");
  const synchronization = read("references/synchronization.md");

  assert.match(skill, /foundation or semantic token/);
  assert.match(skill, /component rule, state, or variant/);
  assert.match(skill, /screen composition/);
  assert.match(skill, /intentional local exception/);
  assert.match(application, /loading, empty, error, partial, stale, and success/);
  assert.match(application, /keyboard reachability, visible focus/);
  assert.match(application, /rendered and computed geometry/);
  assert.match(synchronization, /Design system \| Reusable foundations/);
  assert.match(synchronization, /Mockup \| Screen hierarchy/);
  assert.match(synchronization, /Application \| Working behavior/);
  assert.match(synchronization, /`intentional`/);
  assert.match(synchronization, /`missing`/);
  assert.match(synchronization, /`stale`/);
  assert.match(synchronization, /`accidental`/);
  assert.match(synchronization, /`unresolved`/);
  assert.match(synchronization, /Do not average conflicting values/);
});

test("verification requires rendered evidence without overstating coverage", () => {
  const verification = read("references/verification.md");

  assert.match(verification, /A successful build is not proof/);
  assert.match(verification, /in-app Browser/);
  assert.match(verification, /computed style or geometry/);
  assert.match(verification, /screenshots, overlays, or visual diffs/);
  assert.match(verification, /clipping, overlap, page and component overflow/);
  assert.match(verification, /keyboard navigation, visible focus/);
  assert.match(verification, /State unverified areas plainly/);
  assert.match(verification, /Do not generalize one clean screen/);
});
