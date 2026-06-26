# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


def get_expected_opening_entry_type(purpose):
	"""Visitor trips have a fixed direction: they always open with 'In'
	(visitor enters premises first, leaves later).

	Shift / Co-Work trips don't have a fixed direction - these are contract
	cabs, so a vehicle might open with 'Out' (about to leave) or 'In'
	(returning from a previous trip, e.g. dropped someone home overnight).
	Returns None when no direction is enforced.
	"""
	if purpose == "Visitor":
		return "In"
	return None


class VehicleLogBook(Document):

	def validate(self):
		self.calculate_distance()
		self.validate_opening_entry_type()

	def calculate_distance(self):
		if self.in_km and self.out_km:
			try:
				self.distance = abs(int(self.in_km) - int(self.out_km))
			except (ValueError, TypeError):
				pass

	def validate_opening_entry_type(self):
		# Diesel Issue isn't a vehicle movement at all - no direction to enforce
		if self.entry_type == "Diesel Issue":
			return

		# Only enforced on the opening leg - skip once the trip is already closed
		if self.is_completed:
			return

		expected = get_expected_opening_entry_type(self.purpose)
		if not expected:
			# No fixed direction for this purpose (e.g. Shift / Co-Work contract cabs)
			return

		if self.entry_type and self.entry_type != expected and not self.in_progress:
			frappe.throw(
				_("For purpose {0}, the first entry must be of type {1}").format(
					frappe.bold(self.purpose), frappe.bold(expected)
				)
			)

	def before_save(self):
		if self.vehicle_number:
			self.vehicle_number = self.vehicle_number.upper()

	def before_submit(self):
		# Only In/Out movements are "trips" with an opening/closing leg.
		# A Diesel Issue entry is a standalone record, not part of a trip.
		if self.entry_type in ("In", "Out") and not self.in_progress and not self.is_completed:
			self.in_progress = 1


def validate_closing_km(doc, values):
	"""The odometer reading on the closing leg can't be lower than the
	reading recorded on the opening leg. Doesn't apply to Visitor (no km)."""
	if doc.purpose == "Visitor":
		return

	if doc.entry_type == "Out":
		opening_km, opening_label = doc.out_km, _("Out Km")
		closing_km, closing_label = values.get("in_km"), _("In Km")
	else:
		opening_km, opening_label = doc.in_km, _("In Km")
		closing_km, closing_label = values.get("out_km"), _("Out Km")

	try:
		opening_km = int(opening_km)
		closing_km = int(closing_km)
	except (ValueError, TypeError):
		return

	if closing_km < opening_km:
		frappe.throw(
			_("{0} ({1}) cannot be less than {2} ({3}).").format(
				closing_label, closing_km, opening_label, opening_km
			)
		)


@frappe.whitelist()
def close_entry(docname, values):
	"""Close an open Vehicle Log Book entry by filling in the missing leg
	(In or Out) on the already-submitted document.

	`values` is the dict coming from the "Close Entry" dialog in vehicle_log_book.js
	"""
	if isinstance(values, str):
		values = frappe.parse_json(values)

	doc = frappe.get_doc("Vehicle Log Book", docname)

	if not frappe.has_permission(doc.doctype, "write", doc=doc):
		frappe.throw(_("You are not permitted to close this entry."))

	if doc.docstatus != 1:
		frappe.throw(_("Only submitted entries can be closed."))

	if not doc.in_progress or doc.is_completed:
		frappe.throw(_("This entry is already closed or was never opened."))

	validate_closing_km(doc, values)

	# Submitted docs are normally locked, so we update via db_set
	allowed_fields = ("in_time", "in_km", "out_time", "out_km")
	for fieldname in allowed_fields:
		if values.get(fieldname) not in (None, ""):
			doc.db_set(fieldname, values.get(fieldname))

	doc.reload()
	doc.calculate_distance()
	doc.db_set("distance", doc.distance)

	doc.db_set("is_completed", 1)
	doc.db_set("in_progress", 0)

	return doc.name