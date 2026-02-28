# Agent Context Studio (Tavily Alternative)

## Goal

Provide high-quality, fresh, structured context for AI agents and LLM apps.

## Output contract

- `answer_brief`: compact synthesis hint
- `citations`: URLs for grounding
- `context_chunks`: normalized evidence units
- `freshness_hint`: latency-informed freshness indicator

## Data sources

Primary source in this stack: **Searx** backend results.

## Dataset creation

Create datasets from:
- `open-search` generated rows
- `commoncrawl` connector-style generated rows

This allows offline eval/training workflows and agent memory bootstrapping.
