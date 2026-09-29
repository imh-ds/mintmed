# Task 17 comparator: R mediation::mediate() on the exact datasets Mintmed analysed.
#
# Usage:
#   Rscript benchmarks/comparators/r/run_mediation.R --manifest DIR/manifest.json \
#       --output OUT.csv [--cells ID,ID] [--modes primary,secondary] \
#       [--boot-sims 399] [--qb-sims 1000] [--tool-id mediation] [--seed-offset 0]
#
# --tool-id and --seed-offset serve the Stage 1 noise-floor rerun (T17-S7):
# `--tool-id mediation_reseed --seed-offset 1000000007 --modes primary` refits
# the same datasets with R seed (analysis_seed + offset) mod (2^31 - 1), so its
# bootstrap resamples are independent of the primary run's. The support matrix
# is always mediation's.
#
# For each dataset of a supported cell it fits the cell's declared node models
# from cell.json (lm for gaussian nodes, glm(binomial("logit")) for bernoulli
# nodes) and calls mediate(treat = "A", mediator, control.value = 0,
# treat.value = 1):
#   primary   boot = TRUE, sims = 399, boot.ci.type = "perc" (nonparametric bootstrap)
#   secondary boot = FALSE, sims = 1000 (the package default quasi-Bayesian mode; descriptive)
# Estimand map: TNIE = d1 (ACME, treated), PNDE = z0 (ADE, control), TE = tau.coef.
# Cell 10: mediate(covariates = list(W = 0)) and list(W = 1) with the same seed,
# so both calls use the same bootstrap resamples (or quasi-Bayesian parameter
# draws); TNIE_difference is d1(W=1) - d1(W=0) with the percentile interval of
# the paired per-draw differences.
#
# Point estimates with boot = TRUE (mediation 4.5.1 source, mediate()):
# the bootstrap draws come from boot::boot(statistic = med.fun, R = sims); the
# reported d1/z0 are a separate med.fun() call on the original rows
# (index = 1:n), not the bootstrap mean. med.fun simulates one mediator value
# per observation (predicted mean + one N(0, sigma) draw for lm mediators, one
# Bernoulli draw for glm binomial ones), so the point estimate is exact when
# the outcome is linear in M (the shared error cancels) and carries Monte
# Carlo error otherwise (cells 08, 09, 11). tau.coef = (d1 + d0 + z1 + z0) / 2.
#
# Model frames: mediate() reads treat and mediator columns from
# model.frame(model); for an outcome with I(M^2) or ns(M) (cells 08, 09) or a
# reduced spec that omits A or M (cells 03-05) those columns are absent and
# mediate() stops with "undefined columns selected". Refits inside the
# bootstrap would also need the raw M. The runner therefore appends the missing
# raw dataset columns to each fit's stored model frame (fit$model); the fitted
# coefficients are unchanged and the added columns never enter a formula.

suppressPackageStartupMessages(suppressWarnings({
  library(jsonlite)
  library(splines)
  library(mediation)
}))
sys.source(file.path(local({
  file_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg[1L]))) else getwd()
}), "common.R"), envir = globalenv())

TOOL <- "mediation"
EFFECT_SOURCE <- c(TNIE = "d1", PNDE = "z0", TE = "tau")

fit_node <- function(node, data) {
  formula <- stats::as.formula(node_formula(node), env = new.env(parent = globalenv()))
  # The formula is spliced into the call (not referenced by name) because
  # mediate's bootstrap refits re-evaluate getCall(fit) with a new `data`
  # argument in its own environment.
  fit <- switch(
    node$family,
    gaussian = eval(bquote(stats::lm(.(formula), data = data))),
    bernoulli = eval(bquote(stats::glm(.(formula), family = stats::binomial(link = "logit"), data = data))),
    stop(sprintf("node family %s is not supported", node$family))
  )
  frame <- fit$model
  added <- setdiff(names(data), names(frame))
  for (column in added) frame[[column]] <- data[[column]]
  # With a transformed term (I(M^2), ns(M)) the stored frame holds the basis
  # evaluated at the observed M. mediate's quasi-Bayesian branch calls
  # model.matrix(terms(model.y), data = <frame with M replaced>), and
  # model.matrix reuses the stale basis columns when the frame carries a
  # "terms" attribute, silently giving ACME = 0. Dropping the attribute makes
  # model.matrix re-evaluate the terms (with the fit's stored knots) from the
  # simulated M. Plain-variable models keep their frame untouched.
  transformed <- setdiff(names(fit$model), c(names(data), "(weights)"))
  if (length(transformed)) attr(frame, "terms") <- NULL
  fit$model <- frame
  list(fit = fit, formula = node_formula(node), added = added, family = node$family,
       transformed = transformed)
}

