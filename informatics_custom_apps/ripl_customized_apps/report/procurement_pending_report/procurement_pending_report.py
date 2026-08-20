import frappe
from frappe import _
from frappe.utils import cint, flt

FIELD_MAP = {
	"mr": {"doctype": "Material Request", "plant": "branch", "segment": "custom_segment"},
	"po": {"doctype": "Purchase Order", "plant": "branch", "segment": "segment"},
	"pr": {"doctype": "Purchase Receipt", "plant": "branch", "segment": "segment"},
	"pi": {"doctype": "Purchase Invoice", "plant": "branch", "segment": "segment"},
}

RESPONSIBLE_USER_LOOKBACK_DAYS = 180
INDENT_RESPONSIBLE_USER_LOOKBACK_DAYS = 90
GATE_ENTRY_PO_CHILD_FIELD = "purchase_orders"
QI_STUCK_DOCSTATUS = 0
QI_STUCK_STATUSES = ("Rejected",)
EXCLUDE_SERVICE_ITEM_CLAUSE = "AND IFNULL(item.is_stock_item, 1) = 1"

ITEM_TABLE_MAP = {
	"mr": "Material Request Item",
	"po": "Purchase Order Item",
	"pr": "Purchase Receipt Item",
}

DEFAULT_MIN_DAYS_DELAYED = 10


def plant_field(alias):
	return FIELD_MAP[alias]["plant"]


def segment_field(alias):
	return FIELD_MAP[alias]["segment"]


def execute(filters=None):
	filters = frappe._dict(filters or {})
	drill_type = filters.get("drill_type")

	if drill_type == "indent":
		return get_indent_drilldown_columns(), get_indent_drilldown_data(filters)
	if drill_type == "purchase_order":
		return get_po_pending_drilldown_columns(), get_po_pending_drilldown_data(filters)
	if drill_type == "pr":
		return get_ge_pending_drilldown_columns(), get_ge_pending_drilldown_data(filters)
	if drill_type == "qi":
		return get_qi_drilldown_columns(), get_qi_drilldown_data(filters)
	if drill_type == "prsub":
		return get_prsub_drilldown_columns(), get_prsub_drilldown_data(filters)
	if drill_type == "pi":
		return get_pi_drilldown_columns(), get_pi_drilldown_data(filters)

	return get_summary_columns(), get_summary_data(filters)


def segment_not_blank_clause(alias):
	sf = segment_field(alias)
	return f"AND {alias}.{sf} IS NOT NULL AND {alias}.{sf} != ''"


def get_above_amount_threshold(filters):
	return flt(filters.get("above_amount"))


def only_above_1lakh_clause(amount_expr, filters, keyword="AND"):
	if cint(filters.get("only_above_1lakh", 1)):
		threshold = get_above_amount_threshold(filters)
		return f"{keyword} ({amount_expr}) > {threshold}"
	return ""


def get_min_days_delayed(filters):
	value = filters.get("min_days_delayed")
	if value in (None, ""):
		return DEFAULT_MIN_DAYS_DELAYED
	return cint(value)


def mark_continuation_rows(rows, group_key="document_no"):
	prev = object()  # sentinel that can't equal any real document_no
	for r in rows:
		r["_merged_continuation"] = 1 if r.get(group_key) == prev else 0
		prev = r.get(group_key)
	return rows


def attach_item_list_field(rows, group_key="document_no", item_field="item_name"):
	items_by_doc = {}
	for r in rows:
		items_by_doc.setdefault(r.get(group_key), []).append(r.get(item_field) or "")
	for r in rows:
		r["item_list"] = ", ".join(filter(None, items_by_doc.get(r.get(group_key), [])))
	return rows


