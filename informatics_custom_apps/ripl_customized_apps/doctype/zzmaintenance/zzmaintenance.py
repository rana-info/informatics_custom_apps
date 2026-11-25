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

# True  -> rename the re-created draft Purchase Receipt back to its old name with direct SQL (fast)
# False -> use frappe.rename_doc (slow: scans every link field in the system)
FAST_PR_RENAME = True

# Set on frappe.flags while ZZMaintenance runs. Add this one-line guard at the top of the
# Gate Entry / Weighment hook that auto-creates a Purchase Receipt:
#     if frappe.flags.get("zz_maintenance"): return
ZZ_FLAG = "zz_maintenance"

# After Update, re-apply the original "Last Updated" stamps once more AFTER the request has
# committed, to undo any background / after-commit job that re-saves the documents.
MODIFIED_RESTORE_DEFERRED = True
MODIFIED_RESTORE_DELAY = 6  # seconds the background job waits before restoring

# PO incoterms for which a Rake Bill is maintained
RAIL_INCOTERMS = ("Rail Rack", "RRB", "Rail Rake")


def apply_modified_snaps(snaps, rebuilt=()):
	"""Put remembered modified / modified_by back with direct SQL (no hooks, no new stamp).

	rebuilt: doctypes whose child rows were deleted and re-created, so every current child row
	gets the parent's original stamp instead of a per-row one.
	"""
	for s in snaps:
		dt, name = s["dt"], s["name"]
		frappe.db.sql(f"UPDATE `tab{dt}` SET modified=%s, modified_by=%s WHERE name=%s",
			(s["m"], s["mb"], name))
		for cdt, rows in s["children"].items():
			if dt in rebuilt:
				frappe.db.sql(
					f"UPDATE `tab{cdt}` SET modified=%s, modified_by=%s "
					"WHERE parent=%s AND parenttype=%s", (s["m"], s["mb"], name, dt))
			else:
				for rname, rm, rmb in rows:
					frappe.db.sql(
						f"UPDATE `tab{cdt}` SET modified=%s, modified_by=%s WHERE name=%s",
						(rm, rmb, rname))


