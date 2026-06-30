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
	"135009": "Bagasse-Cane-Mfg (Non Weighment)",
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

GENERAL_STORE_MAP       = {g: g for g in GENERAL_STORE_GROUPS}
GENERAL_STORE_ROW_ORDER = GENERAL_STORE_GROUPS[:]

VALUE_DIVISOR = 100000

_FG_ITEM_GROUPS     = set(FINISHED_GOODS_MAP.keys())
_FUEL_ITEM_CODES    = set(FUEL_MAP.keys())
_FUEL_ITEM_GROUPS   = set(FUEL_GROUP_MAP.keys())
_RM_ITEM_CODES      = set(RAW_MATERIAL_MAP.keys())
_GS_ITEM_GROUPS     = set(GENERAL_STORE_GROUPS)

_ALL_FUEL_CODES     = list(_FUEL_ITEM_CODES)
_ALL_FUEL_GROUPS    = list(_FUEL_ITEM_GROUPS)
_ALL_RM_CODES       = list(_RM_ITEM_CODES)
_ALL_FG_GROUPS      = list(_FG_ITEM_GROUPS)
_ALL_GS_GROUPS      = list(_GS_ITEM_GROUPS)


def _wh_exclude_clause(alias="wh"):
	clause = (
		" AND {a}.disabled = 0"
		" AND {a}.name NOT LIKE %s"
	).format(a=alias)
	return clause, ["%Return%Rejection%"]


def _get_rana_plants():
	if not hasattr(frappe.local, "_ripl_rana_plants"):
		frappe.local._ripl_rana_plants = set(
			frappe.get_all(
				"Branch",
				filters={"company": ["like", "%Rana Sugars Ltd%"]},
				pluck="name",
			)
		)
	return frappe.local._ripl_rana_plants


def _sort_plants(plant_iterable):
	rana = _get_rana_plants()
	return sorted(plant_iterable, key=lambda p: (0 if p in rana else 1, p.lower()))


def _as_list(value):
	if not value:
		return []
	if isinstance(value, str):
		return frappe.parse_json(value) if value.startswith("[") else [value]
	return list(value)


def _format_item_codes(codes):
	codes = sorted({c for c in codes if c})
	if not codes:
		return ""
	if len(codes) <= 3:
		return ", ".join(codes)
	return ", ".join(codes[:3]) + " +{} more".format(len(codes) - 3)


def _batch_uom_conversions(item_codes):
	if not item_codes:
		return {}

	unique = list(set(item_codes))
	ph     = ", ".join(["%s"] * len(unique))

	rows = frappe.db.sql("""
		SELECT parent AS item_code, uom, MAX(conversion_factor) AS factor
		FROM `tabUOM Conversion Detail`
		WHERE parent IN ({})
		GROUP BY parent, uom
		ORDER BY parent, factor DESC
	""".format(ph), unique, as_dict=True)

	result = {}
	for r in rows:
		if r.item_code not in result:
			result[r.item_code] = (flt(r.factor), r.uom)
	return result


def _apply_uom(item_code, qty_raw, stock_uom, conv_map):
	factor, uom_out = conv_map.get(item_code, (0, ""))
	if factor and factor > 0:
		return round(qty_raw / factor, 2), uom_out
	return round(qty_raw, 2), stock_uom or ""


def convert_qty(item_code, qty, stock_uom):
	conv_map = _batch_uom_conversions([item_code])
	return _apply_uom(item_code, qty, stock_uom, conv_map)


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


