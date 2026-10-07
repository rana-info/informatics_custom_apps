import re

import frappe
from frappe import _
from frappe.model import no_value_fields
from frappe.model.workflow import (
	apply_workflow,
	get_transitions,
	get_workflow_name,
	is_transition_condition_satisfied,
)
from frappe.utils import cint, flt, getdate, nowdate, strip_html

from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_dimensions
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry

PAYABLE_VOUCHER_TYPES = ("Purchase Invoice",)
PAYMENT_REQUEST_TYPE = "Outward"
EPSILON = 0.005

# Who may create the Payment Entry once a request is fully approved.
# Empty tuple = anyone who has "create" permission on Payment Entry.
# Example: ("Accounts Manager",) restricts it to that role (the "final person").
PAYMENT_ENTRY_ROLES = ()

# Fields the report fills itself; everything else mandatory on Payment Entry is asked from the user
PE_HANDLED_FIELDS = {
	"naming_series", "company", "payment_type", "posting_date", "mode_of_payment",
	"reference_no", "reference_date", "party_type", "party", "paid_from", "paid_to",
	"paid_amount", "received_amount", "source_exchange_rate", "target_exchange_rate",
	"paid_from_account_currency", "paid_to_account_currency",
}

VIEW_ACTIONS = "My Actions"
VIEW_PAYMENT = "Ready for Payment"
VIEW_ALL = "All Open"

# Workflow states whose documents are treated as dead (not pending, not payable)
REJECTED_STATES = ("Rejected", "Cancelled")
# Actions never auto-applied while completing the Payment Entry workflow
SKIP_ACTIONS = {"Reject", "Cancel", "Send Back", "Return", "Revert", "Reopen"}
MAX_WORKFLOW_STEPS = 10
# Actions that need a mandatory reason and never change the amount
REJECT_RE = re.compile(r"reject|cancel|return|send back|revert", re.I)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def as_list(val):
	if not val:
		return []
	if isinstance(val, str):
		try:
			val = frappe.parse_json(val)
		except Exception:
			val = [v.strip() for v in val.split(",") if v.strip()]
	return list(val) if isinstance(val, (list, tuple)) else [val]


def _pe_state_field():
	return "workflow_state" if frappe.get_meta("Payment Entry").has_field("workflow_state") else None


def _dimension_fields():
	try:
		return [d.fieldname for d in get_dimensions(with_cost_center_and_project=False)[0]]
	except Exception:
		return []


def _err(e):
	msg = strip_html(str(e) or e.__class__.__name__)
	frappe.clear_messages()
	return msg


def _check_link_field():
	if not frappe.get_meta("Payment Entry Reference").has_field("payment_request"):
		frappe.throw(_("This ERPNext version has no 'payment_request' field on Payment Entry Reference."))


def _can_make_payment():
	if not frappe.has_permission("Payment Entry", "create"):
		return False
	if PAYMENT_ENTRY_ROLES and not set(PAYMENT_ENTRY_ROLES) & set(frappe.get_roles()):
		return False
	return True


def _pr_transitions():
	name = get_workflow_name("Payment Request")
	return frappe.get_cached_doc("Workflow", name).transitions if name else []


def _row_actions(transitions, state, owner, roles, user, name):
	"""Workflow actions the current user can take on a Payment Request in `state`."""
	out, doc = [], None
	for t in transitions:
		if t.state != state or t.allowed not in roles:
			continue
		if not (user == "Administrator" or t.allow_self_approval or user != owner):
			continue
		if t.condition:
			doc = doc or frappe.get_doc("Payment Request", name)
			if not is_transition_condition_satisfied(t, doc):
				continue
		if t.action not in out:
			out.append(t.action)
	return out


def _required_pe_fields():
	meta = frappe.get_meta("Payment Entry")
	return [
		df
		for df in meta.fields
		if df.reqd
		and df.fieldname not in PE_HANDLED_FIELDS
		and not df.hidden
		and not df.read_only
		and df.fieldtype not in no_value_fields
		and df.fieldtype != "Dynamic Link"
	]


