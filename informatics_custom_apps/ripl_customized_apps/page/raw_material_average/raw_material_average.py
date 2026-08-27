import frappe
from frappe.utils import getdate, add_days, add_months, flt, get_first_day, get_last_day
from erpnext.stock.get_item_details import get_conversion_factor

PLANT_FIELD = "branch"
HISTORY_MONTHS = 6
PRICE_UOM = "Quintal"

RICE_ITEM_CODE = "106446"

RAW_MATERIALS = [
	{"item_code": "106444", "label": "Maize (106444)", "uom": "Quintal"},
	{"item_code": RICE_ITEM_CODE, "label": "Rice (106446)", "uom": "Quintal"},
	{"item_code": "106448", "label": "FCI (106448)", "uom": "Quintal"},
]


def _conversion_cache():
	if not hasattr(frappe.local, "rm_uom_conversion_cache"):
		frappe.local.rm_uom_conversion_cache = {}
	return frappe.local.rm_uom_conversion_cache


def get_valid_target_uom(item_code, static_uom):
	if not item_code:
		return static_uom
	cache = _conversion_cache()
	key = ("valid_uom", item_code, static_uom)
	if key in cache:
		return cache[key]
	stock_uom = frappe.get_cached_value("Item", item_code, "stock_uom")
	if not stock_uom:
		cache[key] = static_uom
		return static_uom
	if not static_uom or static_uom == stock_uom:
		cache[key] = stock_uom
		return stock_uom
	has_conversion = frappe.db.exists("UOM Conversion Detail", {"parent": item_code, "uom": static_uom})
	result = static_uom if has_conversion else stock_uom
	cache[key] = result
	return result


def get_stock_to_target_factor(item_code, target_uom):
	cache = _conversion_cache()
	key = ("factor", item_code, target_uom)
	if key in cache:
		return cache[key]
	stock_uom = frappe.get_cached_value("Item", item_code, "stock_uom")
	if not stock_uom:
		cache[key] = 1
		return 1
	effective_uom = get_valid_target_uom(item_code, target_uom)
	if effective_uom == stock_uom:
		cache[key] = 1
		return 1
	factor = (get_conversion_factor(item_code, effective_uom) or {}).get("conversion_factor") or 1
	result = 1 / factor if factor else 1
	cache[key] = result
	return result


def convert_qty(item_code, qty, static_uom):
	return qty * get_stock_to_target_factor(item_code, static_uom)


def convert_price_to_quintal(item_code, price_per_stock_uom):
	if not price_per_stock_uom:
		return 0
	factor = get_stock_to_target_factor(item_code, PRICE_UOM)
	return price_per_stock_uom / factor if factor else price_per_stock_uom


def get_plant_options(company=None):
	if frappe.db.has_column("Branch", "company"):
		filters = {"company": company} if company else {}
		return frappe.get_all("Branch", filters=filters, pluck="name", order_by="name")
	if not frappe.db.has_column("Stock Entry", PLANT_FIELD):
		return []
	condition = "and company = %(company)s" if company else ""
	plants = frappe.db.sql(f"""
		select distinct {PLANT_FIELD} as plant from `tabStock Entry`
		where {PLANT_FIELD} is not null and {PLANT_FIELD} != '' {condition}
		order by {PLANT_FIELD}
	""", {"company": company} if company else {}, as_dict=1)
	return [p.plant for p in plants]


def get_issued_qty_by_plant(company, from_date, to_date, item_codes, plants=None):
	if not item_codes:
		return {}
	from_dt = f"{getdate(from_date)} 09:00:00"
	to_dt = f"{add_days(getdate(to_date), 1)} 09:00:00"

	conditions = [
		"se.docstatus = 1",
		"se.stock_entry_type = 'Material Issue'",
		"timestamp(se.posting_date, se.posting_time) >= %(from_dt)s",
		"timestamp(se.posting_date, se.posting_time) < %(to_dt)s",
		"sed.item_code in %(items)s",
	]
	values = {"from_dt": from_dt, "to_dt": to_dt, "items": item_codes}
	if company:
		conditions.append("se.company = %(company)s")
		values["company"] = company
	if plants and None not in plants:
		conditions.append(f"se.{PLANT_FIELD} in %(plants)s")
		values["plants"] = plants

	rows = frappe.db.sql(f"""
		select sed.item_code, se.{PLANT_FIELD} as plant, sum(sed.qty * sed.conversion_factor) as qty
		from `tabStock Entry` se
		inner join `tabStock Entry Detail` sed on se.name = sed.parent
		where {" and ".join(conditions)}
		group by sed.item_code, se.{PLANT_FIELD}
	""", values, as_dict=1)
	return {(r.item_code, r.plant): r.qty or 0 for r in rows}


