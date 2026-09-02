import frappe
from frappe.utils import cint

WAREHOUSE_MAP_CACHE_KEY = "igwm::{company}::{branch}"
WAREHOUSE_MAP_CACHE_TTL = 3600

CAPITAL_WAREHOUSE_CACHE_KEY = "capital_wh::{company}::{branch}::{segment}"
CAPITAL_WAREHOUSE_CACHE_TTL = 3600


def _get_allowed_warehouse_map(company, branch):
	cache_key = WAREHOUSE_MAP_CACHE_KEY.format(company=company, branch=branch)
	cached = frappe.cache().get_value(cache_key)
	if cached is not None:
		return {k: set(v) for k, v in cached.items()}

	rows = frappe.db.sql(
		"""
		select ig.item_group as item_group, wh.warehouse as warehouse
		from `tabItem Group Warehouse Mapping` m
		inner join `tabItem Groups` ig on ig.parent = m.name
		inner join `tabWarehouses` wh on wh.parent = m.name
		where m.company = %s and m.branch = %s
		""",
		(company, branch),
		as_dict=True,
	)

	allowed = {}
	for r in rows:
		allowed.setdefault(r.item_group, set()).add(r.warehouse)

	frappe.cache().set_value(
		cache_key,
		{k: list(v) for k, v in allowed.items()},
		expires_in_sec=WAREHOUSE_MAP_CACHE_TTL,
	)
	return allowed


def _get_allowed_capital_warehouses(company, branch, segment):
	cache_key = CAPITAL_WAREHOUSE_CACHE_KEY.format(company=company, branch=branch, segment=segment)
	cached = frappe.cache().get_value(cache_key)
	if cached is not None:
		return set(cached)

	warehouse_filters = {"disabled": 0, "custom_is_capital": 1}
	if company:
		warehouse_filters["company"] = company
	if branch:
		warehouse_filters["custom_branch"] = branch
	if segment:
		warehouse_filters["custom_segment"] = segment

	names = frappe.get_all("Warehouse", filters=warehouse_filters, pluck="name")
	allowed = set(names)

	frappe.cache().set_value(cache_key, list(allowed), expires_in_sec=CAPITAL_WAREHOUSE_CACHE_TTL)
	return allowed


def clear_warehouse_map_cache(doc=None, method=None):
	"""Hook this to Item Group Warehouse Mapping's on_update/on_trash/after_insert."""
	if doc and doc.company and doc.branch:
		frappe.cache().delete_value(
			WAREHOUSE_MAP_CACHE_KEY.format(company=doc.company, branch=doc.branch)
		)
	else:
		frappe.cache().delete_keys(WAREHOUSE_MAP_CACHE_KEY.format(company="*", branch="*"))


def clear_capital_warehouse_cache(doc=None, method=None):
	frappe.cache().delete_keys("capital_wh::")


def validate_item_warehouse(doc, method=None):
	company = getattr(doc, "company", None)
	branch = getattr(doc, "branch", None) or getattr(doc, "custom_branch", None)
	rows = getattr(doc, "items", None) or getattr(doc, "packed_items", None) or []
	fields = ("t_warehouse",) if doc.doctype == "Stock Entry" else ("warehouse",)

	checks = [(row, f, row.get(f)) for row in rows if row.item_code for f in fields if row.get(f)]
	if not (company and branch and checks):
		return

	is_capital = cint(getattr(doc, "custom_is_capital", 0))

	if is_capital:
		checks_by_segment = {}
		for row, fieldname, warehouse in checks:
			segment = row.get("segment") or row.get("custom_segment")
			checks_by_segment.setdefault(segment, []).append((row, fieldname, warehouse))

		for segment, segment_checks in checks_by_segment.items():
			capital_allowed = _get_allowed_capital_warehouses(company, branch, segment)
			for row, fieldname, warehouse in segment_checks:
				if warehouse not in capital_allowed:
					allowed_list = "".join(f"<li>{wh}</li>" for wh in sorted(capital_allowed)) or "<li>None configured</li>"
					frappe.throw(
						f"""
						Row #{row.idx}: Warehouse <b>{warehouse}</b> is not marked as a Capital Warehouse <br><br>
						Allowed capital warehouses in <b>{branch}</b> / <b>{segment}</b>:
						<ul>{allowed_list}</ul>
						""",
						title="Capital Warehouse Not Allowed",
					)
		return

	item_group = dict(
		frappe.get_all(
			"Item",
			filters={"name": ["in", list({r.item_code for r, _, _ in checks})]},
			fields=["name", "item_group"],
			as_list=True,
		)
	)
	allowed = _get_allowed_warehouse_map(company, branch)
	if not allowed:
		return

	for row, fieldname, warehouse in checks:
		group_allowed = allowed.get(item_group.get(row.item_code))
		if group_allowed and warehouse not in group_allowed:
			allowed_list = "".join(f"<li>{wh}</li>" for wh in sorted(group_allowed))
			frappe.throw(
				f"""
				Row #{row.idx}: Warehouse <b>{warehouse}</b> is not allowed for Item <b>{row.item_code}</b>
				(Item Group: <b>{item_group.get(row.item_code)}</b>).<br><br>
				Allowed warehouses for this item group in <b>{branch}</b>:
				<ul>{allowed_list}</ul>
				""",
				title="Warehouse Not Allowed",
			)