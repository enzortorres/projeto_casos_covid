# Dicionário de Dados

Metadados do conjunto bruto e das tabelas processadas do projeto **COVID-19 no Brasil (2020–2022)**.

| Metadado | Valor |
|---|---|
| Fonte primária | Brasil.IO — *Boletins epidemiológicos da COVID-19 por município por dia* (tabela `caso_full`) |
| URL perene | <https://brasil.io/dataset/covid19/caso_full/> |
| Download direto | <https://data.brasil.io/dataset/covid19/caso_full.csv.gz> |
| Produtores originais | Secretarias Estaduais de Saúde das 27 UFs (boletins), consolidados por voluntários do Brasil.IO |
| Licença da fonte | [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) |
| Cobertura temporal | 25/02/2020 a 27/03/2022 (data em que o Brasil.IO encerrou a atualização) |
| Cobertura espacial | Brasil: 27 UFs e 5.570 municípios |
| Granularidade | Local × dia (municípios e UFs no mesmo arquivo) |
| Formato bruto | CSV, UTF-8, separador `,`, compressão gzip (~92 MB; 3.853.648 linhas × 18 colunas) |
| Formatos processados | Apache Parquet (compressão zstd) e CSV.gz (UTF-8, datas `AAAA-MM-DD`) |
| Gerado por | `src/etl.py` (`python -m src.etl`) |

Convenções dos tipos: `int64` = inteiro; `Int64` = inteiro anulável; `float64` = real; `bool` = verdadeiro/falso;
`date` = data `AAAA-MM-DD`; `category` = texto com domínio fechado; `string` = texto livre.

---

## 1. Arquivo bruto — `data/raw/caso_full.csv.gz`

Não versionado (> 50 MB). É baixado automaticamente por `src/etl.py`.

| Coluna original | Nome tratado | Tipo | Descrição |
|---|---|---|---|
| `city` | `municipio` | string | Nome do município. Vazio nas linhas de UF. `Importados/Indefinidos` = casos sem município definido |
| `city_ibge_code` | `codigo_ibge` | Int64 | Código IBGE do município (7 dígitos) ou da UF (2 dígitos). Nulo para Importados/Indefinidos |
| `date` | `data` | date | Data do boletim (data de **notificação**, não de ocorrência) |
| `epidemiological_week` | `semana_epidemiologica` | int | Semana epidemiológica no formato `AAAASS` |
| `estimated_population` | `populacao` | Int64 | População estimada pelo IBGE para 2020 |
| `estimated_population_2019` | `populacao_2019` | Int64 | População estimada pelo IBGE para 2019 |
| `is_last` | `e_ultimo_registro` | bool | `True` no último registro disponível do local |
| `is_repeated` | `e_repetido` | bool | `True` quando não houve boletim no dia e os acumulados repetem o dia anterior |
| `last_available_confirmed` | `casos_acumulados` | int64 | Casos confirmados acumulados até a data |
| `last_available_confirmed_per_100k_inhabitants` | `casos_por_100k` | float64 | Casos acumulados por 100 mil habitantes (calculado pela fonte) |
| `last_available_date` | `data_ultima_atualizacao` | date | Data do último boletim que alimentou os acumulados |
| `last_available_death_rate` | `letalidade` | float64 | Óbitos ÷ casos acumulados (fração, 0–1) |
| `last_available_deaths` | `obitos_acumulados` | int64 | Óbitos confirmados acumulados até a data |
| `order_for_place` | `ordem_no_local` | int | Número sequencial do registro no local (1 = primeiro caso) |
| `place_type` | `tipo_local` | category | `city` (município) ou `state` (UF) |
| `state` | `uf` | category | Sigla da UF |
| `new_confirmed` | `casos_novos` | int64 | Casos novos no dia. **Pode ser negativo** (correção retroativa) |
| `new_deaths` | `obitos_novos` | int64 | Óbitos novos no dia. **Pode ser negativo** (correção retroativa) |

### Colunas derivadas na limpeza (`clean`)

| Coluna | Tipo | Regra |
|---|---|---|
| `regiao` | category | Grande região do IBGE, derivada da UF (Norte, Nordeste, Centro-Oeste, Sudeste, Sul) |
| `e_importado_indefinido` | bool | `municipio == "Importados/Indefinidos"` |
| `e_correcao` | bool | `casos_novos < 0` ou `obitos_novos < 0` |
| `mes` | date | Primeiro dia do mês de `data` |

### Qualidade observada (ver `data/processed/relatorio_qualidade.json`)

| Item | Quantidade | Tratamento |
|---|---:|---|
| Linhas com `is_repeated = True` | 1.015.645 (26,4%) | Mantidas; séries suavizadas por média móvel de 7 dias |
| `new_confirmed < 0` | 38.638 | Mantidas e sinalizadas (`e_correcao`) |
| `new_deaths < 0` | 6.261 | Mantidas e sinalizadas (`e_correcao`) |
| Linhas Importados/Indefinidos | 13.646 | Incluídas nos totais de UF (via linhas `state`); excluídas da tabela municipal |
| Chaves duplicadas (local × data) | 0 | Validação bloqueante |
| Séries municipais desatualizadas | última atualização entre 22/08/2021 e 26/03/2022, conforme a UF | Tabela municipal medida na data de corte comum 22/08/2021 |

---

## 2. Tabelas processadas — `data/processed/`

Cada tabela existe em `.parquet` e `.csv.gz` com o mesmo conteúdo.

### 2.1 `brasil_diario` — série nacional diária (762 linhas; chave: `data`)

Soma das 27 linhas estaduais em cada data.

