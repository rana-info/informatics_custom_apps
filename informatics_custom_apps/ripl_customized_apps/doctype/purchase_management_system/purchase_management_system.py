import frappe
from frappe.model.document import Document


UOM_TO_KG = {
    "kg": 1, "kgs": 1, "kilogram": 1, "kilograms": 1,
    "quintal": 100, "qtl": 100, "quintals": 100, "qtls": 100,
    "tonne": 1000, "tonnes": 1000, "ton": 1000, "tons": 1000,
}

ITEM_CORRECTION_TYPES = (
    "Wrong Accepted Quantity",
    "Wrong Purchase Order",
    "Wrong Purchase Order and Supplier",
)


class PurchaseManagementSystem(Document):

    def convert_to_kg(self, qty, uom):
        """Convert a quantity to kilograms based on UOM."""
        if not qty:
            return 0

        factor = UOM_TO_KG.get((uom or "").lower())
        if factor is None:
            frappe.throw(f"Unsupported UOM: {uom}")

        return qty * factor

    def get_gate_entry_doc(self):
        """Fetch the linked Gate Entry document."""
        return frappe.get_doc("Gate Entry", self.gate_entry)

    def get_weighment_names(self):
        """Return a list of Weighment names linked to this Gate Entry."""
        return frappe.get_all(
            "Weighment",
            filters={"gate_entry_number": self.gate_entry},
            pluck="name",
        )

    def get_weighment_docs(self, weighment_names=None):
        """Return a list of Weighment documents linked to this Gate Entry."""
        names = weighment_names or self.get_weighment_names()
        return [frappe.get_doc("Weighment", name) for name in names]

    def get_linked_pr_names(self):
        """Return unique Purchase Receipt names linked via custom_gate_entry."""
        pr_items = frappe.db.get_all(
            "Purchase Receipt Item",
            filters={"custom_gate_entry": self.gate_entry},
            fields=["parent"],
        )
        return list({row.parent for row in pr_items})

    def unlink_purchase_receipts(self, weighment_names):
        """Unlink all Purchase Receipt Items from this Gate Entry and its Weighments."""
        frappe.db.sql("""
            UPDATE `tabPurchase Receipt Item`
            SET custom_gate_entry = NULL
            WHERE custom_gate_entry = %s
        """, (self.gate_entry,))

        if weighment_names:
            frappe.db.sql("""
                UPDATE `tabPurchase Receipt Item`
                SET custom_weighment = NULL
                WHERE custom_weighment IN %(weighments)s
            """, {"weighments": tuple(weighment_names)})

        # frappe.db.commit()

    def recreate_purchase_receipts(self, weighment_names):
        """Create fresh Purchase Receipts from Weighments and return their names."""
        if not weighment_names:
            gate_entry_doc = self.get_gate_entry_doc()
            if getattr(gate_entry_doc, "is_weighment_required", "Yes") in ["No", 0, "0", False] and getattr(gate_entry_doc, "entry_type", "") == "Inward":
                try:
                    import importlib
                    ge_module = importlib.import_module(gate_entry_doc.__module__)
                    if hasattr(ge_module, "make_purchase_receipt"):
                        pr_name = ge_module.make_purchase_receipt(gate_entry_doc)
                        if pr_name:
                            return [pr_name]
                except Exception as e:
                    pass

            frappe.msgprint("No Weighment found. Skipping Purchase Receipt creation.")
            return []

        created_prs = []
        for wname in weighment_names:
            weigh_doc = frappe.get_doc("Weighment", wname)
            weigh_doc.create_purchase_receipt_manually()

            pr_name = frappe.db.get_value(
                "Purchase Receipt Item",
                {"custom_weighment": wname},
                "parent",
                order_by="creation desc",
            )
            if pr_name:
                if weigh_doc.outward_date:
                    from frappe.utils import getdate, get_time
                    pr_doc = frappe.get_doc("Purchase Receipt", pr_name)
                    pr_doc.db_set("set_posting_time", 1, update_modified=False)
                    pr_doc.db_set("posting_date", getdate(weigh_doc.outward_date), update_modified=False)
                    pr_doc.db_set("posting_time", get_time(weigh_doc.outward_date), update_modified=False)
                created_prs.append(pr_name)

        return created_prs

    def replace_po_links(self, new_purchase_order, weighment_names):
        """Remove old PO child-table links and insert the new one for GE + Weighments."""
        frappe.db.sql("""
            DELETE FROM `tabPurchase Orders`
            WHERE parent = %s
        """, (self.gate_entry,))

        frappe.db.sql("""
            DELETE FROM `tabPurchase Orders`
            WHERE parent IN (
                SELECT name FROM `tabWeighment`
                WHERE gate_entry_number = %s
            )
        """, (self.gate_entry,))

        frappe.db.sql("""
            INSERT INTO `tabPurchase Orders`
            (name, parent, parenttype, parentfield, purchase_orders)
            VALUES (UUID(), %s, 'Gate Entry', 'purchase_orders', %s)
        """, (self.gate_entry, new_purchase_order))

        for wname in weighment_names:
            frappe.db.sql("""
                INSERT INTO `tabPurchase Orders`
                (name, parent, parenttype, parentfield, purchase_orders)
                VALUES (UUID(), %s, 'Weighment', 'purchase_orders', %s)
            """, (wname, new_purchase_order))

    def update_po_received_percentage(self, po_item_name):
        """Recalculate and update the gate_entry_received_percentage on the parent PO."""
        po_item = frappe.get_doc("Purchase Order Item", po_item_name)
        received_qty = frappe.db.get_value(
            "Purchase Order Item", po_item_name, "gate_entry_received_qty"
        ) or 0

        if po_item.qty:
            percentage = (received_qty / po_item.qty) * 100
            
            allowance = frappe.db.get_value(
                "Item", po_item.item_code, "over_delivery_receipt_allowance"
            ) or 0
            max_allowed_percentage = 100 + allowance

            if percentage > max_allowed_percentage:
                frappe.throw(
                    f"Gate Entry received percentage ({percentage:.2f}%) for item "
                    f"{po_item.item_code} exceeds the maximum allowed "
                    f"({max_allowed_percentage:.2f}%) based on Over Delivery/Receipt "
                    f"Allowance ({allowance}%)."
                )
                
            frappe.db.set_value(
                "Purchase Order",
                po_item.parent,
                "gate_entry_received_percentage",
                percentage,
                update_modified=False,
            )

    def update_field_on_related_docs(self, field_map_ge, field_map_weighment=None,field_map_pr=None):
        """
        Propagate field updates across Gate Entry, Weighments, and Purchase Receipts.

        Args:
            field_map_ge: dict of {field: value} to set on the Gate Entry doc.
            field_map_weighment: dict of {field: value} to set on each Weighment.
            field_map_pr: dict of {field: value} to set on non-cancelled Purchase Receipts.
        """
        gate_entry_doc = self.get_gate_entry_doc()
        for field, value in field_map_ge.items():
            gate_entry_doc.db_set(field, value, update_modified=False)

        if field_map_weighment:
            for wname in self.get_weighment_names():
                frappe.db.set_value(
                    "Weighment", wname, field_map_weighment, update_modified=False
                )

        if field_map_pr:
            for pr_name in self.get_linked_pr_names():
                docstatus = frappe.db.get_value("Purchase Receipt", pr_name, "docstatus")
                if int(docstatus or 0) == 2:
                    continue
                for field, value in field_map_pr.items():
                    frappe.db.set_value(
                        "Purchase Receipt", pr_name, field, value,
                        update_modified=False,
                    )

    def validate_quantity_rules(self):
        if not self.is_completed:
            frappe.throw("Gate Entry must be completed")

        for row in self.items:
            if row.new_accepted_qty < 0:
                frappe.throw(f"Negative qty not allowed for {row.item_code}")
            # if row.new_accepted_qty > row.po_item_qty:
            #     frappe.throw(f"Qty exceeds PO for {row.item_code}")

    def validate_transporter(self):
        gate_entry_doc = self.get_gate_entry_doc()
        if gate_entry_doc.vehicle_owner == "Company Owned":
            frappe.throw("Transporter cannot be changed for Company Owned vehicles.")

    def validate_card_number(self):
        gate_entry_doc = self.get_gate_entry_doc()

        if gate_entry_doc.is_completed == 1:
            frappe.throw("Cannot change Card Number for Completed Gate Entry.")

        new_card = frappe.get_doc("Card Details", self.newcorrect_card_number)

        if new_card.modified and new_card.modified > gate_entry_doc.creation:
            frappe.throw(
                "Selected Card has been recently freed AFTER Gate Entry creation. Not allowed."
            )
        if new_card.branch != gate_entry_doc.branch:
            frappe.throw("Card belongs to different Plant")
        if new_card.is_assigned:
            frappe.throw(f"Card {new_card.name} is already assigned")

    @frappe.whitelist()
    def load_gate_entry_data(self, correction_type=None):
        self.correction_type = correction_type or self.correction_type

        if not self.gate_entry:
            frappe.throw("Please select a Gate Entry first.")

        gate_entry_doc = self.get_gate_entry_doc()

        self.company = gate_entry_doc.company
        self.plant = gate_entry_doc.branch

        self.is_completed = 1 if gate_entry_doc.is_completed else 0
        self.is_in_progress = 1 if gate_entry_doc.is_in_progress else 0
        self.is_manual_weighment = 1 if getattr(gate_entry_doc, 'is_manual_weighment', 0) else 0
        self.is_stock_transfer = 1 if getattr(gate_entry_doc, 'is_stock_transfer', 0) else 0

        self.old_supplier = gate_entry_doc.supplier
        self.old_supplier_name = gate_entry_doc.supplier_name
        self.old_transporter = gate_entry_doc.transporter
        self.old_transporter_name = gate_entry_doc.transporter_name
        self.old_card_number = gate_entry_doc.card_number
        self.vehicle_owner = gate_entry_doc.vehicle_owner
        self.current_vehicle_no = gate_entry_doc.vehicle_number
        self.current_driver_name = gate_entry_doc.driver_name
        self.wrong_vehicle_type = gate_entry_doc.vehicle_type if hasattr(gate_entry_doc, 'vehicle_type') else ''

        weighment_names = self.get_weighment_names()

        if weighment_names:
            first_weighment = frappe.get_doc("Weighment", weighment_names[0])
            self.weighment_date = first_weighment.weighment_date
            self.inward_date = first_weighment.inward_date
            self.outward_date = first_weighment.outward_date
            self.tare_weight = first_weighment.tare_weight or 0
            self.gross_weight = first_weighment.gross_weight or 0
            self.net_weight = first_weighment.net_weight or 0

        items_data = []
        self.old_purchase_order = None

        if self.correction_type in ITEM_CORRECTION_TYPES:
            for row in gate_entry_doc.items:
                items_data.append({
                    "item_code": row.item_code,
                    "item_name": row.item_name,
                    "purchase_order": frappe.db.get_value(
                        "Purchase Order Item", row.purchase_order_item, "parent"
                    ),
                    "purchase_order_item": row.purchase_order_item,
                    "accepted_qty": row.accepted_quantity or 0,
                    "new_accepted_qty": row.accepted_quantity or 0,
                    "uom": row.uom,
                    "po_item_qty": row.qty or 0,
                    "gate_entry_item": row.name,
                    "current_gate_entry_received_qty": frappe.db.get_value(
                        "Purchase Order Item", row.purchase_order_item,
                        "gate_entry_received_qty"
                    ) or 0,
                })

            po_set = {
                frappe.db.get_value(
                    "Purchase Order Item", row.purchase_order_item, "parent"
                )
                for row in gate_entry_doc.items if row.purchase_order_item
            }
            po_list = [po for po in po_set if po]
            if po_list:
                self.old_purchase_order = po_list[0]

        self.old_segment = getattr(gate_entry_doc, 'segment', '') or ''

        return {
            "is_completed": self.is_completed,
            "is_in_progress": self.is_in_progress,
            "vehicle_owner": self.vehicle_owner,
            "items": items_data if self.correction_type in ITEM_CORRECTION_TYPES else [],
            "old_purchase_order": self.old_purchase_order,
            "is_stock_transfer": gate_entry_doc.is_stock_transfer if hasattr(gate_entry_doc, 'is_stock_transfer') else 0,
            "is_manual_weighment": gate_entry_doc.is_manual_weighment if hasattr(gate_entry_doc, 'is_manual_weighment') else 0,
            "entry_type": getattr(gate_entry_doc, 'entry_type', ''),
            "is_weighment_required": getattr(gate_entry_doc, 'is_weighment_required', 1),
            "old_segment": self.old_segment,
        }

    def check_existing_pr_status(self):
        """Return (status, pr_name) for the first linked PR found."""
        pr_names = self.get_linked_pr_names()
        if not pr_names:
            return "NO_PR", None

        for pr_name in pr_names:
            docstatus = frappe.db.get_value("Purchase Receipt", pr_name, "docstatus")
            if docstatus == 0:
                return "DRAFT", pr_name
            elif docstatus == 2:
                return "CANCELLED", pr_name
            elif docstatus == 1:
                return "SUBMITTED", pr_name

        return "NO_PR", None

    def check_existing_se_status(self):
        """Return (status, se_name) for the first linked Stock Entry found."""
        se_items = frappe.get_all("Stock Entry Detail", filters={"custom_gate_entry": self.gate_entry}, pluck="parent")
        if not se_items:
            return "NO_SE", None

        se_names = list(set(se_items))
        for se_name in se_names:
            docstatus = frappe.db.get_value("Stock Entry", se_name, "docstatus")
            if docstatus == 0:
                return "DRAFT", se_name
            elif docstatus == 2:
                return "CANCELLED", se_name
            elif docstatus == 1:
                return "SUBMITTED", se_name

        return "NO_SE", None

    def before_save(self):
        if self.gate_entry:
            ge_docstatus, entry_type = frappe.db.get_value(
                "Gate Entry", self.gate_entry, ["docstatus", "entry_type"]
            )
            if ge_docstatus == 2:
                frappe.throw("Cannot apply correction on cancelled Gate Entry.")
            if entry_type == "Outward" and self.correction_type not in ("Wrong Card Number", "Wrong Vehicle Type"):
                frappe.throw(
                    f"Selected Gate Entry <b>{self.gate_entry}</b> is an <b>Outward</b> entry. "
                    f"Use SMT for Outward Entries"
                )

        if self.correction_type == "Wrong Purchase Order and Supplier":
            if self.newcorrect_supplier and not self.new_purchase_order:
                frappe.throw("Please select Purchase Order along with Supplier.")

        needs_pr_validation = (
            self.correction_type == "Wrong Accepted Quantity"
            or (self.correction_type in ("Wrong Purchase Order", "Wrong Purchase Order and Supplier")
                and self.new_purchase_order)
        )

        if needs_pr_validation:
            status, pr_name = self.check_existing_pr_status()
            if status == "DRAFT":
                pr_link = frappe.utils.get_link_to_form("Purchase Receipt", pr_name)
                frappe.throw(
                    f"Please delete existing Draft Purchase Receipt {pr_link} before applying correction."
                )
            elif status == "SUBMITTED":
                pr_link = frappe.utils.get_link_to_form("Purchase Receipt", pr_name)
                frappe.throw(
                    f"Existing Submitted Purchase Receipt {pr_link} found. Please cancel it first."
                )

        if self.correction_type == "Wrong Weight" and getattr(self.get_gate_entry_doc(), "is_stock_transfer", 0):
            status, se_name = self.check_existing_se_status()
            if status == "DRAFT":
                se_link = frappe.utils.get_link_to_form("Stock Entry", se_name)
                frappe.throw(
                    f"Please delete existing Draft Stock Entry {se_link} before applying correction."
                )
            elif status == "SUBMITTED":
                se_link = frappe.utils.get_link_to_form("Stock Entry", se_name)
                frappe.throw(
                    f"Existing Submitted Stock Entry {se_link} found. Please cancel it first."
                )

    def validate(self):
        if self.correction_type == "Wrong Weight":
            gate_entry_doc = self.get_gate_entry_doc()
            is_manual = getattr(gate_entry_doc, 'is_manual_weighment', 0)
            is_stock = getattr(gate_entry_doc, 'is_stock_transfer', 0)
            is_completed = getattr(gate_entry_doc, 'is_completed', 0)
            is_in_progress = getattr(gate_entry_doc, 'is_in_progress', 0)

            if is_manual:
                # Manual weighment: allow both in-progress and completed
                if not is_completed and not is_in_progress:
                    frappe.throw(
                        "Wrong Weight correction for Manual Weighment requires the Gate Entry "
                        "to be either In Progress or Completed."
                    )
            elif is_stock:
                # Stock transfer: must be completed
                if not is_completed:
                    frappe.throw("Wrong Weight correction can only be applied to Completed Gate Entries.")

        if self.correction_type == "Inward/Outward Wrong Entry (Manual)" and self.gate_entry:
            gate_entry_doc = self.get_gate_entry_doc()
            if not getattr(gate_entry_doc, 'is_manual_weighment', 0):
                frappe.throw(
                    "'Inward/Outward Wrong Entry (Manual)' can only be applied to "
                    "Manual Weighment Gate Entries."
                )
            if not getattr(gate_entry_doc, 'is_in_progress', 0):
                frappe.throw(
                    "'Inward/Outward Wrong Entry (Manual)' can only be applied when "
                    "Gate Entry is In Progress (first weight taken, second weight pending)."
                )

        if self.correction_type in ITEM_CORRECTION_TYPES and self.gate_entry:
            gate_entry_doc = self.get_gate_entry_doc()
            is_stock_transfer = getattr(gate_entry_doc, 'is_stock_transfer', 0)
            is_manual_weighment = getattr(gate_entry_doc, 'is_manual_weighment', 0)
            entry_type = getattr(gate_entry_doc, 'entry_type', '')

            if is_stock_transfer:
                frappe.throw(
                    f"'{self.correction_type}' is not allowed for Stock Transfer Gate Entries."
                )
            if is_manual_weighment:
                frappe.throw(
                    f"'{self.correction_type}' is not allowed for Manual Weighment Gate Entries."
                )
            if entry_type == "Outward":
                frappe.throw(
                    f"'{self.correction_type}' is not allowed for Outward Gate Entries."
                )
        validators = {
            "Wrong Accepted Quantity": self.validate_quantity_rules,
            "Wrong Purchase Order": self.validate_quantity_rules,
            "Wrong Purchase Order and Supplier": self.validate_quantity_rules,
            "Wrong Transporter": self.validate_transporter,
            "Wrong Card Number": self.validate_card_number,
        }
        validator = validators.get(self.correction_type)
        if validator:
            validator()

        if self.correction_type == "Wrong Purchase Order" and self.new_purchase_order and self.old_purchase_order:
            old_supplier = frappe.db.get_value("Purchase Order", self.old_purchase_order, "supplier")
            new_supplier = frappe.db.get_value("Purchase Order", self.new_purchase_order, "supplier")
            if old_supplier and new_supplier and old_supplier != new_supplier:
                frappe.throw(
                    f"New Purchase Order ({self.new_purchase_order}) has a different Supplier "
                    f"than the Old Purchase Order ({self.old_purchase_order}). "
                    f"Please use Purchase Order of the same Supplier."
                )

        if self.correction_type in ("Wrong Purchase Order", "Wrong Purchase Order and Supplier") and self.new_purchase_order:
            po_status = frappe.db.get_value("Purchase Order", self.new_purchase_order, "status")
            if po_status in ("Closed", "Completed"):
                frappe.throw(
                    f"Selected Purchase Order <b>{self.new_purchase_order}</b> is "
                    f"<b>{po_status}</b>. Please choose an open Purchase Order."
                )

        self.validate_no_same_value()

    def validate_no_same_value(self):
        """Ensure new correction value is different from the old value for all correction types."""

        field_pairs = {
            "Wrong Purchase Order": [
                ("old_purchase_order", "new_purchase_order", "Purchase Order"),
            ],
            "Wrong Purchase Order and Supplier": [
                ("old_purchase_order", "new_purchase_order", "Purchase Order"),
                ("old_supplier", "newcorrect_supplier", "Supplier"),
            ],
            "Wrong Transporter": [
                ("old_transporter", "newcorrect_transporter", "Transporter"),
            ],
            "Wrong Card Number": [
                ("old_card_number", "newcorrect_card_number", "Card Number"),
            ],
            "Wrong Vehicle Number": [
                ("current_vehicle_no", "new_vehicle_no", "Vehicle Number"),
            ],
            "Wrong Driver Name": [
                ("current_driver_name", "new_driver_name", "Driver Name"),
            ],
            "Wrong Vehicle Type": [
                ("wrong_vehicle_type", "new_vehicle_type", "Vehicle Type"),
            ],
            "Wrong Segment": [
                ("old_segment", "newcorrect_segment", "Segment"),
            ],
        }

        pairs = field_pairs.get(self.correction_type, [])
        for old_field, new_field, label in pairs:
            old_val = self.get(old_field)
            new_val = self.get(new_field)
            if old_val and new_val and old_val == new_val:
                frappe.throw(
                    f"New {label} cannot be the same as the old {label} ({old_val})."
                )

        if self.correction_type == "Wrong Accepted Quantity":
            for row in self.items:
                if (row.accepted_qty is not None
                        and row.new_accepted_qty is not None
                        and row.accepted_qty == row.new_accepted_qty):
                    frappe.throw(
                        f"New Accepted Qty for {row.item_code} cannot be the same "
                        f"as the old Accepted Qty ({row.accepted_qty})."
                    )

    def before_submit(self):
        if self.correction_type == "Wrong Accepted Quantity":
            total_qty_kg = sum(
                self.convert_to_kg(row.new_accepted_qty, row.uom)
                for row in self.items
            )
            if total_qty_kg > self.net_weight:
                frappe.throw("Total Accepted Qty cannot be greater than Net Weight")

    def on_submit(self):
        
        if self.workflow_state == "Rejected":
            return
        
        correction_handlers = {
            "Wrong Accepted Quantity": self.correct_accepted_quantity,
            "Wrong Transporter": self.correct_transporter,
            "Wrong Card Number": self.correct_card_number,
            "Wrong Vehicle Number": self.correct_vehicle_number,
            "Wrong Driver Name": self.correct_driver_name,
            "Wrong Vehicle Type": self.correct_vehicle_type,
            "Wrong Weight": self.correct_weight,
            "Wrong Segment": self.correct_segment,
            "Inward/Outward Wrong Entry (Manual)": self.correct_entry_flow,
        }

        if self.correction_type == "Wrong Purchase Order and Supplier":
            if self.new_purchase_order:
                self.correct_purchase_order(
                    update_supplier=bool(self.newcorrect_supplier)
                )
        elif self.correction_type == "Wrong Purchase Order":
            if self.new_purchase_order:
                self.correct_purchase_order_only()
        else:
            handler = correction_handlers.get(self.correction_type)
            if handler:
                handler()

        self.db_set({
            "status": "Approved",
            "approved_on": frappe.utils.now(),
            "approved_by": frappe.session.user,
        })

        self.notify_related_docs()

    def notify_related_docs(self):
        """Update the related documents"""

        docs_to_refresh = []

        if self.gate_entry:
            docs_to_refresh.append(("Gate Entry", self.gate_entry))

        for wname in self.get_weighment_names():
            docs_to_refresh.append(("Weighment", wname))

        for pr_name in self.get_linked_pr_names():
            docs_to_refresh.append(("Purchase Receipt", pr_name))
            
            qi_names = frappe.get_all(
                "Quality Inspection",
                filters={"reference_type": "Purchase Receipt", "reference_name": pr_name, "docstatus": ["!=", 2]},
                pluck="name"
            )
            for qi in qi_names:
                docs_to_refresh.append(("Quality Inspection", qi))

            pi_items = frappe.get_all(
                "Purchase Invoice Item",
                filters={"purchase_receipt": pr_name, "docstatus": ["!=", 2]},
                pluck="parent"
            )
            for pi in list(set(pi_items)):
                docs_to_refresh.append(("Purchase Invoice", pi))

        all_pos = set()
        if self.old_purchase_order:
            all_pos.add(self.old_purchase_order)
        if self.new_purchase_order:
            all_pos.add(self.new_purchase_order)
        for row in self.items:
            if getattr(row, "purchase_order_item", None):
                po_name = frappe.db.get_value("Purchase Order Item", row.purchase_order_item, "parent")
                if po_name:
                    all_pos.add(po_name)

        for po_name in all_pos:
            docs_to_refresh.append(("Purchase Order", po_name))
            
            rb_names = frappe.get_all(
                "Rake Bill",
                filters={"purchase_order": po_name, "docstatus": ["<", 2]},
                pluck="name"
            )
            for rb in rb_names:
                docs_to_refresh.append(("Rake Bill", rb))

        for doctype, docname in docs_to_refresh:
            frappe.publish_realtime(
                "doc_update",
                {"modified": "force_reload", "doctype": doctype, "name": docname},
                doctype=doctype,
                docname=docname,
                after_commit=True,
            )

    def correct_accepted_quantity(self):
        """Update accepted quantities on Gate Entry, Weighment, and PO; then recreate PRs."""

        for row in self.items:
            rejected_qty = frappe.db.get_value("Purchase Details", row.gate_entry_item, "rejected_quantity") or 0
            new_received_qty = (row.new_accepted_qty or 0) + rejected_qty
            frappe.db.set_value(
                "Purchase Details",
                row.gate_entry_item,
                {"accepted_quantity": row.new_accepted_qty,
                "received_quantity": new_received_qty},
                update_modified=False,
            )

        weighment_names = self.get_weighment_names()
        
        total_qty_kg = 0
        for row in self.items:
            rejected_qty = frappe.db.get_value("Purchase Details", row.gate_entry_item, "rejected_quantity") or 0
            new_received_qty = (row.new_accepted_qty or 0) + rejected_qty
            total_qty_kg += self.convert_to_kg(new_received_qty, row.uom)

        for weigh_doc in self.get_weighment_docs(weighment_names):
            for w_item in weigh_doc.items:
                for row in self.items:
                    if w_item.purchase_order_item == row.purchase_order_item:
                        rejected_qty = getattr(w_item, "rejected_quantity", 0) or 0
                        new_received_qty = (row.new_accepted_qty or 0) + rejected_qty
                        w_item.db_set("accepted_quantity", row.new_accepted_qty, update_modified=False)
                        w_item.db_set("received_quantity", new_received_qty, update_modified=False)

            current_weights = frappe.db.get_value(
                "Weighment", weigh_doc.name,
                ["tare_weight", "gross_weight"],
                as_dict=True
            )
            db_tare = current_weights.tare_weight or 0
            db_gross = current_weights.gross_weight or 0
            pms_tare = self.tare_weight or 0
            pms_gross = self.gross_weight or 0
            weights_changed = (pms_tare != db_tare) or (pms_gross != db_gross)

            if weights_changed:
                frappe.db.set_value(
                    "Weighment", weigh_doc.name,
                    {
                        "tare_weight": pms_tare,
                        "gross_weight": pms_gross,
                        "net_weight": self.net_weight or 0,
                    },
                    update_modified=False,
                )
            else:
                frappe.db.set_value(
                    "Weighment", weigh_doc.name,
                    {
                        "net_weight": total_qty_kg,
                        "tare_weight": db_gross - total_qty_kg,
                    },
                    update_modified=False,
                )

        for row in self.items:
            if not row.purchase_order_item:
                continue

            old_received = frappe.db.get_value(
                "Purchase Order Item", row.purchase_order_item,
                "gate_entry_received_qty"
            ) or 0

            delta = (row.new_accepted_qty or 0) - (row.accepted_qty or 0)
            new_received = old_received + delta

            frappe.db.set_value(
                "Purchase Order Item", row.purchase_order_item,
                "gate_entry_received_qty", new_received,
                update_modified=False,
            )
            self.update_po_received_percentage(row.purchase_order_item)
            po_name = frappe.db.get_value("Purchase Order Item", row.purchase_order_item, "parent")
            self.update_rake_bill(po_name, delta)

        self.unlink_purchase_receipts(weighment_names)
        created_prs = self.recreate_purchase_receipts(weighment_names)

        # Recalculate robust factory_received_qty mathematically
        affected_pos = set()
        for row in self.items:
            if getattr(row, "purchase_order_item", None):
                po_name = frappe.db.get_value("Purchase Order Item", row.purchase_order_item, "parent")
                if po_name:
                    affected_pos.add(po_name)
        for po in affected_pos:
            self.recalc_rake_bill_factory_received_qty(po)

        if created_prs:
            frappe.msgprint(
                f"Purchase Receipt created: {', '.join(created_prs)}"
            )

    def update_rake_bill(self, po_name, qty_diff):
        """Update Rake Bill fields if PO incoterm is RRB/Rail Rack, adjusting quantities by qty_diff."""
        if not po_name or not qty_diff: return
        incoterm = frappe.db.get_value("Purchase Order", po_name, "incoterm")
        if incoterm in ["Rail Rack", "RRB", "Rail Rake"]:
            rb_name = frappe.db.get_value("Rake Bill", {"purchase_order": po_name, "docstatus": ["<", 2]})
            if not rb_name: return
            
            rb = frappe.get_doc("Rake Bill", rb_name)
            
            new_ge_received_qty = (rb.gate_entry_received_qty or 0) + qty_diff
            
            if new_ge_received_qty > (rb.billed_qty or 0):
                frappe.throw(
                    f"Gate Entry Received Qty ({new_ge_received_qty}) cannot be greater than "
                    f"Billed Qty ({rb.billed_qty}) on Rake Bill {rb.name} for Purchase Order {po_name}"
                )

            new_billed_to_after_tolerance = new_ge_received_qty + (rb.tolerance_qty or 0)
            new_short_billed_qty = (rb.billed_qty or 0) - new_ge_received_qty
            new_debit_note_qty = new_short_billed_qty - (rb.tolerance_qty or 0)
            
            rb.db_set("gate_entry_received_qty", new_ge_received_qty, update_modified=False)
            rb.db_set("billed_to_after_tolerance", new_billed_to_after_tolerance, update_modified=False)
            rb.db_set("short_billed_qty", new_short_billed_qty, update_modified=False)
            rb.db_set("debit_note_qty", new_debit_note_qty, update_modified=False)

    def recalc_rake_bill_factory_received_qty(self, po_name):
        if not po_name: return
        incoterm = frappe.db.get_value("Purchase Order", po_name, "incoterm")
        if incoterm in ["Rail Rack", "RRB", "Rail Rake"]:
            rb_name = frappe.db.get_value("Rake Bill", {"purchase_order": po_name, "docstatus": ["<", 2]})
            if not rb_name: return
            
            sql = """
                SELECT IFNULL(SUM(net_weight), 0)
                FROM `tabWeighment` w
                WHERE w.docstatus = 1
                AND EXISTS (
                    SELECT 1 FROM `tabPurchase Orders` 
                    WHERE parent = w.name 
                    AND parenttype = 'Weighment' 
                    AND purchase_orders = %s
                )
            """
            new_factory_received_qty = frappe.db.sql(sql, (po_name,))[0][0]
            frappe.db.set_value("Rake Bill", rb_name, "factory_received_qty", new_factory_received_qty, update_modified=False)

    def correct_purchase_order_only(self):
        """Correct only the PO on GE, Weighments, and PO items; then recreate PRs. No supplier change."""
        if not self.new_purchase_order:
            frappe.throw("New Purchase Order is required")

        weighment_names = self.get_weighment_names()
        weigh_docs = self.get_weighment_docs(weighment_names)
        affected_po_items = set()

        for row in self.items:
            if not row.purchase_order_item:
                continue

            new_po_item_name = frappe.db.get_value(
                "Purchase Order Item",
                {"parent": self.new_purchase_order, "item_code": row.item_code},
                "name",
            )
            if not new_po_item_name:
                frappe.throw(f"Item {row.item_code} not found in new PO")

            old_po_item = frappe.get_doc("Purchase Order Item", row.purchase_order_item)
            new_po_item = frappe.get_doc("Purchase Order Item", new_po_item_name)
            accepted_qty = row.accepted_qty or 0

            frappe.db.set_value(
                "Purchase Order Item", old_po_item.name,
                "gate_entry_received_qty",
                (old_po_item.gate_entry_received_qty or 0) - accepted_qty,
                update_modified=False,
            )

            frappe.db.set_value(
                "Purchase Order Item", new_po_item.name,
                "gate_entry_received_qty",
                (new_po_item.gate_entry_received_qty or 0) + accepted_qty,
                update_modified=False,
            )

            self.update_rake_bill(old_po_item.parent, -accepted_qty)
            self.update_rake_bill(self.new_purchase_order, accepted_qty)

            affected_po_items.add(old_po_item.name)
            affected_po_items.add(new_po_item.name)

            frappe.db.set_value(
                "Purchase Details", row.gate_entry_item,
                {"purchase_order": self.new_purchase_order,
                "purchase_order_item": new_po_item.name},
                update_modified=False,
            )

            for weigh_doc in weigh_docs:
                for w_item in weigh_doc.items:
                    if w_item.purchase_order_item == row.purchase_order_item:
                        w_item.db_set("purchase_order", self.new_purchase_order, update_modified=False)
                        w_item.db_set("purchase_order_item", new_po_item.name, update_modified=False)

        for po_item_name in affected_po_items:
            self.update_po_received_percentage(po_item_name)

        self.replace_po_links(self.new_purchase_order, weighment_names)
        self.unlink_purchase_receipts(weighment_names)
        created_prs = self.recreate_purchase_receipts(weighment_names)

        self.recalc_rake_bill_factory_received_qty(self.old_purchase_order)
        self.recalc_rake_bill_factory_received_qty(self.new_purchase_order)

        if created_prs:
            frappe.msgprint(
                f"Purchase Receipt created: {', '.join(created_prs)}"
            )

    def correct_purchase_order(self, update_supplier=False):
        """Correct the PO and Supplier on GE, Weighments, and PO items; then recreate PRs."""
        if not self.new_purchase_order:
            frappe.throw("New Purchase Order is required")
        if update_supplier and not self.newcorrect_supplier:
            frappe.throw("New Supplier is required")

        weighment_names = self.get_weighment_names()
        weigh_docs = self.get_weighment_docs(weighment_names)
        affected_po_items = set()

        for row in self.items:
            if not row.purchase_order_item:
                continue

            new_po_item_name = frappe.db.get_value(
                "Purchase Order Item",
                {"parent": self.new_purchase_order, "item_code": row.item_code},
                "name",
            )
            if not new_po_item_name:
                frappe.throw(f"Item {row.item_code} not found in new PO")

            old_po_item = frappe.get_doc("Purchase Order Item", row.purchase_order_item)
            new_po_item = frappe.get_doc("Purchase Order Item", new_po_item_name)
            accepted_qty = row.accepted_qty or 0

            frappe.db.set_value(
                "Purchase Order Item", old_po_item.name,
                "gate_entry_received_qty",
                (old_po_item.gate_entry_received_qty or 0) - accepted_qty,
                update_modified=False,
            )

            frappe.db.set_value(
                "Purchase Order Item", new_po_item.name,
                "gate_entry_received_qty",
                (new_po_item.gate_entry_received_qty or 0) + accepted_qty,
                update_modified=False,
            )

            self.update_rake_bill(old_po_item.parent, -accepted_qty)
            self.update_rake_bill(self.new_purchase_order, accepted_qty)

            affected_po_items.add(old_po_item.name)
            affected_po_items.add(new_po_item.name)

            frappe.db.set_value(
                "Purchase Details", row.gate_entry_item,
                {"purchase_order": self.new_purchase_order,
                "purchase_order_item": new_po_item.name},
                update_modified=False,
            )

            for weigh_doc in weigh_docs:
                for w_item in weigh_doc.items:
                    if w_item.purchase_order_item == row.purchase_order_item:
                        w_item.db_set("purchase_order", self.new_purchase_order,update_modified=False)
                        w_item.db_set("purchase_order_item", new_po_item.name,
                        update_modified=False)

        for po_item_name in affected_po_items:
            self.update_po_received_percentage(po_item_name)

        if update_supplier:
            supplier_name = frappe.db.get_value(
                "Supplier", self.newcorrect_supplier, "supplier_name"
            )

            frappe.db.set_value(
                "Gate Entry", self.gate_entry,
                {"supplier": self.newcorrect_supplier,
                "supplier_name": supplier_name},
                update_modified=False,
            )

            for wname in weighment_names:
                frappe.db.set_value(
                    "Weighment", wname,
                    {"supplier": self.newcorrect_supplier,
                    "supplier_name": supplier_name},
                    update_modified=False,
                )

        self.replace_po_links(self.new_purchase_order, weighment_names)
        self.unlink_purchase_receipts(weighment_names)
        created_prs = self.recreate_purchase_receipts(weighment_names)

        self.recalc_rake_bill_factory_received_qty(self.old_purchase_order)
        self.recalc_rake_bill_factory_received_qty(self.new_purchase_order)

        action = "Purchase Order & Supplier" if update_supplier else "Purchase Order"
        if created_prs:
            frappe.msgprint(
                f"Purchase Receipt created: {', '.join(created_prs)}"
            )

    def correct_transporter(self):
        if not self.newcorrect_transporter:
            frappe.throw("New Transporter is required")

        transporter_name = frappe.db.get_value(
            "Supplier", self.newcorrect_transporter, "supplier_name"
        )

        self.update_field_on_related_docs(
            field_map_ge={
                "transporter": self.newcorrect_transporter,
                "transporter_name": transporter_name,
            },
            field_map_weighment={
                "transporter": self.newcorrect_transporter,
                "transporter_name": transporter_name,
            },
            field_map_pr={
                "transporter": self.newcorrect_transporter,
                "transporter_name": transporter_name,
            },
        )
        frappe.msgprint("Transporter updated successfully")

    def correct_card_number(self):
        gate_entry_doc = self.get_gate_entry_doc()

        if not gate_entry_doc.card_number:
            frappe.throw("No existing card found on Gate Entry")

        old_card = frappe.get_doc("Card Details", gate_entry_doc.card_number)
        new_card = frappe.get_doc("Card Details", self.newcorrect_card_number)

        old_card.db_set("is_assigned", 0, update_modified=False)
        gate_entry_doc.db_set("card_number", new_card.name, update_modified=False)
        new_card.db_set("is_assigned", 1, update_modified=False)

        if self.reason:
            comment_content = (
				f"{self.owner} changed the card number from {gate_entry_doc.card_number} to {self.newcorrect_card_number} <br>"
				f"Reason: {self.reason}"
			)
            frappe.get_doc({
                "doctype": "Comment",
                "comment_type": "Comment",
                "reference_doctype": "Gate Entry",
                "reference_name": gate_entry_doc.name,
                "content": comment_content,
            }).insert(ignore_permissions=True)

        frappe.msgprint("Card Number updated successfully")


    def correct_vehicle_number(self):
        if not self.new_vehicle_no:
            frappe.throw("New Vehicle Number is required.")

        self.update_field_on_related_docs(
            field_map_ge={
                "vehicle_number": self.new_vehicle_no,
                "vehicle": self.new_vehicle_no,
            },
            field_map_weighment={
                "vehicle_number": self.new_vehicle_no,
                "vehicle": self.new_vehicle_no,
            },
            field_map_pr={
                "vehicle_no": self.new_vehicle_no,
            },
        )

        for pr_name in self.get_linked_pr_names():
            qi_names = frappe.get_all(
                "Quality Inspection",
                filters={"reference_type": "Purchase Receipt", "reference_name": pr_name, "docstatus": ["!=", 2]},
                pluck="name"
            )
            for qi in qi_names:
                frappe.db.set_value("Quality Inspection", qi, "custom_vehicle_no", self.new_vehicle_no, update_modified=False)
            
            pi_items = frappe.get_all(
                "Purchase Invoice Item",
                filters={"purchase_receipt": pr_name, "docstatus": ["!=", 2]},
                pluck="parent"
            )
            for pi in list(set(pi_items)):
                frappe.db.set_value("Purchase Invoice", pi, "vehicle_no", self.new_vehicle_no, update_modified=False)

        frappe.msgprint("Vehicle Number updated successfully")

    def correct_driver_name(self):
        if not self.new_driver_name:
            frappe.throw("New Driver Name is required.")

        self.update_field_on_related_docs(
            field_map_ge={"driver_name": self.new_driver_name},
            field_map_weighment={"driver_name": self.new_driver_name},
            field_map_pr={"driver_name": self.new_driver_name},
        )
        frappe.msgprint("Driver Name updated successfully")

    def correct_vehicle_type(self):
        if not self.new_vehicle_type:
            frappe.throw("New Vehicle Type is required.")

        self.update_field_on_related_docs(
            field_map_ge={"vehicle_type": self.new_vehicle_type},
            field_map_weighment={"vehicle_type": self.new_vehicle_type},
        )
        frappe.msgprint("Vehicle Type updated successfully")

    def correct_entry_flow(self):
        """Swap Inward → Outward (or vice-versa) for Manual Weighment entries.

        Weight swap logic (Inward → Outward):
          - tare_weight  = current gross_weight   (first weight becomes tare)
          - gross_weight = 0                      (second weight not yet taken)
          - net_weight   = 0                      (unchanged / zero)
        """
        gate_entry_doc = self.get_gate_entry_doc()
        current_type = getattr(gate_entry_doc, 'entry_type', 'Inward')
        new_type = "Outward" if current_type == "Inward" else "Inward"

        # Update Gate Entry entry_type
        gate_entry_doc.db_set("entry_type", new_type, update_modified=False)

        # Update each linked Weighment
        for wname in self.get_weighment_names():
            current_gross = frappe.db.get_value("Weighment", wname, "gross_weight") or 0

            if new_type == "Outward":
                # Was Inward: first weight (gross) becomes tare; gross reset to 0
                wei_data = {
                    "entry_type": new_type,
                    "tare_weight": current_gross,
                    "gross_weight": 0,
                    "net_weight": 0,
                }
            else:
                # Was Outward: first weight (tare) becomes gross; tare reset to 0
                current_tare = frappe.db.get_value("Weighment", wname, "tare_weight") or 0
                wei_data = {
                    "entry_type": new_type,
                    "gross_weight": current_tare,
                    "tare_weight": 0,
                    "net_weight": 0,
                }

            frappe.db.set_value("Weighment", wname, wei_data, update_modified=False)

        frappe.msgprint(
            f"Entry type swapped from <b>{current_type}</b> to <b>{new_type}</b>. "
            f"Weights adjusted accordingly."
        )

    def correct_segment(self):
        """Update segment across Gate Entry, Weighment, Purchase Receipt and Purchase Invoice."""
        if not self.newcorrect_segment:
            frappe.throw("New Segment is required.")

        new_seg = self.newcorrect_segment

        # 1. Gate Entry
        gate_entry_doc = self.get_gate_entry_doc()
        gate_entry_doc.db_set("segment", new_seg, update_modified=False)

        # 2. Weighments
        for wname in self.get_weighment_names():
            frappe.db.set_value("Weighment", wname, "segment", new_seg, update_modified=False)

        # 3. Purchase Receipts — header, items, taxes
        for pr_name in self.get_linked_pr_names():
            if int(frappe.db.get_value("Purchase Receipt", pr_name, "docstatus") or 0) == 2:
                continue
            frappe.db.set_value("Purchase Receipt", pr_name, "segment", new_seg, update_modified=False)
            frappe.db.sql(
                "UPDATE `tabPurchase Receipt Item` SET segment = %s WHERE parent = %s",
                (new_seg, pr_name)
            )
            frappe.db.sql(
                "UPDATE `tabPurchase Taxes and Charges` SET segment = %s WHERE parent = %s AND parenttype = 'Purchase Receipt'",
                (new_seg, pr_name)
            )

        # 4. Purchase Invoices linked via PR items
        pi_names = list(set(frappe.get_all(
            "Purchase Invoice Item",
            filters={"purchase_receipt": ["in", self.get_linked_pr_names()]},
            pluck="parent",
        )))
        for pi_name in pi_names:
            if int(frappe.db.get_value("Purchase Invoice", pi_name, "docstatus") or 0) == 2:
                continue
            frappe.db.set_value("Purchase Invoice", pi_name, "segment", new_seg, update_modified=False)
            frappe.db.sql(
                "UPDATE `tabPurchase Invoice Item` SET segment = %s WHERE parent = %s",
                (new_seg, pi_name)
            )
            frappe.db.sql(
                "UPDATE `tabPurchase Taxes and Charges` SET segment = %s WHERE parent = %s AND parenttype = 'Purchase Invoice'",
                (new_seg, pi_name)
            )

        frappe.msgprint(f"Segment updated Sucessfully")

    def correct_weight(self):
        """Update gross, tare, and net weights on Weighment only. Recreates SE for Stock Transfers.
        For in-progress manual weighment entries, also completes the GE + Weighment and frees the card."""
        gross = self.gross_weight or 0
        tare = self.tare_weight or 0

        gate_entry_doc = self.get_gate_entry_doc()
        is_manual = getattr(gate_entry_doc, 'is_manual_weighment', 0)


        net = (self.net_weight or 0) if is_manual else (gross - tare)

        weighment_names = self.get_weighment_names()
        for wname in weighment_names:
            frappe.db.set_value(
                "Weighment", wname,
                {"gross_weight": gross,
                "tare_weight": tare,
                "net_weight": net},
                update_modified=False,
            )

        is_in_progress = getattr(gate_entry_doc, 'is_in_progress', 0)

        # For in-progress manual weighment: complete the GE + Weighment and free the card
        if is_manual and is_in_progress:
            gate_entry_doc.db_set(
                {"is_completed": 1, "is_in_progress": 0},
                update_modified=False,
            )
            for wname in weighment_names:
                frappe.db.set_value(
                    "Weighment", wname,
                    {"is_completed": 1, "is_in_progress": 0},
                    update_modified=False,
                )
            # Free the card assigned to the gate entry
            card_number = getattr(gate_entry_doc, 'card_number', None)
            if card_number:
                frappe.db.set_value(
                    "Card Details", card_number, "is_assigned", 0,
                    update_modified=False,
                )
            frappe.msgprint(
                f"Weight updated successfully."
            )
            return

        if getattr(gate_entry_doc, "is_stock_transfer", 0) and getattr(gate_entry_doc, "entry_type", "") == "Inward":
            se_items = frappe.get_all("Stock Entry Detail", filters={"custom_gate_entry": self.gate_entry}, pluck="parent")
            if se_items:
                cancelled_ses = frappe.get_all(
                    "Stock Entry", 
                    filters={"name": ["in", list(set(se_items))], "docstatus": 2}, 
                    pluck="name"
                )
                for se_name in cancelled_ses:
                    frappe.db.sql("UPDATE `tabStock Entry Detail` SET custom_gate_entry = NULL WHERE parent = %s", (se_name,))
                    try:
                        frappe.db.set_value("Stock Entry", se_name, "custom_weighment_reference", None)
                    except Exception:
                        pass

            import importlib
            from frappe.utils import getdate, get_time, get_link_to_form
            created_ses = []
            for wname in weighment_names:
                weigh_doc = frappe.get_doc("Weighment", wname)
                try:
                    weighment_module = importlib.import_module(weigh_doc.__module__)
                    if hasattr(weighment_module, "make_stockentry"):
                        se_name = weighment_module.make_stockentry(weigh_doc)
                        if se_name:
                            se_doc = frappe.get_doc("Stock Entry", se_name)
                            if weigh_doc.outward_date:
                                se_doc.db_set("set_posting_time", 1)
                                se_doc.db_set("posting_date", getdate(weigh_doc.outward_date))
                                se_doc.db_set("posting_time", get_time(weigh_doc.outward_date))
                            se_doc.submit()
                            created_ses.append(get_link_to_form("Stock Entry", se_name))
                    else:
                        frappe.throw(f"Function make_stockentry not found in module {weigh_doc.__module__}")
                except Exception as e:
                    frappe.throw(f"Error calling make_stockentry: {str(e)}")

            if created_ses:
                frappe.msgprint(f"Weight updated and Stock Entries recreated: {', '.join(created_ses)}")
            else:
                frappe.msgprint("Weight updated successfully")
        else:
            frappe.msgprint("Weight updated successfully")

    # def recreate_stock_entry_for_weight(self, weigh_doc):
    #     company_cost_center = frappe.get_value("Branch", weigh_doc.branch, "custom_default_cost_center_for_stock_transfer")
        
    #     stock_entry = frappe.new_doc("Stock Entry")
    #     stock_entry.stock_entry_type = "Material Transfer"
    #     stock_entry.company = weigh_doc.company
    #     stock_entry.posting_date = frappe.utils.nowdate()
    #     stock_entry.branch = getattr(weigh_doc, "branch", "")
    #     stock_entry.custom_transporter = getattr(weigh_doc, "transporter", "")
    #     stock_entry.custom_vehicle_number = getattr(weigh_doc, "vehicle_number", "")
    #     stock_entry.custom_weighment_reference = weigh_doc.name
    #     stock_entry.custom_gate_entry = weigh_doc.gate_entry_number
        
    #     for item in weigh_doc.stock_entry_items:
    #         stock_entry.append("items", {
    #             "item_code": item.item_code,
    #             "qty": weigh_doc.net_weight or 0,
    #             "uom": getattr(item, "uom", ""),
    #             "s_warehouse": getattr(item, "source_warehouse", ""),
    #             "t_warehouse": getattr(item, "target_warehouse", ""),
    #             "conversion_factor": 1,
    #             "cost_center": company_cost_center,
    #             "custom_gate_entry": weigh_doc.gate_entry_number,
    #         })

    #     stock_entry.insert()
    #     frappe.msgprint(f"Stock Entry {frappe.utils.get_link_to_form('Stock Entry', stock_entry.name)} created for Weighment {weigh_doc.name}")


