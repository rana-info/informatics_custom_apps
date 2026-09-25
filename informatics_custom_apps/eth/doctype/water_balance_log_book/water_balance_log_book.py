# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt


class WaterBalanceLogBook(Document):

    def validate(self):
        self.validate_water_balance()
        self.calculate_values()

    def validate_water_balance(self):
        exists = frappe.db.exists(
            "Water Balance Log Book",
            {
                "date": self.date,
                "plant": self.plant,
            }
        )

        if exists and self.get("__islocal"):
            frappe.throw(
                "Water Balance Log Book already exists for this date and plant."
            )

    def calculate_values(self):
        self.total_effluent_genration = (
            flt(self.total_condensate_genration)
            + flt(self.condensate_inlet)
            + flt(self.effluent)
        )

        self.ground_water_extraction = (
            flt(self.float_apqq)
            + flt(self.borewell_2)
        )

        self.ethanol_production = get_ethanol_production(self.plant, self.date)

        if flt(self.ethanol_production):
            self.condensate_generation_ratio = (
                flt(self.total_condensate_genration) / flt(self.ethanol_production)
            )
        else:
            self.condensate_generation_ratio = 0

        if flt(self.ethanol_production):
            self.effluent_generation_ratio = (
                flt(self.total_effluent_genration) / flt(self.ethanol_production)
            )
        else:
            self.effluent_generation_ratio = 0

        if flt(self.total_treated_water):
            self.effluent_treatment_cost = (
                flt(self.cost_of_generation) / flt(self.total_treated_water)
            )
        else:
            self.effluent_treatment_cost = 0

        if flt(self.dmro_water_generation):
            self.dm_water_treatment_cost = (
                flt(self.dm_plant_cost_of_generation) / flt(self.dmro_water_generation)
            )
        else:
            self.dm_water_treatment_cost = 0


ETHANOL_ITEM_CODES = [
    "100112",  
    "100113",  
    "100114"
]


def get_ethanol_production(plant, date):
    result = frappe.db.sql("""
        SELECT SUM(sle.actual_qty) AS qty
        FROM `tabStock Ledger Entry` sle
        INNER JOIN `tabWarehouse` wh ON wh.name = sle.warehouse
        INNER JOIN `tabStock Entry` se ON se.name = sle.voucher_no
        WHERE sle.item_code IN %(item_codes)s
          AND sle.voucher_type = 'Stock Entry'
          AND se.stock_entry_type = 'Material Receipt'
          AND se.docstatus = 1
          AND wh.custom_branch = %(plant)s
          AND sle.posting_date = %(date)s
          AND sle.actual_qty > 0
    """, {
        "item_codes": ETHANOL_ITEM_CODES,
        "plant": plant,
        "date": date,
    })
 
    qty_ltr = flt(result[0][0]) if result and result[0][0] else 0
    return qty_ltr / 1000