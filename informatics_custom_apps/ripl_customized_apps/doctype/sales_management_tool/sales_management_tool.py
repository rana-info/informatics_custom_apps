import frappe
from frappe.model.document import Document

class SalesManagementTool(Document):
    def before_save(self):
        """Run correction validations before save for immediate user feedback."""
        self.validate_no_same_value()

        if self.deal_correction:
            if self.correction_type and self.correction_type != "Wrong Sales Partner":
                frappe.throw(
                    f"'{self.correction_type}' cannot be tackled in Deal Correction mode. "
                    f"Only 'Wrong Sales Partner' is allowed when Deal Correction is enabled."
                )
            return 

        self.validate_in_progress_only_corrections()
        self.validate_reset_second_weight_conditions()

        validators = {
            "Wrong Transporter": self.validate_transporter,
            "Wrong Card Number": self.validate_card_number,
            "Wrong Item Group": self.validate_item_group,
        }
        validator = validators.get(self.correction_type)
        if validator:
            validator()

    def validate(self):
        """Initial data validation and prerequisite checks."""
        if self.gate_entry:
            ge_data = frappe.db.get_all("Gate Entry", filters={"name": self.gate_entry}, fields=["docstatus", "entry_type"])
            if ge_data:
                if ge_data[0].docstatus == 2:
                    frappe.throw("Target Gate Entry is cancelled. Correction not possible.")
                if ge_data[0].entry_type != "Outward":
                    if self.correction_type != "Inward/Outward Wrong Entry (Manual)":
                        frappe.throw("Sales Management System handles Outward entries. Use Purchase module for Inward.")

    def validate_no_same_value(self):
        """Ensure new correction value is different from old value for key correction types."""
        field_pairs = {
            "Wrong Vehicle Number": ("current_vehicle_no", "new_vehicle_no", "Vehicle Number"),
            "Wrong Driver Name": ("current_driver_name", "new_driver_name", "Driver Name"),
            "Wrong Card Number": ("old_card_number", "newcorrect_card_number", "Card Number"),
            "Wrong Transporter": ("old_transporter", "newcorrect_transporter", "Transporter"),
            "Wrong Vehicle Type": ("wrong_vehicle_type", "new_vehicle_type", "Vehicle Type"),
            "Wrong Sales Partner": ("wrong_sales_partner", "new_sales_partner", "Sales Partner"),
        }

        pair = field_pairs.get(self.correction_type)
        if not pair:
            return

        old_field, new_field, label = pair
        old_val = self.get(old_field)
        new_val = self.get(new_field)

        if old_val and new_val and old_val == new_val:
            frappe.throw(
                f"New {label} cannot be the same as the old {label} ({old_val})."
            )

    def validate_transporter(self):
        """Reuse transporter guard similar to Purchase Management System."""
        if not self.gate_entry:
            return
        gate_entry_doc = frappe.get_doc("Gate Entry", self.gate_entry)
        if gate_entry_doc.get("vehicle_owner") == "Company Owned":
            frappe.throw("Transporter cannot be changed for Company Owned vehicles.")

    def validate_card_number(self):
        """Reuse card validation pattern similar to Purchase Management System."""
        if not self.gate_entry or not self.newcorrect_card_number:
            return

        gate_entry_doc = frappe.get_doc("Gate Entry", self.gate_entry)
        self.validate_gate_entry_in_progress_only("Wrong Card Number correction")

        new_card = frappe.get_doc("Card Details", self.newcorrect_card_number)
        if new_card.modified and new_card.modified > gate_entry_doc.creation:
            frappe.throw(
                "Selected Card has been recently freed AFTER Gate Entry creation. Not allowed."
            )
        if new_card.branch != gate_entry_doc.branch:
            frappe.throw("Card belongs to different Plant")
        if new_card.is_assigned:
            frappe.throw(f"Card {new_card.name} is already assigned")

    def validate_item_group(self):
        """Prevent item group change if Delivery Note exists."""
        
        if not self.gate_entry:
            return

        self.validate_gate_entry_in_progress_only("Wrong Item Group correction")

        weighments = self.get_related_weighments()

        for wname in weighments:
            dn_exists = frappe.db.exists(
                "Delivery Note",
                {"custom_weighment": wname, "docstatus": ["<", 2]}
            )

            if dn_exists:
                frappe.throw(
                    f"Item Group cannot be changed because Delivery Note {dn_exists} is already linked with Weighment {wname}."
                )

    def validate_in_progress_only_corrections(self):
        """Enforce in-progress gate-entry status for selected correction types."""
        in_progress_only_corrections = {
            "Wrong Item Group",
            "Wrong Delivery Note",
            "Inward/Outward Wrong Entry (Manual)",
        }
        if self.correction_type in in_progress_only_corrections:
            self.validate_gate_entry_in_progress_only(f"{self.correction_type} correction")

    def validate_reset_second_weight_conditions(self):
        """Allow reset second-weight corrections only for completed outward entries."""
        if self.correction_type not in {"Reset Second Weight (Not Manual)", "Reset Second Weight (Manual)"}:
            return

        ge_status = frappe.db.get_value(
            "Gate Entry",
            self.gate_entry,
            ["entry_type", "is_in_progress", "is_completed"],
            as_dict=1
        )
        if not ge_status:
            frappe.throw("Gate Entry not found.")

        if not (
            ge_status.entry_type == "Outward"
            and ge_status.is_in_progress == 0
            and ge_status.is_completed == 1
        ):
            frappe.throw(
                "Reset Second Weight is allowed only when Gate Entry is Outward, Completed, and not In Progress."
            )

    def on_submit(self):
        """Atomic transaction handler for applying outward corrections."""
        
        if self.workflow_state == "Rejected":
            return
        
        handlers = {
            "Wrong Vehicle Number": self.correct_vehicle_metadata,
            "Wrong Driver Name": self.correct_vehicle_metadata,
            "Wrong Transporter": self.correct_vehicle_metadata,
            "Wrong Vehicle Type": self.correct_vehicle_metadata,
            "Wrong Card Number": self.handle_card_rotation,
            "Reset Second Weight (Not Manual)": self.reset_weighment_complete,
            "Reset Second Weight (Manual)": self.reset_weighment_manual,
            "Wrong Delivery Note": self.rotate_delivery_note,
            "Inward/Outward Wrong Entry (Manual)": self.swap_entry_flow,
            "Wrong Item Group": self.handle_item_group_correction,
            "Wrong Sales Partner": self.handle_sales_partner_correction,
        }

        handler = handlers.get(self.correction_type)
        if not handler:
            frappe.throw(f"No logic implemented for correction type: {self.correction_type}")

        handler()
        frappe.msgprint(f"{self.correction_type} correction has been applied successfully.")

        self.db_set({
            "status": "Approved",
            "approved_on": frappe.utils.now(),
            "approved_by": frappe.session.user
        })

        self.notify_related_docs()

    def get_related_weighments(self):
        """Fetch all active weighments for the gate entry."""
        return frappe.get_all("Weighment", filters={"gate_entry_number": self.gate_entry, "docstatus": ["<", 2]}, pluck="name")

    def validate_gate_entry_in_progress_only(self, action_label):
        """Allow specific corrections only when gate entry is in progress and not completed."""
        ge_status = frappe.db.get_value(
            "Gate Entry",
            self.gate_entry,
            ["is_completed", "is_in_progress"],
            as_dict=1
        )

        if not ge_status:
            frappe.throw("Gate Entry not found.")

        if ge_status.is_completed:
            frappe.throw(
                f"{action_label} is not allowed because Gate Entry is completed. "
            )

        if not ge_status.is_in_progress:
            frappe.throw(
                f"{action_label} is allowed only when Gate Entry is In Progress."
            )

    def correct_vehicle_metadata(self):
        """Updates metadata (Vehicle, Driver, Transporter) across GE, Weighment, DN, and SI."""
        weighments = self.get_related_weighments()
        
        ge_updates = {}
        wei_updates = {}
        others_updates = {}

        if self.correction_type == "Wrong Vehicle Number":
            if not self.new_vehicle_no: frappe.throw("New Vehicle Number is mandatory.")
            ge_updates.update({"vehicle_number": self.new_vehicle_no, "vehicle": self.new_vehicle_no})
            wei_updates.update({"vehicle_number": self.new_vehicle_no, "vehicle": self.new_vehicle_no})
            others_updates.update({"vehicle_no": self.new_vehicle_no})

        elif self.correction_type == "Wrong Driver Name":
            if not self.new_driver_name: frappe.throw("New Driver Name is mandatory.")
            ge_updates.update({"driver_name": self.new_driver_name})
            wei_updates.update({"driver_name": self.new_driver_name})
            others_updates.update({"driver_name": self.new_driver_name})

        elif self.correction_type == "Wrong Transporter":
            if not self.newcorrect_transporter: frappe.throw("New Transporter is mandatory.")
            gst_transporter_id = (
                frappe.db.get_value("Supplier", self.newcorrect_transporter, "gst_transporter_id")
                or frappe.db.get_value("Supplier", self.newcorrect_transporter, "gstin")
                or ""
            )
            ge_updates.update({"transporter": self.newcorrect_transporter, "transporter_name": self.newcorrect_transporter_name})
            wei_updates.update({"transporter": self.newcorrect_transporter, "transporter_name": self.newcorrect_transporter_name})
            others_updates.update({
                "transporter": self.newcorrect_transporter,
                "transporter_name": self.newcorrect_transporter_name,
                "gst_transporter_id": gst_transporter_id
            })

        elif self.correction_type == "Wrong Vehicle Type":
            if not self.new_vehicle_type: frappe.throw("New Vehicle Type is mandatory.")
            ge_updates.update({"vehicle_type": self.new_vehicle_type})
            wei_updates.update({"vehicle_type": self.new_vehicle_type})

        if ge_updates:
            frappe.db.set_value("Gate Entry", self.gate_entry, ge_updates, update_modified=False)
        
        for wname in weighments:
            if wei_updates:
                frappe.db.set_value("Weighment", wname, wei_updates, update_modified=False)
            
            dn_list = frappe.get_all("Delivery Note", filters={"custom_weighment": wname, "docstatus": ["<", 2]}, pluck="name")
            for dn in dn_list:
                if others_updates:
                    frappe.db.set_value("Delivery Note", dn, others_updates, update_modified=False)
                
                si_list = frappe.get_all("Sales Invoice Item", filters={"delivery_note": dn, "docstatus": ["<", 2]}, pluck="parent")
                for si in list(set(si_list)):
                    if others_updates:
                        frappe.db.set_value("Sales Invoice", si, others_updates, update_modified=False)

    def handle_card_rotation(self):
        """Safely unlinks old card and assigns new one."""
        old_card = frappe.db.get_value("Gate Entry", self.gate_entry, "card_number")
        if old_card:
            frappe.db.set_value("Card Details", old_card, "is_assigned", 0, update_modified=False)
        
        frappe.db.set_value("Gate Entry", self.gate_entry, "card_number", self.newcorrect_card_number, update_modified=False)
        frappe.db.set_value("Card Details", self.newcorrect_card_number, "is_assigned", 1, update_modified=False)
        
        if self.reason:
            comment_content = (
                f"{self.owner} changed the card number from {self.old_card_number} to {self.newcorrect_card_number}<br>"
                f" Reason: {self.reason}"
            )
            frappe.get_doc({
                "doctype": "Comment",
                "comment_type": "Comment",
                "reference_doctype": "Gate Entry",
                "reference_name": self.gate_entry,
                "content": comment_content,
            }).insert(ignore_permissions=True)

    def handle_item_group_correction(self):
        """Handles Wrong Item Group Selected (Outward)."""
        if not self.new_item_group:
            frappe.throw("New Item Group is required.")
        
        frappe.db.set_value("Gate Entry", self.gate_entry, "item_group", self.new_item_group, update_modified=False)
        weighments = self.get_related_weighments()
        for wname in weighments:
            frappe.db.set_value("Weighment", wname, "item_group", self.new_item_group, update_modified=False)

    def handle_sales_partner_correction(self):
        """Cascades new Sales Partner across Deal, Dispatch Orders, Sales Orders, Delivery Notes, and Sales Invoices."""
        if not self.deal:
            frappe.throw("Deal is required for Sales Partner correction.")
        if not self.new_sales_partner:
            frappe.throw("New Sales Partner is required.")
        if not frappe.db.exists("Deal", self.deal):
            frappe.throw(f"Deal '{self.deal}' does not exist.")

        new_sp = self.new_sales_partner

        frappe.db.set_value("Deal", self.deal, "sales_partner", new_sp, update_modified=False)

        dispatch_orders = frappe.get_all(
            "Dispatch Order",
            filters={"deal": self.deal, "docstatus": ["<", 2]},
            pluck="name"
        )
        for do_name in dispatch_orders:
            frappe.db.set_value("Dispatch Order", do_name, "sales_partner", new_sp, update_modified=False)

        sales_orders = frappe.get_all(
            "Sales Order",
            filters={"deal": self.deal, "docstatus": ["<", 2]},
            pluck="name"
        )
        for so_name in sales_orders:
            frappe.db.set_value("Sales Order", so_name, "sales_partner", new_sp, update_modified=False)

            dn_names = frappe.get_all(
                "Delivery Note Item",
                filters={"against_sales_order": so_name, "docstatus": ["<", 2]},
                pluck="parent",
                distinct=True
            )
            for dn_name in list(set(dn_names)):
                frappe.db.set_value("Delivery Note", dn_name, "sales_partner", new_sp, update_modified=False)

                si_names = frappe.get_all(
                    "Sales Invoice Item",
                    filters={"delivery_note": dn_name, "docstatus": ["<", 2]},
                    pluck="parent",
                    distinct=True
                )
                for si_name in list(set(si_names)):
                    frappe.db.set_value("Sales Invoice", si_name, "sales_partner", new_sp, update_modified=False)

    def reset_weighment_complete(self):
        self.validate_reset_second_weight_conditions()

        weighments = self.get_related_weighments()

        for wname in weighments:
            is_invoiced = frappe.db.exists(
                "Sales Invoice Item",
                {"custom_weighment": wname, "docstatus": ["<", 2]}
            )

            if is_invoiced:
                frappe.throw(f"Sales Invoice exists for Weighment {wname}. Please cancel it first.")

            frappe.db.sql(
                "UPDATE `tabDelivery Note` SET custom_weighment='', vehicle_no='' WHERE custom_weighment=%s",
                (wname,)
            )

            wei = frappe.get_doc("Weighment", wname)
            wei.set("delivery_notes", [])
            wei.set("delivery_note_details", [])
            wei.save(ignore_permissions=True)

            frappe.db.set_value(
                "Weighment",
                wname,
                {
                    "gross_weight": 0,
                    "net_weight": 0,
                    "total_weight": 0,
                    "minimum_permissible_weight": 0,
                    "maximum_permissible_weight": 0,
                    "is_in_progress": 1,
                    "is_completed": 0
                },
                update_modified=False
            )

        old_card = frappe.db.get_value("Gate Entry", self.gate_entry, "card_number")
        if old_card:
            frappe.db.set_value("Card Details", old_card, "is_assigned", 1, update_modified=False)


        frappe.db.set_value(
            "Gate Entry",
            self.gate_entry,
            {
                "is_in_progress": 1,
                "is_completed": 0
            },
            update_modified=False
        )
        
    def reset_weighment_manual(self):
        """Logic for Reset Second Weight (Manual). No DN detach required."""
        self.validate_reset_second_weight_conditions()

        weighments = self.get_related_weighments()

        for wname in weighments:
            frappe.db.set_value(
                "Weighment",
                wname,
                {
                    "gross_weight": 0,
                    "net_weight": 0,
                    "total_weight": 0,
                    "minimum_permissible_weight": 0,
                    "maximum_permissible_weight": 0,
                    "is_completed": 0,
                    "is_in_progress": 1
                },
                update_modified=False
            )
        
        old_card = frappe.db.get_value("Gate Entry", self.gate_entry, "card_number")
        if old_card:
            frappe.db.set_value("Card Details", old_card, "is_assigned", 1, update_modified=False)

        frappe.db.set_value(
            "Gate Entry",
            self.gate_entry,
            {
                "is_completed": 0,
                "is_in_progress": 1
            },
            update_modified=False
        )

    def rotate_delivery_note(self):
        """Rotates delivery notes on a weighment."""
        if not self.custom_delivery_note: frappe.throw("Target Delivery Note is required.")
        
        weighments = self.get_related_weighments()
        for wname in weighments:
            if frappe.db.exists("Sales Invoice Item", {"custom_weighment": wname, "docstatus": ["<", 2]}):
                frappe.throw("Sales Invoice exists. Manage it before unlinking DN.")
            
            frappe.db.sql("UPDATE `tabDelivery Note` SET custom_weighment = '', vehicle_no = '' WHERE custom_weighment = %s", (wname,))
            frappe.db.sql("DELETE FROM `tabDelivery Notes` WHERE parent = %s", (wname,))
            frappe.db.sql("DELETE FROM `tabDelivery Note Details` WHERE parent = %s", (wname,))

            wei_veh = frappe.db.get_value("Weighment", wname, "vehicle_number")
            frappe.db.set_value("Delivery Note", self.custom_delivery_note, {"custom_weighment": wname, "vehicle_no": wei_veh}, update_modified=False)
            
            wei = frappe.get_doc("Weighment", wname)
            dn = frappe.get_doc("Delivery Note", self.custom_delivery_note)
            wei.append("delivery_notes", {"delivery_note": dn.name})
            for item in dn.items:
                wei.append("delivery_note_details", {
                    "delivery_note": dn.name,
                    "item": item.item_code,
                    "item_name": item.item_name,
                    "qty": item.qty,
                    "uom": item.uom,
                    "total_weight": (item.custom_total_package_weight or 0) + (item.total_weight or 0)
                })
            wei.save(ignore_permissions=True)

    def swap_entry_flow(self):
        """Correction for Inward/Outward mistake on manual entries."""
        weighments = self.get_related_weighments()
        for wname in weighments:
            ge_doc = frappe.get_doc("Gate Entry", self.gate_entry)
            if ge_doc.is_manual_weighment != 1: continue
            
            new_type = "Outward" if ge_doc.entry_type == "Inward" else "Inward"
            ge_doc.db_set("entry_type", new_type)
            
            wei_data = {"entry_type": new_type}
            if new_type == "Inward":
                wei_data.update({"tare_weight": 0, "gross_weight": self.tare_weight or 0})
            else:
                wei_data.update({"gross_weight": 0, "tare_weight": self.gross_weight or 0})
            
            frappe.db.set_value("Weighment", wname, wei_data, update_modified=False)


    def notify_related_docs(self):
        """Standard stealth reload signal for all affected Sales documents."""
        targets = []

        if self.deal_correction and self.deal:
            targets.append(("Deal", self.deal))

            dispatch_orders = frappe.get_all(
                "Dispatch Order", filters={"deal": self.deal}, pluck="name"
            )
            for do_name in dispatch_orders:
                targets.append(("Dispatch Order", do_name))

            sales_orders = frappe.get_all(
                "Sales Order", filters={"deal": self.deal}, pluck="name"
            )
            for so_name in sales_orders:
                targets.append(("Sales Order", so_name))

                dn_names = frappe.get_all(
                    "Delivery Note Item",
                    filters={"against_sales_order": so_name},
                    pluck="parent",
                    distinct=True
                )
                for dn_name in list(set(dn_names)):
                    targets.append(("Delivery Note", dn_name))

                    si_names = frappe.get_all(
                        "Sales Invoice Item",
                        filters={"delivery_note": dn_name},
                        pluck="parent",
                        distinct=True
                    )
                    for si_name in list(set(si_names)):
                        targets.append(("Sales Invoice", si_name))

        elif self.gate_entry:
            targets.append(("Gate Entry", self.gate_entry))
            weighments = self.get_related_weighments()
            for w in weighments:
                targets.append(("Weighment", w))
                dns = frappe.get_all("Delivery Note", filters={"custom_weighment": w}, pluck="name")
                for dn in dns:
                    targets.append(("Delivery Note", dn))
                    sis = frappe.get_all("Sales Invoice Item", filters={"delivery_note": dn}, pluck="parent")
                    for si in list(set(sis)):
                        targets.append(("Sales Invoice", si))

        seen = set()
        for dt, name in targets:
            if not name or (dt, name) in seen:
                continue
            seen.add((dt, name))
            ts = frappe.db.get_value(dt, name, "modified")
            frappe.publish_realtime(
                "doc_update",
                {"modified": str(ts) + " ", "doctype": dt, "name": name},
                doctype=dt, docname=name, after_commit=True
            )


    @frappe.whitelist()
    def load_deal_data(self):
        """Fetches current Sales Partner from the selected Deal."""
        if not self.deal:
            return {}
        
        deal = frappe.db.get_value("Deal", self.deal, ["name", "sales_partner", "company", "branch"], as_dict=1)
        if not deal:
            return {}

        return {
            "wrong_sales_partner": deal.sales_partner,
            "company": deal.company,
            "plant": deal.branch
        }

    @frappe.whitelist()
    def load_gate_entry_data(self):
        """Professional data fetcher for SMS UI."""
        if not self.gate_entry: return {}
        
        ge = frappe.db.get_value(
            "Gate Entry",
            self.gate_entry,
            [
                "vehicle_number", "driver_name", "transporter", "transporter_name",
                "card_number", "vehicle_type", "is_completed", "is_in_progress",
                "item_group", "is_manual_weighment", "entry_type"
            ],
            as_dict=1
        )
        
        res = {
            "is_completed": ge.is_completed,
            "is_in_progress": ge.is_in_progress,
            "is_manual_weighment": ge.is_manual_weighment,
            "entry_type": ge.entry_type,
            "current_vehicle_no": ge.vehicle_number,
            "current_driver_name": ge.driver_name,
            "old_transporter": ge.transporter,
            "old_transporter_name": ge.transporter_name,
            "old_card_number": ge.card_number,
            "wrong_vehicle_type": ge.vehicle_type,
            "wrong_item_group": ge.item_group,
            "wrong_delivert_note": None,
        }

        wei = frappe.db.get_value("Weighment", {"gate_entry_number": self.gate_entry, "docstatus": ["<", 2]}, ["name", "weighment_date", "inward_date", "outward_date", "tare_weight", "gross_weight", "net_weight"], as_dict=1)
        if wei:
            res.update({
                "weighment_date": wei.weighment_date,
                "inward_date": wei.inward_date,
                "outward_date": wei.outward_date,
                "tare_weight": wei.tare_weight,
                "gross_weight": wei.gross_weight,
                "net_weight": wei.net_weight
            })

            old_delivery_note = frappe.db.get_value(
                "Delivery Note",
                {"custom_weighment": wei.name, "docstatus": ["<", 2]},
                "name"
            )
            if old_delivery_note:
                res["wrong_delivert_note"] = old_delivery_note
            
        return res
