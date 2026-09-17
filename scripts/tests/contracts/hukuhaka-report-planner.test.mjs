import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(fileURLToPath(new URL("../../..", import.meta.url)));
const PLUGIN_ROOT = path.join(ROOT, "marketplace", "hukuhaka-report-planner");
const SKILL_ROOT = path.join(PLUGIN_ROOT, "skills", "hukuhaka-report-planner");
const DESIGNER_ROOT = path.join(PLUGIN_ROOT, "skills", "artifact-designer");
const DESIGNER_SKILL = path.join(DESIGNER_ROOT, "SKILL.md");
const STAGES_ROOT = path.join(SKILL_ROOT, "stages");
const EVAL_FIXTURE = path.join(
  ROOT,
  "eval",
  "cases",
  "report-planner-plan-only",
  "fixture"
);

function read(relativePath) {
  return fs.readFileSync(path.join(SKILL_ROOT, relativePath), "utf8");
}

function markdownFiles(root) {
  return fs.readdirSync(root, { withFileTypes: true }).flatMap((entry) => {
    const candidate = path.join(root, entry.name);
    if (entry.isDirectory()) {
      return markdownFiles(candidate);
    }
    return entry.name.endsWith(".md") ? [candidate] : [];
  });
}

function designRead(relativePath) {
  return fs.readFileSync(path.join(DESIGNER_ROOT, relativePath), "utf8");
}

