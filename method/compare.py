# Compare the two independent transcriptions (A/*.json and B/*.json, schema v4: {trials, tables, records, end_checklist})
# Output: method/diff.csv, or method/diff_<doc_id>.csv when doc ids are given, with every trial field
# disagreement first, then every record field disagreement and every record present on one side only
# Copied from ferrugem-soja/method/compare.py. Changed for schema v3: trials are compared field by field
# (trials paired by trial_id), context fields left the records, and the site number comes from the
# trial_label of the record's trial
#
# Matching: records are grouped by (doc_id, page, table_or_figure). Inside a group each A/B pair
# gets a score from treatment, variable and position tokens (numbers, dates) plus small bonuses
# for same value and same crop_stage; pairs are taken greedily from the best score down.
# The value is only a tie-breaker, so a wrong value in A still pairs with the right cell in B
#
# Copied from doencas-feijao/method/compare.py for the cassava round (schema v4). Changed: field names
# (biotic_target, active_ingredient_or_input, planting_date, inoculation_or_infestation, harvest_age,
# spacing_or_density, study_kind, pooled_from), dispersion_as_printed and table_id compared on records,
# and the tables[] inventory compared too, paired by (page, label), with its table_level_labels field by field
#
# Copied from mandioca/method/compare.py for the rice blast round (schema v5). Changed: trial fields
# (crop_system, sowing_date, biotic_target; planting_date and harvest_age left), table_level_labels now
# carry crop_stage, crop_stage_refers_to, crop_stage_source_page and row_identity (a dict, compared as sorted JSON)
#
# Copied from brusone-arroz/method/compare.py for the tomato round (schema v6). Changed: trial fields
# (market_segment, growing_system, planting_date, harvest_period; crop_system and sowing_date left), crop_stage left
# table_level_labels for tables[].columns[], which are compared field by field (paired by column_id inside a paired
# table), and records are compared on the effective value after inheritance (record, column, table, trial), so a
# null that inherits the same value as the other side's written value is no longer a diff (rice RODADA lesson)
#
# Copied from tomate/method/compare.py for the wheat round (schema v7). Changed: trial fields (water_regime,
# tillage_system, previous_crop, sowing_date, harvest_date, spray_volume, seeding_rate_or_spacing, base_fertilization;
# market_segment, growing_system, planting_date, harvest_period and spacing_or_density left) and column fields
# (plant_part, factor_level)
#
# Usage: python compare.py [doc_id ...]   (paths are relative to this file)
import csv
import difflib
import glob
import json
import os
import re
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
A_DIR = os.path.join(ROOT, "A")
B_DIR = os.path.join(ROOT, "B")

# value first (compare_pair treats it apart); then every value-bearing or context field of schema v2.
# doc_id, page and table_or_figure are the group key; notes is free text and is not compared
COMPARED_FIELDS = ["value", "value_kind", "unit", "significance_letter", "statistic", "statistic_stated", "is_marginal",
	"treatment", "treatment_code", "treatment_type", "variable", "variable_standardized", "biotic_target", "trial_id",
	"table_id", "column_id", "cultivar", "crop_stage", "crop_stage_refers_to", "active_ingredient_or_input", "dose_and_unit",
	"dose_source_page", "application_stages", "n_applications", "dispersion_as_printed", "transformation_stated",
	"source_inconsistency"]
# Schema v3 trials block; notes and context_source_pages are not compared
TRIAL_FIELDS = ["trial_label", "study_kind", "pooled_from", "environment", "location", "affiliation", "season_or_year",
	"water_regime", "tillage_system", "previous_crop", "sowing_date", "harvest_date", "cultivar", "biotic_target",
	"inoculation_or_infestation", "application_method", "spray_volume", "application_stages", "n_applications",
	"seeding_rate_or_spacing", "base_fertilization", "n_reps", "design_notes", "source_inconsistency"]
# Schema v4 tables[] inventory; notes and skipped_reason are free text and are not compared
TABLE_FIELDS = ["kind", "trial_ids", "data_cells", "transcribed", "skipped_cells"]
LABEL_FIELDS = ["statistic", "statistic_stated", "statistic_source_page", "statistic_source_place", "transformation_stated",
	"treatment_type", "row_identity", "significance_test",
	"letters_meaning", "scale_meaning", "source_inconsistency"]
