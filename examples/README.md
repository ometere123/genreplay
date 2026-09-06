# Examples

`sample-scenario.json` documents the portable scenario schema only. It is intentionally not presented as a valid GenLayer execution.

Generate a real scenario from a captured transaction:

```bash
genreplay capture 0x... -o incident.genreplay
genreplay fork incident.genreplay -o incident.json
```
