# Open Search Console Guide

## Property onboarding

1. Open `/console`
2. Add property (domain or URL prefix)
3. Navigate to property detail page

## Verification methods

- DNS method: add TXT record with provided token
- URL-prefix method: upload verification file to root path

After completing external action, submit token in UI to mark verified.

## Analytics and diagnostics

For verified properties:
- impressions trend graph
- clicks trend graph
- CTR and average position table
- issue board (crawl/index/metadata quality findings)

## Searx relationship

Console is part of the same platform and aligned to Searx-driven discovery patterns. In this current build, metrics are seeded internally for deterministic operation; in production, wire crawlers and telemetry pipelines.
