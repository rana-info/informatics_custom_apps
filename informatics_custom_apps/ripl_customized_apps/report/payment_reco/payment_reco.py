from __future__ import annotations

import frappe
from frappe import _, qb
from frappe.query_builder import Criterion
from frappe.query_builder.custom import ConstantColumn
from frappe.utils import flt, getdate, nowdate

import erpnext
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import get_dimensions

_PLE_COLUMN_CACHE: dict[str, bool] = {}


def _ple_has_column(fieldname: str) -> bool:
    if fieldname not in _PLE_COLUMN_CACHE:
        _PLE_COLUMN_CACHE[fieldname] = frappe.db.has_column("Payment Ledger Entry", fieldname)
    return _PLE_COLUMN_CACHE[fieldname]


def execute(filters=None):
    filters = frappe._dict(filters or {})
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"label": _("Section"),             "fieldname": "section",            "fieldtype": "Data",         "width": 110},
        {"label": _("Type"),                "fieldname": "reference_type",     "fieldtype": "Data",         "width": 140},
        {"label": _("Reference / Invoice"), "fieldname": "reference_name",     "fieldtype": "Dynamic Link", "options": "reference_type", "width": 180},
        {"label": _("Party type"),          "fieldname": "party_type",         "fieldtype": "Data",         "width": 110},
        {"label": _("Party"),               "fieldname": "party",              "fieldtype": "Dynamic Link", "options": "party_type",     "width": 180},
        {"label": _("Account"),             "fieldname": "account",            "fieldtype": "Link",         "options": "Account",        "width": 200},
        {"label": _("Date"),                "fieldname": "posting_date",       "fieldtype": "Date",         "width": 100},
        {"label": _("Currency"),            "fieldname": "currency",           "fieldtype": "Link",         "options": "Currency",       "width": 80},
        {"label": _("Amount"),              "fieldname": "amount",             "fieldtype": "Currency",     "options": "currency",       "width": 140},
        {"label": _("Outstanding"),         "fieldname": "outstanding_amount", "fieldtype": "Currency",     "options": "currency",       "width": 140},
        {"label": _("Is advance"),          "fieldname": "is_advance",         "fieldtype": "Check",        "width": 90},
        {"label": _("Cost center"),         "fieldname": "cost_center",        "fieldtype": "Link",         "options": "Cost Center",    "width": 140},
        {"label": _("Remarks"),             "fieldname": "remarks",            "fieldtype": "Data",         "width": 220},
    ]



def get_data(filters: frappe._dict) -> list[dict]:
    dimensions = get_dimensions(with_cost_center_and_project=True)[0]
    scope = _build_scope(filters, dimensions)
    if not scope:
        return []

    rows: list[dict] = []
    rows.extend(_fetch_journal_entries(filters, scope))

    dr_cr_rows, dr_cr_voucher_nos = _fetch_dr_cr_notes(filters, scope)
    rows.extend(dr_cr_rows)

    rows.extend(_fetch_invoices(filters, scope, dr_cr_voucher_nos))
    rows.extend(_fetch_payment_entries(filters, scope))
    return rows



class _Scope:
    __slots__ = (
        "companies", "party_types",
        "accounts_by_pt", "all_accounts", "invoice_accounts",
        "parties_by_co_pt", "all_parties",
        "dim_where",          
        "dim_values",         
        "account_type_by_pt",
    )

    def __init__(self, companies, party_types, accounts_by_pt,
                 invoice_accounts, parties_by_co_pt,
                 dim_where, dim_values, account_type_by_pt):
        self.companies          = companies
        self.party_types        = party_types
        self.accounts_by_pt     = accounts_by_pt
        self.all_accounts       = [a for accs in accounts_by_pt.values() for a in accs]
        self.invoice_accounts   = invoice_accounts
        self.parties_by_co_pt   = parties_by_co_pt
        self.all_parties        = list({p for ps in parties_by_co_pt.values() for p in ps})
        self.dim_where          = dim_where
        self.dim_values         = dim_values
        self.account_type_by_pt = account_type_by_pt


