# Shared helpers for the Task 17 R comparator runners (run_mediation.R and
# run_lavaan.R). Sourced by both; defines functions only.
#
# Inputs are the files written by scripts/export_validation_datasets.py:
#   <dir>/manifest.json, <dir>/<cell_id>/cell.json, <dir>/<cell_id>/rep_RRRR.csv
# The output is one long CSV (LONG_COLUMNS) with a row per
# tool x mode x cell x replicate x effect. Every dataset listed in the
# manifest yields rows: errors and unsupported cells become statuses.

LONG_COLUMNS <- c(
  "tool", "mode", "cell_id", "replicate", "effect", "estimate", "lower", "upper",
  "status", "message", "runtime_seconds", "sims_requested", "sims_successful",
  "r_seed", "data_seed", "analysis_seed", "dataset_sha256", "model",
  "point_method", "interval_method", "r_version", "package", "package_version"
)

# Largest prime below 2^31; R's set.seed() takes a 32-bit integer.
SEED_MODULUS <- 2147483647

script_dir <- function() {
  file_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg[1L]))) else getwd()
}

# Parse --key value pairs into a named list, filling `defaults`.
parse_args <- function(defaults, args = commandArgs(trailingOnly = TRUE)) {
  out <- defaults
  i <- 1L
  while (i <= length(args)) {
    key <- args[[i]]
    if (!startsWith(key, "--")) stop(sprintf("unexpected argument %s", key))
    name <- gsub("-", "_", substring(key, 3L))
    if (!name %in% names(defaults)) stop(sprintf("unknown option %s", key))
    if (i == length(args)) stop(sprintf("option %s needs a value", key))
    out[[name]] <- args[[i + 1L]]
    i <- i + 2L
  }
  out
}

split_list <- function(value) {
  if (is.null(value) || !nzchar(value)) return(character())
  trimws(strsplit(value, ",", fixed = TRUE)[[1L]])
}

# Seed rule: the manifest's analysis_seed is an unsigned 64-bit integer stored
# as a decimal string (above 2^53, so it must never pass through a double).
# The R seed is analysis_seed mod (2^31 - 1), computed digit by digit so every
# intermediate value stays below 10 * 2^31 < 2^53 and is exact in a double.
# Python: int(analysis_seed) % 2147483647.
seed_from_decimal <- function(text) {
  text <- as.character(text)
  if (length(text) != 1L || !grepl("^[0-9]+$", text)) stop("analysis_seed must be a decimal string")
  r <- 0
  for (digit in as.integer(strsplit(text, "", fixed = TRUE)[[1L]])) {
    r <- (r * 10 + digit) %% SEED_MODULUS
  }
  as.integer(r)
}

# Fix the generator kinds explicitly so a changed R default cannot change draws.
seed_rng <- function(seed) {
  RNGkind(kind = "Mersenne-Twister", normal.kind = "Inversion", sample.kind = "Rejection")
  set.seed(seed)
}

read_manifest <- function(path) {
  manifest <- jsonlite::fromJSON(path, simplifyVector = FALSE)
  datasets <- manifest$datasets
  # Keep the seeds as strings: never let jsonlite turn them into doubles.
  for (entry in datasets) {
    if (!is.character(entry$analysis_seed) || !is.character(entry$data_seed)) {
      stop("manifest seeds must be decimal strings")
    }
  }
  manifest
}

read_cell <- function(root, cell_id) {
  jsonlite::fromJSON(file.path(root, cell_id, "cell.json"), simplifyVector = FALSE)
}

read_dataset <- function(root, relative_path) {
  # read.csv parses %.17g text with R's correctly rounded strtod.
  utils::read.csv(file.path(root, relative_path), colClasses = "numeric", check.names = FALSE)
}

read_support <- function(dir = script_dir()) {
  jsonlite::fromJSON(file.path(dirname(dir), "support_matrix.json"), simplifyVector = FALSE)
}

node_by_response <- function(cell, response) {
  for (node in cell$nodes) if (identical(node$response, response)) return(node)
  stop(sprintf("cell %s has no node for %s", cell$cell_id, response))
}

# R formula for one exported node, term for term the model Mintmed fits.
# quadratic -> I(x^2) alone (no linear x unless declared);
# natural_spline -> splines::ns(x, df = df), which places its knots exactly
# where patsy's cr(x, df, constraints = "center") does (see comparator_support.md).
node_formula <- function(node) {
  pieces <- character()
  for (term in node$terms) {
    v <- term$variable
    pieces <- c(pieces, switch(
      term$kind,
      linear = v,
      quadratic = sprintf("I(%s^2)", v),
      natural_spline = sprintf("ns(%s, df = %d)", v, as.integer(term$df)),
      stop(sprintf("term kind %s is not supported by the R runners", term$kind))
    ))
  }
  for (pair in node$interactions) {
    pieces <- c(pieces, sprintf("%s:%s", pair[[1L]], pair[[2L]]))
  }
  rhs <- if (length(pieces)) paste(pieces, collapse = " + ") else "1"
  if (!isTRUE(node$intercept)) rhs <- paste(rhs, "- 1")
  sprintf("%s ~ %s", node$response, rhs)
}