def get_common_conditions(filters, alias):
	conditions = []
	values = {}

	if filters.get("plant"):
		conditions.append(f"{alias}.{plant_field(alias)} = %(plant)s")
		values["plant"] = filters.plant
	if filters.get("segment"):
		conditions.append(f"{alias}.{segment_field(alias)} = %(segment)s")
		values["segment"] = filters.segment

	if filters.get("cost_center"):
		item_doctype = ITEM_TABLE_MAP.get(alias)
		if item_doctype:
			conditions.append(
				f"EXISTS (SELECT 1 FROM `tab{item_doctype}` cci WHERE cci.parent = {alias}.name AND cci.cost_center = %(cost_center)s)"
			)
			values["cost_center"] = filters.cost_center

	date_field = "transaction_date" if alias in ("mr", "po") else "posting_date"
	if filters.get("from_date"):
		conditions.append(f"{alias}.{date_field} >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append(f"{alias}.{date_field} <= %(to_date)s")
		values["to_date"] = filters.to_date

	conditions.append(f"DATEDIFF(CURDATE(), {alias}.{date_field}) >= %(min_days_delayed)s")
	values["min_days_delayed"] = get_min_days_delayed(filters)

	clause = ("AND " + " AND ".join(conditions)) if conditions else ""
	return clause, values


def get_frequent_responsible_users(alias, lookback_days=RESPONSIBLE_USER_LOOKBACK_DAYS):
	doctype = FIELD_MAP[alias]["doctype"]
	pf = plant_field(alias)
	sf = segment_field(alias)

	rows = frappe.db.sql(f"""
		SELECT plant, segment, full_name FROM (
			SELECT
				t.{pf} AS plant,
				t.{sf} AS segment,
				IFNULL(u.full_name, t.owner) AS full_name,
				COUNT(*) AS cnt,
				ROW_NUMBER() OVER (
					PARTITION BY t.{pf}, t.{sf}
					ORDER BY COUNT(*) DESC, MAX(t.creation) DESC
				) AS rn
			FROM `tab{doctype}` t
			LEFT JOIN `tabUser` u ON u.name = t.owner
			WHERE t.docstatus = 1
				AND t.creation >= DATE_SUB(CURDATE(), INTERVAL %(lookback_days)s DAY)
			GROUP BY t.{pf}, t.{sf}, t.owner
		) ranked
		WHERE rn = 1
	""", {"lookback_days": lookback_days}, as_dict=True)

	return {(r.plant, r.segment): r.full_name for r in rows}


def get_frequent_submitters(doctype, plant_field_name, segment_field_name, lookback_days=RESPONSIBLE_USER_LOOKBACK_DAYS):
	rows = frappe.db.sql(f"""
		SELECT plant, segment, full_name FROM (
			SELECT
				t.{plant_field_name} AS plant,
				t.{segment_field_name} AS segment,
				IFNULL(u.full_name, t.modified_by) AS full_name,
				COUNT(*) AS cnt,
				ROW_NUMBER() OVER (
					PARTITION BY t.{plant_field_name}, t.{segment_field_name}
					ORDER BY COUNT(*) DESC, MAX(t.modified) DESC
				) AS rn
			FROM `tab{doctype}` t
			LEFT JOIN `tabUser` u ON u.name = t.modified_by
			WHERE t.docstatus = 1
				AND t.modified >= DATE_SUB(CURDATE(), INTERVAL %(lookback_days)s DAY)
			GROUP BY t.{plant_field_name}, t.{segment_field_name}, t.modified_by
		) ranked
		WHERE rn = 1
	""", {"lookback_days": lookback_days}, as_dict=True)

	return {(r.plant, r.segment): r.full_name for r in rows}


def get_frequent_pr_submitters(lookback_days=RESPONSIBLE_USER_LOOKBACK_DAYS):
	return get_frequent_submitters("Purchase Receipt", plant_field("pr"), segment_field("pr"), lookback_days)


def get_frequent_pi_submitters(lookback_days=RESPONSIBLE_USER_LOOKBACK_DAYS):
	return get_frequent_submitters("Purchase Invoice", plant_field("pi"), segment_field("pi"), lookback_days)


def apply_frequent_responsible_user(alias, rows, lookback_days=RESPONSIBLE_USER_LOOKBACK_DAYS):
	if not rows:
		return rows
	frequent = get_frequent_responsible_users(alias, lookback_days=lookback_days)
	for r in rows:
		usual = frequent.get((r.plant, r.segment))
		if usual:
			r["responsible_user"] = usual
	return rows


def get_pr_names_with_draft_pi(pr_names):
	if not pr_names:
		return set()

	rows = frappe.db.sql("""
		SELECT DISTINCT pii.purchase_receipt AS pr_name
		FROM `tabPurchase Invoice Item` pii
		INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent AND pi.docstatus = 0
		WHERE pii.purchase_receipt IN %(pr_names)s
	""", {"pr_names": pr_names}, as_dict=True)

	return {r.pr_name for r in rows}


def get_summary_columns():
	return [
		{"label": _("Plant / Segment"), "fieldname": "plant_segment", "fieldtype": "Data", "width": 290, "align": "left"},
		{"label": _("Pending Indents"), "fieldname": "pending_po", "fieldtype": "Int", "width": 140, "align": "left"},
		{"label": _("Pending Purchase Orders"), "fieldname": "pending_purchase_order", "fieldtype": "Int", "width": 200, "align": "left"},
		{"label": _("Pending Gate Entries"), "fieldname": "pending_gate_entry", "fieldtype": "Int", "width": 180, "align": "left"},
		{"label": _("Pending Quality Inspection"), "fieldname": "pending_qi", "fieldtype": "Int", "width": 210, "align": "left"},
		{"label": _("Pending GRN"), "fieldname": "pending_pr_submission", "fieldtype": "Int", "width": 140, "align": "left"},
		{"label": _("Pending SRV"), "fieldname": "pending_pi", "fieldtype": "Int", "width": 140, "align": "left"},
	]


def get_summary_data(filters):
	mr_conditions, mr_values = get_common_conditions(filters, "mr")
	po_conditions, po_values = get_common_conditions(filters, "po")
	pr_conditions, pr_values = get_common_conditions(filters, "pr")

	mr_amount_expr = "(SELECT SUM(mri.amount) FROM `tabMaterial Request Item` mri WHERE mri.parent = mr.name)"

	indent_pending = frappe.db.sql(f"""
		SELECT mr.{plant_field("mr")} AS plant, mr.{segment_field("mr")} AS segment, COUNT(*) AS cnt
		FROM `tabMaterial Request` mr
		WHERE mr.docstatus = 1
			AND IFNULL(mr.per_ordered, 0) = 0
			AND mr.status NOT IN ('Stopped', 'Cancelled')
			{segment_not_blank_clause("mr")}
			{mr_conditions}
			{only_above_1lakh_clause(mr_amount_expr, filters)}
		GROUP BY mr.{plant_field("mr")}, mr.{segment_field("mr")}
	""", mr_values, as_dict=True)

	po_pending = frappe.db.sql(f"""
		SELECT po.{plant_field("po")} AS plant, po.{segment_field("po")} AS segment, COUNT(*) AS cnt
		FROM `tabPurchase Order` po
		LEFT JOIN (
			SELECT
				gepo.{GATE_ENTRY_PO_CHILD_FIELD} AS po_name,
				MAX(CASE WHEN ge.is_completed = 1 THEN 1 ELSE 0 END) AS weighment_done,
				MAX(CASE WHEN ge.is_weighment_required = 'Yes' THEN 1 ELSE 0 END) AS is_weighment_required
			FROM `tabPurchase Orders` gepo
			INNER JOIN `tabGate Entry` ge ON ge.name = gepo.parent AND ge.docstatus = 1
			GROUP BY gepo.{GATE_ENTRY_PO_CHILD_FIELD}
		) ge ON ge.po_name = po.name
		WHERE po.docstatus = 1
			AND po.status NOT IN ('Completed', 'Closed', 'Delivered')
			AND ge.po_name IS NULL
			{segment_not_blank_clause("po")}
			{po_conditions}
			{only_above_1lakh_clause("po.grand_total", filters)}
		GROUP BY po.{plant_field("po")}, po.{segment_field("po")}
	""", po_values, as_dict=True)

	gate_entry_pending = frappe.db.sql(f"""
		SELECT po.{plant_field("po")} AS plant, po.{segment_field("po")} AS segment, COUNT(*) AS cnt
		FROM `tabPurchase Order` po
		LEFT JOIN (
			SELECT
				gepo.{GATE_ENTRY_PO_CHILD_FIELD} AS po_name,
				MAX(CASE WHEN ge.is_completed = 1 THEN 1 ELSE 0 END) AS weighment_done,
				MAX(CASE WHEN ge.is_weighment_required = 'Yes' THEN 1 ELSE 0 END) AS is_weighment_required
			FROM `tabPurchase Orders` gepo
			INNER JOIN `tabGate Entry` ge ON ge.name = gepo.parent AND ge.docstatus = 1
			GROUP BY gepo.{GATE_ENTRY_PO_CHILD_FIELD}
		) ge ON ge.po_name = po.name
		WHERE po.docstatus = 1
			AND po.status NOT IN ('Completed', 'Closed', 'Delivered')
			AND ge.weighment_done = 0
			AND NOT (
				ge.is_weighment_required = 0
				AND IFNULL(po.per_received, 0) >= 100
			)
			{segment_not_blank_clause("po")}
			{po_conditions}
			{only_above_1lakh_clause("po.grand_total", filters)}
		GROUP BY po.{plant_field("po")}, po.{segment_field("po")}
	""", po_values, as_dict=True)


	qi_pending = frappe.db.sql(f"""
		SELECT pr.{plant_field("pr")} AS plant, pr.{segment_field("pr")} AS segment, COUNT(DISTINCT pr.name) AS cnt
		FROM `tabPurchase Receipt` pr
		INNER JOIN `tabQuality Inspection` qi
			ON qi.reference_type = 'Purchase Receipt'
			AND qi.reference_name = pr.name
			AND qi.docstatus = 0
		WHERE pr.docstatus = 0
			{segment_not_blank_clause("pr")}
			{pr_conditions}
			{only_above_1lakh_clause("pr.grand_total", filters)}
		GROUP BY pr.{plant_field("pr")}, pr.{segment_field("pr")}
	""", pr_values, as_dict=True)


	prsub_pending = frappe.db.sql(f"""
		SELECT pr.{plant_field("pr")} AS plant, pr.{segment_field("pr")} AS segment, COUNT(DISTINCT pr.name) AS cnt
		FROM `tabPurchase Receipt` pr
		INNER JOIN `tabQuality Inspection` qi
			ON qi.reference_type = 'Purchase Receipt'
			AND qi.reference_name = pr.name
			AND qi.docstatus = 1
		WHERE pr.docstatus = 0
			{segment_not_blank_clause("pr")}
			{pr_conditions}
			{only_above_1lakh_clause("pr.grand_total", filters)}
		GROUP BY pr.{plant_field("pr")}, pr.{segment_field("pr")}
	""", pr_values, as_dict=True)

	pi_pending = frappe.db.sql(f"""
		SELECT pr.{plant_field("pr")} AS plant, pr.{segment_field("pr")} AS segment, COUNT(*) AS cnt
		FROM `tabPurchase Receipt` pr
		WHERE pr.docstatus = 1
			AND IFNULL(pr.is_return, 0) = 0
			AND IFNULL(pr.per_billed, 0) = 0
			AND pr.status = 'To Bill'
			{segment_not_blank_clause("pr")}
			{pr_conditions}
			{only_above_1lakh_clause("pr.grand_total", filters)}
		GROUP BY pr.{plant_field("pr")}, pr.{segment_field("pr")}
	""", pr_values, as_dict=True)

	merged = {}
	for rows, key_name in (
		(indent_pending, "pending_po"),
		(po_pending, "pending_purchase_order"),
		(gate_entry_pending, "pending_gate_entry"),
		(qi_pending, "pending_qi"),
		(prsub_pending, "pending_pr_submission"),
		(pi_pending, "pending_pi"),
	):
		for r in rows:
			k = (r.plant, r.segment)
			merged.setdefault(k, {
				"plant": r.plant, "segment": r.segment,
				"pending_po": 0, "pending_purchase_order": 0, "pending_gate_entry": 0,
				"pending_qi": 0, "pending_pr_submission": 0, "pending_pi": 0,
			})
			merged[k][key_name] = r.cnt

	for d in merged.values():
		d["plant_segment"] = " / ".join(p for p in (d["plant"], d["segment"]) if p)

	merged = {k: d for k, d in merged.items() if d["segment"]}

	return sorted(merged.values(), key=lambda d: (d["plant"] or "", d["segment"] or ""))


def get_indent_drilldown_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 200, "align": "left"},
		{"label": _("Required By"), "fieldname": "schedule_date", "fieldtype": "Date", "width": 120, "align": "left"},
		{"label": _("Item"), "fieldname": "item_name", "fieldtype": "Data", "width": 280, "align": "left"},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120, "align": "left"},
  		{"label": _("Days Delayed"), "fieldname": "days_delayed", "fieldtype": "Int", "width": 120, "align": "left"},
		{"label": _("Responsible User"), "fieldname": "responsible_user", "fieldtype": "Data", "width": 140, "align": "left"}
	]


