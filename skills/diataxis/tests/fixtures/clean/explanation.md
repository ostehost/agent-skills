---
diataxis: explanation
---

# About response caching

Why does the service cache responses at the edge instead of inside each
worker? The answer comes from the shape of the traffic.

## Why the cache sits at the edge

Most requests ask for the same few cities. The reason for caching at the edge
is that one cached answer serves every worker, so the hit rate stays high as
the fleet grows. Historically, each worker kept its own cache, and every new
worker started cold.

## Trade-offs

An edge cache is analogous to a shared library shelf: one copy serves many
readers, but the shelf can hold a stale edition. Some users prefer per-worker
caches because they keep latency predictable during an edge outage. That is a
reasonable design decision for small fleets, but it multiplies memory use as
the fleet grows.

The edge cache, in short, favours fleet-wide efficiency over isolation.
