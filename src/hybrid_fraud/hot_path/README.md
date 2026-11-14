# hot_path

The fast, synchronous path. Fetch features (merchant row, velocity in count and dollars), run hard rules (`gate0_rules.py`), score, and route: APPROVE, BLOCK, FAST_HUMAN_LANE or PENDING_REVIEW. Every decision carries a reason code and an evidence trace built from real field values by templates, never by an LLM.

Target: p99 under 150 ms, measured in-process.

*Built in Phases 1 and 2.*
