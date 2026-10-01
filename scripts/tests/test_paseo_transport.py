from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.install.paseo_transport import LocalPaseoTransport, PaseoTransportError


PROFILE = {"id": "hk-worker", "name": "Worker", "provider": "codex", "model": "sol",
           "modeId": "full-access", "thinkingOptionId": "high", "featureValues": {"fast_mode": True}}


class FixtureTransport(LocalPaseoTransport):
    def __init__(self, home):
        super().__init__(home, cli="paseo")
        self.profiles = [{"id": "personal", "name": "Personal", "provider": "custom", "future": {"retain": True}}]
        self.live = copy.deepcopy(self.profiles)
        self.calls = []
        self.result = {"action": "saved", "appliedPaths": ["daemon.agentProfiles"],
                       "restartRequiredPaths": [], "overrideControlledPaths": []}
        self.write_error = None
        self.post_drift = False

    def _call(self, *arguments, mutating=False):
        self.calls.append((arguments, mutating))
        if arguments == ("daemon", "status"):
            return {"home": str(self.home), "localDaemon": "running", "connectedDaemon": "reachable", "listen": "127.0.0.1:6767"}
        if arguments[:3] == ("daemon", "config", "get"):
            return {"source": "configured", "set": True, "value": copy.deepcopy(self.profiles)}
        if arguments == ("daemon", "reload"):
            self.live = copy.deepcopy(self.profiles)
            return {"appliedPaths": ["daemon.agentProfiles"], "restartRequiredPaths": [], "overrideControlledPaths": []}
        if mutating:
            if self.write_error:
                raise self.write_error
            self.profiles = json.loads(arguments[4])
            if self.post_drift:
                self.profiles[0]["name"] = "Other writer"
            if "daemon.agentProfiles" in self.result.get("appliedPaths", []):
                self.live = copy.deepcopy(self.profiles)
            return self.result
        raise AssertionError(arguments)

    def _sdk(self, operation, **extra):
        if operation == "profiles":
            return {"profiles": copy.deepcopy(self.live)}
        if operation == "validate":
            return {"reason": None}
        raise AssertionError(operation)


class PaseoTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name) / "paseo"
        self.transport = FixtureTransport(self.home)

    def test_single_native_write_preserves_unknown_personal_fields(self):
        before = self.transport.read_profiles()
        after = before + [copy.deepcopy(PROFILE)]
        result = self.transport.apply_profiles(before, after)
        writes = [call for call in self.transport.calls if call[1]]
        self.assertEqual(len(writes), 1)
        self.assertEqual(writes[0][0][:4], ("daemon", "config", "set", "daemon.agentProfiles"))
        self.assertEqual(self.transport.profiles, after)
        self.assertTrue(result["saved"])
        self.assertTrue(result["applied"])
        self.assertFalse(result["conditional_update"])

    def test_observed_drift_refuses_before_write(self):
        before = self.transport.read_profiles()
        self.transport.profiles[0]["name"] = "External edit"
        with self.assertRaisesRegex(PaseoTransportError, "changed since preview"):
            self.transport.apply_profiles(before, before + [PROFILE])
        self.assertFalse(any(call[1] for call in self.transport.calls))

    def test_provider_rejection_is_before_mutation(self):
        with mock.patch.object(self.transport, "validate_profile", return_value="Unavailable"):
            with self.assertRaisesRegex(PaseoTransportError, "Unavailable"):
                self.transport.apply_profiles(self.transport.read_profiles(), [PROFILE])
        self.assertFalse(any(call[1] for call in self.transport.calls))

    def test_saved_without_reload_is_partial_and_not_retried(self):
        self.transport.result = {"action": "saved", "applied": False}
        before = self.transport.read_profiles()
        result = self.transport.apply_profiles(before, before + [PROFILE])
        self.assertTrue(result["saved"])
        self.assertFalse(result["applied"])
        self.assertTrue(result["notices"])
        self.assertEqual(sum(call[1] for call in self.transport.calls), 1)

    def test_unrelated_restart_notice_does_not_hide_profile_success(self):
        self.transport.result["restartRequiredPaths"] = ["daemon.listen"]
        before = self.transport.read_profiles()
        result = self.transport.apply_profiles(before, before + [PROFILE])
        self.assertTrue(result["applied"])
        self.assertEqual(result["notices"], ["Paseo reports restart required for daemon.listen."])

    def test_empty_applied_paths_do_not_claim_profile_application(self):
        self.transport.result["appliedPaths"] = []
        before = self.transport.read_profiles()
        result = self.transport.apply_profiles(before, before + [PROFILE])
        self.assertTrue(result["saved"])
        self.assertFalse(result["applied"])

    def test_post_write_drift_fails_without_rollback(self):
        self.transport.post_drift = True
        before = self.transport.read_profiles()
        with self.assertRaises(PaseoTransportError) as error:
            self.transport.apply_profiles(before, before + [PROFILE])
        self.assertTrue(error.exception.saved)
        self.assertTrue(error.exception.mutation_attempted)
        self.assertEqual(sum(call[1] for call in self.transport.calls), 1)
        self.assertEqual(self.transport.profiles[0]["name"], "Other writer")

    def test_unknown_write_outcome_stays_unknown_and_is_not_retried(self):
        self.transport.write_error = PaseoTransportError("Timeout", mutation_attempted=True)
        before = self.transport.read_profiles()
        with self.assertRaises(PaseoTransportError) as error:
            self.transport.apply_profiles(before, before + [PROFILE])
        self.assertIsNone(error.exception.saved)
        self.assertTrue(error.exception.attempted)
        self.assertEqual(sum(call[1] for call in self.transport.calls), 1)

    def test_noop_checks_live_and_registered_without_write(self):
        before = self.transport.read_profiles()
        result = self.transport.apply_profiles(before, before)
        self.assertTrue(result["applied"])
        self.assertFalse(result["changed"])
        self.assertFalse(any(call[1] for call in self.transport.calls))

    def test_read_and_prerequisite_preview_do_not_prepare_cache(self):
        transport = LocalPaseoTransport(self.home, cli="paseo")
        with mock.patch.object(transport, "prepare") as prepare:
            self.assertTrue(transport.prerequisites())
            with mock.patch.object(transport, "_require_node", return_value="node"):
                with self.assertRaisesRegex(PaseoTransportError, "cache is missing"):
                    transport.read_profiles()
            prepare.assert_not_called()
        self.assertFalse(self.home.exists())

    def test_unmanaged_and_symlink_cache_are_preserved(self):
        cache = Path(self.temp.name).resolve() / "cache"
        cache.mkdir()
        personal = cache / "personal.txt"
        personal.write_text("keep")
        transport = LocalPaseoTransport(self.home, cli="paseo", cache=cache)
        with mock.patch.object(transport, "require_cli"), mock.patch.object(transport, "_require_node"):
            transport.npm = "npm"
            with self.assertRaisesRegex(PaseoTransportError, "unmanaged"):
                transport.prepare()
        self.assertEqual(personal.read_text(), "keep")
        link = Path(self.temp.name).resolve() / "link"
        link.symlink_to(cache, target_is_directory=True)
        with self.assertRaisesRegex(PaseoTransportError, "symlinks"):
            LocalPaseoTransport(self.home, cli="paseo", cache=link).prerequisites()

    def test_cli_version_floor_and_argv_environment_boundaries(self):
        transport = LocalPaseoTransport(self.home, cli="/tool/paseo")
        responses = [subprocess.CompletedProcess([], 0, "0.10.2\n", ""), subprocess.CompletedProcess([], 0, "{}", "")]
        with mock.patch.dict(os.environ, {"PASEO_HOST": "remote:9999", "NODE_OPTIONS": "--require /evil"}):
            with mock.patch("subprocess.run", side_effect=responses) as run:
                self.assertEqual(transport.require_cli(), "0.10.2")
                transport._call("daemon", "config", "set", "daemon.agentProfiles", "[]", mutating=True)
        args, kwargs = run.call_args
        self.assertEqual(args[0], ["/tool/paseo", "--home", str(transport.home), "--json", "daemon", "config", "set", "daemon.agentProfiles", "[]"])
        self.assertNotIn("shell", kwargs)
        self.assertNotIn("PASEO_HOST", kwargs["env"])
        self.assertNotIn("NODE_OPTIONS", kwargs["env"])
        with mock.patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, "0.9.0", "")):
            with self.assertRaisesRegex(PaseoTransportError, "0.10.2"):
                LocalPaseoTransport(self.home, cli="paseo").require_cli()

    def test_reviewed_reload_uses_one_reload_and_no_config_write(self):
        self.transport.profiles.append(copy.deepcopy(PROFILE))
        expected = copy.deepcopy(self.transport.profiles)
        result = self.transport.reload_profiles(expected)
        self.assertTrue(result["saved"])
        self.assertTrue(result["applied"])
        writes = [call for call in self.transport.calls if call[1]]
        self.assertEqual(writes, [(("daemon", "reload"), True)])

    def test_reload_refuses_intervening_saved_drift(self):
        expected = self.transport.read_profiles()
        self.transport.profiles[0]["name"] = "External edit"
        with self.assertRaisesRegex(PaseoTransportError, "changed before reload"):
            self.transport.reload_profiles(expected)
        self.assertFalse(any(call[1] for call in self.transport.calls))


