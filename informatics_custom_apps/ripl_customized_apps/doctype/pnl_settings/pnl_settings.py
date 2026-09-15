# Copyright (c) 2026, Rana Informatics and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PNLSettings(Document):
	def validate(self):
		self.validate_unique_section_names()
		self.validate_account_section_links()

	def validate_unique_section_names(self):
		seen = set()
		for row in self.sections:
			key = (row.section_name or "").strip().lower()
			if not key:
				frappe.throw(_("Row {0}: Section Name is required").format(row.idx))
			if key in seen:
				frappe.throw(_("Section Name '{0}' is repeated in row {1}. Section names must be unique.").format(row.section_name, row.idx))
			seen.add(key)

	def validate_account_section_links(self):
		valid_sections = {(row.section_name or "").strip() for row in self.sections}
		seen_accounts = set()
		for row in self.section_accounts:
			if not row.section:
				frappe.throw(_("Row {0}: Section is required for account {1}").format(row.idx, row.account_number))
			if row.section not in valid_sections:
				frappe.throw(_("Row {0}: Section '{1}' does not match any Section defined above").format(row.idx, row.section))
			if not row.account_number:
				frappe.throw(_("Row {0}: Account Number is required").format(row.idx))
			acc_key = (row.account_number or "").strip()
			if acc_key in seen_accounts:
				frappe.throw(_("Row {0}: Account Number '{1}' is already mapped to another section. An account number can only belong to one section.").format(row.idx, row.account_number))
			seen_accounts.add(acc_key)

	@staticmethod
	def get_active_settings():
		return frappe.get_single("PNL Settings")