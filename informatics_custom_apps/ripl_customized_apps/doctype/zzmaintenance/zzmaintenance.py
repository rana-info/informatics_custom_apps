# Copyright (c) 2026, Dexciss and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import datetime
from frappe.utils import flt, get_link_to_form, now_datetime
from frappe.utils.data import get_time, getdate

# Keys that must never be copied from this Single doc to Gate Entry / Weighment
SKIP_KEYS = {
	"doctype", "name", "owner", "creation", "modified", "modified_by",
	"docstatus", "idx", "parent", "parentfield", "parenttype",
}
SKIP_ROW_KEYS = {
	"name", "owner", "creation", "modified", "modified_by",
	"docstatus", "idx", "parent", "parentfield", "parenttype",
}

REQUIRED_FIELDS = [
	"maintenance_type", "date", "time", "supplier", "driver_name",
	"vehicle_number", "vehicle_owner", "weighment_date", "inward_date",
	"outward_date", "purchase_orders", "items", "tare_weight", "gross_weight", "net_weight",
]


RELEASE_CARD_AFTER_COMPLETE = True


@frappe.whitelist()
def get_delivery_notes_for_item_group(doctype, txt, searchfield, start, page_len, filters):
	filters = frappe.parse_json(filters) if isinstance(filters, str) else (filters or {})
	branch = filters.get("branch")
	item_group = filters.get("item_group")
	if not branch or not item_group:
		return []

	search_text = f"%{txt or ''}%"
	return frappe.db.sql(
		"""
		SELECT DISTINCT dn.name, dn.customer, dn.branch
		FROM `tabDelivery Note` dn
		INNER JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
		WHERE dn.docstatus = 0
			AND dn.branch = %(branch)s
			AND (dn.custom_weighment IS NULL OR dn.custom_weighment = '')
			AND dni.item_group = %(item_group)s
			AND (dn.name LIKE %(search_text)s OR dn.customer LIKE %(search_text)s)
		ORDER BY dn.name
		LIMIT %(page_len)s OFFSET %(start)s
		""",
		{
			"branch": branch,
			"item_group": item_group,
			"search_text": search_text,
			"page_len": page_len,
			"start": start,
		},
	)



