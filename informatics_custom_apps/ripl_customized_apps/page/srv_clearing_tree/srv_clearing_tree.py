import frappe
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from frappe.utils import flt, get_number_format_info


def to_decimal_raw(value):
    if value is None:
        return Decimal(0)
    return Decimal(str(value))


def round_decimal(value, precision):
    quant = Decimal(1).scaleb(-precision)
    return value.quantize(quant, rounding=ROUND_HALF_UP)

ROUNDING_ONLY_THRESHOLD = Decimal("0.05")


def get_precision(company):
    """Resolve the same currency precision the General Ledger report
    effectively renders/rounds at, so our sums tie out exactly."""
    if not company:
        return frappe.db.get_default("currency_precision") or 2

    currency = frappe.get_cached_value("Company", company, "default_currency")
    if not currency:
        return frappe.db.get_default("currency_precision") or 2

    number_format = frappe.db.get_value("Currency", currency, "number_format")
    if not number_format:
        return frappe.db.get_default("currency_precision") or 2

    _, _, precision = get_number_format_info(number_format)
    return precision


@frappe.whitelist()
def get_data(filters=None):
    """Single entry point for the page. Returns a plain dict:
        { "data": [ ...rows... ] }
    (no "columns" — the page renders its own fixed table, it doesn't
    need report column metadata the way frappe.desk.query_report.run
    does).
    """
    if isinstance(filters, str):
        filters = frappe.parse_json(filters)
    filters = frappe._dict(filters or {})

    frappe.has_permission("GL Entry", "read", throw=True)

    data = build_report_data(filters)
    return {"data": data}


@frappe.whitelist()
def get_default_account(company):
    if not company:
        return None

    accounts = frappe.get_all(
        "Account",
        filters={
            "company": company,
            "account_name": ["like", "%SRV%"],
            "is_group": 0,
            "disabled": 0,
        },
        order_by="name asc",
        pluck="name",
        limit=1,
    )

    return accounts[0] if accounts else None



def build_report_data(filters):
    precision = get_precision(filters.get("company") if filters else None)

    gl_entries = get_gl_entries(filters, precision)

    valid_docs = set(d.voucher_no for d in gl_entries)

    valid_docs.update(get_non_gl_docs(filters, valid_docs))

    graph, edges = build_graph(valid_docs)

    linked_docs = valid_docs | {e["from"] for e in edges} | {e["to"] for e in edges}

    supplier_map = get_supplier_map(linked_docs)

   
    doc_info_map = batch_fetch_doc_info(linked_docs)

   
    lcv_details = get_lcv_details(linked_docs)

    data = build_flows(
        gl_entries, graph, edges, valid_docs, supplier_map, precision, filters,
        doc_info_map, lcv_details,
    )

    data = append_journal_entries(data, gl_entries, precision)

    if filters and filters.get("supplier"):
        data = filter_by_supplier(data, filters.get("supplier"))

    data = append_total_row(data, precision)

    return data


def filter_by_supplier(data, supplier):
    """Keep whole groups together: a root row (component/JE) matches if
    its own supplier matches; if kept, all of its children come along
    regardless of what's in their own supplier field."""

    keep_ids = {
        d["id"] for d in data
        if not d.get("parent") and d.get("supplier") == supplier
    }

    return [
        d for d in data
        if (not d.get("parent") and d.get("supplier") == supplier)
        or (d.get("parent") in keep_ids)
    ]


