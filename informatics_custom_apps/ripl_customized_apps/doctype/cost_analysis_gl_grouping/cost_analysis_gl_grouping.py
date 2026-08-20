# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe import _
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


@frappe.whitelist()
def create_per_bl_budget(from_date, to_date, plants):
	"""
	Create one 'Per BL Budget' record per selected Plant.
	Each record's child table (per_bl_budget_amount) is populated with the
	GL Accounts belonging to that Plant's Company, matched against the
	account numbers listed in Cost Analysis GL Grouping -> Cost Analysis GL.
	"""
	if isinstance(plants, str):
		plants = frappe.parse_json(plants)
 
	if not plants:
		frappe.throw(_("Please select at least one Plant"))
 
	if not from_date or not to_date:
		frappe.throw(_("Please select both Applicable From and Applicable Till dates"))
 
	if from_date > to_date:
		frappe.throw(_("Applicable From cannot be after Applicable Till"))
 
	# Master list of account numbers from the single doctype
	gl_grouping = frappe.get_single("Cost Analysis GL Grouping")
	account_numbers = list({
		row.account_number for row in gl_grouping.cost_analysis_gl
		if row.account_number
	})
 
	if not account_numbers:
		frappe.throw(
			_("No Account Numbers found in Cost Analysis GL Grouping. "
			  "Please add entries in the Cost Analysis GL table first.")
		)
 
	created = []
	skipped = []
 
	for plant in plants:
		if not frappe.db.exists("Branch", plant):
			skipped.append(_("{0} - Plant not found").format(plant))
			continue
 
		# Avoid creating duplicate records for the same Plant + date range
		existing = frappe.db.exists(
			"Per BL Budget",
			{"plant": plant, "from": from_date, "to": to_date},
		)
		if existing:
			skipped.append(_("{0} - already exists ({1})").format(plant, existing))
			continue
 
		# NOTE: assumes a 'company' field exists on Branch (custom field).
		# Update the fieldname below if it's named differently.
		company = frappe.db.get_value("Branch", plant, "company")
		if not company:
			skipped.append(_("{0} - no Company linked to this Plant").format(plant))
			continue
 
		accounts = frappe.get_all(
			"Account",
			filters={
				"company": company,
				"account_number": ["in", account_numbers],
			},
			fields=["name", "account_number"],
		)
 
		if not accounts:
			skipped.append(
				_("{0} - no matching GL Accounts found for Company {1}").format(plant, company)
			)
			continue
 
		doc = frappe.new_doc("Per BL Budget")
		doc.plant = plant
		doc.set("from", from_date)  # 'from' is a reserved word, use .set()
		doc.set("to", to_date)
 
		for acc in accounts:
			doc.append(
				"per_bl_budget_amount",
				{
					"gl_account": acc.name,
					"account_number": acc.account_number,
					"per_bl_budget": 0,
				},
			)
 
		doc.insert()
		created.append({"name": doc.name, "plant": plant})
 
	return {"created": created, "skipped": skipped}



@frappe.whitelist()
def get_all_plants():
    """Return all Branch (Plant) records except Head Office branches."""
    return frappe.get_all(
        "Branch",
        filters={
            "name": ["not like", "%Head Office%"]
        },
        fields=["name"],
        order_by="name asc",
        limit_page_length=0,
    )