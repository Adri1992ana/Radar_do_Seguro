"""
Radar do Seguro - Automóvel e Patrimonial
App Streamlit do projeto final de Visualização de Dados e BI (SENAI SC / LAB365).

Executar:  streamlit run app.py
Dados lidos de dados/app/ (gerados por src/preparar_dados_app.py). Nenhum caminho absoluto.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import analysis as an

BASE = Path(__file__).resolve().parent
DADOS = BASE / "dados" / "app"
FONTE = "Fonte: CNseg, Panorama Estatístico (compila SUSEP/SES, extração de 28/09/2026). Elaboração própria."
FONTE_SUSEP = "Fonte: SUSEP, SES (arquivo SES_ValoresMovRamos), agregado por ramo e mês. Elaboração própria."

# Paleta categórica validada (primeiros 3 encaixes: passam em todas as comparações, claro e escuro)
CAT_CLARO = ["#2a78d6", "#eb6834", "#1baf7a"]
CAT_ESCURO = ["#3987e5", "#d95926", "#199e70"]
ORDEM_ITENS = ["Automóvel", "Patrimonial", "Habitacional"]  # cor fixa por entidade, nunca por ranking
NEUTRO_CLARO, NEUTRO_ESCURO = "#6b6b66", "#a8a7a0"

METRICAS = {"arrecadacao": "Arrecadação (prêmio direto)", "sinistro": "Sinistros ocorridos"}

st.set_page_config(page_title="Radar do Seguro | Automóvel e Patrimonial", page_icon=None, layout="wide")


# ----------------------------------------------------------------------------- utilidades
def escuro() -> bool:
    try:
        return st.context.theme.type == "dark"
    except Exception:
        return False


def cor_item(item: str) -> str:
    paleta = CAT_ESCURO if escuro() else CAT_CLARO
    if item in ORDEM_ITENS:
        return paleta[ORDEM_ITENS.index(item)]
    return NEUTRO_ESCURO if escuro() else NEUTRO_CLARO


def cats() -> list[str]:
    return CAT_ESCURO if escuro() else CAT_CLARO


def br(x: float, casas: int = 2) -> str:
    if x is None or not np.isfinite(x):
        return "n/d"
    return f"{x:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def bi(v: float, casas: int = 2) -> str:
    return "n/d" if v is None or not np.isfinite(v) else f"R$ {br(v / 1e9, casas)} bi"


def pct(x: float, casas: int = 1, sinal: bool = False) -> str:
    if x is None or not np.isfinite(x):
        return "n/d"
    s = br(x * 100, casas) + "%"
    return ("+" + s) if sinal and x > 0 else s


def mes_fmt(m: pd.Timestamp) -> str:
    return f"{an.MESES_PT[m.month - 1]}/{m.year}"


def layout(fig: go.Figure, titulo: str, y: str, x: str | None = None, altura: int = 420) -> go.Figure:
    grade = "rgba(128,128,128,0.22)"
    fig.update_layout(
        title=dict(text=titulo, x=0, font=dict(size=16)),
        height=altura, margin=dict(l=10, r=10, t=60, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, title_text=""),
        hovermode="x unified",
        separators=",.",  # vírgula decimal e ponto de milhar (padrão brasileiro)
    )
    fig.update_yaxes(title_text=y, gridcolor=grade, zeroline=False)
    fig.update_xaxes(title_text=x, gridcolor="rgba(0,0,0,0)")
    return fig


def mostrar(fig: go.Figure, fonte: str = FONTE) -> None:
    st.plotly_chart(fig, width="stretch")
    st.caption(fonte)


# ----------------------------------------------------------------------------- dados
@st.cache_data(show_spinner="Carregando dados...")
def carregar_cnseg() -> pd.DataFrame | None:
    f = DADOS / "cnseg_danos_mensal.csv"
    return an.carregar_mensal(f) if f.exists() else None


@st.cache_data(show_spinner=False)
def carregar_opcional(nome: str, datas: tuple = ("mes",), texto: tuple = ()) -> pd.DataFrame | None:
    f = DADOS / nome
    if not f.exists():
        return None
    return pd.read_csv(f, parse_dates=list(datas), dtype={c: str for c in texto})


df = carregar_cnseg()
if df is None or df.empty:
    st.error("Arquivo dados/app/cnseg_danos_mensal.csv não encontrado. Rode `python src/preparar_dados_app.py` "
             "(veja o README, seção Como executar).")
    st.stop()

MESES = sorted(df.loc[df.valor.notna(), "mes"].unique())
ULT = an.ultimo_mes(df)

# ----------------------------------------------------------------------------- barra lateral
st.sidebar.title("Radar do Seguro")
PAGINAS = ["Visão geral", "Evolução", "Sazonalidade e volatilidade", "Sinistralidade e relações",
           "Detalhe por ramo (SUSEP)", "Validação CNseg × SUSEP", "Sobre e limitações"]
pagina = st.sidebar.radio("Navegação", PAGINAS)

st.sidebar.markdown("---")
st.sidebar.subheader("Filtros")
itens = st.sidebar.multiselect("Grupos de ramo", ORDEM_ITENS, default=["Automóvel", "Patrimonial"],
                               help="Habitacional entra como contexto opcional.")
ini, fim = st.sidebar.select_slider("Período", options=[pd.Timestamp(m) for m in MESES],
                                    value=(pd.Timestamp(MESES[0]), pd.Timestamp(MESES[-1])), format_func=mes_fmt)
st.sidebar.caption(f"Dados disponíveis: {mes_fmt(pd.Timestamp(MESES[0]))} a {mes_fmt(ULT)}.")


def cabecalho(titulo: str, descricao: str) -> None:
    st.title(titulo)
    st.markdown(descricao)
    st.caption(f"Filtros ativos: {', '.join(itens) if itens else 'nenhum grupo'} | período {mes_fmt(ini)} a {mes_fmt(fim)} "
               f"({int(((fim.year - ini.year) * 12 + fim.month - ini.month) + 1)} meses)")


def exige_itens() -> None:
    if not itens:
        st.warning("Selecione ao menos um grupo de ramo na barra lateral.")
        st.stop()


def recorte(s: pd.Series) -> pd.Series:
    return s[(s.index >= ini) & (s.index <= fim)]


# ----------------------------------------------------------------------------- páginas
def pg_visao_geral() -> None:
    cabecalho("Arrecadação e sinistralidade do seguro: Automóvel e Patrimonial",
              "**Pergunta:** como evoluíram a arrecadação, os sinistros e a sinistralidade de Automóvel e Patrimonial "
              "(Danos e Responsabilidades) entre jan/2021 e jul/2026, e como se comportam a sazonalidade e a volatilidade?  \n"
              "**Para quem:** corretores, analistas e estudantes de seguros que precisam de uma leitura rápida e conferível do segmento.")
    exige_itens()
    st.subheader(f"Indicadores do último mês publicado ({mes_fmt(ULT)})")
    cols = st.columns(len(itens))
    for c, it in zip(cols, itens):
        s = an.serie(df, it, "arrecadacao")
        sl = an.serie(df, it, "sinistralidade")
        with c:
            st.markdown(f"**{it}**")
            st.metric("Arrecadação no mês", bi(s.get(ULT, np.nan)), pct(an.var_aa(s, ULT), 1, True) + " vs mesmo mês de 2025",
                      help="Prêmio direto de seguros: emissão líquida de cancelamento e restituição (definição da CNseg).")
            st.metric(f"Acumulado jan-{an.MESES_PT[ULT.month - 1].lower()}/{ULT.year}", bi(an.acumulado_ano(s, ULT.year, ULT.month)),
                      pct(an.var_acumulado_ano(s, ULT.year, ULT.month), 1, True) + f" vs jan-{an.MESES_PT[ULT.month - 1].lower()}/{ULT.year - 1}")
            st.metric("Sinistralidade no mês (índice da fonte)", pct(sl.get(ULT, np.nan), 1),
                      help="Índice divulgado pela CNseg. Não é idêntico a sinistros ÷ arrecadação; veja a página Sobre e limitações.")
            st.metric("Peso em Danos (12 meses)", pct(an.participacao_12m(df, it, "arrecadacao", ULT), 1),
                      help="Arrecadação dos últimos 12 meses do grupo dividida pela de todo Danos e Responsabilidades.")
    st.subheader("O que os números mostram")
    st.caption("Observações calculadas a partir dos dados; não indicam causa.")
    linhas = []
    for it in itens:
        s = an.serie(df, it, "arrecadacao")
        k = an.serie(df, it, "sinistro")
        linhas.append(
            f"- **{it}:** arrecadação de {bi(an.soma_janela(s, ULT))} nos 12 meses até {mes_fmt(ULT)} "
            f"({pct(an.var_12m(s, ULT), 1, True)} sobre os 12 meses anteriores); sinistros de {bi(an.soma_janela(k, ULT))} "
            f"({pct(an.var_12m(k, ULT), 1, True)}). Crescimento médio anual da arrecadação em 2021-2025: {pct(an.cagr(s, 2021, 2025), 1)}.")
    st.markdown("\n".join(linhas))
    st.info("Use o menu à esquerda para navegar: **Evolução** (séries e totais anuais), **Sazonalidade e volatilidade**, "
            "**Sinistralidade e relações**, **Detalhe por ramo** (residencial, empresarial etc., via SUSEP) e **Validação** das duas fontes.")


def pg_evolucao() -> None:
    cabecalho("Evolução da arrecadação e dos sinistros",
              "Valores em **R$ bilhões**. A visão mensal mostra a sazonalidade; o **acumulado de 12 meses** a suaviza e deixa a tendência visível.")
    exige_itens()
    c1, c2 = st.columns(2)
    met = c1.radio("Métrica", list(METRICAS), format_func=METRICAS.get, horizontal=True)
    modo = c2.radio("Visão", ["Mensal", "Acumulado de 12 meses"], horizontal=True)
    fig = go.Figure()
    tabela = {}
    for it in itens:
        s = an.serie(df, it, met)
        if modo != "Mensal":
            s = an.acumulado_12m_serie(s)
        s = recorte(s) / 1e9
        if s.empty:
            continue
        tabela[it] = s
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=it, mode="lines", line=dict(color=cor_item(it), width=2),
                                 hovertemplate="%{y:.2f} bi"))
    if not tabela:
        st.warning("Sem dados no período selecionado.")
        return
    fig.update_xaxes(tickformat="%b/%Y")
    titulo = f"{METRICAS[met]}: {modo.lower()}"
    mostrar(layout(fig, titulo, "R$ bilhões", "Mês"))
    with st.expander("Ver tabela dos dados do gráfico"):
        t = pd.DataFrame(tabela)
        t.index = [mes_fmt(m) for m in t.index]
        st.dataframe(t.round(3), width="stretch")

    st.subheader("Totais anuais e crescimento")
    st.caption(f"{ULT.year} é parcial ({ULT.month} meses): a variação compara os mesmos meses do ano anterior.")
    linhas = []
    for it in itens:
        s = an.serie(df, it, met)
        ta = an.totais_anuais(s, ULT)
        for _, r in ta.iterrows():
            linhas.append({"Grupo": it, "Ano": f"{int(r.ano)}{' (parcial)' if r.parcial else ''}", "Meses": int(r.meses),
                           "Total (R$ bi)": br(r.total / 1e9), "Var. a/a": pct(r.var_aa, 1, True)})
    st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True)
    cols = st.columns(len(itens))
    for c, it in zip(cols, itens):
        c.metric(f"{it}: crescimento médio anual 2021-2025 (CAGR)", pct(an.cagr(an.serie(df, it, met), 2021, 2025), 1),
                 help="Taxa composta entre os anos completos de 2021 e 2025, valores nominais (sem descontar inflação).")
    st.warning("Valores nominais: parte do crescimento reflete inflação e reajustes de preço, não só aumento de volume.")


def pg_sazonalidade() -> None:
    cabecalho("Sazonalidade e volatilidade",
              "Quais meses concentram mais arrecadação (ou sinistros) e quanto cada grupo oscila.")
    exige_itens()
    met = st.radio("Métrica", list(METRICAS), format_func=METRICAS.get, horizontal=True, key="met_saz")

    st.subheader("Índice sazonal por mês")
    st.caption("Valor do mês ÷ média do ano, promediado nos anos completos (2021-2025). 1,00 = mês médio; 1,10 = 10% acima da média do ano. "
               "O método é simples e não separa o efeito do crescimento ao longo do ano.")
    fig = go.Figure()
    for it in itens:
        idx = an.indice_sazonal(an.serie(df, it, met))
        if idx.empty:
            continue
        fig.add_trace(go.Scatter(x=[an.MESES_PT[m - 1] for m in idx.index], y=idx.values, name=it, mode="lines+markers",
                                 line=dict(color=cor_item(it), width=2), marker=dict(size=8),
                                 hovertemplate="%{y:.2f}"))
    fig.add_hline(y=1.0, line_dash="dot", line_color="rgba(128,128,128,0.7)")
    fig.update_yaxes(tickformat=".2f")
    mostrar(layout(fig, f"Índice sazonal: {METRICAS[met].lower()}", "Índice (média do ano = 1,00)", "Mês"))

    st.subheader("Mapa de calor mês × ano")
    it_h = st.selectbox("Grupo", itens, key="hm_item")
    m = an.matriz_mes_ano(an.serie(df, it_h, met)) / 1e9
    if not m.empty:
        esc = [[0, "#16263d"], [1, "#6aa6f0"]] if escuro() else [[0, "#eaf2fc"], [1, "#1d5aa8"]]
        fig = go.Figure(go.Heatmap(z=m.values, x=an.MESES_PT, y=[str(a) for a in m.index], colorscale=esc,
                                   colorbar=dict(title="R$ bi"), hoverongaps=False, xgap=2, ygap=2,
                                   texttemplate="%{z:.1f}", hovertemplate="%{y} %{x}: R$ %{z:.2f} bi<extra></extra>"))
        fig.update_yaxes(autorange="reversed")
        fig = layout(fig, f"{it_h}: {METRICAS[met].lower()} por mês (R$ bilhões)", "Ano", "Mês", 380)
        fig.update_layout(hovermode="closest")
        mostrar(fig)
        st.caption("Células em branco = meses ainda sem dados na fonte.")

    st.subheader("Volatilidade")
    linhas = []
    for it in itens:
        v = an.volatilidade(an.serie(df, it, met))
        t = an.tendencia_linear(an.serie(df, it, met))
        linhas.append({"Grupo": it, "CV (últimos 24 meses)": pct(v["cv"], 1),
                       "Desvio-padrão da var. a/a (p.p.)": br(v["dp_aa_pp"], 1),
                       "Tendência linear (R$ mi por mês)": br(t["inclinacao_mes"] / 1e6, 1), "R² da tendência": br(t["r2"], 2)})
    st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True)
    st.caption("CV = desvio-padrão ÷ média (quanto maior, mais oscilante). A tendência é uma reta ajustada aos meses: "
               "descreve a direção média e não prevê o futuro.")


def pg_sinistralidade() -> None:
    cabecalho("Sinistralidade e relações",
              "Sinistralidade é a parcela da arrecadação que vira sinistro. Abaixo: sua evolução, meses atípicos e a relação com a arrecadação.")
    exige_itens()
    fig = go.Figure()
    for it in itens:
        s = recorte(an.serie(df, it, "sinistralidade"))
        if s.empty:
            continue
        fig.add_trace(go.Scatter(x=s.index, y=s.values * 100, name=it, mode="lines", line=dict(color=cor_item(it), width=2),
                                 hovertemplate="%{y:.1f}%"))
    fig.update_xaxes(tickformat="%b/%Y")
    mostrar(layout(fig, "Sinistralidade mensal (índice da fonte)", "% (sinistros ÷ prêmio)", "Mês"))
    st.caption("Valores acima de 100% significam sinistros maiores que o prêmio do mês. Meses isolados de Patrimonial "
               "podem refletir sinistros de grande porte; a série mensal é mais ruidosa que a anual.")

    st.subheader("Meses atípicos (outliers)")
    linhas = []
    for it in itens:
        o = an.outliers_mad(an.serie(df, it, "sinistralidade"))
        for _, r in o.iterrows():
            linhas.append({"Grupo": it, "Mês": mes_fmt(r.mes), "Sinistralidade": pct(r.valor, 1), "Escore z robusto": br(r.z_robusto, 1)})
    if linhas:
        st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True)
    else:
        st.write("Nenhum mês ultrapassa o corte de |z| > 3,5 nos grupos selecionados.")
    st.caption("Critério: escore z robusto (mediana e MAD) com corte de 3,5. Um mês atípico não é necessariamente erro; pode ser um evento real.")

    st.subheader("Arrecadação × sinistros: variações anuais")
    st.caption("Cada ponto é um mês: variação a/a da arrecadação (eixo x) e dos sinistros (eixo y). "
               "Compara-se variações, e não níveis, para não confundir tendência comum com relação.")
    fig = go.Figure()
    linhas = []
    for it in itens:
        c = an.correlacao_aa(an.serie(df, it, "arrecadacao"), an.serie(df, it, "sinistro"))
        d = c["dados"]
        if d.empty:
            continue
        d = d[(d.index >= ini) & (d.index <= fim)]
        fig.add_trace(go.Scatter(x=d["arrecadacao"] * 100, y=d["sinistro"] * 100, name=it, mode="markers",
                                 marker=dict(color=cor_item(it), size=9, line=dict(width=2, color="rgba(255,255,255,0.0)")),
                                 text=[mes_fmt(m) for m in d.index],
                                 hovertemplate="%{text}<br>Arrecadação: %{x:.1f}%<br>Sinistros: %{y:.1f}%<extra>" + it + "</extra>"))
        linhas.append({"Grupo": it, "Pares mensais (n)": c["n"], "Pearson": br(c["pearson"], 2),
                       "p (Pearson)": f"{c['p_pearson']:.1e}".replace(".", ","),
                       "Spearman (menos sensível a extremos)": br(c["spearman"], 2),
                       "p (Spearman)": f"{c['p_spearman']:.1e}".replace(".", ",")})
    fig.add_hline(y=0, line_color="rgba(128,128,128,0.5)")
    fig.add_vline(x=0, line_color="rgba(128,128,128,0.5)")
    fig.update_xaxes(ticksuffix="%", gridcolor="rgba(128,128,128,0.22)")
    fig = layout(fig, "Variação a/a: sinistros × arrecadação", "Variação a/a dos sinistros (%)", "Variação a/a da arrecadação (%)", 460)
    fig.update_layout(hovermode="closest")
    # Escala robusta: um mês com variação extrema (ex.: +1.000%) achataria todos os outros pontos.
    ys = np.concatenate([np.asarray(t.y, dtype=float) for t in fig.data]) if len(fig.data) else np.array([])
    fora = 0
    if ys.size >= 20:
        lo, hi = np.percentile(ys, [2, 98])
        folga = 0.15 * max(hi - lo, 1.0)
        fig.update_yaxes(range=[lo - folga, hi + folga])
        fora = int(((ys < lo - folga) | (ys > hi + folga)).sum())
    mostrar(fig)
    if fora:
        st.caption(f"Escala ajustada aos percentis 2 a 98 para legibilidade; {fora} ponto(s) extremo(s) ficam fora do quadro "
                   "(os coeficientes abaixo usam todos os pontos).")
    if linhas:
        st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True)
    st.warning("Correlação mede associação, não causa. Os pares mensais se sobrepõem no tempo (variações sobre 12 meses), "
               "então os valores-p tendem a ser otimistas; use os coeficientes como indicação, não como prova.")


def pg_ramos() -> None:
    cabecalho("Detalhe por ramo (SUSEP)",
              "A SUSEP abre cada grupo em ramos, o que a CNseg não mostra: por exemplo, em Patrimonial, Compreensivo Residencial, Condomínio e Empresarial. "
              "Campo usado: **Prêmios Diretos (12011)** e **Sinistros Ocorridos (12181)**.")
    rm = carregar_opcional("susep_danos_ramo_mes.csv", texto=("codigo",))
    if rm is None or rm.empty:
        st.info("Esta página usa dados da SUSEP que não estão disponíveis nesta instalação. Gere-os com "
                "`python src/susep_validacao.py ...` e `python src/preparar_dados_app.py` (veja o README).")
        return
    c1, c2 = st.columns(2)
    grupo = c1.selectbox("Grupo", [g for g in ORDEM_ITENS if g in rm.grupo1.unique()])
    campo = c2.radio("Campo", ["cmp_12011", "cmp_12181"], format_func=lambda c: {"cmp_12011": "Prêmios Diretos", "cmp_12181": "Sinistros Ocorridos"}[c], horizontal=True)
    if campo not in rm.columns:
        st.warning("Campo indisponível nos dados carregados.")
        return
    g = rm[rm.grupo1 == grupo].copy()
    g["ramo"] = g.codigo + " - " + g.nome_ramo.str.title()
    g12 = g[(g.mes > ULT - pd.DateOffset(years=1)) & (g.mes <= ULT)].groupby("ramo")[campo].sum().sort_values(ascending=False)
    g12 = g12[g12.abs() > 0]
    if g12.empty:
        st.warning("Sem dados para este grupo.")
        return
    topo = g12.head(10)[::-1] / 1e9
    fig = go.Figure(go.Bar(x=topo.values, y=list(topo.index), orientation="h", marker=dict(color=cats()[0]),
                           hovertemplate="%{y}: R$ %{x:.2f} bi<extra></extra>"))
    fig.update_layout(hovermode="closest")
    fig = layout(fig, f"{grupo}: maiores ramos nos 12 meses até {mes_fmt(ULT)}", "", "R$ bilhões", max(320, 40 * len(topo) + 120))
    fig.update_yaxes(gridcolor="rgba(0,0,0,0)")
    fig.update_xaxes(gridcolor="rgba(128,128,128,0.22)")
    mostrar(fig, FONTE_SUSEP)

    padrao = list(g12.index[:3])
    if grupo == "Patrimonial":
        pref = [r for r in g12.index if r[:4] in ("0114", "0118", "0116")]
        padrao = pref[:3] or padrao
    escolha = st.multiselect("Ramos para comparar no tempo (até 3)", list(g12.index), default=padrao, max_selections=3)
    fig = go.Figure()
    for i, r in enumerate(escolha):
        s = g[g.ramo == r].set_index("mes")[campo].sort_index()
        s = s[(s.index >= ini) & (s.index <= fim)] / 1e9
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=r, mode="lines", line=dict(color=cats()[i], width=2), hovertemplate="%{y:.3f} bi"))
    if escolha:
        fig.update_xaxes(tickformat="%b/%Y")
        mostrar(layout(fig, "Evolução mensal dos ramos selecionados", "R$ bilhões", "Mês"), FONTE_SUSEP)
    else:
        st.info("Selecione ao menos um ramo para ver a evolução.")


def pg_validacao() -> None:
    cabecalho("Validação: CNseg × SUSEP",
              "A CNseg compila os dados da SUSEP. Aqui comparamos, por grupo e mês, a arrecadação (prêmio direto) e os sinistros da CNseg com a soma dos ramos correspondentes no SES da SUSEP.")
    v = carregar_opcional("susep_vs_cnseg_danos.csv")
    if v is None or v.empty:
        st.info("Esta página usa a comparação gerada por `src/susep_validacao.py`, que não está disponível nesta instalação (veja o README).")
        return
    exige_itens()
    v = v[v.item.isin(itens)]
    if v.empty:
        st.warning("Sem comparação para os grupos selecionados.")
        return
    met = st.radio("Métrica", ["arrecadacao", "sinistro"], format_func=METRICAS.get, horizontal=True, key="met_val")
    d = v[v.metrica == met].copy()
    mes_sel = st.select_slider("Mês", options=sorted(d.mes.unique()), value=d.mes.max(), format_func=lambda m: mes_fmt(pd.Timestamp(m)))
    t = d[d.mes == mes_sel][["item", "susep", "cnseg", "dif_pct"]].copy()
    t["SUSEP (R$ bi)"] = (t.susep / 1e9).map(lambda x: br(x, 3))
    t["CNseg (R$ bi)"] = (t.cnseg / 1e9).map(lambda x: br(x, 3))
    t["Diferença"] = t.dif_pct.map(lambda x: pct(x, 2, True))
    st.dataframe(t.rename(columns={"item": "Grupo"})[["Grupo", "SUSEP (R$ bi)", "CNseg (R$ bi)", "Diferença"]], width="stretch", hide_index=True)
    fig = go.Figure()
    for it in itens:
        s = d[d.item == it].sort_values("mes")
        fig.add_trace(go.Scatter(x=s.mes, y=s.dif_pct * 100, name=it, mode="lines", line=dict(color=cor_item(it), width=2), hovertemplate="%{y:.2f}%"))
    fig.add_hline(y=0, line_color="rgba(128,128,128,0.6)")
    fig.update_xaxes(tickformat="%b/%Y")
    mostrar(layout(fig, "Diferença SUSEP vs CNseg ao longo do tempo", "Diferença (%)", "Mês"),
            "Fontes: CNseg, Panorama Estatístico (extração de 28/09/2026) e SUSEP, SES (SES_ValoresMovRamos). Elaboração própria.")
    st.caption("Diferenças pequenas e persistentes podem vir de datas de extração diferentes (a CNseg usa 28/09/2026) e de reenvios de dados pelas seguradoras.")


def pg_sobre() -> None:
    st.title("Sobre, fontes e limitações")
    st.markdown(f"""
