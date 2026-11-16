"""ETL dos boletins de COVID-19 das Secretarias Estaduais de Saúde (Brasil.IO).

Etapas (todas determinísticas e sem operações destrutivas sobre o dado bruto):

1. ``download_raw``   -- baixa ``caso_full.csv.gz`` do Brasil.IO (sem autenticação).
2. ``load_raw``       -- leitura com tipos explícitos (datas, inteiros anuláveis, booleanos).
3. ``validate_raw``   -- checagens de esquema e de integridade; gera relatório de qualidade.
4. ``clean``          -- tipagem, enriquecimento (região, capital, porte) e *flags* de qualidade.
5. ``build_*``        -- tabelas analíticas (Brasil diário, UF diário, UF x mês, municípios).
6. ``save``           -- persistência em Parquet e CSV comprimido (formatos abertos).

Uso::

    python -m src.etl            # baixa o bruto (se ausente) e gera data/processed/
    python -m src.etl --force    # força novo download do bruto
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------------------
# Configuração
# --------------------------------------------------------------------------------------
RAW_URL = "https://data.brasil.io/dataset/covid19/caso_full.csv.gz"

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
RAW_FILE = RAW_DIR / "caso_full.csv.gz"

log = logging.getLogger("etl")

EXPECTED_COLUMNS = [
    "city", "city_ibge_code", "date", "epidemiological_week", "estimated_population",
    "estimated_population_2019", "is_last", "is_repeated", "last_available_confirmed",
    "last_available_confirmed_per_100k_inhabitants", "last_available_date",
    "last_available_death_rate", "last_available_deaths", "order_for_place",
    "place_type", "state", "new_confirmed", "new_deaths",
]

RAW_DTYPES = {
    "city": "string",
    "city_ibge_code": "Int64",
    "epidemiological_week": "int32",
    "estimated_population": "Int64",
    "estimated_population_2019": "Int64",
    "last_available_confirmed": "int64",
    "last_available_confirmed_per_100k_inhabitants": "float64",
    "last_available_death_rate": "float64",
    "last_available_deaths": "int64",
    "order_for_place": "int32",
    "place_type": "category",
    "state": "category",
    "new_confirmed": "int64",
    "new_deaths": "int64",
}

UF_REGIAO = {
    "AC": "Norte", "AM": "Norte", "AP": "Norte", "PA": "Norte", "RO": "Norte", "RR": "Norte", "TO": "Norte",
    "AL": "Nordeste", "BA": "Nordeste", "CE": "Nordeste", "MA": "Nordeste", "PB": "Nordeste",
    "PE": "Nordeste", "PI": "Nordeste", "RN": "Nordeste", "SE": "Nordeste",
    "ES": "Sudeste", "MG": "Sudeste", "RJ": "Sudeste", "SP": "Sudeste",
    "PR": "Sul", "RS": "Sul", "SC": "Sul",
    "DF": "Centro-Oeste", "GO": "Centro-Oeste", "MS": "Centro-Oeste", "MT": "Centro-Oeste",
}
REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]

# Códigos IBGE (7 dígitos) das 27 capitais.
CAPITAIS_IBGE = {
    1100205, 1200401, 1302603, 1400100, 1501402, 1600303, 1721000,  # Norte
    2111300, 2211001, 2304400, 2408102, 2507507, 2611606, 2704302, 2800308, 2927408,  # Nordeste
    3106200, 3205309, 3304557, 3550308,  # Sudeste
    4106902, 4205407, 4314902,  # Sul
    5002704, 5103403, 5208707, 5300108,  # Centro-Oeste
}

# Faixas de porte populacional (adaptadas das classes de tamanho do IBGE).
PORTE_BINS = [0, 20_000, 50_000, 100_000, 500_000, np.inf]
PORTE_LABELS = ["Até 20 mil", "20–50 mil", "50–100 mil", "100–500 mil", "Mais de 500 mil"]

IMPORTADOS = "Importados/Indefinidos"


# --------------------------------------------------------------------------------------
# 1. Aquisição
# --------------------------------------------------------------------------------------
def download_raw(dest: Path = RAW_FILE, url: str = RAW_URL, force: bool = False) -> Path:
    """Baixa o arquivo bruto do Brasil.IO, caso ainda não exista localmente."""
    if dest.exists() and not force:
        log.info("Bruto já presente em %s (%.1f MB) — download ignorado.", dest, dest.stat().st_size / 1e6)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    log.info("Baixando %s ...", url)
    req = urllib.request.Request(url, headers={"User-Agent": "projeto-casos-covid/1.0 (python-urllib)"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as fh:
        total = int(resp.headers.get("Content-Length", 0))
        done = 0
        while chunk := resp.read(1 << 20):
            fh.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done / 1e6:6.1f} / {total / 1e6:.1f} MB", end="", file=sys.stderr)
    print(file=sys.stderr)
    tmp.replace(dest)
    log.info("Download concluído: %s", dest)
    return dest


# --------------------------------------------------------------------------------------
# 2. Leitura
# --------------------------------------------------------------------------------------
def load_raw(path: Path = RAW_FILE) -> pd.DataFrame:
    """Lê o CSV comprimido (UTF-8, separador vírgula) com tipagem explícita."""
    log.info("Lendo %s ...", path)
    df = pd.read_csv(
        path,
        compression="gzip",
        encoding="utf-8",
        sep=",",
        dtype=RAW_DTYPES,
        parse_dates=["date", "last_available_date"],
        true_values=["True"],
        false_values=["False"],
    )
    log.info("Bruto: %s linhas x %s colunas", f"{len(df):,}", df.shape[1])
    return df


# --------------------------------------------------------------------------------------
# 3. Validação
# --------------------------------------------------------------------------------------
def validate_raw(df: pd.DataFrame) -> dict:
    """Checa o esquema e devolve um relatório de qualidade (não altera o DataFrame)."""
    missing = set(EXPECTED_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f"Colunas ausentes no arquivo bruto: {sorted(missing)}")

    city = df["place_type"] == "city"
    state = df["place_type"] == "state"
    importados = df["city"] == IMPORTADOS

    report = {
        "fonte": RAW_URL,
        "linhas_brutas": int(len(df)),
        "colunas": int(df.shape[1]),
        "periodo": [str(df["date"].min().date()), str(df["date"].max().date())],
        "linhas_por_tipo": {"city": int(city.sum()), "state": int(state.sum())},
        "nulos_por_coluna": {k: int(v) for k, v in df.isna().sum().items() if v},
        "linhas_repetidas_is_repeated": int(df["is_repeated"].sum()),
        "linhas_importados_indefinidos": int(importados.sum()),
        "municipios_distintos": int(df.loc[city & ~importados, "city_ibge_code"].nunique()),
        "ufs_distintas": int(df["state"].nunique()),
        "new_confirmed_negativos": int((df["new_confirmed"] < 0).sum()),
        "new_deaths_negativos": int((df["new_deaths"] < 0).sum()),
        "chaves_duplicadas_local_data": int(
            df.loc[~importados].duplicated(["place_type", "state", "city_ibge_code", "date"]).sum()
        ),
    }
    if report["chaves_duplicadas_local_data"]:
        raise ValueError("Há registros duplicados para o mesmo local e data.")
    if report["ufs_distintas"] != 27:
        raise ValueError(f"Esperadas 27 UFs, encontradas {report['ufs_distintas']}.")
    log.info("Validação OK: %s", {k: report[k] for k in ("linhas_brutas", "municipios_distintos", "periodo")})
    return report


# --------------------------------------------------------------------------------------
# 4. Limpeza e enriquecimento
# --------------------------------------------------------------------------------------
def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza nomes, cria colunas derivadas e *flags*. Nenhuma linha é descartada aqui."""
    out = df.rename(
        columns={
            "city": "municipio",
            "city_ibge_code": "codigo_ibge",
            "date": "data",
            "epidemiological_week": "semana_epidemiologica",
            "estimated_population": "populacao",
            "estimated_population_2019": "populacao_2019",
            "is_last": "e_ultimo_registro",
            "is_repeated": "e_repetido",
            "last_available_confirmed": "casos_acumulados",
            "last_available_confirmed_per_100k_inhabitants": "casos_por_100k",
            "last_available_date": "data_ultima_atualizacao",
            "last_available_death_rate": "letalidade",
            "last_available_deaths": "obitos_acumulados",
            "order_for_place": "ordem_no_local",
            "place_type": "tipo_local",
            "state": "uf",
            "new_confirmed": "casos_novos",
            "new_deaths": "obitos_novos",
        }
    )
    out["regiao"] = out["uf"].astype(str).map(UF_REGIAO).astype(pd.CategoricalDtype(REGIOES, ordered=True))
    out["e_importado_indefinido"] = out["municipio"].eq(IMPORTADOS).fillna(False)
    # Valores negativos são correções retroativas publicadas pelas secretarias: mantidos e sinalizados.
    out["e_correcao"] = (out["casos_novos"] < 0) | (out["obitos_novos"] < 0)
    out["mes"] = out["data"].dt.to_period("M").dt.to_timestamp()
    return out


