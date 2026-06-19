import frappe
from frappe.utils import flt, add_months, today

def get_context(context):
	pass


FINISHED_GOODS_MAP = {
	"010101-Sugar-Mfg":            "Sugar",
	"010105-Molasses-Mfg":         "Molasses",
	"010201-Ethanol-Mfg":          "Ethanol",
	"010211-Corn Oil-Mfg":         "Corn Oil",
	"010103-Cattle Feed-Mfg-Beet": "Cattle Feed",
	"010203-Cattle Feed-Mfg":      "Cattle Feed",
	"010204-Country Liquor-Mfg":   "Country Liquor",
	"010205-IMFL-Mfg":             "IMFL",
	"010202-ENA-Mfg":              "ENA",
	"010206-Rectified Spirit-Mfg": "Rectified Spirit",
}

FINISHED_GOODS_ROW_ORDER = [
	"Sugar", "Molasses", "Ethanol", "Corn Oil",
	"Cattle Feed", "Country Liquor", "IMFL", "ENA", "Rectified Spirit",
]

FUEL_MAP = {
	"100093": "Bagasse-Cane-Mfg",
	"135009": "Bagasse-Cane-Mfg (Non Weightment)",
	"100094": "Bagasse-Cane-Trd",
	"132087": "Bagasse-Cane-Trd (Non Weighment)",
	"106439": "Bio Mass",
	"130196": "Biomass Pellets",
	"101077": "Cane Trash",
	"111708": "Cane Trash - Non Weightment",
	"128539": "Crusher Bagasse",
	"129853": "Imported Indonesian Coal (Sale)",
	"106983": "Khuddi",
	"106437": "Khudi",
	"119510": "Maize Straw",
	"106442": "Mandi Husk",
	"106440": "Mustard Husk",
	"106441": "Paddy Straw",
	"125335": "Paddy Straw (Non Weighment)",
	"111600": "Pulse Husk",
	"111650": "Pulverized Pellets",
	"131959": "Refuse Derived Fuel (RDF Waste)",
	"106436": "Rice Husk",
	"129122": "Rice Husk (Sale)",
	"106984": "Saw Dust (Burada)",
	"106985": "Sugar Cane Straw",
	"133844": "Wooden Baruda",
	"106443": "Wooden Chips",
}

FUEL_ROW_ORDER = [
	"Bagasse-Cane-Mfg",
	"Bagasse-Cane-Mfg (Non Weighment)",
	"Bagasse-Cane-Trd",
	"Bagasse-Cane-Trd (Non Weighment)",
	"Rice Husk",
	"Saw Dust (Burada)",
	"Pulverized Pellets",
	"Crusher Bagasse",
	"Paddy Straw",
	"Biomass Pellets",
	"Pulse Husk",
	"Bio Mass",
	"Mandi Husk",
	"Maize Straw",
	"Sugar Cane Straw",
	"Mustard Husk",
	"Cane Trash",
	"Wooden Baruda",
	"Wooden Chips",
	"Khudi",
	"Paddy Straw (Non Weighment)",
	"Refuse Derived Fuel (RDF Waste)",
	"Mustard Husk ( Non Weighment )",
	"Imported Indonesian Coal (Sale)",
	"Rice Husk (Sale)",
	"Cane Trash - Non Weightment",
]

FUEL_GROUP_MAP = {
	"010104-Bagasse-Mfg":  "Bagasse-Cane-Mfg",
	"010106-Bagasse-Trd":  "Bagasse-Cane-Trd",
	"010107-Bio Mass-Mfg": "Bio Mass",
	"Fuel":                "Bio Mass",
}

RAW_MATERIAL_MAP = {
	"106444": "Maize",
	"106446": "Damaged/Broken Rice",
	"106448": "FCI Surplus Rice",
	"111325": "Grain",
	"111885": "DE Oiled Rice Bran",
	"106977": "Bajra",
	"106981": "Corn Sand",
}

RAW_MATERIAL_ROW_ORDER = [
	"Maize",
	"Damaged/Broken Rice",
	"FCI Surplus Rice",
	"Grain",
	"DE Oiled Rice Bran",
	"Bajra",
	"Corn Sand",
]

GENERAL_STORE_GROUPS = [
	"Auto",
	"Cane",
	"Civil",
	"Consumable",
	"Electrical",
	"Instrument",
	"Mechinical",
	"Packing Material",
	"Scrap",
	"Pesticides",
	"Other Traded Item",
]

GENERAL_STORE_MAP      = {g: g for g in GENERAL_STORE_GROUPS}
GENERAL_STORE_ROW_ORDER = GENERAL_STORE_GROUPS[:]

