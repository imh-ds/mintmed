# Task 17 comparator: lavaan used purely as an observed-variable path model.
#
# Usage:
#   Rscript benchmarks/comparators/r/run_lavaan.R --manifest DIR/manifest.json \
#       --output OUT.csv [--cells ID,ID] [--modes primary,secondary] [--bootstrap 399]
#
# For each dataset of a supported cell the lavaan syntax is generated from the
# exported node specifications (cell.json): one labelled regression per
# mediator and outcome node, with exactly the terms Mintmed fits (so the
# reduced specs of cells 03-05 omit the same path). There are no latent
# variables and no measurement model. Interactions become observed product
# columns (cell 10: W_x_A = W * A in the M equation, W_x_M = W * M in the Y
# equation). Effects are `:=` defined parameters:
#   TNIE  := sum over directed A -> mediator(s) -> Y paths of the products of
#            the path coefficients (conditional on moderator values);
#   PNDE  := the direct A -> Y coefficient (conditional on moderator values);
#   TE    := PNDE + TNIE.
# Cell 10: TNIE_W0, TNIE_W1 (conditional indirect effects at W = 0, 1) and
# TNIE_difference := TNIE_W1 - TNIE_W0. A TNIE with no A -> ... -> Y path
# through a mediator (cells 03-05) is a structural zero of the fitted model
# and is reported as 0 with interval [0, 0] without a lavaan parameter.
#   primary   sem(se = "bootstrap", bootstrap = 399), parameterEstimates(boot.ci.type = "perc")
#   secondary sem() defaults: ML with delta-method standard errors and normal-theory 95% intervals
# Regression coefficients of these recursive observed-variable models are the
# equation-by-equation OLS coefficients (the likelihood factorises by node);
# lavaan's ML residual variances divide by N rather than N - p, which does not
# change any coefficient or effect.

suppressPackageStartupMessages(suppressWarnings({
  library(jsonlite)
  library(lavaan)
}))
sys.source(file.path(local({
  file_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg[1L]))) else getwd()
}), "common.R"), envir = globalenv())

TOOL <- "lavaan"

product_name <- function(left, right) sprintf("%s_x_%s", left, right)
coef_label <- function(response, column) gsub("[^A-Za-z0-9_]", "_", sprintf("%s__%s", response, column))

# Build the path model for one cell. Returns the syntax, the product columns
# to add to the data and, per effect, an expression over the labels
# (or NULL for a structural zero).
build_model <- function(cell) {
  exposure <- cell$exposure$name
  outcome <- cell$outcome$name
  mediators <- vapply(cell$mediators, function(item) item$name, character(1))
  moderators <- vapply(cell$moderators, function(item) item$name, character(1))
  nodes <- c(mediators, outcome)
  lines <- character()
  products <- list()
  # coefficients[[response]][[parent]] = list(main = label or NULL, by = list(moderator = label))
  coefficients <- list()
  for (response in nodes) {
    node <- node_by_response(cell, response)
    if (node$family != "gaussian") stop(sprintf("node %s is %s; lavaan path products need gaussian nodes", response, node$family))
    rhs <- character()
    entry <- list()
    for (term in node$terms) {
      if (term$kind != "linear") stop(sprintf("term %s(%s) is not linear; natural effects are not path products", term$kind, term$variable))
      label <- coef_label(response, term$variable)
      rhs <- c(rhs, sprintf("%s*%s", label, term$variable))
      entry[[term$variable]] <- list(main = label, by = list())
    }
    for (pair in node$interactions) {
      left <- pair[[1L]]
      right <- pair[[2L]]
      column <- product_name(left, right)
      products[[column]] <- c(left, right)
      label <- coef_label(response, column)
      rhs <- c(rhs, sprintf("%s*%s", label, column))
      if (left %in% moderators && !right %in% moderators) {
        parent <- right; moderator <- left
      } else if (right %in% moderators && !left %in% moderators) {
        parent <- left; moderator <- right
      } else {
        stop(sprintf("interaction %s:%s is not a moderator x path interaction", left, right))
      }
      if (is.null(entry[[parent]])) entry[[parent]] <- list(main = NULL, by = list())
      entry[[parent]]$by[[moderator]] <- label
    }
    lines <- c(lines, sprintf("%s ~ %s", response, paste(rhs, collapse = " + ")))
    coefficients[[response]] <- entry
  }
  list(
    lines = lines, products = products, coefficients = coefficients, exposure = exposure,
    outcome = outcome, mediators = mediators, moderators = moderators
  )
}

