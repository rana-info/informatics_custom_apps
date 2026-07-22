# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt


import frappe
from frappe.model.document import Document
from frappe.utils import get_link_to_form
from frappe.utils.data import get_time, getdate
from datetime import datetime


class WarehouseDumpEntry(Document):

	def validate(self):
		# Always force Inward, this doctype is for Inward entries only
		self.entry_type = "Inward"

		if self.gross_weight and self.tare_weight:
			self.net_weight = self.gross_weight - self.tare_weight
			if self.net_weight <= 0:
				frappe.throw("Net weight can't be zero")

		if self.items:
			for row in self.items:
				if not row.accepted_quantity:
					frappe.throw("Accepted qty in row {} can't be zero".format(row.idx))

	def before_submit(self):
		mandatory_fields = [
			"date", "time", "supplier", "driver_name", "vehicle_number",
			"vehicle_owner", "weighment_date", "inward_date", "outward_date",
			"purchase_orders", "items", "tare_weight", "gross_weight", "net_weight",
			"vehicle_image", "weighment_slip_image"
		]
		for field in mandatory_fields:
			if not self.get(field):
				formatted_field = field.replace("_", " ").capitalize()
				frappe.throw(f"{frappe.bold(formatted_field)} is mandatory for this transaction")

	def on_submit(self):
		self.create_gate_entry_and_weighment()

	def create_gate_entry_and_weighment(self):
		gate_entry = frappe.new_doc("Gate Entry")
		meta_g = frappe.get_meta("Gate Entry")
		child_tables = {}
		data = self.as_dict()

		for key, value in data.items():
			if isinstance(value, list) and all(isinstance(item, dict) for item in value):
				child_tables[key] = value

		for key, value in data.items():
			if key not in child_tables and meta_g.has_field(key):
				gate_entry.set(key, value)

		for table_field, rows in child_tables.items():
			if meta_g.has_field(table_field):
				gate_entry.set(table_field, [])
				for row in rows:
					row = dict(row)
					row.pop("docstatus", None)
					row.pop("name", None)
					gate_entry.append(table_field, row)

		datetime_str = f"{getdate(self.date)} {get_time(self.time)}"
		creation = safe_parse_datetime(datetime_str)
		gate_entry.set("creation", creation)
		gate_entry.set("modified", creation)
		gate_entry.is_in_progress = 0
		gate_entry.is_completed = 1

		gate_entry.insert(ignore_permissions=True)
		gate_entry.submit()
		frappe.db.set_value("Gate Entry", gate_entry.name, "creation", creation, update_modified=False)
		frappe.db.set_value("Gate Entry", gate_entry.name, "modified", creation, update_modified=False)

		frappe.msgprint(
			title="Gate Entry Created",
			indicator="orange",
			alert=True,
			realtime=True,
			msg=f"Gate Entry Created: {gate_entry.name}"
		)

		weighment_name = None
		if self.weighment_date and self.inward_date and self.outward_date and self.tare_weight and self.gross_weight and self.net_weight:
			weighment = frappe.new_doc("Weighment")
			meta_w = frappe.get_meta("Weighment")
			child_tables = {}
			data = self.as_dict()

			for key, value in data.items():
				if isinstance(value, list) and all(isinstance(item, dict) for item in value):
					child_tables[key] = value

			for key, value in data.items():
				if key not in child_tables and meta_w.has_field(key):
					weighment.set(key, value)

			for table_field, rows in child_tables.items():
				if meta_w.has_field(table_field):
					weighment.set(table_field, [])
					for row in rows:
						row = dict(row)
						row.pop("docstatus", None)
						row.pop("name", None)
						weighment.append(table_field, row)

			weighment.gate_entry_number = gate_entry.name
			weighment.is_completed = 1

			datetime_str = f"{getdate(self.date)} {get_time(self.time)}"
			creation = safe_parse_datetime(datetime_str)
			weighment.set("creation", creation)
			weighment.set("modified", creation)

			weighment.insert(ignore_permissions=True)
			weighment.submit()
			frappe.db.set_value("Weighment", weighment.name, "creation", creation, update_modified=False)
			frappe.db.set_value("Weighment", weighment.name, "modified", creation, update_modified=False)

			frappe.msgprint(
				title="Weighment Created",
				indicator="orange",
				alert=True,
				realtime=True,
				msg=f"Weighment Created: {weighment.name}"
			)

			# Commit the Gate Entry / Weighment now. create_purchase_receipt_manually()
			# belongs to a separate app (weighment_server) and can fail for reasons
			# outside our control (e.g. a missing custom field/migration). If it fails
			# after this point, we don't want that to roll back the records already
			# created and submitted above.
			frappe.db.commit()

			try:
				weighment.create_purchase_receipt_manually()
			except Exception:
				frappe.log_error(
					frappe.get_traceback(),
					"Warehouse Dump Entry: Purchase Receipt auto-creation failed"
				)
				frappe.msgprint(
					title="Purchase Receipt Not Created",
					indicator="red",
					alert=True,
					realtime=True,
					msg=(
						f"Gate Entry {gate_entry.name} and Weighment {weighment.name} were created "
						f"successfully, but the Purchase Receipt could not be created automatically. "
						f"Please create it manually from the Weighment record. "
						f"(Error has been logged for admin review.)"
					)
				)

			weighment_name = weighment.name

		# Keep a log/reference back on this record without re-triggering validate/submit
		self.db_set("gate_entry", gate_entry.name, update_modified=False)
		if weighment_name:
			self.db_set("weighment", weighment_name, update_modified=False)

		# Force final Gate Entry status LAST - after Weighment/PR creation, since those
		# steps can trigger Gate Entry's own hooks and flip is_in_progress back to 1.
		frappe.db.set_value("Gate Entry", gate_entry.name, "is_in_progress", 0, update_modified=False)
		frappe.db.set_value("Gate Entry", gate_entry.name, "is_completed", 1, update_modified=False)

	@frappe.whitelist()
	def fetch_purchase_orders(self):
		if not self.supplier:
			frappe.throw("Please select Supplier first")
		if not self.branch:
			frappe.throw("Please select Branch first")

		existing = [d.purchase_orders for d in self.purchase_orders if d.purchase_orders]

		filters = {
			"supplier": self.supplier,
			"branch": self.branch,
			"docstatus": 1,
			"status": ["not in", ["Completed", "Closed", "Cancelled"]],
			"gate_entry_received_percentage": ["<", 100],
		}
		if existing:
			filters["name"] = ["not in", existing]

		pos = frappe.get_all("Purchase Order", filters=filters, pluck="name")

		if not pos:
			frappe.msgprint("No new Purchase Orders found for this Supplier and Branch")
			return False

		for po in pos:
			self.append("purchase_orders", {"purchase_orders": po})

		return True

	@frappe.whitelist()
	def get_item_from_po(self):
		if not self.purchase_orders or len(self.purchase_orders) != 1:
			frappe.throw("Please keep exactly 1 Purchase Order in the table before fetching items")

		if self.purchase_orders:
			self.items = []
			for po in self.purchase_orders:
				if po.purchase_orders:
					data = frappe.get_all("Purchase Order Item", {
						"parent": po.purchase_orders
					}, ["*"])

					for d in data:
						self.append("items", {
							"item_code": d.get("item_code"),
							"item_name": d.get("item_name"),
							"qty": d.get("qty"),
							"is_weighable_item": True if frappe.db.get_value("Item Group", {"name": d.item_group}, ["custom_is_weighment_required"]) == "Yes" else False,
							"description": d.get("description"),
							"gst_hsn_code": d.get("gst_hsn_code"),
							"brand": d.get("brand"),
							"is_ineligible_for_itc": d.get("is_ineligible_for_itc"),
							"stock_uom": d.get("stock_uom"),
							"uom": d.get("uom"),
							"conversion_factor": d.get("conversion_factor"),
							"stock_qty": d.get("stock_qty"),
							"actual_received_qty": d.get("received_qty"),
							"rate": d.get("rate"),
							"amount": d.get("amount"),
							"item_tax_template": d.get("item_tax_template"),
							"gst_treatment": d.get("gst_treatment"),
							"rate_company_currency": d.get("base_rate"),
							"amount_company_currency": d.get("base_amount"),
							"weight_per_unit": d.get("weight_per_unit"),
							"weight_uom": d.get("weight_uom"),
							"total_weight": d.get("total_weight"),
							"warehouse": d.get("warehouse"),
							"material_request": d.get("material_request"),
							"material_request_item": d.get("material_request_item"),
							"delivery_note_item": d.get("delivery_note_item"),
							"purchase_order": d.get("parent"),
							"purchase_order_item": d.get("name"),
							"expense_account": d.get("expense_account"),
							"branch": d.get("branch"),
							"cost_center": d.get("cost_center"),
						})

			return True


def safe_parse_datetime(datetime_str):
	try:
		return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S.%f")
	except ValueError:
		return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")