VALUE_DIVISOR = 100000


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _as_list(value):
	if not value:
		return []
	if isinstance(value, str):
		return frappe.parse_json(value) if value.startswith("[") else [value]
	return list(value)


def convert_qty(item_code, qty, stock_uom):
	stock_uom = (stock_uom or "").strip()
	conversions = frappe.get_all(
		"UOM Conversion Detail",
		filters={"parent": item_code},
		fields=["uom", "conversion_factor"],
		order_by="conversion_factor desc",
		limit=1,
	)
	if not conversions:
		return round(qty, 2), stock_uom
	factor = flt(conversions[0].conversion_factor)
	if factor <= 0:
		return round(qty, 2), stock_uom
	return round(qty / factor, 2), conversions[0].uom


def convert_to_quintal(item_code, qty, stock_uom):
	uom_norm = (stock_uom or "").strip().lower()
	if uom_norm in ("quintal", "qtl"):
		return round(qty, 2), "Quintal"
	if uom_norm in ("kg", "kgs", "kilogram", "kilograms"):
		return round(qty / 100, 2), "Quintal"
	conv = frappe.get_all(
		"UOM Conversion Detail",
		filters={"parent": item_code, "uom": ["like", "%uintal%"]},
		fields=["uom", "conversion_factor"],
		limit=1,
	)
	if conv:
		factor = flt(conv[0].conversion_factor)
		if factor > 0:
			return round(qty / factor, 2), "Quintal"
	return round(qty, 2), stock_uom


def _to_qtl(qty, factor):
	return round(qty / factor, 2) if factor and factor > 0 else round(qty, 2)


# ---------------------------------------------------------------------------
# Core SLE helper  (FIXED)
# ---------------------------------------------------------------------------

def _get_sle_current_value(
	item_codes_clause, item_params,
	as_on_date, company_list, plant_list,
	extra_where="", extra_params=None,
	group_by_item_group=False,
):
	"""
	Returns qty and stock value per (plant, item_code) as-on a given date.

	KEY FIX: uses SUM(sle.stock_value_difference) — the incremental change
	column — so that summing all entries up to the date gives the correct
	running balance.  The old code used SUM(sle.stock_value) which is the
	*running total at the time of each entry*, not the incremental amount,
	causing massive over-counts.
	"""
	extra_params = extra_params or []

	where  = "sle.is_cancelled = 0 AND sle.posting_date <= %s AND " + item_codes_clause
	params = [as_on_date] + list(item_params)

	if company_list:
		where  += " AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list)))
		params += company_list
	if plant_list:
		where  += " AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list)))
		params += plant_list

	if extra_where:
		where  += " " + extra_where
		params += list(extra_params)

	select_extra = "i.item_group," if group_by_item_group else ""
	group_extra  = ", i.item_group" if group_by_item_group else ""

	return frappe.db.sql("""
		SELECT
			wh.custom_branch                AS plant,
			sle.item_code,
			i.item_name,
			i.item_group,
			i.stock_uom,
			{}
			SUM(sle.actual_qty)             AS qty_raw,
			SUM(sle.stock_value_difference) AS value
		FROM `tabStock Ledger Entry` sle
		INNER JOIN `tabItem` i       ON i.name  = sle.item_code
		INNER JOIN `tabWarehouse` wh ON wh.name = sle.warehouse
		WHERE {}
		GROUP BY wh.custom_branch, sle.item_code{}
		HAVING SUM(sle.actual_qty) > 0.009
	""".format(select_extra, where, group_extra), params, as_dict=True)


# ---------------------------------------------------------------------------
# Fuel helpers
# ---------------------------------------------------------------------------

def _label_for_fuel_row(r):
	label = FUEL_MAP.get(r.item_code)
	if label:
		return label
	label = FUEL_GROUP_MAP.get(r.item_group)
	if label:
		return label
	return r.item_name or r.item_code


