# data

`synthetic/` is the committed snapshot of the generated world: seven gzipped tables and a `manifest.json` with the seed, generator version and a SHA-256 of each table. Everything is invented and labelled `synthetic: true`.

Regenerate with `python -m hybrid_fraud.sim.make_snapshot`. The same seed gives the same bytes; a test checks that the committed manifest still matches the generator.

`labels.jsonl.gz` holds the truth. Only the evaluation reads it, never the service. Local SQLite databases are git-ignored.