def _build_scope(filters: frappe._dict, dimensions: list) -> "_Scope | None":
    companies   = ([filters.company] if filters.get("company")
                   else [r.name for r in frappe.get_all("Company", fields=["name"])])
    party_types = ([filters.party_type] if filters.get("party_type")
                   else ["Customer", "Supplier"])

    account_type_by_pt = {pt: erpnext.get_party_account_type(pt) for pt in party_types}

    
    if filters.get("receivable_payable_account"):
        accounts_by_pt = {pt: [filters.receivable_payable_account] for pt in party_types}
    else:
        acc = qb.DocType("Account")
        pt_by_acct_type = {v: k for k, v in account_type_by_pt.items()}
        rows = (
            qb.from_(acc)
            .select(acc.name, acc.account_type)
            .where(
                acc.company.isin(companies)
                & acc.account_type.isin(list(account_type_by_pt.values()))
                & (acc.is_group == 0)
            )
            .run(as_dict=True)
        )
        accounts_by_pt: dict[str, list[str]] = {}
        for r in rows:
            pt = pt_by_acct_type.get(r.account_type)
            if pt:
                accounts_by_pt.setdefault(pt, []).append(r.name)

    all_accounts = [a for accs in accounts_by_pt.values() for a in accs]
    if not all_accounts:
        return None

    invoice_accounts = list(all_accounts)
    if filters.get("default_advance_account"):
        invoice_accounts.append(filters.default_advance_account)

    
    parties_by_co_pt: dict[tuple[str, str], list[str]] = {}

    if filters.get("party"):
        for co in companies:
            for pt in party_types:
                parties_by_co_pt[(co, pt)] = [filters.party]
    else:
        ple = qb.DocType("Payment Ledger Entry")
        rows = (
            qb.from_(ple)
            .select(ple.company, ple.party_type, ple.party)
            .distinct()
            .where(
                ple.company.isin(companies)
                & ple.party_type.isin(party_types)
                & ple.account.isin(all_accounts)
                & (ple.delinked == 0)
            )
            .run(as_dict=True)
        )
        for r in rows:
            if r.party:
                parties_by_co_pt.setdefault((r.company, r.party_type), []).append(r.party)

    if not any(parties_by_co_pt.values()):
        return None

    
    dim_where  = ""
    dim_values = []
    for x in dimensions:
        val = filters.get(x.fieldname)
        if val and _ple_has_column(x.fieldname):
            dim_where += f" AND `{x.fieldname}` = %s"
            dim_values.append(val)

    return _Scope(
        companies=companies, party_types=party_types,
        accounts_by_pt=accounts_by_pt, invoice_accounts=invoice_accounts,
        parties_by_co_pt=parties_by_co_pt,
        dim_where=dim_where, dim_values=dim_values,
        account_type_by_pt=account_type_by_pt,
    )



def _in(values: list) -> tuple[str, list]:
    
    return "(" + ",".join(["%s"] * len(values)) + ")", list(values)


def _row(section, ref_type, ref_name, party_type, party, account,
         posting_date, currency, amount, exchange_rate, is_advance,
         cost_center, remarks) -> dict:
    return {
        "section":            section,
        "reference_type":     ref_type,
        "reference_name":     ref_name,
        "party_type":         party_type,
        "party":              party,
        "account":            account,
        "posting_date":       posting_date,
        "currency":           currency,
        "amount":             flt(amount),
        "outstanding_amount": 0,
        "allocated_amount":   None,
        "difference_amount":  None,
        "exchange_rate":      flt(exchange_rate) if exchange_rate is not None else None,
        "is_advance":         is_advance,
        "cost_center":        cost_center,
        "remarks":            remarks,
    }