def _get_fuel_rows(company_list, plant_list, as_on_date=None):
	fuel_codes  = list(FUEL_MAP.keys())
	fuel_groups = list(FUEL_GROUP_MAP.keys())

	if as_on_date:
		# ── Pass 1 : match by item code ────────────────────────────────────
		ph1   = ", ".join(["%s"] * len(fuel_codes))
		rows1 = _get_sle_current_value(
			"sle.item_code IN ({})".format(ph1),
			fuel_codes, as_on_date, company_list, plant_list,
		)
		seen_keys = {(r.plant, r.item_code) for r in rows1}

		# ── Pass 2 : match by item group (FIX: filter on item_group) ───────
		grp_ph    = ", ".join(["%s"] * len(fuel_groups))
		rows2_raw = _get_sle_current_value(
			"i.item_group IN ({})".format(grp_ph),   # was wrongly item_code IN
			fuel_groups, as_on_date, company_list, plant_list,
		)
		rows2 = [r for r in rows2_raw if (r.plant, r.item_code) not in seen_keys]

		for r in rows1: r["match_by"] = "code"
		for r in rows2: r["match_by"] = "group"
		return list(rows1) + list(rows2)

	# ── Bin path (today / no as_on_date) ────────────────────────────────────
	def _build_where_params(base_where, base_params):
		w, p = base_where, base_params[:]
		if company_list:
			w += " AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list)))
			p += company_list
		if plant_list:
			w += " AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list)))
			p += plant_list
		return w, p

	ph1   = ", ".join(["%s"] * len(fuel_codes))
	w1, p1 = _build_where_params(
		"b.actual_qty > 0 AND b.item_code IN ({})".format(ph1),
		fuel_codes,
	)
	rows1 = frappe.db.sql("""
		SELECT
			wh.custom_branch AS plant,
			b.item_code,
			i.item_name,
			i.item_group,
			i.stock_uom,
			b.actual_qty     AS qty_raw,
			b.stock_value    AS value,
			'code'           AS match_by
		FROM `tabBin` b
		INNER JOIN `tabItem` i       ON i.name  = b.item_code
		INNER JOIN `tabWarehouse` wh ON wh.name = b.warehouse
		WHERE {}
	""".format(w1), p1, as_dict=True)

	seen_keys = {(r.plant, r.item_code) for r in rows1}

	grp_ph  = ", ".join(["%s"] * len(fuel_groups))
	w2, p2  = _build_where_params(
		"b.actual_qty > 0 AND i.item_group IN ({})".format(grp_ph),
		fuel_groups,
	)
	rows2_raw = frappe.db.sql("""
		SELECT
			wh.custom_branch AS plant,
			b.item_code,
			i.item_name,
			i.item_group,
			i.stock_uom,
			b.actual_qty     AS qty_raw,
			b.stock_value    AS value,
			'group'          AS match_by
		FROM `tabBin` b
		INNER JOIN `tabItem` i       ON i.name  = b.item_code
		INNER JOIN `tabWarehouse` wh ON wh.name = b.warehouse
		WHERE {}
	""".format(w2), p2, as_dict=True)

	rows2 = [r for r in rows2_raw if (r.plant, r.item_code) not in seen_keys]
	return list(rows1) + list(rows2)


# ---------------------------------------------------------------------------
# Raw-material helpers
# ---------------------------------------------------------------------------

def _fetch_rm_qtl_factors(rm_item_codes):
	if not rm_item_codes:
		return {}

	placeholders = ", ".join(["%s"] * len(rm_item_codes))
	items = frappe.db.sql("""
		SELECT name AS item_code, stock_uom
		FROM `tabItem`
		WHERE name IN ({})
	""".format(placeholders), rm_item_codes, as_dict=True)

	factors   = {}
	need_conv = []
	for it in items:
		uom = (it.stock_uom or "").strip().lower()
		if uom in ("quintal", "qtl"):
			factors[it.item_code] = 1.0
		elif uom in ("kg", "kgs", "kilogram", "kilograms"):
			factors[it.item_code] = 100.0
		else:
			need_conv.append(it.item_code)

	if need_conv:
		conv_ph = ", ".join(["%s"] * len(need_conv))
		conv_rows = frappe.db.sql("""
			SELECT parent AS item_code, MAX(conversion_factor) AS factor
			FROM `tabUOM Conversion Detail`
			WHERE parent IN ({})
			  AND uom LIKE '%uintal%'
			GROUP BY parent
		""".format(conv_ph), need_conv, as_dict=True)

		for c in conv_rows:
			if flt(c.factor) > 0:
				factors[c.item_code] = flt(c.factor)

		for ic in need_conv:
			if ic not in factors:
				factors[ic] = 1.0

	return factors


