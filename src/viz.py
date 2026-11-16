from __future__ import annotations

import logging

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
from matplotlib.ticker import FuncFormatter  # noqa: E402
from plotly.subplots import make_subplots  # noqa: E402

from src.etl import PORTE_LABELS, PROCESSED_DIR, REGIOES, ROOT  # noqa: E402

ASSETS = ROOT / "docs" / "assets"
log = logging.getLogger("viz")

# Paleta categórica validada (ordem fixa; nunca reciclada) e tokens de texto/superfície.
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
COR_REGIAO = dict(zip(REGIOES, SERIES))
COR_CASOS, COR_OBITOS = SERIES[0], SERIES[1]
TEXT, TEXT_2, MUTED, GRID, SURFACE = "#1f2937", "#4b5563", "#9ca3af", "#e5e7eb", "#ffffff"
SEQ_BLUE = ["#f4f8fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
FONT = "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif"

ONDAS = [
    ("1ª onda", "2020-03-01", "2020-10-31"),
    ("2ª onda (Gama)", "2020-11-01", "2021-10-31"),
    ("3ª onda (Ômicron)", "2021-11-01", "2022-03-27"),
]


def br_num(x: float, dec: int = 0) -> str:
    """Formata número no padrão brasileiro (1.234,5)."""
    s = f"{x:,.{dec}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


# --------------------------------------------------------------------------------------
# Estilos
# --------------------------------------------------------------------------------------
def _mpl_style() -> None:
    plt.rcParams.update({
        "figure.dpi": 100, "savefig.dpi": 200, "savefig.bbox": "tight",
        "font.family": "sans-serif", "font.size": 10,
        "axes.edgecolor": GRID, "axes.labelcolor": TEXT_2, "axes.titlecolor": TEXT,
        "axes.titleweight": "bold", "axes.titlesize": 12, "axes.titlelocation": "left",
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.color": TEXT_2, "ytick.color": TEXT_2,
        "legend.frameon": False,
    })


def _layout(fig: go.Figure, title: str, height: int = 460, **kw) -> go.Figure:
    kw.setdefault("margin", dict(t=60, r=20, l=60, b=50))
    fig.update_layout(
        title=dict(text=title, x=0.01, xanchor="left", font=dict(size=15, color=TEXT)),
        font=dict(family=FONT, color=TEXT_2, size=12),
        paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, height=height,
        hoverlabel=dict(bgcolor="white", font=dict(family=FONT, color=TEXT)),
        separators=",.",
        **kw,
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    return fig


def _save_html(fig: go.Figure, name: str) -> None:
    fig.write_html(
        ASSETS / f"{name}.html", include_plotlyjs="cdn", full_html=True,
        config={"responsive": True, "displaylogo": False,
                "modeBarButtonsToRemove": ["lasso2d", "select2d"], "locale": "pt-BR"},
    )
    log.info("  %s.html", name)


def _save_png(fig: plt.Figure, name: str) -> None:
    fig.savefig(ASSETS / f"{name}.png", facecolor=SURFACE)
    plt.close(fig)
    log.info("  %s.png", name)


# --------------------------------------------------------------------------------------
# Figura 1 -- RQ1: evolução diária nacional (casos e óbitos em painéis separados)
# --------------------------------------------------------------------------------------
def fig1_evolucao(br: pd.DataFrame) -> None:
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.09,
                        subplot_titles=("Casos novos — média móvel de 7 dias",
                                        "Óbitos novos — média móvel de 7 dias"))
    for row, col, cor, rot in ((1, "casos_mm7", COR_CASOS, "Casos (MM7)"),
                               (2, "obitos_mm7", COR_OBITOS, "Óbitos (MM7)")):
        fig.add_trace(go.Scatter(x=br["data"], y=br[col], mode="lines", name=rot,
                                 line=dict(color=cor, width=2),
                                 hovertemplate="%{x|%d/%m/%Y}<br>" + rot + ": %{y:,.0f}<extra></extra>"),
                      row=row, col=1)
    for i, (nome, ini, fim) in enumerate(ONDAS):
        if i % 2 == 0:
            fig.add_vrect(x0=ini, x1=fim, fillcolor="#f1f5f9", line_width=0, layer="below")
        # Rótulos das ondas no painel de óbitos, alinhados ao início de cada período (sem colidir com picos).
        fig.add_annotation(x=pd.Timestamp(ini) + pd.Timedelta(days=7), y=3000, xref="x2", yref="y2",
                           text=nome, showarrow=False, xanchor="left", font=dict(size=11, color=TEXT_2))
    for col, row, (dx, dy) in (("casos_mm7", 1, (-90, 35)), ("obitos_mm7", 2, (70, 10))):
        i = br[col].idxmax()
        fig.add_annotation(x=br.loc[i, "data"], y=br.loc[i, col], row=row, col=1,
                           text=f"Pico: {br_num(br.loc[i, col])}<br>{br.loc[i, 'data']:%d/%m/%Y}",
                           showarrow=True, arrowhead=0, arrowcolor=MUTED, ax=dx, ay=dy,
                           xanchor="right" if dx < 0 else "left",
                           font=dict(size=11, color=TEXT))
    _layout(fig, "Brasil: casos e óbitos diários de COVID-19 (fev/2020 – mar/2022)",
            height=600, showlegend=False, hovermode="x unified")
    fig.update_yaxes(tickformat=",.0f")
    fig.update_xaxes(tickformat="%m/%Y", dtick="M3")
    for a in fig.layout.annotations[:2]:
        a.update(x=0, xanchor="left", font=dict(size=12, color=TEXT))
    _save_html(fig, "fig1_evolucao_brasil")

    # PNG
    f, axs = plt.subplots(2, 1, figsize=(10, 6.4), sharex=True)
    for ax, col, cor, tit in ((axs[0], "casos_mm7", COR_CASOS, "Casos novos — média móvel de 7 dias"),
                              (axs[1], "obitos_mm7", COR_OBITOS, "Óbitos novos — média móvel de 7 dias")):
        for i, (nome, ini, fim) in enumerate(ONDAS):
            if i % 2 == 0:
                ax.axvspan(pd.Timestamp(ini), pd.Timestamp(fim), color="#f1f5f9", zorder=0)
        ax.plot(br["data"], br[col], color=cor, lw=1.8)
        ax.set_title(tit)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: br_num(v)))
        i = br[col].idxmax()
        ax.annotate(f"Pico: {br_num(br.loc[i, col])}\n{br.loc[i, 'data']:%d/%m/%Y}",
                    (br.loc[i, "data"], br.loc[i, col]),
                    xytext=(-120, -25) if col == "casos_mm7" else (40, -12), textcoords="offset points",
                    fontsize=9, color=TEXT, arrowprops=dict(arrowstyle="-", color=MUTED))
    for nome, ini, _ in ONDAS:
        axs[1].text(pd.Timestamp(ini) + pd.Timedelta(days=7), 3000, nome, ha="left", fontsize=9, color=TEXT_2)
    axs[1].xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
    axs[1].xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y"))
    f.suptitle("Brasil: casos e óbitos diários de COVID-19 (fev/2020 – mar/2022)", x=0.01, ha="left",
               fontweight="bold", color=TEXT)
    f.text(0.01, -0.01, "Fonte: Brasil.IO / Secretarias Estaduais de Saúde. Elaboração própria.",
           fontsize=8, color=MUTED)
    _save_png(f, "fig1_evolucao_brasil")