describe_models <- function(m_fit, y_fit) {
  family_label <- function(item) if (item$family == "bernoulli") " [glm binomial logit]" else " [lm]"
  added <- unique(c(m_fit$added, y_fit$added))
  transformed <- unique(c(m_fit$transformed, y_fit$transformed))
  paste0(
    sprintf("model.m: %s%s; model.y: %s%s", m_fit$formula, family_label(m_fit), y_fit$formula, family_label(y_fit)),
    if (length(added)) sprintf("; raw columns appended to model frames: %s", paste(added, collapse = ",")) else "",
    if (length(transformed)) "; terms attribute dropped from frames with transformed terms" else ""
  )
}

call_mediate <- function(models, mediator, mode, settings, covariates = NULL) {
  arguments <- list(
    model.m = models$m$fit, model.y = models$y$fit, treat = "A", mediator = mediator,
    control.value = 0, treat.value = 1
  )
  if (!is.null(covariates)) arguments$covariates <- covariates
  if (mode == "primary") {
    arguments$boot <- TRUE
    arguments$sims <- settings$boot_sims
    arguments$boot.ci.type <- "perc"
  } else {
    arguments$boot <- FALSE
    arguments$sims <- settings$qb_sims
  }
  do.call(mediation::mediate, arguments)
}

effect_value <- function(result, source) {
  switch(
    source,
    d1 = list(estimate = result$d1, ci = result$d1.ci, sims = as.numeric(result$d1.sims)),
    z0 = list(estimate = result$z0, ci = result$z0.ci, sims = as.numeric(result$z0.sims)),
    tau = list(estimate = result$tau.coef, ci = result$tau.ci, sims = as.numeric(result$tau.sims))
  )
}

mode_methods <- function(mode, settings) {
  if (mode == "primary") {
    list(
      sims = settings$boot_sims,
      point = "original-sample med.fun (one simulated mediator draw per observation)",
      interval = sprintf("percentile, %d nonparametric bootstrap refits (quantile type 7)", settings$boot_sims)
    )
  } else {
    list(
      sims = settings$qb_sims,
      point = "mean over quasi-Bayesian simulations",
      interval = sprintf("percentile, %d quasi-Bayesian simulations", settings$qb_sims)
    )
  }
}