def _get_rm_monthly_consumption(company_list, plant_list, qtl_factors, as_on_date=None):
	ref_date  = as_on_date or today()
	from_date = add_months(ref_date, -3)

	rm_item_codes = list(RAW_MATERIAL_MAP.keys())
	placeholders  = ", ".join(["%s"] * len(rm_item_codes))

	where  = """
		sle.is_cancelled = 0
		AND sle.posting_date >= %s
		AND sle.posting_date <= %s
		AND sle.voucher_type = 'Stock Entry'
		AND sle.actual_qty < 0
		AND sle.item_code IN ({})
		AND se.stock_entry_type = 'Material Issue'
	""".format(placeholders)
	params = [from_date, ref_date] + rm_item_codes

	if company_list:
		where  += " AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list)))
		params += company_list
	if plant_list:
		where  += " AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list)))
		params += plant_list

	rows = frappe.db.sql("""
		SELECT
			wh.custom_branch            AS plant,
			sle.item_code,
			SUM(ABS(sle.actual_qty))    AS total_issued
		FROM `tabStock Ledger Entry` sle
		INNER JOIN `tabStock Entry` se  ON se.name  = sle.voucher_no
		INNER JOIN `tabWarehouse` wh    ON wh.name  = sle.warehouse
		WHERE {}
		GROUP BY wh.custom_branch, sle.item_code
	""".format(where), params, as_dict=True)

	consumption = {}
	for r in rows:
		factor  = qtl_factors.get(r.item_code, 1.0)
		qty_qtl = _to_qtl(flt(r.total_issued), factor)
		consumption[(r.plant, r.item_code)] = round(qty_qtl / 3, 2)

	return consumption


# ---------------------------------------------------------------------------
# Group finalisation helpers
# ---------------------------------------------------------------------------

def _finalise_groups(row_order, bucket, plants, sort_by_value=True):
	groups = []
	for label in row_order:
		plant_cells = bucket.get(label, {})
		uom = next((c["uom"] for c in plant_cells.values() if c.get("uom")), "")

		qty_row, value_row, avg_row = {}, {}, {}
		total_qty       = 0
		total_value_raw = 0

		for p in plants:
			cell        = plant_cells.get(p, {"qty": 0, "value": 0})
			q           = round(flt(cell["qty"]),   2)
			v_raw       = flt(cell.get("value", 0))
			v_cr        = round(v_raw / VALUE_DIVISOR, 2)
			avg         = round(v_raw / q, 2) if q else 0

			qty_row[p]   = q
			value_row[p] = v_cr
			avg_row[p]   = avg

			total_qty       += q
			total_value_raw += v_raw

		total_value_cr = round(total_value_raw / VALUE_DIVISOR, 2)
		total_avg      = round(total_value_raw / total_qty, 2) if total_qty else 0

		groups.append({
			"label":       label,
			"uom":         uom,
			"qty":         qty_row,
			"value":       value_row,
			"avg":         avg_row,
			"total_qty":   round(total_qty, 2),
			"total_value": total_value_cr,
			"total_avg":   total_avg,
			"_sort_key":   total_value_raw,
		})

	if sort_by_value:
		groups.sort(key=lambda g: (g["_sort_key"] == 0, -g["_sort_key"]))

	for g in groups:
		g.pop("_sort_key", None)

	return groups


def _finalise_rm_groups(row_order, bucket, plants, consumption_map, sort_by_value=True):
	groups = []
	for label in row_order:
		plant_cells = bucket.get(label, {})
		uom = next((c["uom"] for c in plant_cells.values() if c.get("uom")), "")

		qty_row, value_row, avg_row = {}, {}, {}
		monthly_row, days_row = {}, {}
		total_qty       = 0
		total_value_raw = 0
		total_monthly   = 0

		item_code_key = next(
			(k for k, v in RAW_MATERIAL_MAP.items() if v == label),
			None,
		)

		for p in plants:
			cell  = plant_cells.get(p, {"qty": 0, "value": 0})
			q     = round(flt(cell["qty"]), 2)
			v_raw = flt(cell.get("value", 0))
			v_cr  = round(v_raw / VALUE_DIVISOR, 2)
			avg   = round(v_raw / q, 2) if q else 0

			monthly = 0
			if item_code_key:
				monthly = consumption_map.get((p, item_code_key), 0)

			days = round(q / (monthly / 30), 1) if monthly > 0 else 0

			qty_row[p]     = q
			value_row[p]   = v_cr
			avg_row[p]     = avg
			monthly_row[p] = round(monthly, 2)
			days_row[p]    = days

			total_qty       += q
			total_value_raw += v_raw
			total_monthly   += monthly

		total_value_cr = round(total_value_raw / VALUE_DIVISOR, 2)
		total_avg      = round(total_value_raw / total_qty, 2) if total_qty else 0
		total_days     = round(total_qty / (total_monthly / 30), 1) if total_monthly > 0 else 0

		groups.append({
			"label":               label,
			"uom":                 uom,
			"qty":                 qty_row,
			"value":               value_row,
			"avg":                 avg_row,
			"monthly_consumption": monthly_row,
			"days_stock":          days_row,
			"total_qty":           round(total_qty, 2),
			"total_value":         total_value_cr,
			"total_avg":           total_avg,
			"total_monthly":       round(total_monthly, 2),
			"total_days":          total_days,
			"_sort_key":           total_value_raw,
		})

	if sort_by_value:
		groups.sort(key=lambda g: (g["_sort_key"] == 0, -g["_sort_key"]))

	for g in groups:
		g.pop("_sort_key", None)

	return groups


