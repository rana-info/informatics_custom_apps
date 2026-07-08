# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

from io import BytesIO
import frappe
from frappe.model.document import Document
from frappe.utils import add_days
from frappe.utils.file_manager import get_file
import openpyxl
from openpyxl.utils import column_index_from_string


TAG_NAME_HEADER_TEXT = "Tag Name"

PLANT_CONFIG = {
	"RSL Louhka": {
		"tag_name_col": "B",
		"hourly_start_col": "K",
		"hourly_end_col": "AB",
		"next_day_start_col": "AC",
		"next_day_end_col": None,
		"field_tag_map": {
			"float_zcpn": {"tag": "FT302", "label": "Steam Produced"},
			"float_pvrh": {"tag": "EKW2000", "label": "Power Generation"},
		},
	},
	"Superior Biofuels": {
		"tag_name_col": "B",
		"hourly_start_col": "K",
		"hourly_end_col": "AB",
		"next_day_start_col": "AC",
		"next_day_end_col": None,
		"field_tag_map": {
			"float_zcpn": {"tag": "FT303", "label": "Steam Produced"}
		},
	},
}

XLSX_ZIP_SIGNATURE = b"PK\x03\x04"
XLS_OLE_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


class DMRBoilerAndTurbineParameters(Document):

	def validate(self):
		if self.excel_file and self.has_value_changed("excel_file"):
			self.populate_from_excel()

	def populate_from_excel(self):
		config = self.get_plant_config()
		ws = self.get_worksheet()

		tag_col = column_index_from_string(config["tag_name_col"])
		start_col = column_index_from_string(config["hourly_start_col"])
		end_col = column_index_from_string(config["hourly_end_col"])

		header_row = self.find_header_row(ws, tag_col)
		if not header_row:
			frappe.throw(
				f"Could not locate header row: no cell in column {config['tag_name_col']} matches "
				f"'{TAG_NAME_HEADER_TEXT}'."
			)

		tag_row_map = self.build_tag_row_map(ws, header_row, tag_col)

		next_day_start_col = column_index_from_string(config["next_day_start_col"])
		next_day_end_col = (
			column_index_from_string(config["next_day_end_col"])
			if config["next_day_end_col"] else ws.max_column
		)

		missing = []
		carry_over_values = {}

		for fieldname, cfg in config["field_tag_map"].items():
			tag = cfg["tag"]
			row_idx = tag_row_map.get(tag.upper())
			if not row_idx:
				missing.append(f"{tag} ({cfg['label']})")
				continue

			total = self.sum_row_range(ws, row_idx, start_col, end_col)

			# Add to whatever is already stored for this field, rather than
			# overwriting it, so re-uploads accumulate instead of replacing.
			previous_value = self.get_stored_value(fieldname)
			self.set(fieldname, previous_value + total)

			carry_total = self.sum_row_range(ws, row_idx, next_day_start_col, next_day_end_col)
			carry_over_values[fieldname] = carry_total

		if missing:
			frappe.msgprint(
				f"Tag(s) not found in uploaded sheet, field(s) left unchanged: {', '.join(missing)}"
			)

		if carry_over_values:
			self.upsert_next_day_carry_over(carry_over_values)

	def get_stored_value(self, fieldname):
		"""Value currently saved in the DB for this field on this record.
		0 for a new (unsaved) document."""
		if self.is_new():
			return 0
		return frappe.db.get_value(self.doctype, self.name, fieldname) or 0

	def get_plant_config(self):
		if not self.plant:
			frappe.throw("Plant is not set on this record — cannot determine column layout for parsing.")
		config = PLANT_CONFIG.get(self.plant)
		if not config:
			frappe.throw(
				f"No column/tag mapping configured for plant '{self.plant}'. "
				f"Add an entry for it in PLANT_CONFIG."
			)
		return config

	def upsert_next_day_carry_over(self, carry_over_values):
		if not self.date:
			frappe.msgprint("Date not set on this record — skipping next-day carry-over update.")
			return

		next_date = add_days(self.date, 1)
		filters = {"company": self.company, "plant": self.plant, "date": next_date}

		existing_name = frappe.db.get_value(self.doctype, filters, "name")

		if existing_name:
			for fieldname, carry_total in carry_over_values.items():
				existing_value = frappe.db.get_value(self.doctype, existing_name, fieldname) or 0
				new_value = existing_value + carry_total
				frappe.db.set_value(
					self.doctype, existing_name, fieldname, new_value, update_modified=True
				)
		else:
			new_doc = frappe.new_doc(self.doctype)
			new_doc.company = self.company
			new_doc.plant = self.plant
			new_doc.date = next_date
			for fieldname, carry_total in carry_over_values.items():
				new_doc.set(fieldname, carry_total)
			# excel_file is mandatory on this doctype but this is a system-generated
			# carry-over record with no upload of its own, so mandatory check is bypassed.
			new_doc.flags.ignore_mandatory = True
			new_doc.insert(ignore_permissions=True)

	def get_worksheet(self):
		fname, fcontent = get_file(self.excel_file)
		if not fcontent:
			frappe.throw(f"Uploaded file '{fname}' is empty or could not be read.")
		if isinstance(fcontent, str):
			fcontent = fcontent.encode("utf-8")

		head = fcontent.lstrip()[:8]

		if head.startswith(XLSX_ZIP_SIGNATURE):
			wb = openpyxl.load_workbook(BytesIO(fcontent), data_only=True)
			return wb.active

		if head.startswith(XLS_OLE_SIGNATURE):
			return self.read_legacy_xls(fcontent, fname)

		frappe.throw(
			f"'{fname}' is not a recognizable Excel file (checked .xlsx and legacy .xls). "
			f"First bytes: {fcontent[:40]!r}"
		)

	@staticmethod
	def read_legacy_xls(fcontent, fname):
		try:
			import xlrd
		except ImportError:
			frappe.throw(
				"This is a legacy binary .xls file, which needs the 'xlrd' package to read. "
				"Run: bench pip install xlrd"
			)
		try:
			book = xlrd.open_workbook(file_contents=fcontent)
			sheet = book.sheet_by_index(0)
		except Exception as e:
			frappe.throw(f"Could not parse '{fname}' as a legacy .xls file: {e}")
		return _XlrdSheetAdapter(sheet)

	@staticmethod
	def find_header_row(ws, tag_col, max_scan_rows=15):
		for row in range(1, min(max_scan_rows, ws.max_row) + 1):
			val = ws.cell(row=row, column=tag_col).value
			if val and str(val).strip().lower() == TAG_NAME_HEADER_TEXT.lower():
				return row
		return None

	@staticmethod
	def build_tag_row_map(ws, header_row, tag_col):
		tag_row_map = {}
		for row in range(header_row + 1, ws.max_row + 1):
			val = ws.cell(row=row, column=tag_col).value
			if val:
				tag_row_map[str(val).strip().upper()] = row
		return tag_row_map

	@staticmethod
	def sum_row_range(ws, row_idx, start_col, end_col):
		total = 0
		for col in range(start_col, end_col + 1):
			val = ws.cell(row=row_idx, column=col).value
			if isinstance(val, (int, float)):
				total += val
			elif isinstance(val, str):
				try:
					total += float(val.strip())
				except (ValueError, TypeError):
					pass
		return total


class _XlrdSheetAdapter:
	def __init__(self, xlrd_sheet):
		self._sheet = xlrd_sheet
		self.max_row = xlrd_sheet.nrows
		self.max_column = xlrd_sheet.ncols

	def cell(self, row, column):
		r, c = row - 1, column - 1
		if r < 0 or r >= self._sheet.nrows or c < 0 or c >= self._sheet.ncols:
			return _CellAdapter(None)
		return _CellAdapter(self._sheet.cell_value(r, c))


class _CellAdapter:
	def __init__(self, value):
		self.value = value