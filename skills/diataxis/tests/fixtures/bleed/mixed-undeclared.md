# Caching notes

In this tutorial, we will turn on caching and look at the result. You should
see the hit counter climb after the second request, once the cache is warm and
the same city is asked for again.

The reason the cache sits at the edge is traffic shape: most requests ask for
the same few cities. Historically, each worker kept a private cache, and the
trade-off was memory against cold starts for every new worker in the fleet.
