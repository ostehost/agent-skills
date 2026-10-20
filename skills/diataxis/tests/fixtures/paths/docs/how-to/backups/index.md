# How to back up the database

This guide shows you how to take a manual database backup.

1. Open the admin console.
2. Run `backup now`.
3. Check the job log.
4. Copy the archive off the host.
5. Verify the copy with `backup verify`.

The command accepts these options:

| Option | Type | Default |
|---|---|---|
| `--target` | path | `/var/backups` |
| `--compress` | bool | `true` |
| `--level` | int | `6` |
| `--retain` | int | `7` |
| `--tag` | string | none |
| `--quiet` | bool | `false` |
