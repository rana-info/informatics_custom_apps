# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import re

import frappe
from frappe.model.document import Document


class HPLC(Document):
	pass


@frappe.whitelist()
def parse_hplc_pdf(docname, fieldname, file_url=None):
	doc = frappe.get_doc("HPLC", docname)

	if not file_url:
		file_url = doc.get(fieldname)
	if not file_url:
		frappe.throw(frappe._("No file attached in {0}").format(fieldname))

	files = frappe.get_all(
		"File",
		filters={"file_url": file_url, "attached_to_name": docname, "attached_to_doctype": "HPLC"},
		fields=["name"],
		limit=1,
	)
	if not files:
		files = frappe.get_all("File", filters={"file_url": file_url}, fields=["name"], limit=1)
	if not files:
		frappe.throw(frappe._("Could not find the File record for {0}").format(fieldname))

	file_doc = frappe.get_doc("File", files[0].name)
	file_path = file_doc.get_full_path()

	injection_date, rows, debug_text = extract_hplc_data(file_path)

	if not injection_date and not rows:
		frappe.log_error(
			title="HPLC PDF parse: nothing extracted",
			message="File: {0}\n\n--- extracted text ---\n{1}".format(file_path, debug_text),
		)
		frappe.msgprint(
			frappe._(
				"Could not extract any data from the PDF. Check the Error Log "
				"(HPLC PDF parse: nothing extracted) for the raw text that was read."
			),
			indicator="orange",
		)
		return {"injection_date": None, "rows": []}

	if doc.get(fieldname) != file_url:
		doc.set(fieldname, file_url)

	if injection_date and not doc.injection_date:
		doc.injection_date = injection_date


	doc.set("data", [r for r in doc.get("data") if r.get("source_field") != fieldname])

	for row in rows:
		doc.append(
			"data",
			{

				"parameter_name": row["name"],
				"amount": row["amount"],
				"source_field": fieldname,
			},
		)

	doc.save(ignore_permissions=True)

	return {"injection_date": injection_date, "rows": rows}


def extract_hplc_data(file_path):
	text = _read_pdf_text(file_path)
	injection_date = _extract_injection_date(text)
	rows = _extract_rows(text)
	return injection_date, rows, text


def _read_pdf_text(file_path):
	try:
		from pypdf import PdfReader
	except ImportError:
		from PyPDF2 import PdfReader

	reader = PdfReader(file_path)
	return "\n".join((page.extract_text() or "") for page in reader.pages)


def _extract_injection_date(text):
	match = re.search(
		r"Injection\s*date\s*:?\s*(\d{4}-\d{2}-\d{2})\s+\d{2}:\d{2}:\d{2}(?:[+\-]\d{2}:?\d{2})?",
		text,
	)
	return match.group(1).strip() if match else None


def _extract_rows(text):
	header_match = re.search(r"\bName\b.*?\bAmount\b.*?\n", text)
	if not header_match:
		return []

	totals_match = re.search(r"Totals\s+w/o\s+ISTD", text)
	start = header_match.end()
	end = totals_match.start() if totals_match else len(text)
	body = text[start:end]

	lines = [ln.strip() for ln in body.splitlines() if ln.strip()]

	records = []
	current = []
	for ln in lines:
		if re.match(r"^[A-Za-z]", ln):
			if current:
				records.append(" ".join(current))
			current = [ln]
		elif current:
			current.append(ln)
	if current:
		records.append(" ".join(current))

	number_re = re.compile(r"-?\d+\.?\d*")
	rows = []
	for rec in records:
		name_match = re.match(r"^([A-Za-z][A-Za-z\s]*?)\s+\d", rec)
		if not name_match:
			continue
		name = name_match.group(1).strip()

		numbers = [n for n in number_re.findall(rec) if n not in ("", ".")]
		if len(numbers) < 2:
			continue

		try:
			amount = float(numbers[-2])
		except ValueError:
			continue

		rows.append({"name": name, "amount": amount})

	return rows

@frappe.whitelist()
def clear_hplc_data(docname, fieldname, file_url=None):
	doc = frappe.get_doc("HPLC", docname)
	doc.set(fieldname, None)

	removed = 0
	if file_url:
		files = frappe.get_all("File", filters={"file_url": file_url}, fields=["name"], limit=1)
		if files:
			file_doc = frappe.get_doc("File", files[0].name)
			_, rows, _ = extract_hplc_data(file_doc.get_full_path())
			targets = {(r["name"].strip().lower(), round(r["amount"], 3)) for r in rows}

			kept = []
			for r in doc.get("data"):
				key = ((r.parameter_name or "").strip().lower(), round(r.amount or 0, 3))
				if r.get("source_field") == fieldname or key in targets:
					removed += 1
					continue
				kept.append(r)
			doc.set("data", kept)

	doc.save(ignore_permissions=True)

	return {"cleared": fieldname, "removed": removed}