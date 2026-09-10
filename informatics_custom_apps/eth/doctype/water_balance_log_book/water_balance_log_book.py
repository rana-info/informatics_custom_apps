# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WaterBalanceLogBook(Document):
	
	def validate(self):
		self.validate_water_balance()
		self.calculate_values()
	def validate_water_balance(self):
		exists=frappe.db.exists(
			"Water Balance Log Book",
			{
				"date": self.date,
				"plant": self.plant,}
		)	
		if exists and self.get("__islocal"):
			frappe.throw("Water Balance Log Book already exists for this date and plant.")

	def calculate_values(self):
		self.total_effluent_genration = self.total_condensate_genration + self.effluent
		self.ground_water_extraction = self.float_apqq + self.borewell_2