**Objetivo.** Responder, com dados públicos agregados, como evoluíram a arrecadação, os sinistros e a sinistralidade de Automóvel e Patrimonial no Brasil.

**Fontes.**
- CNseg, *Panorama Estatístico: Arrecadação do Mercado Segurador* (planilha de julho/2026). A CNseg compila SUSEP/SES e ANS/DIOPS; extrações de 17/09/2026 (DIOPS) e 28/09/2026 (SES).
- SUSEP, SES (*SES_ValoresMovRamos*, *Ses_ramos*, *Ses_campos*), usado para o detalhe por ramo e para a validação.
- Período: jan/2021 a {mes_fmt(ULT)}.

**Definições (CNseg).** Arrecadação de seguros = prêmio direto (emissão líquida de cancelamento e restituição). Sinistro = sinistro ocorrido de seguros. Sinistralidade = índice divulgado pela CNseg.

**Limitações e cuidados.**
- **Associação não é causa.** Nenhuma análise aqui demonstra por que os valores variam.
- **Valores nominais**, sem desconto de inflação.
- **Dados preliminares.** Os meses mais recentes podem ser revisados pelas seguradoras e pela SUSEP.
- **Sinistralidade da fonte ≠ sinistros ÷ arrecadação.** Exemplo: Automóvel em jan/2026 dá 63,5% pela divisão e 60,6% no índice da CNseg. A diferença deve vir de a fonte usar outra base de prêmio, hipótese não verificada.
- **Total anual da sinistralidade com erro na fonte.** A planilha repete o mesmo valor anual em 2022, 2023 e 2024 nos grupos de Danos; foi desconsiderado e usamos apenas os valores mensais.
- **Comparação com a SUSEP.** Em Danos, os grupos fecham quase no centavo; diferenças residuais podem vir de data de extração e reenvios de dados.
- **Escopo.** Só Automóvel, Patrimonial e Habitacional (Danos). Não cobre Vida, Previdência, Capitalização nem Saúde.
- **Uso dos dados.** Exibidos apenas valores agregados por grupo e ramo, com a origem citada; a autorização formal da CNseg para uso e divulgação foi solicitada por e-mail e ainda aguarda resposta.
""")


{"Visão geral": pg_visao_geral, "Evolução": pg_evolucao, "Sazonalidade e volatilidade": pg_sazonalidade,
 "Sinistralidade e relações": pg_sinistralidade, "Detalhe por ramo (SUSEP)": pg_ramos,
 "Validação CNseg × SUSEP": pg_validacao, "Sobre e limitações": pg_sobre}[pagina]()
