// Exact profile metadata through the public Paseo SDK. Requests arrive only on
// stdin; credentials and native errors are never emitted or placed in argv.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { createRequire } from "node:module";

let client;
try {
  const request = JSON.parse(readFileSync(0, "utf8"));
  const resolve = createRequire(join(request.cache, "package.json"));
  const { createPaseoClient } = await import(pathToFileURL(resolve.resolve("@getpaseo/client")).href);
  const url = new URL(request.url);
  if (url.protocol !== "ws:" || !["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)) {
    throw new Error("Only loopback TCP daemons are supported");
  }
  const localCredential = () => {
    try {
      const token = readFileSync(join(request.home, "local-credential"), "utf8").trim();
      return /^[A-Za-z0-9_-]{43}$/.test(token) ? token : undefined;
    } catch { return undefined; }
  };
  client = createPaseoClient({
    url: request.url,
    localCredential,
    password: process.env.PASEO_PASSWORD || undefined,
    connectTimeoutMs: 10000,
    reconnect: { enabled: false },
  });
  await client.connect();
  let result;
  if (request.operation === "profiles") {
    const response = await client.config.get();
    result = { profiles: response.config.agentProfiles ?? [] };
  } else if (request.operation === "validate") {
    const profile = request.profile;
    const provider = profile.provider;
    const snapshot = await client.providers.waitForReady({ cwd: request.cwd, timeoutMs: 30000 });
    const entry = snapshot.entries.find(item => item.provider === provider);
    let reason = !entry || entry.status !== "ready" || !entry.enabled
      ? "Selected Paseo provider is unavailable or disabled." : null;
    if (!reason && profile.model != null) {
      const response = await client.providers.listModels(provider, { cwd: request.cwd });
      const model = response.models?.find(item => item.id === profile.model);
      if (response.error) reason = "Paseo model metadata is unavailable.";
      else if (!model) reason = "Selected model is absent from the Paseo provider catalog.";
      else if (profile.thinkingOptionId != null && !model.thinkingOptions?.some(item => item.id === profile.thinkingOptionId)) {
        reason = "Selected thinking option is absent from the Paseo model catalog.";
      }
    } else if (!reason && profile.thinkingOptionId != null) {
      reason = "A model is required to validate a thinking option.";
    }
    if (!reason && profile.modeId != null) {
      const response = await client.providers.listModes(provider, { cwd: request.cwd });
      if (response.error) reason = "Paseo mode metadata is unavailable.";
      else if (!response.modes?.some(item => item.id === profile.modeId)) {
        reason = "Selected mode is absent from the Paseo provider catalog.";
      }
    }
    if (!reason && profile.featureValues && Object.keys(profile.featureValues).length) {
      const response = await client.providers.listFeatures({
        cwd: request.cwd,
        provider: profile.model ? `${provider}/${profile.model}` : provider,
        ...(profile.modeId != null ? { modeId: profile.modeId } : {}),
        ...(profile.thinkingOptionId != null ? { thinkingOptionId: profile.thinkingOptionId } : {}),
        featureValues: profile.featureValues,
      });
      if (response.error) reason = "Paseo feature metadata is unavailable.";
      else for (const [id, value] of Object.entries(profile.featureValues)) {
        const feature = response.features?.find(item => item.id === id);
        if (!feature) { reason = "Selected feature is absent from the Paseo provider catalog."; break; }
        if (feature.type === "toggle" ? typeof value !== "boolean"
          : feature.type === "select" ? !feature.options.some(item => item.id === value)
          : true) {
          reason = "Selected feature value is unsupported by the Paseo provider catalog."; break;
        }
      }
    }
    result = { reason };
  } else { throw new Error("Unsupported operation"); }
  process.stdout.write(JSON.stringify(result));
} catch {
  process.stdout.write(JSON.stringify({ error: "Paseo SDK request failed; inspect the selected local daemon and SDK prerequisites." }));
  process.exitCode = 1;
} finally {
  if (client) await client.close();
}
