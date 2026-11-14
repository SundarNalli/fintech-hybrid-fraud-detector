# The problem, restated

> Practice scenario. ThalentQore and every figure here are fictional.

## In one sentence

Money leaves in seconds. The truth about whether it was stolen arrives days later. We get a few seconds to guess.

## What is asked

A payment company pays merchants out in seconds ("Instant Payouts"). Fraud losses are 48 basis points: $0.48 lost per $100 paid out. The brief wants 15 bps or less, fewer good merchants wrongly stopped, and an AI investigator for the unclear cases.

## What this project builds

- **A fast rules path** that approves, blocks or holds each payout in about 150 ms.
- **A slow, checked AI path** for held payouts. The AI reads evidence through read-only tools and recommends. A verifier checks every claim against real records. A deterministic policy wrapper makes the final call.
- **A measurement** of what the AI path adds beyond rules, and what it costs per extra fraud caught. An earlier test gave the AI a perfect answer, so its numbers are ceilings, not results.

## What we know at payout time, and what we learn later

| Known at payout time | Learned later |
|---|---|
| Merchant profile and age, amount, beneficiary | Chargebacks (up to about 120 days) |
| Velocity in count and dollars | Bank returns (2 to 5 days) |
| Device and entity graph links | Fraud found only because the real merchant calls |
| KYB text, tickets, memos (attacker-controlled) | Whether a blocked payout was really fraud (never learned) |

## The four brief scenarios

The prototype must route all four as the brief expects. Fixtures are hand-written in Phase 1.

## What this does not prove

- Synthetic data only. Every effect size depends on how the generator was built.
- Latency is measured in-process, with no network.
- The labelled gray-zone cases are written by a person and a model, so they can flatter the agent.
- Nothing here says whether merchants accept a hold on an "Instant" payout.
