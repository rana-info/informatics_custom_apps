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
                    "name": ["!=", self.name],
                    "docstatus":1
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
    if doc.total_production and doc.plant not in ["RSL Louhka","ETH Louhka"]:
        doc.steam_cost_per_bl = (
            (flt(doc.steam_through_prdston) + flt(doc.steam_through_turbineton)) * flt(doc.steam_cost_per_ton)
        ) / doc.total_production
    else:
        doc.steam_cost_per_bl = 0

    # Total Capacity & Total Actual Production Till Date
    # Find the latest previous entry for same plant (confirmed, submitted)
    if not doc.opening_entry:
        prev_total = frappe.db.sql("""
            SELECT total_capacity_till_date, total_actual_production_till_date
            FROM `tabzzProduction Overview`
            WHERE plant = %s
            AND date < %s
            AND docstatus = 1
            ORDER BY date DESC
            LIMIT 1
        """, (doc.plant, doc.date))

        if prev_total:
            prev_capacity, prev_actual = prev_total[0]
            doc.total_capacity_till_date = flt(prev_capacity) + flt(doc.target_production)
            doc.total_actual_production_till_date = flt(prev_actual) + flt(doc.total_production)
        else:
            # In case user forgot to create opening entry, fallback gracefully
            doc.total_capacity_till_date = flt(doc.target_production)
            doc.total_actual_production_till_date = flt(doc.total_production)

        
	#Capacity Utilization
    if doc.total_capacity_till_date and doc.total_actual_production_till_date:
        doc.capacity_utilization=(doc.total_actual_production_till_date/doc.total_capacity_till_date)*100
    #Loss Calculation
    doc.loss_in_month=(doc.total_capacity_till_date-doc.total_actual_production_till_date)*5
    #AVG Per day loss
    current_day_of_month = doc.date.day
    print("---------------------------->current_day_of_month", current_day_of_month)

    if current_day_of_month:
        doc.avg_per_day_loss = flt(doc.loss_in_month) / current_day_of_month
    else:
        doc.avg_per_day_loss = 0

    doc.save(ignore_permissions=True)
   
    return doc.as_dict()