def _fetch_avg_purchase_prices(item_codes, start, end, plant=None, group_by_plant=False):
	if not item_codes:
		return {}
	has_branch = frappe.db.has_column("Warehouse", "custom_branch")
	values = {"items": item_codes, "start": start, "end": end}
	plant_select, group_sql, plant_sql = "", "", ""

	if group_by_plant and has_branch:
		plant_select = ", w.custom_branch as plant"
		group_sql = ", custom_branch"
	elif plant and has_branch:
		plant_sql = " and w.custom_branch = %(plant)s"
		values["plant"] = plant

	rows = frappe.db.sql(f"""
		select pri.item_code{plant_select}, sum(pri.amount) as amount, sum(pri.qty * pri.conversion_factor) as qty
		from `tabPurchase Receipt Item` pri
		inner join `tabPurchase Receipt` pr on pr.name = pri.parent
		inner join `tabWarehouse` w on w.name = pri.warehouse
		where pri.item_code in %(items)s and pr.docstatus = 1
			and pr.posting_date between %(start)s and %(end)s
			{plant_sql}
		group by pri.item_code{group_sql}
	""", values, as_dict=True)

	result = {}
	for r in rows:
		price_per_stock_uom = (r.amount / r.qty) if r.qty else 0
		price = convert_price_to_quintal(r.item_code, price_per_stock_uom)
		key = (r.item_code, r.plant) if group_by_plant else r.item_code
		result[key] = price
	return result


def get_closing_qty_by_plant(item_codes, as_on_date, plants=None):
	if not item_codes:
		return {}
	has_branch = frappe.db.has_column("Warehouse", "custom_branch")
	values = {"items": item_codes, "as_on_date": as_on_date}
	plant_filter_sql = ""

	if plants and None not in plants and has_branch:
		plant_filter_sql = " and w.custom_branch in %(plants)s"
		values["plants"] = plants

	if has_branch:
		rows = frappe.db.sql(f"""
			select t.item_code, t.plant, t.qty from (
				select sle.item_code, w.custom_branch as plant, sle.qty_after_transaction as qty,
					row_number() over (
						partition by sle.item_code, w.custom_branch
						order by sle.posting_date desc, sle.posting_time desc, sle.creation desc
					) as rn
				from `tabStock Ledger Entry` sle
				inner join `tabWarehouse` w on w.name = sle.warehouse
				where sle.item_code in %(items)s
					and sle.posting_date <= %(as_on_date)s
					and sle.is_cancelled = 0
					{plant_filter_sql}
			) t
			where t.rn = 1
		""", values, as_dict=True)
		return {(r.item_code, r.plant): r.qty or 0 for r in rows}

	rows = frappe.db.sql("""
		select t.item_code, t.qty from (
			select sle.item_code, sle.qty_after_transaction as qty,
				row_number() over (
					partition by sle.item_code
					order by sle.posting_date desc, sle.posting_time desc, sle.creation desc
				) as rn
			from `tabStock Ledger Entry` sle
			where sle.item_code in %(items)s
				and sle.posting_date <= %(as_on_date)s
				and sle.is_cancelled = 0
		) t
		where t.rn = 1
	""", values, as_dict=True)
	return {(r.item_code, None): r.qty or 0 for r in rows}


@frappe.whitelist()
def get_filter_options(company=None):
	return {
		"companies": frappe.get_all("Company", pluck="name", order_by="name"),
		"plants": get_plant_options(company),
		"materials": RAW_MATERIALS,
	}


