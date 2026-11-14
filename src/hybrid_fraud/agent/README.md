# agent

The slow path for held payouts. Four read-only tools (merchant profile, 2-hop entity graph, recent tickets, beneficiary history), a plain tool-call loop, a budget meter, and two LLM providers: OpenAI-compatible HTTP and Replay.

The agent only recommends. Timeout, malformed output or a missing key all end in ESCALATE_HUMAN, never an approval. Merchant text is attacker-controlled and goes in clearly delimited data blocks.

*Built in Phase 3.*