# Schema v6 tables[].columns[]; notes is free text and is not compared
COLUMN_FIELDS = ["header_as_printed", "variable_standardized", "unit", "organism_stage", "plant_part", "factor_level", "crop_stage", "crop_stage_refers_to",
	"crop_stage_source_page", "crop_stage_status", "statistic", "statistic_stated", "transformation_stated", "biotic_target"]
# Record field -> where a null inherits from, in order (schema v6: record, column, table, trial)
INHERITED = {
	"variable": [("column", "header_as_printed")],
	"variable_standardized": [("column", "variable_standardized")],
	"unit": [("column", "unit")],
	"crop_stage": [("column", "crop_stage")],
	"crop_stage_refers_to": [("column", "crop_stage_refers_to")],
	"statistic": [("column", "statistic"), ("labels", "statistic")],
	"statistic_stated": [("column", "statistic_stated"), ("labels", "statistic_stated")],
	"transformation_stated": [("column", "transformation_stated"), ("labels", "transformation_stated")],
	"treatment_type": [("labels", "treatment_type")],
	"biotic_target": [("column", "biotic_target"), ("trial", "biotic_target")],
	"application_stages": [("trial", "application_stages")],
	"n_applications": [("trial", "n_applications")],
}
MIN_PAIR_SCORE = 3.0


def fill_effective(records, trials, tables):
	# Write the inherited value into every null record field, so A and B are compared on what the record means
	trials_by_id = {trial["trial_id"]: trial for trial in trials}
	tables_by_id = {table["table_id"]: table for table in tables}
	for record in records:
		table = tables_by_id.get(record.get("table_id")) or {}
		sources = {
			"trial": trials_by_id.get(record.get("trial_id")) or {},
			"labels": table.get("table_level_labels") or {},
			"column": next((column for column in table.get("columns") or [] if column.get("column_id") == record.get("column_id")), {}),
		}
		record["_inherited"] = set()
		for field, chain in INHERITED.items():
			if record.get(field) is not None:
				continue
			for source, source_field in chain:
				if sources[source].get(source_field) is not None:
					record[field] = sources[source][source_field]
					record["_inherited"].add(field)
					break


def norm(text):
	if text is None:
		return ""
	# row_identity is a dict; compare it as sorted JSON so key order does not count
	if isinstance(text, (dict, list)):
		text = json.dumps(text, sort_keys=True, ensure_ascii=False)
	text = unicodedata.normalize("NFKD", str(text))
	text = "".join(ch for ch in text if not unicodedata.combining(ch))
	text = text.lower().replace("±", " pm ")
	return re.sub(r"[^a-z0-9]+", " ", text).strip()


def norm_label(text):
	# filippi2007: A copies "FIG. 1" and "TABELA 1" as printed, B writes "Figura 1" and "Tabela 1", so the
	# figure abbreviation is spelled out before tables and record groups are paired
	return re.sub(r"^fig(?:ura)?\b", "figura", norm(text))


def norm_unit(text):
	# kg/ha, Kg ha-1 and kg.ha-1 are the same unit
	text = norm(text).replace(" 1", " ")
	return re.sub(r"\s+", "", text)


def number_tokens(text):
	return set(re.findall(r"\d+(?:[.,]\d+)?", text or ""))


def similarity(a, b):
	a, b = norm(a), norm(b)
	if not a and not b:
		return 1.0
	if a == b:
		return 1.0
	tokens_a, tokens_b = set(a.split()), set(b.split())
	jaccard = len(tokens_a & tokens_b) / max(1, len(tokens_a | tokens_b))
	ratio = difflib.SequenceMatcher(None, a, b).ratio()
	return max(jaccard, ratio)


def position_text(record):
	return " ".join(str(record.get(k) or "") for k in ("treatment", "variable", "crop_stage", "trial_label", "cultivar"))


