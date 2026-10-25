# Merge the adjudicated documents into trials.csv, dataset.csv and qa/decisions.csv, and print the round numbers for RODADA.md
# Usage: python -X utf8 method/merge.py   (paths are relative to the trigo folder)
# Copied from brusone-arroz/method/merge.py for the tomato round (schema v6). Changed: records inherit from the column first
# and then from the table (compare.INHERITED says the chain), column fields that the record has no place for go to the
# dataset (organism_stage, crop_stage_status...), column errors are a category of their own, one-sided columns count like
# tables, and source text copied past 15 words is no longer cut with "(...)": the script lists it, we rewrite it in our own
# words in adjudicated/, and the self-check fails while any copy is left
#
# Copied from tomate/method/merge.py for the wheat round (schema v7). Changed: the column also carries plant_part and
# factor_level (copied to the dataset), the trial block has water_regime, tillage_system, previous_crop, sowing_date,
# harvest_date, spray_volume, seeding_rate_or_spacing and base_fertilization, and the cascade comparison is wheat x tomato
import ast
import csv
import glob
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "method"))
import compare  # noqa: E402  only for the compared field lists and the inheritance chain
MAX_QUOTE_WORDS = 15
COMPARED_RECORD_FIELD_COUNT = len(compare.COMPARED_FIELDS)  # value also covers value_as_printed
COMPARED_TRIAL_FIELD_COUNT = len(compare.TRIAL_FIELDS)
COMPARED_COLUMN_FIELD_COUNT = len(compare.COLUMN_FIELDS)
LICENSE_REPOSITORY = "CC BY-NC-ND 4.0 (aviso geral do repositório {repo}, não é licença do item)"

# Record fields filled from the column, then the table (and biotic_target from the trial). application_stages and
# n_applications stay empty on the record when they are the trial's: the dataset joins trials.csv for context
DATASET_INHERITED = {field: chain for field, chain in compare.INHERITED.items() if field not in ("application_stages", "n_applications")}
SOURCE_NAME = {"column": "column", "labels": "table", "trial": "trial"}
# Column and table fields with no record field, copied to the dataset
EXTRA_COLUMN_FIELDS = {"organism_stage": "organism_stage", "plant_part": "plant_part", "factor_level": "factor_level",
	"crop_stage_source_page": "crop_stage_source_page", "crop_stage_status": "crop_stage_status", "notes": "column_notes"}
EXTRA_LABEL_COLUMNS = {"significance_test": "significance_test", "letters_meaning": "letters_meaning",
	"scale_meaning": "scale_meaning", "footnote_summary": "table_footnote_summary", "source_inconsistency": "table_source_inconsistency"}
DECISION_TEXT_COLUMNS = ["a_value", "b_value", "final_value", "evidence"]
NOT_SOURCE_TEXT = {"citation", "license", "record_id", "doc_id", "source_file", "decision_ids", "inherited"}

# One-sided entries the adjudicator marked X_right but called an optional summary in the evidence. None this round:
# the six lau2020 text records only in B are both_acceptable, so they already count as optional
OPTIONAL_DESPITE_DECISION = set()
# Pairs per document in the adjudication summaries, checked against the count from A minus the A-only records
EXPECTED_PAIRS = {"ramos1976-nitrogenio-modos-epocas-ponta-grossa-pr": 124, "sonego1987-fungicidas-ferrugens-dourados-ms": 144,
	"silva1991-nitrogenio-cobertura-irrigado-planaltina-df": 72, "goulart1992-tebuconazole-brusone-dourados-ms": 118,
	"picinini1999-ensaio-cooperativo-fungicidas-1993-passo-fundo": 73, "goulart1999-tratamento-sementes-oidio-ferrugem-dourados-ms": 144,
	"salvadori1999-inseticidas-sementes-pulgao-verde": 75, "salvadori1999-tratamento-sementes-coro-phyllophaga": 72,
	"gomez2001-inseticidas-lagarta-do-cartucho-dourados-ms": 349, "brancao2004-doencas-cultivares-pelotas-rs": 190,
	"lima2005-giberela-ensaio-estadual-coxilha-rs": 282, "braz2006-nitrogenio-palhadas-santo-antonio-de-goias": 83,
	"bassoi2009-trifloxistrobina-tebuconazol-cultivares-londrina-pr": 220, "santana2012-fungicidas-giberela-cooperativos-2011": 375,
	"maciel2015-reacao-brusone-genotipos-cerrado": 42, "chagas2015-densidade-nitrogenio-sequeiro-planaltina-df": 75,
	"lau2020-reacao-bydv-pav-cultivares-rs": 140, "bilibio2021-manejo-afideos-nanismo-amarelo-coxilha-rs": 54,
	"chagas2026-epocas-semeadura-brusone-sequeiro-planaltina-df": 169, "ferreira2025-tratamento-sementes-fungicidas-cooperativos-2024": 44}