@frappe.whitelist()
def get_payment_entry_fields():
	"""Mandatory Payment Entry fields (incl. custom fields) the user must fill in the dialog."""
	return [
		{
			"fieldname": df.fieldname,
			"label": df.label,
			"fieldtype": df.fieldtype,
			"options": df.options,
			"default": df.default,
		}
		for df in _required_pe_fields()
	]


# --------------------------------------------------------------------------- #
# Report
# --------------------------------------------------------------------------- #
def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not filters.get("company"):
		frappe.throw(_("Company is required"))
	_check_link_field()
	return get_columns(filters.get("view") or VIEW_ACTIONS), get_data(filters)


def get_data(filters):
	pr_meta = frappe.get_meta("Payment Request")
	state_field = _pe_state_field()
	pr_has_state = pr_meta.has_field("workflow_state")

	user = frappe.session.user
	roles = set(frappe.get_roles())
	transitions = _pr_transitions() if pr_has_state else []
	can_pay = _can_make_payment()
	view = filters.get("view") or VIEW_ACTIONS

	values = {"company": filters.company, "ptype": PAYMENT_REQUEST_TYPE, "rejected": REJECTED_STATES}
	conds = [
		"pr.payment_request_type = %(ptype)s",
		"pr.party_type = 'Supplier'",
		"pr.company = %(company)s",
	]

	# What each user sees depends on the workflow state and the roles allowed to act on it
	if view == VIEW_ACTIONS:
		states = sorted({t.state for t in transitions if t.allowed in roles})
		if not states:
			return []
		conds += ["pr.docstatus = 0", "pr.workflow_state in %(states)s"]
		values["states"] = tuple(states)
	elif view == VIEW_PAYMENT:
		if not can_pay:
			return []
		conds.append("pr.docstatus = 1")
	else:
		conds.append("pr.docstatus < 2")
		if pr_has_state:
			conds.append("ifnull(pr.workflow_state, '') not in %(rejected)s")

	if filters.get("from_date"):
		conds.append("pr.transaction_date >= %(from_date)s")
		values["from_date"] = getdate(filters.from_date)
	if filters.get("to_date"):
		conds.append("pr.transaction_date <= %(to_date)s")
		values["to_date"] = getdate(filters.to_date)

	suppliers = as_list(filters.get("supplier"))
	if suppliers:
		conds.append("pr.party in %(suppliers)s")
		values["suppliers"] = tuple(suppliers)

	has_branch = pr_meta.has_field("branch")
	has_segment = pr_meta.has_field("segment")
	plants = as_list(filters.get("plant"))
	if plants and has_branch:
		conds.append("pr.branch in %(plants)s")
		values["plants"] = tuple(plants)
	segments = as_list(filters.get("segment"))
	if segments and has_segment:
		conds.append("pr.segment in %(segments)s")
		values["segments"] = tuple(segments)

	in_process = "pe.docstatus = 0"
	state_expr = "if(pe.docstatus = 1, 'Submitted', 'Draft')"
	if state_field:
		in_process += f" and ifnull(pe.{state_field}, '') not in %(rejected)s"
		state_expr = f"coalesce(nullif(pe.{state_field}, ''), {state_expr})"

	query = f"""
		select
			pr.name as payment_request,
			pr.owner as pr_owner,
			pr.docstatus as pr_docstatus,
			{"pr.workflow_state" if pr_has_state else "''"} as pr_state,
			pr.transaction_date,
			pr.party,
			sup.supplier_name,
			{"pr.branch" if has_branch else "''"} as plant,
			{"pr.segment" if has_segment else "''"} as segment,
			pr.reference_doctype,
			pr.reference_name,
			pr.currency,
			pr.grand_total,
			ifnull(pep.paid_amount, 0) as paid_amount,
			ifnull(pep.in_process, 0) as in_process,
			pi.outstanding_amount as invoice_outstanding,
			pi.credit_to as party_account,
			pep.payment_entries
		from `tabPayment Request` pr
		left join `tabSupplier` sup on sup.name = pr.party
		left join `tabPurchase Invoice` pi
			on pi.name = pr.reference_name
			and pr.reference_doctype = 'Purchase Invoice'
			and pi.docstatus = 1
		left join (
			select
				ref.payment_request as pr_name,
				sum(case when pe.docstatus = 1 then ref.allocated_amount else 0 end) as paid_amount,
				sum(case when {in_process} then ref.allocated_amount else 0 end) as in_process,
				group_concat(
					concat(pe.name, ' (', {state_expr}, ')') order by pe.creation separator ', '
				) as payment_entries
			from `tabPayment Entry Reference` ref
			inner join `tabPayment Entry` pe on pe.name = ref.parent
			where ref.parenttype = 'Payment Entry' and pe.docstatus < 2
				and ifnull(ref.payment_request, '') != ''
			group by ref.payment_request
		) pep on pep.pr_name = pr.name
		where {" and ".join(conds)}
		order by pr.transaction_date, pr.name
	"""

	out = []
	for d in frappe.db.sql(query, values, as_dict=True):
		paid, proc = flt(d.paid_amount), flt(d.in_process)
		pending = flt(d.grand_total) - paid - proc

		max_amount = pending
		if d.invoice_outstanding is not None:
			max_amount = min(pending, flt(d.invoice_outstanding) - proc)
		max_amount = max(flt(max_amount, 2), 0)

		# fully paid (submitted Payment Entries cover the request) -> nothing left to show;
		# partial payments, in-process drafts and cancelled entries stay visible
		if paid >= flt(d.grand_total) - EPSILON:
			continue
		# invoice already cleared (e.g. fully settled by advances) and nothing in process -> nothing to pay
		if d.pr_docstatus == 1 and d.invoice_outstanding is not None and flt(d.invoice_outstanding) <= EPSILON and not proc:
			continue

		d.pending_amount = flt(max(pending, 0), 2)
		d.max_amount = max_amount
		d.pr_state = d.pr_state or (_("Approved") if d.pr_docstatus == 1 else _("Draft"))

		actions = []
		if d.pr_docstatus == 0:
			actions = _row_actions(transitions, d.pr_state, d.pr_owner, roles, user, d.payment_request)
		d.available_actions = ", ".join(actions)
		d.can_pay = 1 if (can_pay and d.pr_docstatus == 1 and max_amount > 0) else 0

		d.status = (
			_("Fully Processed")
			if pending <= EPSILON
			else _("Partly Processed")
			if (paid or proc)
			else _("Open")
		)
		out.append(d)
	return out