def pair_score(a, b):
	score = 3.0 * similarity(a["treatment"], b["treatment"])
	score += 3.0 * similarity(a["variable"], b["variable"])
	numbers_a, numbers_b = number_tokens(position_text(a)), number_tokens(position_text(b))
	if numbers_a or numbers_b:
		score += 2.0 * len(numbers_a & numbers_b) / max(1, len(numbers_a | numbers_b))
	else:
		score += 2.0
	if norm(a["treatment"]) == norm(b["treatment"]):
		score += 1.0
	# Schema v2 treatment_code: the annex rows print only the code (TRAT 3), so one side may write
	# "3" and the other the name from the products table; the same printed code is strong evidence
	if norm(a.get("treatment_code")) and norm(a.get("treatment_code")) == norm(b.get("treatment_code")):
		score += 3.0
	if a.get("value") == b.get("value"):
		score += 0.75
	if norm(a.get("crop_stage")) == norm(b.get("crop_stage")):
		score += 0.25
	return score


def text_field_differs(field, value_a, value_b):
	if field == "unit":
		return norm_unit(value_a) != norm_unit(value_b)
	# prabhu1990: norm() drops '*', so a '*' significance mark on one side and nothing on the other passed as equal
	if field == "significance_letter":
		return str(value_a or "").strip() != str(value_b or "").strip()
	return norm(value_a) != norm(value_b)


def site_number(record):
	# Cooperative circulars print one small table per site inside the same annex page ("3. Fundação MS"),
	# all with the same TRAT 1..15 rows, so the site number in trial_label is part of the group key
	# A separator ";" or " - " goes between the protocol name and the site ("Protocolo X - 1. Desafios agro")
	match = re.search(r"(?:^|; | - )(\d+)\. ", record.get("trial_label") or "")
	return int(match.group(1)) if match else 0


def load(directory, name):
	with open(os.path.join(directory, name), encoding="utf-8") as handle:
		data = json.load(handle)
	# Schema v3: copy the trial_label onto each record so site_number and position_text still see it
	labels = {trial["trial_id"]: trial.get("trial_label") for trial in data["trials"]}
	for record in data["records"]:
		record["trial_label"] = labels.get(record.get("trial_id"))
	fill_effective(data["records"], data["trials"], data.get("tables", []))
	return data["trials"], data["records"], data.get("tables", [])


def compare_pair(a, b):
	rows = []
	value_a, value_b = a.get("value"), b.get("value")
	printed_a, printed_b = (a.get("value_as_printed") or "").strip(), (b.get("value_as_printed") or "").strip()
	if value_a != value_b:
		rows.append(("value", value_a, value_b, printed_a, printed_b))
	elif printed_a.replace(" ", "") != printed_b.replace(" ", ""):
		rows.append(("value_as_printed", value_a, value_b, printed_a, printed_b))
	# A field both sides inherited is already one row at its trial, table or column, so it is not repeated per record
	inherited_both = a.get("_inherited", set()) & b.get("_inherited", set())
	for field in COMPARED_FIELDS[1:]:
		if field in inherited_both:
			continue
		if text_field_differs(field, a.get(field), b.get(field)):
			rows.append((field, a.get(field), b.get(field), printed_a, printed_b))
	return rows


def renumber_trials_b_by_tables(trials_a, trials_b, records_a, records_b):
	# kluthcouski2003: A t5 = Tabela 8 and t6 = text p22, B the other way round, and the labels differ
	# too much for the label pairing ("Costa (1999)" vs "Costa (1999), podridões radiculares")
	# So each trial is identified by the (page, table) cells its records sit in, and B ids are rewritten
	# only when every trial footprint on one side equals exactly one footprint on the other
	def footprints(trials, records):
		cells = {trial["trial_id"]: set() for trial in trials}
		for record in records:
			if record.get("trial_id") in cells:
				cells[record["trial_id"]].add((record["page"], norm(record["table_or_figure"])))
		return cells
	cells_a, cells_b = footprints(trials_a, records_a), footprints(trials_b, records_b)
	if len(cells_a) != len(cells_b) or len(cells_a) < 2:
		return
	new_id_for_b = {}
	for trial_id_a, footprint_a in cells_a.items():
		same = [trial_id_b for trial_id_b, footprint_b in cells_b.items() if footprint_a and footprint_b == footprint_a]
		if len(same) != 1 or same[0] in new_id_for_b:
			return
		new_id_for_b[same[0]] = trial_id_a
	for trial_b in trials_b:
		trial_b["trial_id"] = new_id_for_b[trial_b["trial_id"]]
	for record in records_b:
		if record.get("trial_id") in new_id_for_b:
			record["trial_id"] = new_id_for_b[record["trial_id"]]