# --------------------------------------------------------------------------------------
# 5. Tabelas analíticas
# --------------------------------------------------------------------------------------
def _per_100k(num: pd.Series, pop: pd.Series) -> pd.Series:
    return (num / pop.astype("float64") * 100_000).round(2)


def build_uf_diario(df: pd.DataFrame) -> pd.DataFrame:
    """Série diária por UF (registros ``tipo_local == 'state'``) com médias móveis de 7 dias."""
    uf = (
        df.loc[df["tipo_local"] == "state",
               ["data", "uf", "regiao", "populacao", "casos_novos", "obitos_novos",
                "casos_acumulados", "obitos_acumulados", "e_repetido", "e_correcao"]]
        .assign(uf=lambda d: d["uf"].astype(str))
        .sort_values(["uf", "data"])
        .reset_index(drop=True)
    )
    grp = uf.groupby("uf", observed=True)
    for col, new in (("casos_novos", "casos_mm7"), ("obitos_novos", "obitos_mm7")):
        uf[new] = grp[col].transform(lambda s: s.rolling(7, min_periods=7).mean()).round(2)
    uf["casos_mm7_por_100k"] = _per_100k(uf["casos_mm7"], uf["populacao"])
    uf["obitos_mm7_por_100k"] = _per_100k(uf["obitos_mm7"], uf["populacao"])
    return uf