def get_columns(view=VIEW_ACTIONS):
	def col(label, fieldname, fieldtype="Data", width=120, options=None, hidden=0):
		c = {"label": _(label), "fieldname": fieldname, "fieldtype": fieldtype, "width": width}
		if options:
			c["options"] = options
		if hidden:
			c["hidden"] = 1
		return c

	money = lambda label, fn, w=120: col(label, fn, "Currency", w, "currency")

	request = col("Payment Request", "payment_request", "Link", 160, "Payment Request")
	state = col("Request State", "pr_state", "Data", 130)
	actions = col("My Actions", "available_actions", "Data", 150)
	date = col("Date", "transaction_date", "Date", 100)
	plant = col("Plant", "plant", "Link", 110, "Branch")
	segment = col("Segment", "segment", "Data", 80)
	supplier = col("Supplier", "supplier_name", "Data", 230)
	voucher = col("Voucher No", "reference_name", "Dynamic Link", 160, "reference_doctype")
	requested = money("Requested Amount", "grand_total")

	if view == VIEW_ACTIONS:
		# approval stage: nothing is paid yet, so no payment columns
		columns = [request, state, actions, date, plant, segment, supplier, voucher, requested,
			money("Invoice Outstanding", "invoice_outstanding", 160)]
	elif view == VIEW_PAYMENT:
		columns = [request, date, plant, segment, supplier, voucher, requested,
			money("Paid (Submitted)", "paid_amount"),
			money("Max Payable", "max_amount"), col("Payment Entries (State)", "payment_entries", "Data", 260)]
	else:
		columns = [request, state, actions, date, plant, segment, supplier, voucher, requested,
			money("Paid (Submitted)", "paid_amount"),
			money("Max Payable", "max_amount"), col("Status", "status", "Data", 110),
			col("Payment Entries (State)", "payment_entries", "Data", 260)]

	# hidden helpers used by the client (button logic / currency formatting)
	return columns + [
		col("Can Pay", "can_pay", "Int", 40, hidden=1),
		col("Currency", "currency", "Link", 60, "Currency", hidden=1),
	]