def append_total_row(data, precision):
    """Grand total across whatever ROOT rows survive filtering, appended
    as the last row.

    IMPORTANT for the collapsible tree: only root-level rows
    (parent is None — i.e. component summaries and standalone JEs) are
    summed here. Voucher-wise child rows (parent = "comp-N") already
    roll up into their parent's raw total in build_flows(), so summing
    them again here would double-count every linked voucher into the
    grand total.
    """

    total_debit = sum(
        (to_decimal_raw(d.get("_raw_debit", d.get("gl_debit")))
         for d in data if not d.get("parent")),
        Decimal(0),
    )
    total_credit = sum(
        (to_decimal_raw(d.get("_raw_credit", d.get("gl_credit")))
         for d in data if not d.get("parent")),
        Decimal(0),
    )

    data.append({
        "posting_date": "Total",
        "debit_date": None,
        "credit_date": None,
        "purchase_invoice": None,
        "purchase_receipt": None,
        "return_invoice": None,
        "return_pr": None,
        "purchase_order": None,
        "case": None,
        "supplier": None,
        "supplier_name": None,
        "gl_debit": float(round_decimal(total_debit, precision)),
        "gl_credit": float(round_decimal(total_credit, precision)),
        "net_impact": float(round_decimal(total_debit - total_credit, precision)),
        "je": None,
        "id": "grand-total",
        "parent": None,
        "indent": 0,
        "edges": [],
        "remarks": "",
        "is_rounding_only": False,
        "has_srv_impact": None,
    })

    # Hidden raw values were only needed to compute totals exactly;
    # strip them so they don't show up as stray columns in the report.
    for row in data:
        row.pop("_raw_debit", None)
        row.pop("_raw_credit", None)

    return data


def get_supplier_map(valid_docs):
    if not valid_docs:
        return {}

    doc_tuple = tuple(valid_docs)
    if len(doc_tuple) == 1:
        doc_tuple = f"('{doc_tuple[0]}')"

    rows = frappe.db.sql(f"""
        SELECT name, supplier, supplier_name, is_return, 'Purchase Invoice' AS doctype
        FROM `tabPurchase Invoice`
        WHERE name IN {doc_tuple}
        UNION
        SELECT name, supplier, supplier_name, is_return, 'Purchase Receipt' AS doctype
        FROM `tabPurchase Receipt`
        WHERE name IN {doc_tuple}
    """, as_dict=1)

    return {
        r.name: {
            "supplier": r.supplier,
            "supplier_name": r.supplier_name,
            "is_return": bool(r.is_return),
            "doctype": r.doctype,
        }
        for r in rows
    }


def get_non_gl_docs(filters, existing_docs):
    """Candidate PI/PR names within the date range that DIDN'T show up
    via GL Entry on the filtered account (e.g. a PI whose own GL hits
    Creditors, not this clearing account, but that still needs to be
    considered as a link target for a PR that DID hit this account).

    Scoped to `filters.company` (else every page load scans PR/PI
    across every company in the system) and combined into one query
    instead of two separate frappe.get_all() calls.
    """
    if not filters.get("company"):
        return set()

    rows = frappe.db.sql("""
        SELECT name FROM `tabPurchase Receipt`
        WHERE company = %(company)s AND docstatus = 1
          AND posting_date BETWEEN %(from_date)s AND %(to_date)s
        UNION
        SELECT name FROM `tabPurchase Invoice`
        WHERE company = %(company)s AND docstatus = 1
          AND posting_date BETWEEN %(from_date)s AND %(to_date)s
    """, filters, as_dict=0)

    return {r[0] for r in rows if r[0] not in existing_docs}


def get_gl_entries(filters, precision):
    conditions = """
        company = %(company)s
        AND account = %(account)s
        AND is_cancelled = 0
        AND posting_date BETWEEN %(from_date)s AND %(to_date)s
    """

    if not filters.get("show_opening_entries"):
        conditions += " AND (is_opening != 'Yes' OR is_opening IS NULL)"

    if not filters.get("finance_book"):
        conditions += " AND (finance_book IS NULL OR finance_book = '')"
    else:
        conditions += " AND (finance_book = %(finance_book)s OR finance_book IS NULL OR finance_book = '')"

    # Optional filters
    if filters.get("plant"):
        conditions += " AND branch = %(plant)s"

    rows = frappe.db.sql(f"""
        SELECT voucher_type, voucher_no,
               posting_date,
               SUM(debit) AS debit,
               SUM(credit) AS credit
        FROM `tabGL Entry`
        WHERE {conditions}
        GROUP BY voucher_type, voucher_no, posting_date
    """, filters, as_dict=1)


    for r in rows:
        r.debit = to_decimal_raw(r.debit)
        r.credit = to_decimal_raw(r.credit)

    return rows