def get_indent_drilldown_data(filters):
	conditions, values = get_common_conditions(filters, "mr")
	rows = frappe.db.sql(f"""
		SELECT * FROM (
			SELECT
				mr.name AS document_no,
				mr.{plant_field("mr")} AS plant,
				mr.{segment_field("mr")} AS segment,
				mr.transaction_date AS posting_date,
				IFNULL(u.full_name, mr.owner) AS responsible_user,
				DATEDIFF(CURDATE(), mr.transaction_date) AS days_delayed,
				IFNULL(SUM(mri.amount) OVER (PARTITION BY mr.name), 0) AS amount,
				COALESCE(item.item_name, mri.item_code, '') AS item_name,
				mri.idx AS item_idx,
				(
					SELECT MIN(mri2.schedule_date)
					FROM `tabMaterial Request Item` mri2
					WHERE mri2.parent = mr.name
				) AS schedule_date
			FROM `tabMaterial Request` mr
			LEFT JOIN `tabMaterial Request Item` mri ON mri.parent = mr.name
			LEFT JOIN `tabItem` item ON item.name = mri.item_code
			LEFT JOIN `tabUser` u ON u.name = mr.owner
			WHERE mr.docstatus = 1
				AND IFNULL(mr.per_ordered, 0) = 0
				AND mr.status NOT IN ('Stopped', 'Cancelled')
				{conditions}
				{EXCLUDE_SERVICE_ITEM_CLAUSE}
		) ranked
		{only_above_1lakh_clause("amount", filters, keyword="WHERE")}
		ORDER BY amount DESC, document_no, item_idx
	""", values, as_dict=True)

	if not rows:
		return rows

	attach_item_list_field(rows)

	rows = apply_frequent_responsible_user("po", rows, lookback_days=INDENT_RESPONSIBLE_USER_LOOKBACK_DAYS)
	return mark_continuation_rows(rows)


