# Single source of truth for the Task 17 R comparator environment.
# Sourced by install_packages.R and versions.R; defines constants only.

# Posit Package Manager CRAN snapshot. 2026-09-28 serves lavaan 0.7-2 (current
# CRAN; the owner chose it over 0.6-21 on 2026-09-29), mediation 4.5.1 and
# jsonlite 2.0.0. Changing this date changes every package.
COMPARATOR_SNAPSHOT_DATE <- "2026-09-28"
COMPARATOR_SNAPSHOT_BASE <- "https://packagemanager.posit.co/cran"

# R minor version the environment is pinned to (any 4.6.x patch release).
COMPARATOR_R_MINOR <- "4.6"

# Exact versions the snapshot must yield; install_packages.R asserts them.
COMPARATOR_PINNED <- c(
  mediation = "4.5.1",
  lavaan = "0.7.2",
  jsonlite = "2.0.0"
)

# Packages whose versions are recorded (not asserted) because they shape the
# comparators' numerics: mediation's and lavaan's direct dependencies.
COMPARATOR_RECORDED <- c(
  "MASS", "Matrix", "mvtnorm", "sandwich", "lme4", "boot", "lpSolve", "Hmisc",
  "mnormt", "pbivnorm", "numDeriv", "quadprog"
)

# Snapshot URL for this platform. On Linux, PPM serves prebuilt binaries only
# under __linux__/<codename>/<date>; elsewhere the plain date URL serves
# source packages (and Windows/macOS binaries).
comparator_snapshot_url <- function(date = COMPARATOR_SNAPSHOT_DATE) {
  if (identical(Sys.info()[["sysname"]], "Linux") && file.exists("/etc/os-release")) {
    os <- readLines("/etc/os-release", warn = FALSE)
    codename <- sub("^VERSION_CODENAME=\"?([^\"]*)\"?$", "\\1",
                    grep("^VERSION_CODENAME=", os, value = TRUE))
    if (length(codename) == 1L && nzchar(codename)) {
      return(sprintf("%s/__linux__/%s/%s", COMPARATOR_SNAPSHOT_BASE, codename, date))
    }
  }
  sprintf("%s/%s", COMPARATOR_SNAPSHOT_BASE, date)
}

# Library the comparator packages live in: R_COMPARATOR_LIB when set,
# otherwise R's first library path (the user library on a local machine).
comparator_lib <- function() {
  lib <- Sys.getenv("R_COMPARATOR_LIB", unset = "")
  if (nzchar(lib)) normalizePath(lib, winslash = "/", mustWork = FALSE) else .libPaths()[1L]
}