def build_graph(valid_docs):

    graph = defaultdict(set)
    edges = []
    seen_edges = set()

    def link(a, b, a_type, b_type, rel_label):
        if not (a and b):
            return

        graph[a].add(b)
        graph[b].add(a)

        edge_key = (a, b, rel_label)
        if edge_key in seen_edges:
            return
        seen_edges.add(edge_key)

        edges.append({
            "from": a,
            "from_type": a_type,
            "to": b,
            "to_type": b_type,
            "type": rel_label,
        })

    if not valid_docs:
        return graph, edges

    def fmt(names):
        t = tuple(names)
        return f"('{t[0]}')" if len(t) == 1 else t

    known = set(valid_docs)
    frontier = set(valid_docs)

    while frontier:
        doc_tuple = fmt(frontier)
        newly_found = set()

        def discovered(*docs):
            for d in docs:
                if d and d not in known:
                    newly_found.add(d)

        for r in frappe.db.sql(f"""
            SELECT DISTINCT parent AS pi, purchase_receipt AS pr
            FROM `tabPurchase Invoice Item`
            WHERE purchase_receipt IS NOT NULL
              AND (parent IN {doc_tuple} OR purchase_receipt IN {doc_tuple})
        """, as_dict=1):
            link(r.pi, r.pr, "PI", "PR", "PI-PR")
            discovered(r.pi, r.pr)

        # PR ↔ RETURN PR
        for r in frappe.db.sql(f"""
            SELECT name AS return_pr, return_against AS pr
            FROM `tabPurchase Receipt`
            WHERE is_return = 1
              AND return_against IS NOT NULL
              AND (name IN {doc_tuple} OR return_against IN {doc_tuple})
        """, as_dict=1):
            link(r.pr, r.return_pr, "PR", "Return PR", "PR-RETURN_PR")
            discovered(r.pr, r.return_pr)

        # RETURN PR ↔ RETURN PI (Debit Note raised against the Return PR)
        for r in frappe.db.sql(f"""
            SELECT DISTINCT pii.purchase_receipt AS return_pr, pii.parent AS return_pi
            FROM `tabPurchase Invoice Item` pii
            INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
            WHERE pi.is_return = 1
              AND (pii.parent IN {doc_tuple} OR pii.purchase_receipt IN {doc_tuple})
        """, as_dict=1):
            link(r.return_pr, r.return_pi, "Return PR", "Return Invoice", "RETURN_PR-RETURN_PI")
            discovered(r.return_pr, r.return_pi)

        # PI ↔ RETURN PI (Debit Note raised directly against the PI)
        for r in frappe.db.sql(f"""
            SELECT name AS return_pi, return_against AS pi
            FROM `tabPurchase Invoice`
            WHERE is_return = 1
              AND return_against IS NOT NULL
              AND (name IN {doc_tuple} OR return_against IN {doc_tuple})
        """, as_dict=1):
            link(r.pi, r.return_pi, "PI", "Return Invoice", "PI-RETURN_PI")
            discovered(r.pi, r.return_pi)

        # LCV ↔ PR (one LCV can distribute cost across several PRs —
        # that's a genuine link, those PRs belong in the same group)
        for r in frappe.db.sql(f"""
            SELECT DISTINCT parent AS lcv, receipt_document AS pr
            FROM `tabLanded Cost Purchase Receipt`
            WHERE receipt_document_type = 'Purchase Receipt'
              AND receipt_document IS NOT NULL
              AND (parent IN {doc_tuple} OR receipt_document IN {doc_tuple})
        """, as_dict=1):
            link(r.lcv, r.pr, "LCV", "PR", "LCV-PR")
            discovered(r.lcv, r.pr)

        # PR ↔ PO — intentionally one-directional (PR side only) and
        # the PO is never added to `newly_found`, so a shared PO never
        # becomes a bridge that merges unrelated PR chains together.
        for r in frappe.db.sql(f"""
            SELECT DISTINCT parent AS pr, purchase_order AS po
            FROM `tabPurchase Receipt Item`
            WHERE purchase_order IS NOT NULL
              AND purchase_order != ''
              AND parent IN {doc_tuple}
        """, as_dict=1):
            link(r.pr, r.po, "PR", "PO", "PR-PO")

        known.update(newly_found)
        frontier = newly_found

    for doc in valid_docs:
        if doc not in graph:
            graph[doc] = set()

    return graph, edges


