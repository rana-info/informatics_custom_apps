import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, nowdate

from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_dimensions
from erpnext.accounts.report.accounts_receivable.accounts_receivable import (
	ReceivablePayableReport,
)


PAYABLE_VOUCHER_TYPES = ("Purchase Invoice",)
PAYMENT_REQUEST_TYPE = "Outward"
CHUNK_SIZE = 5000
EPSILON = 0.005


def execute(filters=None):
	args = {
		"account_type": "Payable",
		"naming_by": ["Buying Settings", "supp_master_name"],
	}
	return PaymentRequisitionReport(filters).run(args)


def as_list(val):
	if not val:
		return []
	if isinstance(val, str):
		try:
			val = frappe.parse_json(val)
		except Exception:
			val = [v.strip() for v in val.split(",") if v.strip()]
	return list(val) if isinstance(val, (list, tuple)) else [val]


def _chunks(seq, size=CHUNK_SIZE):
	for i in range(0, len(seq), size):
		yield seq[i : i + size]


def get_po_map(voucher_nos):
	po_map = {}
	for chunk in _chunks(list(set(voucher_nos))):
		for d in frappe.db.sql(
			"""
			select distinct parent, purchase_order
			from `tabPurchase Invoice Item`
			where parent in %(n)s and ifnull(purchase_order, '') != ''
			""",
			{"n": chunk},
			as_dict=True,
		):
			lst = po_map.setdefault(d.parent, [])
			if d.purchase_order not in lst:
				lst.append(d.purchase_order)
	return po_map