# --------------------------------------------------------------------------------------
# Figura 2 -- RQ1: letalidade aparente mensal
# --------------------------------------------------------------------------------------
def fig2_letalidade(br: pd.DataFrame) -> None:
    m = (br.assign(mes=br["data"].dt.to_period("M").dt.to_timestamp())
         .groupby("mes", as_index=False)[["casos_novos", "obitos_novos"]].sum())
    m = m[m["casos_novos"] >= 10_000]  # descarta meses com base muito pequena (fev–mar/2020)
    m["letalidade"] = m["obitos_novos"] / m["casos_novos"] * 100
    rotulo = m["mes"].dt.strftime("%m/%Y")
    hover = [f"{r}<br>Letalidade: {br_num(l, 2)}%<br>Casos: {br_num(c)}<br>Óbitos: {br_num(o)}"
             for r, l, c, o in zip(rotulo, m["letalidade"], m["casos_novos"], m["obitos_novos"])]
    fig = go.Figure(go.Bar(x=m["mes"], y=m["letalidade"], marker_color=COR_OBITOS,
                           marker_line_color=SURFACE, marker_line_width=2,
                           hovertext=hover, hoverinfo="text"))
    media = br["obitos_novos"].sum() / br["casos_novos"].sum() * 100
    fig.add_hline(y=media, line=dict(color=TEXT_2, width=1, dash="dot"),
                  annotation_text=f"Média do período: {br_num(media, 2)}%",
                  annotation_position="top right", annotation_font=dict(color=TEXT_2, size=11))
    _layout(fig, "Letalidade aparente mensal (óbitos ÷ casos notificados no mês, %)",
            yaxis=dict(title="%", ticksuffix="%"), bargap=0.15,
            xaxis=dict(tickformat="%m/%Y", dtick="M3"))
    _save_html(fig, "fig2_letalidade_mensal")

    f, ax = plt.subplots(figsize=(10, 4))
    ax.bar(m["mes"], m["letalidade"], width=25, color=COR_OBITOS, edgecolor=SURFACE, linewidth=1)
    ax.axhline(media, color=TEXT_2, lw=1, ls=":")
    ax.text(m["mes"].iloc[-1], media + 0.15, f"Média do período: {br_num(media, 2)}%", ha="right",
            fontsize=9, color=TEXT_2)
    ax.set_title("Letalidade aparente mensal (óbitos ÷ casos notificados no mês)")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{br_num(v, 0)}%"))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%Y"))
    ax.grid(axis="x", visible=False)
    _save_png(f, "fig2_letalidade_mensal")