# Quotes: 'x', "x", ‘x’, “x”. The single quote must not touch a letter, so "B's" is not a quote
QUOTE_PATTERN = re.compile(r"(?<![\w])'([^']{3,}?)'(?![\w])|\"([^\"]{3,}?)\"|‘([^’]+)’|“([^”]+)”")

TABLE_FIELDS = {"kind", "trial_ids", "data_cells", "transcribed", "skipped_cells", "table", "table_id"}
CROP_STAGE_FIELDS = {"crop_stage", "crop_stage_refers_to", "crop_stage_source_page", "crop_stage_status"}
ROW_IDENTITY_FIELDS = {"treatment", "treatment_code", "cultivar", "is_marginal", "row_identity"}
VALUE_FIELDS = {"value", "value_as_printed", "significance_letter", "unit", "dispersion_as_printed"}
NUMBER_FIELDS = {"value", "value_as_printed", "significance_letter", "dispersion_as_printed"}
CLASSIFICATION_FIELDS = {"statistic", "statistic_stated", "transformation_stated", "treatment_type", "source_inconsistency"}
INPUT_FIELDS = {"active_ingredient_or_input", "dose_and_unit", "dose_source_page", "application_stages", "n_applications"}


def NormalizeWord(word):
	return re.sub(r"^[^\w]+|[^\w]+$", "", word.lower())


def LoadPdfWordShingles(pdf_path):
	# Text layer of the whole PDF, with line-break hyphens joined, as a set of 16-word sequences
	pdf_text = subprocess.run(["pdftotext", "-enc", "UTF-8", pdf_path, "-"], capture_output=True).stdout.decode("utf-8", "replace")
	pdf_text = re.sub(r"-\s*\n\s*", "", pdf_text)
	pdf_words = [NormalizeWord(word) for word in pdf_text.split()]
	pdf_words = [word for word in pdf_words if word]
	shingle_size = MAX_QUOTE_WORDS + 1
	return {tuple(pdf_words[index:index + shingle_size]) for index in range(len(pdf_words) - shingle_size + 1)}


def CopiedRuns(text, pdf_shingles):
	# Word runs of the text found in the PDF text layer with more than MAX_QUOTE_WORDS words in a row
	words = text.split()
	normalized = [NormalizeWord(word) for word in words]
	shingle_size = MAX_QUOTE_WORDS + 1
	runs = []
	index = 0
	while index + shingle_size <= len(words):
		if tuple(normalized[index:index + shingle_size]) in pdf_shingles and "" not in normalized[index:index + shingle_size]:
			run_end = index + shingle_size
			while run_end < len(words) and tuple(normalized[run_end - shingle_size + 1:run_end + 1]) in pdf_shingles:
				run_end += 1
			runs.append(" ".join(words[index:run_end]))
			index = run_end
		else:
			index += 1
	return runs


def LongQuotes(text):
	return [quoted for quoted in (next(group for group in match.groups() if group) for match in QUOTE_PATTERN.finditer(text))
		if len(quoted.split()) > MAX_QUOTE_WORDS]


def StringLeaves(value):
	# A cell that holds a dict or list (JSON, or the Python repr the adjudicators wrote in a_value and b_value) is
	# checked string by string: the quotes around each string are syntax, not a quotation of the source
	if isinstance(value, str):
		if value[:1] in "{[":
			for parser in (json.loads, ast.literal_eval):
				try:
					return StringLeaves(parser(value))
				except (ValueError, SyntaxError, TypeError, MemoryError, RecursionError):
					continue
		return [value]
	if isinstance(value, dict):
		return [leaf for each_value in value.values() for leaf in StringLeaves(each_value)]
	if isinstance(value, list):
		return [leaf for each_value in value for leaf in StringLeaves(each_value)]
	return []


def FindLongCopies(text, pdf_shingles):
	if not isinstance(text, str) or not text:
		return []
	return [copy for leaf in StringLeaves(text) for copy in CopiedRuns(leaf, pdf_shingles) + LongQuotes(leaf)]


