# Radar do Seguro: Automóvel e Patrimonial

Análise de dados com Python e aplicação de BI em Streamlit sobre a **arrecadação, os sinistros e a sinistralidade dos seguros de Automóvel e Patrimonial** no Brasil, de janeiro de 2021 a julho de 2026.

Projeto final individual de *Visualização de Dados e BI [T1]* (Módulo 2, Semana 13), SENAI Santa Catarina / LAB365. Autora: ADRIANA SILVA DIAS DE SOUZA.

> **Aplicação publicada:** [radardoseguro.streamlit.app](https://radardoseguro.streamlit.app/)

---

## 1. Título e resumo

O projeto obtém a planilha pública de arrecadação do mercado segurador da CNseg, trata e valida os dados com Python (ETL), calcula estatísticas descritivas (crescimento, sazonalidade, volatilidade, tendência, valores atípicos e correlação) e as apresenta em um app interativo. Para o detalhe por ramo e para conferir a fonte, usa os dados primários da SUSEP.

## 2. Problema, objetivo e importância

**Pergunta:** como evoluíram a arrecadação, os sinistros e a sinistralidade de Automóvel e Patrimonial (grupo *Danos e Responsabilidades*) entre jan/2021 e jul/2026, e como se comportam a sazonalidade e a volatilidade de cada um?

**Para quem:** corretores, analistas de mercado e estudantes de seguros, que precisam de uma leitura rápida e conferível do segmento.

**Por que importa:** Danos e Responsabilidades somou R$ 148,2 bi nos 12 meses até jul/2026. Automóvel responde por 43,0% desse valor e Patrimonial por 21,9%. Entender o ritmo de crescimento e a relação entre prêmio e sinistro ajuda a planejar carteira, metas e preços.

## 3. Escopo e resultados esperados

**Dentro do escopo:** Automóvel e Patrimonial (Habitacional como contexto opcional); valores nominais mensais de arrecadação (prêmio direto) e sinistros ocorridos; sinistralidade divulgada pela CNseg; detalhe por ramo via SUSEP (por exemplo, Compreensivo Residencial, Condomínio e Empresarial em Patrimonial).

**Fora do escopo:** Vida, Previdência, Capitalização e Saúde Suplementar; análise por seguradora; projeções; qualquer afirmação de causalidade; valores reais (descontados da inflação).

**Entregas:** ETL reproduzível, EDA e estatísticas, app Streamlit com filtros e avisos, validação cruzada entre as duas fontes, este README.

**Critério de conclusão:** responder à pergunta com números conferíveis, registrar as decisões de limpeza e declarar as limitações.

## 4. Fonte e autorização

| Item                                           | Detalhe                                                                                                                                                                                                                                                                                                                                                 |
| ---------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Fonte principal                                | CNseg, *Panorama Estatístico: Arrecadação do Mercado Segurador* (planilha de julho/2026). https://casadoseguro.cnseg.org.br/mais-conteudos/analises-e-estatisticas/panorama-estatistico                                                                                                                                                            |
| Origem primária (segundo a própria planilha) | SES/SUSEP (extração de 28/09/2026) e DIOPS/ANS (extração de 17/09/2026)                                                                                                                                                                                                                                                                             |
| Fonte complementar                             | SUSEP, SES: arquivos `SES_ValoresMovRamos.csv`, `Ses_ramos.csv` e `Ses_campos.csv` (pacote `BaseCompleta.zip`, baixados em 27/10/2026). [inserir URL exata do portal da SUSEP]                                                                                                                                                                  |
| Período                                       | Jan/2021 a jul/2026 (último mês publicado na planilha)                                                                                                                                                                                                                                                                                                |
| Método de captura                             | Download manual dos arquivos públicos, sem scraping e sem API. A página da CNseg carrega a lista de arquivos por JavaScript. [inserir data do download da planilha]                                                                                                                                                                                   |
| Campos usados (CNseg)                          | Abas *Arrecadação*, *Sinistros*, *Sinistralidade* e *De_Para_Ramos*; linhas Automóvel, Patrimonial, Habitacional e subtotal de Danos                                                                                                                                                                                                         |
| Campos usados (SUSEP)                          | `cmpid` 12011 (Prêmios Diretos) e 12181 (Sinistros Ocorridos); chave de ramo = `gracodigo` + `ramcodigo` (4 dígitos)                                                                                                                                                                                                                            |
| Dados pessoais                                 | Nenhum. Todos os dados são valores agregados do setor. O código da empresa (`coenti`) é descartado no ETL.                                                                                                                                                                                                                                         |
| Licença e termos                              | A página da CNseg não traz termos de uso, licença ou regra de citação que eu tenha encontrado. **Autorização solicitada por e-mail à CNseg em 31/10/2026; aguardando resposta.** Enquanto isso, o repositório é privado, os arquivos originais não são versionados e o app exibe apenas valores agregados, sempre com a fonte citada. |

## 5. Pipeline e metodologia

```
Planilha CNseg (.xlsx)  ──►  transform_cnseg.py  ──►  dados/processado/cnseg_mensal_longo.csv
SES_ValoresMovRamos.csv ──►  susep_validacao.py  ──►  dados/processado/susep_*.csv
                                  │
                       preparar_dados_app.py  ──►  dados/app/*.csv (mínimo para o app)
                                  │
                       analysis.py + app.py   ──►  Streamlit
```

**Extração.** Leitura das quatro abas da planilha com `openpyxl`. O arquivo da SUSEP (cerca de 550 MB) é lido em blocos com `pandas` (`chunksize`), filtrando só os campos e meses necessários.

**Transformação (decisões de limpeza).** O ETL registra o que foi feito em `observacao` e em `qa_checks.csv`:

| Problema encontrado na fonte                                                                                                   | Decisão                                                                             |
| ------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------ |
| Datas do cabeçalho derivam de 1 a 8 dias (ex.: `2021-10-02`)                                                                | Calendário reconstruído por posição (12 meses + 1 coluna de total anual por ano) |
| Colunas de total anual misturadas com as mensais                                                                               | Separadas em tabela anual própria, para evitar dupla contagem                       |
| Meses futuros (ago a dez/2026) aparecem como 0                                                                                 | Convertidos para vazio (NaN)                                                         |
| Sinistralidade **anual** de Danos repete o mesmo valor em 2022, 2023 e 2024 (erro de origem)                             | 20 valores anulados; o app usa apenas a série mensal                                |
| Aba *Sinistralidade* mistura razão (%) e valores em R$ | Separados em `sinistralidade` (razão) e `captacao_liquida` (R$) |                                                                                      |
| Subtotal de Capitalização (captação líquida) de abr a jul/2026 repete o de Sinistros                                      | Recalculado pela soma dos itens (fora do escopo do app, mas registrado)              |
| Linha DPVAT da aba *Sinistralidade* idêntica à da aba *Sinistros*                                                        | Descartada                                                                           |
| Saúde Suplementar (ANS) é trimestral, com zeros nos outros meses                                                             | Zeros viram vazio fora de mar/jun/set/dez (fora do escopo do app)                    |

**Conferências automáticas:** 1.231 testes (soma dos meses contra o total anual da fonte, itens contra subtotal, total do mercado contra segmentos). Falharam 4, todos no subtotal de Capitalização acima, já corrigidos.

**Carregamento.** `preparar_dados_app.py` grava em `dados/app/` somente o necessário (princípio de minimização): três grupos de Danos, métricas mensais e os ramos da SUSEP correspondentes.

**Estatística (`src/analysis.py`).**

| Medida                               | Método e por quê                                                                                                                                  |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| Variação a/a                       | Compara o mês com o mesmo mês do ano anterior; neutraliza a sazonalidade                                                                          |
| Acumulado de 12 meses                | Soma móvel; deixa a tendência visível                                                                                                            |
| CAGR 2021-2025                       | Só anos completos, valores nominais                                                                                                                |
| Índice sazonal                      | Valor do mês ÷ média do ano, promediado nos anos completos. Método simples; não separa o crescimento ao longo do ano                           |
| Volatilidade                         | Coeficiente de variação dos últimos 24 meses e desvio-padrão da variação a/a                                                                  |
| Tendência                           | Regressão linear simples (`scipy.stats.linregress`); descreve a direção, não prevê                                                           |
| Valores atípicos                    | Escore z robusto (mediana e MAD), corte de 3,5                                                                                                      |
| Relação arrecadação × sinistros | Correlação de Pearson e de Spearman entre as **variações a/a** (e não entre níveis, para não confundir tendência comum com relação) |

## 6. Bibliotecas e tecnologias

| Biblioteca                                  | Função no projeto                                               |
| ------------------------------------------- | ----------------------------------------------------------------- |
| [pandas](https://pandas.pydata.org/docs/)    | Leitura em blocos, limpeza, agregações e séries temporais      |
| [NumPy](https://numpy.org/doc/)              | Cálculos numéricos                                              |
| [openpyxl](https://openpyxl.readthedocs.io/) | Leitura da planilha da CNseg                                      |
| [SciPy](https://docs.scipy.org/doc/scipy/)   | Regressão linear, correlações de Pearson e Spearman            |
| [Plotly](https://plotly.com/python/)         | Gráficos interativos (linhas, barras, dispersão, mapa de calor) |
| [Streamlit](https://docs.streamlit.io/)      | Aplicação de BI e publicação (Community Cloud)                |
| Git e GitHub                                | Versionamento e repositório privado                              |

## 7. Resultados encontrados

Valores nominais; "12 meses" = agosto/2025 a julho/2026. Fonte: CNseg.

### Arrecadação (prêmio direto)

|                                           | Automóvel                                               | Patrimonial                                            |
| ----------------------------------------- | -------------------------------------------------------- | ------------------------------------------------------ |
| Jul/2026                                  | R$ 5,97 bi (+5,9% sobre jul/2025) | R$ 3,31 bi (+8,1%) |                                                        |
| Acumulado jan-jul/2026                    | R$ 36,70 bi (+6,2%) | R$ 19,19 bi (+4,0%)              |                                                        |
| 12 meses                                  | R$ 63,72 bi (+6,9%) | R$ 32,52 bi (+7,5%)              |                                                        |
| Crescimento médio anual 2021-2025 (CAGR) | 12,5%                                                    | 17,0%                                                  |
| Variação a/a por ano                    | 2022: +32,8%; 2023: +9,4%; 2024: +3,2%; 2025: +6,8%      | 2022: +21,3%; 2023: +17,2%; 2024: +16,3%; 2025: +13,3% |

### Sinistros e sinistralidade

|                                               | Automóvel                                  | Patrimonial                    |
| --------------------------------------------- | ------------------------------------------- | ------------------------------ |
| Sinistros em 12 meses                         | R$ 37,36 bi (+8,6%) | R$ 8,59 bi (-11,1%) |                                |
| Sinistros ÷ arrecadação em 12 meses        | 58,6%                                       | 26,4%                          |
| Sinistralidade de jul/2026 (índice da CNseg) | 63,1%                                       | 25,5%                          |
| Meses atípicos (                             | z robusto                                   | > 3,5)                         |
| Tendência linear da sinistralidade mensal    | -1,2 p.p. por ano (R² = 0,11)              | -3,8 p.p. por ano (R² = 0,11) |

### Sazonalidade e volatilidade

|                                                       | Automóvel       | Patrimonial      |
| ----------------------------------------------------- | ---------------- | ---------------- |
| Mês mais forte da arrecadação (índice)            | Dezembro (1,17)  | Junho (1,17)     |
| Mês mais fraco                                       | Fevereiro (0,85) | Fevereiro (0,86) |
| Coeficiente de variação (24 meses)                  | 7,5%             | 11,7%            |
| Desvio-padrão da variação a/a, arrecadação       | 13,0 p.p.        | 9,3 p.p.         |
| Desvio-padrão da variação a/a, **sinistros** | 15,9 p.p.        | 157,4 p.p.       |

### Relação entre arrecadação e sinistros (variações a/a, 55 meses)

|             | Pearson          | Spearman         |
| ----------- | ---------------- | ---------------- |
| Automóvel  | 0,79 (p < 0,001) | 0,73 (p < 0,001) |
| Patrimonial | 0,10 (p = 0,46)  | 0,15 (p = 0,27)  |

### Validação cruzada CNseg × SUSEP (jul/2026)

| Grupo        | Arrecadação (SUSEP × CNseg)    | Sinistros (diferença) |
| ------------ | --------------------------------- | ---------------------- |
| Automóvel   | R$ 5.970.141.873 × 5.970.141.874 | +0,05%                 |
| Patrimonial  | R$ 3.314.387.869 (idêntico)      | +0,02%                 |
| Habitacional | R$ 752.740.770 (idêntico)        | 0,00%                  |

O campo *Prêmios Diretos* (12011) é o que reproduz a arrecadação da CNseg, o que confirma a definição da própria planilha ("prêmio direto: emissão líquida de cancelamento e restituição"). A página **Validação** do app mostra a diferença mês a mês.

## 8. Discussão e conclusão

**Observações** (apoiadas nos números acima):

- Os dois grupos cresceram em prêmio todos os anos, mas **em ritmo decrescente**: Automóvel saiu de +32,8% (2022) para +6,8% (2025); Patrimonial de +21,3% para +13,3%, e no acumulado de 2026 está em +4,0%.
- Em Patrimonial, os sinistros dos 12 meses caíram 11,1% enquanto a arrecadação subiu 7,5%; em Automóvel, os sinistros subiram mais (+8,6%) que o prêmio (+6,9%).
- A arrecadação de Automóvel tem pico em dezembro e vale em fevereiro; os sinistros de Patrimonial são muito mais instáveis que os de Automóvel (desvio-padrão da variação a/a de 157 p.p. contra 16 p.p.).
- Em Automóvel, prêmio e sinistros se movem juntos (correlação de 0,79 nas variações anuais); em Patrimonial, não há relação detectável (0,10).

**Hipóteses** (não testadas aqui): os meses atípicos de Habitacional (mai/2024, sinistralidade de 103,6%) e de Patrimonial (jun/2024, 99,3%) coincidem no tempo com as enchentes no Rio Grande do Sul, mas dados nacionais agregados não permitem confirmar essa relação. Parte do crescimento do prêmio de Automóvel em 2022 pode refletir reajuste de preços e não só aumento de volume; os dados nominais não separam os dois efeitos.

**O que os resultados não permitem concluir:** causas de qualquer variação; comportamento por região, por seguradora ou por perfil de segurado; desempenho em termos reais; previsão. A correlação mede associação, e os pares mensais se sobrepõem no tempo (variações sobre 12 meses), então os valores-p tendem a ser otimistas. A tendência linear da sinistralidade é negativa, mas o R² de 0,11 mostra que a reta explica pouco da oscilação mensal.

**Recomendação:** acompanhar a sinistralidade por **janelas de 12 meses**, e não por mês isolado, e tratar os meses atípicos como eventos a investigar, não como tendência.

## 9. Aplicação profissional

- **Uso possível:** painel mensal de acompanhamento de mercado para corretoras, áreas comerciais e de subscrição, ou material de estudo.
- **Atualização:** a CNseg publica a planilha mensalmente. Basta substituir o arquivo em `dados/original/` e rodar o pipeline (seção 11). O ETL interrompe com erro se o calendário do cabeçalho mudar, em vez de gravar dados errados.
- **Qualidade:** os 1.231 testes automáticos e a validação com a SUSEP detectam inconsistências; erros da fonte são registrados, não escondidos.
- **Segurança e privacidade:** só dados agregados do setor, sem pessoas nem empresas; sem credenciais no código.
- **Governança:** confirmar a licença de uso e de divulgação antes de qualquer uso comercial. Em um uso real, a SUSEP (fonte primária) seria a base preferida.
- **Riscos e manutenção:** mudança de layout da planilha; revisão retroativa dos dados pelas seguradoras; dependência de download manual. Melhoria natural: automatizar a coleta, se permitido pelos termos da fonte.

## 10. Aplicação Streamlit

**Link:** [radardoseguro.streamlit.app](https://radardoseguro.streamlit.app/)

| Página                     | O que mostra                                                          |
| --------------------------- | --------------------------------------------------------------------- |
| Visão geral                | Pergunta, público e indicadores do último mês por grupo            |
| Evolução                  | Séries mensais ou acumuladas em 12 meses, totais anuais e CAGR       |
| Sazonalidade e volatilidade | Índice sazonal, mapa de calor mês × ano, volatilidade e tendência |
| Sinistralidade e relações | Sinistralidade mensal, meses atípicos, dispersão e correlação     |
| Detalhe por ramo (SUSEP)    | Ramos de cada grupo (inclui Residencial, Condomínio e Empresarial)   |
| Validação CNseg × SUSEP  | Diferença entre as fontes por grupo e mês                           |
| Sobre e limitações        | Fontes, definições e avisos                                         |

**Navegação:** menu na barra lateral; filtros de grupos (Automóvel, Patrimonial, Habitacional) e de período valem para todas as páginas. Cada gráfico tem título, eixos com unidade, fonte e tabela de dados; os filtros ativos aparecem sob o título.

## 11. Como executar

**Pré-requisitos:** Python 3.11 ou mais novo (testado com 3.13), Git.

```bash
git clone https://github.com/Adri1992ana/Radar_do_Seguro.git
cd Radar_do_Seguro
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

O app abre em `http://localhost:8501` e usa os arquivos já incluídos em `dados/app/`. Não há segredos nem variáveis de ambiente.

**Para reproduzir o pipeline completo** (os arquivos de entrada **não** estão no repositório):

1. Baixe a planilha da CNseg (link na seção 4) e salve em `dados/original/`.
2. Para a SUSEP, baixe `BaseCompleta.zip`, extraia `SES_ValoresMovRamos.csv`, `Ses_ramos.csv` e `Ses_campos.csv` e coloque em `dados/original/`.
3. Rode, nesta ordem:

```bash
python src/transform_cnseg.py --xlsx dados/original/<arquivo>.xlsx
python src/susep_validacao.py --movimento dados/original/SES_ValoresMovRamos.csv --de-para dados/processado/de_para_ramos.csv --cnseg dados/processado/cnseg_mensal_longo.csv
python src/preparar_dados_app.py
python -m streamlit run app.py
```

O arquivo da SUSEP é grande (cerca de 550 MB); a leitura em blocos leva alguns minutos.

## 12. Estrutura de pastas

```
Radar_do_Seguro/
├── app.py                      # aplicação Streamlit
├── requirements.txt            # dependências
├── README.md
├── .gitignore                  # bloqueia dados originais e processados
├── src/
│   ├── transform_cnseg.py      # ETL da planilha da CNseg + conferências
│   ├── susep_validacao.py      # leitura em blocos da SUSEP e comparação com a CNseg
│   ├── preparar_dados_app.py   # gera o conjunto mínimo para o app
│   └── analysis.py             # funções de estatística e EDA
├── dados/
│   ├── app/                    # versionado: valores agregados lidos pelo app
│   ├── original/               # NÃO versionado: planilha e CSVs da SUSEP
│   └── processado/             # NÃO versionado: saídas do ETL (regeneráveis)
└── notebooks/                  # exploração inicial
```

## 13. Limitações e melhorias futuras

- **Licença:** autorização da CNseg ainda pendente (seção 4).
- **Valores nominais:** crescimento inclui inflação e reajustes. Melhoria: deflacionar com IPCA.
- **Dados preliminares:** os meses mais recentes podem ser revisados pelas seguradoras.
- **Sinistralidade da fonte ≠ sinistros ÷ arrecadação** (ex.: Automóvel em jan/2026: 63,5% pela divisão e 60,6% no índice). Provável diferença de base de prêmio; hipótese não verificada.
- **Erros da fonte** (seção 5) foram tratados, mas indicam que a planilha deve ser sempre conferida.
- **Comparação com a SUSEP:** a diferença de 0,02% a 0,05% nos sinistros pode vir de datas de extração distintas (CNseg: 28/09/2026; arquivo da SUSEP: 27/10/2026) e de reenvios de dados.
- **Escopo:** os grupos de Pessoas (Vida e Outros Planos de Risco) ficaram de fora porque a composição que a CNseg usa não pôde ser reproduzida com a SUSEP (a regra provisória deu -46% em Vida em jul/2026).
- **Estatística:** índice sazonal simples; correlações com janelas sobrepostas; regressão linear sem testar pressupostos.
- **Melhorias:** coleta automatizada (se os termos permitirem), análise por região e por ramo, modelos de previsão com intervalo de confiança.

## 14. Créditos e referências

- **Dados:** CNseg (Panorama Estatístico); SUSEP (SES); ANS (DIOPS), via CNseg.
- **Bibliotecas:** pandas, NumPy, openpyxl, SciPy, Plotly e Streamlit (links na seção 6).
- **Método de valores atípicos:** escore z robusto com MAD e corte de 3,5 (Iglewicz e Hoaglin, *How to Detect and Handle Outliers*, 1993).
- **Orientação do projeto:** Prof. Rodrigo Garcia Brunini, SENAI Santa Catarina / LAB365 (enunciado do projeto).
- **Apoio de IA:** o desenvolvimento contou com a assistência do Claude (Anthropic) para escrever e revisar código e documentação. As escolhas de tema, escopo e fontes, a execução dos scripts, a conferência dos resultados e as decisões analíticas são da autora.

## 15. Links de entrega

| Item                                               | Link                                                                                                                       |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Repositório pessoal (privado)                     | https://github.com/Adri1992ana/Radar_do_Seguro                                                                             |
| Aplicação publicada                              | [radardoseguro.streamlit.app](https://radardoseguro.streamlit.app/)                                                         |
| Quadro de tarefas (Trello)                         | [trello.com/b/9ZS88B0X/projeto-final-de-analise-de-dados](https://trello.com/b/9ZS88B0X/projeto-final-de-analise-de-dados)  |
| Repositório oficial da turma                      | [inserir]                                                                                                                  |
| Vídeo (até 3 min, LinkedIn)                      | [inserir]                                                                                                                  |
| Vídeo (Google Drive, leitor para qualquer pessoa) | [inserir]                                                                                                                  |

**Estratégia de versionamento:** branch `main` com commits pequenos e mensagens no imperativo (por exemplo, "adiciona ETL da planilha da CNseg"). [ajustar se criar branches de funcionalidade]

## 16. Evidências das conclusões

Cada afirmação da seção 8 tem origem rastreável: valores em `dados/app/cnseg_danos_mensal.csv`; cálculos em `src/analysis.py`; conferências em `dados/processado/qa_checks.csv` (gerado pelo ETL); comparação com a SUSEP na página **Validação** do app. A distinção entre observação, hipótese e recomendação está explícita na seção 8.
