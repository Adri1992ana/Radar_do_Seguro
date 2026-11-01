#!/usr/bin/env python3
"""
ETL da planilha "Arrecadação do Mercado Segurador" (CNseg - Panorama Estatístico).

Entrada : xlsx baixado da CNseg (abas Arrecadação, Sinistros, Sinistralidade, De_Para_Ramos)
Saída   : dados/processado/
            cnseg_mensal_longo.csv   tabela longa mensal (uma linha por mês x item x métrica)
            cnseg_anual.csv          totais anuais da fonte (2026 = parcial)
            de_para_ramos.csv        código SUSEP (4 dígitos) -> segmento/grupo CNseg
            qa_checks.csv            conferências de consistência (ok = True/False)

Decisões de limpeza (todas registradas na coluna `observacao` ou no qa_checks.csv):
  1. Calendário reconstruído por POSIÇÃO: 12 meses + 1 coluna de total anual por ano.
     (as datas do cabeçalho da fonte derivam de 1 a 8 dias e não são confiáveis).
  2. Colunas de total anual são separadas das mensais (evita dupla contagem).
  3. Meses sem dados na fonte (zeros após o último mês publicado) viram NaN.
  4. Saúde Suplementar (ANS) é trimestral: meses fora de mar/jun/set/dez viram NaN.
  5. Aba Sinistralidade mistura razão (%) e R$ (captação líquida): separadas em
     metrica = "sinistralidade" (unidade razao) e "captacao_liquida" (unidade R$).
  6. Subtotal de Capitalização (captação líquida) divergente da soma dos itens é
     recalculado; o valor original é mantido em `valor_original`.
  7. Linha DPVAT da aba Sinistralidade repete a aba Sinistros: descartada (checado no QA).

Uso:
    python src/transform_cnseg.py --xlsx dados/original/Planilha_para_o_site_jul_2026_valores.xlsx
"""
from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

import numpy as np
import openpyxl
import pandas as pd

ABAS = {"Arrecadação": "arrecadacao", "Sinistros": "sinistro", "Sinistralidade": "sinistralidade"}
SEGMENTOS = {"Danos e Responsabilidades", "Coberturas de Pessoas", "Capitalização", "Saúde Suplementar"}
TOTAIS = {
    "Mercado Segurador": "total_mercado",
    "Mercado Segurador (sem Saúde)": "total_mercado_sem_saude",
    "DPVAT": "dpvat",
}
PRIMEIRA_LINHA_DADOS = 9   # 1-indexado
LINHA_CABECALHO = 7        # 1-indexado
COL_VALOR_INICIO = 3       # 0-indexado (A=0, B=1, C=2, D=3)
TOL_REAIS = 1.0            # tolerância (R$) nas conferências de soma


def _txt(v):
    return v.strip() if isinstance(v, str) and v.strip() else None


def construir_calendario(cabecalho):
    """Devolve [(indice_coluna, 'mensal'|'anual', ano, mes|None)] por posição."""
    cols, ano, mes = [], None, 1
    for j in range(COL_VALOR_INICIO, len(cabecalho)):
        v = cabecalho[j]
        if v is None:
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if ano is None or int(v) != ano or mes != 13:
                raise ValueError(f"Coluna anual inesperada na posição {j}: {v} (ano esperado {ano}, mes {mes})")
            cols.append((j, "anual", ano, None))
            ano_prox = ano + 1
            ano, mes = ano_prox, 1
        else:
            if ano is None:
                ano = v.year
            if v.year != ano:
                raise ValueError(f"Ano do cabeçalho ({v.year}) difere do esperado ({ano}) na coluna {j}")
            cols.append((j, "mensal", ano, mes))
            mes += 1
    return cols


def eh_razao(segmento, grupo, item):
    return segmento == "Danos e Responsabilidades" or grupo == "Seguros de Pessoas" or item == "Planos Tradicionais"


