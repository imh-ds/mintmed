# Install the pinned Task 17 comparator packages (mediation, lavaan, jsonlite
# and their hard dependencies) from a dated Posit Package Manager CRAN
# snapshot, then assert the exact versions and that every package loads.
#
# Usage:
#   Rscript benchmarks/comparators/r/install_packages.R              # install if needed, then assert
#   Rscript benchmarks/comparators/r/install_packages.R --check-only # assert only, never download
#
# Target library: $R_COMPARATOR_LIB when set (created if missing), otherwise
# R's first library path. Nothing outside that library is written: no
# .Rprofile, no global options, no system library. Packages already at the
# pinned version are not reinstalled, so a cached library costs no download.

local({
  file_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg[1L]))) else getwd()
  sys.source(file.path(script_dir, "pins.R"), envir = globalenv())
})

args <- commandArgs(trailingOnly = TRUE)
unknown <- setdiff(args, "--check-only")
if (length(unknown)) stop("unknown argument(s): ", paste(unknown, collapse = " "), call. = FALSE)
check_only <- "--check-only" %in% args

fail <- function(...) {
  message("ERROR: ", ...)
  quit(save = "no", status = 1L)
}

# R itself: pinned to the 4.6 minor series.
r_minor <- sprintf("%s.%s", R.version$major, sub("\\..*$", "", R.version$minor))
if (!identical(r_minor, COMPARATOR_R_MINOR)) {
  fail(sprintf("R %s required, found R %s", COMPARATOR_R_MINOR, getRversion()))
}

lib <- comparator_lib()
repo <- comparator_snapshot_url()
cat(sprintf("R %s | library %s | snapshot %s\n", getRversion(), lib, repo))

installed_version <- function(pkg) {
  tryCatch(as.character(packageVersion(pkg, lib.loc = lib)), error = function(e) NA_character_)
}
pinned <- names(COMPARATOR_PINNED)
current <- vapply(pinned, installed_version, character(1))
needed <- pinned[is.na(current) | current != COMPARATOR_PINNED[pinned]]

if (length(needed) && !check_only) {
  if (!dir.exists(lib)) dir.create(lib, recursive = TRUE)
  # Session-only settings; nothing is persisted.
  .libPaths(c(lib, .libPaths()))
  if (identical(Sys.info()[["sysname"]], "Linux")) {
    # PPM serves Linux binaries only to clients that identify their R build.
    options(HTTPUserAgent = sprintf(
      "R/%s R (%s)", getRversion(),
      paste(getRversion(), R.version[["platform"]], R.version[["arch"]], R.version[["os"]])
    ))
  }
  options(install.packages.compile.from.source = "never", Ncpus = max(1L, parallel::detectCores()))
  cat("Installing:", paste(needed, collapse = ", "), "\n")
  install.packages(
    needed,
    lib = lib,
    repos = c(CRAN = repo),
    dependencies = c("Depends", "Imports", "LinkingTo")
  )
} else if (length(needed)) {
  cat("--check-only: not installing", paste(needed, collapse = ", "), "\n")
} else {
  cat("All pinned packages already present at the pinned versions; nothing to install.\n")
}

# Assert exact versions in the target library, then that each package loads
# (a load failure catches missing dependencies or system libraries).
problems <- character()
for (pkg in pinned) {
  got <- installed_version(pkg)
  want <- COMPARATOR_PINNED[[pkg]]
  status <- if (is.na(got)) "MISSING" else if (got != want) "MISMATCH" else "ok"
  cat(sprintf("  %-10s pinned %-8s installed %-8s %s\n", pkg, want, ifelse(is.na(got), "-", got), status))
  if (status != "ok") problems <- c(problems, sprintf("%s: pinned %s, found %s", pkg, want, got))
}
if (length(problems)) fail("version assertion failed:\n  ", paste(problems, collapse = "\n  "))

for (pkg in pinned) {
  ok <- tryCatch({
    loadNamespace(pkg, lib.loc = unique(c(lib, .libPaths())))
    TRUE
  }, error = function(e) {
    message(sprintf("  %s failed to load: %s", pkg, conditionMessage(e)))
    FALSE
  })
  if (!ok) problems <- c(problems, pkg)
}
if (length(problems)) fail("package(s) failed to load: ", paste(problems, collapse = ", "))

cat("OK: pinned comparator packages verified.\n")