@frappe.whitelist()
def get_filtered_purchase_orders(doctype, txt, searchfield, start, page_len, filters):
    company = filters.get("company")
    plant = filters.get("plant")
    item_codes = filters.get("item_codes") or []
    existing_pos = filters.get("existing_pos") or []

    if not company or not plant:
        return []

    existing_pos = tuple(existing_pos) if existing_pos else ("",)
    searchfield = searchfield or "name"

    item_condition = "AND poi.item_code IN %(item_codes)s" if item_codes else ""

    return frappe.db.sql(f"""
        SELECT DISTINCT
            po.name,
            CONCAT(
                po.supplier_name, ', ',
                po.transaction_date, ', ',
                po.rounded_total
            ) AS description
        FROM `tabPurchase Order` po
        INNER JOIN `tabPurchase Order Item` poi
            ON poi.parent = po.name
        WHERE po.company = %(company)s
        AND po.branch = %(plant)s
        AND po.docstatus = 1
        AND po.status NOT IN ('Closed', 'Completed')
        AND po.name NOT IN %(existing_pos)s
        {item_condition}
        AND po.{searchfield} LIKE %(txt)s
        ORDER BY po.modified DESC
        LIMIT %(start)s, %(page_len)s
    """, {
        "company": company,
        "plant": plant,
        "item_codes": tuple(item_codes) if item_codes else (),
        "existing_pos": existing_pos,
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len,
    })