def get_po_pending_drilldown_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 210, "align": "left"},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Data", "width": 270, "align": "left"},
		{"label": _("Item"), "fieldname": "item_name", "fieldtype": "Data", "width": 280, "align": "left"},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120, "align": "left"},
		{"label": _("Received%"), "fieldname": "received_pct", "fieldtype": "Data", "width": 110, "align": "left"},
		{"label": _("Days Delayed"), "fieldname": "days_delayed", "fieldtype": "Int", "width": 120, "align": "left"},
		{"label": _("Responsible User"), "fieldname": "responsible_user", "fieldtype": "Data", "width": 170, "align": "left"},
	]


def get_po_pending_drilldown_data(filters):
	conditions, values = get_common_conditions(filters, "po")
	rows = frappe.db.sql(f"""
		SELECT
			po.name AS document_no,
			po.{plant_field("po")} AS plant,
			po.{segment_field("po")} AS segment,
			po.transaction_date AS posting_date,
			IFNULL(s.supplier_name, po.supplier) AS supplier,
			po.grand_total AS amount,
			IFNULL(po.per_received, 0) AS received_pct,
			IFNULL(u.full_name, po.owner) AS responsible_user,
			DATEDIFF(CURDATE(), po.transaction_date) AS days_delayed,
			COALESCE(item.item_name, poi.item_code, '') AS item_name,
			poi.idx AS item_idx
		FROM `tabPurchase Order` po
		LEFT JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
		LEFT JOIN `tabItem` item ON item.name = poi.item_code
		LEFT JOIN `tabUser` u ON u.name = po.owner
		LEFT JOIN `tabSupplier` s ON s.name = po.supplier
		LEFT JOIN (
			SELECT
				gepo.{GATE_ENTRY_PO_CHILD_FIELD} AS po_name,
				MAX(CASE WHEN ge.is_completed = 1 THEN 1 ELSE 0 END) AS weighment_done,
				MAX(CASE WHEN ge.is_weighment_required = 'Yes' THEN 1 ELSE 0 END) AS is_weighment_required
			FROM `tabPurchase Orders` gepo
			INNER JOIN `tabGate Entry` ge ON ge.name = gepo.parent AND ge.docstatus = 1
			GROUP BY gepo.{GATE_ENTRY_PO_CHILD_FIELD}
		) ge ON ge.po_name = po.name
		WHERE po.docstatus = 1
			AND po.status NOT IN ('Completed', 'Closed', 'Delivered')
			AND ge.po_name IS NULL
			{conditions}
			{only_above_1lakh_clause("po.grand_total", filters)}
			{EXCLUDE_SERVICE_ITEM_CLAUSE}
		ORDER BY amount DESC, document_no, item_idx
	""", values, as_dict=True)

	if not rows:
		return rows

	document_nos = list({r.document_no for r in rows})
	po_receipt_map = get_po_receipt_map(document_nos)
	for r in rows:
		r["pr_count"] = len(po_receipt_map.get(r.document_no, []))

	attach_item_list_field(rows)
	return mark_continuation_rows(rows)