def renumber_trials_b_by_values(trials_a, trials_b, records_a, records_b):
	# barros2001: Tabela 1 holds two trials (casa de vegetação and campo columns), so the (page, table)
	# footprint is the same for both and the labels differ ("teste de emergência em campo" vs "Campo")
	# Last resort: each trial is the set of (page, table, value) it holds, and each A trial takes the B trial
	# with the highest overlap, only when every pairing is one to one and overlaps more than half
	def footprints(trials, records):
		cells = {trial["trial_id"]: set() for trial in trials}
		for record in records:
			if record.get("trial_id") in cells:
				cells[record["trial_id"]].add((record["page"], norm(record["table_or_figure"]), record.get("value")))
		return cells
	cells_a, cells_b = footprints(trials_a, records_a), footprints(trials_b, records_b)
	if len(cells_a) != len(cells_b) or len(cells_a) < 2:
		return
	new_id_for_b = {}
	for trial_id_a, footprint_a in cells_a.items():
		best_trial_id_b, best_overlap = None, 0.0
		for trial_id_b, footprint_b in cells_b.items():
			overlap = len(footprint_a & footprint_b) / max(1, len(footprint_a | footprint_b))
			if overlap > best_overlap:
				best_trial_id_b, best_overlap = trial_id_b, overlap
		if best_trial_id_b is None or best_overlap <= 0.5 or best_trial_id_b in new_id_for_b:
			return
		new_id_for_b[best_trial_id_b] = trial_id_a
	for trial_b in trials_b:
		trial_b["trial_id"] = new_id_for_b[trial_b["trial_id"]]
	for record in records_b:
		if record.get("trial_id") in new_id_for_b:
			record["trial_id"] = new_id_for_b[record["trial_id"]]


def renumber_trials_b(trials_a, trials_b, records_b):
	# The two transcribers can number the same trials in a different order (rava2002: A t1 = TO, B t1 = GO),
	# so B trials are paired with A trials by trial_label and B ids are rewritten to the A ids
	# Only when every trial on both sides has a label and each A label has one clear best B label
	if len(trials_a) != len(trials_b) or len(trials_a) < 2:
		return
	for trial in trials_a + trials_b:
		if not trial.get("trial_label"):
			return
	new_id_for_b = {}
	for trial_a in trials_a:
		best_trial_b = None
		best_score = 0.0
		for trial_b in trials_b:
			score = similarity(trial_a["trial_label"], trial_b["trial_label"])
			if score > best_score:
				best_score = score
				best_trial_b = trial_b
		if best_trial_b is None or best_score < 0.8 or best_trial_b["trial_id"] in new_id_for_b:
			return
		new_id_for_b[best_trial_b["trial_id"]] = trial_a["trial_id"]
	for trial_b in trials_b:
		trial_b["trial_id"] = new_id_for_b[trial_b["trial_id"]]
	for record in records_b:
		if record.get("trial_id") in new_id_for_b:
			record["trial_id"] = new_id_for_b[record["trial_id"]]


def pair_columns_by_values(table_a, table_b, records_a, records_b):
	# utumi1999: A puts each parenthesis column right after its yield column (c1 yield, c2 its %), B puts all yields
	# first and all % after, so pairing by column_id compared yield with % and flagged 364 record column_ids.
	# Columns are paired by the (treatment, value) cells their records share, best overlap first
	def footprints(table, records):
		cells = {}
		for record in records:
			if record.get("table_id") == table["table_id"]:
				cells.setdefault(record.get("column_id"), set()).add((norm(record.get("treatment")), record.get("value")))
		return cells
	cells_a, cells_b = footprints(table_a, records_a), footprints(table_b, records_b)
	candidates = sorted(((len(cells_a[ia] & cells_b[ib]), ia, ib) for ia in cells_a for ib in cells_b), key=lambda c: (-c[0], str(c[1]), str(c[2])))
	pairs, used_b = {}, set()
	for overlap, column_a, column_b in candidates:
		if overlap == 0 or column_a in pairs or column_b in used_b:
			continue
		pairs[column_a] = column_b
		used_b.add(column_b)
	return pairs


