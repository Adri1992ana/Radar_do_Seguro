"""
Funções de análise (EDA e estatística descritiva) usadas pelo app Streamlit e reutilizáveis em notebooks.

Todas trabalham sobre a tabela longa mensal gerada por src/transform_cnseg.py
(colunas: mes, item, metrica, valor, ...). Valores em R$; sinistralidade em razão (0,60 = 60%).

Escolhas metodológicas (resumo; detalhes no README):
- Variação a/a compara cada mês com o mesmo mês do ano anterior (neutraliza a sazonalidade).
- Acumulado de 12 meses suaviza a sazonalidade para ver a tendência.
- Índice sazonal = valor do mês / média do ano, calculado só em anos completos e depois
  promediado entre os anos (método simples; não separa a tendência de crescimento).
- Outliers por escore z robusto (mediana e MAD), que não é distorcido pelos próprios outliers.
- Correlação entre variações a/a (e não entre níveis), para não confundir tendência comum com relação.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

ITENS_DANOS = ["Automóvel", "Patrimonial", "Habitacional"]
SUBTOTAL_DANOS = "Subtotal Danos e Responsabilidades"
MESES_PT = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]


def _aa(s: pd.Series) -> pd.Series:
    """Variação contra o mesmo mês do ano anterior. Evita pct_change, cujo preenchimento de lacunas muda entre versões do pandas."""
    s = s.asfreq("MS")
    return s / s.shift(12) - 1


# ----------------------------------------------------------------------------- séries básicas
def carregar_mensal(caminho) -> pd.DataFrame:
    df = pd.read_csv(caminho, parse_dates=["mes"])
    return df.sort_values(["metrica", "item", "mes"]).reset_index(drop=True)


def serie(df: pd.DataFrame, item: str, metrica: str) -> pd.Series:
    """Série mensal (índice = primeiro dia do mês) sem meses vazios, com frequência mensal explícita."""
    d = df[(df["item"] == item) & (df["metrica"] == metrica)].dropna(subset=["valor"])
    s = d.set_index("mes")["valor"].sort_index()
    return s.asfreq("MS") if len(s) else s


def ultimo_mes(df: pd.DataFrame) -> pd.Timestamp:
    d = df[(df["metrica"] == "arrecadacao") & df["valor"].notna()]
    return d["mes"].max()


# ----------------------------------------------------------------------------- variações e acumulados
def var_aa(s: pd.Series, mes: pd.Timestamp) -> float:
    """Variação do mês contra o mesmo mês do ano anterior."""
    ant = mes - pd.DateOffset(years=1)
    if mes in s.index and ant in s.index and pd.notna(s[mes]) and pd.notna(s[ant]) and s[ant] != 0:
        return float(s[mes] / s[ant] - 1)
    return float("nan")


def soma_janela(s: pd.Series, fim: pd.Timestamp, meses: int = 12) -> float:
    """Soma dos `meses` meses que terminam em `fim` (exige a janela completa)."""
    idx = pd.date_range(end=fim, periods=meses, freq="MS")
    v = s.reindex(idx)
    return float(v.sum()) if v.notna().all() else float("nan")


def var_12m(s: pd.Series, fim: pd.Timestamp) -> float:
    """Acumulado de 12 meses contra os 12 meses imediatamente anteriores."""
    atual = soma_janela(s, fim, 12)
    anterior = soma_janela(s, fim - pd.DateOffset(years=1), 12)
    return atual / anterior - 1 if np.isfinite(atual) and np.isfinite(anterior) and anterior != 0 else float("nan")


def acumulado_ano(s: pd.Series, ano: int, ate_mes: int) -> float:
    idx = pd.date_range(f"{ano}-01-01", periods=ate_mes, freq="MS")
    v = s.reindex(idx)
    return float(v.sum()) if v.notna().all() else float("nan")


def var_acumulado_ano(s: pd.Series, ano: int, ate_mes: int) -> float:
    a, b = acumulado_ano(s, ano, ate_mes), acumulado_ano(s, ano - 1, ate_mes)
    return a / b - 1 if np.isfinite(a) and np.isfinite(b) and b != 0 else float("nan")


def acumulado_12m_serie(s: pd.Series) -> pd.Series:
    return s.asfreq("MS").rolling(12).sum().dropna()


def totais_anuais(s: pd.Series, ultimo: pd.Timestamp) -> pd.DataFrame:
    """Total por ano calendário; o último ano é parcial e sua variação compara os mesmos meses do ano anterior."""
    linhas = []
    for ano in sorted(set(s.dropna().index.year)):
        n = int(s[(s.index.year == ano)].notna().sum())
        parcial = ano == ultimo.year and ultimo.month < 12
        ate = ultimo.month if parcial else 12
        total = acumulado_ano(s, ano, ate)
        linhas.append({"ano": ano, "meses": ate, "parcial": parcial, "total": total,
                       "var_aa": var_acumulado_ano(s, ano, ate), "n_obs": n})
    return pd.DataFrame(linhas)


def cagr(s: pd.Series, ano_ini: int, ano_fim: int) -> float:
    """Taxa composta de crescimento anual entre dois anos COMPLETOS."""
    a, b = acumulado_ano(s, ano_ini, 12), acumulado_ano(s, ano_fim, 12)
    n = ano_fim - ano_ini
    return (b / a) ** (1 / n) - 1 if np.isfinite(a) and np.isfinite(b) and a > 0 and b > 0 and n > 0 else float("nan")


# ----------------------------------------------------------------------------- sazonalidade e volatilidade
def anos_completos(s: pd.Series) -> list[int]:
    cont = s.dropna().groupby(s.dropna().index.year).size()
    return [int(a) for a, n in cont.items() if n == 12]


def indice_sazonal(s: pd.Series) -> pd.Series:
    """Índice por mês (1..12); 1,00 = média do ano. Usa só anos completos."""
    anos = anos_completos(s)
    d = s[s.index.year.isin(anos)].dropna()
    if d.empty:
        return pd.Series(dtype=float)
    razao = d / d.groupby(d.index.year).transform("mean")
    return razao.groupby(razao.index.month).mean()


def matriz_mes_ano(s: pd.Series) -> pd.DataFrame:
    d = s.dropna()
    return d.groupby([d.index.year, d.index.month]).sum().unstack(1).reindex(columns=range(1, 13))


def volatilidade(s: pd.Series, janela: int = 24) -> dict:
    """CV dos últimos `janela` meses e desvio-padrão da variação a/a mensal (em pontos percentuais)."""
    d = s.dropna()
    ult = d.iloc[-janela:]
    cv = float(ult.std(ddof=1) / ult.mean()) if len(ult) >= 12 and ult.mean() != 0 else float("nan")
    yoy = _aa(s).replace([np.inf, -np.inf], np.nan).dropna()
    return {"cv": cv, "dp_aa_pp": float(yoy.std(ddof=1) * 100) if len(yoy) >= 12 else float("nan"), "n_aa": int(len(yoy))}


# ----------------------------------------------------------------------------- tendência, outliers, relações
def tendencia_linear(s: pd.Series) -> dict:
    """Regressão linear simples do valor contra o tempo (meses). Indica direção, não prevê nem explica."""
    d = s.dropna()
    if len(d) < 12:
        return {"inclinacao_mes": np.nan, "r2": np.nan, "p": np.nan, "n": len(d)}
    x = np.arange(len(d))
    r = stats.linregress(x, d.values)
    return {"inclinacao_mes": float(r.slope), "r2": float(r.rvalue ** 2), "p": float(r.pvalue), "n": int(len(d))}


def outliers_mad(s: pd.Series, limiar: float = 3.5) -> pd.DataFrame:
    """Escore z robusto: 0,6745*(x - mediana)/MAD. |z| > 3,5 é o corte usual (Iglewicz e Hoaglin)."""
    d = s.dropna()
    if len(d) < 12:
        return pd.DataFrame(columns=["mes", "valor", "z_robusto"])
    med = d.median()
    mad = (d - med).abs().median()
    if mad == 0:
        return pd.DataFrame(columns=["mes", "valor", "z_robusto"])
    z = 0.6745 * (d - med) / mad
    out = pd.DataFrame({"mes": d.index, "valor": d.values, "z_robusto": z.values})
    return out[out["z_robusto"].abs() > limiar].sort_values("z_robusto", key=np.abs, ascending=False).reset_index(drop=True)


def correlacao_aa(arrecadacao: pd.Series, sinistro: pd.Series) -> dict:
    """Correlação entre as variações a/a mensais de arrecadação e de sinistros (Pearson e Spearman)."""
    a = _aa(arrecadacao)
    b = _aa(sinistro)
    d = pd.concat([a, b], axis=1, keys=["arrecadacao", "sinistro"]).replace([np.inf, -np.inf], np.nan).dropna()
    if len(d) < 12:
        return {"n": len(d), "pearson": np.nan, "p_pearson": np.nan, "spearman": np.nan, "p_spearman": np.nan, "dados": d}
    pr = stats.pearsonr(d["arrecadacao"], d["sinistro"])
    sr = stats.spearmanr(d["arrecadacao"], d["sinistro"])
    return {"n": int(len(d)), "pearson": float(pr[0]), "p_pearson": float(pr[1]),
            "spearman": float(sr[0]), "p_spearman": float(sr[1]), "dados": d}


def participacao_12m(df: pd.DataFrame, item: str, metrica: str, fim: pd.Timestamp, total: str = SUBTOTAL_DANOS) -> float:
    a = soma_janela(serie(df, item, metrica), fim, 12)
    t = soma_janela(serie(df, total, metrica), fim, 12)
    return a / t if np.isfinite(a) and np.isfinite(t) and t != 0 else float("nan")