def get_ge_pending_drilldown_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110, "align": "left"},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Data", "width": 280, "align": "left"},
		{"label": _("Item"), "fieldname": "item_name", "fieldtype": "Data", "width": 280, "align": "left"},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 160, "align": "left"},
		{"label": _("Weighment*"), "fieldname": "is_weighment_required", "fieldtype": "Data", "width": 110, "align": "left"},
		{"label": _("Weighment Status"), "fieldname": "weighment_status", "fieldtype": "Data", "width": 180, "align": "left"},
		{"label": _("Days Delayed"), "fieldname": "days_delayed", "fieldtype": "Int", "width": 120, "align": "left"},
		{"label": _("Responsible User"), "fieldname": "responsible_user", "fieldtype": "Data", "width": 170, "align": "left"},
	]


def get_ge_pending_drilldown_data(filters):
	conditions, values = get_common_conditions(filters, "po")
	rows = frappe.db.sql(f"""
		SELECT
			po.name AS document_no,
			po.{plant_field("po")} AS plant,
			po.{segment_field("po")} AS segment,
			po.transaction_date AS posting_date,
			IFNULL(s.supplier_name, po.supplier) AS supplier,
			po.grand_total AS amount,
			IFNULL(u.full_name, po.owner) AS responsible_user,
			DATEDIFF(CURDATE(), po.transaction_date) AS days_delayed,
			COALESCE(item.item_name, poi.item_code, '') AS item_name,
			poi.idx AS item_idx,
			ge.weighment_in_progress AS weighment_in_progress,
			ge.is_weighment_required AS is_weighment_required_raw,
			ge.latest_gate_entry AS gate_entry
		FROM `tabPurchase Order` po
		LEFT JOIN `tabPurchase Order Item` poi ON poi.parent = po.name
		LEFT JOIN `tabItem` item ON item.name = poi.item_code
		LEFT JOIN `tabUser` u ON u.name = po.owner
		LEFT JOIN `tabSupplier` s ON s.name = po.supplier
		LEFT JOIN (
			SELECT
				gepo.{GATE_ENTRY_PO_CHILD_FIELD} AS po_name,
				MAX(CASE WHEN ge.is_completed = 1 THEN 1 ELSE 0 END) AS weighment_done,
				MAX(CASE WHEN ge.is_in_progress = 1 THEN 1 ELSE 0 END) AS weighment_in_progress,
				MAX(CASE WHEN ge.is_weighment_required = 'Yes' THEN 1 ELSE 0 END) AS is_weighment_required,
				-- Most recently created linked Gate Entry, used as "the"
				-- gate entry for this PO when routing the row's link --
				-- relevant when a PO has more than one Gate Entry against it.
				SUBSTRING_INDEX(GROUP_CONCAT(gepo.parent ORDER BY ge.creation DESC), ',', 1) AS latest_gate_entry
			FROM `tabPurchase Orders` gepo
			INNER JOIN `tabGate Entry` ge ON ge.name = gepo.parent AND ge.docstatus = 1
			GROUP BY gepo.{GATE_ENTRY_PO_CHILD_FIELD}
		) ge ON ge.po_name = po.name
		WHERE po.docstatus = 1
			AND po.status NOT IN ('Completed', 'Closed', 'Delivered')
			AND ge.weighment_done = 0
			AND NOT (
				ge.is_weighment_required = 0
				AND IFNULL(po.per_received, 0) >= 100
			)
			{conditions}
			{only_above_1lakh_clause("po.grand_total", filters)}
			{EXCLUDE_SERVICE_ITEM_CLAUSE}
		ORDER BY amount DESC, document_no, item_idx
	""", values, as_dict=True)

	if not rows:
		return rows
	gate_entries = list({r.gate_entry for r in rows if r.gate_entry})
	weighment_map = get_latest_weighment_by_gate_entry(gate_entries)

	frequent_pr_submitters = get_frequent_pr_submitters()

	for r in rows:
		r["weighment"] = weighment_map.get(r.gate_entry) if r.gate_entry else None

		if not r.is_weighment_required_raw:

			r["is_weighment_required"] = "No"
			r["weighment_status"] = ""
		else:

			r["is_weighment_required"] = "Yes"
			r["weighment_status"] = "Weighment In Progress" if r.weighment_in_progress else "Weighment Pending"


		usual_pr_submitter = frequent_pr_submitters.get((r.plant, r.segment))
		if usual_pr_submitter:
			r["responsible_user"] = usual_pr_submitter

		del r["is_weighment_required_raw"]

	attach_item_list_field(rows)
	return mark_continuation_rows(rows)