run_mode <- function(context, cell, models, mode, settings, fit_seconds) {
  methods <- mode_methods(mode, settings)
  mediator <- cell$mediators[[1L]]$name
  model_text <- describe_models(models$m, models$y)
  effects <- unlist(cell$effects)
  rows <- list()
  start <- proc.time()
  moderated <- all(c("TNIE_W0", "TNIE_W1", "TNIE_difference") %in% effects)
  if (!moderated) {
    covariates <- if (length(cell$moderator_values)) cell$moderator_values else NULL
    seed_rng(context$r_seed)
    outcome <- guarded(call_mediate(models, mediator, mode, settings, covariates))
    runtime <- elapsed(start) + fit_seconds
    for (effect in effects) {
      if (outcome$failed) {
        rows[[length(rows) + 1L]] <- new_row(context, mode, effect, status = "error",
          message = c(outcome$value$message, outcome$warnings), runtime = runtime,
          sims_requested = methods$sims, model = model_text, point_method = methods$point,
          interval_method = methods$interval)
        next
      }
      value <- effect_value(outcome$value, EFFECT_SOURCE[[effect]])
      rows[[length(rows) + 1L]] <- new_row(context, mode, effect, value$estimate, value$ci[[1L]], value$ci[[2L]],
        status = if (length(outcome$warnings)) "ok_warnings" else "ok", message = outcome$warnings,
        runtime = runtime, sims_requested = methods$sims, sims_successful = sum(is.finite(value$sims)),
        model = model_text, point_method = methods$point, interval_method = methods$interval)
    }
    return(rows)
  }

  moderator <- cell$moderators[[1L]]$name
  results <- list()
  for (level in c(0, 1)) {
    covariates <- setNames(list(level), moderator)
    seed_rng(context$r_seed)  # same seed: identical resamples / parameter draws at W = 0 and W = 1
    results[[as.character(level)]] <- guarded(call_mediate(models, mediator, mode, settings, covariates))
  }
  runtime <- elapsed(start) + fit_seconds
  warnings <- unique(c(results[["0"]]$warnings, results[["1"]]$warnings))
  status <- if (length(warnings)) "ok_warnings" else "ok"
  for (level in c(0, 1)) {
    effect <- sprintf("TNIE_%s%d", moderator, level)
    outcome <- results[[as.character(level)]]
    if (outcome$failed) {
      rows[[length(rows) + 1L]] <- new_row(context, mode, effect, status = "error",
        message = c(outcome$value$message, warnings), runtime = runtime, sims_requested = methods$sims,
        model = model_text, point_method = methods$point, interval_method = methods$interval)
    } else {
      value <- effect_value(outcome$value, "d1")
      rows[[length(rows) + 1L]] <- new_row(context, mode, effect, value$estimate, value$ci[[1L]], value$ci[[2L]],
        status = status, message = warnings, runtime = runtime, sims_requested = methods$sims,
        sims_successful = sum(is.finite(value$sims)), model = model_text,
        point_method = methods$point, interval_method = methods$interval)
    }
  }
  difference_interval <- "percentile of paired per-draw differences d1(W=1) - d1(W=0)"
  if (results[["0"]]$failed || results[["1"]]$failed) {
    rows[[length(rows) + 1L]] <- new_row(context, mode, "TNIE_difference", status = "error",
      message = c("a conditional mediate() call failed", warnings), runtime = runtime,
      sims_requested = methods$sims, model = model_text, point_method = "d1(W=1) - d1(W=0)",
      interval_method = difference_interval)
    return(rows)
  }
  low <- effect_value(results[["0"]]$value, "d1")
  high <- effect_value(results[["1"]]$value, "d1")
  # Pairing check: the outcome model has no A x W term, so z0 does not depend
  # on W and its draws must agree (to rounding) when the resamples are shared.
  z_low <- as.numeric(results[["0"]]$value$z0.sims)
  z_high <- as.numeric(results[["1"]]$value$z0.sims)
  paired <- length(z_low) == length(z_high) &&
    isTRUE(max(abs(z_low - z_high), na.rm = TRUE) <= 1e-9 * (1 + max(abs(z_low), na.rm = TRUE)))
  draws <- high$sims - low$sims
  if (!paired) {
    rows[[length(rows) + 1L]] <- new_row(context, mode, "TNIE_difference", high$estimate - low$estimate,
      status = "error", message = c("draws at W=0 and W=1 are not paired", warnings), runtime = runtime,
      sims_requested = methods$sims, model = model_text, point_method = "d1(W=1) - d1(W=0)",
      interval_method = difference_interval)
    return(rows)
  }
  ci <- stats::quantile(draws, c(0.025, 0.975), na.rm = TRUE, names = FALSE)
  rows[[length(rows) + 1L]] <- new_row(context, mode, "TNIE_difference", high$estimate - low$estimate,
    ci[[1L]], ci[[2L]], status = status, message = warnings, runtime = runtime,
    sims_requested = methods$sims, sims_successful = sum(is.finite(draws)), model = model_text,
    point_method = "d1(W=1) - d1(W=0)", interval_method = difference_interval)
  rows
}

