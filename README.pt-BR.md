# Ensaios de manejo do trigo no Brasil

English version: [README.md](README.md)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23649650.svg)](https://doi.org/10.5281/zenodo.23649650)

2.851 resultados de 54 ensaios com trigo (*Triticum aestivum*) no Brasil, tirados das tabelas de 20 publicações de acesso aberto da Embrapa: doenças (ferrugem-da-folha e ferrugem-do-colmo, giberela, brusone, manchas foliares, oídio, nanismo-amarelo-da-cevada), fungicidas e tratamento de sementes, ensaios de cultivares, nitrogênio, densidade e época de semeadura, e pragas (pulgão-verde-dos-cereais *Schizaphis graminum*, o coró-do-trigo *Phyllophaga triticophaga*, lagarta-do-cartucho *Spodoptera frugiperda*, pulgões vetores do nanismo-amarelo-da-cevada). Cada linha é um número exatamente como foi impresso, com a página e a tabela de onde saiu, e aponta para o ensaio a que pertence.

O trigo é a base do pão e das massas, e o Brasil importa boa parte do trigo que consome. É cultivado no Sul e, mais recentemente, no Cerrado. Boa parte dos dados de ensaios sobre suas doenças, pragas e manejo está em boletins de pesquisa e nos anais das reuniões brasileiras de pesquisa de trigo, alguns deles escaneados. Este dataset torna 20 deles pesquisáveis e comparáveis, do Rio Grande do Sul a Goiás e ao Distrito Federal.

Faz parte do [Paper Rerun](https://paper-rerun.github.io), na linha Open Tables. O trabalho foi feito por agentes de IA num computador doméstico e revisado por uma pessoa antes da publicação.

## O que tem

| | |
|---|---|
| Publicações | 20 (Alice e Infoteca-e, os repositórios abertos da Embrapa), 1976 a 2026 |
| Ensaios | 54 (48 experimentos e 6 análises conjuntas; 42 de campo, 11 em laboratório, 1 em vasos em casa de vegetação), no Rio Grande do Sul, Paraná, Santa Catarina, Mato Grosso do Sul, Distrito Federal e Goiás |
| Registros | 2.851 (produtividade, notas de doenças, severidade e incidência, índice de giberela e grãos giberelados, eficiência de controle, contagens de pragas, perda ou ganho de produtividade, peso do hectolitro, massa de mil grãos, características da planta, infecção de sementes, dados econômicos e outros) |

Arquivos:
- `data/wheat_trials.csv`: o dataset, um registro por valor impresso, com `doc_id` e `trial_id`. As colunas estão descritas em `method/schema.json`. Quando um registro herda um valor da sua coluna na tabela ou da tabela inteira (unidade, estatística, alvo, parte da planta, nível do fator, momento da avaliação), o valor vem preenchido e `inherited` diz de onde ele veio.
- `data/wheat_trials_context.csv`: uma linha por ensaio (local, safra, datas de semeadura e de colheita, regime hídrico, sistema de preparo do solo, cultura anterior, cultivar, pressão de doenças ou pragas, método de aplicação, volume de calda e momento das aplicações, densidade de semeadura ou espaçamento, adubação de base, delineamento). Junte os dois arquivos por `doc_id` + `trial_id`; `application_stages` ou `n_applications` vazios num registro significam que vale o valor do ensaio.
- `data/sources.csv`: as 20 publicações, com autores, link do registro e aviso de licença.
- `qa/decisions.csv`: cada divergência entre as duas transcrições independentes e como ela foi resolvida conferindo o PDF (3.376 decisões, com a página).
- `method/`: o schema, o script de comparação e o script de junção.

### Principais colunas

O arquivo está em UTF-8, com vírgula separando as colunas. Local, safra, regime hídrico, sistema de preparo, cultura anterior, cultivar e delineamento de cada ensaio estão em `data/wheat_trials_context.csv`.

- `doc_id`: identificador da publicação de origem. Liga o registro a `data/sources.csv` e é também o nome do PDF, sem a extensão.
- `trial_id`: o ensaio a que o valor pertence, dentro da publicação. Com `doc_id`, liga o registro à sua linha no arquivo de contexto.
- `page`: página do PDF contada a partir de 1 (a primeira página do arquivo é 1), e não o número impresso na página. O rótulo da tabela está em `table_or_figure`, como impresso ("Tabela 3", "Quadro 1"), ou `text` quando o número está no corpo do texto.
- `treatment`: rótulo da linha exatamente como impresso (cultivar, código, produto, dose, época de semeadura, "Testemunha", "Média"). Numa célula de fatorial, os níveis vêm unidos por " x ", na ordem da tabela.
- `biotic_target`: a doença ou praga a que a variável se refere, como `fusarium_head_blight` (giberela), `wheat_blast` (brusone), `leaf_rust` (ferrugem-da-folha), `stem_rust` (ferrugem-do-colmo), `powdery_mildew` (oídio), `tan_spot` (mancha-amarela), `bydv` (nanismo-amarelo-da-cevada), `aphids` (pulgões) ou `caterpillars` (lagartas). É `multiple` quando um valor cobre várias.
- `variable`: variável medida, como impressa no cabeçalho da coluna ou na legenda. Quando o cabeçalho tem mais de um nível, os níveis vêm separados por " / " ("Avaliação Final / MF / 0-9").
- `variable_standardized`: a mesma variável numa lista fechada. Alguns exemplos: `grain_yield_area` (produtividade de grãos por área ou parcela, na unidade impressa), `disease_score` (nota de doença), `disease_severity_pct` (severidade em % da área da folha, da espiga ou da planta), `disease_incidence_pct` (% de plantas, afilhos, folhas ou espigas com sintoma), `disease_index` (índice que combina incidência e severidade, como o índice de giberela), `control_efficacy_pct` (% de controle impresso pelos autores), `pest_density` (pulgões por afilho, lagartas ou corós por m²), `yield_loss_or_gain` (perda ou ganho de produtividade em relação à testemunha) e `hectoliter_weight` (peso do hectolitro, PH). A lista completa está em `method/schema.json`.
- `value_as_printed`: a célula exatamente como impressa, sem letras, asteriscos, marcas de rodapé ou termo de dispersão ("3.770", "0,5"). Quando `value_kind` é `class` ou `illegible`, `value` fica vazio.
- `value`: o mesmo número pronto para cálculo, com ponto decimal e sem separador de milhar ("3.770" vira 3770, "0,5" vira 0.5). Nada foi calculado, convertido ou arredondado.
- `unit`: unidade como impressa ou informada na legenda ou no cabeçalho ("kg/ha", "%", "kg/hL", "0-9" para escalas de notas). Vazia quando não há unidade impressa.
- `statistic`: o que o número é: `mean` (média), `relative_to_check` (calculado pelos autores em relação à testemunha), `total`, `median`, `single_value` (uma parcela ou uma observação), `percentage_of_total` ou `other`.
- `significance_letter`: letra(s) do teste de médias exatamente como impressas ("a", "AB", "a A", "bc"). Vazia quando não há. O teste e o significado das letras estão em `significance_test` e `letters_meaning`.

## Como foi feito

1. **Coleta.** Um agente buscou nos repositórios abertos da Embrapa publicações com tabelas de ensaios quantitativos sobre o tema e baixou 20, registrando cada candidata que não entrou, com o motivo.
2. **Duas transcrições independentes.** Dois agentes por publicação transcreveram o contexto dos ensaios, os rótulos que valem para uma tabela inteira ou para uma coluna (qual estatística, qual teste, o que as letras significam, quando a cultura foi avaliada, qual parte da planta) e cada célula de tabela sobre o tema num schema fixo, sem ver o trabalho um do outro, copiando os números exatamente como impressos e prestando contas de cada célula de dados.
3. **Comparação e arbitragem.** Um script pareou as duas transcrições, ensaio por ensaio, tabela por tabela e registro por registro, e listou cada divergência e cada valor presente em só uma delas. Cada caso foi resolvido conferindo o PDF, com a página como evidência.

## Qual a precisão

- **Números:** nenhum número, letra de significância ou valor de dispersão foi lido errado em nenhuma das duas transcrições. Dos 2.845 registros pareados, 2.844 bateram com o impresso. O outro é uma célula de goulart1999 (Tabela 5, p. 18) impressa como "0b,6 c": uma transcrição descartou o caractere solto e escreveu 0,6, a outra copiou o impresso. O dataset mantém o impresso, marca o valor como ilegível e dá 0,6 como valor provável nas notas.
- **Contexto e rótulos:** sozinha, uma transcrição estava totalmente correta em 86,6% dos registros, e a outra em 83,0%. A maioria dos erros veio de contexto impresso na metodologia e que vale para todos os registros de um documento: pulverizações de fungicida feitas em todas as parcelas lidas como parte do tratamento (chagas2026, 169 registros), as aplicações de nitrogênio de cada tratamento não contadas (ramos1976), a dose do produto comercial deixada de fora (goulart1999), a unidade de uma escala de notas informada só na metodologia (brancao2004), ou "na colheita" registrado como momento da avaliação onde nenhum estádio está impresso. As 3.376 decisões foram resolvidas conferindo o PDF, então o dataset não depende de nenhuma das duas transcrições sozinha.
- **Limites conhecidos:** valores mostrados só em gráficos, sem número impresso, não foram lidos; nenhum registro vem de figura, e 42 vêm do texto. O desoxinivalenol (DON) não está incluído: os ensaios cooperativos de giberela que trazem DON em tabela têm mais de 400 registros cada, demais para esta rodada, e os ensaios estaduais de 2017 a 2024 mostram o DON só em gráficos sem número. ramos1976, sonego1987, goulart1992 e goulart1999 são documentos escaneados com camada de texto ruidosa e tabelas impressas de lado; foram lidos a partir da imagem da página. Um documento, santana2012 (ensaios cooperativos de fungicidas contra a giberela em sete locais do Paraná, Rio Grande do Sul e Santa Catarina), tem 375 registros, 13% do dataset. Em maciel2015 e chagas2026, todas as parcelas recebem as mesmas pulverizações de fungicida; maciel2015 as registra em `application_stages` e `n_applications` do ensaio, e chagas2026 deixa esses campos vazios e descreve as pulverizações nas notas do ensaio.

## Licença e citação

- O dataset (os arquivos CSV, o schema e os scripts) é publicado sob a licença [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Por favor, cite as publicações originais listadas em `data/sources.csv` e também este dataset.
- As publicações não são redistribuídas. Os repositórios da Embrapa exibem um aviso CC BY-NC-ND 4.0; os dois artigos de periódico (silva1991, na Pesquisa Agropecuária Brasileira, e braz2006, na Ciência e Agrotecnologia) e os oito trabalhos das reuniões brasileiras de pesquisa de trigo mantêm os próprios termos, e quatro boletins da Embrapa (gomez2001, bilibio2021, chagas2026 e ferreira2025) trazem "Todos os direitos reservados". Aqui são usados só os números, que são fatos, e citações curtas.

Erros ou ensaios que faltam: por favor, [abra uma issue](https://github.com/paper-rerun/wheat-trials-br/issues).

## Como este dataset foi feito

Este dataset foi montado por agentes de IA (Claude, da Anthropic) num computador doméstico e revisado por uma pessoa antes da publicação. Nenhum valor foi estimado ou digitado à mão: cada um foi transcrito do PDF original duas vezes, de forma independente, e cada divergência foi conferida na página. O método e os scripts estão em `method/`. Como funciona o projeto como um todo (em inglês): https://github.com/paper-rerun/paper-rerun/blob/main/METHOD.md

Contato: Filipe Tessaro, pelas issues deste repositório.
