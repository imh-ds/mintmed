# R comparator environment (Task 17)

Task 17 compares Mintmed with R's `mediation::mediate()` and with `lavaan`.
lavaan is used **only as an observed-variable path model**: `lavaan::sem()` on
measured variables, with no latent variables and no measurement model.

## What is pinned

| Item | Pin |
| --- | --- |
| R | 4.6.x |
| Package snapshot | Posit Package Manager CRAN, **2026-07-16** |
| mediation | 4.5.1 |
| lavaan | 0.6-21 |
| jsonlite | 2.0.0 |

Dependencies come from the same snapshot, so the snapshot date fixes every
version. R's bundled recommended packages (MASS, Matrix, boot, ...) come with
R itself; `versions.R` records them.

The pins live in `pins.R`. 2026-07-16 is the last snapshot with lavaan 0.6-21;
from 2026-07-17 the snapshot serves lavaan 0.7-2. Changing the date is a
deliberate re-pin: update `COMPARATOR_PINNED` to match, or the install fails.

Snapshot URLs:

- Linux (binaries): `https://packagemanager.posit.co/cran/__linux__/<codename>/2026-07-16`,
  for example `__linux__/noble/...` on `ubuntu-latest`.
- Windows and macOS: `https://packagemanager.posit.co/cran/2026-07-16`.

## Files

- `pins.R` — the snapshot date, the pinned versions and the helper that builds the snapshot URL.
- `install_packages.R` — installs any pinned package that is missing or at the
  wrong version, with its hard dependencies, from the snapshot. It then checks
  the exact versions and that each package loads. It exits non-zero on any
  mismatch. `--check-only` runs the checks without downloading.
- `versions.R` — prints R, the platform, the snapshot and the package versions as one JSON object, used to stamp comparator outputs.
- `run_mediation.R`, `run_lavaan.R` — the comparator runners. Each reads an
  export from `scripts/export_validation_datasets.py` (`--manifest DIR/manifest.json`)
  and writes one long CSV row per mode × dataset × effect. `common.R` holds
  their shared helpers (seed rule, formula builder, error capture, CSV writer).
  The support matrix is `../support_matrix.json`. The fitted models and
  estimand mapping are documented in `docs/validation/comparator_support.md`.

## Run the comparators

```sh
python scripts/export_validation_datasets.py --config configs/mediation_validation_v3.yaml --output OUT --cell-id cell01_linear_n100 --replicate-stop 2
Rscript benchmarks/comparators/r/run_mediation.R --manifest OUT/manifest.json --output mediation.csv
Rscript benchmarks/comparators/r/run_lavaan.R --manifest OUT/manifest.json --output lavaan.csv
```

The shardable wrapper does both steps and writes `raw_metrics.csv`:

```sh
python -m mintmed.experiments.comparator_benchmark --config configs/mediation_validation_v3.yaml \
    --output OUT --cell-id cell01_linear_n100 --replicate-block 0of4 [--tool mediation|lavaan|all]
```

In `sharded_benchmark.yml`, dispatch it with:

- `runner_module = mintmed.experiments.comparator_benchmark`;
- `with_r = "true"`;
- `--cell-id` and `--replicate-block` as the two shard dimensions.

## Install locally

```sh
Rscript benchmarks/comparators/r/install_packages.R              # installs into R's first library path
Rscript benchmarks/comparators/r/install_packages.R --check-only # verify only
Rscript benchmarks/comparators/r/versions.R
```

Set `R_COMPARATOR_LIB` to install into a separate library. When you do, also
set `R_LIBS` to that path so that other R sessions find it. The scripts write
nothing outside the target library.

## CI

- `verification.yml`, job `r-comparators-env`, runs on every push and
  dispatch. It sets up R 4.6 with `r-lib/actions/setup-r@v2`, runs
  `install_packages.R` and prints `versions.R`. The library in
  `$RUNNER_TEMP/r-comparator-lib` is cached with `actions/cache`. The cache key
  combines the Ubuntu codename, R 4.6 and a hash of `pins.R` and
  `install_packages.R`.
- `sharded_benchmark.yml` has the dispatch input `with_r` (default `"false"`).
  When it is `"true"`, each shard sets up R and restores the same cache. The
  shard then runs `install_packages.R`, which only checks versions on a cache
  hit, before the runner. A push to the branch warms the cache for later
  dispatches from it.