def get_connected_components(graph):
    visited = set()
    components = []

    for node in graph:
        if node in visited:
            continue

        stack = [node]
        comp = set()

        while stack:
            n = stack.pop()

            if n in visited:
                continue

            visited.add(n)
            comp.add(n)

            for nbr in graph.get(n, []):
                if nbr not in visited:
                    stack.append(nbr)

        components.append(comp)

    return components


def get_rate_difference_prs(prs, tolerance=0.01):
    if not prs:
        return set()

    doc_tuple = tuple(prs)
    if len(doc_tuple) == 1:
        doc_tuple = f"('{doc_tuple[0]}')"

    try:
        rows = frappe.db.sql(f"""
            SELECT pri.parent AS pr, pri.rate AS pr_rate, poi.rate AS po_rate
            FROM `tabPurchase Receipt Item` pri
            INNER JOIN `tabPurchase Order Item` poi ON poi.name = pri.purchase_order_item
            WHERE pri.parent IN {doc_tuple}
        """, as_dict=1)
    except Exception:
        frappe.log_error(title="SRV Clearing Analysis: rate-difference lookup failed")
        return set()

    diff_prs = set()
    for r in rows:
        if r.po_rate is None or r.pr_rate is None:
            continue
        if abs(flt(r.pr_rate) - flt(r.po_rate)) > tolerance:
            diff_prs.add(r.pr)

    return diff_prs


def batch_fetch_doc_info(doc_names):
    if not doc_names:
        return {}

    doc_tuple = tuple(doc_names)
    if len(doc_tuple) == 1:
        doc_tuple = f"('{doc_tuple[0]}')"

    info = {}
    for doctype, table in (
        ("Purchase Receipt", "tabPurchase Receipt"),
        ("Purchase Invoice", "tabPurchase Invoice"),
        ("Landed Cost Voucher", "tabLanded Cost Voucher"),
    ):
        rows = frappe.db.sql(f"""
            SELECT name, posting_date FROM `{table}` WHERE name IN {doc_tuple}
        """, as_dict=1)
        for r in rows:
            info[r.name] = {"doctype": doctype, "posting_date": r.posting_date}

    return info


def get_lcv_details(doc_names):
    if not doc_names:
        return {}

    doc_tuple = tuple(doc_names)
    if len(doc_tuple) == 1:
        doc_tuple = f"('{doc_tuple[0]}')"

    amount_rows = frappe.db.sql(f"""
        SELECT name, total_taxes_and_charges
        FROM `tabLanded Cost Voucher`
        WHERE name IN {doc_tuple}
    """, as_dict=1)

    if not amount_rows:
        return {}

    desc_rows = frappe.db.sql(f"""
        SELECT parent, GROUP_CONCAT(DISTINCT description SEPARATOR ', ') AS description
        FROM `tabLanded Cost Taxes and Charges`
        WHERE parent IN {doc_tuple}
        GROUP BY parent
    """, as_dict=1)
    desc_map = {r.parent: r.description for r in desc_rows}

    return {
        r.name: {
            "amount": to_decimal_raw(r.total_taxes_and_charges),
            "description": desc_map.get(r.name) or "",
        }
        for r in amount_rows
    }


def get_excluded_doc_remarks(chain_excluded_docs, filters, doc_info_map):
    if not chain_excluded_docs:
        return []

    from_date = filters.get("from_date") if filters else None
    to_date = filters.get("to_date") if filters else None

    remarks = []

    for doc in chain_excluded_docs:
        info = doc_info_map.get(doc)
        doctype = info["doctype"] if info else None
        posting_date = info["posting_date"] if info else None

        if not doctype:
            remarks.append(
                f"{doc}: linked to this chain but the document could not be found — "
                f"it may have been cancelled, renamed, or deleted."
            )
            continue

        if posting_date and from_date and to_date and not (str(from_date) <= str(posting_date) <= str(to_date)):
            remarks.append(
                f"{doctype} {doc} exists (dated {posting_date}) but falls outside the "
                f"selected date range ({from_date} to {to_date}) — that's why it shows "
                f"zero above; widen the date range to see its impact."
            )
        else:
            remarks.append(
                f"{doctype} {doc} is linked to this chain but never posts to the "
                f"filtered account (e.g. a Return Purchase Receipt only reverses stock) "
                f"— its zero here is expected."
            )

    return remarks