def ler_aba(ws, metrica_aba, calendario):
    linhas = list(ws.iter_rows(values_only=True))
    seg, grupo, registros = None, None, []
    for r in linhas[PRIMEIRA_LINHA_DADOS - 1:]:
        c0, c1, c2 = (_txt(r[i]) if i < len(r) else None for i in range(3))
        if c0 and c0.startswith("Fontes"):
            break
        if not (c0 or c1 or c2):
            continue

        if c0 in SEGMENTOS:
            seg, grupo = c0, None
            tipo, segmento_linha = "ramo", seg
        elif c0 == "Subtotal":
            tipo, segmento_linha = "subtotal", seg
        elif c0 in TOTAIS:
            tipo, segmento_linha, seg, grupo = TOTAIS[c0], ("DPVAT" if c0 == "DPVAT" else "Mercado Segurador"), None, None
        else:
            tipo, segmento_linha = "ramo", seg

        if tipo == "ramo":
            if c1:
                grupo = c1
            item = c2 or grupo
            grupo_linha = grupo or item
        elif tipo == "subtotal":
            item, grupo_linha = f"Subtotal {segmento_linha}", f"Subtotal {segmento_linha}"
        else:
            item, grupo_linha = c0, c0

        if metrica_aba == "sinistralidade":
            if tipo == "ramo" or tipo == "subtotal" and segmento_linha == "Danos e Responsabilidades":
                razao = eh_razao(segmento_linha, grupo_linha, item)
            else:
                razao = False
            metrica, unidade = ("sinistralidade", "razao") if razao else ("captacao_liquida", "R$")
        else:
            metrica, unidade = metrica_aba, "R$"

        for j, per, ano, mes in calendario:
            v = r[j] if j < len(r) else None
            registros.append({
                "segmento": segmento_linha, "grupo": grupo_linha, "item": item, "tipo_linha": tipo,
                "metrica": metrica, "unidade": unidade, "periodo_tipo": per, "ano": ano, "mes_num": mes,
                "valor_original": float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else np.nan,
            })
    return pd.DataFrame(registros)


def ler_de_para(wb):
    rows = list(wb["De_Para_Ramos"].iter_rows(values_only=True))
    h = col0 = None
    for i, r in enumerate(rows):
        for k, c in enumerate(r):
            if _txt(c) == "SEGMENTO":
                h, col0 = i, k
                break
        if h is not None:
            break
    if h is None:
        raise ValueError("Cabeçalho SEGMENTO não encontrado na aba De_Para_Ramos")
    out = []
    for r in rows[h + 1:]:
        campos = [_txt(r[col0 + k]) if col0 + k < len(r) else None for k in range(4)]
        seg, g1, g2, ramo = campos
        if not ramo:
            continue
        m = re.match(r"^(\d{4})\s*-\s*(.*)$", html.unescape(ramo))
        if not m:
            continue
        out.append({"codigo": m.group(1), "nome_ramo": m.group(2).strip(), "segmento": seg, "grupo1": g1, "grupo2": g2})
    df = pd.DataFrame(out)
    df = df.drop_duplicates(subset=["codigo", "segmento", "grupo1", "grupo2"], keep="first")
    conflitos = df[df.duplicated("codigo", keep=False)]
    if len(conflitos):
        print("ATENÇÃO: códigos com mais de um mapeamento no De_Para:\n", conflitos.to_string())
        df = df.drop_duplicates("codigo", keep="first")
    return df.reset_index(drop=True)


def limpar(df):
    obs = pd.Series("", index=df.index)
    df["valor"] = df["valor_original"]

    # último mês publicado = último mês com total do mercado (sem saúde) diferente de zero
    ref = df[(df.metrica == "arrecadacao") & (df.tipo_linha == "total_mercado_sem_saude") & (df.periodo_tipo == "mensal")]
    ref = ref[ref.valor_original.fillna(0) != 0]
    ult = (ref.ano * 100 + ref.mes_num).max()
    ult_ano, ult_mes = divmod(int(ult), 100)

    mensal = df.periodo_tipo == "mensal"
    futuro = mensal & ((df.ano * 100 + df.mes_num.fillna(0)) > ult)
    df.loc[futuro, "valor"] = np.nan
    obs[futuro] = "mês sem dados na fonte (zero na planilha)"

    saude = mensal & (df.segmento == "Saúde Suplementar") & (~df.mes_num.isin([3, 6, 9, 12])) & ~futuro
    df.loc[saude, "valor"] = np.nan
    obs[saude] = "Saúde (ANS) é trimestral: valor alocado só em mar/jun/set/dez"

    df["periodicidade"] = np.where(df.segmento == "Saúde Suplementar", "trimestral", "mensal")
    df["mes"] = pd.to_datetime(dict(year=df.ano, month=df.mes_num.fillna(1).astype(int), day=1)).where(mensal)
    df["observacao"] = obs
    return df, (ult_ano, ult_mes)