def build_brasil_diario(uf_diario: pd.DataFrame) -> pd.DataFrame:
    """Agrega as 27 UFs em uma série nacional diária."""
    pop_br = uf_diario.groupby("uf")["populacao"].first().sum()
    br = (
        uf_diario.groupby("data", as_index=False)
        .agg(casos_novos=("casos_novos", "sum"), obitos_novos=("obitos_novos", "sum"),
             casos_acumulados=("casos_acumulados", "sum"), obitos_acumulados=("obitos_acumulados", "sum"),
             ufs_reportando=("uf", "nunique"))
        .sort_values("data")
        .reset_index(drop=True)
    )
    br["populacao"] = int(pop_br)
    br["casos_mm7"] = br["casos_novos"].rolling(7, min_periods=7).mean().round(1)
    br["obitos_mm7"] = br["obitos_novos"].rolling(7, min_periods=7).mean().round(1)
    # Letalidade "instantânea": óbitos MM7 / casos MM7 de 14 dias antes (defasagem caso→óbito).
    br["letalidade_defasada_14d"] = (br["obitos_mm7"] / br["casos_mm7"].shift(14) * 100).round(3)
    return br


def build_uf_mensal(uf_diario: pd.DataFrame) -> pd.DataFrame:
    """Casos e óbitos por UF e mês, com taxas por 100 mil habitantes."""
    m = (
        uf_diario.assign(mes=uf_diario["data"].dt.to_period("M").dt.to_timestamp())
        .groupby(["uf", "regiao", "mes"], observed=True, as_index=False)
        .agg(casos=("casos_novos", "sum"), obitos=("obitos_novos", "sum"), populacao=("populacao", "first"),
             dias_observados=("data", "nunique"))
    )
    m["casos_por_100k"] = _per_100k(m["casos"], m["populacao"])
    m["obitos_por_100k"] = _per_100k(m["obitos"], m["populacao"])
    return m


def build_uf_resumo(uf_diario: pd.DataFrame) -> pd.DataFrame:
    """Situação acumulada final de cada UF (último registro disponível)."""
    last = uf_diario.sort_values("data").groupby("uf", as_index=False).tail(1)
    r = last[["uf", "regiao", "populacao", "casos_acumulados", "obitos_acumulados", "data"]].rename(
        columns={"data": "data_referencia"}
    )
    r["incidencia_por_100k"] = _per_100k(r["casos_acumulados"], r["populacao"])
    r["mortalidade_por_100k"] = _per_100k(r["obitos_acumulados"], r["populacao"])
    r["letalidade_pct"] = (r["obitos_acumulados"] / r["casos_acumulados"] * 100).round(3)
    return r.sort_values("mortalidade_por_100k", ascending=False).reset_index(drop=True)