def compute_chain_remarks(pi, pr_docs, lcv_docs, pi_debit_note_docs, return_pr_docs,
                           return_debit_note_docs, rate_diff, chain_net, precision,
                           chain_excluded_docs, filters, doc_info_map, lcv_details=None):
    tolerance = Decimal(1).scaleb(-precision)

    if abs(chain_net) < tolerance:
        return []

    if abs(chain_net) <= ROUNDING_ONLY_THRESHOLD:
        return [
            f"PI {pi}: debit and credit differ by less than {ROUNDING_ONLY_THRESHOLD} "
            f"— almost certainly rounding drift, not a missing document."
        ]

    remarks = []

    # No PR linked to this PI at all — the invoice was booked without a
    # linked receipt (or the link hasn't been made yet).
    if not pr_docs:
        remarks.append(
            f"PI {pi}: no Purchase Receipt is linked to this Purchase Invoice — "
            f"{float(chain_net):,.2f} isn't reconciled against any PR in SRV."
        )
        remarks.extend(get_excluded_doc_remarks(chain_excluded_docs, filters, doc_info_map))
        return remarks

    pr_label = ", ".join(sorted(pr_docs))

    # A PO/PR rate mismatch was detected on the linked PR but no LCV has
    # even been raised yet to record it.
    if rate_diff and not lcv_docs:
        remarks.append(
            f"PI {pi}: PO rate differs from the PR rate on {pr_label} but no Landed "
            f"Cost Voucher (LCV) has been raised to record it yet."
        )

    if lcv_docs:
        negative_lcvs, positive_lcvs = [], []
        for lcv in sorted(set(lcv_docs)):
            info = (lcv_details or {}).get(lcv, {})
            amt = info.get("amount", Decimal(0))
            desc = info.get("description") or "Landed Cost Voucher"
            label = f"{lcv} ({desc}: {float(amt):,.2f})"
            if amt < 0:
                negative_lcvs.append(label)
            elif amt > 0:
                positive_lcvs.append(label)
            # amt == 0: nothing meaningful to say either way.

        if negative_lcvs and not pi_debit_note_docs:
            remarks.append(
                f"PI {pi}: {', '.join(negative_lcvs)} reduced {pr_label}'s valuation "
                f"(vendor owes money back), but no Debit Note has been raised against "
                f"this PI to pass that reduction through to SRV — SRV is still "
                f"carrying the pre-LCV rate."
            )

        if positive_lcvs:
            remarks.append(
                f"PI {pi}: {', '.join(positive_lcvs)} increased {pr_label}'s "
                f"valuation — this is an additional amount payable to the vendor, "
                f"absorbed directly into the PR/PI valuation; no Debit Note is "
                f"expected for this part."
            )

        if len(negative_lcvs) > 1:
            remarks.append(
                f"PI {pi}: {len(negative_lcvs)} reducing LCVs raised against "
                f"{pr_label} ({', '.join(negative_lcvs)}) — if only one has a "
                f"matching Debit Note vs this PI, the other's reduction is still "
                f"sitting un-passed-through to SRV."
            )

    if return_pr_docs and not return_debit_note_docs:
        remarks.append(
            f"PI {pi}: Return PR ({', '.join(sorted(set(return_pr_docs)))}) against "
            f"{pr_label} has reversed the rejected quantity in stock, but no Return "
            f"Invoice / Debit Note has been raised against it — SRV still carries the "
            f"full original PR amount, including the rejected quantity."
        )

    if not remarks:
        remarks.append(
            f"PI {pi}: linked PR(s) ({pr_label}) don't fully clear this PI "
            f"({float(chain_net):,.2f} remaining) — check for partial billing or a "
            f"rate/quantity mismatch between the PI and PR."
        )

    remarks.extend(get_excluded_doc_remarks(chain_excluded_docs, filters, doc_info_map))

    if not remarks:
        remarks.append(
            f"PI {pi}: all expected vouchers for this chain appear to be present, but "
            f"it still doesn't net to zero ({float(chain_net):,.2f}) — check for an "
            f"amount mismatch, a partial billing/receipt, or a voucher cancelled or "
            f"amended after this analysis."
        )

    return remarks