# Conditional coefficient of `parent` in the `response` equation at moderator values.
conditional_coefficient <- function(model, response, parent, values) {
  entry <- model$coefficients[[response]][[parent]]
  if (is.null(entry)) return(NULL)
  pieces <- character()
  if (!is.null(entry$main)) pieces <- c(pieces, entry$main)
  for (moderator in names(entry$by)) {
    value <- values[[moderator]]
    if (is.null(value)) stop(sprintf("no value for moderator %s", moderator))
    if (value != 0) pieces <- c(pieces, sprintf("%s*%s", format(value, digits = 17), entry$by[[moderator]]))
  }
  if (!length(pieces)) return("0")
  if (length(pieces) == 1L) pieces else sprintf("(%s)", paste(pieces, collapse = " + "))
}

# Sum of path products over directed paths exposure -> mediator(s) -> outcome.
indirect_expression <- function(model, values) {
  products <- character()
  walk <- function(node, factors) {
    for (child in c(model$mediators, model$outcome)) {
      coefficient <- conditional_coefficient(model, child, node, values)
      if (is.null(coefficient)) next
      if (child == model$outcome) {
        if (length(factors)) products <<- c(products, paste(c(factors, coefficient), collapse = "*"))
      } else {
        walk(child, c(factors, coefficient))
      }
    }
  }
  walk(model$exposure, character())
  if (!length(products)) return(NULL)
  paste(products, collapse = " + ")
}

effect_definitions <- function(cell, model) {
  effects <- unlist(cell$effects)
  base_values <- cell$moderator_values
  definitions <- list()
  if (all(c("TNIE_W0", "TNIE_W1", "TNIE_difference") %in% effects)) {
    moderator <- model$moderators[[1L]]
    low <- indirect_expression(model, setNames(list(0), moderator))
    high <- indirect_expression(model, setNames(list(1), moderator))
    definitions$TNIE_W0 <- low
    definitions$TNIE_W1 <- high
    definitions$TNIE_difference <- if (is.null(low) && is.null(high)) NULL else
      sprintf("(%s) - (%s)", if (is.null(high)) "0" else high, if (is.null(low)) "0" else low)
    return(definitions[effects])
  }
  direct <- conditional_coefficient(model, model$outcome, model$exposure, base_values)
  indirect <- indirect_expression(model, base_values)
  definitions$TNIE <- indirect
  definitions$PNDE <- direct
  definitions$TE <- paste(c(direct, indirect), collapse = " + ")
  definitions[effects]
}

model_syntax <- function(model, definitions) {
  defined <- character()
  for (effect in names(definitions)) {
    if (!is.null(definitions[[effect]])) defined <- c(defined, sprintf("%s := %s", effect, definitions[[effect]]))
  }
  paste(c(model$lines, defined), collapse = "\n")
}

add_products <- function(data, products) {
  for (column in names(products)) {
    pair <- products[[column]]
    data[[column]] <- data[[pair[[1L]]]] * data[[pair[[2L]]]]
  }
  data
}

fit_mode <- function(syntax, data, mode, settings) {
  if (mode == "primary") {
    fit <- lavaan::sem(syntax, data = data, se = "bootstrap", bootstrap = settings$bootstrap, parallel = "no")
    estimates <- lavaan::parameterEstimates(fit, boot.ci.type = "perc", level = 0.95)
    boot <- lavaan::lavInspect(fit, "boot")
    successful <- if (is.null(boot) || !length(boot)) 0L else sum(stats::complete.cases(boot))
  } else {
    fit <- lavaan::sem(syntax, data = data)
    estimates <- lavaan::parameterEstimates(fit, level = 0.95)
    successful <- NA_integer_
  }
  list(fit = fit, estimates = estimates, successful = successful,
       converged = isTRUE(lavaan::lavInspect(fit, "converged")))
}

mode_methods <- function(mode, settings) {
  if (mode == "primary") {
    list(sims = settings$bootstrap, point = "ML estimate on the original sample",
         interval = sprintf("percentile, %d nonparametric bootstrap refits (lavaan boot.ci.type = 'perc')", settings$bootstrap))
  } else {
    list(sims = NA_integer_, point = "ML estimate on the original sample",
         interval = "normal-theory 95% interval with delta-method standard errors")
  }
}