def _fetch_invoices(
    filters: frappe._dict,
    scope: _Scope,
    dr_cr_voucher_nos: set[str],
) -> list[dict]:

    held_invoices = _get_held_invoices_once() if "Supplier" in scope.party_types else set()

    all_parties  = scope.all_parties
    all_accounts = scope.invoice_accounts
    companies    = scope.companies

    ph_parties,  v_parties  = _in(all_parties)
    ph_accounts, v_accounts = _in(all_accounts)
    ph_companies, v_companies = _in(companies)
    ph_pt, v_pt = _in(scope.party_types)

    where_extra = ""
    extra_vals: list = []

    if filters.get("from_invoice_date"):
        where_extra += " AND posting_date >= %s"
        extra_vals.append(filters.from_invoice_date)
    if filters.get("to_invoice_date"):
        where_extra += " AND posting_date <= %s"
        extra_vals.append(filters.to_invoice_date)
    if filters.get("invoice_name"):
        where_extra += " AND (voucher_no LIKE %s OR against_voucher_no LIKE %s)"
        extra_vals += [f"%{filters.invoice_name}%", f"%{filters.invoice_name}%"]

    where_extra += scope.dim_where
    extra_vals  += scope.dim_values

    having_extra = ""
    having_vals: list = []
    min_out = filters.get("minimum_invoice_amount")
    max_out = filters.get("maximum_invoice_amount")
    if min_out:
        having_extra += " AND outstanding >= %s"
        having_vals.append(min_out)
    if max_out:
        having_extra += " AND outstanding <= %s"
        having_vals.append(max_out)

    sql = f"""
        SELECT
            against_voucher_no                                    AS voucher_no,
            against_voucher_type                                  AS voucher_type,
            party_type,
            party,
            account,
            account_currency                                      AS currency,
            MAX(posting_date)                                     AS posting_date,
            MAX(due_date)                                         AS due_date,
            MAX(cost_center)                                      AS cost_center,
            MAX(remarks)                                          AS remarks,
            SUM(CASE WHEN voucher_no = against_voucher_no
                     THEN amount_in_account_currency ELSE 0 END)  AS invoice_amount,
            SUM(amount_in_account_currency)                       AS outstanding
        FROM `tabPayment Ledger Entry`
        WHERE
            delinked = 0
            AND company      IN {ph_companies}
            AND party_type   IN {ph_pt}
            AND party        IN {ph_parties}
            AND account      IN {ph_accounts}
            {where_extra}
        GROUP BY
            against_voucher_type, against_voucher_no, party_type, party, account, account_currency
        HAVING outstanding > 0
            {having_extra}
        ORDER BY due_date
    """

    values = v_companies + v_pt + v_parties + v_accounts + extra_vals + having_vals
    rows = frappe.db.sql(sql, values, as_dict=True)

    precision = frappe.get_precision("Sales Invoice", "outstanding_amount") or 2
    threshold = 0.5 / (10 ** precision)
    invoice_limit = filters.get("invoice_limit") or 0

    result = []
    for d in rows:
        if flt(d.outstanding) <= threshold:
            continue
        if d.voucher_no in dr_cr_voucher_nos:
            continue
        if d.voucher_type == "Purchase Invoice" and d.voucher_no in held_invoices:
            continue
        result.append({
            "section":            "Invoice",
            "reference_type":     d.voucher_type,
            "reference_name":     d.voucher_no,
            "party_type":         d.party_type,
            "party":              d.party or "",
            "account":            d.account,
            "posting_date":       d.posting_date,
            "currency":           d.currency,
            "amount":             0,
            "outstanding_amount": flt(d.outstanding),
            "allocated_amount":   None,
            "difference_amount":  None,
            "exchange_rate":      None,
            "is_advance":         0,
            "cost_center":        d.cost_center,
            "remarks":            d.remarks,
        })

    if invoice_limit:
        result = result[:invoice_limit]
    return result



def _fetch_payment_entries(filters: frappe._dict, scope: _Scope) -> list[dict]:
    rows: list[dict] = []

    for party_type in scope.party_types:
        accounts = scope.accounts_by_pt.get(party_type, [])
        parties  = [p for (co, pt), ps in scope.parties_by_co_pt.items()
                    if pt == party_type for p in ps]
        if not accounts or not parties:
            continue

        pe  = qb.DocType("Payment Entry")
        per = qb.DocType("Payment Entry Reference")

        if party_type == "Supplier":
            payment_type   = "Pay"
            account_field  = pe.paid_to
            exrate_field   = pe.target_exchange_rate
            currency_field = pe.paid_to_account_currency
            order_doctype  = "Purchase Order"
        else:
            payment_type   = "Receive"
            account_field  = pe.paid_from
            exrate_field   = pe.source_exchange_rate
            currency_field = pe.paid_from_account_currency
            order_doctype  = "Sales Order"

        base_conds = [
            pe.docstatus == 1,
            pe.payment_type == payment_type,
            pe.party_type == party_type,
            pe.party.isin(parties),
            account_field.isin(accounts),
            pe.company.isin(scope.companies),
        ]
        if filters.get("to_payment_date"):
            base_conds.append(pe.posting_date.lte(filters.to_payment_date))
        if filters.get("from_payment_date"):
            base_conds.append(pe.posting_date.gte(filters.from_payment_date))
        if filters.get("payment_name"):
            base_conds.append(pe.name.like(f"%{filters.payment_name}%"))
        if filters.get("cost_center"):
            base_conds.append(pe.cost_center == filters.cost_center)

        sel = [
            pe.name.as_("reference_name"), pe.party,
            account_field.as_("account"), pe.posting_date, pe.remarks,
            pe.book_advance_payments_in_separate_party_account.as_("is_advance"),
            exrate_field.as_("exchange_rate"), currency_field.as_("currency"), pe.cost_center,
        ]

        q1_conds = base_conds + [pe.unallocated_amount > 0]
        if filters.get("minimum_payment_amount"):
            q1_conds.append(pe.unallocated_amount.gte(filters.minimum_payment_amount))
        if filters.get("maximum_payment_amount"):
            q1_conds.append(pe.unallocated_amount.lte(filters.maximum_payment_amount))
        q1 = (qb.from_(pe).select(*sel, pe.unallocated_amount.as_("amount"))
              .where(Criterion.all(q1_conds)))

        q2_conds = base_conds + [per.reference_doctype == order_doctype, per.allocated_amount > 0]
        if filters.get("minimum_payment_amount"):
            q2_conds.append(per.allocated_amount.gte(filters.minimum_payment_amount))
        if filters.get("maximum_payment_amount"):
            q2_conds.append(per.allocated_amount.lte(filters.maximum_payment_amount))
        q2 = (qb.from_(pe).join(per).on(per.parent == pe.name)
              .select(*sel, per.allocated_amount.as_("amount"))
              .where(Criterion.all(q2_conds)))

        limit = filters.get("payment_limit") or 0
        if limit:
            q1 = q1.limit(limit)
            q2 = q2.limit(limit)

        seen: set[str] = set()
        for r in [*q1.run(as_dict=True), *q2.run(as_dict=True)]:
            key = r["reference_name"]
            if key in seen:
                continue
            seen.add(key)
            rows.append(_row(
                "Payment", "Payment Entry", r["reference_name"],
                party_type, r["party"], r["account"], r["posting_date"],
                r["currency"], r["amount"], r["exchange_rate"],
                r["is_advance"], r["cost_center"], r["remarks"],
            ))

    rows.sort(key=lambda r: r["posting_date"] or getdate(nowdate()))
    return rows




