# Baseline before application restructuring (2026-11-01)

Source application: 9d855aff7efbc325b73a45badb0ba630aeff322c; imported as 78d3130.

- Original source files in server/app and mobile/src were unchanged during this run.
- Backend: **151 passed**, 5 dependency/lifecycle deprecation warnings, 31.12 seconds.
- Frontend: **16 files / 72 tests passed**; vue-tsc and production Vite build passed.
- OpenAPI: 81 path keys, SHA256 `6508bdae4206d8a8db0942bf3129b99f3fa9b400ed8cff81dad339d1afb34c95` (sorted compact JSON, UTF-8).
- Python 3.11.9; original installed dependency versions reproduced in a separate new venv using metadata-derived constraints. Broad-range install was stopped before baseline validation to avoid upgrades.
- Node v24.18.0; frontend installed from its original lockfile with npm ci.
- Initial sandbox install attempts failed due to network/filesystem restrictions; approved installation succeeded. These were environment failures, not test failures.
- Vite preview requires --outDir web-dist; unconfigured preview looks for dist and fails. Build output itself passed.
- No Android SDK standard configuration detected; JAVA_HOME points to a local JDK. Docker engine is not running. APK/device and Docker runtime results are not claimed.
- Generated logs, build outputs, dependency snapshots and visual evidence are stored under ignored .runtime, not in the old project.

This is an engineering baseline, not a claim of complete platform or live-AI acceptance.
