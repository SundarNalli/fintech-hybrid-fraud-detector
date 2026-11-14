# store

SQLite plumbing.

| File | What |
|---|---|
| `db.py` | Opens the database (WAL), creates tables, loads the synthetic world. Never loads labels |
| `sqlite_lookup.py` | The hot path's questions, answered from SQLite. A test checks it gives the same decisions as the in-memory version on all 20,000 payouts |
| `readonly_repository.py` | The agent's view: a `mode=ro` connection bound to one moment, with no write methods |

Times are stored as epoch seconds. The agent's connection refuses writes at the database, so the guarantee does not rest on code behaving.

*Built in Phase 2.*
