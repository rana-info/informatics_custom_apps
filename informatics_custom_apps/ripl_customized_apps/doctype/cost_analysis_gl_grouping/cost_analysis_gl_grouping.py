# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class CostAnalysisGLGrouping(Document):
	def validate(self):
		self.validate_total_row_setup()

	def validate_total_row_setup(self):
		section_names = {row.section_name for row in self.section_name if row.section_name}

		total_row_labels = []
		cop_base_count = 0
		for row in self.total_row:
			if not row.row_label:
				continue
			if row.row_label in total_row_labels:
				frappe.throw(_("Total Row: duplicate Row Label {0}").format(frappe.bold(row.row_label)))
			total_row_labels.append(row.row_label)
			if row.is_cop_base:
				cop_base_count += 1

		if cop_base_count > 1:
			frappe.throw(_("Only one Total Row can be marked \"Use as Cost of Production Base\""))

		total_row_label_set = set(total_row_labels)

		# component_graph: total_row_label -> [other total_row_labels it depends on]
		component_graph = {label: [] for label in total_row_labels}

		for row in self.total_row_components:
			if not row.row_label and not row.component_name:
				continue

			if row.row_label not in total_row_label_set:
				frappe.throw(
					_("Total Row Components, row {0}: {1} does not match any Row Label in the Total Row table").format(
						row.idx, frappe.bold(row.row_label)
					)
				)

			if row.component_type == "Section":
				if row.component_name not in section_names:
					frappe.throw(
						_("Total Row Components, row {0}: {1} does not match any Section Name").format(
							row.idx, frappe.bold(row.component_name)
						)
					)
			elif row.component_type == "Total Row":
				if row.component_name not in total_row_label_set:
					frappe.throw(
						_("Total Row Components, row {0}: {1} does not match any Total Row Label").format(
							row.idx, frappe.bold(row.component_name)
						)
					)
				if row.component_name == row.row_label:
					frappe.throw(
						_("Total Row Components, row {0}: {1} cannot include itself as a component").format(
							row.idx, frappe.bold(row.row_label)
						)
					)
				component_graph[row.row_label].append(row.component_name)

		self.check_total_row_cycles(component_graph)

		section_or_total_names = section_names | total_row_label_set
		seen_sequence_entries = set()
		for row in self.row_sequence:
			if not row.row_name:
				continue

			key = (row.row_type, row.row_name)
			if key in seen_sequence_entries:
				frappe.throw(
					_("Row Sequence, row {0}: duplicate entry for {1} {2}").format(
						row.idx, row.row_type, frappe.bold(row.row_name)
					)
				)
			seen_sequence_entries.add(key)

			if row.row_type == "Section" and row.row_name not in section_names:
				frappe.throw(
					_("Row Sequence, row {0}: {1} does not match any Section Name").format(
						row.idx, frappe.bold(row.row_name)
					)
				)
			if row.row_type == "Total Row" and row.row_name not in total_row_label_set:
				frappe.throw(
					_("Row Sequence, row {0}: {1} does not match any Total Row Label").format(
						row.idx, frappe.bold(row.row_name)
					)
				)

	def check_total_row_cycles(self, component_graph):
		"""Depth-first search over Total Row -> Total Row dependencies to catch
		circular references (e.g. A sums B, B sums A) before they cause an
		infinite loop or silently-zero row in the report."""
		WHITE, GRAY, BLACK = 0, 1, 2
		state = {label: WHITE for label in component_graph}

		def visit(label, path):
			state[label] = GRAY
			for dep in component_graph.get(label, []):
				if state.get(dep) == GRAY:
					cycle = " -> ".join(path + [dep])
					frappe.throw(_("Circular reference between Total Rows: {0}").format(frappe.bold(cycle)))
				if state.get(dep) == WHITE:
					visit(dep, path + [dep])
			state[label] = BLACK

		for label in component_graph:
			if state[label] == WHITE:
				visit(label, [label])


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
def get_section_names():
    """Section Names currently defined in this doc's Cost Analysis Section table.
    Useful for client-side autocomplete on Total Row Component / Row Sequence rows,
    since those match by plain string rather than a Link field."""
    gl_grouping = frappe.get_single("Cost Analysis GL Grouping")
    return sorted({row.section_name for row in gl_grouping.section_name if row.section_name})


@frappe.whitelist()
def get_total_row_labels():
    """Total Row Labels currently defined in this doc's Total Row table.
    Useful for client-side autocomplete on Total Row Component / Row Sequence rows."""
    gl_grouping = frappe.get_single("Cost Analysis GL Grouping")
    return sorted({row.row_label for row in gl_grouping.total_row if row.row_label})


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