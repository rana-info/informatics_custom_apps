# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class AMTool(Document):
	def validate(self):
		if self.wrong_account and self.wrong_account == self.correct_account:
			frappe.throw("Wrong Account and Correct Account cannot be the same.")
		if self.wrong_cost_center and self.wrong_cost_center == self.correct_cost_center:
			frappe.throw("Wrong Cost Center and Correct Cost Center cannot be the same.")
			
	def on_submit(self):
		if self.asset_category_update:
			self.update_category()
		elif self.accounting_dimension_update:
			self.update_accounting()

	def update_category(self):
		doc=frappe.get_doc("Asset", self.asset, update_modified=False)
		doc.db_set("item_code", self.item_code, update_modified=False)
		doc.db_set("item_name", self.item_name, update_modified=False)
		doc.db_set("asset_category", self.asset_category, update_modified=False)

		#Journal Entry Account Update
		frappe.db.set_value(
        "Journal Entry Account",
        {
            "reference_type": "Asset",
            "reference_name": self.asset,
            "account": self.wrong_account
        },
        {
            "account": self.correct_account
        },
        update_modified=False
    	)

		 # ---------- GL Entry : update account ----------
		frappe.db.set_value(
			"GL Entry",
			{
				"voucher_type": "Journal Entry",
				"voucher_subtype": "Depreciation Entry",
				"against_voucher_type": "Asset",
				"against_voucher": self.asset,
				"account": self.wrong_account
			},
			{
				"account": self.correct_account
			},
			update_modified=False
			)

		# ---------- GL Entry : update against ----------
		frappe.db.set_value(
			"GL Entry",
			{
				"voucher_type": "Journal Entry",
				"voucher_subtype": "Depreciation Entry",
				"against_voucher_type": "Asset",
				"against_voucher": self.asset,
				"against": self.wrong_account
			},
			{
				"against": self.correct_account
			},
			update_modified=False
			)
	
	def update_accounting(self):
		doc=frappe.get_doc("Asset", self.asset)
		update_common = {}
		if self.correct_cost_center:
			update_common["cost_center"] = self.correct_cost_center
		if self.segment:
			update_common["segment"] = self.segment
			doc.db_set("segment", self.segment, update_modified=False)
		if self.section:
			update_common["section"] = self.section
			doc.db_set("section", self.section, update_modified=False)
	
		if self.wrong_cost_center==doc.cost_center and self.correct_cost_center:
			doc.db_set("cost_center", self.correct_cost_center, update_modified=False)
		
		#Journal Entry Account Update
		frappe.db.set_value(
        "Journal Entry Account",
        {
            "reference_type": "Asset",
            "reference_name": self.asset,
            "cost_center": self.wrong_cost_center
        },
        update_common,
        update_modified=False
  		  )
		
		# ---------- GL Entry :Depreciation ----------
		frappe.db.set_value(
        "GL Entry",
        {
            "voucher_type": "Journal Entry",
            "voucher_subtype": "Depreciation Entry",
            "against_voucher_type": "Asset",
            "against_voucher": self.asset,
            "cost_center": self.wrong_cost_center
        },
        update_common,
        update_modified=False
		)

		# ---------- GL Entry (Direct Asset Entry) ----------
		frappe.db.set_value(
			"GL Entry",
			{
				"voucher_type": "Asset",
				"voucher_no": self.asset,
				"cost_center": self.wrong_cost_center
			},
			update_common,
			update_modified=False
		)
		# ---------- Asset Repair ----------
		frappe.db.set_value(
			"Asset Repair",
			{
				"asset": self.asset,
				"cost_center": self.wrong_cost_center
			},
			update_common,
			update_modified=False
		)
		# ---------- Asset Capitalization ----------
		frappe.db.set_value(
			"Asset Capitalization",
			{
				"target_asset": self.asset,
				"cost_center": self.wrong_cost_center
			},
			{
				"cost_center": self.correct_cost_center,
				"segment": self.segment
			},
			update_modified=False
		)