class PaymentRequisitionReport(ReceivablePayableReport):
	def __init__(self, filters=None):
		filters = frappe._dict(filters or {})
		filters.report_date = filters.get("as_on_date") or nowdate()
		filters.ageing_based_on = "Due Date"
		filters.calculate_ageing_with = "Report Date"
		filters.range = "30, 60, 90, 120"
		super().__init__(filters)

	def prepare_conditions(self):
		super().prepare_conditions()
		ple = self.ple

		accounts = as_list(self.filters.get("payable_accounts"))
		if accounts:
			self.qb_selection_filter.append(ple.account.isin(accounts))
		suppliers = as_list(self.filters.get("supplier"))
		if suppliers:
			self.qb_selection_filter.append(ple.party.isin(suppliers))

		self.qb_selection_filter.append(ple.against_voucher_type.isin(PAYABLE_VOUCHER_TYPES))

		if getdate(self.filters.report_date) >= getdate(nowdate()):
			pi = frappe.qb.DocType("Purchase Invoice")
			open_pi = (
				frappe.qb.from_(pi)
				.select(pi.name)
				.where(pi.docstatus == 1)
				.where(pi.outstanding_amount > 0)
			)
			if self.filters.get("company"):
				open_pi = open_pi.where(pi.company == self.filters.company)
			self.qb_selection_filter.append(ple.against_voucher_no.isin(open_pi))


		plants = as_list(self.filters.get("plant"))
		segments = as_list(self.filters.get("segment"))
		if plants or segments:
			gle = frappe.qb.DocType("GL Entry")
			q = (
				frappe.qb.from_(gle)
				.select(gle.voucher_no)
				.where(gle.is_cancelled == 0)
				.where(gle.voucher_type.isin(PAYABLE_VOUCHER_TYPES))
				.where(gle.party != "")
			)
			if plants:
				q = q.where(gle.branch.isin(plants))
			if segments:
				q = q.where(gle.segment.isin(segments))
			self.qb_selection_filter.append(ple.against_voucher_no.isin(q))

	def run(self, args):
		self.filters.update(args)
		self.set_defaults()
		self.party_naming_by = frappe.db.get_value(args["naming_by"][0], None, args["naming_by"][1])
		self.get_data()
		self.data = self.build_requisition_rows()
		return self.get_pr_columns(), self.data, None, None, None, 1

	def get_voucher_dimensions(self, rows):
		vouchers = list({r.voucher_no for r in rows})
		dims = {}
		for chunk in _chunks(vouchers):
			for d in frappe.db.sql(
				"""
				select voucher_no, account, party,
					max(branch) as branch, max(segment) as segment
				from `tabGL Entry`
				where is_cancelled = 0
					and voucher_type in %(types)s
					and ifnull(party, '') != ''
					and voucher_no in %(vouchers)s
				group by voucher_no, account, party
				""",
				{"vouchers": chunk, "types": PAYABLE_VOUCHER_TYPES},
				as_dict=True,
			):
				dims[(d.voucher_no, d.account, d.party)] = d
		return dims

	def build_requisition_rows(self):
		plants = set(as_list(self.filters.get("plant")))
		segments = set(as_list(self.filters.get("segment")))
		suppliers = set(as_list(self.filters.get("supplier")))
		as_on = getdate(self.filters.report_date)
		precision = self.currency_precision

		candidates = []
		for r in self.data:
			if r.get("voucher_type") not in PAYABLE_VOUCHER_TYPES or not r.get("voucher_no"):
				continue
			if suppliers and r.party not in suppliers:
				continue
			outstanding = flt(r.outstanding, precision)
			if outstanding <= 0:
				continue
			candidates.append((r, outstanding))

		dims = self.get_voucher_dimensions([r for r, _o in candidates]) if candidates else {}

		out = []
		for r, outstanding in candidates:
			dim = dims.get((r.voucher_no, r.party_account, r.party)) or {}
			plant = dim.get("branch") or ""
			segment = dim.get("segment") or ""

			if plants and plant not in plants:
				continue
			if segments and segment not in segments:
				continue

			due_date = r.get("due_date") or r.get("posting_date")

			out.append(
				frappe._dict(
					supplier_name=r.get("supplier_name"),
					plant=plant,
					segment=segment,
					party_account=r.party_account,
					party=r.party,
					voucher_no=r.voucher_no,
					bill_type=r.voucher_type,
					due_amount=outstanding,
					due_date=due_date,
					overdue_days=max(date_diff(as_on, due_date), 0) if due_date else 0,
					currency=self.company_currency,
				)
			)

		out.sort(key=lambda d: (d.overdue_days, d.due_amount), reverse=True)
		return out

	def get_pr_columns(self):
		return [
			{"label": _("Plant"), "fieldname": "plant", "fieldtype": "Link", "options": "Branch", "width": 110},
			{"label": _("Segment"), "fieldname": "segment", "fieldtype": "Data", "width": 80},
			{"label": _("GL Name with Code"), "fieldname": "party_account", "fieldtype": "Link", "options": "Account", "width": 250},
			{"label": _("Supplier Code"), "fieldname": "party", "fieldtype": "Link", "options": "Supplier", "width": 120},
			{"label": _("Supplier Name"), "fieldname": "supplier_name", "fieldtype": "Data", "width": 210},
			{"label": _("Bill Type"), "fieldname": "bill_type", "fieldtype": "Data", "width": 125},
			{"label": _("Voucher No"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "bill_type", "width": 160},
			{"label": _("Due Date"), "fieldname": "due_date", "fieldtype": "Date", "width": 110},
			{"label": _("Due Amount"), "fieldname": "due_amount", "fieldtype": "Currency", "options": "currency", "width": 110},
			{"label": _("OverDue Days"), "fieldname": "overdue_days", "fieldtype": "Int", "width": 130},
			{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "hidden": 1, "width": 60},
		]


def _new_reconciliation(company, party, account):
	pr = frappe.get_doc("Payment Reconciliation")
	pr.company = company
	pr.party_type = "Supplier"
	pr.party = party
	pr.receivable_payable_account = account
	pr.payment_limit = 0
	pr.invoice_limit = 0
	return pr


def _clean_remarks(text):
	if not text:
		return ""
	lines = [l.strip() for l in str(text).splitlines() if l.strip()]
	return " | ".join(l for l in lines if not l.startswith("Amount "))


def _adv_key(p):
	key = (p.reference_type, p.reference_name)
	return key + ((p.reference_row,) if p.reference_type == "Journal Entry" else ())


def _advance_details(payments):
	out = {}

	pes = list({p.reference_name for p in payments if p.reference_type == "Payment Entry"})
	if pes:
		for d in frappe.get_all("Payment Entry", filters={"name": ["in", pes]}, fields=["name", "remarks"]):
			out[("Payment Entry", d.name)] = {"remarks": _clean_remarks(d.remarks), "purchase_orders": []}
		for d in frappe.get_all(
			"Payment Entry Reference",
			filters={"parent": ["in", pes], "reference_doctype": "Purchase Order"},
			fields=["parent", "reference_name"],
		):
			po_list = out[("Payment Entry", d.parent)]["purchase_orders"]
			if d.reference_name not in po_list:
				po_list.append(d.reference_name)

	je_payments = [p for p in payments if p.reference_type == "Journal Entry"]
	if je_payments:
		jes = list({p.reference_name for p in je_payments})
		jrows = list({p.reference_row for p in je_payments if p.reference_row})
		hdr = {
			d.name: d
			for d in frappe.get_all(
				"Journal Entry", filters={"name": ["in", jes]}, fields=["name", "user_remark", "remark"]
			)
		}
		rows = {}
		if jrows:
			rows = {
				d.name: d
				for d in frappe.get_all(
					"Journal Entry Account",
					filters={"name": ["in", jrows]},
					fields=["name", "user_remark", "reference_type", "reference_name"],
				)
			}
		for p in je_payments:
			h = hdr.get(p.reference_name)
			r = rows.get(p.reference_row)
			text = (r and r.user_remark) or (h and h.user_remark) or (h and h.remark) or ""
			po = [r.reference_name] if r and r.reference_type == "Purchase Order" and r.reference_name else []
			out[_adv_key(p)] = {"remarks": _clean_remarks(text), "purchase_orders": po}

	return out


@frappe.whitelist()
def get_advance_summary(company, rows):
	rows = frappe.parse_json(rows)

	keys = list(dict.fromkeys((r["party"], r["party_account"]) for r in rows))
	po_map = get_po_map([r["voucher_no"] for r in rows])

	invoices_by_key = {}
	for r in rows:
		invoices_by_key.setdefault((r["party"], r["party_account"]), []).append(r["voucher_no"])

	supplier_names = {
		d.name: d.supplier_name
		for d in frappe.get_all(
			"Supplier",
			filters={"name": ["in", list({k[0] for k in keys})]},
			fields=["name", "supplier_name"],
		)
	}

	out = []
	for party, account in keys:
		pr = _new_reconciliation(company, party, account)
		pr.get_nonreconciled_payment_entries()

		payments = [p for p in pr.payments if flt(p.amount) > 0]
		details = _advance_details(payments)

		advances = []
		for p in payments:
			d = details.get(_adv_key(p))
			advances.append(
				{
					"voucher_type": p.reference_type,
					"voucher_no": p.reference_name,
					"posting_date": p.posting_date,
					"amount": flt(p.amount),
					"remarks": d["remarks"] if d else _clean_remarks(p.remarks),
					"purchase_orders": d["purchase_orders"] if d else [],
				}
			)

		out.append(
			{
				"party": party,
				"party_account": account,
				"supplier_name": supplier_names.get(party),
				"advance_total": flt(sum(a["amount"] for a in advances), 2),
				"advances": advances,
				"invoice_pos": {v: po_map.get(v, []) for v in invoices_by_key[(party, account)]},
			}
		)
	return out


def _dimension_fields():
	try:
		return [d.fieldname for d in get_dimensions(with_cost_center_and_project=False)[0]]
	except Exception:
		return []


def _rows_dimensions(rows, fields):
	if not fields or not rows:
		return {}

	result = {}
	vouchers = list({r["voucher_no"] for r in rows})
	for chunk in _chunks(vouchers):
		for d in frappe.get_all(
			"GL Entry",
			filters={
				"voucher_no": ["in", chunk],
				"is_cancelled": 0,
				"party": ["is", "set"],
			},
			fields=["voucher_no", "account", "party", *fields],
		):
			dims = result.setdefault((d.voucher_no, d.account, d.party), {})
			for f in fields:
				if d.get(f) and f not in dims:
					dims[f] = d[f]
	return result


def _validate_open_invoices(company, rows):
	company_currency = frappe.get_cached_value("Company", company, "default_currency")
	invoices = {
		d.name: d
		for d in frappe.get_all(
			"Purchase Invoice",
			filters={"name": ["in", list({r["voucher_no"] for r in rows})]},
			fields=["name", "docstatus", "outstanding_amount", "currency", "company"],
		)
	}

	for r in rows:
		inv = invoices.get(r["voucher_no"])
		if not inv or inv.docstatus != 1:
			frappe.throw(_("{0} is not a submitted invoice.").format(r["voucher_no"]))
		if inv.company != company:
			frappe.throw(_("{0} does not belong to company {1}.").format(r["voucher_no"], company))
		if flt(inv.outstanding_amount) <= 0:
			frappe.throw(_("{0} is already settled.").format(r["voucher_no"]))
		if (inv.currency or company_currency) == company_currency and flt(r["pay_amount"]) > flt(
			inv.outstanding_amount
		) + EPSILON:
			frappe.throw(
				_("Request amount for {0} exceeds its outstanding amount {1}.").format(
					r["voucher_no"], flt(inv.outstanding_amount)
				)
			)

	return {name: inv.currency or company_currency for name, inv in invoices.items()}


def _create_payment_requests(company, rows, request_date, currencies, mode_of_payment=None):
	meta = frappe.get_meta("Payment Request")
	has_party_name = meta.has_field("party_name")
	has_email_to = meta.has_field("email_to")

	parties = list({r["party"] for r in rows})
	suppliers = {
		d.name: d
		for d in frappe.get_all(
			"Supplier",
			filters={"name": ["in", parties]},
			fields=["name", "supplier_name", "email_id"],
		)
	}

	created = []
	for r in rows:
		supplier = suppliers.get(r["party"]) or frappe._dict()

		pr = frappe.new_doc("Payment Request")
		pr.payment_request_type = PAYMENT_REQUEST_TYPE
		pr.company = company
		pr.transaction_date = request_date
		pr.party_type = "Supplier"
		pr.party = r["party"]
		pr.reference_doctype = r["bill_type"]
		pr.reference_name = r["voucher_no"]
		pr.grand_total = flt(r["pay_amount"])
		pr.currency = currencies[r["voucher_no"]]
		pr.subject = _("Payment Request for {0}").format(r["voucher_no"])

		if has_party_name:
			pr.party_name = supplier.get("supplier_name")
		if has_email_to and supplier.get("email_id"):
			pr.email_to = supplier.email_id
		if mode_of_payment:
			pr.mode_of_payment = mode_of_payment

		for f, v in (r.get("_dims") or {}).items():
			if meta.has_field(f):
				pr.set(f, v)

		pr.insert()
		created.append(pr.name)

	return created


@frappe.whitelist()
def create_payment_requests(company, rows, posting_date=None, mode_of_payment=None):
	frappe.has_permission("Payment Request", "create", throw=True)
	rows = frappe.parse_json(rows)

	for r in rows:
		if r["bill_type"] not in PAYABLE_VOUCHER_TYPES:
			frappe.throw(
				_("Payment Request cannot be created against {0} {1}. Select invoices only.").format(
					r["bill_type"], r["voucher_no"]
				)
			)

	rows = [r for r in rows if flt(r["pay_amount"]) > 0]
	if not rows:
		return {"payment_requests": []}

	currencies = _validate_open_invoices(company, rows)

	dim_map = _rows_dimensions(rows, _dimension_fields())
	for r in rows:
		r["_dims"] = dim_map.get((r["voucher_no"], r["party_account"], r["party"]), {})

	created = _create_payment_requests(
		company, rows, posting_date or nowdate(), currencies, mode_of_payment
	)
	return {"payment_requests": created}