def _fetch_journal_entries(filters: frappe._dict, scope: _Scope) -> list[dict]:
    je  = qb.DocType("Journal Entry")
    jea = qb.DocType("Journal Entry Account")

    conditions = [
        je.company.isin(scope.companies),
        jea.party_type.isin(scope.party_types),
        jea.party.isin(scope.all_parties),
        jea.account.isin(scope.all_accounts),
        je.docstatus == 1,
        (
            (jea.reference_type == "")
            | jea.reference_type.isnull()
            | jea.reference_type.isin(("Sales Order", "Purchase Order"))
        ),
    ]
    if filters.get("from_payment_date"):
        conditions.append(je.posting_date.gte(filters.from_payment_date))
    if filters.get("to_payment_date"):
        conditions.append(je.posting_date.lte(filters.to_payment_date))
    if filters.get("minimum_payment_amount"):
        conditions.append(je.total_debit.gte(filters.minimum_payment_amount))
    if filters.get("maximum_payment_amount"):
        conditions.append(je.total_debit.lte(filters.maximum_payment_amount))
    if filters.get("payment_name"):
        conditions.append(je.name.like(f"%%{filters.payment_name}%%"))
    if filters.get("cost_center"):
        conditions.append(jea.cost_center == filters.cost_center)
    if filters.get("bank_cash_account"):
        conditions.append(jea.against_account.like(f"%%{filters.bank_cash_account}%%"))
    conditions.extend([
        jea[x.fieldname] == filters.get(x.fieldname)
        for x in scope.party_types  
    ] if False else [])   
    
    dimensions = get_dimensions(with_cost_center_and_project=True)[0]
    for x in dimensions:
        val = filters.get(x.fieldname)
        if val and hasattr(jea, x.fieldname):
            conditions.append(jea[x.fieldname] == val)

    query = (
        qb.from_(je)
        .inner_join(jea).on(jea.parent == je.name)
        .select(
            je.name.as_("reference_name"), jea.party, jea.party_type,
            jea.account, je.posting_date, je.remark.as_("remarks"),
            jea.debit_in_account_currency, jea.credit_in_account_currency,
            jea.is_advance, jea.exchange_rate,
            jea.account_currency.as_("currency"), jea.cost_center,
        )
        .where(Criterion.all(conditions))
        .orderby(je.posting_date)
    )

    limit = filters.get("payment_limit") or 0
    if limit:
        query = query.limit(limit)

    result = []
    for r in query.run(as_dict=True):
        pt = r["party_type"]
        amount = (flt(r["credit_in_account_currency"]) - flt(r["debit_in_account_currency"])
                  if pt == "Customer"
                  else flt(r["debit_in_account_currency"]) - flt(r["credit_in_account_currency"]))
        if amount <= 0:
            continue
        result.append(_row(
            "Journal Entry", "Journal Entry", r["reference_name"],
            pt, r["party"], r["account"], r["posting_date"],
            r["currency"], amount, r["exchange_rate"],
            r["is_advance"] or 0, r["cost_center"], r["remarks"],
        ))
    return result