# --------------------------------------------------------------------------- #
# Advances (supplier debit entries not yet reconciled) - shown before moving a request
# --------------------------------------------------------------------------- #
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
			for d in frappe.get_all("Journal Entry", filters={"name": ["in", jes]}, fields=["name", "user_remark", "remark"])
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


def _supplier_advances(company, party, account):
	rec = frappe.get_doc("Payment Reconciliation")
	rec.company = company
	rec.party_type = "Supplier"
	rec.party = party
	rec.receivable_payable_account = account
	rec.payment_limit = 0
	rec.invoice_limit = 0
	rec.get_nonreconciled_payment_entries()

	payments = [p for p in rec.payments if flt(p.amount) > 0]
	details = _advance_details(payments)
	advances = []
	for p in payments:
		d = details.get(_adv_key(p))
		advances.append(
			{
				"voucher_type": p.reference_type,
				"voucher_no": p.reference_name,
				"reference_row": p.reference_row if p.reference_type == "Journal Entry" else "",
				"posting_date": p.posting_date,
				"amount": flt(p.amount),
				"remarks": d["remarks"] if d else _clean_remarks(p.remarks),
				"purchase_orders": d["purchase_orders"] if d else [],
			}
		)
	return advances


@frappe.whitelist()
def get_supplier_advances(company, party, account):
	"""Advances of ONE supplier - the dialog calls this once per supplier, in parallel."""
	advances = _supplier_advances(company, party, account)
	return {"advances": advances, "advance_total": flt(sum(a["amount"] for a in advances), 2)}


@frappe.whitelist()
def get_advance_summary(company, names):
	"""Per supplier advances + per request amount limits, for the 'move to next stage' dialog."""
	names = frappe.parse_json(names)
	if not names:
		return {"requests": {}, "suppliers": []}

	prs = frappe.get_all(
		"Payment Request",
		filters={"name": ["in", names]},
		fields=["name", "party", "reference_doctype", "reference_name", "grand_total"],
	)
	invs = {
		d.name: d
		for d in frappe.get_all(
			"Purchase Invoice",
			filters={"name": ["in", list({p.reference_name for p in prs}) or [""]]},
			fields=["name", "credit_to", "outstanding_amount", "docstatus"],
		)
	}
	sup_names = {
		d.name: d.supplier_name
		for d in frappe.get_all(
			"Supplier",
			filters={"name": ["in", list({p.party for p in prs}) or [""]]},
			fields=["name", "supplier_name"],
		)
	}

	requests, keys = {}, []
	for p in prs:
		inv = invs.get(p.reference_name)
		paid, in_process = _processed(p.name)
		account = inv.credit_to if inv else None
		requests[p.name] = {
			"party": p.party,
			"party_account": account,
			"grand_total": flt(p.grand_total),
			"invoice_outstanding": flt(inv.outstanding_amount) if inv else None,
			"min_amount": flt(paid + in_process, 2),
			"max_amount": flt(flt(inv.outstanding_amount) + paid, 2) if inv else flt(p.grand_total),
		}
		if account and (p.party, account) not in keys:
			keys.append((p.party, account))

	suppliers = []
	for party, account in keys:
		advances = _supplier_advances(company, party, account)
		suppliers.append(
			{
				"party": party,
				"party_account": account,
				"supplier_name": sup_names.get(party),
				"advance_total": flt(sum(a["amount"] for a in advances), 2),
				"advances": advances,
			}
		)
	return {"requests": requests, "suppliers": suppliers}