def BuildCitation(document):
	authors = "; ".join(document["authors"]).rstrip(".")
	title = document["title"].rstrip(".")
	reference = document["journal_article"] or document["citation"]
	return f"{authors}. {title}. {reference} Disponível em: {document['record_url']}"


def BuildLicense(document):
	license_text = LICENSE_REPOSITORY.format(repo=document["repository"])
	if document.get("publisher_copyright_in_pdf") and not document["publisher_copyright_in_pdf"].startswith("none found"):
		license_text += "; o PDF imprime: " + document["publisher_copyright_in_pdf"]
	if document.get("journal_article"):
		license_text += "; artigo de periódico, valem os termos da revista (não conferidos)"
	elif "anais" in document["type"].lower():
		license_text += "; trabalho em anais, valem os termos do evento (não conferidos)"
	return license_text


def DecisionIds(record):
	ids = record.get("decision_ids")
	if isinstance(ids, list):
		return "; ".join(str(each_id) for each_id in ids)
	return ids or ""


def SideOfError(decision):
	# Which side a decision counts against
	if decision == "B_right":
		return ("A",)
	if decision == "A_right":
		return ("B",)
	if decision == "both_wrong":
		return ("A", "B")
	return ()


def PlainField(field):
	# 'columns.c3.unit' -> 'unit', 'table_level_labels.statistic' -> 'statistic'
	return re.sub(r"^columns\.[^.]+\.", "", field).replace("table_level_labels.", "")


def CategoryOf(row):
	# trial context, column, table label, inventory, end_checklist or record
	field, table_label = row["field"], row["table_or_figure"]
	if table_label == "trials":
		return "trial"
	if table_label == "end_checklist" or row["kind"] == "checklist" or field.startswith(("end_checklist", "context", "footnotes", "rows")):
		return "checklist"
	if field.startswith("columns.") or field == "column":
		return "column"
	if field.startswith("table_level_labels."):
		return "label"
	if field in TABLE_FIELDS:
		return "inventory"
	return "record"


def CascadeGroupErrors(decisions_path):
	# Record, column and label errors per side, grouped by the rule that makes a cascade, for the round comparison
	group_errors = Counter()
	for row in csv.DictReader(open(decisions_path, encoding="utf-8-sig")):
		if CategoryOf(row) not in ("record", "label", "column"):
			continue
		field = PlainField(row["field"])
		if field in CLASSIFICATION_FIELDS:
			group = "classification"
		elif field in CROP_STAGE_FIELDS:
			group = "crop_stage"
		elif field in ROW_IDENTITY_FIELDS:
			group = "row_identity"
		elif field == "trial_id":
			group = "trial_id"
		elif field in VALUE_FIELDS:
			group = "value"
		elif field in INPUT_FIELDS:
			group = "input"
		elif field in ("variable_standardized", "biotic_target", "organism_stage"):
			group = "vocabulary"
		else:
			group = "other"
		for side in SideOfError(row["decision"]):
			group_errors[(side, group)] += 1
	return group_errors


def CellText(value):
	if value is None:
		return ""
	if isinstance(value, (list, dict)):
		return json.dumps(value, ensure_ascii=False)
	return value


