# Changelog

All notable changes to pyHidroWeb are documented here. This project follows
[Semantic Versioning](https://semver.org/).

## [2.0.0]

Complete rebuild of pyHidroWeb as a faithful Python translation of the
[hydroDataBR](https://github.com/hydrostat/hydroDataBR) R package
(hydro_stat/UFMG, MIT), the reference client for the official ANA
HidroWebService. Every endpoint, schema, parsing rule and algorithm was taken
from its source code, and the parsers are validated against the hydroDataBR
test fixtures.

### Added

- **Full hydroDataBR public API (16 functions):**
  - Authentication: `ana_authenticate` (OAuth against the ANA HidroWebService;
    token kept in memory only and hidden in `repr`; credentials read from
    arguments or the `ANA_HIDROWEBSERVICE_IDENTIFIER` /
    `ANA_HIDROWEBSERVICE_PASSWORD` environment variables).
  - Acquisition: `get_ana_data`, `get_ana_data_batch`, `get_ana_stations`,
    `download_ana_cross_section_vertices` (mandatory SHA-256 verification).
  - Local readers: `read_ana_xml`, `read_ana_json`, `read_hidroweb`,
    `read_hidroweb_cross_sections`.
  - Filtering: `filter_ana_stations`.
  - Analysis: `analyze_hydro_data` (availability, statistics, Weibull
    flow-duration curves, QMLT/Q90/Q95, annual maxima with quality flags,
    low-flow moving-average minima, ETCCDI rainfall indices, rainfall /
    measurement / rating diagnostics), `diagnose_daily_hydrometry`,
    `diagnose_station_hydrometry`.
  - Output: `plot_hydro_data` (matplotlib), `table_hydro_data`,
    `write_hydro_data` (CSV/Parquet/PNG/PDF, sensitive-column scrub, manifest).
- **Standardized 8-column daily contract** shared by every source
  (`station_code`, `date`, `variable`, `value`, `unit`, `consistency_level`,
  `source_status`, `source`), with Brazilian numeric/date parsing and
  consistency-preference deduplication.
- **Bundled ANA snapshot (June 2026)** converted from hydroDataBR's `.rda`
  datasets to Parquet: 37,584 stations plus discharge measurements, rating
  curves and cross-section metadata, for offline lookups and diagnostics.
- Automatic splitting of API date ranges longer than 366 days.
- Rewritten beginner tutorial (`tutorials/tutorial.ipynb`) for the 2.0 API,
  with offline (internal-database) cells that run without network or
  credentials.

### Changed

- Legacy daily-series requests now use HTTPS
  (`https://telemetriaws1.ana.gov.br`) instead of HTTP.
- `setup.py` reduced to a shim; `pyproject.toml` is the single source of
  metadata (fixes the previous 1.0.0/2.0.0 version drift).

### Removed

- The invented `EstacaoMetaDados` XML metadata extraction (that element does
  not exist in real `HidroSerieHistorica` responses).
- The `metadata.py` module, whose inventory URL and column schema were
  unverified guesses; station metadata now comes from the real inventory route
  (`get_ana_stations`) or the bundled inventory (`filter_ana_stations`).

### Deprecated

- `download_hidroweb_data`, `extract_data`, `download_from_list` and
  `download_from_shape` remain as wrappers over the new modules (emitting
  `DeprecationWarning`); the `anagovbr` GitHub raw URLs they used are gone.

## [1.0.0]

Initial release: download rainfall and flow data from the HidroWeb portal.