def get_gate_weighment_status(po_names):
	if not po_names:
		return {}

	rows = frappe.db.sql(f"""
		SELECT
			gepo.{GATE_ENTRY_PO_CHILD_FIELD} AS po_name,
			MAX(CASE WHEN ge.is_completed = 1 THEN 1 ELSE 0 END) AS weighment_done,
			MAX(CASE WHEN ge.is_in_progress = 1 THEN 1 ELSE 0 END) AS weighment_in_progress,
			MAX(CASE WHEN ge.is_weighment_required = 'Yes' THEN 1 ELSE 0 END) AS is_weighment_required
		FROM `tabPurchase Orders` gepo
		INNER JOIN `tabGate Entry` ge ON ge.name = gepo.parent AND ge.docstatus = 1
		WHERE gepo.{GATE_ENTRY_PO_CHILD_FIELD} IN %(po_names)s
		GROUP BY gepo.{GATE_ENTRY_PO_CHILD_FIELD}
	""", {"po_names": po_names}, as_dict=True)

	return {r.po_name: r for r in rows}


def get_po_receipt_map(po_names):
	if not po_names:
		return {}

	rows = frappe.db.sql("""
		SELECT DISTINCT pri.purchase_order AS po_name, pri.parent AS pr_name
		FROM `tabPurchase Receipt Item` pri
		INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent AND pr.docstatus = 1
		WHERE pri.purchase_order IN %(po_names)s
	""", {"po_names": po_names}, as_dict=True)

	po_to_receipts = {}
	for r in rows:
		po_to_receipts.setdefault(r.po_name, set()).add(r.pr_name)
	return po_to_receipts


def get_latest_weighment_by_gate_entry(gate_entry_names):
	if not gate_entry_names:
		return {}

	rows = frappe.db.sql("""
		SELECT gate_entry_number, name AS weighment_name
		FROM `tabWeighment`
		WHERE gate_entry_number IN %(gate_entry_names)s
		ORDER BY creation DESC
	""", {"gate_entry_names": gate_entry_names}, as_dict=True)

	weighment_map = {}
	for r in rows:

		weighment_map.setdefault(r.gate_entry_number, r.weighment_name)
	return weighment_map


