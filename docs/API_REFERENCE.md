# API Reference — pyHidroWeb 2.0

A API pública espelha o pacote R [hydroDataBR](https://github.com/hydrostat/hydroDataBR)
(hydro_stat/UFMG, MIT). Todas as funções abaixo são importáveis de `pyhydroweb`.

## Autenticação

### `ana_authenticate(identifier=None, password=None, *, base_url=..., timeout=60, max_attempts=3, retry_sleep_seconds=1) -> AnaToken`

Autentica na HidroWebService da ANA (`/OAUth/v1`, headers `Identificador`/`Senha`)
e retorna um `AnaToken` (válido ~1 h, mantido só em memória; o `repr` oculta o
valor). Credenciais podem vir das variáveis de ambiente
`ANA_HIDROWEBSERVICE_IDENTIFIER` / `ANA_HIDROWEBSERVICE_PASSWORD`
(aliases `ANA_HIDRO_IDENTIFICADOR` / `ANA_HIDRO_SENHA`).

## Aquisição

### `get_ana_data(product, data_source="webservice", station_code=None, path=None, start_date=None, end_date=None, token=None, consistency_level=None, timeout=60)`

Ponto de entrada único.

- **Produtos**: `daily_discharge`, `daily_stage`, `daily_rainfall` (aliases
  `vazao`, `cota`, `chuva`…), `stations`, `discharge_measurements`,
  `rating_curves`, `cross_sections`.
- **Fontes**: `webservice` (rota legada HTTPS `HidroSerieHistorica`, sem
  credenciais — usada pelos produtos diários), `api` (HidroWebService
  autenticada — produtos especializados, janelas > 366 dias divididas
  automaticamente), `hidroweb`/`xml`/`json` (arquivo local em `path`).
- Produtos diários retornam o contrato padronizado de 8 colunas; seções
  transversais retornam `{"sections": DataFrame, "vertices": DataFrame}`.

### `get_ana_data_batch(product, station_codes, **kwargs) -> {"results", "request_report"}`

Uma chamada por estação, com isolamento de falhas; `request_report` traz
`status` (`success`/`empty`/`error`), `n_rows` e `message` por estação.

### `get_ana_stations(station_code=None, state_code=None, basin_code=None, token=None)`

Inventário ao vivo (`/HidroInventarioEstacoes/v1`; exige ao menos um filtro).
Colunas padronizadas: `station_code`, `station_name`, `state_code/state_name`,
`municipality_code/municipality`, `basin_code/basin_name`, `station_type`,
`operating`, `latitude`, `longitude`, `altitude_m`, `drainage_area_km2`,
`operator_code/operator_acronym`, `responsible_acronym`, `last_update`, `source`.

### `download_ana_cross_section_vertices(path=None, version="2026-06", read=True, overwrite=False, verify_checksum=True)`

Baixa o dataset opcional de vértices de seções transversais (~14 MB, 2.170.742
vértices/2.842 estações) do repositório hydroDataBR. **SHA-256 verificado por
padrão**; a leitura do RDS requer o extra `pyreadr`.

## Leitura de arquivos locais

Todas retornam o contrato diário padronizado (exceto a última).

- `read_ana_xml(path, variables="all", merge_consistency=True)` — XML legado
  `HidroSerieHistorica` (elementos `SerieHistorica`, colunas-dia
  `Vazao01..31`/`Cota01..31`/`Chuva01..31` + `*Status`).
- `read_ana_json(path, ...)` — JSON da API (envelope `items`; vírgula decimal).
- `read_hidroweb(path, ...)` — CSV/ZIP do portal (Latin-1, `;`, preâmbulo antes
  do header `EstacaoCodigo;`).
- `read_hidroweb_cross_sections(file)` — `PerfilTransversal.csv` (célula
  `Vertical` empacotada) → `{"sections", "vertices"}`.

## Contrato diário padronizado

`station_code` (str) · `date` (date) · `variable`
(`discharge`|`stage`|`rainfall`) · `value` (float) · `unit`
(`m3/s`|`cm`|`mm`) · `consistency_level` (`"2"` consistido > `"1"` bruto) ·
`source_status` · `source`.

Com `merge_consistency=True` (padrão) mantém-se uma linha por
estação/dia/variável, preferindo o dado consistido.

## Filtragem de estações

### `filter_ana_stations(station_data=None, station_code=None, state_code=None, municipality=None, station_type=None, basin_code=None, name_pattern=None, product=None, is_operating=None)`

Filtra o inventário embutido (37.584 estações, retrato 2026-06) ou um
DataFrame fornecido. `product` ∈ {`discharge`, `stage`, `rainfall`,
`telemetry`, `discharge_measurements`}; `name_pattern` é regex
case-insensitive sobre `station_name`.

## Análise

### `analyze_hydro_data(data, analysis, variable=None, station_code=None, period="annual", year_start_month=1, durations=(1,3,7,15,30), wet_day_threshold=1.0, exceedance_probabilities=range(1,100), complete_years_only=True, **kwargs)`

| `analysis` | Conteúdo |
|---|---|
| `daily_availability` | dias esperados/observados/válidos e % sobre o calendário completo |
| `daily_statistics` | média/mín/máx/quartis/total por período |
| `flow_duration` | curva de permanência (posições de Weibull, interpolação linear, 1–99 %) |
| `flow_indices` | QMLT, Q90 (p0.10) e Q95 (p0.05), quantil tipo 8 |
| `monthly_flow_indices` | os mesmos índices por mês-calendário |
| `annual_maxima` / `rainfall_annual_maxima` | máximas anuais + flags de qualidade (IQR 3×, gap ±3 dias, empates) + `rank_descending` |
| `low_flows` | mínimas anuais de médias móveis (janelas 100 % válidas) + `rank_ascending` |
| `rainfall_indices` | ETCCDI: total, dias úmidos/secos, Rx1day, Rx5day, R10/R20/R50, SDII, CDD, CWD |
| `daily_gap_summary` | falhas por período |
| `rainfall_diagnostics` | flags diários (negativos, ≥400 mm, outlier mediana+8·MAD, zeros ≥20 dias, valores repetidos) |

`year_start_month=10` usa ano hidrológico (rotulado pelo ano final).

## Diagnósticos

### `diagnose_daily_hydrometry(daily_data, rating_curves=None, relative_error_threshold_pct=20, measurements=None, rating_curve_summary=None, station_code=None, use_internal_database=True)`

Consistência diária vazão↔cota↔curva-chave. Retorna dict com `summary`,
`daily_flags` (flags booleanos por dia), `rating_matches` e a origem da
referência (`hydrometry_reference_source`: `user` > `internal_database`;
`hydrometry_reference_snapshot`: `2026-06`). A previsão usa
`Q = a·(H/100 − h0_m)^n` (h0 em metros, como no hydroDataBR).

### `diagnose_station_hydrometry(measurements=None, rating_curves=None, detailed=True, rating_curve_summary=None, station_code=None, use_internal_database=True)`

Qualidade de medições e curvas por estação: flags de medições (valores não
positivos, repetições inconsistentes), casamento medição↔segmento com resíduo
log e envelope empírico, e um score de atenção (`low`/`moderate`/`high`).

## Saída

### `plot_hydro_data(data, plot, variable=None, station_code=None, **kwargs) -> matplotlib.figure.Figure`

Plots: `daily_series` (chuva em barras), `daily_availability` (heatmap
mensal), `monthly_summary`, `annual_summary`, `flow_duration` (eixo x em
escala normal-probabilística), `rating_curves`, `measurements`
(`rating`/`year`/`velocity`), `annual_maxima` (lollipop com flags),
`low_flows`, `rainfall_indices`, `cross_section_profile`,
`cross_section_overlay`. Requer o extra `plot` (matplotlib).

### `table_hydro_data(data, table, variable=None, station_code=None, period=None, **kwargs) -> DataFrame`

Todas as análises acima como tabela, mais `station_products` (disponibilidade
de produtos por estação, do inventário), `request_report` e `cross_sections`
(`level` ∈ {`sections`, `vertices`, `summary`}).

### `write_hydro_data(x, path, format=None, components="all", overwrite=False, manifest=False) -> dict`

Exporta DataFrames (CSV/Parquet) e figuras (PNG/PDF). Com múltiplos
componentes, `path` vira diretório com um arquivo por componente e manifesto
opcional. Colunas com nomes sensíveis (token/senha/cpf/...) são removidas
antes da escrita.

## Endpoints usados (verificados no hydroDataBR)

- Autenticada: `https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas`
  — `/OAUth/v1`, `/HidroInventarioEstacoes/v1`, `/HidroSerieResumoDescarga/v1`,
  `/HidroSerieCurvaDescarga/v1`, `/HidroSeriePerfilTransversal/v1`,
  `/HidroUF/v1`, `/HidroMunicipio/v1`, `/HidroBacia/v1`, `/HidroSubBacia/v1`,
  `/HidroRio/v1`, `/HidroEntidade/v1` (chaves de query com acento, p.ex.
  `Código da Estação`, `Data Inicial (yyyy-MM-dd)`).
- Legada (sem autenticação): `https://telemetriaws1.ana.gov.br/ServiceANA.asmx/HidroSerieHistorica`
  (`codEstacao`, `dataInicio`/`dataFim` em dd/mm/YYYY, `tipoDados`
  1=cota/2=chuva/3=vazão, `nivelConsistencia` 1|2).

Cadastro de credenciais e séries históricas: https://www.snirh.gov.br/hidroweb/

## API legada (deprecada)

`download_hidroweb_data`, `extract_data`, `download_from_list`,
`download_from_shape` — wrappers com `DeprecationWarning` sobre os novos
módulos. O antigo elemento `EstacaoMetaDados` não existe na API real e a
extração de metadados por ele foi removida; use `get_ana_stations` ou
`filter_ana_stations`.