@frappe.whitelist()
def get_report_data(company=None, to_date=None, plant=None):
	frappe.local.rm_uom_conversion_cache = {}

	to_date = getdate(to_date or frappe.utils.nowdate())
	current_period_start = get_first_day(to_date)
	current_period_end = to_date

	plants = [plant] if plant else (get_plant_options(company) or [None])
	item_codes = [m["item_code"] for m in RAW_MATERIALS]

	last_month_ref = add_months(current_period_start, -1)
	last_month_start, last_month_end = get_first_day(last_month_ref), get_last_day(last_month_ref)

	history_ranges = []
	for i in range(HISTORY_MONTHS, 0, -1):
		m_ref = add_months(current_period_start, -i)
		history_ranges.append((get_first_day(m_ref), get_last_day(m_ref)))
	months_labels = [d[0].strftime("%b-%y") for d in history_ranges] + [current_period_start.strftime("%b-%y")]

	trend_series = {item_code: [] for item_code in item_codes}
	for s, e in history_ranges + [(current_period_start, current_period_end)]:
		prices = _fetch_avg_purchase_prices(item_codes, s, e, plant=plant)
		for item_code in item_codes:
			trend_series[item_code].append(round(flt(prices.get(item_code, 0)), 2))

	last_month_prices_bulk = _fetch_avg_purchase_prices(
		item_codes, last_month_start, last_month_end, group_by_plant=True
	)
	current_prices_bulk = _fetch_avg_purchase_prices(
		item_codes, current_period_start, current_period_end, group_by_plant=True
	)
	current_issued_bulk = get_issued_qty_by_plant(
		company, current_period_start, current_period_end, item_codes, plants
	)
	history_issued_bulk = [
		get_issued_qty_by_plant(company, s, e, item_codes, plants) for s, e in history_ranges
	]
	closing_qty_bulk = get_closing_qty_by_plant(item_codes, last_month_end, plants)

	days_elapsed = max((current_period_end - current_period_start).days + 1, 1)

	summary_rows = []
	for p in plants:
		for material in RAW_MATERIALS:
			item_code, label, static_uom = material["item_code"], material["label"], material["uom"]
			display_uom = get_valid_target_uom(item_code, static_uom)

			carrying_qty = convert_qty(item_code, closing_qty_bulk.get((item_code, p), 0), static_uom)
			last_month_price = last_month_prices_bulk.get((item_code, p), 0)

			cur_consumption = convert_qty(item_code, current_issued_bulk.get((item_code, p), 0), static_uom)
			cur_price = current_prices_bulk.get((item_code, p), 0) or last_month_price

			avg_daily_consumption = (cur_consumption / days_elapsed) if cur_consumption else 0
			days_covered = round(carrying_qty / avg_daily_consumption, 1) if avg_daily_consumption else None

			past_consumptions = [
				convert_qty(item_code, h.get((item_code, p), 0), static_uom) for h in history_issued_bulk
			]
			avg_past_consumption = (sum(past_consumptions) / len(past_consumptions)) if past_consumptions else 0
			pct_of_past_consumption = round((cur_consumption / avg_past_consumption) * 100, 1) if avg_past_consumption else None

			if not any([carrying_qty, last_month_price, cur_consumption, cur_price]):
				continue

			summary_rows.append({
				"plant": p or "—",
				"item_code": item_code,
				"label": label,
				"uom": display_uom,
				"price_uom": PRICE_UOM,
				"last_month_carrying_qty": round(flt(carrying_qty), 2),
				"last_month_purchase_price": round(flt(last_month_price), 2),
				"current_month_days_covered": days_covered,
				"current_month_consumption": round(flt(cur_consumption), 2),
				"current_month_consumption_price": round(flt(cur_price), 2),
				"pct_of_past_consumption": pct_of_past_consumption,
			})

	plant_price_comparison = {item_code: [] for item_code in item_codes}
	for p in plants:
		for item_code in item_codes:
			price = current_prices_bulk.get((item_code, p), 0)
			if price:
				plant_price_comparison[item_code].append({"plant": p or "—", "avg_price": round(flt(price), 2)})
	for item_code in item_codes:
		plant_price_comparison[item_code].sort(key=lambda r: r["avg_price"], reverse=True)

	return {
		"months": months_labels,
		"summary_rows": summary_rows,
		"trend": {"months": months_labels, "series": trend_series},
		"plant_price_comparison": plant_price_comparison,
		"materials": RAW_MATERIALS,
		"price_uom": PRICE_UOM,
	}