# ---------------------------------------------------------------------------
# Whitelisted API endpoints
# ---------------------------------------------------------------------------

@frappe.whitelist()
def get_collapsed_summary(company=None, plant=None, as_on_date=None):
	company_list = _as_list(company)
	plant_list   = _as_list(plant)

	fg_item_groups = list(FINISHED_GOODS_MAP.keys())
	fg_ph = ", ".join(["%s"] * len(fg_item_groups))

	# ── Finished Goods ───────────────────────────────────────────────────────
	if as_on_date:
		# FIX: use i.item_group IN (...) directly — no subquery, no doubled param
		fg_data = _get_sle_current_value(
			"i.item_group IN ({})".format(fg_ph),
			fg_item_groups,
			as_on_date, company_list, plant_list,
			group_by_item_group=True,
		)
	else:
		fg_data = frappe.db.sql("""
			SELECT
				wh.custom_branch AS plant,
				i.item_group,
				SUM(b.stock_value) AS value
			FROM `tabBin` b
			INNER JOIN `tabItem` i       ON i.name  = b.item_code
			INNER JOIN `tabWarehouse` wh ON wh.name = b.warehouse
			WHERE b.actual_qty > 0
			  AND i.item_group IN ({fg_ph})
			  {comp} {plant_f}
			GROUP BY wh.custom_branch, i.item_group
		""".format(
			fg_ph=fg_ph,
			comp=" AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list))) if company_list else "",
			plant_f=" AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list))) if plant_list else "",
		), fg_item_groups + company_list + plant_list, as_dict=True)

	# ── Fuel ─────────────────────────────────────────────────────────────────
	fuel_rows        = _get_fuel_rows(company_list, plant_list, as_on_date)
	fuel_by_plant_raw = {}
	for r in fuel_rows:
		fuel_by_plant_raw[r.plant] = fuel_by_plant_raw.get(r.plant, 0) + flt(r.value)

	# ── Raw Material ─────────────────────────────────────────────────────────
	rm_item_codes = list(RAW_MATERIAL_MAP.keys())
	rm_ph = ", ".join(["%s"] * len(rm_item_codes))

	if as_on_date:
		rm_data = _get_sle_current_value(
			"sle.item_code IN ({})".format(rm_ph),
			rm_item_codes,
			as_on_date, company_list, plant_list,
		)
	else:
		rm_data = frappe.db.sql("""
			SELECT wh.custom_branch AS plant, SUM(b.stock_value) AS value
			FROM `tabBin` b
			INNER JOIN `tabItem` i       ON i.name  = b.item_code
			INNER JOIN `tabWarehouse` wh ON wh.name = b.warehouse
			WHERE b.actual_qty > 0
			  AND b.item_code IN ({rm_ph})
			  {comp} {plant_f}
			GROUP BY wh.custom_branch
		""".format(
			rm_ph=rm_ph,
			comp=" AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list))) if company_list else "",
			plant_f=" AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list))) if plant_list else "",
		), rm_item_codes + company_list + plant_list, as_dict=True)

	rm_by_plant_raw = {d.plant: flt(d.value) for d in rm_data if d.plant}

	# ── General Store ────────────────────────────────────────────────────────
	gs_ph           = ", ".join(["%s"] * len(GENERAL_STORE_GROUPS))
	gs_group_params = GENERAL_STORE_GROUPS[:] + GENERAL_STORE_GROUPS[:]
	comp_clause     = " AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list))) if company_list else ""
	plant_clause    = " AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list))) if plant_list else ""

	if as_on_date:
		gs_data = frappe.db.sql("""
			SELECT
				wh.custom_branch                AS plant,
				SUM(sle.stock_value_difference) AS value
			FROM `tabStock Ledger Entry` sle
			INNER JOIN `tabItem` i        ON i.name  = sle.item_code
			INNER JOIN `tabItem Group` ig ON ig.name = i.item_group
			INNER JOIN `tabWarehouse` wh  ON wh.name = sle.warehouse
			WHERE sle.is_cancelled = 0
			  AND sle.posting_date <= %s
			  AND (i.item_group IN ({ph}) OR ig.parent_item_group IN ({ph}))
			  {comp} {plant_f}
			GROUP BY wh.custom_branch
			HAVING SUM(sle.actual_qty) > 0.009
		""".format(ph=gs_ph, comp=comp_clause, plant_f=plant_clause),
		[as_on_date] + gs_group_params + company_list + plant_list, as_dict=True)
	else:
		gs_data = frappe.db.sql("""
			SELECT wh.custom_branch AS plant, SUM(b.stock_value) AS value
			FROM `tabBin` b
			INNER JOIN `tabItem` i        ON i.name  = b.item_code
			INNER JOIN `tabItem Group` ig ON ig.name = i.item_group
			INNER JOIN `tabWarehouse` wh  ON wh.name = b.warehouse
			WHERE b.actual_qty > 0
			  AND (i.item_group IN ({ph}) OR ig.parent_item_group IN ({ph}))
			  {comp} {plant_f}
			GROUP BY wh.custom_branch
		""".format(ph=gs_ph, comp=comp_clause, plant_f=plant_clause),
		gs_group_params + company_list + plant_list, as_dict=True)

	gs_by_plant_raw = {d.plant: flt(d.value) for d in gs_data if d.plant}

	# ── Collect all plants ───────────────────────────────────────────────────
	plants = sorted(
		{d.plant for d in fg_data if d.plant}
		| set(fuel_by_plant_raw)
		| set(rm_by_plant_raw)
		| set(gs_by_plant_raw)
	)

	fg_by_plant   = {p: 0.0 for p in plants}
	fuel_by_plant = {p: 0.0 for p in plants}
	rm_by_plant   = {p: 0.0 for p in plants}
	gs_by_plant   = {p: 0.0 for p in plants}

	for d in fg_data:
		if d.plant and d.item_group in FINISHED_GOODS_MAP:
			fg_by_plant[d.plant] += flt(d.value)

	for p, v in fuel_by_plant_raw.items():
		if p in fuel_by_plant:
			fuel_by_plant[p] = v

	for p, v in rm_by_plant_raw.items():
		if p in rm_by_plant:
			rm_by_plant[p] = v

	for p, v in gs_by_plant_raw.items():
		if p in gs_by_plant:
			gs_by_plant[p] = v

	master_rows = []
	for label in ["Finished Goods", "Fuel", "Raw Material", "General Store"]:
		row = {"label": label}
		for p in plants:
			if   label == "Finished Goods": row[p] = round(fg_by_plant[p]   / VALUE_DIVISOR, 2)
			elif label == "Fuel":           row[p] = round(fuel_by_plant[p] / VALUE_DIVISOR, 2)
			elif label == "Raw Material":   row[p] = round(rm_by_plant[p]   / VALUE_DIVISOR, 2)
			elif label == "General Store":  row[p] = round(gs_by_plant[p]   / VALUE_DIVISOR, 2)
		master_rows.append(row)

	total_row = {"label": "Total"}
	for p in plants:
		total_row[p] = round(sum(r[p] for r in master_rows), 2)

	return {"plants": plants, "rows": master_rows, "total": total_row}