def corrigir_subtotal_capitalizacao(df):
    """Recalcula o subtotal de captação líquida de Capitalização quando diverge da soma dos itens."""
    base = (df.periodo_tipo == "mensal") & (df.metrica == "captacao_liquida") & (df.segmento == "Capitalização")
    itens = df[base & (df.tipo_linha == "ramo")].groupby(["ano", "mes_num"])["valor_original"].sum()
    sub = base & (df.tipo_linha == "subtotal") & df.valor.notna()
    idx = df[sub].index
    n = 0
    for i in idx:
        soma = itens.get((df.at[i, "ano"], df.at[i, "mes_num"]))
        if soma is not None and abs(df.at[i, "valor_original"] - soma) > TOL_REAIS:
            df.at[i, "valor"] = soma
            df.at[i, "observacao"] = "subtotal da fonte divergente da soma dos itens: recalculado"
            n += 1
    return n


def conferencias(df):
    qa = []

    def add(check, ref, mes, esperado, obtido):
        d = obtido - esperado
        qa.append({"check": check, "referencia": ref, "mes": mes, "esperado": esperado, "obtido": obtido,
                   "diferenca": d, "ok": bool(abs(d) <= TOL_REAIS)})

    m = df[(df.periodo_tipo == "mensal") & df.valor.notna()]
    anu = df[df.periodo_tipo == "anual"]
    chave = ["segmento", "grupo", "item", "tipo_linha", "metrica"]

    # 1) soma dos meses = total anual da fonte (apenas métricas em R$)
    mr = m[m.unidade == "R$"].groupby(chave + ["ano"])["valor"].sum().rename("soma_meses")
    ar = anu[anu.unidade == "R$"].set_index(chave + ["ano"])["valor_original"].rename("anual")
    j = pd.concat([mr, ar], axis=1).dropna()
    for k, row in j.iterrows():
        add("soma_meses_vs_anual", " | ".join(map(str, k[:3])) + f" | {k[4]} | {k[5]}", None, row["anual"], row["soma_meses"])

    # 2) subtotal da fonte = soma dos itens (usa valores originais)
    for (seg, met, ano, mes), g in m[m.metrica != "sinistralidade"].groupby(["segmento", "metrica", "ano", "mes_num"]):
        sub = g[g.tipo_linha == "subtotal"]
        if len(sub):
            add("subtotal_vs_itens", f"{seg} | {met}", f"{ano}-{int(mes):02d}",
                g[g.tipo_linha == "ramo"]["valor_original"].sum(), sub["valor_original"].iloc[0])

    # 3) total sem saúde = Danos + Pessoas + Capitalização ; total = sem saúde + Saúde
    for met in ["arrecadacao", "sinistro"]:
        for (ano, mes), g in m[m.metrica == met].groupby(["ano", "mes_num"]):
            sub = g[g.tipo_linha == "subtotal"].set_index("segmento")["valor_original"]
            ts = g[g.tipo_linha == "total_mercado_sem_saude"]["valor_original"]
            tt = g[g.tipo_linha == "total_mercado"]["valor_original"]
            partes = sum(sub.get(s, 0.0) for s in ["Danos e Responsabilidades", "Coberturas de Pessoas", "Capitalização"])
            if len(ts):
                add("total_sem_saude_vs_subtotais", met, f"{ano}-{int(mes):02d}", partes, ts.iloc[0])
            if len(ts) and len(tt):
                add("total_vs_sem_saude_mais_saude", met, f"{ano}-{int(mes):02d}", ts.iloc[0] + sub.get("Saúde Suplementar", 0.0), tt.iloc[0])
    return pd.DataFrame(qa)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--xlsx", required=True, help="caminho do xlsx da CNseg")
    ap.add_argument("--saida", default="dados/processado", help="pasta de saída")
    a = ap.parse_args()

    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)
    wb = openpyxl.load_workbook(a.xlsx, data_only=True)

    partes = []
    for nome, metrica in ABAS.items():
        ws = wb[nome]
        cab = list(ws.iter_rows(min_row=LINHA_CABECALHO, max_row=LINHA_CABECALHO, values_only=True))[0]
        cal = construir_calendario(cab)
        d = ler_aba(ws, metrica, cal)
        d["aba"] = nome
        partes.append(d)
        print(f"{nome}: {len(cal)} colunas de período ({sum(c[1]=='mensal' for c in cal)} mensais), {len(d)} registros")
    df = pd.concat(partes, ignore_index=True)

    # DPVAT da aba Sinistralidade: conferir e descartar
    dp_sin = df[(df.aba == "Sinistralidade") & (df.tipo_linha == "dpvat")].set_index(["ano", "mes_num"])["valor_original"]
    dp_ref = df[(df.aba == "Sinistros") & (df.tipo_linha == "dpvat")].set_index(["ano", "mes_num"])["valor_original"]
    iguais = np.allclose(dp_sin.fillna(0).values, dp_ref.reindex(dp_sin.index).fillna(0).values)
    print(f"DPVAT (Sinistralidade) idêntico ao de Sinistros: {iguais} -> linha descartada")
    df = df[~((df.aba == "Sinistralidade") & (df.tipo_linha == "dpvat"))].reset_index(drop=True)

    df, (ua, um) = limpar(df)
    print(f"Último mês publicado na fonte: {ua}-{um:02d}")
    n = corrigir_subtotal_capitalizacao(df)
    print(f"Subtotais de Capitalização (captação líquida) recalculados: {n} meses")

    qa = conferencias(df)
    falhas = qa[~qa.ok]
    print(f"Conferências: {len(qa)} | falhas: {len(falhas)}")
    if len(falhas):
        print(falhas.groupby(["check", "referencia"]).size().to_string())

    cols = ["mes", "ano", "mes_num", "segmento", "grupo", "item", "tipo_linha", "metrica", "unidade",
            "periodicidade", "valor", "valor_original", "observacao"]
    mensal = df[df.periodo_tipo == "mensal"][cols].sort_values(["metrica", "segmento", "grupo", "item", "mes"])
    anual = df[df.periodo_tipo == "anual"].copy()
    anual["ano_parcial"] = anual.ano == ua
    anual["meses_com_dado"] = np.where(anual.ano == ua, um, 12)
    anual = anual[["ano", "ano_parcial", "meses_com_dado", "segmento", "grupo", "item", "tipo_linha", "metrica",
                   "unidade", "valor_original"]].rename(columns={"valor_original": "valor"})
    anual["valor_original"] = anual["valor"]
    anual["observacao"] = ""
    # Erro da fonte: sinistralidade anual repetida de um ano para o outro (ex.: Danos 2022 = 2023 = 2024)
    anual = anual.sort_values(["segmento", "grupo", "item", "tipo_linha", "metrica", "ano"])
    anterior = anual.groupby(["segmento", "grupo", "item", "tipo_linha", "metrica"])["valor"].shift(1)
    repetido = (anual.metrica == "sinistralidade") & anterior.notna() & ((anual.valor - anterior).abs() < 1e-12)
    anual.loc[repetido, "valor"] = np.nan
    anual.loc[repetido, "observacao"] = "sinistralidade anual da fonte repete o ano anterior (erro de origem): anulada"
    print(f"Sinistralidade anual repetida pela fonte e anulada: {int(repetido.sum())} valores")

    mensal.to_csv(saida / "cnseg_mensal_longo.csv", index=False)
    anual.to_csv(saida / "cnseg_anual.csv", index=False)
    qa.to_csv(saida / "qa_checks.csv", index=False)
    de_para = ler_de_para(wb)
    de_para.to_csv(saida / "de_para_ramos.csv", index=False)  # ao ler: pd.read_csv(..., dtype=str) para manter zeros à esquerda
    print(f"Arquivos gravados em {saida.resolve()}: mensal={len(mensal)} linhas, anual={len(anual)}, de_para={len(de_para)} ramos")


if __name__ == "__main__":
    main()