# --------------------------------------------------------------------------- #
# Workflow actions on Payment Requests (approve / reject / ... by the user's role)
# --------------------------------------------------------------------------- #
def _validate_new_amount(doc, amount):
	if amount <= 0:
		frappe.throw(_("Request amount for {0} must be greater than zero.").format(doc.name))
	paid, in_process = _processed(doc.name)
	if amount < paid + in_process - EPSILON:
		frappe.throw(
			_("Request amount for {0} cannot be below {1} already paid / in process.").format(
				doc.name, flt(paid + in_process, 2)
			)
		)
	inv = frappe.db.get_value(
		doc.reference_doctype, doc.reference_name, ["docstatus", "outstanding_amount"], as_dict=True
	)
	if inv and inv.docstatus == 1 and amount > flt(inv.outstanding_amount) + paid + EPSILON:
		frappe.throw(
			_("Request amount for {0} exceeds the invoice outstanding ({1}).").format(
				doc.name, flt(flt(inv.outstanding_amount) + paid, 2)
			)
		)


@frappe.whitelist()
def apply_request_action(rows, action, reason=None):
	"""rows: [{"payment_request": name, "amount": new request amount (optional)}]"""
	rows = frappe.parse_json(rows)
	is_reject = bool(REJECT_RE.search(action or ""))
	reason = (reason or "").strip()
	if is_reject and not reason:
		frappe.throw(_("A reason is mandatory for '{0}'.").format(action))

	results = []
	for i, r in enumerate(rows):
		name = r["payment_request"] if isinstance(r, dict) else r
		new_amount = flt(r.get("amount")) if isinstance(r, dict) else 0
		sp = f"prq_wf_{i}"
		frappe.db.savepoint(sp)
		try:
			frappe.db.sql("select name from `tabPayment Request` where name = %s for update", name)
			doc = frappe.get_doc("Payment Request", name)
			if action not in {t.action for t in get_transitions(doc)}:
				frappe.throw(_("'{0}' is not available to you on {1} in its current state.").format(action, name))

			old_amount = flt(doc.grand_total)
			changed = not is_reject and doc.docstatus == 0 and new_amount and abs(new_amount - old_amount) > EPSILON
			if changed:
				_validate_new_amount(doc, new_amount)
				doc.grand_total = new_amount

			doc = apply_workflow(doc, action)
			if is_reject:
				doc.add_comment("Comment", _("{0}: {1}").format(action, reason))
			if changed:
				doc.add_comment(
					"Comment",
					_("Request amount changed from {0} to {1} while applying '{2}'.").format(
						flt(old_amount, 2), flt(new_amount, 2), action
					),
				)
			results.append(
				{
					"payment_request": name,
					"state": doc.get("workflow_state"),
					"docstatus": doc.docstatus,
					"amount_changed": 1 if changed else 0,
					"old_amount": old_amount,
					"new_amount": flt(doc.grand_total),
				}
			)
		except Exception as e:
			frappe.db.rollback(save_point=sp)
			results.append({"payment_request": name, "error": _err(e)})
	return {"results": results}



def _processed(pr_name):
	"""(submitted_paid, in_process) Payment Entry amounts already linked to a Payment Request."""
	state_field = _pe_state_field()
	cond = "pe.docstatus = 0"
	params = {"pr": pr_name}
	if state_field:
		cond += f" and ifnull(pe.{state_field}, '') not in %(rejected)s"
		params["rejected"] = REJECTED_STATES
	row = frappe.db.sql(
		f"""
		select
			sum(case when pe.docstatus = 1 then ref.allocated_amount else 0 end),
			sum(case when {cond} then ref.allocated_amount else 0 end)
		from `tabPayment Entry Reference` ref
		inner join `tabPayment Entry` pe on pe.name = ref.parent
		where ref.parenttype = 'Payment Entry' and ref.payment_request = %(pr)s and pe.docstatus < 2
		""",
		params,
	)[0]
	return flt(row[0]), flt(row[1])