process_dataset <- function(entry, root, support, settings, cells_cache) {
  context <- dataset_context(entry, TOOL, "lavaan")
  cell <- cells_cache[[entry$cell_id]]
  effects <- unlist(cell$effects)
  rows <- list()
  if (!entry$cell_id %in% unlist(support$supported)) {
    reason <- support$not_estimable[[entry$cell_id]]
    if (is.null(reason)) reason <- "cell is not in the lavaan support matrix"
    for (mode in settings$modes) for (effect in effects) {
      rows[[length(rows) + 1L]] <- new_row(context, mode, effect, status = "not_estimable", message = reason)
    }
    return(rows)
  }
  prepared <- guarded({
    model <- build_model(cell)
    definitions <- effect_definitions(cell, model)
    data <- add_products(read_dataset(root, entry$path), model$products)
    list(model = model, definitions = definitions, syntax = model_syntax(model, definitions), data = data)
  })
  for (mode in settings$modes) {
    methods <- mode_methods(mode, settings)
    if (prepared$failed) {
      for (effect in effects) {
        rows[[length(rows) + 1L]] <- new_row(context, mode, effect, status = "error",
          message = c(prepared$value$message, prepared$warnings), sims_requested = methods$sims,
          point_method = methods$point, interval_method = methods$interval)
      }
      next
    }
    syntax <- prepared$value$syntax
    model_text <- gsub("\n", "; ", syntax, fixed = TRUE)
    start <- proc.time()
    seed_rng(context$r_seed)
    outcome <- guarded(fit_mode(syntax, prepared$value$data, mode, settings))
    runtime <- elapsed(start)
    for (effect in effects) {
      definition <- prepared$value$definitions[[effect]]
      if (is.null(definition)) {
        rows[[length(rows) + 1L]] <- new_row(context, mode, effect, 0, 0, 0, status = "ok",
          message = "structural zero: the fitted model has no A -> mediator -> Y path",
          runtime = runtime, sims_requested = methods$sims, model = model_text,
          point_method = "structural zero", interval_method = "structural zero")
        next
      }
      if (outcome$failed) {
        rows[[length(rows) + 1L]] <- new_row(context, mode, effect, status = "error",
          message = c(outcome$value$message, outcome$warnings), runtime = runtime,
          sims_requested = methods$sims, model = model_text, point_method = methods$point,
          interval_method = methods$interval)
        next
      }
      estimates <- outcome$value$estimates
      hit <- estimates[estimates$op == ":=" & estimates$lhs == effect, , drop = FALSE]
      if (nrow(hit) != 1L) {
        rows[[length(rows) + 1L]] <- new_row(context, mode, effect, status = "error",
          message = c("defined parameter missing from parameterEstimates", outcome$warnings),
          runtime = runtime, sims_requested = methods$sims, model = model_text)
        next
      }
      status <- if (!outcome$value$converged) "error" else if (length(outcome$warnings)) "ok_warnings" else "ok"
      message <- c(if (!outcome$value$converged) "lavaan did not converge", outcome$warnings)
      rows[[length(rows) + 1L]] <- new_row(context, mode, effect, hit$est[[1L]], hit$ci.lower[[1L]],
        hit$ci.upper[[1L]], status = status, message = message, runtime = runtime,
        sims_requested = methods$sims, sims_successful = outcome$value$successful, model = model_text,
        point_method = methods$point, interval_method = methods$interval)
    }
  }
  rows
}

main <- function() {
  options <- parse_args(list(manifest = "", output = "", cells = "", modes = "primary,secondary",
                             bootstrap = "399"))
  if (!nzchar(options$manifest) || !nzchar(options$output)) stop("--manifest and --output are required")
  settings <- list(modes = split_list(options$modes), bootstrap = as.integer(options$bootstrap))
  if (!all(settings$modes %in% c("primary", "secondary"))) stop("--modes must be primary and/or secondary")
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
      context <- dataset_context(entry, TOOL, "lavaan")
      for (mode in settings$modes) for (effect in unlist(cells_cache[[entry$cell_id]]$effects)) {
        rows[[length(rows) + 1L]] <- new_row(context, mode, effect, status = "error",
          message = c("runner error", result$value$message))
      }
    } else {
      rows <- c(rows, result$value)
    }
  }
  write_long(rows, options$output)
  cat(sprintf("lavaan: wrote %d row(s) for %d dataset(s) to %s\n", length(rows), length(entries), options$output))
}

main()