def get_quality_inspection_status(po_names, po_receipt_map=None):
	if not po_names:
		return {}

	if po_receipt_map is None:
		po_receipt_map = get_po_receipt_map(po_names)
	if not po_receipt_map:
		return {}

	receipt_to_pos = {}
	for po_name, receipts in po_receipt_map.items():
		for pr_name in receipts:
			receipt_to_pos.setdefault(pr_name, set()).add(po_name)

	receipt_names = list(receipt_to_pos.keys())
	if not receipt_names:
		return {}

	qi_rows = frappe.db.sql("""
		SELECT
			qi.name AS qi_name,
			qi.reference_name AS pr_name,
			qi.docstatus AS docstatus,
			qi.status AS status,
			qi.modified AS modified,
			IFNULL(qi.custom_employee_name, IFNULL(u.full_name, qi.inspected_by)) AS inspector
		FROM `tabQuality Inspection` qi
		LEFT JOIN `tabUser` u ON u.name = qi.inspected_by
		WHERE qi.reference_type = 'Purchase Receipt'
			AND qi.reference_name IN %(receipt_names)s
		ORDER BY qi.modified DESC
	""", {"receipt_names": receipt_names}, as_dict=True)

	result = {}
	for row in qi_rows:
		is_stuck = row.docstatus == QI_STUCK_DOCSTATUS or row.status in QI_STUCK_STATUSES
		if not is_stuck:
			continue
		for po_name in receipt_to_pos.get(row.pr_name, []):
			if po_name not in result:
				result[po_name] = {
					"stuck_in_quality": 1,
					"quality_responsible_user": row.inspector or "",
					"quality_inspection": row.qi_name,
				}

	return result


def get_qi_drilldown_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110, "align": "left"},
		# {"label": _("Purchase Receipt"), "fieldname": "purchase_receipt", "fieldtype": "Link", "options": "Purchase Receipt", "width": 170, "align": "left"},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Data", "width": 210, "align": "left"},
		{"label": _("Item"), "fieldname": "item_name", "fieldtype": "Data", "width": 210, "align": "left"},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 160, "align": "left"},
  		{"label": _("Days Delayed"), "fieldname": "days_delayed", "fieldtype": "Int", "width": 120, "align": "left"},
		{"label": _("Responsible User"), "fieldname": "responsible_user", "fieldtype": "Data", "width": 150, "align": "left"},
	]


def get_qi_drilldown_data(filters):
	conditions, values = get_common_conditions(filters, "pr")
	rows = frappe.db.sql(f"""
		SELECT
			w.document_no, w.purchase_receipt, w.plant, w.segment, w.posting_date,
			w.supplier, w.amount, w.responsible_user, w.days_delayed,
			COALESCE(item.item_name, pri.item_code, '') AS item_name,
			pri.idx AS item_idx
		FROM (
			SELECT
				document_no, purchase_receipt, plant, segment, posting_date,
				supplier, amount, responsible_user, days_delayed
			FROM (
				SELECT
					qi.name AS document_no,
					pr.name AS purchase_receipt,
					pr.{plant_field("pr")} AS plant,
					pr.{segment_field("pr")} AS segment,
					pr.posting_date AS posting_date,
					IFNULL(s.supplier_name, pr.supplier) AS supplier,
					pr.grand_total AS amount,
					IFNULL(qi.custom_employee_name, IFNULL(u.full_name, pr.owner)) AS responsible_user,
					DATEDIFF(CURDATE(), pr.creation) AS days_delayed,
					ROW_NUMBER() OVER (
						PARTITION BY pr.name
						ORDER BY qi.modified DESC
					) AS rn
				FROM `tabPurchase Receipt` pr
				INNER JOIN `tabQuality Inspection` qi
					ON qi.reference_type = 'Purchase Receipt'
					AND qi.reference_name = pr.name
					AND qi.docstatus = 0
				LEFT JOIN `tabUser` u ON u.name = pr.owner
				LEFT JOIN `tabSupplier` s ON s.name = pr.supplier
				WHERE pr.docstatus = 0
					{conditions}
					{only_above_1lakh_clause("pr.grand_total", filters)}
			) ranked
			WHERE rn = 1
		) w
		LEFT JOIN `tabPurchase Receipt Item` pri ON pri.parent = w.purchase_receipt
		LEFT JOIN `tabItem` item ON item.name = pri.item_code
		WHERE 1 = 1
			{EXCLUDE_SERVICE_ITEM_CLAUSE}
		ORDER BY w.amount DESC, w.document_no, pri.idx
	""", values, as_dict=True)

	if not rows:
		return rows

	attach_item_list_field(rows)
	return mark_continuation_rows(rows)


def get_prsub_drilldown_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110, "align": "left"},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Data", "width": 280, "align": "left"},
		{"label": _("Item"), "fieldname": "item_name", "fieldtype": "Data", "width": 280, "align": "left"},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120, "align": "left"},
		# {"label": _("Quality Inspection"), "fieldname": "quality_inspection", "fieldtype": "Link", "options": "Quality Inspection", "width": 170, "align": "left"},
		{"label": _("Days Delayed"), "fieldname": "days_delayed", "fieldtype": "Int", "width": 120, "align": "left"},
  		{"label": _("Responsible User"), "fieldname": "responsible_user", "fieldtype": "Data", "width": 150, "align": "left"},
	]