# --------------------------------------------------------------------------------------
# Figura 3 -- RQ1/RQ2: mapa de calor UF x mês (óbitos por 100 mil)
# --------------------------------------------------------------------------------------
def fig3_heatmap(uf_mensal: pd.DataFrame, uf_resumo: pd.DataFrame) -> None:
    ordem = (uf_resumo.assign(regiao=pd.Categorical(uf_resumo["regiao"], REGIOES, ordered=True))
             .sort_values(["regiao", "uf"])["uf"].tolist())
    piv = uf_mensal.pivot(index="uf", columns="mes", values="obitos_por_100k").reindex(ordem)
    piv = piv.clip(lower=0)  # correções negativas pontuais não têm leitura em escala sequencial
    rotulos_y = [f"{uf} · {uf_resumo.set_index('uf').loc[uf, 'regiao']}" for uf in piv.index]
    fig = go.Figure(go.Heatmap(
        z=piv.values, x=piv.columns, y=rotulos_y, colorscale=[[i / 7, c] for i, c in enumerate(SEQ_BLUE)],
        xgap=1, ygap=1, colorbar=dict(title="Óbitos por<br>100 mil hab.", thickness=12),
        hovertemplate="%{y}<br>%{x|%m/%Y}<br>%{z:.1f} óbitos por 100 mil<extra></extra>"))
    _layout(fig, "Óbitos mensais por 100 mil habitantes, por UF (agrupadas por região)", height=680,
            margin=dict(t=60, r=20, l=130, b=50))
    fig.update_yaxes(autorange="reversed", showgrid=False, tickfont=dict(size=11))
    fig.update_xaxes(showgrid=False, dtick="M3", tickformat="%m/%Y")
    _save_html(fig, "fig3_heatmap_uf_mes")

    f, ax = plt.subplots(figsize=(11, 7.5))
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("seq", SEQ_BLUE)
    im = ax.imshow(piv.values, aspect="auto", cmap=cmap, interpolation="nearest")
    ax.set_yticks(range(len(piv)), rotulos_y, fontsize=8)
    idx = [i for i, d in enumerate(piv.columns) if d.month in (1, 4, 7, 10)]
    ax.set_xticks(idx, [piv.columns[i].strftime("%m/%Y") for i in idx], rotation=0, fontsize=8)
    ax.grid(False)
    cb = f.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("Óbitos por 100 mil hab.", color=TEXT_2)
    cb.outline.set_visible(False)
    ax.set_title("Óbitos mensais por 100 mil habitantes, por UF")
    _save_png(f, "fig3_heatmap_uf_mes")