| Coluna | Tipo | Unidade | Descrição |
|---|---|---|---|
| `data` | date | — | Data do boletim |
| `casos_novos` | int64 | casos | Casos novos notificados no dia (soma das UFs) |
| `obitos_novos` | int64 | óbitos | Óbitos novos notificados no dia |
| `casos_acumulados` | int64 | casos | Casos acumulados até a data |
| `obitos_acumulados` | int64 | óbitos | Óbitos acumulados até a data |
| `ufs_reportando` | int64 | UFs | Número de UFs com registro na data (< 27 antes do primeiro caso de alguma UF) |
| `populacao` | int64 | habitantes | População do Brasil (soma das UFs, estimativa de 2020) |
| `casos_mm7` | float64 | casos/dia | Média móvel de 7 dias de `casos_novos` (nula nos 6 primeiros dias) |
| `obitos_mm7` | float64 | óbitos/dia | Média móvel de 7 dias de `obitos_novos` |
| `letalidade_defasada_14d` | float64 | % | `obitos_mm7` ÷ `casos_mm7` de 14 dias antes × 100 |

### 2.2 `uf_diario` — série diária por UF (20.119 linhas; chave: `uf` + `data`)

| Coluna | Tipo | Unidade | Descrição |
|---|---|---|---|
| `data` | date | — | Data do boletim |
| `uf` | string | — | Sigla da UF |
| `regiao` | category | — | Grande região |
| `populacao` | Int64 | habitantes | População estimada (2020) |
| `casos_novos`, `obitos_novos` | int64 | casos / óbitos | Novos no dia (podem ser negativos) |
| `casos_acumulados`, `obitos_acumulados` | int64 | casos / óbitos | Acumulados até a data |
| `e_repetido` | bool | — | Dia sem boletim novo |
| `e_correcao` | bool | — | Dia com valor novo negativo |
| `casos_mm7`, `obitos_mm7` | float64 | por dia | Médias móveis de 7 dias dentro da UF |
| `casos_mm7_por_100k`, `obitos_mm7_por_100k` | float64 | por 100 mil hab./dia | Médias móveis normalizadas pela população |

### 2.3 `uf_mensal` — UF × mês (676 linhas; chave: `uf` + `mes`)

| Coluna | Tipo | Unidade | Descrição |
|---|---|---|---|
| `uf`, `regiao` | string / category | — | Identificação |
| `mes` | date | — | Primeiro dia do mês |
| `casos`, `obitos` | int64 | casos / óbitos | Soma dos novos no mês |
| `populacao` | Int64 | habitantes | População estimada (2020) |
| `dias_observados` | int64 | dias | Dias com registro no mês (meses parciais no início e no fim da série) |
| `casos_por_100k`, `obitos_por_100k` | float64 | por 100 mil hab. | Taxas mensais |

### 2.4 `uf_resumo` — situação acumulada final por UF (27 linhas; chave: `uf`)

| Coluna | Tipo | Unidade | Descrição |
|---|---|---|---|
| `uf`, `regiao` | string / category | — | Identificação |
| `populacao` | Int64 | habitantes | População estimada (2020) |
| `casos_acumulados`, `obitos_acumulados` | int64 | casos / óbitos | Totais no último registro |
| `data_referencia` | date | — | Data do último registro (27/03/2022 para todas as UFs) |
| `incidencia_por_100k` | float64 | por 100 mil hab. | Casos acumulados ÷ população × 100.000 |
| `mortalidade_por_100k` | float64 | por 100 mil hab. | Óbitos acumulados ÷ população × 100.000 |
| `letalidade_pct` | float64 | % | Óbitos ÷ casos × 100 (letalidade **aparente**) |

### 2.5 `municipios` — situação acumulada por município (5.570 linhas; chave: `codigo_ibge`)

Os indicadores usam a **data de corte comum** (`data_corte` = 22/08/2021), a mais recente em que todos os municípios ainda estavam atualizados. Os valores do último registro de cada município ficam em colunas próprias, para rastreabilidade.

| Coluna | Tipo | Unidade | Descrição |
|---|---|---|---|
| `codigo_ibge` | int64 | — | Código IBGE do município (7 dígitos) |
| `municipio` | string | — | Nome do município |
| `uf`, `regiao` | string / category | — | Localização |
| `populacao` | int64 | habitantes | População estimada (2020) |
| `casos_ultimo_registro`, `obitos_ultimo_registro` | int64 | casos / óbitos | Acumulados no último registro do município |
| `data_ultima_atualizacao` | date | — | Data do último registro do município |
| `data_corte` | date | — | Data de corte comum usada nos indicadores |
| `casos_acumulados`, `obitos_acumulados` | int64 | casos / óbitos | Acumulados até `data_corte`. Zero quando não havia registro até essa data |
| `e_capital` | bool | — | Município é capital de UF |
| `porte` | category | — | Faixa populacional: `Até 20 mil`, `20–50 mil`, `50–100 mil`, `100–500 mil`, `Mais de 500 mil` |
| `incidencia_por_100k` | float64 | por 100 mil hab. | Casos ÷ população × 100.000 |
| `mortalidade_por_100k` | float64 | por 100 mil hab. | Óbitos ÷ população × 100.000 |
| `letalidade_pct` | float64 | % | Óbitos ÷ casos × 100. Nula (`NaN`) quando não há casos |

### 2.6 `relatorio_qualidade.json`

Relatório gerado em cada execução: linhas brutas, período, nulos por coluna, contagem de repetidos, negativos e duplicados, totais nacionais e linhas por tabela.