def compare_tables(doc_id, tables_a, tables_b, records_b, records_a=None):
	rows = []
	new_column_for_b = {}
	# Two entries can share (page, label), like two 'text' blocks on one page (souza2021 B: weather and values on p6).
	# A dict keyed by (page, label) dropped one of them without a row, so keep a list and take the same kind first
	by_key_b = {}
	for table in tables_b:
		by_key_b.setdefault((table["page"], norm_label(table["label"])), []).append(table)
	new_id_for_b = {}
	for table_a in tables_a:
		candidates = by_key_b.get((table_a["page"], norm_label(table_a["label"])), [])
		same_kind = [table for table in candidates if table["kind"] == table_a["kind"]]
		table_b = (same_kind or candidates or [None])[0]
		if table_b is not None:
			candidates.remove(table_b)
		if table_b is None:
			rows.append([doc_id, table_a["page"], table_a["label"], "only_in_A", "table", table_a["table_id"], "", "", "", "", "", "", "", "", "", ""])
			continue
		new_id_for_b[table_b["table_id"]] = table_a["table_id"]
		if table_a["table_id"] != table_b["table_id"]:
			rows.append([doc_id, table_a["page"], table_a["label"], "wording", "table_id", table_a["table_id"], table_b["table_id"], "", "", "", "", table_a["table_id"], table_b["table_id"], "", "", ""])
		labels_a, labels_b = table_a.get("table_level_labels") or {}, table_b.get("table_level_labels") or {}
		fields = [(field, table_a.get(field), table_b.get(field)) for field in TABLE_FIELDS]
		fields += [("table_level_labels." + field, labels_a.get(field), labels_b.get(field)) for field in LABEL_FIELDS]
		columns_b = {column["column_id"]: column for column in table_b.get("columns") or []}
		column_pairs = pair_columns_by_values(table_a, table_b, records_a or [], records_b)
		paired_b = set(column_pairs.values())
		for column_a in table_a.get("columns") or []:
			# A column with no shared cell falls back to the same id, unless that B id is already paired by values
			column_id_b = column_pairs.get(column_a["column_id"])
			if column_id_b is None and column_a["column_id"] not in paired_b:
				column_id_b = column_a["column_id"]
			column_b = columns_b.pop(column_id_b, None)
			if column_b is not None:
				new_column_for_b[(table_b["table_id"], column_id_b)] = column_a["column_id"]
			if column_b is None:
				rows.append([doc_id, table_a["page"], table_a["label"], "only_in_A", "column", table_a["table_id"] + "." + column_a["column_id"], "", "", "", "", "", "", "", "", "", ""])
				continue
			fields += [("columns.%s.%s" % (column_a["column_id"], field), column_a.get(field), column_b.get(field)) for field in COLUMN_FIELDS]
		for column_id in columns_b:
			rows.append([doc_id, table_a["page"], table_a["label"], "only_in_B", "column", "", table_b["table_id"] + "." + column_id, "", "", "", "", "", "", "", "", ""])
		for field, value_a, value_b in fields:
			if text_field_differs(field, value_a, value_b):
				rows.append([doc_id, table_a["page"], table_a["label"], kind_of(field, value_a, value_b), field,
					table_a["table_id"], table_b["table_id"], "", "", "", "", value_a, value_b, "", "", ""])
	for table_b in [table for candidates in by_key_b.values() for table in candidates]:
		rows.append([doc_id, table_b["page"], table_b["label"], "only_in_B", "table", "", table_b["table_id"], "", "", "", "", "", "", "", "", ""])
	for record in records_b:
		key = (record.get("table_id"), record.get("column_id"))
		if key in new_column_for_b:
			record["column_id"] = new_column_for_b[key]
		if record.get("table_id") in new_id_for_b:
			record["table_id"] = new_id_for_b[record["table_id"]]
	return rows


def kind_of(field, value_a, value_b):
	if field in ("value", "value_as_printed", "significance_letter"):
		return "value_mismatch" if field != "significance_letter" else "letter_mismatch"
	if value_a in (None, "", []) or value_b in (None, "", []):
		return "null_vs_text"
	if number_tokens(str(value_a)) != number_tokens(str(value_b)):
		return "numbers_differ"
	return "wording"