def get_prsub_drilldown_data(filters):
	conditions, values = get_common_conditions(filters, "pr")
	rows = frappe.db.sql(f"""
		SELECT
			pr.name AS document_no,
			pr.{plant_field("pr")} AS plant,
			pr.{segment_field("pr")} AS segment,
			pr.posting_date AS posting_date,
			IFNULL(s.supplier_name, pr.supplier) AS supplier,
			pr.grand_total AS amount,
			qi.name AS quality_inspection,
			IFNULL(u.full_name, pr.owner) AS responsible_user,
			DATEDIFF(CURDATE(), pr.creation) AS days_delayed,
			COALESCE(item.item_name, pri.item_code, '') AS item_name,
			pri.idx AS item_idx
		FROM `tabPurchase Receipt` pr
		INNER JOIN `tabQuality Inspection` qi
			ON qi.reference_type = 'Purchase Receipt'
			AND qi.reference_name = pr.name
			AND qi.docstatus = 1
		LEFT JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
		LEFT JOIN `tabItem` item ON item.name = pri.item_code
		LEFT JOIN `tabUser` u ON u.name = pr.owner
		LEFT JOIN `tabSupplier` s ON s.name = pr.supplier
		WHERE pr.docstatus = 0
			{conditions}
			{only_above_1lakh_clause("pr.grand_total", filters)}
			{EXCLUDE_SERVICE_ITEM_CLAUSE}
		ORDER BY amount DESC, document_no, item_idx
	""", values, as_dict=True)

	if not rows:
		return rows

	frequent_pr_submitters = get_frequent_pr_submitters()
	for r in rows:
		usual = frequent_pr_submitters.get((r.plant, r.segment))
		if usual:
			r["responsible_user"] = usual

	attach_item_list_field(rows)
	return mark_continuation_rows(rows)


def get_pi_drilldown_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110, "align": "left"},
		{"label": _("Supplier"), "fieldname": "supplier", "fieldtype": "Data", "width": 260, "align": "left"},
		{"label": _("Item"), "fieldname": "item_name", "fieldtype": "Data", "width": 260, "align": "left"},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 110, "align": "left"},
  		{"label": _("Days Delayed"), "fieldname": "days_delayed", "fieldtype": "Int", "width": 120, "align": "left"},

		{"label": _("Responsible User"), "fieldname": "responsible_user", "fieldtype": "Data", "width": 150, "align": "left"},
	]


def get_pi_drilldown_data(filters):
	conditions, values = get_common_conditions(filters, "pr")
	rows = frappe.db.sql(f"""
		SELECT
			pr.name AS document_no,
			pr.{plant_field("pr")} AS plant,
			pr.{segment_field("pr")} AS segment,
			pr.posting_date AS posting_date,
			IFNULL(s.supplier_name, pr.supplier) AS supplier,
			pr.grand_total AS amount,
			IFNULL(u.full_name, pr.owner) AS responsible_user,
			DATEDIFF(CURDATE(), pr.posting_date) AS days_delayed,
			COALESCE(item.item_name, pri.item_code, '') AS item_name,
			pri.idx AS item_idx
		FROM `tabPurchase Receipt` pr
		LEFT JOIN `tabPurchase Receipt Item` pri ON pri.parent = pr.name
		LEFT JOIN `tabItem` item ON item.name = pri.item_code
		LEFT JOIN `tabUser` u ON u.name = pr.owner
		LEFT JOIN `tabSupplier` s ON s.name = pr.supplier
		WHERE pr.docstatus = 1
			AND IFNULL(pr.is_return, 0) = 0
			AND IFNULL(pr.per_billed, 0) = 0
			AND pr.status = 'To Bill'
			{conditions}
			{only_above_1lakh_clause("pr.grand_total", filters)}
			{EXCLUDE_SERVICE_ITEM_CLAUSE}
		ORDER BY amount DESC, document_no, item_idx
	""", values, as_dict=True)

	if not rows:
		return rows
	document_nos = list({r.document_no for r in rows})
	prs_with_draft_pi = get_pr_names_with_draft_pi(document_nos)
	frequent_creators = get_frequent_responsible_users("pi")
	frequent_submitters = get_frequent_pi_submitters()

	for r in rows:
		key = (r.plant, r.segment)
		if r.document_no in prs_with_draft_pi:
			usual = frequent_submitters.get(key)
		else:
			usual = frequent_creators.get(key)
		if usual:
			r["responsible_user"] = usual

	attach_item_list_field(rows)
	return mark_continuation_rows(rows)