@frappe.whitelist()
def get_finished_goods_detail(company=None, plant=None, as_on_date=None):
	company_list = _as_list(company)
	plant_list   = _as_list(plant)

	fg_item_groups = list(FINISHED_GOODS_MAP.keys())
	placeholders   = ", ".join(["%s"] * len(fg_item_groups))

	if as_on_date:
		rows = _get_sle_current_value(
			"i.item_group IN ({})".format(placeholders),
			fg_item_groups,
			as_on_date, company_list, plant_list,
		)
	else:
		rows = frappe.db.sql("""
			SELECT
				wh.custom_branch AS plant,
				i.name           AS item_code,
				i.item_group,
				i.stock_uom,
				b.actual_qty     AS qty_raw,
				b.stock_value    AS value
			FROM `tabBin` b
			INNER JOIN `tabItem` i       ON i.name  = b.item_code
			INNER JOIN `tabWarehouse` wh ON wh.name = b.warehouse
			WHERE b.actual_qty > 0
			  AND i.item_group IN ({ph})
			  {comp} {plant_f}
		""".format(
			ph=placeholders,
			comp=" AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list))) if company_list else "",
			plant_f=" AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list))) if plant_list else "",
		), fg_item_groups + company_list + plant_list, as_dict=True)

	plants = sorted({r.plant for r in rows if r.plant})
	bucket = {label: {} for label in FINISHED_GOODS_ROW_ORDER}

	for r in rows:
		label = FINISHED_GOODS_MAP.get(r.item_group)
		if not label:
			continue
		qty_conv, uom_conv = convert_qty(r.item_code, flt(r.qty_raw), r.stock_uom)
		cell = bucket[label].setdefault(r.plant, {"qty": 0, "value": 0, "uom": uom_conv})
		cell["qty"]   += qty_conv
		cell["value"] += flt(r.value)
		cell["uom"]    = uom_conv

	groups = _finalise_groups(FINISHED_GOODS_ROW_ORDER, bucket, plants)
	return {"plants": plants, "groups": groups}


