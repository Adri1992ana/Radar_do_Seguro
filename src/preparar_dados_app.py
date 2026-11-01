#!/usr/bin/env python3
"""
Gera os arquivos MÍNIMOS que o app Streamlit lê (pasta dados/app/), a partir de dados/processado/.

Princípio de minimização (PDF, seção 4.4): o app só recebe valores agregados dos três grupos do escopo
(Automóvel, Patrimonial, Habitacional) e o subtotal de Danos; nada de empresas, nem planilha original.

Entradas (dados/processado/):
    cnseg_mensal_longo.csv          obrigatório (gerado por transform_cnseg.py)
    susep_ramo_mes.csv              opcional (gerado por susep_validacao.py)
    susep_vs_cnseg_item_mes.csv     opcional (gerado por susep_validacao.py)
Saídas (dados/app/):
    cnseg_danos_mensal.csv
    susep_danos_ramo_mes.csv        (somente se a entrada existir)
    susep_vs_cnseg_danos.csv        (somente se a entrada existir)

Uso:
    python src/preparar_dados_app.py
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

ITENS = ["Automóvel", "Patrimonial", "Habitacional", "Subtotal Danos e Responsabilidades"]
GRUPOS_SUSEP = ["Automóvel", "Patrimonial", "Habitacional"]
CAMPOS = {"cmp_12011": "Prêmios Diretos", "cmp_12181": "Sinistros Ocorridos"}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entrada", default="dados/processado")
    ap.add_argument("--saida", default="dados/app")
    a = ap.parse_args()
    ent, sai = Path(a.entrada), Path(a.saida)
    sai.mkdir(parents=True, exist_ok=True)

    cn = pd.read_csv(ent / "cnseg_mensal_longo.csv", parse_dates=["mes"])
    cn = cn[(cn.segmento == "Danos e Responsabilidades") & cn.item.isin(ITENS) & cn.metrica.isin(["arrecadacao", "sinistro", "sinistralidade"])]
    cn = cn[["mes", "item", "metrica", "unidade", "valor"]].dropna(subset=["valor"])
    cn.to_csv(sai / "cnseg_danos_mensal.csv", index=False)
    print(f"cnseg_danos_mensal.csv: {len(cn)} linhas | {cn.mes.min():%Y-%m} a {cn.mes.max():%Y-%m}")

    f = ent / "susep_ramo_mes.csv"
    if f.exists():
        rm = pd.read_csv(f, dtype={"codigo": str}, parse_dates=["mes"])
        rm = rm[(rm.segmento == "Danos e Responsabilidades") & rm.grupo1.isin(GRUPOS_SUSEP)]
        cols = ["mes", "codigo", "nome_ramo", "grupo1", "grupo2"] + [c for c in CAMPOS if c in rm.columns]
        rm[cols].to_csv(sai / "susep_danos_ramo_mes.csv", index=False)
        print(f"susep_danos_ramo_mes.csv: {len(rm)} linhas")
    else:
        print(f"AVISO: {f} não existe; a página de detalhe por ramo ficará indisponível no app.")

    f = ent / "susep_vs_cnseg_item_mes.csv"
    if f.exists():
        v = pd.read_csv(f, parse_dates=["mes"])
        v = v[v.item.isin(GRUPOS_SUSEP) & v.campo.isin(CAMPOS.values())]
        v = v[v.cmpid.astype(str).isin(["12011", "12181"])]
        v[["mes", "item", "metrica", "campo", "susep", "cnseg", "dif_pct"]].to_csv(sai / "susep_vs_cnseg_danos.csv", index=False)
        print(f"susep_vs_cnseg_danos.csv: {len(v)} linhas")
    else:
        print(f"AVISO: {f} não existe; a página de validação ficará indisponível no app.")


if __name__ == "__main__":
    main()