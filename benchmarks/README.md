# Benchmarks

This folder is the permanent record of every Mintmed benchmark run: validation matrices, runtime pilots and diagnostic experiments.

| Path | Contents | In git? |
|---|---|---|
| [`benchmark_log.md`](benchmark_log.md) | The running log: one row per run, newest last. **Append to it every time a benchmark runs.** | yes |
| `runs/<github-run-id>/` | Small summary artifacts from each GitHub run: gate summaries, per-cell summaries, reports, resolved configs and pilot JSON | yes |
| [`manifest.sha256`](manifest.sha256) | SHA-256, path and size of every archived artifact file and local experiment output, so a copy can be checked for integrity | yes |
| `results/generated/archive/github/<run-id>/` | The complete downloaded GitHub artifacts, including raw per-dataset rows and every shard | no (git-ignored, local only) |
| `results/generated/<experiment>/` | Outputs of local diagnostic experiments | no (git-ignored, local only) |

## Why the split

GitHub keeps this repository's workflow artifacts for **14 days** only. The complete artifacts are therefore downloaded to `results/generated/archive/github/` as soon as a run finishes. The raw per-dataset rows total about 16 MB for the two validation matrices, and the shard files about 20 MB more. They are too large to belong in git, so only their summaries are committed here and the manifest fingerprints the rest.

The raw rows are needed to re-derive any gate result. Keep a backup of `results/generated/archive/` outside this machine.

## Adding a run

1. Download all of the run's artifacts right away:

   ```bash
   gh run download <run-id> -D results/generated/archive/github/<run-id>
   ```

2. Copy the small summary files into `runs/<run-id>/`.
3. Regenerate `manifest.sha256`, or append the new files to it.
4. Append a row to `benchmark_log.md`, and link the permanent record document if there is one.