# --------------------------------------------------------------------------------------
# Figura 4 -- RQ2: ranking das UFs por mortalidade acumulada
# --------------------------------------------------------------------------------------
def fig4_ranking(uf_resumo: pd.DataFrame, br: pd.DataFrame) -> None:
    r = uf_resumo.sort_values("mortalidade_por_100k")
    mort_br = br["obitos_acumulados"].iloc[-1] / br["populacao"].iloc[0] * 1e5
    fig = go.Figure()
    for reg in REGIOES:
        d = r[r["regiao"] == reg]
        fig.add_trace(go.Bar(
            y=d["uf"], x=d["mortalidade_por_100k"], orientation="h", name=reg,
            marker_color=COR_REGIAO[reg], marker_line_color=SURFACE, marker_line_width=2,
            customdata=np.stack([d["obitos_acumulados"], d["letalidade_pct"], d["incidencia_por_100k"]], axis=1),
            hovertemplate="<b>%{y}</b> (" + reg + ")<br>Mortalidade: %{x:.1f} por 100 mil"
                          "<br>Óbitos: %{customdata[0]:,.0f}<br>Incidência: %{customdata[2]:,.0f} por 100 mil"
                          "<br>Letalidade: %{customdata[1]:.2f}%<extra></extra>"))
    fig.add_vline(x=mort_br, line=dict(color=TEXT, width=1, dash="dot"),
                  annotation_text=f"Brasil: {br_num(mort_br, 1)}", annotation_position="bottom right",
                  annotation_font=dict(size=11, color=TEXT))
    _layout(fig, "Mortalidade acumulada por COVID-19 (óbitos por 100 mil hab.), por UF", height=680,
            legend=dict(orientation="h", y=1.04, x=0, title=None), bargap=0.2,
            yaxis=dict(categoryorder="array", categoryarray=r["uf"].tolist(), showgrid=False),
            xaxis=dict(title="Óbitos por 100 mil habitantes"))
    _save_html(fig, "fig4_ranking_uf")

    f, ax = plt.subplots(figsize=(8, 8))
    ax.barh(r["uf"], r["mortalidade_por_100k"], color=[COR_REGIAO[g] for g in r["regiao"]],
            edgecolor=SURFACE, linewidth=1, height=0.8)
    for y, v in enumerate(r["mortalidade_por_100k"]):
        ax.text(v + 4, y, br_num(v, 1), va="center", fontsize=8, color=TEXT_2)
    ax.axvline(mort_br, color=TEXT, lw=1, ls=":")
    ax.text(mort_br + 4, 0.2, f"Brasil: {br_num(mort_br, 1)}", fontsize=8, color=TEXT)
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Óbitos por 100 mil habitantes")
    ax.set_title("Mortalidade acumulada por UF (até 27/03/2022)")
    from matplotlib.patches import Patch
    ax.legend(handles=[Patch(color=COR_REGIAO[g], label=g) for g in REGIOES], loc="lower right")
    _save_png(f, "fig4_ranking_uf")


# --------------------------------------------------------------------------------------
# Figura 5 -- RQ2: incidência x letalidade por UF
# --------------------------------------------------------------------------------------
def fig5_dispersao(uf_resumo: pd.DataFrame) -> None:
    fig = go.Figure()
    for reg in REGIOES:
        d = uf_resumo[uf_resumo["regiao"] == reg]
        fig.add_trace(go.Scatter(
            x=d["incidencia_por_100k"], y=d["letalidade_pct"], mode="markers+text", name=reg,
            text=d["uf"], textposition="top center", textfont=dict(size=10, color=TEXT_2),
            marker=dict(size=np.sqrt(d["populacao"]) / 220 + 8, color=COR_REGIAO[reg], opacity=0.9,
                        line=dict(color=SURFACE, width=2)),
            customdata=np.stack([d["mortalidade_por_100k"], d["populacao"]], axis=1),
            hovertemplate="<b>%{text}</b> (" + reg + ")<br>Incidência: %{x:,.0f} por 100 mil"
                          "<br>Letalidade: %{y:.2f}%<br>Mortalidade: %{customdata[0]:.1f} por 100 mil"
                          "<br>População: %{customdata[1]:,.0f}<extra></extra>"))
    _layout(fig, "Incidência acumulada × letalidade aparente por UF (tamanho = população)", height=520,
            legend=dict(orientation="h", y=1.06, x=0, title=None),
            xaxis=dict(title="Casos confirmados por 100 mil habitantes", tickformat=",.0f"),
            yaxis=dict(title="Letalidade aparente (%)", ticksuffix="%"))
    _save_html(fig, "fig5_incidencia_letalidade")

    f, ax = plt.subplots(figsize=(9, 5.5))
    for reg in REGIOES:
        d = uf_resumo[uf_resumo["regiao"] == reg]
        ax.scatter(d["incidencia_por_100k"], d["letalidade_pct"], s=np.sqrt(d["populacao"]) / 12 + 20,
                   color=COR_REGIAO[reg], edgecolor=SURFACE, linewidth=1.5, label=reg, zorder=3)
        for _, row in d.iterrows():
            ax.annotate(row["uf"], (row["incidencia_por_100k"], row["letalidade_pct"]), xytext=(0, 7),
                        textcoords="offset points", ha="center", fontsize=8, color=TEXT_2)
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: br_num(v)))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{br_num(v, 1)}%"))
    ax.set_xlabel("Casos confirmados por 100 mil habitantes")
    ax.set_ylabel("Letalidade aparente")
    ax.set_title("Incidência acumulada × letalidade aparente por UF")
    ax.legend(loc="upper right", markerscale=0.6)
    _save_png(f, "fig5_incidencia_letalidade")