test("planner runs four content stages and stops plan-only at spec", () => {
  const skill = read("SKILL.md");
  const description = skill.match(/^description:\s*"(.+)"$/m)?.[1] ?? "";
  assert.ok(description.length > 0 && Buffer.byteLength(description) < 1024);
  const stages = fs.readdirSync(STAGES_ROOT).sort();
  assert.deepEqual(stages, ["1-frame.md", "2-structure.md", "3-direct.md", "4-lock.md"]);
  for (const stage of stages) assert.ok(skill.includes("stages/" + stage));
  assert.match(skill, /four stages all concern content planning/);
  assert.match(skill, /IF planning-only:\s+Report the finalized spec path and stop\./);
  assert.match(skill, /Do not select design craft references/);
  assert.match(skill, /record it as a\s+user constraint/);
  assert.match(skill, /editorial brief, not finished report copy/);
  assert.match(skill, /Source coverage is not display coverage/);
  assert.match(skill, /one artifact-designer\s+in a separate context/);
  assert.match(read("stages/4-lock.md"), /Do not create design.md or delegate/);
  assert.match(read("stages/3-direct.md"), /Do not.*design\.md/);
  assert.match(read("stages/1-frame.md"), /limits claims, not the designer's visual language/);
  assert.match(read("stages/1-frame.md"), /do not fill it with the spec's save path/);
  assert.match(read("stages/3-direct.md"), /not a requirement to quote every related function/);
  assert.match(read("stages/4-lock.md"), /do not solve excess content by redefining a page limit/);
});

test("content-v1 spec has no mandatory design fields or future anchor dependency", () => {
  const schema = read("references/spec-schema.md");
  const template = schema.match(/\x60{3}markdown\n([\s\S]*?)\x60{3}/)?.[1] ?? "";
  assert.match(template, /plan-format: content-v1\nplan-state: draft/);
  assert.deepEqual([...template.matchAll(/^## (.+)$/gm)].map(m => m[1]),
    ["Document Model", "Evidence", "Structure", "Acceptance Tests"]);
  for (const field of ["reader question:", "reader outcome:", "content:", "evidence:"])
    assert.ok(template.includes(field));
  assert.doesNotMatch(template, /A\d|color roles|craft\/|material:|composition:|treatment:|locked:|guided:|open:/);
  assert.match(schema, /not an executable schema/);
  assert.match(schema, /explicit user presentation requirements/);
  assert.match(read("stages/4-lock.md"), /Set \x60plan-state: finalized\x60/);
  assert.match(read("stages/4-lock.md"), /must not depend on\s+a future A#/);
});

test("designer owns design and keeps content read-only", () => {
  const designer = designRead("SKILL.md");
  const schema = designRead("references/design-schema.md");
  assert.match(designer, /Do not edit \x60spec.md\x60/);
  assert.match(designer, /Own its Design Direction, Anchors, Build Boundaries, and Realization/);
  assert.match(designer, /may refine representation, layout, styling, and design.md/);
  assert.match(designer, /Changes to meaning or user constraints require a return\s+to planning/);
  assert.match(schema, /design-format: designer-v1/);
  assert.match(schema, /Every \x60A#\x60 resolves to one or more \x60U#\x60, \x60S#\x60, and \x60T#\x60/);
  assert.match(schema, /one realized region may implement multiple anchors/);
  assert.match(schema, /prose-only design records/);
  assert.match(schema, /compact \x60direction\x60/);
  for (const field of ["material:", "composition:", "treatment:"]) assert.ok(schema.includes(field));
  assert.match(schema, /not-run/);
  assert.match(designer, /timed human reading test/);
  assert.match(designer, /not overall acceptance/);
  assert.match(designer, /every exact width/);
  assert.match(designer, /no horizontal overflow/);
  assert.match(designer, /reduced motion/);
  assert.match(designer, /source has\s+drifted/);
  assert.match(designer, /\x60failed\x60 for failed checks or\s+source drift/);
  assert.match(designer, /\x60unavailable\x60 for missing build or rendering capability/);
});

test("unmarked and incomplete plans cannot silently acquire new design permissions", () => {
  const compatibility = read("references/plan-compatibility.md");
  for (const kind of ["Legacy combined plan", "Legacy paired plan", "Incomplete legacy pair",
    "Incomplete new plan", "Unsupported input"]) assert.ok(compatibility.includes(kind));
  assert.match(compatibility, /Unknown marker or unrecognizable contract/);
  assert.match(compatibility, /do not reinterpret it as content-v1/);
  assert.match(compatibility, /only Realization is designer-mutable/);
  assert.match(compatibility, /Legacy paths are read-only/);
  assert.match(compatibility, /distinct destination that preserves the original/);
  assert.match(compatibility, /Never dual-write/);
  assert.match(compatibility, /Never auto-load/);
  assert.match(compatibility, /does not authorize arbitrary archived absolute paths/);
  for (const file of ["SKILL.md", "references/build-handoff.md"])
    assert.match(read(file), /plan-compatibility.md/);
  assert.match(designRead("SKILL.md"), /plan-compatibility.md/);
  assert.match(designRead("SKILL.md"), /Path-level read-only rules take precedence/);
  assert.match(read("references/build-handoff.md"), /For content-v1, the designer/);
  assert.match(read("references/build-handoff.md"), /Missing required legacy input stops the handoff/);
});

test("design restraint and craft live with the designer, not the planner", () => {
  const schema = designRead("references/design-schema.md");
  const designer = designRead("SKILL.md");
  assert.match(read("references/principles.md"), /Comprehension over coverage/);
  assert.match(schema, /- thesis:/);
  assert.match(schema, /<!-- roles:/);
  assert.match(schema, /Omit the block when the thesis and ordinary hierarchy are sufficient/);
  assert.match(schema, /Do not duplicate a unit's reader question or outcome/);
  assert.match(schema, /omit them instead of writing \x60none\x60/);
  assert.match(designer, /no more than five intentional chromatic or semantic colors/);
  assert.match(designer, /button-shaped element without a real action/);
  assert.match(designer, /pills only for a recurring status or category/);
  assert.match(designer, /sort mAP descending · best bold/);
  assert.match(designRead("references/craft/charts.md"), /display a takeaway only when the\s+encoding does not make it reliably inferable/);
  assert.match(designRead("references/craft/kpi-tiles.md"), /definition only when the audience needs it/);
  assert.match(designRead("references/craft/kpi-tiles.md"), /do not default to a pill or chip/);
  assert.match(designRead("references/craft/layout.md"), /Omit it when the visual encoding already communicates the meaning/);
  for (const relativePath of ["references/reference-index.md",
    "references/directions.md", "references/design-schema.md"]) {
    assert.equal(fs.existsSync(path.join(SKILL_ROOT, relativePath)), false, relativePath);
    assert.ok(fs.existsSync(path.join(DESIGNER_ROOT, relativePath)), relativePath);
  }
});

test("designer selects progressive references and bundled links resolve after the move", () => {
  const designer = designRead("SKILL.md");
  const index = designRead("references/reference-index.md");
  assert.match(designer, /select zero to three craft files/);
  assert.match(designer, /Do not read all of/);
  assert.match(index, /bundled craft knowledge, not style targets or templates/);
  const craft = path.join(DESIGNER_ROOT, "references", "craft");
  assert.equal(fs.readdirSync(craft).filter(name => name.endsWith(".md")).length, 25);
  for (const file of markdownFiles(craft)) {
    assert.equal(fs.existsSync(path.join(SKILL_ROOT, "references", "craft", path.basename(file))), false,
      "a migrated bundled craft file remains planner-owned: " + file);
    const content = fs.readFileSync(file, "utf8");
    for (const field of ["use_when", "do_not_use_when", "style_risk"])
      assert.match(content, new RegExp("^" + field + ":", "m"), file);
    assert.doesNotMatch(content, /In Stage 3|The planner records|the planner guides/);
    for (const match of content.matchAll(/\x60((?:\.\.\/)?[\w/-]+\.md)\x60/g)) {
      assert.ok(fs.existsSync(path.resolve(path.dirname(file), match[1])), file + ": " + match[1]);
    }
  }
  for (const match of index.matchAll(/\x60(craft\/[\w-]+\.md|directions\.md)\x60/g))
    assert.ok(fs.existsSync(path.join(DESIGNER_ROOT, "references", match[1])));
  const runtime = markdownFiles(PLUGIN_ROOT).map(file => fs.readFileSync(file, "utf8")).join("\n");
  assert.match(runtime, /uppercase \x60DESIGN.md\x60/);
  assert.match(runtime, /Never auto-load/);
  assert.doesNotMatch(runtime, /design source:/i);
});

test("handoff is one separate designer with no parent design or build", () => {
  const handoff = read("references/build-handoff.md");
  const designer = designRead("SKILL.md");
  assert.match(handoff, /Stage 4 finalizes the content spec/);
  for (const field of ["spec path:", "source material:", "form:", "output target:", "verification:"])
    assert.ok(handoff.includes(field));
  assert.match(handoff, /Do not send a planner-authored design or a selected craft list/);
  assert.match(handoff, /Do not build in the parent/);
  assert.match(handoff, /## Codex handoff/);
  assert.doesNotMatch(handoff, /Claude Code/);
  assert.match(handoff, /do not install a user-level(?: or project-level)? agent/);
  assert.match(handoff, /write-capable worker/);
  assert.match(handoff, /\.\.\/artifact-designer\/SKILL.md/);
  assert.match(handoff, /same-named\s+installed copy from another version/);
  assert.match(handoff, /cannot delegate, report that\s+capability as unavailable/);
  assert.match(designer, /Do not spawn another builder/);
  assert.doesNotMatch(handoff + designer, /validate-spec/);
});

test("validator and static design fixtures are absent", () => {
  const validator = path.join(SKILL_ROOT, "scripts", "validate-spec.sh");
  const runtimeFigma = path.join(SKILL_ROOT, "references", "fixtures", "figma");
  const ibmFixture = path.join(EVAL_FIXTURE, "design", "IBM");

  assert.equal(fs.existsSync(validator), false);
  assert.deepEqual(
    fs.existsSync(ibmFixture) ? fs.readdirSync(ibmFixture) : [],
    [],
    "IBM fixture files still exist"
  );
  assert.deepEqual(
    fs.existsSync(runtimeFigma) ? fs.readdirSync(runtimeFigma) : [],
    [],
    "runtime Figma fixture files still exist"
  );
});

test("design-led eval fixture exposes the backend-contract-frontend seam", () => {
  if (!fs.existsSync(path.join(ROOT, "eval"))) {
    return;
  }

  const expected = [
    "README.md",
    "contracts/report.schema.json",
    "backend/app.py",
    "frontend/report-api.ts",
    "frontend/report-view.ts",
    "tests/test_contract.py"
  ];

  for (const relativePath of expected) {
    assert.ok(fs.existsSync(path.join(EVAL_FIXTURE, relativePath)), `${relativePath} missing`);
  }
  const prompt = fs.readFileSync(
    path.join(ROOT, "eval", "cases", "report-planner-plan-only", "prompt.md"),
    "utf8"
  );
  assert.match(prompt, /frontend\/backend connection/);
  assert.match(prompt, /exact source excerpt/);
  assert.match(prompt, /stop after Stage 4/);
  assert.doesNotMatch(prompt, /DESIGN\.md|IBM/);
  assert.doesNotMatch(prompt, /validate/i);
});

test("eval cases distinguish plan-only output from designer-owned build output", () => {
  if (!fs.existsSync(path.join(ROOT, "eval"))) return;
  const loadCase = name => JSON.parse(fs.readFileSync(path.join(ROOT, "eval", "cases", name, "case.json"), "utf8"));
  const plan = loadCase("report-planner-plan-only");
  const design = plan.checks.find(check => check.path?.endsWith("/design.md"));
  assert.equal(design.mode, "absent");
  assert.deepEqual(plan.checks.find(check => check.mode === "changed_only").patterns,
    [".hukuhaka/reports/eval-system-explainer/spec.md"]);
  assert.equal(plan.checks.find(check => check.kind === "subagent").count, 0);
  const build = loadCase("report-planner-build-now");
  assert.equal(build.checks.find(check => check.path?.endsWith("/design.md")).mode, "exists");
  for (const host of ["codex"]) {
    assert.equal(build.hosts[host].checks.find(check => check.type === "artifact-designer").count, 1);
    assert.equal(build.hosts[host].checks.find(check => check.scope === "parent").count, 0);
  }
});

test("Codex manifest exposes the report-planner version", () => {
  const codex = JSON.parse(
    fs.readFileSync(path.join(PLUGIN_ROOT, ".codex-plugin", "plugin.json"), "utf8")
  );

  assert.equal(codex.version, "0.8.0");
});
