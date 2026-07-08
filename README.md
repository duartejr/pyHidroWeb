# pyHidroWeb

[![Python Version](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

Biblioteca Python para obter, padronizar, analisar, visualizar e exportar dados
hidrológicos da Agência Nacional de Águas e Saneamento Básico (ANA).

A partir da versão 2.0, o pyHidroWeb é uma **tradução para Python do pacote R
[hydroDataBR](https://github.com/hydrostat/hydroDataBR)** (hydro_stat/UFMG,
MIT), cobrindo toda a sua API pública: aquisição pela HidroWebService
autenticada da ANA e pelo WebService legado, leitura de arquivos locais do
HidroWeb, contrato diário padronizado, análises hidrológicas, diagnósticos
fluviométricos, gráficos, tabelas e exportação.

## Instalação

```bash
pip install pyhydroweb              # núcleo (pandas, numpy, requests, pyarrow)
pip install pyhydroweb[plot]        # + matplotlib (gráficos)
pip install pyhydroweb[geo]         # + geopandas/shapely (shapefiles)
pip install pyhydroweb[xarray]      # + xarray (saída legada)
pip install pyhydroweb[vertices]    # + pyreadr (vértices de seções transversais)
pip install pyhydroweb[all]
```

## API pública (equivalente 1:1 ao hydroDataBR)

| Grupo | Funções |
|---|---|
| Autenticação | `ana_authenticate` |
| Aquisição | `get_ana_data`, `get_ana_data_batch`, `get_ana_stations`, `download_ana_cross_section_vertices` |
| Leitura local | `read_ana_xml`, `read_ana_json`, `read_hidroweb`, `read_hidroweb_cross_sections` |
| Filtragem | `filter_ana_stations` |
| Análise | `analyze_hydro_data`, `diagnose_daily_hydrometry`, `diagnose_station_hydrometry` |
| Saída | `plot_hydro_data`, `table_hydro_data`, `write_hydro_data` |

## O contrato diário padronizado

Todas as fontes (XML legado, JSON da API, CSV/ZIP do HidroWeb) são
normalizadas para o mesmo DataFrame de 8 colunas:

```
station_code | date | variable | value | unit | consistency_level | source_status | source
```

- `variable`: `discharge` (m3/s), `stage` (cm) ou `rainfall` (mm)
- `consistency_level`: `"2"` = consistido (preferido), `"1"` = bruto
- Duplicatas por (estação, dia, variável) são resolvidas priorizando o dado
  consistido, exatamente como no hydroDataBR.

## Início rápido com o banco interno

O pacote embute um retrato estático de dados da ANA (junho/2026, herdado do
hydroDataBR): inventário com **37.584 estações**, 457 mil medições de
descarga, curvas-chave e seções transversais — útil para buscas rápidas e
diagnósticos offline.

```python
import pyhydroweb as ph

# Estações fluviométricas em operação com dados de vazão no Piauí
stations = ph.filter_ana_stations(
    state_code="PI", product="discharge", is_operating=True
)
print(stations[["station_code", "station_name", "latitude", "longitude"]].head())

# Produtos disponíveis para uma estação real (LUZILÂNDIA/PI)
ph.table_hydro_data(None, "station_products", station_code="34879500")
```

## Baixando séries diárias (WebService legado, sem credenciais)

```python
daily = ph.get_ana_data(
    "daily_discharge",              # ou daily_stage / daily_rainfall
    station_code="34879500",        # LUZILÂNDIA (PI)
    start_date="2020-01-01",
    end_date="2020-12-31",
)

# Várias estações de uma vez, com relatório por estação
batch = ph.get_ana_data_batch(
    "daily_discharge", ["34879500", "34880000"], start_date="2020-01-01",
    end_date="2020-12-31",
)
print(batch["request_report"])
```

## API autenticada da ANA (inventário, medições, curvas-chave, seções)

As rotas novas da HidroWebService exigem credenciais próprias cadastradas na
ANA. Forneça-as por variáveis de ambiente (recomendado):

```bash
export ANA_HIDROWEBSERVICE_IDENTIFIER="seu-identificador"
export ANA_HIDROWEBSERVICE_PASSWORD="sua-senha"
```

```python
token = ph.ana_authenticate()   # lê as variáveis de ambiente

inventory = ph.get_ana_stations(state_code="MG", token=token)

measurements = ph.get_ana_data(
    "discharge_measurements", data_source="api",
    station_code="56460000", start_date="2019-01-01", end_date="2019-12-31",
    token=token,
)
curves = ph.get_ana_data("rating_curves", data_source="api",
                         station_code="56460000", token=token)
```

Segurança (herdada do hydroDataBR e reforçada aqui): o token vive apenas em
memória e o `repr` oculta seu valor; corpos de erro HTTP são truncados e têm
credenciais redigidas; janelas acima de 366 dias são divididas
automaticamente; o download opcional de vértices **verifica SHA-256 por
padrão**; colunas com nomes sensíveis são removidas antes de exportar.

## Lendo arquivos locais do HidroWeb

```python
daily = ph.read_hidroweb("estacao.zip")            # ZIP/CSV do portal (Latin-1, ';')
daily = ph.read_ana_xml("HidroSerieHistorica.xml") # XML legado salvo em disco
daily = ph.read_ana_json("serie.json")             # JSON da API salvo em disco
xs = ph.read_hidroweb_cross_sections("estacao.zip")  # PerfilTransversal.csv
```

## Análises

```python
ph.analyze_hydro_data(daily, "daily_availability")     # disponibilidade
ph.analyze_hydro_data(daily, "daily_statistics")       # estatísticas
ph.analyze_hydro_data(daily, "flow_duration")          # curva de permanência (Weibull)
ph.analyze_hydro_data(daily, "flow_indices")           # QMLT, Q90, Q95
ph.analyze_hydro_data(daily, "annual_maxima")          # máximas anuais + flags
ph.analyze_hydro_data(daily, "low_flows")              # mínimas móveis (Q7 etc.)
ph.analyze_hydro_data(daily, "rainfall_indices")       # ETCCDI: Rx1day, SDII, CDD...
ph.analyze_hydro_data(daily, "rainfall_diagnostics")   # plausibilidade da chuva
```

## Diagnósticos fluviométricos

```python
diag = ph.diagnose_daily_hydrometry(daily)        # vazão x cota x curva-chave
diag["summary"]
diag["hydrometry_reference_source"]               # 'user' | 'internal_database'

station_diag = ph.diagnose_station_hydrometry(station_code="56460000")
```

Quando o usuário não fornece medições/curvas, o banco interno (retrato
2026-06) é usado como referência e a origem fica registrada no resultado.

## Gráficos, tabelas e exportação

```python
fig = ph.plot_hydro_data(daily, "daily_series")         # matplotlib Figure
fig = ph.plot_hydro_data(daily, "flow_duration")        # eixo probabilístico normal
fig = ph.plot_hydro_data(daily, "daily_availability")   # heatmap mensal

table = ph.table_hydro_data(daily, "daily_availability")

ph.write_hydro_data(
    {"daily": daily, "fdc": ph.analyze_hydro_data(daily, "flow_duration")},
    "exportacao/", format="csv", manifest=True,
)
```

## API legada (pré-2.0)

`download_hidroweb_data`, `extract_data`, `download_from_list` e
`download_from_shape` continuam funcionando como wrappers deprecados sobre os
novos módulos (agora via HTTPS e com o contrato padronizado). Migre para
`get_ana_data`/`get_ana_data_batch`.

## Proveniência e créditos

- Endpoints, schemas, algoritmos e o banco interno vêm do pacote R
  [hydroDataBR](https://github.com/hydrostat/hydroDataBR) (Wilson Fernandes,
  EHR/UFMG — grupo hydro_stat, licença MIT), usado como fonte de verdade
  desta tradução.
- As fixtures de teste em `tests/fixtures/` foram copiadas do hydroDataBR
  para validar os parsers Python contra as mesmas entradas do pacote R.
- Os dados são da ANA — Agência Nacional de Águas e Saneamento Básico. O
  acesso autenticado requer cadastro próprio junto à ANA.

## Desenvolvimento

```bash
pip install -e ".[dev]"
pytest
```

## Licença

MIT — veja [LICENSE](LICENSE).
