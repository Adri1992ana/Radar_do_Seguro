#!/usr/bin/env python3
"""
Validação cruzada: SUSEP (SES_ValoresMovRamos.csv) x CNseg, usando a aba De_Para_Ramos.

Lê o arquivo grande da SUSEP em blocos, mantém só os campos de prêmio e sinistro de seguros,
agrega por mês e ramo (descarta o código da empresa) e compara com os grupos da CNseg.

Chave do ramo: codigo = gracodigo (2 dígitos) + ramcodigo (2 dígitos) -> 4 dígitos (ex.: 05+31 = 0531).
Campos (cmpid, vindos do Ses_campos.csv, quadros 2 e 6):
    12009 Prêmios Emitidos | 12010 Prêmios de Seguros | 12011 Prêmios Diretos | 12181 Sinistros Ocorridos
A CNseg define arrecadação de seguros como PRÊMIO DIRETO (emissão líquida de cancelamento e restituição);
por isso o script compara os três campos de prêmio e mostra qual fica mais próximo.

Saídas (pasta --saida):
    susep_ramo_mes.csv          mês x ramo x campo (pequeno, pode ir ao repositório se a licença permitir)
    susep_vs_cnseg_item_mes.csv comparação por item da CNseg e mês

Uso:
    python src/susep_validacao.py --movimento dados/original/SES_ValoresMovRamos.csv \
        --de-para dados/processado/de_para_ramos.csv --cnseg dados/processado/cnseg_mensal_longo.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

PREMIOS = {"12009": "Prêmios Emitidos", "12010": "Prêmios de Seguros", "12011": "Prêmios Diretos"}
SINISTROS = {"12181": "Sinistros Ocorridos"}
CMPIDS = {**PREMIOS, **SINISTROS}

# Abertura de "Seguros de Pessoas" da CNseg (Vida / Prestamista / Viagem / Outros Planos de Risco).
# ATENÇÃO: é uma suposição minha a partir dos nomes dos ramos (o De_Para não traz essa abertura).
# Ajuste conforme o resultado da comparação.
PESSOAS_VIDA = {"0991", "0993", "1391", "0996", "1396", "0997"}
PESSOAS_PRESTAMISTA = {"0977", "1377"}
PESSOAS_VIAGEM = {"0969", "1369"}


def ler_movimento(caminho, mes_min):
    usecols = ["damesano", "cmpid", "ramcodigo", "gracodigo", "valor"]
    ultimo_erro = None
    for enc in ("utf-8-sig", "latin-1"):
        try:
            partes = []
            for ch in pd.read_csv(caminho, sep=";", dtype=str, encoding=enc, usecols=usecols, chunksize=500_000):
                ch = ch[ch["cmpid"].str.strip().isin(CMPIDS) & (ch["damesano"].str.strip() >= mes_min)]
                if ch.empty:
                    continue
                ch = ch.assign(
                    valor=ch["valor"].str.strip().str.replace(",", ".", regex=False).astype(float),
                    cmpid=ch["cmpid"].str.strip(),
                    damesano=ch["damesano"].str.strip(),
                    codigo=ch["gracodigo"].str.strip().str.zfill(2) + ch["ramcodigo"].str.strip().str.zfill(2),
                )
                partes.append(ch.groupby(["damesano", "cmpid", "codigo"], as_index=False)["valor"].sum())
            if not partes:
                raise SystemExit("Nenhuma linha encontrada para os campos/períodos pedidos.")
            df = pd.concat(partes).groupby(["damesano", "cmpid", "codigo"], as_index=False)["valor"].sum()
            print(f"Movimento lido (encoding {enc}): {len(df)} linhas agregadas")
            return df
        except UnicodeDecodeError as e:
            ultimo_erro = e
    raise SystemExit(f"Não consegui decodificar o arquivo: {ultimo_erro}")


def item_cnseg(linha, itens_danos):
    if linha.segmento == "Danos e Responsabilidades":
        if linha.grupo1 == "DPVAT":
            return None
        return itens_danos.get(linha.grupo1.casefold(), linha.grupo1)
    if linha.segmento == "Coberturas de Pessoas" and linha.grupo1 == "Seguros de Pessoas":
        if linha.codigo in PESSOAS_VIDA:
            return "Vida"
        if linha.codigo in PESSOAS_PRESTAMISTA:
            return "Prestamista"
        if linha.codigo in PESSOAS_VIAGEM:
            return "Viagem"
        return "Outros Planos de Risco"
    return None  # previdência, capitalização, saúde e DPVAT ficam fora da comparação de seguros


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--movimento", required=True)
    ap.add_argument("--de-para", required=True, dest="de_para")
    ap.add_argument("--cnseg", required=True)
    ap.add_argument("--saida", default="dados/processado")
    ap.add_argument("--mes-min", default="202101", help="AAAAMM inicial (padrão 202101)")
    a = ap.parse_args()

    saida = Path(a.saida)
    saida.mkdir(parents=True, exist_ok=True)

    mov = ler_movimento(a.movimento, a.mes_min)
    dp = pd.read_csv(a.de_para, dtype=str)
    cn = pd.read_csv(a.cnseg, parse_dates=["mes"])

    # cobertura do De_Para
    mov = mov.merge(dp, on="codigo", how="left")
    sem = mov[mov.segmento.isna()]
    tot = mov.groupby("cmpid")["valor"].sum()
    print("\nValor SUSEP sem correspondência no De_Para (% do total por campo):")
    for c, v in sem.groupby("cmpid")["valor"].sum().items():
        print(f"  {c} {CMPIDS[c]}: {v / tot[c]:.2%}")
    if len(sem):
        print("  códigos sem mapeamento (maiores):", sem.groupby("codigo")["valor"].sum().abs().nlargest(8).round(0).to_dict())

    mov["mes"] = pd.to_datetime(mov["damesano"], format="%Y%m")
    ramo_mes = mov.pivot_table(index=["mes", "codigo", "nome_ramo", "segmento", "grupo1", "grupo2"],
                               columns="cmpid", values="valor", aggfunc="sum").reset_index()
    ramo_mes.columns = [f"cmp_{c}" if c in CMPIDS else c for c in ramo_mes.columns]
    ramo_mes.to_csv(saida / "susep_ramo_mes.csv", index=False)

    # comparação por item CNseg
    itens_danos = {i.casefold(): i for i in cn[cn.segmento == "Danos e Responsabilidades"].item.unique()}
    mov["item"] = mov.apply(lambda l: item_cnseg(l, itens_danos) if pd.notna(l.segmento) else None, axis=1)
    susep = mov.dropna(subset=["item"]).groupby(["mes", "item", "cmpid"], as_index=False)["valor"].sum()
    susep["metrica"] = susep.cmpid.map(lambda c: "sinistro" if c in SINISTROS else "arrecadacao")

    base = cn[(cn.tipo_linha == "ramo") & cn.metrica.isin(["arrecadacao", "sinistro"]) &
              cn.segmento.isin(["Danos e Responsabilidades", "Coberturas de Pessoas"]) & cn.valor.notna()]
    base = base[base.item.isin(susep.item.unique())][["mes", "item", "metrica", "valor"]].rename(columns={"valor": "cnseg"})
    comp = susep.merge(base, on=["mes", "item", "metrica"], how="inner").rename(columns={"valor": "susep"})
    comp["dif_pct"] = comp.susep / comp.cnseg - 1
    comp["campo"] = comp.cmpid.map(CMPIDS)
    comp.to_csv(saida / "susep_vs_cnseg_item_mes.csv", index=False)

    resumo = comp.groupby(["mes", "cmpid", "campo"], as_index=False)[["susep", "cnseg"]].sum()
    resumo["dif_pct"] = resumo.susep / resumo.cnseg - 1
    ult = sorted(resumo.mes.unique())[-6:]
    print("\nTotal comparado (Danos + Seguros de Pessoas de risco), últimos 6 meses:")
    print(resumo[resumo.mes.isin(ult)].assign(
        susep_bi=lambda d: (d.susep / 1e9).round(2), cnseg_bi=lambda d: (d.cnseg / 1e9).round(2),
        dif_pct=lambda d: (d.dif_pct * 100).round(1))[["mes", "campo", "susep_bi", "cnseg_bi", "dif_pct"]].to_string(index=False))

    ult_m = ult[-1]
    print(f"\nDiferença por item em {ult_m:%Y-%m} (campo de prêmio mais próximo do total):")
    melhor = resumo[(resumo.mes == ult_m) & resumo.cmpid.isin(PREMIOS)].assign(a=lambda d: d.dif_pct.abs()).nsmallest(1, "a").cmpid.iloc[0]
    print(f"  campo escolhido: {melhor} {CMPIDS[melhor]}")
    print(comp[(comp.mes == ult_m) & (comp.cmpid.isin([melhor, "12181"]))]
          .assign(dif_pct=lambda d: (d.dif_pct * 100).round(1))[["item", "campo", "susep", "cnseg", "dif_pct"]]
          .sort_values(["campo", "cnseg"], ascending=[True, False]).round(0).to_string(index=False))


if __name__ == "__main__":
    main()