# Evaluate `expr`, collecting warnings (muffled) and turning an error into a value.
guarded <- function(expr) {
  warnings <- character()
  value <- withCallingHandlers(
    tryCatch(expr, error = function(e) structure(list(message = conditionMessage(e)), class = "runner_error")),
    warning = function(w) {
      warnings <<- c(warnings, conditionMessage(w))
      invokeRestart("muffleWarning")
    },
    message = function(m) invokeRestart("muffleMessage")
  )
  list(value = value, warnings = unique(warnings), failed = inherits(value, "runner_error"))
}

clean_message <- function(parts) {
  parts <- parts[nzchar(parts)]
  if (!length(parts)) return("")
  text <- paste(unique(parts), collapse = " | ")
  text <- gsub("[\r\n\t]+", " ", text)
  if (nchar(text) > 500L) text <- paste0(substr(text, 1L, 497L), "...")
  text
}

elapsed <- function(start) as.numeric((proc.time() - start)[["elapsed"]])

new_row <- function(context, mode, effect, estimate = NA_real_, lower = NA_real_, upper = NA_real_,
                    status, message = "", runtime = NA_real_, sims_requested = NA_integer_,
                    sims_successful = NA_integer_, model = "", point_method = "", interval_method = "") {
  data.frame(
    tool = context$tool, mode = mode, cell_id = context$cell_id, replicate = context$replicate,
    effect = effect, estimate = as.numeric(estimate), lower = as.numeric(lower), upper = as.numeric(upper),
    status = status, message = clean_message(message), runtime_seconds = as.numeric(runtime),
    sims_requested = as.integer(sims_requested), sims_successful = as.integer(sims_successful),
    r_seed = context$r_seed, data_seed = context$data_seed, analysis_seed = context$analysis_seed,
    dataset_sha256 = context$sha256, model = model, point_method = point_method,
    interval_method = interval_method, r_version = as.character(getRversion()),
    package = context$package, package_version = context$package_version,
    stringsAsFactors = FALSE
  )
}

# Write numbers with 17 significant digits (lossless for doubles).
write_long <- function(rows, path) {
  frame <- if (length(rows)) do.call(rbind, rows) else
    as.data.frame(setNames(replicate(length(LONG_COLUMNS), character(), simplify = FALSE), LONG_COLUMNS))
  frame <- frame[, LONG_COLUMNS, drop = FALSE]
  for (column in c("estimate", "lower", "upper", "runtime_seconds")) {
    values <- frame[[column]]
    frame[[column]] <- ifelse(is.na(values), "", sprintf("%.17g", values))
  }
  dir.create(dirname(path), recursive = TRUE, showWarnings = FALSE)
  temporary <- paste0(path, ".tmp")
  utils::write.csv(frame, temporary, row.names = FALSE, na = "", fileEncoding = "UTF-8")
  file.rename(temporary, path)
  invisible(frame)
}

# Iterate over the manifest's datasets, restricted to `cells` when given.
selected_datasets <- function(manifest, cells) {
  keep <- Filter(function(entry) !length(cells) || entry$cell_id %in% cells, manifest$datasets)
  keep
}

# Seed offset of a noise-floor rerun (T17-S7): the rerun's seed is
# (analysis_seed + offset) mod (2^31 - 1). Both terms are below 2^31, so the
# sum is exact in a double. Python: (int(analysis_seed) + offset) % 2147483647.
parse_seed_offset <- function(text) {
  text <- as.character(text)
  if (length(text) != 1L || !grepl("^[0-9]+$", text)) stop("--seed-offset must be a non-negative integer")
  offset <- as.numeric(text)
  if (offset >= SEED_MODULUS) stop("--seed-offset must be below 2147483647")
  offset
}

offset_seed <- function(seed, offset = 0) as.integer((seed + offset) %% SEED_MODULUS)

dataset_context <- function(entry, tool, package, seed_offset = 0) {
  list(
    tool = tool, cell_id = entry$cell_id, replicate = as.integer(entry$replicate),
    r_seed = offset_seed(seed_from_decimal(entry$analysis_seed), seed_offset), data_seed = entry$data_seed,
    analysis_seed = entry$analysis_seed, sha256 = entry$sha256, package = package,
    package_version = as.character(utils::packageVersion(package))
  )
}