@frappe.whitelist()
def get_fuel_detail(company=None, plant=None, as_on_date=None):
	company_list = _as_list(company)
	plant_list   = _as_list(plant)

	rows   = _get_fuel_rows(company_list, plant_list, as_on_date)
	plants = sorted({r.plant for r in rows if r.plant})

	extra_labels = []
	for r in rows:
		lbl = _label_for_fuel_row(r)
		if lbl and lbl not in FUEL_ROW_ORDER and lbl not in extra_labels:
			extra_labels.append(lbl)

	effective_order = FUEL_ROW_ORDER + extra_labels
	bucket = {label: {} for label in effective_order}

	for r in rows:
		label = _label_for_fuel_row(r)
		if not label:
			continue
		qty_conv, uom_conv = convert_to_quintal(r.item_code, flt(r.qty_raw), r.stock_uom)
		cell = bucket.setdefault(label, {}).setdefault(
			r.plant, {"qty": 0, "value": 0, "uom": uom_conv}
		)
		cell["qty"]   += qty_conv
		cell["value"] += flt(r.value)
		cell["uom"]    = uom_conv

	groups = _finalise_groups(effective_order, bucket, plants)
	return {"plants": plants, "groups": groups}


@frappe.whitelist()
def get_raw_material_detail(company=None, plant=None, as_on_date=None):
	company_list = _as_list(company)
	plant_list   = _as_list(plant)

	rm_item_codes = list(RAW_MATERIAL_MAP.keys())
	placeholders  = ", ".join(["%s"] * len(rm_item_codes))

	if as_on_date:
		rows = _get_sle_current_value(
			"sle.item_code IN ({})".format(placeholders),
			rm_item_codes,
			as_on_date, company_list, plant_list,
		)
	else:
		rows = frappe.db.sql("""
			SELECT
				wh.custom_branch AS plant,
				i.name           AS item_code,
				i.item_group,
				i.stock_uom,
				b.actual_qty     AS qty_raw,
				b.stock_value    AS value
			FROM `tabBin` b
			INNER JOIN `tabItem` i       ON i.name  = b.item_code
			INNER JOIN `tabWarehouse` wh ON wh.name = b.warehouse
			WHERE b.actual_qty > 0
			  AND b.item_code IN ({ph})
			  {comp} {plant_f}
		""".format(
			ph=placeholders,
			comp=" AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list))) if company_list else "",
			plant_f=" AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list))) if plant_list else "",
		), rm_item_codes + company_list + plant_list, as_dict=True)

	plants       = sorted({r.plant for r in rows if r.plant})
	bucket       = {label: {} for label in RAW_MATERIAL_ROW_ORDER}
	qtl_factors  = _fetch_rm_qtl_factors(rm_item_codes)

	for r in rows:
		label = RAW_MATERIAL_MAP.get(r.item_code)
		if not label:
			continue
		factor   = qtl_factors.get(r.item_code, 1.0)
		qty_conv = _to_qtl(flt(r.qty_raw), factor)
		cell = bucket[label].setdefault(r.plant, {"qty": 0, "value": 0, "uom": "Quintal"})
		cell["qty"]   += qty_conv
		cell["value"] += flt(r.value)
		cell["uom"]    = "Quintal"

	consumption_map = _get_rm_monthly_consumption(company_list, plant_list, qtl_factors, as_on_date)
	groups = _finalise_rm_groups(RAW_MATERIAL_ROW_ORDER, bucket, plants, consumption_map)
	return {"plants": plants, "groups": groups}


