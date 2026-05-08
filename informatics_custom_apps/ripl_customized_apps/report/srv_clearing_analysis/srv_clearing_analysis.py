# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from collections import defaultdict
from frappe.utils import flt


def execute(filters=None):
    columns = get_columns()

    gl_entries = get_gl_entries(filters)

    valid_docs = set(d.voucher_no for d in gl_entries)

    graph = build_graph(valid_docs)

    data = build_flows(gl_entries, graph, valid_docs)

    data = append_journal_entries(data, gl_entries)

    data = [
        d for d in data
        if abs(d.get("net_impact") or 0) > 1
    ]

    return columns, data


def get_columns():
    return [
        {
            "label": "Posting Date", 
            "fieldname": "posting_date", 
            "fieldtype": "Date", 
            "width": 120
            },
        {
            "label": "Purchase Invoice", 
            "fieldname": "purchase_invoice", 
            "fieldtype": "Link", 
            "options": "Purchase Invoice", 
            "width": 320
            },
        {
            "label": "Purchase Receipt", 
            "fieldname": "purchase_receipt", 
            "fieldtype": "Link", 
            "options": "Purchase Receipt", 
            "width": 320
            },
        {
            "label": "GL Debit", 
            "fieldname": "gl_debit", 
            "fieldtype": "Currency", 
            "width": 240
            },
        {
            "label": "GL Credit", 
            "fieldname": "gl_credit", 
            "fieldtype": "Currency", 
            "width": 240
            },
        {
            "label": "Net Impact", 
            "fieldname": "net_impact", 
            "fieldtype": "Currency", 
            "width": 240
            },
        {
            "label": "JE", 
            "fieldname": "je", 
            "fieldtype": "Link", 
            "options": "Journal Entry", 
            "width": 320
            }
    ]


def get_gl_entries(filters):
    conditions = """
        company = %(company)s
        AND account = %(account)s
        AND is_cancelled = 0
        AND posting_date BETWEEN %(from_date)s AND %(to_date)s
    """

    # Optional filters
    if filters.get("plant"):
        conditions += " AND branch = %(plant)s"

    if filters.get("segment"):
        conditions += " AND segment = %(segment)s"

    return frappe.db.sql(f"""
        SELECT voucher_type, voucher_no,
               posting_date,
               SUM(debit) AS debit,
               SUM(credit) AS credit
        FROM `tabGL Entry`
        WHERE {conditions}
        GROUP BY voucher_type, voucher_no, posting_date
    """, filters, as_dict=1)


def build_graph(valid_docs):

    graph = defaultdict(set)

    def link(a, b):
        if a and b:
            graph[a].add(b)
            graph[b].add(a)

    if not valid_docs:
        return graph

    doc_tuple = tuple(valid_docs)

    # PI ↔ PR
    data = frappe.db.sql(f"""
        SELECT parent AS pi, purchase_receipt AS pr
        FROM `tabPurchase Invoice Item`
        WHERE purchase_receipt IS NOT NULL
          AND parent IN {doc_tuple}
    """, as_dict=1)

    for r in data:
        link(r.pi, r.pr)

    # PR ↔ RETURN PR
    data = frappe.db.sql(f"""
        SELECT name AS return_pr, return_against AS pr
        FROM `tabPurchase Receipt`
        WHERE is_return = 1
          AND return_against IS NOT NULL
          AND (name IN {doc_tuple} OR return_against IN {doc_tuple})
    """, as_dict=1)

    for r in data:
        link(r.pr, r.return_pr)

    # RETURN PR ↔ RETURN PI
    data = frappe.db.sql(f"""
        SELECT pii.purchase_receipt AS return_pr, pii.parent AS return_pi
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
        WHERE pi.is_return = 1
          AND (pii.parent IN {doc_tuple} OR pii.purchase_receipt IN {doc_tuple})
    """, as_dict=1)

    for r in data:
        link(r.return_pr, r.return_pi)

    # PI ↔ RETURN PI
    data = frappe.db.sql(f"""
        SELECT name AS return_pi, return_against AS pi
        FROM `tabPurchase Invoice`
        WHERE is_return = 1
          AND return_against IS NOT NULL
          AND (name IN {doc_tuple} OR return_against IN {doc_tuple})
    """, as_dict=1)

    for r in data:
        link(r.pi, r.return_pi)

    for doc in valid_docs:
        if doc not in graph:
            graph[doc] = set()

    return graph


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

def build_flows(gl_entries, graph, valid_docs):

    voucher_index = defaultdict(list)

    for d in gl_entries:
        if d.voucher_type == "Journal Entry":
            continue

        voucher_index[d.voucher_no].append({
            "voucher_type": d.voucher_type,
            "posting_date": d.posting_date,
            "debit": flt(d.debit),
            "credit": flt(d.credit)
        })

    components = get_connected_components(graph)

    result = []

    processed_docs = set()

    for comp in components:

        if not any(doc in valid_docs for doc in comp):
            continue

        pis, prs, rpis, rprs = set(), set(), set(), set()

        total_debit = 0
        total_credit = 0

        component_dates = set()

        for doc in comp:

            if doc in processed_docs:
                continue

            processed_docs.add(doc)

            entries = voucher_index.get(doc)
            if not entries:
                continue

            for e in entries:

                total_debit += e["debit"]
                total_credit += e["credit"]

                component_dates.add(e["posting_date"])

                vt = e["voucher_type"]

                if vt == "Purchase Invoice":
                    if "Return" in doc:
                        rpis.add(doc)
                    else:
                        pis.add(doc)

                elif vt == "Purchase Receipt":
                    if "Return" in doc:
                        rprs.add(doc)
                    else:
                        prs.add(doc)

        result.append({
            "posting_date": ", ".join(sorted(str(d) for d in component_dates)),
            "purchase_invoice": ", ".join(sorted(pis)) or None,
            "purchase_receipt": ", ".join(sorted(prs)) or None,
            "return_invoice": ", ".join(sorted(rpis)) or None,
            "return_pr": ", ".join(sorted(rprs)) or None,
            "gl_debit": total_debit,
            "gl_credit": total_credit,
            "net_impact": total_debit - total_credit
        })

    return result

def append_journal_entries(flows, gl_entries):

    je_map = {}

    for d in gl_entries:
        if d.voucher_type != "Journal Entry":
            continue

        key = (d.voucher_no, d.posting_date)

        je_map.setdefault(key, {"debit": 0, "credit": 0})
        je_map[key]["debit"] += flt(d.debit)
        je_map[key]["credit"] += flt(d.credit)

    for (je, dt), val in je_map.items():
        flows.append({
            "posting_date": dt,
            "purchase_invoice": None,
            "purchase_receipt": None,
            "return_pr": None,
            "return_invoice": None,
            "gl_debit": val["debit"],
            "gl_credit": val["credit"],
            "net_impact": val["debit"] - val["credit"],
            "je": je
        })

    return flows