def main(doc_ids):
	if doc_ids:
		names = [doc_id + ".json" for doc_id in doc_ids]
		out_path = os.path.join(HERE, "diff_%s.csv" % "_".join(doc_ids)) if len(doc_ids) == 1 else os.path.join(HERE, "diff_selected.csv")
	else:
		names = sorted(os.path.basename(p) for p in glob.glob(os.path.join(A_DIR, "*.json")) if os.path.exists(os.path.join(B_DIR, os.path.basename(p))))
		out_path = os.path.join(HERE, "diff.csv")
	header = ["diff_id", "doc_id", "page", "table_or_figure", "kind", "field", "a_index", "b_index",
		"treatment_a", "treatment_b", "variable_a", "variable_b", "a_value", "b_value",
		"value_as_printed_a", "value_as_printed_b", "match_score"]
	out_rows = []
	totals = {"a": 0, "b": 0, "pairs": 0}
	for name in names:
		trials_a, records_a, tables_a = load(A_DIR, name)
		trials_b, records_b, tables_b = load(B_DIR, name)
		renumber_trials_b(trials_a, trials_b, records_b)
		renumber_trials_b_by_tables(trials_a, trials_b, records_a, records_b)
		renumber_trials_b_by_values(trials_a, trials_b, records_a, records_b)
		# Trials first: one row per differing field, trials paired by trial_id
		trials_by_id_b = {trial["trial_id"]: trial for trial in trials_b}
		for trial_a in trials_a:
			trial_b = trials_by_id_b.pop(trial_a["trial_id"], None)
			if trial_b is None:
				out_rows.append([name[:-5], "", "trials", "only_in_A", "trial", trial_a["trial_id"], "", "", "", "", "", "", "", "", "", ""])
				continue
			for field in TRIAL_FIELDS:
				if text_field_differs(field, trial_a.get(field), trial_b.get(field)):
					out_rows.append([name[:-5], "", "trials", kind_of(field, trial_a.get(field), trial_b.get(field)), field,
						trial_a["trial_id"], trial_b["trial_id"], "", "", "", "", trial_a.get(field), trial_b.get(field), "", "", ""])
		for trial_id in trials_by_id_b:
			out_rows.append([name[:-5], "", "trials", "only_in_B", "trial", "", trial_id, "", "", "", "", "", "", "", "", ""])
		# Tables second: paired by (page, label) since the two sides may number table_ids in another order
		# (alves2012: A k4 = text p4 and k5 = Figura 2, B the other way round). B table_ids on records are
		# rewritten to the A id of the same table so the record table_id is only flagged when the table differs
		out_rows.extend(compare_tables(name[:-5], tables_a, tables_b, records_b, records_a))
		totals["a"] += len(records_a)
		totals["b"] += len(records_b)
		# The site number only splits groups when both sides number the same sites. bettiol1992: B labels its
		# trials with the methods section number ("5. Efeito de...") and A does not, so no record paired
		sites_a = {site_number(record) for record in records_a}
		sites_b = {site_number(record) for record in records_b}
		bUseSiteNumber = sites_a == sites_b
		groups = {}
		for side, records in (("a", records_a), ("b", records_b)):
			for index, record in enumerate(records):
				key = (record["page"], norm_label(record["table_or_figure"]), site_number(record) if bUseSiteNumber else 0)
				groups.setdefault(key, {"a": [], "b": []})[side].append(index)
		for key in sorted(groups, key=lambda k: (k[0], k[1])):
			indexes_a, indexes_b = groups[key]["a"], groups[key]["b"]
			candidates = []
			for ia in indexes_a:
				for ib in indexes_b:
					score = pair_score(records_a[ia], records_b[ib])
					if score >= MIN_PAIR_SCORE:
						candidates.append((score, ia, ib))
			# Best pairs first; ties keep file order so parallel tables line up
			candidates.sort(key=lambda c: (-c[0], c[1], c[2]))
			used_a, used_b, pairs = set(), set(), []
			for score, ia, ib in candidates:
				if ia in used_a or ib in used_b:
					continue
				used_a.add(ia)
				used_b.add(ib)
				pairs.append((score, ia, ib))
			totals["pairs"] += len(pairs)
			for score, ia, ib in sorted(pairs, key=lambda p: p[1]):
				a, b = records_a[ia], records_b[ib]
				for field, value_a, value_b, printed_a, printed_b in compare_pair(a, b):
					out_rows.append([name[:-5], a["page"], a["table_or_figure"], kind_of(field, value_a, value_b), field,
						ia, ib, a["treatment"], b["treatment"], a["variable"], b["variable"], value_a, value_b,
						printed_a, printed_b, round(score, 2)])
			for ia in indexes_a:
				if ia not in used_a:
					a = records_a[ia]
					out_rows.append([name[:-5], a["page"], a["table_or_figure"], "only_in_A", "record", ia, "",
						a["treatment"], "", a["variable"], "", a["value"], "", a["value_as_printed"], "", ""])
			for ib in indexes_b:
				if ib not in used_b:
					b = records_b[ib]
					out_rows.append([name[:-5], b["page"], b["table_or_figure"], "only_in_B", "record", "", ib,
						"", b["treatment"], "", b["variable"], "", b["value"], "", b["value_as_printed"], ""])
	with open(out_path, "w", encoding="utf-8", newline="") as handle:
		writer = csv.writer(handle)
		writer.writerow(header)
		for number, row in enumerate(out_rows, 1):
			writer.writerow(["D%04d" % number] + row)
	print("A records %d, B records %d, matched pairs %d, diff rows %d" % (totals["a"], totals["b"], totals["pairs"], len(out_rows)))