def _fetch_dr_cr_notes(filters: frappe._dict, scope: _Scope) -> tuple[list[dict], set[str]]:
    all_return_invoices: list[dict] = []
    dr_cr_voucher_nos: set[str]    = set()

    for party_type in scope.party_types:
        voucher_type = "Sales Invoice" if party_type == "Customer" else "Purchase Invoice"
        party_field  = frappe.scrub(party_type)
        doc          = qb.DocType(voucher_type)
        parties      = [p for (co, pt), ps in scope.parties_by_co_pt.items()
                        if pt == party_type for p in ps]
        if not parties:
            continue

        conds = [
            doc.docstatus == 1,
            doc[party_field].isin(parties),
            doc.is_return == 1,
            doc.outstanding_amount != 0,
        ]
        if filters.get("payment_name"):
            conds.append(doc.name.like(f"%{filters.payment_name}%"))

        q = (qb.from_(doc)
             .select(
                 ConstantColumn(voucher_type).as_("voucher_type"),
                 doc.name.as_("voucher_no"),
                 doc[party_field].as_("party"),
                 doc.return_against,
             )
             .where(Criterion.all(conds)))

        limit = filters.get("payment_limit") or 0
        if limit:
            q = q.limit(limit)

        for r in q.run(as_dict=True):
            r["_party_type"] = party_type
            all_return_invoices.append(r)
            dr_cr_voucher_nos.add(r["voucher_no"])

    if not all_return_invoices:
        return [], set()

    
    
    voucher_nos = [r["voucher_no"] for r in all_return_invoices]
    ph_vn, v_vn = _in(voucher_nos)
    ph_co, v_co = _in(scope.companies)
    ph_ac, v_ac = _in(scope.all_accounts)

    date_where  = ""
    date_vals: list = []
    if filters.get("from_payment_date"):
        date_where += " AND posting_date >= %s"
        date_vals.append(filters.from_payment_date)
    if filters.get("to_payment_date"):
        date_where += " AND posting_date <= %s"
        date_vals.append(filters.to_payment_date)

    having_extra = ""
    having_vals: list = []
    if filters.get("minimum_payment_amount"):
        having_extra += " AND outstanding >= %s"
        having_vals.append(-filters.minimum_payment_amount)
    if filters.get("maximum_payment_amount"):
        having_extra += " AND outstanding <= %s"
        having_vals.append(-filters.maximum_payment_amount)

    sql = f"""
        SELECT
            against_voucher_no              AS voucher_no,
            against_voucher_type            AS voucher_type,
            party_type, party, account,
            account_currency                AS currency,
            MAX(posting_date)               AS posting_date,
            MAX(cost_center)                AS cost_center,
            MAX(remarks)                    AS remarks,
            SUM(amount_in_account_currency) AS outstanding
        FROM `tabPayment Ledger Entry`
        WHERE
            delinked = 0
            AND company          IN {ph_co}
            AND against_voucher_no IN {ph_vn}
            AND account          IN {ph_ac}
            {date_where}
            {scope.dim_where}
        GROUP BY
            against_voucher_type, against_voucher_no, party_type, party, account, account_currency
        HAVING outstanding < 0
            {having_extra}
    """
    values = v_co + v_vn + v_ac + date_vals + scope.dim_values + having_vals
    ple_rows = frappe.db.sql(sql, values, as_dict=True)

    party_by_vn      = {r["voucher_no"]: r["party"]       for r in all_return_invoices}
    party_type_by_vn = {r["voucher_no"]: r["_party_type"] for r in all_return_invoices}

    result = [
        {
            "section":            "Dr/Cr Note",
            "reference_type":     r.voucher_type,
            "reference_name":     r.voucher_no,
            "party_type":         party_type_by_vn.get(r.voucher_no, ""),
            "party":              party_by_vn.get(r.voucher_no) or r.get("party") or "",
            "account":            r.account,
            "posting_date":       r.posting_date,
            "currency":           r.currency,
            "amount":             0,
            "outstanding_amount": flt(-r.outstanding),
            "allocated_amount":   None,
            "difference_amount":  None,
            "exchange_rate":      None,
            "is_advance":         0,
            "cost_center":        r.cost_center,
            "remarks":            r.remarks,
        }
        for r in ple_rows
        if r.outstanding != 0
    ]
    return result, dr_cr_voucher_nos


def _get_held_invoices_once() -> set[str]:
    rows = frappe.db.sql(
        "SELECT name FROM `tabPurchase Invoice` "
        "WHERE on_hold = 1 AND release_date IS NOT NULL AND release_date > CURDATE()",
        as_dict=True,
    )
    return {r["name"] for r in rows}