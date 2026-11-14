# sim

Synthetic data. Everything is invented, seeded and labelled `synthetic: true`.

| File | What |
|---|---|
| `generate_data.py` | The generator: merchants, payees, devices, tickets, 20,000 payouts, four fraud shapes |
| `models.py` | The tables. `Label` (the truth) is kept apart from everything the service reads |
| `dataset_io.py` | Writes and reads `data/synthetic/` (gzipped JSON lines plus a manifest with hashes) |
| `lookup.py` | Answers the hot path's questions from the dataset. Never touches labels |
| `replay.py` | Runs the dataset through the hot path in time order and prints a summary |
| `scenarios.py` | The four hand-written scenarios, with the evidence records an agent would see |
| `vocab.py` | Invented sectors, payee names, memos and ticket text |

Try it:

```bash
python -m hybrid_fraud.sim.replay          # rules-only results on the committed snapshot
python -m hybrid_fraud.sim.make_snapshot   # regenerate the snapshot (same seed, same bytes)
```

Rules alone, on the committed snapshot: 35% of fraud blocked, 42% held for review, 23% missed; 0.02% of legitimate payouts blocked and 0.2% held. These are properties of this generator, not of the world. See decisions D-011 to D-014.

*Built in Phase 1.*
