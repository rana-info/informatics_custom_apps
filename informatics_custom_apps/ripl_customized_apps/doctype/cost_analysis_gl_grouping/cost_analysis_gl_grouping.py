# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class CostAnalysisGLGrouping(Document):
	pass



@frappe.whitelist()
def get_all_account_numbers():
    accounts = frappe.db.sql("""
        SELECT DISTINCT account_number
        FROM `tabAccount`
        WHERE account_number IS NOT NULL AND account_number != ''
        ORDER BY account_number
    """, as_dict=True)
    return [a.account_number for a in accounts]