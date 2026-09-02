# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ItemGroupWarehouseMapping(Document):
	def on_update(self):
		self.clear_warehouse_map_cache()

	def on_trash(self):
		self.clear_warehouse_map_cache()

	def after_insert(self):
		self.clear_warehouse_map_cache()

	def clear_warehouse_map_cache(self):
		if self.company and self.branch:
			frappe.cache().delete_value(
				f"igwm::{self.company}::{self.branch}"
			)

	def before_save(self):
		if not self.is_new():
			old = frappe.db.get_value(
				"Warehouse", self.name, ["company", "custom_branch"], as_dict=True
			)
			if old and (old.company != self.company or old.custom_branch != self.custom_branch):
				frappe.cache().delete_value(f"capital_wh::{old.company}::{old.custom_branch}")