class ZZMaintenance(Document):

	def _split(self):
		"""Return (scalar_data, child_tables) from this doc."""
		data = self.as_dict()
		child_tables = {k: v for k, v in data.items()
			if isinstance(v, list) and all(isinstance(i, dict) for i in v)}
		scalars = {k: v for k, v in data.items() if k not in child_tables and k not in SKIP_KEYS}
		return scalars, child_tables

	def _copy_to(self, target, scalars, child_tables, only_changed=False, skip_blank=()):
		meta = frappe.get_meta(target.doctype)
		for key, value in scalars.items():
			if not meta.has_field(key):
				continue
			if key in skip_blank and not value:
				continue
			if only_changed and target.get(key) == value:
				continue
			target.set(key, value)

		for table_field, rows in child_tables.items():
			if not meta.has_field(table_field):
				continue
			target.set(table_field, [])
			for row in rows:
				target.append(table_field, {k: v for k, v in row.items() if k not in SKIP_ROW_KEYS})

	def _set_if_field_exists(self, doc, fieldname, value):
		if value is not None and doc.meta.has_field(fieldname):
			doc.set(fieldname, value)

	def _populate_contact_and_location(self, doc):
		location = self.location or frappe.db.get_value("Branch", self.branch, "custom_location")
		transporter = self.transporter or doc.get("transporter")
		transporter_name = (
			frappe.db.get_value("Supplier", transporter, "supplier_name")
			if transporter else None
		) or self.transporter_name or doc.get("transporter_name")
		driver_name = self.driver_name
		driver_contact = self.driver_contact
		if self.vehicle_owner == "Company Owned" and self.driver:
			driver = frappe.db.get_value(
				"Driver", self.driver, ["full_name", "cell_number"], as_dict=True
			)
			if driver:
				driver_name = driver.full_name
				driver_contact = driver.cell_number
		self._set_if_field_exists(doc, "location", location)
		self._set_if_field_exists(doc, "transporter", transporter)
		self._set_if_field_exists(doc, "transporter_name", transporter_name)
		self._set_if_field_exists(doc, "driver_name", driver_name)
		self._set_if_field_exists(doc, "driver_contact", driver_contact)

	def _persist_transporter(self, doc, source_doc=None):
		transporter = (
			self.transporter
			or (source_doc.get("transporter") if source_doc else None)
			or doc.get("transporter")
		)
		if not transporter:
			return

		transporter_name = (
			frappe.db.get_value("Supplier", transporter, "supplier_name")
			or self.transporter_name
			or (source_doc.get("transporter_name") if source_doc else None)
			or doc.get("transporter_name")
		)
		if not transporter_name:
			frappe.throw(f"Supplier {frappe.bold(transporter)} has no Supplier Name")
		values = {
			fieldname: value
			for fieldname, value in (
				("transporter", transporter),
				("transporter_name", transporter_name),
			)
			if doc.meta.has_field(fieldname)
		}
		if values:
			frappe.db.set_value(doc.doctype, doc.name, values, update_modified=False)
			for fieldname, value in values.items():
				doc.set(fieldname, value)
			saved_values = frappe.db.get_value(
				doc.doctype, doc.name, list(values), as_dict=True
			)
			if any(saved_values.get(field) != value for field, value in values.items()):
				frappe.throw(
					f"Could not persist transporter details on {doc.doctype} {doc.name}"
				)

	def _populate_weighment_delivery_notes(self, weighment):
		weighment.set("delivery_notes", [])
		seen_notes = set()
		for row in self.delivery_note or []:
			if row.delivery_note and row.delivery_note not in seen_notes:
				weighment.append("delivery_notes", {"delivery_note": row.delivery_note})
				seen_notes.add(row.delivery_note)

		net_weight = flt(self.net_weight)
		self._set_if_field_exists(weighment, "total_weight", net_weight)
		self._set_if_field_exists(
			weighment,
			"minimum_permissible_weight",
			net_weight,
		)
		self._set_if_field_exists(
			weighment,
			"maximum_permissible_weight",
			net_weight,
		)

	def _creation_dt(self):
		return safe_parse_datetime(f"{getdate(self.date)} {get_time(self.time)}")

	def _stamp(self, doc, creation):
		frappe.db.set_value(doc.doctype, doc.name, "creation", creation, update_modified=False)
		frappe.db.set_value(doc.doctype, doc.name, "modified", creation, update_modified=False)

	def _notify(self, title, msg):
		frappe.msgprint(title=title, indicator="orange", alert=True, realtime=True, msg=msg)

	def _assign_card(self):
		"""Pick a free card of this plant and mark it assigned.

		SELECT ... FOR UPDATE locks the row until this request commits, so two
		simultaneous requests can never grab the same card.
		"""
		conditions = ["is_assigned = 0"]
		values = {}
		if self.branch:
			conditions.append("branch = %(branch)s")
			values["branch"] = self.branch
		# if self.location:
		# 	conditions.append("location = %(location)s")
		# 	values["location"] = self.location

		card = frappe.db.sql(
			f"""
			SELECT name, card_number
			FROM `tabCard Details`
			WHERE {' AND '.join(conditions)}
			ORDER BY creation ASC
			LIMIT 1
			FOR UPDATE
			""",
			values,
			as_dict=True,
		)
		if not card:
			frappe.throw("No free card available for plant {}".format(frappe.bold(self.branch)))

		frappe.db.set_value("Card Details", card[0].name, "is_assigned", 1, update_modified=False)
		return card[0].card_number or card[0].name

	def _finalize_flags(self, gate_entry, weighment=None):
		"""Mark Gate Entry / Weighment completed straight in the DB.

		Done only at the very end and without hooks, so setting is_completed /
		is_in_progress can never trigger an automatic Purchase Receipt earlier.
		"""
		for doc, values in (
			(gate_entry, {"is_completed": 1, "is_in_progress": 0}),
			(weighment, {"is_completed": 1, "is_in_progress": 0}),
		):
			if not doc:
				continue
			meta = frappe.get_meta(doc.doctype)
			for fld, val in values.items():
				if meta.has_field(fld):
					frappe.db.set_value(doc.doctype, doc.name, fld, val, update_modified=False)

	def _get_pr(self, gate_entry_name):
		return frappe.db.get_value(
			"Purchase Receipt Item",
			{"custom_gate_entry": gate_entry_name, "docstatus": ["!=", 2]},
			"parent",
		)

	def _get_prs(self, gate_entry_name):
		return frappe.db.sql(
			"""
			SELECT DISTINCT pr.name, pr.docstatus
			FROM `tabPurchase Receipt` pr
			JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
			WHERE pri.custom_gate_entry = %s AND pr.docstatus < 2
			""",
			(gate_entry_name,),
		)

	def _ensure_purchase_receipt(self, weighment, gate_entry_name):
		"""Create the PR from the FINAL weighment.

		A hook may already have auto-created a draft PR while the Gate Entry /
		Weighment was being saved (built from stale data: no Weighment ID, old qty).
		Such drafts are removed first, then the PR is created once from the
		up-to-date Weighment.
		"""
		for pr_name, docstatus in self._get_prs(gate_entry_name):
			if docstatus != 0:
				return pr_name  # submitted PR: never touch
			frappe.delete_doc("Purchase Receipt", pr_name, force=1,
				ignore_permissions=True, delete_permanently=True)

		weighment.reload()
		weighment.create_purchase_receipt_manually()

		pr = self._get_pr(gate_entry_name)
		if not pr:
			frappe.throw("Purchase Receipt was not created for Gate Entry {}".format(
				get_link_to_form("Gate Entry", gate_entry_name)))
		return pr

	def _release_card(self, card_name):
		if not card_name:
			return

		card_docname = frappe.db.get_value("Card Details", card_name, "name")
		if not card_docname:
			card_docname = frappe.db.get_value(
				"Card Details", {"card_number": card_name}, "name"
			)
		if card_docname:
			frappe.db.set_value(
				"Card Details", card_docname, "is_assigned", 0, update_modified=False
			)

	@frappe.whitelist()
	def map_gate_entry_data(self):
		if not self.gate_entry:
			return

		meta = frappe.get_meta("ZZMaintenance")
		data = frappe.get_doc("Gate Entry", self.gate_entry).as_dict()
		child_tables = {k: v for k, v in data.items()
			if isinstance(v, list) and all(isinstance(i, dict) for i in v)}

		for key, value in data.items():
			if key not in child_tables and key not in SKIP_KEYS and meta.has_field(key):
				self.set(key, value)

		for table_field, rows in child_tables.items():
			if meta.has_field(table_field):
				self.set(table_field, [])
				for row in rows:
					self.append(table_field, {k: v for k, v in row.items() if k not in SKIP_ROW_KEYS})

		w = frappe.db.get_value("Weighment", {"gate_entry_number": self.gate_entry},
			["weighment_date", "inward_date", "outward_date", "tare_weight", "gross_weight", "net_weight"],
			as_dict=True)
		if w:
			for k, v in w.items():
				self.set(k, v)

		return True

	@frappe.whitelist()
	def create_transaction(self):
		if self.entry_type == "Inward":
			for field in REQUIRED_FIELDS + ["segment", "company", "branch"]:
				if not self.get(field):
					frappe.throw(f"{frappe.bold(field.replace('_', ' ').capitalize())} is mandatory for this transaction")

		if self.entry_type == "Inward":
			for k in self.items or []:
				if not k.accepted_quantity:
					frappe.throw("Accepted qty in row {} can't be zero".format(k.idx))

		# Whole method runs in one DB transaction: any throw below rolls back
		# the card assignment as well.
		card_number = self._assign_card()
		creation = self._creation_dt()
		scalars, child_tables = self._split()

		# ---- Gate Entry
		gate_entry = frappe.new_doc("Gate Entry")
		self._copy_to(gate_entry, scalars, child_tables)
		if self.entry_type == "Outward":
			gate_entry.is_weighment_required = self.is_weighment_required or "Yes"
		self._populate_contact_and_location(gate_entry)
		gate_entry.segment = self.segment
		gate_entry.card_number = card_number
		gate_entry.set("creation", creation)
		gate_entry.set("modified", creation)
		gate_entry.insert(ignore_permissions=True)
		gate_entry.submit()
		self._stamp(gate_entry, creation)
		self._notify("Gate Entry Created", f"Gate Entry Created: {gate_entry.name}")

		weighment = None
		# ---- Weighment
		if all([self.weighment_date, self.inward_date, self.outward_date,
				self.tare_weight, self.gross_weight, self.net_weight]):
			weighment = frappe.new_doc("Weighment")
			self._copy_to(weighment, scalars, child_tables)
			if self.entry_type == "Outward":
				weighment.is_weighment_required = self.is_weighment_required or "Yes"
			self._populate_contact_and_location(weighment)
			self._populate_weighment_delivery_notes(weighment)
			weighment.gate_entry_number = gate_entry.name
			weighment.is_completed = 1
			for fld, val in (("card_number", card_number), ("segment", self.segment)):
				if weighment.meta.has_field(fld):
					weighment.set(fld, val)
			weighment.set("creation", creation)
			weighment.set("modified", creation)
			weighment.insert(ignore_permissions=True)
			weighment.submit()
			if self.entry_type == "Outward":
				self._update_outward_delivery_notes(weighment)
			self._stamp(weighment, creation)
			self._notify("Weighment Created", f"Weighment Created: {weighment.name}")

			if self.entry_type == "Inward":
				# Purchase Receipts are created only for inward transactions.
				self._ensure_purchase_receipt(weighment, gate_entry.name)

		self._persist_transporter(gate_entry, weighment)

		# nothing after this point may flip the flag back
		self._finalize_flags(gate_entry, weighment)

		if RELEASE_CARD_AFTER_COMPLETE:
			self._release_card(card_number)

		return True

	@frappe.whitelist()
	def update_transaction(self):
		if not self.gate_entry:
			frappe.throw("Gate Entry is mandatory for Update")

		if self.entry_type == "Inward":
			for field in REQUIRED_FIELDS:
				if not self.get(field):
					frappe.throw(f"{frappe.bold(field.replace('_', ' ').capitalize())} is mandatory for this transaction")

			for k in self.items or []:
				if not k.accepted_quantity:
					frappe.throw("Accepted qty in row {} can't be zero".format(k.idx))
		elif self.entry_type == "Outward":
			for field in ("weighment_date", "outward_date", "tare_weight", "gross_weight", "net_weight"):
				if not self.get(field):
					frappe.throw(f"{frappe.bold(field.replace('_', ' ').capitalize())} is mandatory for this transaction")
			if self.gross_weight <= self.tare_weight or self.net_weight <= 0:
				frappe.throw("Gross weight must be greater than tare weight and net weight must be positive")
		else:
			frappe.throw("Entry Type must be Inward or Outward")

		# only a draft Purchase Receipt may be replaced (no stock / GL entries exist yet)
		old_pr = None
		if self.entry_type == "Inward":
			old_pr = self._get_pr(self.gate_entry)
			if old_pr and frappe.db.get_value("Purchase Receipt", old_pr, "docstatus") != 0:
				frappe.throw(
					"Purchase Receipt {} is already <b>submitted</b>. Update is allowed only while the "
					"Purchase Receipt is in <b>Draft</b>.".format(frappe.bold(get_link_to_form("Purchase Receipt", old_pr)))
				)

		started = now_datetime()

		pr_meta = None
		if old_pr:
			pr_meta = self._delete_purchase_receipt(old_pr)

		gate_entry = frappe.get_doc("Gate Entry", self.gate_entry)
		scalars, child_tables = self._split()

		if self.entry_type == "Outward":
			self._update_without_hooks(
				gate_entry,
				scalars,
				skip_blank=("card_number", "segment", "transporter", "transporter_name"),
			)
			weighment = frappe.get_doc("Weighment", {"gate_entry_number": gate_entry.name})
			self._update_without_hooks(
				weighment,
				scalars,
				skip_blank=("card_number", "segment", "transporter", "transporter_name"),
			)
			self._persist_transporter(gate_entry, weighment)

			self._update_outward_delivery_notes(weighment)
			self._finalize_flags(gate_entry, weighment)
			self._release_card(gate_entry.card_number)
			self._notify(
				"Data Updated Successfully",
				f"Data Updated Successfully: {gate_entry.name}, {weighment.name}",
			)
			return True

		modified_g, modified_by_g = gate_entry.modified, gate_entry.modified_by
		self._copy_to(gate_entry, scalars, child_tables, only_changed=True,
			skip_blank=("card_number", "segment"))
		self._save_silently(gate_entry)
		self._notify("Data Updated Successfully", f"Data Updated Successfully: {gate_entry.name}")

		weighment = None
		modified_w = modified_by_w = None
		if frappe.db.exists("Weighment", {"gate_entry_number": gate_entry.name}):
			weighment = frappe.get_doc("Weighment", {"gate_entry_number": gate_entry.name})
			modified_w, modified_by_w = weighment.modified, weighment.modified_by

			self._copy_to(weighment, scalars, child_tables, only_changed=True,
				skip_blank=("card_number", "segment"))
			self._save_silently(weighment)
			self._notify("Data Updated Successfully", f"Data Updated Successfully: {weighment.name}")

		# ---- 4. Re-create the inward Purchase Receipt with the same ID.
		pr_name = old_pr
		if weighment:
			self._ensure_purchase_receipt(weighment, gate_entry.name)
			if old_pr:
				self._restore_pr_name(gate_entry.name, old_pr, pr_meta)
			else:
				pr_name = self._get_pr(gate_entry.name)

		self._finalize_flags(gate_entry, weighment)

		# ---- 5. Put back original modified stamps
		frappe.db.set_value("Gate Entry", gate_entry.name, "modified", modified_g, update_modified=False)
		frappe.db.set_value("Gate Entry", gate_entry.name, "modified_by", modified_by_g, update_modified=False)
		if weighment:
			frappe.db.set_value("Weighment", weighment.name, "modified", modified_w, update_modified=False)
			frappe.db.set_value("Weighment", weighment.name, "modified_by", modified_by_w, update_modified=False)

		# ---- 6. Remove every Version / Comment / Deleted Document row this run created
		self._purge_traces(started, [
			("Gate Entry", gate_entry.name),
			("Weighment", weighment.name if weighment else None),
			("Purchase Receipt", pr_name),
		])

		return True

	def _update_without_hooks(self, doc, scalars, skip_blank=()):
		"""Update outward fields directly, avoiding costly submit hooks and child-table rewrites."""
		meta = frappe.get_meta(doc.doctype)
		values = {
			key: value for key, value in scalars.items()
			if meta.has_field(key) and (key not in skip_blank or value)
		}
		values = {
			key: value for key, value in values.items()
			if doc.get(key) != value
		}
		if values:
			frappe.db.set_value(doc.doctype, doc.name, values, update_modified=False)
			for key, value in values.items():
				doc.set(key, value)

	def _update_outward_delivery_notes(self, weighment):
		"""Apply the final outward net weight to its weighment and draft delivery notes."""
		if not weighment.delivery_note_details:
			frappe.throw("No Delivery Note Details are linked to Weighment {}".format(weighment.name))

		details_by_note = {}
		for detail in weighment.delivery_note_details:
			if not detail.delivery_note or not detail.item:
				frappe.throw("Delivery Note and Item are required in Weighment {}".format(weighment.name))
			details_by_note.setdefault(detail.delivery_note, set()).add(detail.item)

		for delivery_note_name, item_codes in details_by_note.items():
			delivery_note = frappe.get_doc("Delivery Note", delivery_note_name)
			if delivery_note.docstatus != 0:
				frappe.throw(
					"Delivery Note {} is not in Draft. Cancel or amend it before updating the outward weighment.".format(
						frappe.bold(get_link_to_form("Delivery Note", delivery_note_name))
					)
				)

			if delivery_note.meta.has_field("custom_weighment"):
				delivery_note.custom_weighment = weighment.name

			matching_items = [
				item for item in delivery_note.items if item.item_code in item_codes
			]
			if not matching_items:
				frappe.throw(
					"No matching items found in Delivery Note {}".format(
						get_link_to_form("Delivery Note", delivery_note_name)
					)
				)

			for detail in weighment.delivery_note_details:
				if detail.delivery_note == delivery_note_name:
					frappe.db.set_value(
						"Delivery Note Details",
						detail.name,
						"qty",
						self.net_weight,
						update_modified=False,
					)

			for item in matching_items:
				item.qty = self.net_weight
			self._save_silently(delivery_note)

		return list(details_by_note)

	@frappe.whitelist()
	def get_delivery_note_items(self):
		if not self.branch:
			frappe.throw("Select a Plant before selecting Delivery Notes")
		if not self.item_group:
			frappe.throw("Select an Item Group before selecting Delivery Notes")

		selected_notes = list(dict.fromkeys(
			row.delivery_note for row in self.delivery_note or [] if row.delivery_note
		))
		if not selected_notes:
			frappe.throw("Select at least one Delivery Note")

		valid_notes = frappe.db.sql(
			"""
			SELECT DISTINCT dn.name
			FROM `tabDelivery Note` dn
			INNER JOIN `tabDelivery Note Item` dni ON dni.parent = dn.name
			WHERE dn.name IN %(selected_notes)s
				AND dn.branch = %(branch)s
				AND dn.docstatus = 0
				AND (dn.custom_weighment IS NULL OR dn.custom_weighment = '')
				AND dni.item_group = %(item_group)s
			""",
			{
				"selected_notes": tuple(selected_notes),
				"branch": self.branch,
				"item_group": self.item_group,
			},
		)
		valid_note_set = {row[0] for row in valid_notes}
		ineligible_notes = [name for name in selected_notes if name not in valid_note_set]
		if ineligible_notes:
			frappe.throw(
				"These Delivery Notes must be Draft, unlinked to a Weighment, belong to Plant {}, and contain Item Group {}: {}".format(
					frappe.bold(self.branch), frappe.bold(self.item_group), ", ".join(ineligible_notes)
				)
			)

		item_fields = ["parent", "item_code", "item_name", "qty", "uom", "total_weight"]
		if frappe.get_meta("Delivery Note Item").has_field("custom_total_package_weight"):
			item_fields.append("custom_total_package_weight")

		items = frappe.get_all(
			"Delivery Note Item",
			filters={
				"parent": ["in", selected_notes],
				"item_group": self.item_group,
			},
			fields=item_fields,
			order_by="parent asc, idx asc",
		)
		if not items:
			frappe.throw("No item rows found in the selected Delivery Notes")

		return [
			{
				"delivery_note": item.parent,
				"item": item.item_code,
				"item_name": item.item_name,
				"qty": item.qty,
				"uom": item.uom,
				"total_weight": flt(item.get("custom_total_package_weight"))
					+ flt(item.get("total_weight")),
			}
			for item in items
		]

	def _save_silently(self, doc):
		"""Save without Version row and without permission / after-submit blockers."""
		doc.flags.ignore_version = True
		doc.flags.ignore_permissions = True
		doc.flags.ignore_links = True
		doc.flags.ignore_validate_update_after_submit = True
		doc.save(ignore_permissions=True, ignore_version=True)

	def _purge_traces(self, since, refs):
		for doctype, name in refs:
			if not name:
				continue
			frappe.db.sql(
				"DELETE FROM `tabVersion` WHERE ref_doctype=%s AND docname=%s AND creation >= %s",
				(doctype, name, since),
			)
			frappe.db.sql(
				"DELETE FROM `tabComment` WHERE reference_doctype=%s AND reference_name=%s AND creation >= %s",
				(doctype, name, since),
			)
			frappe.db.sql(
				"DELETE FROM `tabDeleted Document` WHERE deleted_doctype=%s AND deleted_name=%s AND creation >= %s",
				(doctype, name, since),
			)

	def _delete_purchase_receipt(self, pr_name):
		meta = frappe.db.get_value(
			"Purchase Receipt", pr_name,
			["creation", "modified", "owner", "modified_by"], as_dict=True,
		)
		frappe.delete_doc("Purchase Receipt", pr_name, force=1,
			ignore_permissions=True, delete_permanently=True)

		self._notify("Purchase Receipt Deleted", f"Purchase Receipt Deleted: {pr_name}")
		return meta

	def _restore_pr_name(self, gate_entry_name, old_name, pr_meta=None):
		new_name = self._get_pr(gate_entry_name)
		if not new_name:
			frappe.throw("New Purchase Receipt was not created for Gate Entry {}".format(
				get_link_to_form("Gate Entry", gate_entry_name)))

		if new_name != old_name:
			frappe.rename_doc("Purchase Receipt", new_name, old_name, force=True, merge=False)

		if pr_meta:
			# same creation / owner / modified as the PR that was replaced
			frappe.db.set_value("Purchase Receipt", old_name, dict(pr_meta), update_modified=False)
		self._notify("Purchase Receipt Created", f"Purchase Receipt Created: {old_name}")

	@frappe.whitelist()
	def get_item_from_po(self):
		if not self.purchase_orders:
			return

		self.items = []
		weighment_cache = {}
		for po in self.purchase_orders:
			if not po.purchase_orders:
				continue
			data = frappe.get_all("Purchase Order Item", {"parent": po.purchase_orders}, ["*"])
			for d in data:
				if d.item_group not in weighment_cache:
					weighment_cache[d.item_group] = frappe.db.get_value(
						"Item Group", d.item_group, "custom_is_weighment_required") == "Yes"
				self.append("items", {
					"item_code": d.get("item_code"),
					"item_name": d.get("item_name"),
					"qty": d.get("qty"),
					"is_weighable_item": weighment_cache[d.item_group],
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