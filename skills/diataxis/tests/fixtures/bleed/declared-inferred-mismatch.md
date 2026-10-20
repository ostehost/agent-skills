---
diataxis: reference
---

# Cache design

The reason the cache sits at the edge is traffic shape. Most requests ask for
the same few cities, so one shared copy serves many workers.

## Why not per-worker caches

Per-worker caches are analogous to private bookshelves: each reader keeps a
copy. Some users prefer them for predictable latency. The trade-off is memory,
which grows with every worker added to the fleet, and cold starts, which hurt
each new worker until its private copy fills with the popular cities.