def build_municipios(df: pd.DataFrame) -> pd.DataFrame:
    """Situação acumulada de cada município numa **data de corte comum**.

    As séries municipais deixam de ser atualizadas em datas diferentes conforme a UF (entre
    ago/2021 e mar/2022). Comparar o "último registro" de cada município misturaria períodos
    distintos; por isso todos são medidos na data mais recente em que *todos* ainda estavam
    atualizados (o menor ``data_ultima_atualizacao`` entre os municípios). Os valores do último
    registro disponível são mantidos em colunas próprias, para rastreabilidade.
    Exclui a categoria Importados/Indefinidos (sem município e sem população).
    """
    cidades = df.loc[(df["tipo_local"] == "city") & ~df["e_importado_indefinido"]]
    ultimo = cidades.loc[cidades["e_ultimo_registro"],
                         ["codigo_ibge", "municipio", "uf", "regiao", "populacao",
                          "casos_acumulados", "obitos_acumulados", "data_ultima_atualizacao"]]
    ultimo = ultimo.rename(columns={"casos_acumulados": "casos_ultimo_registro",
                                    "obitos_acumulados": "obitos_ultimo_registro"})
    corte = ultimo["data_ultima_atualizacao"].min()
    no_corte = (cidades.loc[cidades["data"] <= corte, ["codigo_ibge", "data", "casos_acumulados", "obitos_acumulados"]]
                .sort_values("data").groupby("codigo_ibge").tail(1).drop(columns="data"))
    m = ultimo.merge(no_corte, on="codigo_ibge", how="left", validate="one_to_one")
    # Município sem nenhum registro até o corte = nenhum caso notificado até então (acumulado zero).
    m[["casos_acumulados", "obitos_acumulados"]] = m[["casos_acumulados", "obitos_acumulados"]].fillna(0).astype("int64")
    m.insert(m.columns.get_loc("casos_acumulados"), "data_corte", corte)
    m["uf"] = m["uf"].astype(str)
    m["codigo_ibge"] = m["codigo_ibge"].astype("int64")
    m["populacao"] = m["populacao"].astype("int64")
    m["e_capital"] = m["codigo_ibge"].isin(CAPITAIS_IBGE)
    m["porte"] = pd.cut(m["populacao"], bins=PORTE_BINS, labels=PORTE_LABELS, right=True)
    m["incidencia_por_100k"] = _per_100k(m["casos_acumulados"], m["populacao"])
    m["mortalidade_por_100k"] = _per_100k(m["obitos_acumulados"], m["populacao"])
    # Letalidade indefinida (NaN) quando não há casos — evita divisão por zero sem imputar valor.
    m["letalidade_pct"] = (
        (m["obitos_acumulados"] / m["casos_acumulados"].replace(0, np.nan)) * 100
    ).round(3)
    return m.sort_values("codigo_ibge").reset_index(drop=True)


# --------------------------------------------------------------------------------------
# 6. Persistência
# --------------------------------------------------------------------------------------
def save(tables: dict[str, pd.DataFrame], report: dict, out_dir: Path = PROCESSED_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, t in tables.items():
        t.to_parquet(out_dir / f"{name}.parquet", index=False, engine="pyarrow", compression="zstd")
        t.to_csv(out_dir / f"{name}.csv.gz", index=False, encoding="utf-8", compression="gzip",
                 date_format="%Y-%m-%d")
        log.info("Salvo %-14s %8s linhas", name, f"{len(t):,}")
    with open(out_dir / "relatorio_qualidade.json", "w", encoding="utf-8") as fh:
        json.dump(report, fh, ensure_ascii=False, indent=2)


def run(force_download: bool = False) -> dict[str, pd.DataFrame]:
    download_raw(force=force_download)
    raw = load_raw()
    report = validate_raw(raw)
    df = clean(raw)
    del raw

    uf_diario = build_uf_diario(df)
    tables = {
        "brasil_diario": build_brasil_diario(uf_diario),
        "uf_diario": uf_diario,
        "uf_mensal": build_uf_mensal(uf_diario),
        "uf_resumo": build_uf_resumo(uf_diario),
        "municipios": build_municipios(df),
    }
    br = tables["brasil_diario"].iloc[-1]
    report["totais_brasil"] = {
        "data_referencia": str(br["data"].date()),
        "casos_acumulados": int(br["casos_acumulados"]),
        "obitos_acumulados": int(br["obitos_acumulados"]),
    }
    report["linhas_por_tabela"] = {k: int(len(v)) for k, v in tables.items()}
    save(tables, report)
    return tables


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true", help="força novo download do arquivo bruto")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    run(force_download=args.force)


if __name__ == "__main__":
    main()
