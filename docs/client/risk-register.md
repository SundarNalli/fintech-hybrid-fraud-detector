# Risk register

> Likelihood and impact are my judgement for a prototype heading to a pilot, not measured values. Change them with the client.

| # | Risk | Likelihood | Impact | Mitigation in the design | Still open |
|---|---|---|---|---|---|
| R1 | The real model is less accurate or slower than hoped | High | Medium | Agent only advises; verifier and policy wrapper decide; timeout and failure escalate to a human | No real model measured (O-003) |
| R2 | The agent is not needed: rules already do the job | Medium | Medium | Shadow mode measures the gain on real data before spend is committed | The synthetic world cannot say either way |
| R3 | Fraud the rules approve never reaches the agent (23% of fraud payouts here) | High | High | Reported openly; fixing it is rule work | No fix yet |
| R4 | A prompt-injection memo or ticket steers the model | Medium | High | Merchant text fenced and marked untrusted; claims must match records; policy wrapper has the final say | Only hand-written attacks tested |
| R5 | Two parts disagree on a field name and a safety rule silently never fires | Medium | High | Found once already (hard-fact names); a test now checks the guard against real repository output | The same class of bug can return with a new field |
| R6 | The AI approval cap is wrong | High | Medium | An invented placeholder (A-19), isolated in config | A business decision nobody has made |
| R7 | The 8 s hold cannot be met with several model round trips | Medium | Medium | Hold lives in SQLite; reaper escalates; hot path never waits | Latency unmeasured with a real model |
| R8 | Tampering with the newest ledger rows goes unnoticed | Low | Medium | Triggers reject UPDATE/DELETE; hash chain detects edits | A chain cannot detect truncation of the tail; needs an external anchor |
| R9 | One SQLite writer lock limits throughput | Medium | Medium | Honest for a prototype; latency numbers include waiting | Not load-tested beyond the 50,000-event run |
| R10 | Labels arrive months late, so loss claims are premature | High | Medium | Maturity window stated with every loss figure | Client label process unknown |
| R11 | Model cost grows with volume | Medium | Medium | Per-case budget meter; dollar cap on live runs | Real prices not entered |
| R12 | Customer data reaches a model provider | Medium | High | Prototype uses synthetic data only | Needs a data-handling and provider review before any real data |
| R13 | Reviewers over-trust the AI's explanation | Medium | High | Evidence shown beside every claim; output framed as advice | Needs measuring in the advisory stage |
| R14 | Definitions of false positive and auto-resolution differ from the client's | High | Medium | Both variants reported (KPI 3, 4, 6) | O-002 open |