def _complete_workflow(doc):
	"""Apply every forward transition the current user may perform on `doc`."""
	wf_name = get_workflow_name(doc.doctype)
	if not wf_name:
		return doc, []

	wf = frappe.get_cached_doc("Workflow", wf_name)
	state_field = wf.workflow_state_field
	doc_status_of = {s.state: cint(s.doc_status) for s in wf.states}

	trail = []
	seen = {doc.get(state_field)}
	for _i in range(MAX_WORKFLOW_STEPS):
		if doc.docstatus != 0:
			break
		options = [
			t for t in get_transitions(doc) if t.action not in SKIP_ACTIONS and t.next_state not in seen
		]
		if not options:
			break
		step = max(options, key=lambda t: doc_status_of.get(t.next_state, 0))
		doc = apply_workflow(doc, step.action)
		seen.add(doc.get(state_field))
		trail.append(step.action)

	return doc, trail


def _create_one(company, pr_name, amount, posting_date, bank_account, mode_of_payment,
		reference_no, reference_date, extra_fields=None, settled=0):
	frappe.db.sql("select name from `tabPayment Request` where name = %s for update", pr_name)
	pr = frappe.get_doc("Payment Request", pr_name)

	if pr.docstatus != 1:
		frappe.throw(_("{0} is not fully approved yet.").format(pr.name))
	if pr.company != company:
		frappe.throw(_("{0} does not belong to company {1}.").format(pr.name, company))
	if pr.payment_request_type != PAYMENT_REQUEST_TYPE or pr.party_type != "Supplier":
		frappe.throw(_("{0} is not an outward supplier payment request.").format(pr.name))
	if pr.reference_doctype not in PAYABLE_VOUCHER_TYPES:
		frappe.throw(_("Payment cannot be made against {0} {1}.").format(pr.reference_doctype, pr.reference_name))

	paid, in_process = _processed(pr.name)
	pending = flt(pr.grand_total) - paid - in_process
	if amount > pending - flt(settled) + EPSILON:
		frappe.throw(_("Amount for {0} exceeds its pending amount {1}.").format(pr.name, flt(pending - flt(settled), 2)))

	inv = frappe.db.get_value(
		pr.reference_doctype, pr.reference_name, ["docstatus", "outstanding_amount"], as_dict=True
	)
	if not inv or inv.docstatus != 1:
		frappe.throw(_("{0} is not a submitted invoice.").format(pr.reference_name))
	if amount > flt(inv.outstanding_amount) - in_process + EPSILON:
		frappe.throw(_("Amount for {0} exceeds the outstanding amount of {1}.").format(pr.name, pr.reference_name))

	pe = get_payment_entry(pr.reference_doctype, pr.reference_name, party_amount=amount, bank_account=bank_account)
	pe.posting_date = posting_date
	pe.mode_of_payment = mode_of_payment
	if reference_no:
		pe.reference_no = reference_no
		pe.reference_date = reference_date or posting_date


	pe_meta = frappe.get_meta("Payment Entry")
	if pe_meta.has_field("custom_remarks"):
		pe.custom_remarks = 1
	pe.remarks = " | ".join(
		[
			_("Payment against {0} {1}").format(pr.reference_doctype, pr.reference_name),
			_("Payment Request {0}").format(pr.name),
		]
	)

	for ref in pe.references:
		if ref.reference_name == pr.reference_name:
			ref.payment_request = pr.name

	for f in {*_dimension_fields(), "branch", "segment", "section"}:
		if pr.get(f) and pe_meta.has_field(f):
			pe.set(f, pr.get(f))
	for f, v in (extra_fields or {}).items():
		if v not in (None, "") and pe_meta.has_field(f):
			pe.set(f, v)

	missing = [df.label for df in _required_pe_fields() if pe.get(df.fieldname) in (None, "")]
	if missing:
		frappe.throw(_("Please fill: {0}").format(", ".join(_(m) for m in missing)))

	if abs(flt(pe.paid_amount) - amount) > EPSILON:
		frappe.throw(
			_("Payment Entry amount {0} differs from requested {1} (multi-currency / deductions are not supported here).").format(
				flt(pe.paid_amount, 2), flt(amount, 2)
			)
		)

	pe.insert()
	pe, trail = _complete_workflow(pe)

	state_field = _pe_state_field()
	return {
		"payment_request": pr.name,
		"payment_entry": pe.name,
		"docstatus": pe.docstatus,
		"state": pe.get(state_field) if state_field else None,
		"actions": trail,
	}


