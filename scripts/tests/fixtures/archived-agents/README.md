# Archived Evidence Scout

`evidence-scout.toml` preserves the retired Luna max collector definition.
It is a frozen fixture for manifest migration, safe removal, and historical
evaluation reproducibility. This definition is not the active install source.

The restored Scout is a separate Luna xhigh definition at
`agents/evidence-scout.toml`, alongside `agents/astra_worker.toml` and
`agents/result-runner.toml`. Existing installations are upgraded or removed
through ownership manifests; modified files remain conflicts. Do not copy
this frozen Luna max definition into the active agent directory.