def self_check():
	assert norm_unit("Kg ha-1") == norm_unit("kg/ha")
	assert norm("Labóratório") == "laboratorio"
	assert norm_label("FIG. 1") == norm_label("Figura 1") == "figura 1" and norm_label("TABELA 2") == norm_label("Tabela 2")
	assert text_field_differs("significance_letter", None, "*") and not text_field_differs("significance_letter", "a ", "a")
	assert number_tokens("Aug,7 (4)") == {"7", "4"}
	assert site_number({"trial_label": "Experimento com fungicidas registrados; 18. Fundação Mato Grosso"}) == 18
	assert site_number({"trial_label": "Protocolo FUNGICIDAS REGISTRADOS - 1. Desafios agro, Chapadão do Sul, MS"}) == 1
	assert site_number({"trial_label": "19. TAGRO"}) == 19 and site_number({"trial_label": None}) == 0
	a = {"treatment": "Untreated", "variable": "Infestation Aug,7 (4)", "crop_stage": None, "value": 1.0}
	b_right = {"treatment": "Untreated", "variable": "Infestation (mean) Aug,7 (4)", "crop_stage": None, "value": 2.0}
	b_wrong = {"treatment": "Untreated", "variable": "Infestation (mean) Aug,9 (6)", "crop_stage": None, "value": 1.0}
	assert pair_score(a, b_right) > pair_score(a, b_wrong)
	trials_a = [{"trial_id": "t1", "trial_label": "Fazenda Barreira da Cruz-TO"}, {"trial_id": "t2", "trial_label": "Embrapa Arroz e Feijão-GO"}]
	trials_b = [{"trial_id": "t1", "trial_label": "Embrapa Arroz e Feijão-GO"}, {"trial_id": "t2", "trial_label": "Fazenda Barreira da Cruz-TO"}]
	records_b = [{"trial_id": "t1"}, {"trial_id": "t2"}]
	renumber_trials_b(trials_a, trials_b, records_b)
	assert [t["trial_id"] for t in trials_b] == ["t2", "t1"] and [r["trial_id"] for r in records_b] == ["t2", "t1"]
	trials_a = [{"trial_id": "t1"}, {"trial_id": "t2"}]
	trials_b = [{"trial_id": "t1"}, {"trial_id": "t2"}]
	records_a = [{"trial_id": "t1", "page": 23, "table_or_figure": "Tabela 8"}, {"trial_id": "t2", "page": 22, "table_or_figure": "text"}]
	records_b = [{"trial_id": "t2", "page": 23, "table_or_figure": "Tabela 8"}, {"trial_id": "t1", "page": 22, "table_or_figure": "text"}]
	renumber_trials_b_by_tables(trials_a, trials_b, records_a, records_b)
	assert [r["trial_id"] for r in records_b] == ["t1", "t2"] and [t["trial_id"] for t in trials_b] == ["t2", "t1"]
	tables_a = [{"table_id": "k4", "page": 4, "label": "text", "kind": "text"}, {"table_id": "k5", "page": 4, "label": "Figura 2", "kind": "figure_labeled"}]
	tables_b = [{"table_id": "k4", "page": 4, "label": "Figura 2", "kind": "figure_labeled"}, {"table_id": "k5", "page": 4, "label": "text", "kind": "text"}]
	records_b = [{"table_id": "k5"}]
	table_rows = compare_tables("doc", tables_a, tables_b, records_b)
	assert records_b[0]["table_id"] == "k4" and [row[4] for row in table_rows] == ["table_id", "table_id"]
	# Columns numbered in another order pair by their cells, and the B record takes the A column_id
	tables_a = [{"table_id": "k1", "page": 6, "label": "Tabela 1", "kind": "results", "columns": [{"column_id": "c1", "unit": "t/ha"}, {"column_id": "c2", "unit": "%"}]}]
	tables_b = [{"table_id": "k1", "page": 6, "label": "TABELA 1", "kind": "results", "columns": [{"column_id": "c1", "unit": "%"}, {"column_id": "c2", "unit": "t/ha"}]}]
	records_a = [{"table_id": "k1", "column_id": "c1", "treatment": "Carmen", "value": 61.2}, {"table_id": "k1", "column_id": "c2", "treatment": "Carmen", "value": 84.0}]
	records_b = [{"table_id": "k1", "column_id": "c2", "treatment": "Carmen", "value": 61.2}, {"table_id": "k1", "column_id": "c1", "treatment": "Carmen", "value": 84.0}]
	table_rows = compare_tables("doc", tables_a, tables_b, records_b, records_a)
	assert [r["column_id"] for r in records_b] == ["c1", "c2"] and not [row for row in table_rows if ".unit" in row[4]]
	trials_a = [{"trial_id": "t1"}, {"trial_id": "t2"}]
	trials_b = [{"trial_id": "t1"}, {"trial_id": "t2"}]
	records_a = [{"trial_id": "t1", "page": 4, "table_or_figure": "Tabela 1", "value": 49.0}, {"trial_id": "t2", "page": 4, "table_or_figure": "Tabela 1", "value": 52.0}]
	records_b = [{"trial_id": "t2", "page": 4, "table_or_figure": "Tabela 1", "value": 49.0}, {"trial_id": "t1", "page": 4, "table_or_figure": "Tabela 1", "value": 52.0}]
	renumber_trials_b_by_values(trials_a, trials_b, records_a, records_b)
	assert [r["trial_id"] for r in records_b] == ["t1", "t2"]
	# A null record field takes the column, then the table label, then the trial; a written field stays
	tables = [{"table_id": "k1", "table_level_labels": {"treatment_type": "insecticide", "statistic": "mean"},
		"columns": [{"column_id": "c1", "header_as_printed": "% frutos", "unit": "%", "statistic": None, "biotic_target": None}]}]
	trials = [{"trial_id": "t1", "biotic_target": "multiple", "n_applications": 13}]
	records = [{"trial_id": "t1", "table_id": "k1", "column_id": "c1", "treatment_type": "control", "n_applications": 0}]
	fill_effective(records, trials, tables)
	assert records[0]["variable"] == "% frutos" and records[0]["statistic"] == "mean" and records[0]["biotic_target"] == "multiple"
	assert records[0]["treatment_type"] == "control" and records[0]["n_applications"] == 0
	# Inherited on both sides: no record row; written on one side and inherited different on the other: a row
	record_a = {"value": 1, "variable": None, "column_id": "c1", "table_id": "k1", "trial_id": "t1"}
	record_b = {"value": 1, "variable": None, "column_id": "c1", "table_id": "k1", "trial_id": "t1"}
	fill_effective([record_a], trials, tables)
	fill_effective([record_b], trials, [{"table_id": "k1", "columns": [{"column_id": "c1", "header_as_printed": "% dos frutos"}]}])
	assert not [row for row in compare_pair(record_a, record_b) if row[0] == "variable"]
	record_b = {"value": 1, "variable": "% dos frutos", "column_id": "c1", "table_id": "k1", "trial_id": "t1"}
	fill_effective([record_b], trials, tables)
	assert [row for row in compare_pair(record_a, record_b) if row[0] == "variable"]


if __name__ == "__main__":
	self_check()
	if "--check" not in sys.argv:
		main([arg for arg in sys.argv[1:] if not arg.startswith("--")])