def _doc_values(doctype, name, fields):
	meta = frappe.get_meta(doctype)
	fs = [f for f in fields if meta.has_field(f)]
	return frappe.db.get_value(doctype, name, fs, as_dict=True) or {} if fs else {}


def _adv_select_key(voucher_type, voucher_no, row):
	return (voucher_type, voucher_no, (row or "") if voucher_type == "Journal Entry" else "")


def _reconcile_rows(company, party, account, rows, selected):
	"""Settle `settle_amount` of each row's invoice using the ticked advances (oldest advance first)."""
	rec = frappe.get_doc("Payment Reconciliation")
	rec.company = company
	rec.party_type = "Supplier"
	rec.party = party
	rec.receivable_payable_account = account
	rec.payment_limit = 0
	rec.invoice_limit = 0
	rec.get_unreconciled_entries()

	payments = [
		p for p in rec.payments
		if flt(p.amount) > 0 and _adv_select_key(p.reference_type, p.reference_name, p.reference_row) in selected
	]
	if not payments:
		frappe.throw(_("None of the selected advances is available any more for {0}.").format(party))

	dim_fields = [x.fieldname for x in rec.dimensions if x.fieldname not in ("cost_center", "project")]
	dims_by_inv = {}

	settle_by_inv = {}
	for r in rows:
		pr = frappe.db.get_value(
			"Payment Request", r["payment_request"],
			["docstatus", "company", "grand_total", "reference_doctype", "reference_name"], as_dict=True,
		)
		if not pr or pr.docstatus != 1 or pr.company != company or pr.reference_doctype != "Purchase Invoice":
			frappe.throw(_("{0} cannot be settled through advances.").format(r["payment_request"]))
		settle = flt(r.get("settle_amount"))
		paid, in_process = _processed(r["payment_request"])
		pending = flt(pr.grand_total) - paid - in_process
		outstanding = flt(frappe.db.get_value("Purchase Invoice", pr.reference_name, "outstanding_amount"))
		if settle > min(pending, outstanding - in_process) + EPSILON:
			frappe.throw(_("Advance settlement for {0} exceeds the amount that can still be paid.").format(r["payment_request"]))
		settle_by_inv[pr.reference_name] = flt(settle_by_inv.get(pr.reference_name, 0) + settle, 2)
		from_pr = _doc_values("Payment Request", r["payment_request"], dim_fields)
		from_pi = _doc_values("Purchase Invoice", pr.reference_name, dim_fields)
		dims_by_inv[pr.reference_name] = {f: from_pr.get(f) or from_pi.get(f) for f in dim_fields}

	by_name = {i.invoice_number: i for i in rec.invoices if i.invoice_type == "Purchase Invoice"}
	invoices = []
	for inv_name, amt in settle_by_inv.items():
		inv = by_name.get(inv_name)
		if not inv:
			frappe.throw(_("{0} has no outstanding amount to settle.").format(inv_name))
		if amt > flt(inv.outstanding_amount) + EPSILON:
			frappe.throw(_("Settlement for {0} exceeds its outstanding amount.").format(inv_name))
		row = inv.as_dict()
		row["outstanding_amount"] = amt  # allocate only what the user asked to settle
		invoices.append(row)

	rec.allocate_entries(frappe._dict(payments=[p.as_dict() for p in payments], invoices=invoices))
	for a in rec.allocation:
		for f, v in (dims_by_inv.get(a.invoice_number) or {}).items():
			if v:
				a.set(f, v)
	allocated = flt(sum(flt(a.allocated_amount) for a in rec.allocation), 2)
	wanted = flt(sum(settle_by_inv.values()), 2)
	if abs(allocated - wanted) > EPSILON:
		frappe.throw(
			_("Selected advances ({0}) are not enough to settle {1} for {2}.").format(allocated, wanted, party)
		)

	rec.validate_allocation()
	rec.reconcile_allocations()
	return allocated


