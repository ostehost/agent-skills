---
diataxis: how-to
---

# How to rotate a leaked API key

This guide shows you how to replace a leaked API key without dropping live
traffic. It assumes you administer the service and can sign in to its admin
console.

1. Open the admin console and go to **Keys**.
2. Create a second key with the same scopes as the leaked one.
3. Copy the new key into your secret store.
4. Restart the workers so they read the new key.
5. Revoke the leaked key from the **Keys** page.

The workers load the key once, at start-up.

If your workers run on Kubernetes, restart the deployment instead of each worker:

```console
$ kubectl rollout restart deployment/workers
```

If you want to confirm the rotation, check the audit log for a `key.revoked`
event. When the log shows no requests signed with the old key for an hour,
delete the old key from the secret store as well.