def build_flows(gl_entries, graph, edges, valid_docs, supplier_map, precision, filters,
                 doc_info_map, lcv_details=None):

    lcv_details = lcv_details or {}

    voucher_index = defaultdict(list)

    for d in gl_entries:
        if d.voucher_type == "Journal Entry":
            continue

        voucher_index[d.voucher_no].append({
            "voucher_type": d.voucher_type,
            "posting_date": d.posting_date,
            "debit": d.debit,
            "credit": d.credit
        })

    components = get_connected_components(graph)

    result = []
    processed_docs = set()
    comp_counter = 0

    for comp in components:

        if not any(doc in valid_docs for doc in comp):
            continue

        comp_counter += 1
        parent_id = f"comp-{comp_counter}"

        pis, prs, rpis, rprs, lcvs = set(), set(), set(), set(), set()

        total_debit = Decimal(0)
        total_credit = Decimal(0)

        comp_edges = [
            e for e in edges
            if e["from"] in comp and e["to"] in comp
        ]

        po_docs = sorted({
            e["to"] for e in comp_edges if e["to_type"] == "PO"
        } | {
            e["from"] for e in comp_edges if e["from_type"] == "PO"
        })

        node_role_hint = {}
        for e in comp_edges:
            node_role_hint.setdefault(e["from"], e["from_type"])
            node_role_hint.setdefault(e["to"], e["to_type"])

        children = []
        child_by_doc = {}
        excluded_docs = []
        has_real_entry = False

        for doc in comp:

            if doc in processed_docs:
                continue

            processed_docs.add(doc)

            if doc in po_docs:
                continue

            entries = voucher_index.get(doc)

            if entries:
                has_real_entry = True

                voucher_debit = Decimal(0)
                voucher_credit = Decimal(0)
                voucher_dates = set()
                debit_dates = set()
                credit_dates = set()
                voucher_type = entries[0]["voucher_type"]

                for e in entries:
                    voucher_debit += e["debit"]
                    voucher_credit += e["credit"]
                    voucher_dates.add(e["posting_date"])

                    if e["debit"]:
                        debit_dates.add(e["posting_date"])
                    if e["credit"]:
                        credit_dates.add(e["posting_date"])

                    total_debit += e["debit"]
                    total_credit += e["credit"]

                info = supplier_map.get(doc, {})
                is_return = bool(info.get("is_return"))
                no_gl_impact = False

            else:
                info = supplier_map.get(doc, {})
                voucher_type = info.get("doctype")

                if not voucher_type:
                    role = node_role_hint.get(doc)
                    if role == "LCV":
                        voucher_type = "Landed Cost Voucher"
                    elif role in ("PR", "Return PR"):
                        voucher_type = "Purchase Receipt"
                    elif role in ("PI", "Return Invoice"):
                        voucher_type = "Purchase Invoice"

                if not voucher_type:
                    excluded_docs.append(doc)
                    continue

                is_return = bool(info.get("is_return")) or node_role_hint.get(doc) in (
                    "Return PR", "Return Invoice",
                )
                no_gl_impact = True

                voucher_debit = Decimal(0)
                voucher_credit = Decimal(0)
                voucher_dates = set()
                debit_dates = set()
                credit_dates = set()

                excluded_docs.append(doc)

            if voucher_type == "Purchase Invoice":
                (rpis if is_return else pis).add(doc)
            elif voucher_type == "Purchase Receipt":
                (rprs if is_return else prs).add(doc)
            elif voucher_type == "Landed Cost Voucher":
                lcvs.add(doc)

    
            lcv_info = lcv_details.get(doc) if voucher_type == "Landed Cost Voucher" else None

            children.append({
                "posting_date": ", ".join(sorted(str(d) for d in voucher_dates)),
                "debit_date": ", ".join(sorted(str(d) for d in debit_dates)),
                "credit_date": ", ".join(sorted(str(d) for d in credit_dates)),
                "purchase_invoice": doc if (voucher_type == "Purchase Invoice" and not is_return) else None,
                "purchase_receipt": doc if (voucher_type == "Purchase Receipt" and not is_return) else None,
                "return_invoice": doc if (voucher_type == "Purchase Invoice" and is_return) else None,
                "return_pr": doc if (voucher_type == "Purchase Receipt" and is_return) else None,
                "lcv": doc if voucher_type == "Landed Cost Voucher" else None,
                "lcv_description": lcv_info.get("description") if lcv_info else None,
                "lcv_amount": float(round_decimal(lcv_info["amount"], precision)) if lcv_info else None,
                "lcv_direction": (
                    ("Reduces valuation (vendor owes back)" if lcv_info["amount"] < 0
                     else "Increases valuation (payable to vendor)" if lcv_info["amount"] > 0
                     else None)
                    if lcv_info else None
                ),
                "supplier": info.get("supplier"),
                "supplier_name": info.get("supplier_name"),
                "gl_debit": float(round_decimal(voucher_debit, precision)),
                "gl_credit": float(round_decimal(voucher_credit, precision)),
                "net_impact": float(round_decimal(voucher_debit - voucher_credit, precision)),
                "je": None,
                "id": f"{parent_id}-{doc}",
                "parent": parent_id,
                "indent": 1,
                "case": None,
                "remarks": "",
                "no_gl_impact": no_gl_impact,
            })
            child_by_doc[doc] = children[-1]

        if not (pis or prs or rpis or rprs or lcvs):
            continue

        rate_diff_prs = get_rate_difference_prs(prs)
        chain_remarks_all = []


        edges_by_to = defaultdict(lambda: defaultdict(list))
        edges_by_from = defaultdict(lambda: defaultdict(list))
        for e in comp_edges:
            edges_by_to[e["type"]][e["to"]].append(e["from"])
            edges_by_from[e["type"]][e["from"]].append(e["to"])


        for pr_doc in prs:
            flags = []
            if edges_by_to["LCV-PR"].get(pr_doc):
                flags.append("Rate Difference")
            if edges_by_from["PR-RETURN_PR"].get(pr_doc):
                flags.append("Rejected")
            case = " + ".join(flags) if flags else "Rate Matched"
            pr_child = child_by_doc.get(pr_doc)
            if pr_child:
                pr_child["case"] = case


        prs_covered_by_a_pi = set()

        for pi_doc in pis:
            pi_child = child_by_doc.get(pi_doc)

            pr_docs = list(dict.fromkeys(edges_by_from["PI-PR"].get(pi_doc, [])))
            prs_covered_by_a_pi.update(pr_docs)

            lcv_docs = list(dict.fromkeys(
                d for pr in pr_docs for d in edges_by_to["LCV-PR"].get(pr, [])
            ))
            pi_debit_note_docs = list(dict.fromkeys(
                edges_by_from["PI-RETURN_PI"].get(pi_doc, [])
            ))
            return_pr_docs = list(dict.fromkeys(
                d for pr in pr_docs for d in edges_by_from["PR-RETURN_PR"].get(pr, [])
            ))
            return_debit_note_docs = list(dict.fromkeys(
                d for rpr in return_pr_docs for d in edges_by_from["RETURN_PR-RETURN_PI"].get(rpr, [])
            ))

            chain_docs = (
                {pi_doc} | set(pr_docs) | set(lcv_docs)
                | set(pi_debit_note_docs) | set(return_pr_docs) | set(return_debit_note_docs)
            )

            chain_net = sum(
                (
                    Decimal(str(child_by_doc[d]["gl_debit"])) - Decimal(str(child_by_doc[d]["gl_credit"]))
                    for d in chain_docs if d in child_by_doc
                ),
                Decimal(0),
            )

            chain_excluded_docs = [
                d for d in chain_docs
                if child_by_doc.get(d, {}).get("no_gl_impact")
            ]

            rate_diff_here = bool(set(pr_docs) & rate_diff_prs)

            pi_remarks = compute_chain_remarks(
                pi_doc, pr_docs, lcv_docs, pi_debit_note_docs, return_pr_docs,
                return_debit_note_docs, rate_diff_here, chain_net, precision,
                chain_excluded_docs, filters, doc_info_map, lcv_details,
            )

            if pi_child and pi_remarks:
                pi_child["remarks"] = "\n".join(pi_remarks)
                chain_remarks_all.extend(pi_remarks)

        tolerance = Decimal(1).scaleb(-precision)

        for pr_doc in prs:
            if pr_doc in prs_covered_by_a_pi:
                continue

            pr_child = child_by_doc.get(pr_doc)
            pr_net = (
                Decimal(str(pr_child["gl_debit"])) - Decimal(str(pr_child["gl_credit"]))
                if pr_child else Decimal(0)
            )

            if abs(pr_net) < tolerance:
                continue

            remark = (
                f"PR {pr_doc}: no Purchase Invoice has been booked against this PR yet — "
                f"the full amount ({float(pr_net):,.2f}) is sitting unbilled in SRV."
            )
            if pr_child:
                pr_child["remarks"] = remark
            chain_remarks_all.append(remark)

        supplier = None
        supplier_name = None

        for doc in pis | prs | rpis | rprs | lcvs:
            info = supplier_map.get(doc)
            if info:
                supplier = info.get("supplier")
                supplier_name = info.get("supplier_name")
                break

        net_impact_dec = total_debit - total_credit
        remarks = chain_remarks_all

        if not has_real_entry:
            no_impact_docs = ", ".join(sorted(pis | prs | rpis | rprs | lcvs))
            remarks = [
                f"{no_impact_docs}: no document in this chain posted to the SRV "
                f"account for the selected filters — zero SRV impact."
            ]

        result.append({
            "posting_date": None,
            "debit_date": None,
            "credit_date": None,
            "purchase_invoice": None,
            "purchase_receipt": None,
            "return_invoice": None,
            "return_pr": None,
            "lcv": None,
            "purchase_order": ", ".join(po_docs) if po_docs else None,
            "case": None,
            "supplier": supplier,
            "supplier_name": supplier_name,
            "gl_debit": float(round_decimal(total_debit, precision)),
            "gl_credit": float(round_decimal(total_credit, precision)),
            "net_impact": float(round_decimal(net_impact_dec, precision)),
            "je": None,
            "id": parent_id,
            "parent": None,
            "indent": 0,
            "edges": comp_edges,
            "remarks": "\n".join(remarks),
            "is_rounding_only": 0 < abs(net_impact_dec) <= ROUNDING_ONLY_THRESHOLD,
            "has_srv_impact": has_real_entry,
            "_raw_debit": total_debit,
            "_raw_credit": total_credit,
        })

        result.extend(children)

    return result


def append_journal_entries(flows, gl_entries, precision):

    je_map = {}

    for d in gl_entries:
        if d.voucher_type != "Journal Entry":
            continue

        key = (d.voucher_no, d.posting_date)

        je_map.setdefault(key, {"debit": Decimal(0), "credit": Decimal(0)})
        je_map[key]["debit"] += d.debit
        je_map[key]["credit"] += d.credit

    for (je, dt), val in je_map.items():
        flows.append({
            "posting_date": dt,
            "debit_date": dt if val["debit"] else None,
            "credit_date": dt if val["credit"] else None,
            "purchase_invoice": None,
            "purchase_receipt": None,
            "return_pr": None,
            "return_invoice": None,
            "purchase_order": None,
            "case": None,
            "supplier": None,
            "supplier_name": None,
            "gl_debit": float(round_decimal(val["debit"], precision)),
            "gl_credit": float(round_decimal(val["credit"], precision)),
            "net_impact": float(round_decimal(val["debit"] - val["credit"], precision)),
            "je": je,
            "id": f"je-{je}-{dt}",
            "parent": None,
            "indent": 0,
            "edges": [],
            "remarks": "",
            "is_rounding_only": False,
            "has_srv_impact": True,
        })

    return flows