def _ref_key(party, account):
	"""Same key the dialog uses per supplier card: '<party>||<party account>'."""
	return f"{party}||{account}"


@frappe.whitelist()
def create_payment_entries(company, rows, posting_date=None, mode_of_payment=None,
		references=None, extra_fields=None, advances=None):
	if not _can_make_payment():
		frappe.throw(_("You are not allowed to create Payment Entries."), frappe.PermissionError)
	_check_link_field()
	rows = frappe.parse_json(rows)
	extra_fields = frappe.parse_json(extra_fields) if extra_fields else {}
	advances = frappe.parse_json(advances) if advances else []
	references = frappe.parse_json(references) if references else {}

	rows = [r for r in rows if flt(r.get("pay_amount")) > 0 or flt(r.get("settle_amount")) > 0]
	if not rows:
		return {"results": []}

	selected = {_adv_select_key(a["voucher_type"], a["voucher_no"], a.get("reference_row")) for a in advances}

	# each vendor can pay through a different Mode of Payment -> resolve its account once per mode
	bank_accounts = {}

	def get_bank_account(mode):
		if mode not in bank_accounts:
			from erpnext.accounts.doctype.journal_entry.journal_entry import get_default_bank_cash_account

			bank = get_default_bank_cash_account(company, mode_of_payment=mode)
			if not bank or not bank.get("account"):
				frappe.throw(_("No account is configured for Mode of Payment {0} in company {1}.").format(mode, company))
			bank_accounts[mode] = bank.get("account")
		return bank_accounts[mode]

	posting_date = posting_date or nowdate()

	groups = {}
	for r in rows:
		pr = frappe.db.get_value(
			"Payment Request", r["payment_request"], ["party", "reference_doctype", "reference_name"], as_dict=True
		)
		account = None
		if pr and pr.reference_doctype == "Purchase Invoice":
			account = frappe.db.get_value("Purchase Invoice", pr.reference_name, "credit_to")
		r["_ref_key"] = _ref_key(pr.party if pr else None, account)
		groups.setdefault((pr.party if pr else None, account), []).append(r)

	def pay(r):
		settle = flt(r.get("settle_amount"))
		amount = flt(r.get("pay_amount"))
		if amount > 0:
			ref = references.get(r.get("_ref_key")) or {}
			mode = ref.get("mode_of_payment") or mode_of_payment
			if not mode:
				frappe.throw(_("Mode of Payment is required for {0}.").format(r["payment_request"]))
			vendor_extra = {
				k: v for k, v in (ref.get("extra_fields") or {}).items() if v not in (None, "")
			}
			res = _create_one(
				company, r["payment_request"], amount, posting_date, get_bank_account(mode), mode,
				(ref.get("reference_no") or "").strip(), ref.get("reference_date") or None,
				{**extra_fields, **vendor_extra}, settled=settle,
			)
		else:
			res = {"payment_request": r["payment_request"], "payment_entry": None, "docstatus": None,
				"state": None, "actions": []}
		res["settled"] = settle
		return res

	results = []
	for gi, ((party, account), grp) in enumerate(groups.items()):
		settle_rows = [r for r in grp if flt(r.get("settle_amount")) > 0]
		if settle_rows:
			sp = f"prq_grp_{gi}"
			frappe.db.savepoint(sp)
			try:
				_reconcile_rows(company, party, account, settle_rows, selected)
				for r in grp:
					results.append(pay(r))
			except Exception as e:
				frappe.db.rollback(save_point=sp)
				msg = _err(e)
				results.extend({"payment_request": r["payment_request"], "error": msg} for r in grp)
		else:
			for j, r in enumerate(grp):
				sp = f"prq_pe_{gi}_{j}"
				frappe.db.savepoint(sp)
				try:
					results.append(pay(r))
				except Exception as e:
					frappe.db.rollback(save_point=sp)
					results.append({"payment_request": r["payment_request"], "error": _err(e)})

	return {"results": results}