# --------------------------------------------------------------------------------------
# Figura 6 -- RQ3: mortalidade por porte populacional dos municípios
# --------------------------------------------------------------------------------------
def fig6_porte(mun: pd.DataFrame) -> None:
    agg = (mun.groupby("porte", observed=True)
           .agg(n=("codigo_ibge", "size"), pop=("populacao", "sum"), obitos=("obitos_acumulados", "sum"))
           .reindex(PORTE_LABELS))
    agg["taxa"] = agg["obitos"] / agg["pop"] * 1e5
    fig = go.Figure()
    for p in PORTE_LABELS:
        d = mun[mun["porte"] == p]
        fig.add_trace(go.Box(
            y=d["mortalidade_por_100k"], name=f"{p}<br>(n = {br_num(len(d))})", marker_color=COR_CASOS,
            line=dict(width=1.5), fillcolor="rgba(42,120,214,0.15)", boxpoints="outliers",
            marker=dict(size=4, opacity=0.5), text=d["municipio"] + " – " + d["uf"],
            hovertemplate="%{text}<br>%{y:.1f} óbitos por 100 mil<extra></extra>", showlegend=False))
    fig.add_trace(go.Scatter(
        x=[f"{p}<br>(n = {br_num(n)})" for p, n in zip(agg.index, agg["n"])], y=agg["taxa"],
        mode="markers+lines", name="Taxa agregada do grupo (Σ óbitos ÷ Σ população)",
        line=dict(color=COR_OBITOS, width=2, dash="dot"),
        marker=dict(size=10, color=COR_OBITOS, symbol="diamond", line=dict(color=SURFACE, width=2)),
        hovertemplate="Taxa agregada: %{y:.1f} por 100 mil<extra></extra>"))
    corte = mun["data_corte"].iloc[0].strftime("%d/%m/%Y")
    _layout(fig, f"Mortalidade acumulada dos municípios por porte populacional (até {corte})", height=520,
            legend=dict(orientation="h", y=1.06, x=0),
            yaxis=dict(title="Óbitos por 100 mil habitantes"), xaxis=dict(title="Porte do município"))
    _save_html(fig, "fig6_porte_municipios")

    f, ax = plt.subplots(figsize=(9, 5))
    dados = [mun.loc[mun["porte"] == p, "mortalidade_por_100k"] for p in PORTE_LABELS]
    bp = ax.boxplot(dados, patch_artist=True, widths=0.55, flierprops=dict(marker=".", ms=3, alpha=0.4,
                                                                             mfc=COR_CASOS, mec="none"),
                    medianprops=dict(color=COR_CASOS, lw=2))
    for b in bp["boxes"]:
        b.set(facecolor="#e8f1fc", edgecolor=COR_CASOS)
    ax.plot(range(1, 6), agg["taxa"], color=COR_OBITOS, marker="D", ls=":", lw=1.5,
            label="Taxa agregada do grupo")
    ax.set_xticks(range(1, 6), [f"{p}\n(n = {br_num(n)})" for p, n in zip(agg.index, agg["n"])], fontsize=9)
    ax.set_ylabel("Óbitos por 100 mil habitantes")
    ax.set_title(f"Mortalidade acumulada dos municípios por porte populacional (até {corte})")
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper left")
    _save_png(f, "fig6_porte_municipios")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    ASSETS.mkdir(parents=True, exist_ok=True)
    _mpl_style()
    br = pd.read_parquet(PROCESSED_DIR / "brasil_diario.parquet")
    uf_mensal = pd.read_parquet(PROCESSED_DIR / "uf_mensal.parquet")
    uf_resumo = pd.read_parquet(PROCESSED_DIR / "uf_resumo.parquet")
    mun = pd.read_parquet(PROCESSED_DIR / "municipios.parquet")
    log.info("Gerando figuras em %s", ASSETS.relative_to(ROOT).as_posix())
    fig1_evolucao(br)
    fig2_letalidade(br)
    fig3_heatmap(uf_mensal, uf_resumo)
    fig4_ranking(uf_resumo, br)
    fig5_dispersao(uf_resumo)
    fig6_porte(mun)


if __name__ == "__main__":
    main()
