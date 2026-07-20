# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import datetime
from io import BytesIO
import frappe
from frappe.model.document import Document
from frappe.utils import add_days
from frappe.utils.file_manager import get_file
import openpyxl
from openpyxl.utils import column_index_from_string


TAG_NAME_HEADER_TEXT = "Tag Name"

# Columns for the Min/Max/Avg child table (min_max_avg) — same layout for
# every plant, regardless of PLANT_CONFIG's hourly column range.
MIN_MAX_AVG_COLUMNS = {
	"engg_units_col": "D",
	"max_col": "F",
	"max_time_col": "G",
	"min_col": "H",
	"min_time_col": "I",
	"avg_col": "J",
}

PLANT_CONFIG = {
	"RSL Louhka": {
		"tag_name_col": "B",
		"hourly_start_col": "K",
		"hourly_end_col": "AH",
		"next_day_start_col": None,
		"next_day_end_col": None,

		"field_tag_map": {
			"float_zcpn": {"tag": "FT302", "label": "Steam Produced", "agg": "sum"},
			"float_pvrh": {"tag": "EKW2000", "label": "Power Generation", "agg": "sum"},
   			"float_reke": {"tag": "TE414", "label": "ESP Outlet Temp", "agg": "avg"},
   			"deaerator": {"tag": "FT102", "label": "Deartor", "agg": "sum"},

			"main_steam_pressure": {"tag": "PT302", "label": "Main Steam Pressure", "agg": "avg"},
			"main_steam_temprature": {"tag": "TT303", "label": "Main Steam Temprature", "agg": "avg"},
			"oxygen__at_eco_ol": {"tag": "AT401", "label": "Oxygen % At Eco O/L", "agg": "avg"},
			"boiler_feed_water_flow": {"tag": "FT301", "label": "Boiler Feed Water Flow", "agg": "sum"},
            "dm_flow_to_dearator": {"tag": "FT101", "label": "DM Flow To Dearator ", "agg": "sum"},
            "turbine_steam": {"tag": "FT2001", "label": "Turbine Steam", "agg": "sum"},


		},
	},
	"Superior Biofuels": {
		"tag_name_col": "B",
		"hourly_start_col": "K",
		"hourly_end_col": "AH",
		"next_day_start_col": None,
		"next_day_end_col": None,
		"field_tag_map": {
			"float_zcpn": {"tag": "FT303", "label": "Steam Produced", "agg": "sum"}
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

		# Columns for the Min/Max/Avg child table (same layout for every plant).
		engg_col = column_index_from_string(MIN_MAX_AVG_COLUMNS["engg_units_col"])
		max_col = column_index_from_string(MIN_MAX_AVG_COLUMNS["max_col"])
		max_time_col = column_index_from_string(MIN_MAX_AVG_COLUMNS["max_time_col"])
		min_col = column_index_from_string(MIN_MAX_AVG_COLUMNS["min_col"])
		min_time_col = column_index_from_string(MIN_MAX_AVG_COLUMNS["min_time_col"])
		avg_col = column_index_from_string(MIN_MAX_AVG_COLUMNS["avg_col"])

		header_row = self.find_header_row(ws, tag_col)
		if not header_row:
			frappe.throw(
				f"Could not locate header row: no cell in column {config['tag_name_col']} matches "
				f"'{TAG_NAME_HEADER_TEXT}'."
			)

		tag_row_map = self.build_tag_row_map(ws, header_row, tag_col)

		# Plants with no next_day_start_col configured don't carry any
		# values forward — skip next-day column resolution and the
		# per-field carry-over sum entirely.
		has_next_day = config["next_day_start_col"] is not None
		if has_next_day:
			next_day_start_col = column_index_from_string(config["next_day_start_col"])
			next_day_end_col = (
				column_index_from_string(config["next_day_end_col"])
				if config["next_day_end_col"] else ws.max_column
			)

		missing = []
		carry_over_values = {}

		# min_max_avg is rebuilt fresh on every upload rather than accumulated —
		# it's a Min/Max/Avg-with-Time snapshot of the file just uploaded, so
		# old rows are cleared before appending the new ones.
		self.set("min_max_avg", [])

		for fieldname, cfg in config["field_tag_map"].items():
			tag = cfg["tag"]
			row_idx = tag_row_map.get(tag.upper())
			if not row_idx:
				missing.append(f"{tag} ({cfg['label']})")
				continue

			# "sum" for cumulative quantities (flow/energy), "avg" for instantaneous
			# readings (pressure/temperature/analyzer %). Defaults to "sum" for any
			# entry that hasn't been classified yet, matching prior behaviour.
			agg = cfg.get("agg", "sum")

			if agg == "avg":
				value = self.average_row_range(ws, row_idx, start_col, end_col)
				# Averages aren't cumulative — re-uploads replace, they don't stack.
				self.set(fieldname, value)
			else:
				total = self.sum_row_range(ws, row_idx, start_col, end_col)
				# Add to whatever is already stored for this field, rather than
				# overwriting it, so re-uploads accumulate instead of replacing.
				previous_value = self.get_stored_value(fieldname)
				self.set(fieldname, previous_value + total)

			# Only cumulative (sum) fields get carried forward into next day's
			# opening total — carrying an average forward doesn't mean anything.
			if has_next_day and agg == "sum":
				carry_total = self.sum_row_range(ws, row_idx, next_day_start_col, next_day_end_col)
				carry_over_values[fieldname] = carry_total

			# Append the Min/Max/Avg-with-Time snapshot row for this tag.
			self.append("min_max_avg", {
				"parameter_name": cfg["label"],
				"field_name": fieldname,
				"engg_units": self.get_cell_str(ws, row_idx, engg_col),
				"max_value": self.get_cell_float(ws, row_idx, max_col),
				"max_value_time": self.get_cell_time(ws, row_idx, max_time_col),
				"min_value": self.get_cell_float(ws, row_idx, min_col),
				"min_value_time": self.get_cell_time(ws, row_idx, min_time_col),
				"average_value": self.get_cell_float(ws, row_idx, avg_col),
			})

		if missing:
			frappe.msgprint(
				f"Tag(s) not found in uploaded sheet, field(s) left unchanged: {', '.join(missing)}"
			)

		# No next-day config -> no carry-over entry is created at all.
		if has_next_day and carry_over_values:
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

	@staticmethod
	def average_row_range(ws, row_idx, start_col, end_col):
		total = 0
		count = 0
		for col in range(start_col, end_col + 1):
			val = ws.cell(row=row_idx, column=col).value
			if isinstance(val, (int, float)):
				total += val
				count += 1
			elif isinstance(val, str):
				try:
					total += float(val.strip())
					count += 1
				except (ValueError, TypeError):
					pass
		# No numeric readings in range -> 0 rather than a ZeroDivisionError.
		return total / count if count else 0

	@staticmethod
	def get_cell_str(ws, row_idx, col):
		val = ws.cell(row=row_idx, column=col).value
		return str(val).strip() if val not in (None, "") else None

	@staticmethod
	def get_cell_float(ws, row_idx, col):
		val = ws.cell(row=row_idx, column=col).value
		if isinstance(val, (int, float)):
			return val
		if isinstance(val, str):
			try:
				return float(val.strip())
			except (ValueError, TypeError):
				return None
		return None

	@staticmethod
	def get_cell_time(ws, row_idx, col):
		"""Return HH:MM:SS for a time-only cell, or None if unreadable.
		openpyxl gives datetime.time/datetime.datetime; xlrd gives a raw
		day-fraction float (e.g. 0.25 == 06:00:00)."""
		val = ws.cell(row=row_idx, column=col).value
		if val is None or val == "":
			return None
		if isinstance(val, datetime.datetime):
			return val.time().strftime("%H:%M:%S")
		if isinstance(val, datetime.time):
			return val.strftime("%H:%M:%S")
		if isinstance(val, (int, float)):
			total_seconds = round(val * 86400) % 86400
			hh, rem = divmod(total_seconds, 3600)
			mm, ss = divmod(rem, 60)
			return f"{hh:02d}:{mm:02d}:{ss:02d}"
		return None


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