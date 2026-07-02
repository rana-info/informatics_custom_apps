import frappe
from frappe.model.document import Document

class SalesManagementTool(Document):
    def before_save(self):
        """Run correction validations before save for immediate user feedback."""
        self.validate_no_same_value()

        if self.deal_correction and self.delivery_note_correction:
            frappe.throw(
                "Deal Correction and Delivery Note Correction cannot be enabled at the same time. "
                "Please uncheck one before proceeding."
            )

        if self.deal_correction:
            allowed_deal_corrections = {"Wrong Sales Partner", "Wrong Segment(Deal)"}
            if self.correction_type and self.correction_type not in allowed_deal_corrections:
                frappe.throw(
                    f"'{self.correction_type}' cannot be tackled in Deal Correction mode. "
                    f"Only {', '.join(allowed_deal_corrections)} are allowed when Deal Correction is enabled."
                )
            return

        if self.delivery_note_correction:
            if not self.delivery_note:
                frappe.throw("Delivery Note is required when Delivery Note Correction is enabled.")
            if self.correction_type and self.correction_type != "Unlink Weighment":
                frappe.throw(
                    f"'{self.correction_type}' is not allowed in Delivery Note Correction mode. "
                    f"Only 'Unlink Weighment' is allowed."
                )
            if self.delivery_note:
                dn = frappe.db.get_value(
                    "Delivery Note", self.delivery_note, ["status", "is_return"], as_dict=True
                )
                if dn:
                    allowed_statuses = {"Draft", "To Bill"}
                    if dn.status not in allowed_statuses:
                        frappe.throw(
                            f"Delivery Note <b>{self.delivery_note}</b> is in "
                            f"<b>{dn.status}</b> status. Only Draft or To Bill are expected. "
                            f"Unlinking the weighment may have unintended consequences.",
                            title="Unexpected Delivery Note Status"
                        )
                    if dn.is_return:
                        frappe.throw(
                            f"Warning: Delivery Note <b>{self.delivery_note}</b> is a <b>Return</b> "
                            f"entry (Credit Note). Unlinking the weighment from a return DN "
                            f"may have unintended consequences.",
                            title="Return Delivery Note Selected"
                        )
            return



        self.validate_in_progress_only_corrections()
        self.validate_reset_second_weight_conditions()

        validators = {
            "Wrong Transporter": self.validate_transporter,
            "Wrong Card Number": self.validate_card_number,
            "Wrong Item Group": self.validate_item_group,
            "Wrong Delivery Note": self.validate_wrong_delivery_note,
            "Wrong Segment": self.validate_wrong_segment,
            "Wrong Weight(Sale)": self.validate_wrong_weight_sale,
        }
        validator = validators.get(self.correction_type)
        if validator:
            validator()

        api_response_warning_types = {
            "Reset Second Weight (Not Manual)",
            "Reset Second Weight (Manual)",
            "Wrong Item Group",
            "Wrong Delivery Note",
            "Inward/Outward Wrong Entry (Manual)",
            "Wrong Segment",
            "Change First Weight(Tare)",
        }

        if self.correction_type in api_response_warning_types:

            weighment_name = frappe.db.get_value(
                "Weighment",
                {
                    "gate_entry_number": self.gate_entry,
                    "docstatus": ["<", 2]
                },
                "name"
            )

            if weighment_name:
                api_data_updated = frappe.db.get_value(
                    "Weighment",
                    weighment_name,
                    "api_data_updated"
                )

                if api_data_updated == 1:
                    frappe.throw(
                        f"Warning: API Response is already sent for this record. ",
                        title="API Response Already Sent",
                    )

    def validate(self):
        """Initial data validation and prerequisite checks."""
        if self.gate_entry:
            ge_data = frappe.db.get_all("Gate Entry", filters={"name": self.gate_entry}, fields=["docstatus", "entry_type"])
            if ge_data:
                if ge_data[0].docstatus == 2:
                    frappe.throw("Target Gate Entry is cancelled. Correction not possible.")
                if ge_data[0].entry_type != "Outward":
                    if self.correction_type != "Inward/Outward Wrong Entry (Manual)":
                        frappe.throw("Sales Management System handles Outward entries. Use PMS for Inward entries.")

    def validate_no_same_value(self):
        """Ensure new correction value is different from old value for key correction types."""
        field_pairs = {
            "Wrong Vehicle Number": ("current_vehicle_no", "new_vehicle_no", "Vehicle Number"),
            "Wrong Driver Name": ("current_driver_name", "new_driver_name", "Driver Name"),
            "Wrong Card Number": ("old_card_number", "newcorrect_card_number", "Card Number"),
            "Wrong Transporter": ("old_transporter", "newcorrect_transporter", "Transporter"),
            "Wrong Vehicle Type": ("wrong_vehicle_type", "new_vehicle_type", "Vehicle Type"),
            "Wrong Sales Partner": ("wrong_sales_partner", "new_sales_partner", "Sales Partner"),
            "Wrong Segment": ("wrong_segment", "new_segment", "Segment"),
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
        """Validate Transporter change only for non-company owned vehicles."""
        if not self.gate_entry:
            return
        gate_entry_doc = frappe.get_doc("Gate Entry", self.gate_entry)
        if gate_entry_doc.get("vehicle_owner") == "Company Owned":
            frappe.throw("Transporter cannot be changed for Company Owned vehicles.")

    def validate_card_number(self):
        """Validate New Card Number for Wrong Card Number correction: must be unassigned, same branch, and not recently freed."""
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

    def validate_wrong_delivery_note(self):
        """Wrong Delivery Note correction is only allowed when Gate Entry is completed, not while in progress."""
        if not self.gate_entry:
            return

        ge_status = frappe.db.get_value(
            "Gate Entry",
            self.gate_entry,
            ["is_completed", "is_in_progress"],
            as_dict=1
        )

        if not ge_status:
            frappe.throw("Gate Entry not found.")

    def validate_wrong_segment(self):
        """Wrong Segment correction requires Gate Entry to be in-progress and no DNs on any linked Weighment."""
        if not self.gate_entry:
            return

        ge_in_progress = frappe.db.get_value("Gate Entry", self.gate_entry, "is_in_progress")
        if not ge_in_progress:
            frappe.throw(
                f"Gate Entry <b>{self.gate_entry}</b> is not In-Progress. "
                f"Wrong Segment correction is only allowed when the Gate Entry is in progress."
            )

        for wname in self.get_related_weighments():
            linked_dns = frappe.get_all(
                "Delivery Note",
                filters={"custom_weighment": wname, "docstatus": ["<", 2]},
                pluck="name",
                limit=1
            )
            if linked_dns:
                frappe.throw(
                    f"Cannot change Segment because Weighment is already linked to Delivery Note(s) "
                )

    def validate_in_progress_only_corrections(self):
        """Enforce in-progress gate-entry status for selected correction types."""
        in_progress_only_corrections = {
            "Wrong Item Group",
            "Inward/Outward Wrong Entry (Manual)",
            "Change First Weight(Tare)",
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
                "Reset Second Weight is allowed only when Gate Entry is Completed"
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
            "Change First Weight(Tare)": self.handle_change_first_weight,
            "Wrong Segment": self.handle_wrong_segment,
            "Unlink Weighment": self.handle_unlink_weighment,
            "Wrong Segment(Deal)": self.handle_wrong_segment_deal,
            "Wrong Weight(Sale)": self.handle_wrong_weight_sale,
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
        """Cascades new Sales Partner across Deal, Dispatch Orders, Sales Orders,
        Delivery Notes, and Sales Invoices.

        Also updates:
            - rate_of_commission_per_uom  in Deal, SO, DN, SI
            (fetched from Sales Partner.custom_rate_of_commission_per_uom)
            - total_commission             in SO, DN, SI
            (= rate_of_commission_per_uom * total_net_weight / 100)
        """
        if not self.deal:
            frappe.throw("Deal is required for Sales Partner correction.")
        if not self.new_sales_partner:
            frappe.throw("New Sales Partner is required.")
        if not frappe.db.exists("Deal", self.deal):
            frappe.throw(f"Deal '{self.deal}' does not exist.")

        new_sp = self.new_sales_partner

        # Fetch the commission rate from the new Sales Partner master
        new_rate = frappe.db.get_value(
            "Sales Partner", new_sp, "custom_rate_of_commission_per_uom"
        ) or 0

        frappe.db.set_value(
            "Deal", self.deal,
            {"sales_partner": new_sp, "rate_of_commission_per_uom": new_rate},
            update_modified=False
        )

        # --- Dispatch Orders: sales_partner + rate + total_commission ---
        dispatch_orders = frappe.get_all(
            "Dispatch Order",
            filters={"deal": self.deal, "docstatus": ["<", 2]},
            pluck="name"
        )
        for do_name in dispatch_orders:
            do_net_weight = frappe.db.get_value("Dispatch Order", do_name, "total_net_weight") or 0
            frappe.db.set_value(
                "Dispatch Order", do_name,
                {
                    "sales_partner": new_sp,
                    "rate_of_commission_per_uom": new_rate,
                    "total_commission": new_rate * do_net_weight / 100,
                },
                update_modified=False
            )

        # --- Sales Orders -> Delivery Notes -> Sales Invoices ---
        sales_orders = frappe.get_all(
            "Sales Order",
            filters={"deal": self.deal, "docstatus": ["<", 2]},
            pluck="name"
        )
        for so_name in sales_orders:
            so_net_weight = frappe.db.get_value("Sales Order", so_name, "total_net_weight") or 0
            frappe.db.set_value(
                "Sales Order", so_name,
                {
                    "sales_partner": new_sp,
                    "rate_of_commission_per_uom": new_rate,
                    "total_commission": new_rate * so_net_weight / 100,
                },
                update_modified=False
            )

            dn_names = frappe.get_all(
                "Delivery Note Item",
                filters={"against_sales_order": so_name, "docstatus": ["<", 2]},
                pluck="parent",
                distinct=True
            )
            for dn_name in list(set(dn_names)):
                dn_net_weight = frappe.db.get_value("Delivery Note", dn_name, "total_net_weight") or 0
                frappe.db.set_value(
                    "Delivery Note", dn_name,
                    {
                        "sales_partner": new_sp,
                        "rate_of_commission_per_uom": new_rate,
                        "total_commission": new_rate * dn_net_weight / 100,
                    },
                    update_modified=False
                )

                si_names = frappe.get_all(
                    "Sales Invoice Item",
                    filters={"delivery_note": dn_name, "docstatus": ["<", 2]},
                    pluck="parent",
                    distinct=True
                )
                for si_name in list(set(si_names)):
                    si_net_weight = frappe.db.get_value("Sales Invoice", si_name, "total_net_weight") or 0
                    frappe.db.set_value(
                        "Sales Invoice", si_name,
                        {
                            "sales_partner": new_sp,
                            "rate_of_commission_per_uom": new_rate,
                            "total_commission": new_rate * si_net_weight / 100,
                        },
                        update_modified=False
                    )


    def _reset_weighment_weights(self, weighments):
        """Zero out weight fields and mark all related weighments as in-progress."""
        WEIGHT_RESET = {
            "gross_weight": 0, "net_weight": 0, "total_weight": 0,
            "minimum_permissible_weight": 0, "maximum_permissible_weight": 0,
            "is_in_progress": 1, "is_completed": 0,
        }
        for wname in weighments:
            frappe.db.set_value("Weighment", wname, WEIGHT_RESET, update_modified=False)

        old_card = frappe.db.get_value("Gate Entry", self.gate_entry, "card_number")
        if old_card:
            frappe.db.set_value("Card Details", old_card, "is_assigned", 1, update_modified=False)

        frappe.db.set_value(
            "Gate Entry", self.gate_entry,
            {"is_in_progress": 1, "is_completed": 0},
            update_modified=False
        )

    def reset_weighment_complete(self):
        """Reset second weight for non-manual weighments: detaches DNs then resets weights."""
        self.validate_reset_second_weight_conditions()
        weighments = self.get_related_weighments()

        for wname in weighments:
            if frappe.db.exists("Sales Invoice Item", {"custom_weighment": wname, "docstatus": ["<", 2]}):
                frappe.throw(f"Sales Invoice exists for Weighment {wname}. Please cancel it first.")

            frappe.db.sql(
                "UPDATE `tabDelivery Note` SET custom_weighment='', vehicle_no='' WHERE custom_weighment=%s",
                (wname,)
            )
            wei = frappe.get_doc("Weighment", wname)
            wei.set("delivery_notes", [])
            wei.set("delivery_note_details", [])
            wei.save(ignore_permissions=True)

        self._reset_weighment_weights(weighments)

    def reset_weighment_manual(self):
        """Reset second weight for manual weighments: no DN detach required."""
        self.validate_reset_second_weight_conditions()
        self._reset_weighment_weights(self.get_related_weighments())

    def handle_change_first_weight(self):
        """Update only the tare (first) weight on the Weighment.

        Only permitted when Gate Entry is In Progress (is_in_progress=1, is_completed=0).
        Net weight is NOT recalculated here because the second weight (gross) may not
        have been captured yet.
        """
        if not self.tare_weight and self.tare_weight != 0:
            frappe.throw("New Tare Weight is required.")

        for wname in self.get_related_weighments():
            frappe.db.set_value(
                "Weighment", wname,
                {"tare_weight": self.tare_weight},
                update_modified=False
            )

    def validate_wrong_weight_sale(self):
        """Validate Wrong Weight(Sale) correction:
        - Gate Entry must exist
        - Weighment must have a linked Delivery Note (warning if not)
        - At least one of gross_weight or tare_weight must be provided
        """
        if not self.gate_entry:
            return

        weighments = self.get_related_weighments()
        if not weighments:
            frappe.throw("No active Weighment found for this Gate Entry.")

        # Check that at least one weighment has a linked Delivery Note
        has_dn = False
        for wname in weighments:
            dn_exists = frappe.db.exists(
                "Delivery Note",
                {"custom_weighment": wname, "docstatus": ["<", 2]}
            )
            if dn_exists:
                has_dn = True
                break

        if not has_dn:
            frappe.throw(
                "No Delivery Note exists for this Weighment. "
                "Wrong Weight(Sale) correction requires a Delivery Note to be linked.",
                title="Delivery Note Required"
            )

        # At least one weight must be entered
        has_gross = self.gross_weight and self.gross_weight > 0
        has_tare = self.tare_weight and self.tare_weight > 0
        if not has_gross and not has_tare:
            frappe.throw("At least one of Gross Weight or Tare Weight must be provided.")

        # Block if gate entry is already completed
        ge_status = frappe.db.get_value(
            "Gate Entry", self.gate_entry,
            ["is_completed", "is_in_progress"], as_dict=True
        )
        if ge_status and ge_status.is_completed:
            frappe.throw(
                f"Gate Entry <b>{self.gate_entry}</b> is already Completed. "
                f"Wrong Weight(Sale) correction is not allowed on completed entries.",
                title="Gate Entry Already Completed"
            )

    def handle_wrong_weight_sale(self):
        """Handles Wrong Weight(Sale) correction.

        Works for is_in_progress Gate Entries.
        """
        if not self.gate_entry:
            frappe.throw("Gate Entry is required for Wrong Weight(Sale) correction.")

        weighments = self.get_related_weighments()
        if not weighments:
            frappe.throw("No active Weighment found for this Gate Entry.")

        has_gross = self.gross_weight and self.gross_weight > 0
        has_tare = self.tare_weight and self.tare_weight > 0
        both_provided = has_gross and has_tare

        for wname in weighments:
            wei_updates = {}

            if both_provided:
                # Both weights provided: update all 3, mark as completed
                net = self.gross_weight - self.tare_weight
                wei_updates = {
                    "gross_weight": self.gross_weight,
                    "tare_weight": self.tare_weight,
                    "net_weight": net,
                    "is_completed": 1,
                    "is_in_progress": 0,
                }
            elif has_gross:
                # Only gross weight: update gross, zero net, keep in-progress
                wei_updates = {
                    "gross_weight": self.gross_weight,
                    "net_weight": 0,
                    "is_in_progress": 1,
                    "is_completed": 0,
                }
            elif has_tare:
                # Only tare weight: update tare, zero net, keep in-progress
                wei_updates = {
                    "tare_weight": self.tare_weight,
                    "net_weight": 0,
                    "is_in_progress": 1,
                    "is_completed": 0,
                }

            if wei_updates:
                frappe.db.set_value("Weighment", wname, wei_updates, update_modified=False)

            # Set outward_date via raw SQL to guarantee modified/modified_by stay untouched
            if both_provided:
                frappe.db.sql(
                    """UPDATE `tabWeighment` SET outward_date = %s
                       WHERE name = %s""",
                    (frappe.utils.now(), wname)
                )

        # Update Gate Entry status accordingly
        if both_provided:
            frappe.db.set_value(
                "Gate Entry", self.gate_entry,
                {"is_completed": 1, "is_in_progress": 0},
                update_modified=False
            )
            # Free the card since the weighment cycle is now complete
            card = frappe.db.get_value("Gate Entry", self.gate_entry, "card_number")
            if card:
                frappe.db.set_value("Card Details", card, "is_assigned", 0, update_modified=False)
        else:
            frappe.db.set_value(
                "Gate Entry", self.gate_entry,
                {"is_in_progress": 1, "is_completed": 0},
                update_modified=False
            )

    def handle_wrong_segment(self):
        """Update Segment on Gate Entry and linked Weighments only.

        Pre-conditions (strictly enforced):
            1. The Gate Entry must be in-progress (is_in_progress = 1).
            2. No Delivery Note(s) must exist for any Weighment linked to the Gate Entry.
        """
        if not self.new_segment:
            frappe.throw("New Segment is required.")

        ge_in_progress = frappe.db.get_value("Gate Entry", self.gate_entry, "is_in_progress")
        if not ge_in_progress:
            frappe.throw(
                f"Gate Entry <b>{self.gate_entry}</b> is not In-Progress. "
                f"Wrong Segment correction is only allowed when the Gate Entry is in progress."
            )

        weighments = self.get_related_weighments()
        for wname in weighments:
            linked_dns = frappe.get_all(
                "Delivery Note",
                filters={"custom_weighment": wname, "docstatus": ["<", 2]},
                pluck="name",
                limit=1
            )
            if linked_dns:
                frappe.throw(
                    f"Weighment <b>{wname}</b> already has Delivery Note(s) linked to it "
                    f"(<b>{linked_dns[0]}</b>). Remove all Delivery Notes before "
                    f"correcting the Segment."
                )

        new_seg = self.new_segment

        frappe.db.set_value("Gate Entry", self.gate_entry, "segment", new_seg, update_modified=False)

        for wname in weighments:
            frappe.db.set_value("Weighment", wname, "segment", new_seg, update_modified=False)


    def handle_wrong_segment_deal(self):
        """Cascades new Cost Center and Segment across Deal, Dispatch Orders,
        Sales Orders (+ Items), Delivery Notes (+ Items), Sales Invoices (+ Items),
        GL Entries, and Stock Ledger Entries.

        The new cost_center and segment values are read from the selected
        Cost Center document. Deal only has a cost_center field (no segment).
        """
        if not self.deal:
            frappe.throw("Deal is required for Wrong Segment(Deal) correction.")
        if not self.new_cost_center:
            frappe.throw("New Cost Center is required.")
        if not frappe.db.exists("Deal", self.deal):
            frappe.throw(f"Deal '{self.deal}' does not exist.")
        if not frappe.db.exists("Cost Center", self.new_cost_center):
            frappe.throw(f"Cost Center '{self.new_cost_center}' does not exist.")

        new_cc = self.new_cost_center
        # Cost Center document has a 'segment' field (custom or standard) that holds
        # the segment name associated with that cost center.
        # The cost center 'name' field is the full path like "9999 - Distillery - BBPL".
        new_segment = frappe.db.get_value("Cost Center", new_cc, "segment") or ""

        # --- Deal: cost_center only (Deal has no segment field) ---
        frappe.db.set_value(
            "Deal", self.deal,
            {"cost_center": new_cc},
            update_modified=False
        )

        # --- Dispatch Orders: cost_center only ---
        dispatch_orders = frappe.get_all(
            "Dispatch Order",
            filters={"deal": self.deal, "docstatus": ["<", 2]},
            pluck="name"
        )
        for do_name in dispatch_orders:
            frappe.db.set_value(
                "Dispatch Order", do_name,
                {"cost_center": new_cc},
                update_modified=False
            )

        # --- Sales Orders -> Delivery Notes -> Sales Invoices ---
        sales_orders = frappe.get_all(
            "Sales Order",
            filters={"deal": self.deal, "docstatus": ["<", 2]},
            pluck="name"
        )
        for so_name in sales_orders:
            # Sales Order header: cost_center + segment
            frappe.db.set_value(
                "Sales Order", so_name,
                {"cost_center": new_cc, "segment": new_segment},
                update_modified=False
            )
            # Sales Order Items
            so_items = frappe.get_all(
                "Sales Order Item",
                filters={"parent": so_name},
                pluck="name"
            )
            for soi_name in so_items:
                frappe.db.set_value(
                    "Sales Order Item", soi_name,
                    {"cost_center": new_cc, "segment": new_segment},
                    update_modified=False
                )

            # Delivery Notes linked via SO
            dn_names = frappe.get_all(
                "Delivery Note Item",
                filters={"against_sales_order": so_name, "docstatus": ["<", 2]},
                pluck="parent",
                distinct=True
            )
            for dn_name in list(set(dn_names)):
                # DN header: cost_center + segment
                frappe.db.set_value(
                    "Delivery Note", dn_name,
                    {"cost_center": new_cc, "segment": new_segment},
                    update_modified=False
                )
                # DN Items
                dni_names = frappe.get_all(
                    "Delivery Note Item",
                    filters={"parent": dn_name},
                    pluck="name"
                )
                for dni_name in dni_names:
                    frappe.db.set_value(
                        "Delivery Note Item", dni_name,
                        {"cost_center": new_cc, "segment": new_segment},
                        update_modified=False
                    )

                # GL Entries from DN: cost_center + segment
                dn_gl_entries = frappe.get_all(
                    "GL Entry",
                    filters={"voucher_no": dn_name, "is_cancelled": 0},
                    pluck="name"
                )
                for gl_name in dn_gl_entries:
                    frappe.db.set_value(
                        "GL Entry", gl_name,
                        {"cost_center": new_cc, "segment": new_segment},
                        update_modified=False
                    )

                # Stock Ledger Entries from DN: segment only
                dn_sle_entries = frappe.get_all(
                    "Stock Ledger Entry",
                    filters={"voucher_no": dn_name, "is_cancelled": 0},
                    pluck="name"
                )
                for sle_name in dn_sle_entries:
                    frappe.db.set_value(
                        "Stock Ledger Entry", sle_name,
                        {"segment": new_segment},
                        update_modified=False
                    )

                # Sales Invoices linked via DN
                si_names = frappe.get_all(
                    "Sales Invoice Item",
                    filters={"delivery_note": dn_name, "docstatus": ["<", 2]},
                    pluck="parent",
                    distinct=True
                )
                for si_name in list(set(si_names)):
                    # SI header: cost_center + segment
                    frappe.db.set_value(
                        "Sales Invoice", si_name,
                        {"cost_center": new_cc, "segment": new_segment},
                        update_modified=False
                    )
                    # SI Items
                    sii_names = frappe.get_all(
                        "Sales Invoice Item",
                        filters={"parent": si_name},
                        pluck="name"
                    )
                    for sii_name in sii_names:
                        frappe.db.set_value(
                            "Sales Invoice Item", sii_name,
                            {"cost_center": new_cc, "segment": new_segment},
                            update_modified=False
                        )

                    # GL Entries from SI: cost_center + segment
                    si_gl_entries = frappe.get_all(
                        "GL Entry",
                        filters={"voucher_no": si_name, "is_cancelled": 0},
                        pluck="name"
                    )
                    for gl_name in si_gl_entries:
                        frappe.db.set_value(
                            "GL Entry", gl_name,
                            {"cost_center": new_cc, "segment": new_segment},
                            update_modified=False
                        )

    def handle_unlink_weighment(self):
        """Unlinks the selected Delivery Note from its Weighment by clearing custom_weighment."""
        if not self.delivery_note:
            frappe.throw("Delivery Note is required for Unlink Weighment correction.")

        current_weighment = frappe.db.get_value("Delivery Note", self.delivery_note, "custom_weighment")
        if not current_weighment:
            frappe.throw(
                f"Delivery Note {self.delivery_note} is not linked to any Weighment."
            )

        frappe.db.set_value(
            "Delivery Note",
            self.delivery_note,
            {"custom_weighment": "", "vehicle_no": ""},
            update_modified=False
        )

        # Preserve the DN reference in a Data field (not a Link) so it stays visible
        # on the approved SMT without blocking future Delivery Note cancellation.
        self.db_set("corrected_delivery_note", self.delivery_note, update_modified=False)
        self.db_set("delivery_note", "", update_modified=False)

    def rotate_delivery_note(self):

        """Swap one or more old Delivery Notes for new ones on their linked Weighments.

        The mapping is passed from the JS dynamic table via frappe.form_dict
        (as a plain list of {old_delivery_note, new_delivery_note} dicts) because
        Frappe's Document hydration drops list entries that lack a registered doctype.
        """
        rotation_entries = []

        for row in self.delivery_note_entries:

            if row.old_delivery_note and row.new_delivery_note:

                rotation_entries.append(
                    frappe._dict({
                        "old_delivery_note": row.old_delivery_note,
                        "new_delivery_note": row.new_delivery_note
                    })
                )

        if not rotation_entries:
            frappe.throw("Please select at least one New Delivery Note.")

        for e in rotation_entries:
            if e.old_delivery_note == e.new_delivery_note:
                frappe.throw(f"Old and New Delivery Note cannot be the same ({e.old_delivery_note}).")
        new_dns = [e.new_delivery_note for e in rotation_entries]
        if len(new_dns) != len(set(new_dns)):
            frappe.throw("Duplicate New Delivery Notes are not allowed.")

        for wname in self.get_related_weighments():
            if frappe.db.exists("Sales Invoice Item", {"custom_weighment": wname, "docstatus": ["<", 2]}):
                frappe.throw(f"Sales Invoice exists for Weighment {wname}. Please cancel it first.")

        for e in rotation_entries:
            old_dn, new_dn = e.old_delivery_note, e.new_delivery_note

            wname = frappe.db.get_value("Delivery Note", old_dn, "custom_weighment")
            if not wname:
                frappe.throw(f"Delivery Note {old_dn} is not linked to any Weighment.")

            if frappe.db.get_value("Delivery Note", new_dn, "custom_weighment"):
                frappe.throw(f"New Delivery Note {new_dn} is already linked to another Weighment.")

            frappe.db.set_value("Delivery Note", old_dn, {"custom_weighment": "", "vehicle_no": ""}, update_modified=False)
            frappe.db.sql("DELETE FROM `tabDelivery Notes` WHERE parent=%s AND delivery_note=%s", (wname, old_dn))
            frappe.db.sql("DELETE FROM `tabDelivery Note Details` WHERE parent=%s AND delivery_note=%s", (wname, old_dn))

            vehicle_no = frappe.db.get_value("Weighment", wname, "vehicle_number")
            frappe.db.set_value("Delivery Note", new_dn, {"custom_weighment": wname, "vehicle_no": vehicle_no}, update_modified=False)

            wei = frappe.get_doc("Weighment", wname)
            dn_doc = frappe.get_doc("Delivery Note", new_dn)
            wei.append("delivery_notes", {"delivery_note": dn_doc.name})
            for item in dn_doc.items:
                wei.append("delivery_note_details", {
                    "delivery_note": dn_doc.name,
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

        elif self.delivery_note_correction and self.delivery_note:
            targets.append(("Delivery Note", self.delivery_note))

        elif self.gate_entry:
            targets.append(("Gate Entry", self.gate_entry))
            weighments = self.get_related_weighments()
            for w in weighments:
                if self.correction_type != "Wrong Weight(Sale)":
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
        if not self.deal:
            return {}
        
        deal = frappe.db.get_value(
            "Deal", self.deal,
            ["name", "sales_partner", "company", "branch", "cost_center"],
            as_dict=1
        )
        if not deal:
            return {}

        return {
            "wrong_sales_partner": deal.sales_partner,
            "company": deal.company,
            "plant": deal.branch,
            "cost_center": deal.cost_center,
        }

    @frappe.whitelist()
    def load_gate_entry_data(self):
        """Fetches all relevant gate entry and weighment data for the SMS UI."""
        if not self.gate_entry: return {}

        ge = frappe.db.get_value(
            "Gate Entry",
            self.gate_entry,
            [
                "vehicle_number", "driver_name", "transporter", "transporter_name",
                "card_number", "vehicle_type", "is_completed", "is_in_progress",
                "item_group", "is_manual_weighment", "entry_type", "segment"
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
            "wrong_segment": ge.segment,
            "wrong_delivert_note": None,
            "linked_delivery_notes": [],
        }

        wei = frappe.db.get_value(
            "Weighment",
            {"gate_entry_number": self.gate_entry, "docstatus": ["<", 2]},
            ["name", "weighment_date", "inward_date", "outward_date", "tare_weight", "gross_weight", "net_weight"],
            as_dict=1
        )
        if wei:
            res.update({
                "weighment_date": wei.weighment_date,
                "inward_date": wei.inward_date,
                "outward_date": wei.outward_date,
                "tare_weight": wei.tare_weight,
                "gross_weight": wei.gross_weight,
                "net_weight": wei.net_weight
            })

            wei_doc = frappe.get_doc("Weighment", wei.name)
            linked_dns = [row.delivery_note for row in wei_doc.delivery_notes if row.delivery_note]
            res["linked_delivery_notes"] = linked_dns
            if linked_dns:
                res["wrong_delivert_note"] = linked_dns[0]

        return res