@unittest.skipUnless(shutil.which("node"), "Node unavailable for SDK helper test")
class PaseoSdkHelperTests(unittest.TestCase):
    def test_exact_metadata_ids_and_feature_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            package = root / "node_modules/@getpaseo/client"
            package.mkdir(parents=True)
            (root / "package.json").write_text('{"type":"module"}')
            (package / "package.json").write_text('{"type":"module","exports":"./index.js"}')
            (package / "index.js").write_text('''
export function createPaseoClient() {
 return {connect:async()=>{},close:async()=>{},providers:{
 waitForReady:async()=>({entries:[{provider:"codex",status:"ready",enabled:true}]}),
 listModels:async()=>({models:[{id:"sol",thinkingOptions:[{id:"high"}]}]}),
 listModes:async()=>({modes:[{id:"full-access"}]}),
 listFeatures:async draft=>{if(!draft.cwd)throw Error("cwd");return {features:[
 {id:"fast_mode",type:"toggle"},{id:"choice",type:"select",options:[{id:"option-id",label:"Display"}]}]};}
 }};
}
''')
            helper = Path(__file__).parents[1] / "install/paseo_sdk.mjs"
            def validate(profile):
                request = {"operation": "validate", "profile": profile, "cache": directory,
                           "home": directory, "url": "ws://127.0.0.1:6767/ws", "cwd": directory}
                result = subprocess.run([shutil.which("node"), str(helper)], input=json.dumps(request), capture_output=True, text=True, timeout=5)
                self.assertEqual(result.returncode, 0, result.stdout)
                return json.loads(result.stdout)["reason"]
            self.assertIsNone(validate(PROFILE))
            self.assertIn("model", validate(dict(PROFILE, model="unknown")))
            self.assertIn("thinking", validate(dict(PROFILE, thinkingOptionId="medium")))
            self.assertIn("mode", validate(dict(PROFILE, modeId="Full Access")))
            self.assertIn("feature", validate(dict(PROFILE, featureValues={"unavailable": True})))
            self.assertIn("feature value", validate(dict(PROFILE, featureValues={"fast_mode": "true"})))
            self.assertIsNone(validate(dict(PROFILE, featureValues={"choice": "option-id"})))
            self.assertIn("feature value", validate(dict(PROFILE, featureValues={"choice": "Display"})))


if __name__ == "__main__":
    unittest.main()
