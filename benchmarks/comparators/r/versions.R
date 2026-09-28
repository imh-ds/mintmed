# Print the R comparator environment as one JSON object on stdout, for
# stamping comparator outputs. Reads the library from $R_COMPARATOR_LIB when
# set (see pins.R), falling back to R's library paths.
#
# Usage: Rscript benchmarks/comparators/r/versions.R

local({
  file_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  script_dir <- if (length(file_arg)) dirname(normalizePath(sub("^--file=", "", file_arg[1L]))) else getwd()
  sys.source(file.path(script_dir, "pins.R"), envir = globalenv())
})

lib_paths <- unique(c(comparator_lib(), .libPaths()))
.libPaths(lib_paths)  # session only; lets jsonlite load from the comparator library

version_of <- function(pkg) {
  tryCatch(as.character(packageVersion(pkg, lib.loc = lib_paths)), error = function(e) NA_character_)
}
pinned <- names(COMPARATOR_PINNED)
pinned_versions <- vapply(pinned, version_of, character(1))
recorded_versions <- vapply(COMPARATOR_RECORDED, version_of, character(1))

info <- list(
  r_version = as.character(getRversion()),
  r_version_string = R.version$version.string,
  platform = R.version$platform,
  os = unname(Sys.info()[["sysname"]]),
  snapshot_date = COMPARATOR_SNAPSHOT_DATE,
  snapshot_url = comparator_snapshot_url(),
  library = comparator_lib(),
  packages = as.list(pinned_versions),
  pinned = as.list(COMPARATOR_PINNED),
  pins_match = isTRUE(all(!is.na(pinned_versions) & pinned_versions == COMPARATOR_PINNED[pinned])),
  dependencies = as.list(recorded_versions),
  blas = tryCatch(extSoftVersion()[["BLAS"]], error = function(e) NA_character_),
  lapack = tryCatch(La_version(), error = function(e) NA_character_)
)

if (!requireNamespace("jsonlite", quietly = TRUE)) {
  message("ERROR: jsonlite is not installed; run install_packages.R first")
  quit(save = "no", status = 1L)
}
cat(jsonlite::toJSON(info, auto_unbox = TRUE, na = "null", null = "null"), "\n", sep = "")