process_dataset <- function(entry, root, support, settings, cells_cache) {
  context <- dataset_context(entry, settings$tool_id, "mediation", settings$seed_offset)
  cell <- cells_cache[[entry$cell_id]]
  effects <- unlist(cell$effects)
  rows <- list()
  if (!entry$cell_id %in% unlist(support$supported)) {
    reason <- support$not_estimable[[entry$cell_id]]
    if (is.null(reason)) reason <- "cell is not in the mediation support matrix"
    for (mode in settings$modes) for (effect in effects) {
      rows[[length(rows) + 1L]] <- new_row(context, mode, effect, status = "not_estimable", message = reason)
    }
    return(rows)
  }
  start <- proc.time()
  fitted <- guarded({
    if (length(cell$mediators) != 1L) stop("mediate() needs exactly one mediator")
    data <- read_dataset(root, entry$path)
    mediator <- cell$mediators[[1L]]$name
    list(
      m = fit_node(node_by_response(cell, mediator), data),
      y = fit_node(node_by_response(cell, cell$outcome$name), data)
    )
  })
  fit_seconds <- elapsed(start)
  for (mode in settings$modes) {
    if (fitted$failed) {
      for (effect in effects) {
        rows[[length(rows) + 1L]] <- new_row(context, mode, effect, status = "error",
          message = c(fitted$value$message, fitted$warnings), runtime = fit_seconds)
      }
      next
    }
    mode_rows <- run_mode(context, cell, fitted$value, mode, settings, fit_seconds)
    if (length(fitted$warnings)) {
      mode_rows <- lapply(mode_rows, function(row) {
        row$message <- clean_message(c(fitted$warnings, row$message))
        if (row$status == "ok") row$status <- "ok_warnings"
        row
      })
    }
    rows <- c(rows, mode_rows)
  }
  rows
}

main <- function() {
  options <- parse_args(list(manifest = "", output = "", cells = "", modes = "primary,secondary",
                             boot_sims = "399", qb_sims = "1000", tool_id = TOOL, seed_offset = "0"))
  if (!nzchar(options$manifest) || !nzchar(options$output)) stop("--manifest and --output are required")
  settings <- list(
    modes = split_list(options$modes),
    boot_sims = as.integer(options$boot_sims),
    qb_sims = as.integer(options$qb_sims),
    tool_id = options$tool_id,
    seed_offset = parse_seed_offset(options$seed_offset)
  )
  if (!all(settings$modes %in% c("primary", "secondary"))) stop("--modes must be primary and/or secondary")
  if (!grepl("^[a-z_]+$", settings$tool_id)) stop("--tool-id must be lower-case letters and underscores")
  if (identical(settings$tool_id, TOOL) != (settings$seed_offset == 0)) {
    stop("a seed offset needs its own --tool-id, and a non-default --tool-id needs a nonzero --seed-offset")
  }
  root <- dirname(normalizePath(options$manifest, winslash = "/"))
  manifest <- read_manifest(options$manifest)
  support <- read_support()$tools[[TOOL]]
  entries <- selected_datasets(manifest, split_list(options$cells))
  cells_cache <- list()
  for (cell_id in unique(vapply(entries, function(entry) entry$cell_id, character(1)))) {
    cells_cache[[cell_id]] <- read_cell(root, cell_id)
  }
  rows <- list()
  for (entry in entries) {
    result <- guarded(process_dataset(entry, root, support, settings, cells_cache))
    if (result$failed) {
      context <- dataset_context(entry, settings$tool_id, "mediation", settings$seed_offset)
      for (mode in settings$modes) for (effect in unlist(cells_cache[[entry$cell_id]]$effects)) {
        rows[[length(rows) + 1L]] <- new_row(context, mode, effect, status = "error",
          message = c("runner error", result$value$message))
      }
    } else {
      rows <- c(rows, result$value)
    }
  }
  write_long(rows, options$output)
  cat(sprintf("%s: wrote %d row(s) for %d dataset(s) to %s\n", settings$tool_id, length(rows), length(entries), options$output))
}

main()
