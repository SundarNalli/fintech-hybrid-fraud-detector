# agent

The slow path for held payouts. The agent only recommends; the guard verifies and a deterministic policy decides.

| File | Job |
|---|---|
| `tools.py` | Four read-only tools (merchant profile, entity graph, tickets, beneficiary history) over `ReadOnlyRepository`. Bound to one payout, no arguments from the model. |
| `providers.py` | `LlmProvider` protocol, `OpenAICompatibleProvider` (httpx, OpenRouter by default) and `ReplayProvider` (JSON fixtures keyed by case id). |
| `budget.py` | Meters dollars (prices passed in), tool calls and seconds against `thresholds.agent`. |
| `orchestrator.py` | The plain tool-call loop. Returns an `AgentResult`: recommendation, the exact evidence records, call count, cost, latency. |
| `prompt.py` | System prompt and fenced blocks for attacker-controlled text. |

## Rules it keeps
- The final answer is a `submit_recommendation` call that validates as `Recommendation`.
- Timeout, malformed output, over budget, provider error, no tool support or a fifth tool call all return ESCALATE_HUMAN with a reason code (`agent_timeout`, `agent_malformed_output`, `agent_over_budget`, `agent_provider_error`, `agent_no_tool_support`, `agent_tool_call_limit`). Never an approval.
- Claims are not checked here. The guard checks them against `AgentResult.evidence`.

## Running without a key (D-005)
Set `LLM_API_KEY` (plus optionally `LLM_MODEL`, `LLM_BASE_URL`) in the environment to call a real model. With no key, `make_provider` returns the replay provider, which reads `<fixture_dir>/<case_id>.json`. The key is a `SecretStr` and is never printed or logged.

## After merge
`prompt.wrap_untrusted` is a minimal stand-in for `guard.injection_hygiene`. Swap it once the guard folder lands, so there is one delimiter function in the repo.
