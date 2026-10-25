# Wheat management trials in Brazil

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23649650.svg)](https://doi.org/10.5281/zenodo.23649650)

2,851 trial results from 54 trials on wheat (*Triticum aestivum*) in Brazil, taken from the tables of 20 open-access Embrapa publications: diseases (leaf and stem rust, Fusarium head blight, wheat blast, leaf spots, powdery mildew, barley yellow dwarf), fungicides and seed treatment, cultivar trials, nitrogen, sowing density and date, and pests (greenbug *Schizaphis graminum*, the white grub *Phyllophaga triticophaga*, fall armyworm *Spodoptera frugiperda*, aphid vectors of barley yellow dwarf). Each row is one number exactly as printed, with the page and table it came from, and points to the trial it belongs to.

Wheat is the base of bread and pasta, and Brazil imports a large share of the wheat it eats. It is grown in the South and, more recently, in the Cerrado. Much of the trial evidence on its diseases, pests and management sits in research bulletins and in the proceedings of the Brazilian wheat research meetings, some of them scanned. This dataset makes 20 of them searchable and comparable, from Rio Grande do Sul to Goiás and the Federal District.

Part of [Paper Rerun](https://paper-rerun.github.io), in its Open Tables line. The work was done by AI agents on a home computer and reviewed by a human before publication.

## What is in it

| | |
|---|---|
| Publications | 20 (Alice and Infoteca-e, Embrapa's open repositories), 1976 to 2026 |
| Trials | 54 (48 experiments and 6 joint analyses; 42 field, 11 laboratory, 1 greenhouse pots), in Rio Grande do Sul, Paraná, Santa Catarina, Mato Grosso do Sul, the Federal District and Goiás |
| Records | 2,851 (yield, disease scores, severity and incidence, Fusarium head blight index and scabby kernels, control efficacy, pest counts, yield loss or gain, test weight, thousand-kernel weight, plant traits, seed infection, economics and others) |

Files:
- `data/wheat_trials.csv`: the dataset, one record per printed value, with `doc_id` and `trial_id`. Columns are described in `method/schema.json`. Where a record takes a value from its table column or from the whole table (unit, statistic, target, plant part, factor level, assessment time), the value is filled in and `inherited` says where it came from.
- `data/wheat_trials_context.csv`: one row per trial (place, season, sowing and harvest date, water regime, tillage system, previous crop, cultivar, disease or pest pressure, application method, spray volume and timing, seeding rate or spacing, base fertilization, design). Join on `doc_id` + `trial_id`; an empty `application_stages` or `n_applications` in a record means the trial's value applies.
- `data/sources.csv`: the 20 publications, with authors, record link and licence notice.
- `qa/decisions.csv`: every disagreement between the two independent transcriptions and how it was settled against the PDF (3,376 decisions, with page).
- `method/`: the schema, the comparison script and the merge script.

## How it was made

1. **Collection.** An agent searched Embrapa's open repositories for publications with quantitative trial tables on this topic and downloaded 20, recording every candidate it did not take, with the reason.
2. **Two independent transcriptions.** Two agents per publication transcribed the trial context, the labels that apply to a whole table or to one column (which statistic, which test, what the letters mean, when the crop was assessed, which plant part) and every table cell on the topic into a fixed schema, without seeing each other's work, copying numbers exactly as printed and accounting for every data cell.
3. **Comparison and adjudication.** A script paired the two transcriptions, trial by trial, table by table and record by record, and listed every disagreement and every value present in only one of them. Each one was settled by checking the PDF, with the page as evidence.

## How accurate it is

- **Numbers:** no number, significance letter or dispersion value was misread in either transcription. Of the 2,845 paired records, 2,844 matched as printed. The other is one cell of goulart1999 (Table 5, p. 18) printed as "0b,6 c": one transcription dropped the stray character and wrote 0,6, the other copied the print. The dataset keeps the print, marks the value as illegible and gives 0,6 as the likely value in the notes.
- **Context and labels:** one transcription alone was fully correct on 86.6% and 83.0% of records. Most errors came from context printed in the methods and carried down to every record of a document: fungicide sprays given to every plot read as part of the treatment (chagas2026, 169 records), the nitrogen applications per treatment not counted (ramos1976), the commercial-product dose left out (goulart1999), the unit of a rating scale given only in the methods (brancao2004), or "at harvest" entered as the assessment time where no stage is printed. All 3,376 decisions were settled against the PDF, so the dataset does not depend on either transcription alone.
- **Known limits:** values shown only in charts without printed numbers were not read; no record comes from a figure, and 42 come from the text. Deoxynivalenol (DON) is not included: the cooperative Fusarium head blight trials that print DON in a table have more than 400 records each, too many for this round, and the state trials of 2017 to 2024 show DON only in charts without numbers. ramos1976, sonego1987, goulart1992 and goulart1999 are scans with a noisy text layer and tables printed sideways; they were read from the rendered page. One document, santana2012 (cooperative fungicide trials against Fusarium head blight at seven sites in Paraná, Rio Grande do Sul and Santa Catarina), holds 375 records, 13% of the dataset. In maciel2015 and chagas2026 every plot gets the same fungicide sprays; maciel2015 records them in the trial's `application_stages` and `n_applications`, chagas2026 leaves those fields empty and describes the sprays in the trial notes.

## Licence and citation

- The dataset (the CSV files, schema and scripts) is released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Please cite the original publications listed in `data/sources.csv` as well as this dataset.
- The publications are not redistributed. Embrapa's repositories show a CC BY-NC-ND 4.0 notice; the two journal articles (silva1991 in Pesquisa Agropecuária Brasileira, braz2006 in Ciência e Agrotecnologia) and the eight papers from the Brazilian wheat research meetings keep their own terms, and four Embrapa bulletins (gomez2001, bilibio2021, chagas2026 and ferreira2025) print "Todos os direitos reservados" (all rights reserved). Only numbers, which are facts, and short citations are used here.

Errors or missing trials: please [open an issue](https://github.com/paper-rerun/wheat-trials-br/issues).

## How this dataset was made

This dataset was built by AI agents (Claude, by Anthropic) on a home computer and reviewed by a human before publication. No value was estimated or typed by hand: each one was transcribed from the source PDF twice, independently, and every disagreement was checked against the page. The method and scripts are in `method/`. How the wider project works: https://github.com/paper-rerun/paper-rerun/blob/main/METHOD.md

Contact: Filipe Tessaro, via issues on this repository.
