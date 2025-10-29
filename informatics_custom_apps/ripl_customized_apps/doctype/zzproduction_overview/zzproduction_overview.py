# Copyright (c) 2025, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, getdate, flt, get_first_day, get_last_day


class zzProductionOverview(Document):

    def validate(self):
        self.validate_duplicate_entry()
        self.validate_previous_day_entry()

    def validate_duplicate_entry(self):
        # Ensure no duplicate entry for same plant & date
        if self.date and self.plant:
            existing = frappe.db.exists(
                self.doctype,
                {
                    "date": self.date,
                    "plant": self.plant,
                    "name": ["!=", self.name]
                }
            )
            if existing:
                frappe.throw(
                    f"Record already exists for Plant <b>{self.plant}</b> on <b>{self.date}</b>."
                )

    def validate_previous_day_entry(self):
        # Skip check if opening entry is marked
        if self.opening_entry:
            return

        prev_date = add_days(getdate(self.date), -1)

        prev_exists = frappe.db.exists(
            self.doctype,
            {
                "plant": self.plant,
                "date": prev_date,
                "docstatus": 1
            }
        )

        if not prev_exists:
            frappe.throw(
                f"Since <b>Opening Entry</b> is not checked, a submitted entry must exist "
                f"for Plant <b>{self.plant}</b> on previous date <b>{prev_date}</b>."
            )


# ---------------- Custom Button Action ----------------
@frappe.whitelist()
def calculate_values(docname):
    doc = frappe.get_doc("zzProduction Overview", docname)

    # Total Production
    pe = flt(doc.ethanol)
    ena = flt(doc.ena)
    doc.total_production = pe + ena

    # Capacity Achieved (%)
    if flt(doc.target_production):
        doc.capacity_achieved = (doc.total_production / flt(doc.target_production)) * 100
    else:
        doc.capacity_achieved = 0

    # Avg Boiler Load Per Hour
    doc.avg_bolier_load_per_hour = (
        flt(doc.steam_through_prdston) + flt(doc.steam_through_turbineton)
    ) / 24

    # Steam Cost Per BL
    if doc.total_production:
        doc.steam_cost_per_bl = (
            (flt(doc.steam_through_prdston) + flt(doc.steam_through_turbineton)) * flt(doc.steam_cost_per_ton)
        ) / doc.total_production
    else:
        doc.steam_cost_per_bl = 0

    # Total Capacity & Total Actual Production Till Date
    if not doc.opening_entry:
        month_start = get_first_day(doc.date)
        month_end = get_last_day(doc.date)
        print("--------------->month_start",month_start)
        print("--------------->month_end",month_end)
        # Sum of target capacity for the month for the same plant
        total_capacity = frappe.db.sql("""
            SELECT SUM(target_production)
            FROM `tabzzProduction Overview`
            WHERE plant = %s
              AND date BETWEEN %s AND %s
              AND name != %s
              AND docstatus=1
        """, (doc.plant, month_start, month_end, doc.name))
        print("--------------->total_capacity",total_capacity)

        # Sum of total actual production for month
        total_production1 = frappe.db.sql("""
            SELECT SUM(total_production)
            FROM `tabzzProduction Overview`
            WHERE plant = %s
              AND date BETWEEN %s AND %s
              AND name != %s
              AND docstatus=1
        """, (doc.plant, month_start, month_end, doc.name))
        print("--------------->total_production1",total_production1)

        total_capacity = flt(total_capacity[0][0]) if total_capacity else 0
        total_production = flt(total_production1[0][0]) if total_production1 else 0
        print("--------------->total_capacity",total_capacity)

        doc.total_capacity_till_date = total_capacity + flt(doc.target_production)
        doc.total_actual_production_till_date = total_production + flt(doc.total_production)
        
	#Capacity Utilization
    doc.capacity_utilization=doc.total_actual_production_till_date/doc.total_capacity_till_date
    #Loss Calculation
    doc.loss_in_month=(doc.total_capacity_till_date-doc.total_actual_production_till_date)*5
    #AVG Per day loss
    total_days_in_month = get_last_day(doc.date).day
    if total_days_in_month:
        doc.avg_per_day_loss = doc.loss_in_month / total_days_in_month
    else:
        doc.avg_per_day_loss = 0
    doc.save(ignore_permissions=True)
    frappe.msgprint("Values calculated and updated successfully.")
    return doc.as_dict()