def main():
	schema = json.load(open(os.path.join(ROOT, "schema.json"), encoding="utf-8"))
	record_fields = schema["$defs"]["record"]["required"]
	trial_fields = schema["$defs"]["trial"]["required"]
	sources = json.load(open(os.path.join(ROOT, "sources.json"), encoding="utf-8"))
	documents_by_id = {document["id"]: document for document in sources["documents"]}

	shingles_by_doc = {}
	dataset_rows = []
	trial_rows = []
	stats = defaultdict(dict)
	for adjudicated_path in sorted(glob.glob(os.path.join(ROOT, "adjudicated", "*.json"))):
		doc_id = os.path.basename(adjudicated_path)[:-5]
		document = documents_by_id[doc_id]
		shingles_by_doc[doc_id] = LoadPdfWordShingles(os.path.join(ROOT, document["pdf_path"]))
		adjudicated = json.load(open(adjudicated_path, encoding="utf-8"))
		citation, license_text = BuildCitation(document), BuildLicense(document)
		trials_by_id = {}
		for trial in adjudicated["trials"]:
			assert all(field in trial for field in trial_fields), (doc_id, trial.get("trial_id"))
			row = {"doc_id": doc_id}
			for field in trial_fields:
				row[field] = CellText(trial[field])
			row["citation"] = citation
			trial_rows.append(row)
			trials_by_id[trial["trial_id"]] = trial
		tables_by_id = {table["table_id"]: table for table in adjudicated["tables"]}
		for record_number, record in enumerate(adjudicated["records"], start=1):
			# Every schema field must be there, the record belongs to this document and points to one of its trials, tables and columns
			assert all(field in record for field in record_fields), (doc_id, record_number)
			assert record["doc_id"] == doc_id
			assert record["trial_id"] in trials_by_id, (doc_id, record_number, record["trial_id"])
			assert record["table_id"] in tables_by_id, (doc_id, record_number, record["table_id"])
			table = tables_by_id[record["table_id"]]
			assert record["trial_id"] in table["trial_ids"], (doc_id, record_number, record["table_id"], record["trial_id"])
			columns_by_id = {column["column_id"]: column for column in table.get("columns") or []}
			assert record["column_id"] in columns_by_id, (doc_id, record_number, record["table_id"], record["column_id"])
			sources_of_record = {"column": columns_by_id[record["column_id"]], "labels": table.get("table_level_labels") or {},
				"trial": trials_by_id[record["trial_id"]]}
			row = {"record_id": f"{doc_id}#{record_number:04d}"}
			inherited = []
			for field in record_fields:
				value = record[field]
				# Null on the record means "as the column, then as the table": write that value and say where it came from
				if value is None and field in DATASET_INHERITED:
					for source, source_field in DATASET_INHERITED[field]:
						if sources_of_record[source].get(source_field) is not None:
							value = sources_of_record[source][source_field]
							inherited.append(f"{field}:{SOURCE_NAME[source]}")
							break
				row[field] = CellText(value)
			for column_field, dataset_column in EXTRA_COLUMN_FIELDS.items():
				row[dataset_column] = CellText(sources_of_record["column"].get(column_field))
			for label_field, dataset_column in EXTRA_LABEL_COLUMNS.items():
				row[dataset_column] = CellText(sources_of_record["labels"].get(label_field))
			row["inherited"] = "; ".join(inherited)
			row["origin"] = record.get("origin")
			row["decision_ids"] = DecisionIds(record)
			row["citation"] = citation
			row["license"] = license_text
			dataset_rows.append(row)
		stats[doc_id]["final"] = len(adjudicated["records"])
		stats[doc_id]["trials"] = len(adjudicated["trials"])
		stats[doc_id]["tables"] = len(adjudicated["tables"])
		stats[doc_id]["label_tables"] = sum(1 for table in adjudicated["tables"] if table.get("table_level_labels"))
		stats[doc_id]["columns"] = sum(len(table.get("columns") or []) for table in adjudicated["tables"])

	# trial_id is per document (t1, t2...), so the dataset joins trials.csv on doc_id + trial_id
	record_columns = ["record_id", "doc_id", "trial_id"] + [field for field in record_fields if field not in ("doc_id", "trial_id")]
	record_columns += list(EXTRA_COLUMN_FIELDS.values()) + list(EXTRA_LABEL_COLUMNS.values())
	record_columns += ["inherited", "origin", "decision_ids", "citation", "license"]
	with open(os.path.join(ROOT, "dataset.csv"), "w", encoding="utf-8", newline="") as output_file:
		writer = csv.DictWriter(output_file, fieldnames=record_columns)
		writer.writeheader()
		writer.writerows(dataset_rows)
	trial_columns = ["doc_id"] + trial_fields + ["citation"]
	with open(os.path.join(ROOT, "trials.csv"), "w", encoding="utf-8", newline="") as output_file:
		writer = csv.DictWriter(output_file, fieldnames=trial_columns)
		writer.writeheader()
		writer.writerows(trial_rows)

	# Concatenate the decision files as they are, union of columns
	decision_rows = []
	decision_columns = ["source_file"]
	for decisions_path in sorted(glob.glob(os.path.join(ROOT, "adjudicated", "*_decisions.csv"))):
		for row in csv.DictReader(open(decisions_path, encoding="utf-8-sig", newline="")):
			row = {"source_file": "adjudicated/" + os.path.basename(decisions_path), **row}
			for key in row:
				if key not in decision_columns:
					decision_columns.append(key)
			decision_rows.append(row)
	os.makedirs(os.path.join(ROOT, "qa"), exist_ok=True)
	with open(os.path.join(ROOT, "qa", "decisions.csv"), "w", encoding="utf-8", newline="") as output_file:
		writer = csv.DictWriter(output_file, fieldnames=decision_columns)
		writer.writeheader()
		writer.writerows(decision_rows)

	# Source text copied past 15 words, or quoted past 15 words, anywhere in the three files
	long_copies = []
	for file_name, rows, key_of in (("trials.csv", trial_rows, lambda row: f"{row['doc_id']} {row['trial_id']}"),
			("dataset.csv", dataset_rows, lambda row: row["record_id"]),
			("qa/decisions.csv", decision_rows, lambda row: f"{row['source_file']} {row['diff_id']}")):
		for row in rows:
			for column, text in row.items():
				if column in NOT_SOURCE_TEXT:
					continue
				for copy in FindLongCopies(text, shingles_by_doc[row["doc_id"]]):
					long_copies.append((file_name, key_of(row), column, copy))
	unique_copies = sorted({(file_name, key.split("#")[0] if file_name == "dataset.csv" else key, column, copy) for file_name, key, column, copy in long_copies})
	print(f"long copies: {len(long_copies)} cells, {len(unique_copies)} distinct")
	for copy in unique_copies:
		print("  COPY", copy)

	# Per side and per category: field errors, wrong units, omissions, optional and spurious entries
	field_errors_by_side = Counter()
	error_types = Counter()
	for doc_id in stats:
		a_document = json.load(open(os.path.join(ROOT, "A", doc_id + ".json"), encoding="utf-8"))
		b_document = json.load(open(os.path.join(ROOT, "B", doc_id + ".json"), encoding="utf-8"))
		doc_stats = stats[doc_id]
		doc_stats.update(a_records=len(a_document["records"]), b_records=len(b_document["records"]),
			a_trials=len(a_document["trials"]), b_trials=len(b_document["trials"]),
			a_tables=len(a_document["tables"]), b_tables=len(b_document["tables"]),
			a_columns=sum(len(table.get("columns") or []) for table in a_document["tables"]),
			b_columns=sum(len(table.get("columns") or []) for table in b_document["tables"]))
		counts = Counter()
		wrong = {(side, category): set() for side in "AB" for category in ("record", "trial", "label", "inventory", "column", "checklist")}
		wrong_columns = {"A": set(), "B": set()}
		for row in decision_rows:
			if row["doc_id"] != doc_id:
				continue
			counts["decision_" + row["decision"]] += 1
			kind, field = row["kind"], row["field"]
			if kind.startswith("only_in") or kind == "missing_in_both":
				unit = field if field in ("trial", "table", "column") else "record"
				if kind == "missing_in_both":
					for side in ("both", "A", "B"):
						counts[f"{side}_{unit}_omitted"] += 1
					continue
				present_side = kind[-1]
				missing_side = "B" if present_side == "A" else "A"
				present_index = row[present_side.lower() + "_index"]
				if (doc_id, unit, present_index) in OPTIONAL_DESPITE_DECISION:
					counts[f"{present_side}_{unit}_optional"] += 1
				elif row["decision"] in (present_side + "_right", "ambiguous_print"):
					counts[f"{missing_side}_{unit}_omitted"] += 1
				elif row["decision"] == missing_side + "_right":
					counts[f"{present_side}_{unit}_spurious"] += 1
					if unit == "column":
						wrong_columns[present_side].add(present_index)
				else:
					counts[f"{present_side}_{unit}_optional"] += 1
				if unit == "record" and present_side == "A":
					counts["a_only_records"] += 1
				continue
			category = CategoryOf(row)
			for side in SideOfError(row["decision"]):
				counts[f"{side}_{category}_field_errors"] += 1
				# Trial, column and table rows carry the trial_id or table_id; record rows the record index
				wrong[(side, category)].add(row[side.lower() + "_index"] or row["a_index"] or row["b_index"])
				if category == "column":
					wrong_columns[side].add((row["a_index"], field.split(".")[1]))
				field_errors_by_side[(side, category, PlainField(field))] += 1
				error_type = row[side.lower() + "_error_type"] or "(sem tipo)"
				error_types[(side, error_type)] += 1
				if category == "record" and field in NUMBER_FIELDS:
					counts[f"{side}_number_errors"] += 1
				if category == "record" and field in VALUE_FIELDS:
					counts[f"{side}_value_errors"] += 1
		doc_stats.update(counts)
		for (side, category), units in wrong.items():
			doc_stats[f"{side}_wrong_{category}"] = len(units)
		for side in "AB":
			# Tables with a label, inventory or column error count once
			doc_stats[f"{side}_wrong_table"] = len(wrong[(side, "label")] | wrong[(side, "inventory")] | wrong[(side, "column")])
			doc_stats[f"{side}_wrong_column_count"] = len(wrong_columns[side])
		doc_stats["pairs"] = doc_stats["a_records"] - counts["a_only_records"]
		assert doc_stats["pairs"] == EXPECTED_PAIRS[doc_id], (doc_id, doc_stats["pairs"])
		doc_stats["required"] = doc_stats["pairs"] + counts["A_record_omitted"] + counts["B_record_omitted"] - counts["both_record_omitted"]

	totals = Counter()
	print("doc_id;final;required;pairs;trials;tables;columns;A_rec;B_rec;A_wrong_rec;B_wrong_rec;A_omit;B_omit;A_spur;B_spur;A_opt;B_opt;"
		"A_wrong_trial;B_wrong_trial;A_wrong_table;B_wrong_table;A_rec_fields;B_rec_fields")
	for doc_id, doc_stats in sorted(stats.items()):
		for key, value in doc_stats.items():
			totals[key] += value
		print(f"{doc_id};{doc_stats['final']};{doc_stats['required']};{doc_stats['pairs']};{doc_stats['trials']};{doc_stats['tables']};{doc_stats['columns']};"
			f"{doc_stats['a_records']};{doc_stats['b_records']};{doc_stats['A_wrong_record']};{doc_stats['B_wrong_record']};"
			f"{doc_stats.get('A_record_omitted', 0)};{doc_stats.get('B_record_omitted', 0)};{doc_stats.get('A_record_spurious', 0)};"
			f"{doc_stats.get('B_record_spurious', 0)};{doc_stats.get('A_record_optional', 0)};{doc_stats.get('B_record_optional', 0)};"
			f"{doc_stats['A_wrong_trial']};{doc_stats['B_wrong_trial']};{doc_stats['A_wrong_table']};{doc_stats['B_wrong_table']};"
			f"{doc_stats.get('A_record_field_errors', 0)};{doc_stats.get('B_record_field_errors', 0)}")
	print(dict(sorted(totals.items())))

	# Accuracy per record, trial, column and table, counting omissions, with and without the largest document
	largest_doc = max(stats, key=lambda doc_id: stats[doc_id]["required"])
	for side in ("A", "B"):
		required = totals["required"]
		omitted = totals[side + "_record_omitted"]
		wrong_records = totals[side + "_wrong_record"]
		paired = totals["pairs"]
		record_field_errors = totals[side + "_record_field_errors"]
		print(f"{side} records: right {required - omitted - wrong_records}/{required} = {100 * (required - omitted - wrong_records) / required:.1f}%"
			f" | omitted {omitted} | with error {wrong_records} | spurious {totals[side + '_record_spurious']} | optional {totals[side + '_record_optional']}"
			f" | fields {record_field_errors}/{paired * COMPARED_RECORD_FIELD_COUNT} = {100 * record_field_errors / (paired * COMPARED_RECORD_FIELD_COUNT):.2f}%"
			f" | number/letter errors {totals[side + '_number_errors']} | unit errors {totals[side + '_value_errors'] - totals[side + '_number_errors']}")
		largest = stats[largest_doc]
		required_rest = required - largest["required"]
		right_rest = required_rest - (omitted - largest.get(side + "_record_omitted", 0)) - (wrong_records - largest[side + "_wrong_record"])
		print(f"{side} records without {largest_doc}: {right_rest}/{required_rest} = {100 * right_rest / required_rest:.1f}%")
		trial_total = totals["trials"]
		trial_omitted = totals[side + "_trial_omitted"]
		wrong_trials = totals[side + "_wrong_trial"]
		trial_field_errors = totals[side + "_trial_field_errors"]
		trial_fields_compared = (trial_total - trial_omitted) * COMPARED_TRIAL_FIELD_COUNT
		print(f"{side} trials: right {trial_total - trial_omitted - wrong_trials}/{trial_total} = {100 * (trial_total - trial_omitted - wrong_trials) / trial_total:.1f}%"
			f" | omitted {trial_omitted} | spurious {totals[side + '_trial_spurious']} | with error {wrong_trials}"
			f" | fields {trial_field_errors}/{trial_fields_compared} = {100 * trial_field_errors / trial_fields_compared:.2f}%")
		column_total = totals["columns"]
		column_omitted = totals[side + "_column_omitted"]
		wrong_column_count = totals[side + "_wrong_column_count"]
		print(f"{side} columns: right {column_total - column_omitted - wrong_column_count}/{column_total}"
			f" = {100 * (column_total - column_omitted - wrong_column_count) / column_total:.1f}% | omitted {column_omitted}"
			f" | spurious {totals[side + '_column_spurious']} | optional {totals[side + '_column_optional']} | with error {wrong_column_count}"
			f" | fields {totals[side + '_column_field_errors']}/{(column_total - column_omitted) * COMPARED_COLUMN_FIELD_COUNT}")
		table_total = totals["tables"]
		table_omitted = totals[side + "_table_omitted"]
		wrong_tables = totals[side + "_wrong_table"]
		print(f"{side} tables: right {table_total - table_omitted - wrong_tables}/{table_total} = {100 * (table_total - table_omitted - wrong_tables) / table_total:.1f}%"
			f" | omitted {table_omitted} | optional {totals[side + '_table_optional']} | spurious {totals[side + '_table_spurious']}"
			f" | with label error {totals[side + '_wrong_label']} of {totals['label_tables']} labelled"
			f" | label fields {totals[side + '_label_field_errors']} | inventory fields {totals[side + '_inventory_field_errors']}"
			f" | column fields {totals[side + '_column_field_errors']} | checklist fields {totals[side + '_checklist_field_errors']}")
	print("field errors by side:", sorted(field_errors_by_side.items(), key=lambda item: -item[1]))
	print("error types by side:", sorted(error_types.items(), key=lambda item: -item[1]))
	value_rows = [row for row in decision_rows if row["field"] in VALUE_FIELDS]
	print("value/letter/unit diff rows:", Counter((row["doc_id"][:20], row["field"], row["decision"]) for row in value_rows))
	print("decision rows:", len(decision_rows), Counter(row["decision"] for row in decision_rows))
	print("decision rows by category:", Counter((CategoryOf(row), row["decision"]) for row in decision_rows))
	print("both_acceptable fields:", Counter(PlainField(row["field"]) for row in decision_rows if row["decision"] == "both_acceptable").most_common(12))
	print("origin:", Counter(row["origin"] for row in dataset_rows))
	print("variable_standardized:", Counter(row["variable_standardized"] for row in dataset_rows).most_common())
	print("other by doc:", Counter(row["doc_id"] for row in dataset_rows if row["variable_standardized"] == "other"))
	print("other variables:", Counter((row["doc_id"][:12], row["variable"][:60]) for row in dataset_rows if row["variable_standardized"] == "other").most_common(40))
	print("biotic_target:", Counter(row["biotic_target"] for row in dataset_rows).most_common())
	print("treatment_type:", Counter(row["treatment_type"] for row in dataset_rows).most_common())
	print("statistic:", Counter(row["statistic"] for row in dataset_rows).most_common())
	print("value_kind:", Counter(row["value_kind"] for row in dataset_rows).most_common())
	print("organism_stage:", Counter(row["organism_stage"] for row in dataset_rows).most_common())
	print("unit:", Counter(row["unit"] for row in dataset_rows).most_common(25))
	print("crop_stage_status:", Counter(row["crop_stage_status"] for row in dataset_rows).most_common())
	print("inherited:", Counter(entry for row in dataset_rows for entry in row["inherited"].split("; ") if entry))
	for field in ("cultivar", "dose_and_unit", "application_stages", "crop_stage", "significance_letter", "active_ingredient_or_input",
			"dispersion_as_printed", "unit", "statistic", "value"):
		empty = sum(1 for row in dataset_rows if row[field] in (None, ""))
		print(f"null record {field}: {empty} ({100 * empty / len(dataset_rows):.1f}%)")
	for field in ("location", "affiliation", "season_or_year", "water_regime", "tillage_system", "previous_crop", "sowing_date",
			"harvest_date", "cultivar", "biotic_target", "inoculation_or_infestation", "application_method", "spray_volume",
			"application_stages", "n_applications", "seeding_rate_or_spacing", "base_fertilization", "n_reps"):
		empty = sum(1 for row in trial_rows if row[field] in (None, ""))
		print(f"null trial {field}: {empty}/{len(trial_rows)}")
	trial_of = {(row["doc_id"], row["trial_id"]): row for row in trial_rows}
	print("environment:", Counter(row["environment"] for row in trial_rows), "study_kind:", Counter(row["study_kind"] for row in trial_rows))
	print("water_regime:", Counter(row["water_regime"] for row in trial_rows), "tillage_system:", Counter(row["tillage_system"] for row in trial_rows))
	print("trial biotic_target:", Counter(row["biotic_target"] for row in trial_rows))
	print("records by environment:", Counter(trial_of[(row["doc_id"], row["trial_id"])]["environment"] for row in dataset_rows))
	print("records by water_regime:", Counter(trial_of[(row["doc_id"], row["trial_id"])]["water_regime"] for row in dataset_rows))
	print("plant_part:", Counter(row["plant_part"] for row in dataset_rows).most_common())
	print("factor_level filled:", sum(1 for row in dataset_rows if row["factor_level"]))
	print("pooled trials:", sum(1 for row in trial_rows if row["pooled_from"] not in ("", "[]")))
	print("source_inconsistency filled (record):", sum(1 for row in dataset_rows if row["source_inconsistency"]),
		"(record or table):", sum(1 for row in dataset_rows if row["source_inconsistency"] or row["table_source_inconsistency"]),
		"trials:", sum(1 for row in trial_rows if row["source_inconsistency"]))
	print("from text:", sum(1 for row in dataset_rows if row["table_or_figure"] == "text"),
		"from figure:", sum(1 for row in dataset_rows if row["table_or_figure"].lower().startswith(("fig", "gráf", "graf"))))
	print("empty decision_ids:", sum(1 for row in dataset_rows if not row["decision_ids"]))

	# Tomato round, same split, for the cascade comparison
	print("wheat cascade groups:", sorted(CascadeGroupErrors(os.path.join(ROOT, "qa", "decisions.csv")).items()))
	print("tomato cascade groups:", sorted(CascadeGroupErrors(os.path.join(ROOT, "..", "tomate", "qa", "decisions.csv")).items()))

	# Self-check: every adjudicated record once, every record points to a trial, and no long copy is left
	assert len(dataset_rows) == sum(doc_stats["final"] for doc_stats in stats.values())
	assert len({row["record_id"] for row in dataset_rows}) == len(dataset_rows)
	assert len({(row["doc_id"], row["trial_id"]) for row in trial_rows}) == len(trial_rows)
	assert all((row["doc_id"], row["trial_id"]) in trial_of for row in dataset_rows)
	assert len(decision_rows) == sum(sum(1 for _ in csv.DictReader(open(path, encoding="utf-8-sig"))) for path in glob.glob(os.path.join(ROOT, "adjudicated", "*_decisions.csv")))
	# Inheritance leaves no record without its column variable and standardized variable. statistic stays empty only where
	# the schema allows it: the print does not let one decide, and the table footnote summary says why (bassoi2009 Tabela 2)
	assert all(row["variable"] and row["variable_standardized"] for row in dataset_rows)
	assert all(row["statistic"] or row["table_footnote_summary"] for row in dataset_rows)
	# A 16-word copy is caught, a 15-word copy is not, and a 16-word quote is caught even when it is not in the PDF
	test_words = [f"w{index}" for index in range(30)]
	test_shingles = {tuple(test_words[index:index + MAX_QUOTE_WORDS + 1]) for index in range(len(test_words) - MAX_QUOTE_WORDS)}
	assert CopiedRuns(" ".join(test_words[:16]) + " x", test_shingles) == [" ".join(test_words[:16])]
	assert CopiedRuns(" ".join(test_words[:15]) + " x", test_shingles) == []
	assert LongQuotes("as in '" + " ".join(["z"] * 16) + "' here") and not LongQuotes("B's and '" + " ".join(["z"] * 15) + "'")
	# A dict repr with a long string of our own words is not a quote, but a long quote inside one of its strings still is
	assert not FindLongCopies(repr({"column_factor": " ".join(["z"] * 16)}), set())
	assert FindLongCopies(repr({"notes": "p3 says '" + " ".join(["z"] * 16) + "'"}), set())
	assert not long_copies, f"{len(long_copies)} cells copy more than {MAX_QUOTE_WORDS} words of the source: rewrite them in adjudicated/"


if __name__ == "__main__":
	main()