@frappe.whitelist()
def get_general_store_detail(company=None, plant=None, as_on_date=None):
	company_list = _as_list(company)
	plant_list   = _as_list(plant)

	gs_ph           = ", ".join(["%s"] * len(GENERAL_STORE_GROUPS))
	gs_group_params = GENERAL_STORE_GROUPS[:] + GENERAL_STORE_GROUPS[:]
	comp_clause     = " AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list))) if company_list else ""
	plant_clause    = " AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list))) if plant_list else ""

	if as_on_date:
		rows = frappe.db.sql("""
			SELECT
				wh.custom_branch               AS plant,
				i.name                         AS item_code,
				i.item_group,
				ig.parent_item_group,
				i.stock_uom,
				SUM(sle.actual_qty)             AS qty_raw,
				SUM(sle.stock_value_difference) AS value
			FROM `tabStock Ledger Entry` sle
			INNER JOIN `tabItem` i        ON i.name  = sle.item_code
			INNER JOIN `tabItem Group` ig ON ig.name = i.item_group
			INNER JOIN `tabWarehouse` wh  ON wh.name = sle.warehouse
			WHERE sle.is_cancelled = 0
			  AND sle.posting_date <= %s
			  AND (i.item_group IN ({ph}) OR ig.parent_item_group IN ({ph}))
			  {comp} {plant_f}
			GROUP BY wh.custom_branch, i.name
			HAVING SUM(sle.actual_qty) > 0.009
		""".format(ph=gs_ph, comp=comp_clause, plant_f=plant_clause),
		[as_on_date] + gs_group_params + company_list + plant_list, as_dict=True)
	else:
		rows = frappe.db.sql("""
			SELECT
				wh.custom_branch AS plant,
				i.name           AS item_code,
				i.item_group,
				ig.parent_item_group,
				i.stock_uom,
				b.actual_qty     AS qty_raw,
				b.stock_value    AS value
			FROM `tabBin` b
			INNER JOIN `tabItem` i        ON i.name  = b.item_code
			INNER JOIN `tabItem Group` ig ON ig.name = i.item_group
			INNER JOIN `tabWarehouse` wh  ON wh.name = b.warehouse
			WHERE b.actual_qty > 0
			  AND (i.item_group IN ({ph}) OR ig.parent_item_group IN ({ph}))
			  {comp} {plant_f}
		""".format(ph=gs_ph, comp=comp_clause, plant_f=plant_clause),
		gs_group_params + company_list + plant_list, as_dict=True)

	plants      = sorted({r.plant for r in rows if r.plant})
	bucket      = {label: {} for label in GENERAL_STORE_ROW_ORDER}
	gs_group_set = set(GENERAL_STORE_GROUPS)

	for r in rows:
		if r.item_group in gs_group_set:
			label = r.item_group
		elif (r.parent_item_group or "") in gs_group_set:
			label = r.parent_item_group
		else:
			continue

		cell = bucket[label].setdefault(r.plant, {"qty": 0, "value": 0, "uom": ""})
		cell["qty"]   += round(flt(r.qty_raw), 2)
		cell["value"] += flt(r.value)

	groups = _finalise_groups(GENERAL_STORE_ROW_ORDER, bucket, plants)
	return {"plants": plants, "groups": groups}


# ---------------------------------------------------------------------------
# Debug helper (unchanged)
# ---------------------------------------------------------------------------

@frappe.whitelist()
def debug_fuel_items(company=None, plant=None):
	company_list = _as_list(company)
	plant_list   = _as_list(plant)

	where  = "b.actual_qty > 0"
	params = []

	if company_list:
		where  += " AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list)))
		params += company_list
	if plant_list:
		where  += " AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list)))
		params += plant_list

	rows = frappe.db.sql("""
		SELECT DISTINCT
			b.item_code,
			i.item_name,
			i.item_group,
			wh.custom_branch AS plant,
			b.actual_qty,
			b.stock_value
		FROM `tabBin` b
		INNER JOIN `tabItem` i       ON i.name  = b.item_code
		INNER JOIN `tabWarehouse` wh ON wh.name = b.warehouse
		WHERE {}
		ORDER BY b.stock_value DESC
		LIMIT 200
	""".format(where), params, as_dict=True)

	fuel_map_keys   = set(FUEL_MAP.keys())
	fuel_group_keys = set(FUEL_GROUP_MAP.keys())

	matched_by_code  = [r for r in rows if r.item_code  in fuel_map_keys]
	matched_by_group = [r for r in rows if r.item_group in fuel_group_keys]
	unmatched        = [
		r for r in rows
		if r.item_code  not in fuel_map_keys
		and r.item_group not in fuel_group_keys
	]

	return {
		"matched_by_item_code":   matched_by_code,
		"matched_by_item_group":  matched_by_group,
		"unmatched_sample":       unmatched[:30],
		"fuel_map_keys":          sorted(fuel_map_keys),
		"fuel_group_map_keys":    sorted(fuel_group_keys),
		"total_bin_rows_scanned": len(rows),
	}