def _get_sle_current_value(
	item_codes_clause, item_params,
	as_on_date, company_list, plant_list,
	extra_where="", extra_params=None,
	group_by_item_group=False,
):
	extra_params = extra_params or []

	where  = "sle.is_cancelled = 0 AND sle.posting_date <= %s AND " + item_codes_clause
	params = [as_on_date] + list(item_params)

	if company_list:
		where  += " AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list)))
		params += company_list
	if plant_list:
		where  += " AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list)))
		params += plant_list

	wh_clause, wh_params = _wh_exclude_clause("wh")
	where  += wh_clause
	params += wh_params

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
		INNER JOIN `tabBin` b        ON b.warehouse = sle.warehouse AND b.item_code = sle.item_code AND b.actual_qty > 0
		WHERE {}
		GROUP BY wh.custom_branch, sle.item_code{}
		HAVING SUM(sle.actual_qty) > 0
	""".format(select_extra, where, group_extra), params, as_dict=True)


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
		ph1   = ", ".join(["%s"] * len(fuel_codes))
		rows1 = _get_sle_current_value(
			"sle.item_code IN ({})".format(ph1),
			fuel_codes, as_on_date, company_list, plant_list,
		)
		seen_keys = {(r.plant, r.item_code) for r in rows1}

		grp_ph    = ", ".join(["%s"] * len(fuel_groups))
		rows2_raw = _get_sle_current_value(
			"i.item_group IN ({})".format(grp_ph),
			fuel_groups, as_on_date, company_list, plant_list,
		)
		rows2 = [r for r in rows2_raw if (r.plant, r.item_code) not in seen_keys]

		for r in rows1: r["match_by"] = "code"
		for r in rows2: r["match_by"] = "group"
		return list(rows1) + list(rows2)

	def _build_where_params(base_where, base_params):
		w, p = base_where, base_params[:]
		if company_list:
			w += " AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list)))
			p += company_list
		if plant_list:
			w += " AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list)))
			p += plant_list
		wh_clause, wh_params = _wh_exclude_clause("wh")
		w += wh_clause
		p += wh_params
		return w, p

	ph1    = ", ".join(["%s"] * len(fuel_codes))
	w1, p1 = _build_where_params(
		"b.actual_qty > 0 AND b.item_code IN ({})".format(ph1), fuel_codes,
	)
	grp_ph  = ", ".join(["%s"] * len(fuel_groups))
	w2, p2  = _build_where_params(
		"b.actual_qty > 0 AND i.item_group IN ({})".format(grp_ph), fuel_groups,
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
			  AND uom LIKE '%%uintal%%'
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

	wh_clause, wh_params = _wh_exclude_clause("wh")
	where  += wh_clause
	params += wh_params

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
		if not r.plant:
			continue
		factor  = qtl_factors.get(r.item_code, 1.0)
		qty_qtl = _to_qtl(flt(r.total_issued), factor)
		consumption[(r.plant, r.item_code)] = round(qty_qtl / 3, 2)

	return consumption


def _finalise_groups(row_order, bucket, plants, sort_by_value=True, item_code_map=None):
	item_code_map = item_code_map or {}
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
			"item_code":   item_code_map.get(label, ""),
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
			"item_code":           item_code_key or "",
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


def _get_rm_value_by_plant(company_list, plant_list, as_on_date=None):
	rm_item_codes = list(RAW_MATERIAL_MAP.keys())
	placeholders  = ", ".join(["%s"] * len(rm_item_codes))

	if as_on_date:
		rows = _get_sle_current_value(
			"sle.item_code IN ({})".format(placeholders),
			rm_item_codes,
			as_on_date, company_list, plant_list,
		)
	else:
		comp_clause  = " AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list))) if company_list else ""
		plant_clause = " AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list))) if plant_list else ""
		wh_clause, wh_params = _wh_exclude_clause("wh")

		rows = frappe.db.sql("""
			SELECT
				wh.custom_branch AS plant,
				i.name           AS item_code,
				i.stock_uom,
				b.actual_qty     AS qty_raw,
				b.stock_value    AS value
			FROM `tabBin` b
			INNER JOIN `tabItem` i       ON i.name  = b.item_code
			INNER JOIN `tabWarehouse` wh ON wh.name = b.warehouse
			WHERE b.actual_qty > 0
				AND b.item_code IN ({ph})
				{comp} {plant_f} {wh_excl}
		""".format(
			ph=placeholders,
			comp=comp_clause,
			plant_f=plant_clause,
			wh_excl=wh_clause,
		), rm_item_codes + company_list + plant_list + wh_params, as_dict=True)

	rm_by_plant_raw = {}
	for r in rows:
		if not r.plant:
			continue
		if r.item_code not in RAW_MATERIAL_MAP:
			continue
		rm_by_plant_raw[r.plant] = rm_by_plant_raw.get(r.plant, 0.0) + flt(r.value)

	return rm_by_plant_raw


@frappe.whitelist()
def get_collapsed_summary(company=None, plant=None, as_on_date=None):
	company_list = _as_list(company)
	plant_list   = _as_list(plant)

	fg_item_groups = list(FINISHED_GOODS_MAP.keys())
	fg_ph = ", ".join(["%s"] * len(fg_item_groups))

	if as_on_date:
		fg_data = _get_sle_current_value(
			"i.item_group IN ({})".format(fg_ph),
			fg_item_groups,
			as_on_date, company_list, plant_list,
			group_by_item_group=True,
		)
	else:
		wh_clause, wh_params = _wh_exclude_clause("wh")
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
				{comp} {plant_f} {wh_excl}
		""".format(
			fg_ph=fg_ph,
			comp=" AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list))) if company_list else "",
			plant_f=" AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list))) if plant_list else "",
			wh_excl=wh_clause,
		), fg_item_groups + company_list + plant_list + wh_params, as_dict=True)

	fuel_rows         = _get_fuel_rows(company_list, plant_list, as_on_date)
	fuel_by_plant_raw = {}
	for r in fuel_rows:
		if not r.plant:
			continue
		fuel_by_plant_raw[r.plant] = fuel_by_plant_raw.get(r.plant, 0) + flt(r.value)

	rm_by_plant_raw = _get_rm_value_by_plant(company_list, plant_list, as_on_date)

	gs_ph           = ", ".join(["%s"] * len(GENERAL_STORE_GROUPS))
	gs_group_params = GENERAL_STORE_GROUPS[:] + GENERAL_STORE_GROUPS[:]
	comp_clause     = " AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list))) if company_list else ""
	plant_clause    = " AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list))) if plant_list else ""
	wh_clause, wh_params = _wh_exclude_clause("wh")

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
				{comp} {plant_f} {wh_excl}
			GROUP BY wh.custom_branch
			HAVING SUM(sle.actual_qty) > 0
		""".format(ph=gs_ph, comp=comp_clause, plant_f=plant_clause, wh_excl=wh_clause),
		[as_on_date] + gs_group_params + company_list + plant_list + wh_params, as_dict=True)
	else:
		gs_data = frappe.db.sql("""
			SELECT wh.custom_branch AS plant, SUM(b.stock_value) AS value
			FROM `tabBin` b
			INNER JOIN `tabItem` i        ON i.name  = b.item_code
			INNER JOIN `tabItem Group` ig ON ig.name = i.item_group
			INNER JOIN `tabWarehouse` wh  ON wh.name = b.warehouse
			WHERE b.actual_qty > 0
				AND (i.item_group IN ({ph}) OR ig.parent_item_group IN ({ph}))
				{comp} {plant_f} {wh_excl}
		""".format(ph=gs_ph, comp=comp_clause, plant_f=plant_clause, wh_excl=wh_clause),
		gs_group_params + company_list + plant_list + wh_params, as_dict=True)

	gs_by_plant_raw = {}
	for d in gs_data:
		if d.plant:
			gs_by_plant_raw[d.plant] = gs_by_plant_raw.get(d.plant, 0.0) + flt(d.value)

	all_plants = (
		{d.plant for d in fg_data if d.plant}
		| set(fuel_by_plant_raw)
		| set(rm_by_plant_raw)
		| set(gs_by_plant_raw)
	)
	plants = _sort_plants(all_plants)

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
		wh_clause, wh_params = _wh_exclude_clause("wh")
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
				{comp} {plant_f} {wh_excl}
		""".format(
			ph=placeholders,
			comp=" AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list))) if company_list else "",
			plant_f=" AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list))) if plant_list else "",
			wh_excl=wh_clause,
		), fg_item_groups + company_list + plant_list + wh_params, as_dict=True)

	plants = _sort_plants({r.plant for r in rows if r.plant})
	bucket = {label: {} for label in FINISHED_GOODS_ROW_ORDER}

	unique_codes = list({r.item_code for r in rows})
	conv_map     = _batch_uom_conversions(unique_codes)

	for r in rows:
		label = FINISHED_GOODS_MAP.get(r.item_group)
		if not label:
			continue
		qty_conv, uom_conv = _apply_uom(r.item_code, flt(r.qty_raw), r.stock_uom, conv_map)
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
    plants = _sort_plants({r.plant for r in rows if r.plant})

    extra_labels = []
    for r in rows:
        lbl = _label_for_fuel_row(r)
        if lbl and lbl not in FUEL_ROW_ORDER and lbl not in extra_labels:
            extra_labels.append(lbl)

    effective_order = FUEL_ROW_ORDER + extra_labels
    bucket = {label: {} for label in effective_order}

    # ── Pre-populate item_code_map from static FUEL_MAP so that even
    #    zero-stock rows show their item code(s).
    static_item_code_map = {}
    for code, label in FUEL_MAP.items():
        static_item_code_map.setdefault(label, set()).add(code)

    label_item_codes = {}   # overrides from live rows (same codes, but keeps the pattern)

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
        label_item_codes.setdefault(label, set()).add(r.item_code)

    # Merge: live codes take priority; fall back to static map for zero-stock rows
    merged_item_code_map = {}
    for label in effective_order:
        codes = label_item_codes.get(label) or static_item_code_map.get(label) or set()
        merged_item_code_map[label] = _format_item_codes(codes)

    groups = _finalise_groups(effective_order, bucket, plants, item_code_map=merged_item_code_map)
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
		wh_clause, wh_params = _wh_exclude_clause("wh")
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
				{comp} {plant_f} {wh_excl}
		""".format(
			ph=placeholders,
			comp=" AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list))) if company_list else "",
			plant_f=" AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list))) if plant_list else "",
			wh_excl=wh_clause,
		), rm_item_codes + company_list + plant_list + wh_params, as_dict=True)

	plants      = _sort_plants({r.plant for r in rows if r.plant})
	bucket      = {label: {} for label in RAW_MATERIAL_ROW_ORDER}
	qtl_factors = _fetch_rm_qtl_factors(rm_item_codes)

	for r in rows:
		if not r.plant:
			continue
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
	wh_clause, wh_params = _wh_exclude_clause("wh")

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
				{comp} {plant_f} {wh_excl}
			GROUP BY wh.custom_branch, i.name
			HAVING SUM(sle.actual_qty) > 0
		""".format(ph=gs_ph, comp=comp_clause, plant_f=plant_clause, wh_excl=wh_clause),
		[as_on_date] + gs_group_params + company_list + plant_list + wh_params, as_dict=True)
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
				{comp} {plant_f} {wh_excl}
		""".format(ph=gs_ph, comp=comp_clause, plant_f=plant_clause, wh_excl=wh_clause),
		gs_group_params + company_list + plant_list + wh_params, as_dict=True)

	plants      = _sort_plants({r.plant for r in rows if r.plant})
	bucket      = {label: {} for label in GENERAL_STORE_ROW_ORDER}
	gs_group_set = set(GENERAL_STORE_GROUPS)

	for r in rows:
		if not r.plant:
			continue
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


@frappe.whitelist()
def get_finished_goods_item_detail(company=None, plant=None, as_on_date=None, label=None):
	if not label:
		frappe.throw("label is required")

	company_list = _as_list(company)
	plant_list   = _as_list(plant)

	item_groups  = [k for k, v in FINISHED_GOODS_MAP.items() if v == label]
	if not item_groups:
		return {"plants": [], "items": [], "total": {}, "uom": ""}

	placeholders = ", ".join(["%s"] * len(item_groups))

	if as_on_date:
		rows = _get_sle_current_value(
			"i.item_group IN ({})".format(placeholders),
			item_groups,
			as_on_date, company_list, plant_list,
		)
	else:
		wh_clause, wh_params = _wh_exclude_clause("wh")
		rows = frappe.db.sql("""
			SELECT
				wh.custom_branch AS plant,
				i.name           AS item_code,
				i.item_name,
				i.item_group,
				i.stock_uom,
				b.actual_qty     AS qty_raw,
				b.stock_value    AS value
			FROM `tabBin` b
			INNER JOIN `tabItem` i       ON i.name  = b.item_code
			INNER JOIN `tabWarehouse` wh ON wh.name = b.warehouse
			WHERE b.actual_qty > 0
				AND i.item_group IN ({ph})
				{comp} {plant_f} {wh_excl}
		""".format(
			ph=placeholders,
			comp=" AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list))) if company_list else "",
			plant_f=" AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list))) if plant_list else "",
			wh_excl=wh_clause,
		), item_groups + company_list + plant_list + wh_params, as_dict=True)

	plants = _sort_plants({r.plant for r in rows if r.plant})

	unique_codes = list({r.item_code for r in rows})
	conv_map     = _batch_uom_conversions(unique_codes)

	item_bucket = {}
	for r in rows:
		if not r.plant:
			continue
		qty_conv, uom_conv = _apply_uom(r.item_code, flt(r.qty_raw), r.stock_uom, conv_map)
		entry = item_bucket.setdefault(r.item_code, {
			"item_name": r.item_name,
			"uom":       uom_conv,
			"plants":    {},
		})
		cell = entry["plants"].setdefault(r.plant, {"qty": 0, "value": 0})
		cell["qty"]   += qty_conv
		cell["value"] += flt(r.value)
		if uom_conv:
			entry["uom"] = uom_conv

	items = []
	uom_overall = ""
	grand = {p: {"qty": 0.0, "value": 0.0} for p in plants}

	for item_code, data in item_bucket.items():
		qty_row, value_row, avg_row = {}, {}, {}
		total_qty       = 0
		total_value_raw = 0

		for p in plants:
			cell  = data["plants"].get(p, {"qty": 0, "value": 0})
			q     = round(flt(cell["qty"]), 2)
			v_raw = flt(cell.get("value", 0))
			v_cr  = round(v_raw / VALUE_DIVISOR, 2)
			avg   = round(v_raw / q, 2) if q else 0

			qty_row[p]   = q
			value_row[p] = v_cr
			avg_row[p]   = avg

			total_qty       += q
			total_value_raw += v_raw

			grand[p]["qty"]   += q
			grand[p]["value"] += v_raw

		total_value_cr = round(total_value_raw / VALUE_DIVISOR, 2)
		total_avg      = round(total_value_raw / total_qty, 2) if total_qty else 0

		if data["uom"]:
			uom_overall = data["uom"]

		items.append({
			"item_code":   item_code,
			"item_name":   data["item_name"],
			"qty":         qty_row,
			"value":       value_row,
			"avg":         avg_row,
			"total_qty":   round(total_qty, 2),
			"total_value": total_value_cr,
			"total_avg":   total_avg,
			"_sort_key":   total_value_raw,
		})

	items.sort(key=lambda it: (it["_sort_key"] == 0, -it["_sort_key"]))
	for it in items:
		it.pop("_sort_key", None)

	total_qty_row, total_value_row, total_avg_row = {}, {}, {}
	grand_qty       = 0
	grand_value_raw = 0

	for p in plants:
		q     = round(flt(grand[p]["qty"]), 2)
		v_raw = flt(grand[p]["value"])
		v_cr  = round(v_raw / VALUE_DIVISOR, 2)
		avg   = round(v_raw / q, 2) if q else 0

		total_qty_row[p]   = q
		total_value_row[p] = v_cr
		total_avg_row[p]   = avg

		grand_qty       += q
		grand_value_raw += v_raw

	grand_value_cr = round(grand_value_raw / VALUE_DIVISOR, 2)
	grand_avg      = round(grand_value_raw / grand_qty, 2) if grand_qty else 0

	total = {
		"qty":         total_qty_row,
		"value":       total_value_row,
		"avg":         total_avg_row,
		"total_qty":   round(grand_qty, 2),
		"total_value": grand_value_cr,
		"total_avg":   grand_avg,
	}

	return {"plants": plants, "items": items, "total": total, "uom": uom_overall}


@frappe.whitelist()
def get_general_store_item_detail(company=None, plant=None, as_on_date=None, label=None):
	if not label:
		frappe.throw("label is required")
	if label not in GENERAL_STORE_GROUPS:
		return {"plants": [], "items": [], "total": {}}

	company_list = _as_list(company)
	plant_list   = _as_list(plant)

	comp_clause  = " AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list))) if company_list else ""
	plant_clause = " AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list))) if plant_list else ""
	wh_clause, wh_params = _wh_exclude_clause("wh")

	if as_on_date:
		rows = frappe.db.sql("""
			SELECT
				wh.custom_branch                AS plant,
				i.name                          AS item_code,
				i.item_name,
				i.item_group,
				ig.parent_item_group,
				SUM(sle.stock_value_difference) AS value
			FROM `tabStock Ledger Entry` sle
			INNER JOIN `tabItem` i        ON i.name  = sle.item_code
			INNER JOIN `tabItem Group` ig ON ig.name = i.item_group
			INNER JOIN `tabWarehouse` wh  ON wh.name = sle.warehouse
			WHERE sle.is_cancelled = 0
				AND sle.posting_date <= %s
				AND (i.item_group = %s OR ig.parent_item_group = %s)
				{comp} {plant_f} {wh_excl}
			GROUP BY wh.custom_branch, i.name
			HAVING SUM(sle.actual_qty) > 0
		""".format(comp=comp_clause, plant_f=plant_clause, wh_excl=wh_clause),
		[as_on_date, label, label] + company_list + plant_list + wh_params, as_dict=True)
	else:
		rows = frappe.db.sql("""
			SELECT
				wh.custom_branch AS plant,
				i.name           AS item_code,
				i.item_name,
				i.item_group,
				ig.parent_item_group,
				b.stock_value    AS value
			FROM `tabBin` b
			INNER JOIN `tabItem` i        ON i.name  = b.item_code
			INNER JOIN `tabItem Group` ig ON ig.name = i.item_group
			INNER JOIN `tabWarehouse` wh  ON wh.name = b.warehouse
			WHERE b.actual_qty > 0
				AND (i.item_group = %s OR ig.parent_item_group = %s)
				{comp} {plant_f} {wh_excl}
		""".format(comp=comp_clause, plant_f=plant_clause, wh_excl=wh_clause),
		[label, label] + company_list + plant_list + wh_params, as_dict=True)

	plants = _sort_plants({r.plant for r in rows if r.plant})

	item_bucket = {}
	for r in rows:
		if not r.plant:
			continue
		entry = item_bucket.setdefault(r.item_code, {"item_name": r.item_name, "plants": {}})
		entry["plants"][r.plant] = entry["plants"].get(r.plant, 0.0) + flt(r.value)

	items = []
	grand = {p: 0.0 for p in plants}

	for item_code, data in item_bucket.items():
		value_row = {}
		total_value_raw = 0

		for p in plants:
			v_raw = flt(data["plants"].get(p, 0))
			value_row[p] = round(v_raw / VALUE_DIVISOR, 2)
			total_value_raw += v_raw
			grand[p] += v_raw

		items.append({
			"item_code":   item_code,
			"item_name":   data["item_name"],
			"value":       value_row,
			"total_value": round(total_value_raw / VALUE_DIVISOR, 2),
			"_sort_key":   total_value_raw,
		})

	items.sort(key=lambda it: (it["_sort_key"] == 0, -it["_sort_key"]))
	for it in items:
		it.pop("_sort_key", None)

	grand_total_raw = sum(grand.values())
	total = {
		"value":       {p: round(v / VALUE_DIVISOR, 2) for p, v in grand.items()},
		"total_value": round(grand_total_raw / VALUE_DIVISOR, 2),
	}

	return {"plants": plants, "items": items, "total": total}


def _build_ih_item_filter(item_group):
	if item_group == "Finished Goods":
		fg_groups = list(FINISHED_GOODS_MAP.keys())
		ph = ", ".join(["%s"] * len(fg_groups))
		return "i.item_group IN ({})".format(ph), fg_groups

	elif item_group == "Fuel":
		fuel_codes    = list(FUEL_MAP.keys())
		fuel_grp_keys = list(FUEL_GROUP_MAP.keys())
		ph_c = ", ".join(["%s"] * len(fuel_codes))
		ph_g = ", ".join(["%s"] * len(fuel_grp_keys))
		clause = "(sle.item_code IN ({pc}) OR (i.item_group IN ({pg}) AND sle.item_code NOT IN ({pc})))".format(
			pc=ph_c, pg=ph_g
		)
		return clause, fuel_codes + fuel_grp_keys + fuel_codes

	elif item_group == "Raw Material":
		rm_codes = list(RAW_MATERIAL_MAP.keys())
		ph = ", ".join(["%s"] * len(rm_codes))
		return "sle.item_code IN ({})".format(ph), rm_codes

	elif item_group == "General Store":
		gs = GENERAL_STORE_GROUPS[:]
		ph = ", ".join(["%s"] * len(gs))
		clause = "(i.item_group IN ({ph}) OR IFNULL(ig.parent_item_group,'') IN ({ph}))".format(ph=ph)
		return clause, gs + gs

	else:
		fg_groups     = list(FINISHED_GOODS_MAP.keys())
		fuel_codes    = list(FUEL_MAP.keys())
		fuel_grp_keys = list(FUEL_GROUP_MAP.keys())
		rm_codes      = list(RAW_MATERIAL_MAP.keys())
		gs            = GENERAL_STORE_GROUPS[:]

		fg_ph     = ", ".join(["%s"] * len(fg_groups))
		fuel_ph   = ", ".join(["%s"] * len(fuel_codes))
		fuel_g_ph = ", ".join(["%s"] * len(fuel_grp_keys))
		rm_ph     = ", ".join(["%s"] * len(rm_codes))
		gs_ph     = ", ".join(["%s"] * len(gs))

		clause = """(
			i.item_group IN ({fg_ph})
			OR sle.item_code IN ({fuel_ph})
			OR (i.item_group IN ({fuel_g_ph}) AND sle.item_code NOT IN ({fuel_ph}))
			OR sle.item_code IN ({rm_ph})
			OR i.item_group IN ({gs_ph})
			OR IFNULL(ig.parent_item_group,'') IN ({gs_ph})
		)""".format(
			fg_ph=fg_ph, fuel_ph=fuel_ph, fuel_g_ph=fuel_g_ph,
			rm_ph=rm_ph, gs_ph=gs_ph,
		)
		params = (
			fg_groups
			+ fuel_codes
			+ fuel_grp_keys + fuel_codes
			+ rm_codes
			+ gs + gs
		)
		return clause, params


def _build_ih_bin_filter(item_group):
	if item_group == "Finished Goods":
		fg_groups = list(FINISHED_GOODS_MAP.keys())
		ph = ", ".join(["%s"] * len(fg_groups))
		return "i.item_group IN ({})".format(ph), fg_groups

	elif item_group == "Fuel":
		fuel_codes    = list(FUEL_MAP.keys())
		fuel_grp_keys = list(FUEL_GROUP_MAP.keys())
		ph_c = ", ".join(["%s"] * len(fuel_codes))
		ph_g = ", ".join(["%s"] * len(fuel_grp_keys))
		clause = "(b.item_code IN ({pc}) OR (i.item_group IN ({pg}) AND b.item_code NOT IN ({pc})))".format(
			pc=ph_c, pg=ph_g
		)
		return clause, fuel_codes + fuel_grp_keys + fuel_codes

	elif item_group == "Raw Material":
		rm_codes = list(RAW_MATERIAL_MAP.keys())
		ph = ", ".join(["%s"] * len(rm_codes))
		return "b.item_code IN ({})".format(ph), rm_codes

	elif item_group == "General Store":
		gs = GENERAL_STORE_GROUPS[:]
		ph = ", ".join(["%s"] * len(gs))
		clause = "(i.item_group IN ({ph}) OR IFNULL(ig.parent_item_group,'') IN ({ph}))".format(ph=ph)
		return clause, gs + gs

	else:
		fg_groups     = list(FINISHED_GOODS_MAP.keys())
		fuel_codes    = list(FUEL_MAP.keys())
		fuel_grp_keys = list(FUEL_GROUP_MAP.keys())
		rm_codes      = list(RAW_MATERIAL_MAP.keys())
		gs            = GENERAL_STORE_GROUPS[:]

		fg_ph     = ", ".join(["%s"] * len(fg_groups))
		fuel_ph   = ", ".join(["%s"] * len(fuel_codes))
		fuel_g_ph = ", ".join(["%s"] * len(fuel_grp_keys))
		rm_ph     = ", ".join(["%s"] * len(rm_codes))
		gs_ph     = ", ".join(["%s"] * len(gs))

		clause = """(
			i.item_group IN ({fg_ph})
			OR b.item_code IN ({fuel_ph})
			OR (i.item_group IN ({fuel_g_ph}) AND b.item_code NOT IN ({fuel_ph}))
			OR b.item_code IN ({rm_ph})
			OR i.item_group IN ({gs_ph})
			OR IFNULL(ig.parent_item_group,'') IN ({gs_ph})
		)""".format(
			fg_ph=fg_ph, fuel_ph=fuel_ph, fuel_g_ph=fuel_g_ph,
			rm_ph=rm_ph, gs_ph=gs_ph,
		)
		params = (
			fg_groups
			+ fuel_codes
			+ fuel_grp_keys + fuel_codes
			+ rm_codes
			+ gs + gs
		)
		return clause, params


@frappe.whitelist()
def get_inventory_health(company=None, plant=None, as_on_date=None, item_group=None):
	company_list = _as_list(company)
	plant_list   = _as_list(plant)
	item_group   = item_group or None
	ref_date     = as_on_date or today()
	use_bin      = not as_on_date
	ref          = frappe.utils.getdate(ref_date)

	comp_clause  = " AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list))) if company_list else ""
	plant_clause = " AND wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list))) if plant_list else ""
	wh_clause, wh_params = _wh_exclude_clause("wh")

	if use_bin:
		bin_clause, bin_params = _build_ih_bin_filter(item_group)

		stock_rows = frappe.db.sql("""
			SELECT
				wh.custom_branch AS plant,
				b.item_code,
				b.stock_value
			FROM `tabBin` b
			INNER JOIN `tabItem` i        ON i.name  = b.item_code
			LEFT  JOIN `tabItem Group` ig ON ig.name = i.item_group
			INNER JOIN `tabWarehouse` wh  ON wh.name = b.warehouse
			WHERE b.actual_qty > 0
			  AND {item_f} {comp} {plant_f} {wh_excl}
		""".format(item_f=bin_clause, comp=comp_clause, plant_f=plant_clause, wh_excl=wh_clause),
		bin_params + company_list + plant_list + wh_params, as_dict=True)

		if not stock_rows:
			return {"plants": [], "rows": []}

		bin_item_codes = list({r.item_code for r in stock_rows if r.plant})
		ic_ph = ", ".join(["%s"] * len(bin_item_codes))

		lm_rows = frappe.db.sql("""
			SELECT
				wh.custom_branch      AS plant,
				sle.item_code,
				MAX(sle.posting_date) AS last_movement_date
			FROM `tabStock Ledger Entry` sle
			INNER JOIN `tabWarehouse` wh ON wh.name = sle.warehouse
			WHERE sle.is_cancelled = 0
			  AND sle.item_code IN ({ic_ph})
			  {comp} {plant_f} {wh_excl}
			GROUP BY wh.custom_branch, sle.item_code
		""".format(ic_ph=ic_ph, comp=comp_clause, plant_f=plant_clause, wh_excl=wh_clause),
		bin_item_codes + company_list + plant_list + wh_params, as_dict=True)

		last_movement = {(r.plant, r.item_code): r.last_movement_date for r in lm_rows}

		plant_data = {}
		for r in stock_rows:
			if not r.plant:
				continue
			val = flt(r.stock_value)
			if val <= 0:
				continue

			p = r.plant
			if p not in plant_data:
				plant_data[p] = {"total": 0.0, "slow": 0.0, "non_moving": 0.0, "dead": 0.0}

			lm_date    = last_movement.get((p, r.item_code))
			last_date  = frappe.utils.getdate(lm_date) if lm_date else None
			days_since = (ref - last_date).days if last_date else 9999

			plant_data[p]["total"] += val
			if 90 <= days_since <= 180:
				plant_data[p]["slow"]       += val
			elif 180 < days_since <= 365:
				plant_data[p]["non_moving"] += val
			elif days_since > 365:
				plant_data[p]["dead"]       += val

	else:
		sle_clause, sle_params = _build_ih_item_filter(item_group)

		where_parts = ["sle.is_cancelled = 0", "sle.posting_date <= %s"]
		params      = [ref_date]

		if company_list:
			where_parts.append("wh.company IN ({})".format(", ".join(["%s"] * len(company_list))))
			params.extend(company_list)
		if plant_list:
			where_parts.append("wh.custom_branch IN ({})".format(", ".join(["%s"] * len(plant_list))))
			params.extend(plant_list)

		where_parts.append(sle_clause)
		params.extend(sle_params)

		where_sql = " AND ".join(where_parts) + wh_clause
		params    = params + wh_params

		sle_rows = frappe.db.sql("""
			SELECT
				wh.custom_branch                AS plant,
				sle.item_code,
				SUM(sle.stock_value_difference) AS stock_value,
				MAX(sle.posting_date)           AS last_movement_date
			FROM `tabStock Ledger Entry` sle
			INNER JOIN `tabItem` i        ON i.name  = sle.item_code
			LEFT  JOIN `tabItem Group` ig ON ig.name = i.item_group
			INNER JOIN `tabWarehouse` wh  ON wh.name = sle.warehouse
			WHERE {where}
			GROUP BY wh.custom_branch, sle.item_code
			HAVING SUM(sle.actual_qty) > 0
		""".format(where=where_sql), params, as_dict=True)

		plant_data = {}
		for r in sle_rows:
			if not r.plant:
				continue
			val = flt(r.stock_value)
			if val <= 0:
				continue

			p = r.plant
			if p not in plant_data:
				plant_data[p] = {"total": 0.0, "slow": 0.0, "non_moving": 0.0, "dead": 0.0}

			last_date  = frappe.utils.getdate(r.last_movement_date) if r.last_movement_date else None
			days_since = (ref - last_date).days if last_date else 9999

			plant_data[p]["total"] += val
			if 90 <= days_since <= 180:
				plant_data[p]["slow"]       += val
			elif 180 < days_since <= 365:
				plant_data[p]["non_moving"] += val
			elif days_since > 365:
				plant_data[p]["dead"]       += val

	plants = _sort_plants(set(plant_data.keys()))

	result_rows = []
	for p in plants:
		d = plant_data[p]
		result_rows.append({
			"plant":       p,
			"total_value": round(d["total"]      / VALUE_DIVISOR, 2),
			"slow_moving": round(d["slow"]       / VALUE_DIVISOR, 2),
			"non_moving":  round(d["non_moving"] / VALUE_DIVISOR, 2),
			"dead_stock":  round(d["dead"]       / VALUE_DIVISOR, 2),
		})

	return {"plants": plants, "rows": result_rows}


@frappe.whitelist()
def get_inventory_health_item_detail(
	company=None, plant=None, as_on_date=None,
	item_group=None, target_plant=None,
):
	if not target_plant:
		frappe.throw("target_plant is required")

	company_list = _as_list(company)
	item_group   = item_group or None
	ref_date     = as_on_date or today()
	use_bin      = not as_on_date
	ref          = frappe.utils.getdate(ref_date)

	comp_clause = " AND wh.company IN ({})".format(", ".join(["%s"] * len(company_list))) if company_list else ""
	wh_clause, wh_params = _wh_exclude_clause("wh")

	def _bucket_for(days_since):
		if days_since is None:
			return "fresh"
		if 90 <= days_since <= 180:
			return "slow"
		if 180 < days_since <= 365:
			return "non_moving"
		if days_since > 365:
			return "dead"
		return "fresh"

	items = []

	if use_bin:
		bin_clause, bin_params = _build_ih_bin_filter(item_group)

		params = bin_params + company_list + [target_plant] + wh_params
		rows = frappe.db.sql("""
			SELECT
				b.item_code,
				i.item_name,
				i.stock_uom,
				b.actual_qty  AS qty_raw,
				b.stock_value AS stock_value
			FROM `tabBin` b
			INNER JOIN `tabItem` i        ON i.name  = b.item_code
			LEFT  JOIN `tabItem Group` ig ON ig.name = i.item_group
			INNER JOIN `tabWarehouse` wh  ON wh.name = b.warehouse
			WHERE b.actual_qty > 0
			  AND {item_f} {comp} AND wh.custom_branch = %s {wh_excl}
		""".format(item_f=bin_clause, comp=comp_clause, wh_excl=wh_clause), params, as_dict=True)

		item_codes = list({r.item_code for r in rows})
		last_movement = {}
		if item_codes:
			ic_ph = ", ".join(["%s"] * len(item_codes))
			lm_params = item_codes + company_list + [target_plant] + wh_params
			lm_rows = frappe.db.sql("""
				SELECT sle.item_code, MAX(sle.posting_date) AS last_movement_date
				FROM `tabStock Ledger Entry` sle
				INNER JOIN `tabWarehouse` wh ON wh.name = sle.warehouse
				WHERE sle.is_cancelled = 0
				  AND sle.item_code IN ({ic_ph})
				  {comp} AND wh.custom_branch = %s {wh_excl}
				GROUP BY sle.item_code
			""".format(ic_ph=ic_ph, comp=comp_clause, wh_excl=wh_clause), lm_params, as_dict=True)
			last_movement = {r.item_code: r.last_movement_date for r in lm_rows}

		for r in rows:
			val = flt(r.stock_value)
			if val <= 0:
				continue
			lm_date    = last_movement.get(r.item_code)
			last_date  = frappe.utils.getdate(lm_date) if lm_date else None
			days_since = (ref - last_date).days if last_date else None

			items.append({
				"item_code":           r.item_code,
				"item_name":           r.item_name,
				"uom":                 r.stock_uom or "",
				"qty":                 round(flt(r.qty_raw), 2),
				"value":               round(val / VALUE_DIVISOR, 2),
				"days_since_movement": days_since,
				"bucket":              _bucket_for(days_since),
			})

	else:
		sle_clause, sle_params = _build_ih_item_filter(item_group)

		where_parts = [
			"sle.is_cancelled = 0",
			"sle.posting_date <= %s",
			"wh.custom_branch = %s",
		]
		params = [ref_date, target_plant]

		if company_list:
			where_parts.append("wh.company IN ({})".format(", ".join(["%s"] * len(company_list))))
			params.extend(company_list)

		where_parts.append(sle_clause)
		params.extend(sle_params)

		where_sql = " AND ".join(where_parts) + wh_clause
		params    = params + wh_params

		rows = frappe.db.sql("""
			SELECT
				sle.item_code,
				i.item_name,
				i.stock_uom,
				SUM(sle.actual_qty)             AS qty_raw,
				SUM(sle.stock_value_difference) AS stock_value,
				MAX(sle.posting_date)           AS last_movement_date
			FROM `tabStock Ledger Entry` sle
			INNER JOIN `tabItem` i        ON i.name  = sle.item_code
			LEFT  JOIN `tabItem Group` ig ON ig.name = i.item_group
			INNER JOIN `tabWarehouse` wh  ON wh.name = sle.warehouse
			WHERE {where}
			GROUP BY sle.item_code
			HAVING SUM(sle.actual_qty) > 0
		""".format(where=where_sql), params, as_dict=True)

		for r in rows:
			val = flt(r.stock_value)
			if val <= 0:
				continue
			last_date  = frappe.utils.getdate(r.last_movement_date) if r.last_movement_date else None
			days_since = (ref - last_date).days if last_date else None

			items.append({
				"item_code":           r.item_code,
				"item_name":           r.item_name,
				"uom":                 r.stock_uom or "",
				"qty":                 round(flt(r.qty_raw), 2),
				"value":               round(val / VALUE_DIVISOR, 2),
				"days_since_movement": days_since,
				"bucket":              _bucket_for(days_since),
			})

	items.sort(key=lambda it: -it["value"])

	bucket_totals = {"fresh": 0.0, "slow": 0.0, "non_moving": 0.0, "dead": 0.0}
	total_value   = 0.0
	for it in items:
		bucket_totals[it["bucket"]] += it["value"]
		total_value += it["value"]

	return {
		"plant":         target_plant,
		"items":         items,
		"total_value":   round(total_value, 2),
		"bucket_totals": {k: round(v, 2) for k, v in bucket_totals.items()},
	}


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

	wh_clause, wh_params = _wh_exclude_clause("wh")
	where  += wh_clause
	params += wh_params

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