def restore_modified_deferred(snaps, rebuilt=(), delay=MODIFIED_RESTORE_DELAY):
	"""Background job (runs after the request commits): restore the stamps one more time."""
	import time
	time.sleep(delay)
	apply_modified_snaps(snaps, rebuilt)
	frappe.db.commit()


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
		transporter = self.transporter if self.vehicle_owner == "Third Party" else None
		transporter_name = (
			frappe.db.get_value("Supplier", transporter, "supplier_name")
			if transporter else None
		) or (self.transporter_name if transporter else None)
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
		if doc.meta.has_field("transporter"):
			doc.set("transporter", transporter or "")
		if doc.meta.has_field("transporter_name"):
			doc.set("transporter_name", transporter_name or "")
		self._set_if_field_exists(doc, "driver_name", driver_name)
		self._set_if_field_exists(doc, "driver_contact", driver_contact)

	def _transporter_details(self):
		"""Return transporter details only for third-party vehicles."""
		if self.vehicle_owner != "Third Party":
			return None
		transporter = self.transporter
		if not transporter:
			return None
		fields = ["supplier_name"]
		if frappe.get_meta("Supplier").has_field("gst_transporter_id"):
			fields.append("gst_transporter_id")
		supplier = frappe.db.get_value("Supplier", transporter, fields, as_dict=True)
		if not supplier or not supplier.supplier_name:
			frappe.throw(f"Supplier {frappe.bold(transporter)} has no Supplier Name")
		return {
			"transporter": transporter,
			"transporter_name": supplier.supplier_name,
			"gst_transporter_id": supplier.get("gst_transporter_id"),
		}

	def _write_transporter(self, doctype, name, details):
		meta = frappe.get_meta(doctype)
		values = {f: v for f, v in details.items() if v and meta.has_field(f)}
		if not values:
			return
		frappe.db.set_value(doctype, name, values, update_modified=False)
		saved = frappe.db.get_value(doctype, name, list(values), as_dict=True)
		if any(saved.get(f) != v for f, v in values.items()):
			frappe.throw(f"Could not persist transporter details on {doctype} {name}")

	def _clear_transporter(self, doctype, name):
		meta = frappe.get_meta(doctype)
		fields = ("transporter", "transporter_name", "gst_transporter_id")
		values = {field: "" for field in fields if meta.has_field(field)}
		if not values:
			return
		frappe.db.set_value(doctype, name, values, update_modified=False)
		saved = frappe.db.get_value(doctype, name, list(values), as_dict=True)
		if any(saved.get(field) for field in values):
			frappe.throw(f"Could not clear transporter details on {doctype} {name}")

	def _persist_transporter(self, gate_entry=None, weighment=None):
		"""Persist transporter only for third-party vehicles, after document hooks."""
		details = self._transporter_details()
		if not details:
			if gate_entry:
				self._clear_transporter("Gate Entry", gate_entry.name)
				for field in ("transporter", "transporter_name"):
					if gate_entry.meta.has_field(field):
						gate_entry.set(field, "")
			if weighment:
				self._clear_transporter("Weighment", weighment.name)
				for field in ("transporter", "transporter_name"):
					if weighment.meta.has_field(field):
						weighment.set(field, "")
				notes = {
					d.delivery_note
					for d in (weighment.get("delivery_note_details") or [])
					if d.delivery_note
				}
			else:
				notes = set()
			notes.update(
				row.delivery_note for row in (self.delivery_note or [])
				if row.delivery_note
			)
			for dn in notes:
				self._clear_transporter("Delivery Note", dn)
			return
		if gate_entry:
			self._write_transporter("Gate Entry", gate_entry.name, details)
			gate_entry.transporter = details["transporter"]
			gate_entry.transporter_name = details["transporter_name"]
		if weighment:
			self._write_transporter("Weighment", weighment.name, details)
			weighment.transporter = details["transporter"]
			weighment.transporter_name = details["transporter_name"]
			notes = dict.fromkeys(
				d.delivery_note for d in (weighment.get("delivery_note_details") or [])
				if d.delivery_note
			)
			for dn in notes:
				self._write_transporter("Delivery Note", dn, details)

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
			ORDER BY RAND()
			LIMIT 1
			FOR UPDATE SKIP LOCKED
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
		weighment.create_purchase_receipt_manually(ignore_permissions=True)

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

	# ============ PO / RAKE BILL SYNC============

	def _row_po_item(self, r):
		"""Purchase Order Item name for a Purchase Details row.
		Falls back to (purchase_order, item_code) when purchase_order_item is blank."""
		po_item = r.get("purchase_order_item")
		if po_item:
			return po_item
		po, code = r.get("purchase_order"), r.get("item_code")
		if po and code:
			return frappe.db.get_value(
				"Purchase Order Item", {"parent": po, "item_code": code}, "name")
		return None

	def _po_item_qty_map(self, rows):
		"""{purchase_order_item: total accepted_quantity} from Purchase Details rows."""
		out = {}
		for r in rows or []:
			po_item = self._row_po_item(r)
			if po_item:
				out[po_item] = out.get(po_item, 0) + flt(r.get("accepted_quantity"))
		return out

	def _old_gate_entry_qty_map(self):
		"""Accepted qty per PO item as currently saved on the Gate Entry (BEFORE update)."""
		rows = frappe.get_all(
			"Purchase Details",
			filters={"parent": self.gate_entry, "parenttype": "Gate Entry"},
			fields=["purchase_order_item", "purchase_order", "item_code", "accepted_quantity"],
		)
		return self._po_item_qty_map(rows)

	def _qty_deltas(self, old_map, new_map):
		"""new - old for every PO item that appears on either side.
		Old PO item gets a negative delta, new PO item a positive one, so a PO
		change is handled automatically."""
		deltas = {}
		for po_item in set(old_map) | set(new_map):
			delta = flt(new_map.get(po_item, 0)) - flt(old_map.get(po_item, 0))
			if abs(delta) > 0.000001:
				deltas[po_item] = delta
		return deltas

	def _rake_bill(self, po_name):
		"""Return the live Rake Bill row for a Rail PO, else None."""
		if not po_name:
			return None
		incoterm = (frappe.db.get_value("Purchase Order", po_name, "incoterm") or "").strip().casefold()
		if incoterm not in {i.casefold() for i in RAIL_INCOTERMS}:
			return None
		rb = frappe.db.get_value(
			"Rake Bill",
			{"purchase_order": po_name, "docstatus": ["<", 2]},
			["name", "billed_qty", "gate_entry_received_qty", "tolerance_qty"],
			as_dict=True,
		)
		if not rb:
			warned = frappe.flags.setdefault("zz_rb_warned", set())
			if po_name not in warned:
				warned.add(po_name)
				frappe.msgprint(
					f"Purchase Order {frappe.bold(po_name)} is a Rail PO but has no Rake Bill. "
					f"Rake Bill was not updated.", indicator="orange", alert=True)
		return rb

	def _validate_po_limits(self, deltas):
		"""Throw if applying `deltas` pushes any PO item (or Rake Bill) over its limit.
		Only increases are checked; decreases are always allowed.
		Nothing is written here, so call it BEFORE touching any document."""
		qty_by_po = {}

		for po_item, delta in deltas.items():
			d = frappe.db.get_value(
				"Purchase Order Item", po_item,
				["parent", "item_code", "qty", "gate_entry_received_qty"],
				as_dict=True,
			)
			if not d:
				frappe.throw(f"Purchase Order Item {frappe.bold(po_item)} not found")

			qty_by_po[d.parent] = qty_by_po.get(d.parent, 0) + delta

			if delta <= 0 or not flt(d.qty):
				continue

			allowance = flt(frappe.db.get_value(
				"Item", d.item_code, "over_delivery_receipt_allowance"))
			max_pct = 100 + allowance
			max_qty = flt(d.qty) * max_pct / 100
			new_received = flt(d.gate_entry_received_qty) + delta
			new_pct = new_received / flt(d.qty) * 100

			if new_received - max_qty > 0.0001:
				frappe.throw(
					f"Gate Entry received quantity ({flt(new_received, 3)}) for item "
					f"{frappe.bold(d.item_code)} in {frappe.bold(d.parent)} exceeds the maximum "
					f"allowed quantity ({flt(max_qty, 3)}), and received percentage "
					f"({new_pct:.2f}%) exceeds the limit ({max_pct:.2f}%) set by Over "
					f"Delivery/Receipt Allowance ({allowance}%)."
				)

		for po_name, delta in qty_by_po.items():
			if delta <= 0:
				continue
			rb = self._rake_bill(po_name)
			if rb and flt(rb.gate_entry_received_qty) + delta - flt(rb.billed_qty) > 0.0001:
				frappe.throw(
					f"Gate Entry Received Qty ({flt(flt(rb.gate_entry_received_qty) + delta, 3)}) "
					f"cannot be greater than Billed Qty ({flt(rb.billed_qty, 3)}) on Rake Bill "
					f"{frappe.bold(rb.name)} for Purchase Order {frappe.bold(po_name)}"
				)

	def _refresh_po_received_percentage(self, po_item_name):
		"""Recalculate gate_entry_received_percentage on the parent PO (no validation)."""
		d = frappe.db.get_value(
			"Purchase Order Item", po_item_name,
			["parent", "qty", "gate_entry_received_qty"], as_dict=True,
		)
		if d and flt(d.qty):
			frappe.db.set_value(
				"Purchase Order", d.parent, "gate_entry_received_percentage",
				flt(d.gate_entry_received_qty) / flt(d.qty) * 100,
				update_modified=False,
			)

	def _set_rake_bill_received(self, rb, new_received):
		"""Write gate_entry_received_qty and the 3 fields derived from it on a Rake Bill."""
		billed = flt(rb.billed_qty)
		tolerance = flt(rb.tolerance_qty)
		new_received = flt(new_received)

		if new_received - billed > 0.0001:
			frappe.throw(
				f"Gate Entry Received Qty ({flt(new_received, 3)}) cannot be greater than "
				f"Billed Qty ({billed}) on Rake Bill {rb.name}"
			)

		short_billed = billed - new_received
		frappe.db.set_value("Rake Bill", rb.name, {
			"gate_entry_received_qty": new_received,
			"billed_to_after_tolerance": new_received + tolerance,
			"short_billed_qty": short_billed,
			"debit_note_qty": short_billed - tolerance,
		}, update_modified=False)

	def _update_rake_bill(self, po_name, qty_diff):
		"""Adjust Rake Bill quantities by qty_diff (same formulas as PMS.update_rake_bill)."""
		if not qty_diff:
			return
		rb = self._rake_bill(po_name)
		if not rb:
			return
		self._set_rake_bill_received(rb, flt(rb.gate_entry_received_qty) + qty_diff)

	def _snapshot_po_state(self, deltas):
		"""Record PO item received qty and Rake Bill received qty BEFORE anything is created."""
		po_base, parents = {}, set()
		for po_item in deltas:
			d = frappe.db.get_value(
				"Purchase Order Item", po_item, ["parent", "gate_entry_received_qty"], as_dict=True)
			if d:
				po_base[po_item] = flt(d.gate_entry_received_qty)
				parents.add(d.parent)
		rb_base = {}
		for po in parents:
			rb = self._rake_bill(po)
			if rb:
				rb_base[po] = flt(rb.gate_entry_received_qty)
		return po_base, rb_base

	def _apply_baseline_sync(self, deltas, snapshot):
		"""CREATE flow: set PO item qty and PO % to  baseline + delta; returns the PO names touched.

		Absolute (not incremental), so it gives the right result whether or not a
		Gate Entry hook already wrote to the PO - nothing is ever counted twice.
		"""
		qty_by_po = {}
		for po_item, delta in deltas.items():
			parent = frappe.db.get_value("Purchase Order Item", po_item, "parent")
			if not parent:
				continue
			total = frappe.db.sql(
				"""
				SELECT IFNULL(SUM(accepted_quantity), 0)
				FROM `tabPurchase Details`
				WHERE parenttype = 'Gate Entry'
					AND docstatus = 1
					AND purchase_order_item = %s
				""",
				(po_item,),
			)[0][0]
			frappe.db.set_value(
				"Purchase Order Item", po_item, "gate_entry_received_qty",
				max(flt(total), 0), update_modified=False,
			)
			self._refresh_po_received_percentage(po_item)
			qty_by_po[parent] = qty_by_po.get(parent, 0) + delta

		return list(qty_by_po)

	def _sync_rake_bills_from_po(self, po_names):
		"""Set each Rake Bill's received qty (and the 3 fields derived from it) from the PO.

		gate_entry_received_qty on a Rake Bill = sum of gate_entry_received_qty over the PO's
		items. It is ABSOLUTE (recomputed from the PO, not added to the old Rake Bill value), so it
		can never double, whatever else touched the Rake Bill earlier in the request.
		Run as the very LAST data step of the transaction.
		"""
		for po_name in po_names:
			rb = self._rake_bill(po_name)
			if not rb:
				continue
			total = frappe.db.sql(
				"SELECT IFNULL(SUM(gate_entry_received_qty), 0) FROM `tabPurchase Order Item` WHERE parent=%s",
				(po_name,),
			)[0][0]
			self._set_rake_bill_received(rb, total)
			self._recalc_rake_bill_factory_qty(po_name)

	def _recalc_rake_bill_factory_qty(self, po_name):
		"""factory_received_qty = sum of net_weight of submitted Weighments linked to the PO."""
		rb = self._rake_bill(po_name)
		if not rb:
			return
		total = frappe.db.sql(
			"""
			SELECT IFNULL(SUM(w.net_weight), 0)
			FROM `tabWeighment` w
			WHERE w.docstatus = 1
			AND EXISTS (
				SELECT 1 FROM `tabPurchase Orders`
				WHERE parent = w.name AND parenttype = 'Weighment' AND purchase_orders = %s
			)
			""",
			(po_name,),
		)[0][0]
		frappe.db.set_value("Rake Bill", rb.name, "factory_received_qty", total,
			update_modified=False)

	def _sync_po_and_rake_bill(self, deltas, update_po_items=True):
		"""Apply qty deltas.

		update_po_items=True  -> also write Purchase Order Item.gate_entry_received_qty
		                         (needed on UPDATE; on CREATE the Gate Entry hook already does it)
		Always refreshes PO percentage, Rake Bill received/short/debit qty and factory qty.
		"""
		qty_by_po = {}
		for po_item, delta in deltas.items():
			parent = frappe.db.get_value("Purchase Order Item", po_item, "parent")
			if not parent:
				continue
			if update_po_items:
				current = flt(frappe.db.get_value(
					"Purchase Order Item", po_item, "gate_entry_received_qty"))
				frappe.db.set_value(
					"Purchase Order Item", po_item, "gate_entry_received_qty",
					max(current + delta, 0), update_modified=False,
				)
			self._refresh_po_received_percentage(po_item)
			qty_by_po[parent] = qty_by_po.get(parent, 0) + delta

		for po_name, delta in qty_by_po.items():
			rb = self._rake_bill(po_name)
			if rb:
				total = frappe.db.sql(
					"SELECT IFNULL(SUM(gate_entry_received_qty), 0) "
					"FROM `tabPurchase Order Item` WHERE parent=%s",
					(po_name,),
				)[0][0]
				self._set_rake_bill_received(rb, total)
			self._recalc_rake_bill_factory_qty(po_name)

	# ============ END PO / RAKE BILL SYNC ============


	def _snap_modified(self, refs):
		"""Remember modified / modified_by of each (doctype, name) and of its child rows."""
		snaps = []
		for dt, name in refs:
			if not name or not frappe.db.exists(dt, name):
				continue
			stamp = frappe.db.get_value(dt, name, ["modified", "modified_by"], as_dict=True)
			children = {}
			for df in frappe.get_meta(dt).get_table_fields():
				children[df.options] = frappe.db.sql(
					f"SELECT name, modified, modified_by FROM `tab{df.options}` "
					"WHERE parent=%s AND parenttype=%s", (name, dt))
			snaps.append({"dt": dt, "name": name, "m": stamp.modified,
				"mb": stamp.modified_by, "children": children})
		return snaps

	def _restore_modified(self, snaps, rebuilt=()):
		apply_modified_snaps(snaps, rebuilt)

	def _inward_update_refs(self):
		"""Every document an Inward update can touch: Gate Entry, Weighment, its POs, Rake Bills."""
		pos = {r.purchase_orders for r in (self.purchase_orders or []) if r.purchase_orders}
		for row in frappe.get_all("Purchase Details",
				filters={"parent": self.gate_entry, "parenttype": "Gate Entry"},
				fields=["purchase_order"]):
			if row.purchase_order:
				pos.add(row.purchase_order)
		rbs = frappe.get_all("Rake Bill", filters={"purchase_order": ["in", list(pos)]},
			pluck="name") if pos else []
		weighment = frappe.db.get_value("Weighment", {"gate_entry_number": self.gate_entry}, "name")
		refs = [("Gate Entry", self.gate_entry), ("Weighment", weighment)]
		refs += [("Purchase Order", p) for p in sorted(pos)]
		refs += [("Rake Bill", r) for r in rbs]
		return refs

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
		frappe.flags[ZZ_FLAG] = True  # lets Gate Entry / Weighment hooks skip auto Purchase Receipt creation
		if self.entry_type == "Inward":
			for field in REQUIRED_FIELDS + ["segment", "company", "branch"]:
				if not self.get(field):
					frappe.throw(f"{frappe.bold(field.replace('_', ' ').capitalize())} is mandatory for this transaction")

		if self.entry_type == "Inward":
			for k in self.items or []:
				if not k.accepted_quantity:
					frappe.throw("Accepted qty in row {} can't be zero".format(k.idx))

		# Validate over-delivery allowance and Rake Bill billed qty BEFORE anything is created
		create_deltas = {}
		if self.entry_type == "Inward":
			create_deltas = self._qty_deltas({}, self._po_item_qty_map(self.items))
			self._validate_po_limits(create_deltas)
		create_snapshot = self._snapshot_po_state(create_deltas)

		# Whole method runs in one DB transaction: any throw below rolls back
		# the card assignment as well.
		card_number = self._assign_card()
		creation = self._creation_dt()
		scalars, child_tables = self._split()

		# ---- Gate Entry
		gate_entry = frappe.new_doc("Gate Entry")
		self._copy_to(gate_entry, scalars, child_tables)
		if gate_entry.meta.has_field("is_weighment_required"):
			gate_entry.is_weighment_required = self.is_weighment_required or "Yes"
		self._populate_contact_and_location(gate_entry)
		gate_entry.segment = self.segment
		gate_entry.card_number = card_number
		gate_entry.set("creation", creation)
		gate_entry.set("modified", creation)
		gate_entry.insert(ignore_permissions=True)
		gate_entry.flags.ignore_permissions = True
		gate_entry.submit()
		self._stamp(gate_entry, creation)
		self._notify("Gate Entry Created", f"Gate Entry Created: {gate_entry.name}")

		weighment = None
		synced_pos = []
		# ---- Weighment
		if all([self.weighment_date, self.inward_date, self.outward_date,
				self.tare_weight, self.gross_weight, self.net_weight]):
			weighment = frappe.new_doc("Weighment")
			self._copy_to(weighment, scalars, child_tables)
			if weighment.meta.has_field("is_weighment_required"):
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
			weighment.flags.ignore_permissions = True
			weighment.submit()
			if self.entry_type == "Outward":
				self._update_outward_delivery_notes(weighment)
			self._stamp(weighment, creation)
			self._notify("Weighment Created", f"Weighment Created: {weighment.name}")

			if self.entry_type == "Inward":
				self._ensure_purchase_receipt(weighment, gate_entry.name)

				synced_pos = self._apply_baseline_sync(create_deltas, create_snapshot)

		self._finalize_flags(gate_entry, weighment)

		if RELEASE_CARD_AFTER_COMPLETE:
			self._release_card(card_number)

		self._persist_transporter(gate_entry, weighment)

		if self.entry_type == "Inward":
			self._sync_rake_bills_from_po(synced_pos)

		return True

	@frappe.whitelist()
	def update_transaction(self):
		frappe.flags[ZZ_FLAG] = True
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

		update_deltas = {}
		if self.entry_type == "Inward":
			update_deltas = self._qty_deltas(
				self._old_gate_entry_qty_map(),
				self._po_item_qty_map(self.items),
			)
			self._validate_po_limits(update_deltas)

		old_pr = None
		if self.entry_type == "Inward":
			old_pr = self._get_pr(self.gate_entry)
			if old_pr and frappe.db.get_value("Purchase Receipt", old_pr, "docstatus") != 0:
				frappe.throw(
					"Purchase Receipt {} is already <b>submitted</b>. Update is allowed only while the "
					"Purchase Receipt is in <b>Draft</b>.".format(frappe.bold(get_link_to_form("Purchase Receipt", old_pr)))
				)

		started = now_datetime()

		# remember every "Last Updated" stamp BEFORE anything is changed (restored at the end)
		modified_refs, modified_snaps = [], []
		if self.entry_type == "Inward":
			modified_refs = self._inward_update_refs()
			modified_snaps = self._snap_modified(modified_refs)

		pr_meta = None
		if old_pr:
			pr_meta = self._delete_purchase_receipt(old_pr)

		gate_entry = frappe.get_doc("Gate Entry", self.gate_entry)
		scalars, child_tables = self._split()

		if self.entry_type == "Outward":
			self._update_without_hooks(
				gate_entry,
				scalars,
				skip_blank=("card_number", "segment", "transporter", "transporter_name", "is_weighment_required"),
			)
			weighment = frappe.get_doc("Weighment", {"gate_entry_number": gate_entry.name})
			self._update_without_hooks(
				weighment,
				scalars,
				skip_blank=("card_number", "segment", "transporter", "transporter_name", "is_weighment_required"),
			)

			dn_snaps = self._snap_modified([
				("Delivery Note", n) for n in dict.fromkeys(
					d.delivery_note for d in (weighment.delivery_note_details or []) if d.delivery_note)
			])
			self._update_outward_delivery_notes(weighment)
			self._restore_modified(dn_snaps)
			self._finalize_flags(gate_entry, weighment)
			self._release_card(gate_entry.card_number)

			# LAST step: force the ZZMaintenance transporter, replacing any existing value
			self._persist_transporter(gate_entry, weighment)

			self._notify(
				"Data Updated Successfully",
				f"Data Updated Successfully: {gate_entry.name}, {weighment.name}",
			)
			return True

		modified_g, modified_by_g = gate_entry.modified, gate_entry.modified_by
		self._copy_to(gate_entry, scalars, child_tables, only_changed=True,
			skip_blank=("card_number", "segment", "is_weighment_required"))
		self._save_silently(gate_entry)
		self._notify("Data Updated Successfully", f"Data Updated Successfully: {gate_entry.name}")

		weighment = None
		modified_w = modified_by_w = None
		if frappe.db.exists("Weighment", {"gate_entry_number": gate_entry.name}):
			weighment = frappe.get_doc("Weighment", {"gate_entry_number": gate_entry.name})
			modified_w, modified_by_w = weighment.modified, weighment.modified_by

			self._copy_to(weighment, scalars, child_tables, only_changed=True,
				skip_blank=("card_number", "segment", "is_weighment_required"))
			self._save_silently(weighment)
			self._notify("Data Updated Successfully", f"Data Updated Successfully: {weighment.name}")

		# ---- 3b. Sync PO items (gate_entry_received_qty / %) and Rake Bills.
		# Done after the Weighment is saved so factory_received_qty uses the new net weight.
		self._sync_po_and_rake_bill(update_deltas, update_po_items=True)

		# ---- 4. Re-create the inward Purchase Receipt with the same ID.
		pr_name = old_pr
		if weighment:
			self._ensure_purchase_receipt(weighment, gate_entry.name)
			if old_pr:
				self._restore_pr_name(gate_entry.name, old_pr, pr_meta)
			else:
				pr_name = self._get_pr(gate_entry.name)

		self._finalize_flags(gate_entry, weighment)

		# LAST data step: force the ZZMaintenance transporter, replacing any existing value
		self._persist_transporter(gate_entry, weighment)

		# ---- 6. Remove every Version / Comment / Deleted Document row this run created
		self._purge_traces(started, [
			("Gate Entry", gate_entry.name),
			("Weighment", weighment.name if weighment else None),
			("Purchase Receipt", pr_name),
		] + [(dt, n) for dt, n in modified_refs if dt in ("Purchase Order", "Rake Bill")])

		# ---- 7. LAST statements: original "Last Updated" on Gate Entry / Weighment (incl. child
		# rows), PO (+items) and Rake Bill - now, and again after commit for background jobs.
		self._restore_modified(modified_snaps, rebuilt=("Gate Entry", "Weighment"))
		if MODIFIED_RESTORE_DEFERRED and modified_snaps:
			frappe.enqueue(
				f"{__name__}.restore_modified_deferred",
				queue="short",
				enqueue_after_commit=True,
				snaps=modified_snaps,
				rebuilt=["Gate Entry", "Weighment"],
				delay=MODIFIED_RESTORE_DELAY,
			)

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
		"""Apply the final outward net weight to its weighment and draft delivery notes.

		Transporter details are NOT handled here; _persist_transporter writes them
		as the very last step of the flow.
		"""
		if not weighment.delivery_note_details:
			frappe.throw("No Delivery Note Details are linked to Weighment {}".format(weighment.name))

		details_by_note = {}
		for detail in weighment.delivery_note_details:
			if not detail.delivery_note or not detail.item:
				frappe.throw("Delivery Note and Item are required in Weighment {}".format(weighment.name))
			details_by_note.setdefault(detail.delivery_note, []).append(detail)

		for delivery_note_name, details in details_by_note.items():
			delivery_note = frappe.get_doc("Delivery Note", delivery_note_name)
			if delivery_note.docstatus != 0:
				frappe.throw(
					"Delivery Note {} is not in Draft. Cancel or amend it before updating the outward weighment.".format(
						frappe.bold(get_link_to_form("Delivery Note", delivery_note_name))
					)
				)

			if delivery_note.meta.has_field("custom_weighment"):
				delivery_note.custom_weighment = weighment.name
			if delivery_note.meta.has_field("vehicle_no"):
				delivery_note.vehicle_no = self.vehicle_number

			for detail in details:
				matching_items = [
					item for item in delivery_note.items
					if item.item_code == detail.item and item.uom == detail.uom
				]
				if not matching_items:
					frappe.throw(
						"No matching item {} with UOM {} found in Delivery Note {}".format(
							frappe.bold(detail.item),
							frappe.bold(detail.uom or "not set"),
							get_link_to_form("Delivery Note", delivery_note_name),
						)
					)

				qty = self._qty_for_uom(self.net_weight, detail.uom)
				if qty is None:
					continue

				frappe.db.set_value(
					"Delivery Note Details",
					detail.name,
					"qty",
					qty,
					update_modified=False,
				)
				detail.qty = qty
				for item in matching_items:
					item.qty = qty

			delivery_note.calculate_taxes_and_totals()
			# Validation re-fetches tax templates and requires select permission.
			delivery_note.flags.ignore_validate = True
			self._save_silently(delivery_note)

		return list(details_by_note)

	def _qty_for_uom(self, net_weight, uom):
		unit = (uom or "").strip().casefold()
		net_weight = flt(net_weight)

		if unit in {"quintal", "quintals"}:
			return flt(net_weight / 100, 6)

		if unit in {"klr", "kiloliter", "kilolitre", "kiloliters", "kilolitres"}:
			return flt(net_weight / 1000, 6)

		if unit in {"ltr", "liter", "litre", "liters", "litres", "nos", "meter",
					"case", "box", "bag", "tonne"}:
			return None

		return net_weight

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

	def _fast_rename_draft_pr(self, new_name, old_name):
		"""Rename a DRAFT Purchase Receipt with a few direct UPDATEs.

		frappe.rename_doc() walks every Link / Dynamic Link field in the whole
		system (many full-table scans) and is the slowest step of the update.
		A draft PR created seconds ago has no stock / GL entries, so only its own
		child rows (and any Quality Inspection / Comment pointing at it) need to follow.
		"""
		if frappe.db.get_value("Purchase Receipt", new_name, "docstatus") != 0:
			# never shortcut a submitted document
			frappe.rename_doc("Purchase Receipt", new_name, old_name, force=True,
				merge=False, ignore_permissions=True, show_alert=False)
			return

		if frappe.db.exists("Purchase Receipt", old_name):
			frappe.throw(f"Purchase Receipt {frappe.bold(old_name)} already exists")

		frappe.db.sql("UPDATE `tabPurchase Receipt` SET name=%s WHERE name=%s", (old_name, new_name))

		for df in frappe.get_meta("Purchase Receipt").get_table_fields():
			frappe.db.sql(
				f"UPDATE `tab{df.options}` SET parent=%s WHERE parent=%s AND parenttype='Purchase Receipt'",
				(old_name, new_name),
			)

		frappe.db.sql(
			"UPDATE `tabQuality Inspection` SET reference_name=%s "
			"WHERE reference_type='Purchase Receipt' AND reference_name=%s",
			(old_name, new_name),
		)
		frappe.db.sql(
			"UPDATE `tabComment` SET reference_name=%s "
			"WHERE reference_doctype='Purchase Receipt' AND reference_name=%s",
			(old_name, new_name),
		)

	def _restore_pr_name(self, gate_entry_name, old_name, pr_meta=None):
		new_name = self._get_pr(gate_entry_name)
		if not new_name:
			frappe.throw("New Purchase Receipt was not created for Gate Entry {}".format(
				get_link_to_form("Gate Entry", gate_entry_name)))

		if new_name != old_name:
			if FAST_PR_RENAME:
				self._fast_rename_draft_pr(new_name, old_name)
			else:
				frappe.rename_doc("Purchase Receipt", new_name, old_name, force=True,
					merge=False, ignore_permissions=True, show_alert=False)

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