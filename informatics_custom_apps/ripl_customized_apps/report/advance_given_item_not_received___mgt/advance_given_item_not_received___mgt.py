import frappe
import json
from frappe.utils import flt


DRILL_GROUP_DELIMITER = "|||"

QUALIFYING_PENDING_PO_SUBQUERY = """
    po.name IN (
        SELECT pl.po_name
        FROM (
            SELECT
                p.name AS po_name,
                adv.advance_paid AS advance_paid,
                IFNULL(rec.received_amount, 0) AS received_amount
            FROM `tabPurchase Order` p
            INNER JOIN (
                SELECT per.reference_name AS po_name, SUM(per.allocated_amount) AS advance_paid
                FROM `tabPayment Entry Reference` per
                INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
                WHERE per.reference_doctype = 'Purchase Order'
                  AND pe.docstatus = 1
                  AND pe.payment_type = 'Pay'
                GROUP BY per.reference_name
            ) adv ON adv.po_name = p.name
            LEFT JOIN (
                SELECT pri.purchase_order AS po_name, SUM(pri.base_amount) AS received_amount
                FROM `tabPurchase Receipt Item` pri
                INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
                WHERE pr.docstatus = 1
                  -- Exclude return receipts entirely (negative amounts) -
                  -- goods sent back are not counted as received at all
                  AND IFNULL(pr.is_return, 0) = 0
                GROUP BY pri.purchase_order
            ) rec ON rec.po_name = p.name
            WHERE p.docstatus = 1
              -- Exclude POs that are already fully received (by qty),
              -- regardless of how the value-based advance/received compare.
              AND ROUND(IFNULL(p.per_received, 0), 2) < 100
        ) pl
        WHERE pl.received_amount < pl.advance_paid
    )
"""

# Reusable PO-level joins so every drilldown can expose the same
# "Pending Amount" and "Taxes / Extra Charges" figures consistently.
# Each expects the outer query to have a `po` alias for `tabPurchase Order`.

PO_ADVANCE_JOIN = """
    INNER JOIN (
        SELECT per.reference_name AS po_name, SUM(per.allocated_amount) AS advance_paid
        FROM `tabPayment Entry Reference` per
        INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
        WHERE per.reference_doctype = 'Purchase Order'
          AND pe.docstatus = 1
          AND pe.payment_type = 'Pay'
        GROUP BY per.reference_name
    ) adv ON adv.po_name = po.name
"""

PO_RECEIVED_JOIN = """
    LEFT JOIN (
        SELECT pri.purchase_order AS po_name, SUM(pri.base_amount) AS received_amount
        FROM `tabPurchase Receipt Item` pri
        INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
        WHERE pr.docstatus = 1
          -- Exclude return receipts entirely (negative amounts) -
          -- goods sent back are not counted as received at all
          AND IFNULL(pr.is_return, 0) = 0
        GROUP BY pri.purchase_order
    ) rec ON rec.po_name = po.name
"""

PO_TAXES_JOIN = """
    LEFT JOIN (
        SELECT ptc.parent AS po_name, SUM(ptc.base_tax_amount) AS taxes
        FROM `tabPurchase Taxes and Charges` ptc
        WHERE ptc.parenttype = 'Purchase Order'
        GROUP BY ptc.parent
    ) tax ON tax.po_name = po.name
"""


def split_drill_group(drill_group):
    """drill_group arrives as 'branch|||segment' (segment may be empty)."""
    if not drill_group:
        return "", ""
    if DRILL_GROUP_DELIMITER in drill_group:
        branch, segment = drill_group.split(DRILL_GROUP_DELIMITER, 1)
    else:
        branch, segment = drill_group, ""
    return branch, segment


def execute(filters=None):

    filters = frappe._dict(filters or {})
    drill_type = filters.get("drill_type")

    if filters.get("drill_group"):
        branch, segment = split_drill_group(filters.get("drill_group"))
        filters["drill_branch"] = branch
        filters["drill_segment"] = segment

    if drill_type == "advance_paid":
        return get_advance_drill_columns(), get_advance_drill_data(filters)

    if drill_type == "po_amount":
        return get_po_amount_drill_columns(), get_po_amount_drill_data(filters)

    if drill_type == "material_received":
        return get_received_drill_columns(), get_received_drill_data(filters)

    if drill_type == "pending":
        return get_pending_drill_columns(), get_pending_drill_data(filters)

    return get_summary_columns(), get_summary_data(filters)



def get_summary_columns():
    return [
        {
            "label": "Plant / Segment",
            "fieldname": "group_by",
            "fieldtype": "Data",
            "width": 220
        },
        {
            "label": "Total Advance Paid",
            "fieldname": "advance_paid",
            "fieldtype": "Currency",
            "width": 180
        },
        {
            "label": "PO Amount",
            "fieldname": "po_amount",
            "fieldtype": "Currency",
            "width": 180
        },
        {
            "label": "Material Received",
            "fieldname": "received_amount",
            "fieldtype": "Currency",
            "width": 180
        },
        {
            "label": "Pending Amount",
            "fieldname": "pending_amount",
            "fieldtype": "Currency",
            "width": 180
        },
    ]


def get_summary_data(filters):
    conditions = get_conditions(filters)

    data = frappe.db.sql(f"""
        SELECT
            po_level.branch AS branch,
            po_level.segment AS segment,

            SUM(po_level.po_amount) AS po_amount,
            SUM(po_level.advance_paid) AS advance_paid,
            SUM(po_level.received_amount) AS received_amount,

            SUM(
                po_level.advance_paid - po_level.received_amount
            ) AS pending_amount,

            COUNT(*) AS po_count

        FROM (
            SELECT
                po.name AS po_name,
                po.branch AS branch,
                IFNULL(po.segment, '') AS segment,

                -- PO Amount EXCLUDING TAX
                IFNULL((
                    SELECT SUM(poi.base_net_amount)
                    FROM `tabPurchase Order Item` poi
                    WHERE poi.parent = po.name
                ), 0) AS po_amount,

                -- Actual amount paid against PO.
                -- Payment Entry allocated amount includes taxes
                -- because it represents the actual payment allocation.
                IFNULL(adv.advance_paid, 0) AS advance_paid,

                -- Material received value
                -- compared against Advance Paid amount.
                IFNULL(rec.received_amount, 0) AS received_amount

            FROM `tabPurchase Order` po

            -- ONLY POs having at least one submitted
            -- Payment Entry against them
            INNER JOIN (
                SELECT
                    per.reference_name AS po_name,
                    SUM(per.allocated_amount) AS advance_paid

                FROM `tabPayment Entry Reference` per

                INNER JOIN `tabPayment Entry` pe
                    ON pe.name = per.parent

                WHERE per.reference_doctype = 'Purchase Order'
                    AND pe.docstatus = 1
                    AND pe.payment_type = 'Pay'

                GROUP BY per.reference_name

            ) adv
                ON adv.po_name = po.name

            LEFT JOIN (
                SELECT
                    pri.purchase_order AS po_name,

                    -- Received amount excluding tax
                    SUM(pri.base_amount) AS received_amount

                FROM `tabPurchase Receipt Item` pri

                INNER JOIN `tabPurchase Receipt` pr
                    ON pr.name = pri.parent

                WHERE pr.docstatus = 1
                    AND IFNULL(pri.purchase_order, '') != ''
                    -- Exclude return receipts entirely (negative amounts) -
                    -- goods sent back are not counted as received at all
                    AND IFNULL(pr.is_return, 0) = 0

                GROUP BY pri.purchase_order

            ) rec
                ON rec.po_name = po.name

            WHERE po.docstatus = 1
                -- Exclude POs that are already fully received (by qty)
                AND ROUND(IFNULL(po.per_received, 0), 2) < 100
                {conditions}

        ) po_level

        -- PO has advance payment AND
        -- material received value is less than the ADVANCE PAID
        -- (i.e. goods not yet received to the value of the advance).
        WHERE po_level.received_amount < po_level.advance_paid

        GROUP BY
            po_level.branch,
            po_level.segment

        ORDER BY pending_amount DESC

    """, filters, as_dict=True)

    for d in data:
        d["group_by"] = (
            f"{d['branch']} / {d['segment']}"
            if d.get("segment")
            else d["branch"]
        )

        d["drill_group"] = (
            f"{d['branch']}{DRILL_GROUP_DELIMITER}"
            f"{d.get('segment') or ''}"
        )

    # TOTAL row
    total_row = {
        "group_by": "TOTAL",
        "po_amount": sum(
            flt(d.get("po_amount"))
            for d in data
        ),
        "advance_paid": sum(
            flt(d.get("advance_paid"))
            for d in data
        ),
        "received_amount": sum(
            flt(d.get("received_amount"))
            for d in data
        ),
        "pending_amount": sum(
            flt(d.get("pending_amount"))
            for d in data
        ),
        "is_total_row": 1
    }

    return [total_row] + data


def get_advance_drill_columns():
    return [
        {
            "label": "Purchase Order",
            "fieldname": "purchase_order",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 230,
        },
        {
            "label": "PO Date",
            "fieldname": "po_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": "Supplier Name",
            "fieldname": "supplier_name",
            "fieldtype": "Data",
            "width": 300,
        },
        {
            "label": "P.O Amount",
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": "Taxes / Extra Charges",
            "fieldname": "taxes",
            "fieldtype": "Currency",
            "width": 170,
        },
        {
            "label": "Advance Paid Amount",
            "fieldname": "advance_amount",
            "fieldtype": "Currency",
            "width": 180,
        },
        {
            "label": "Material Received",
            "fieldname": "received_amount",
            "fieldtype": "Currency",
            "width": 150,
        },
        {
            "label": "Pending Amount",
            "fieldname": "pending_amount",
            "fieldtype": "Currency",
            "width": 140,
        },
        {
            "label": "Advance Paid Date",
            "fieldname": "advance_date",
            "fieldtype": "Date",
            "width": 160,
        },
    
    ]


def get_advance_drill_data(filters):
    conditions = get_conditions(filters)

    data = frappe.db.sql(f"""
        SELECT
            po.name AS purchase_order,
            po.transaction_date AS po_date,
            po.supplier_name AS supplier_name,
            po.grand_total AS amount,
            per.allocated_amount AS advance_amount,
            pe.posting_date AS advance_date,
            pe.name AS payment_entry,

            -- PO-level figures (same for every payment row of a given PO;
            -- de-duplicated per PO when totalling in Python below)
            IFNULL(tax.taxes, 0) AS taxes,
            IFNULL(rec.received_amount, 0) AS received_amount,
            (IFNULL(adv.advance_paid, 0) - IFNULL(rec.received_amount, 0)) AS pending_amount

        FROM `tabPayment Entry Reference` per
        INNER JOIN `tabPayment Entry` pe
            ON pe.name = per.parent
        INNER JOIN `tabPurchase Order` po
            ON po.name = per.reference_name
        {PO_ADVANCE_JOIN}
        {PO_RECEIVED_JOIN}
        {PO_TAXES_JOIN}

        WHERE per.reference_doctype = 'Purchase Order'
          AND pe.docstatus = 1
          AND pe.payment_type = 'Pay'
          AND po.docstatus = 1
          AND po.branch = %(drill_branch)s
          AND IFNULL(po.segment, '') = %(drill_segment)s
          AND {QUALIFYING_PENDING_PO_SUBQUERY}
        {conditions}

        ORDER BY po.transaction_date ASC, pe.posting_date ASC
    """, filters, as_dict=True)

    seen_pos = set()
    total_amount = 0
    total_advance = 0
    total_taxes = 0
    total_received = 0
    total_pending = 0
    for d in data:
        total_advance += flt(d.get("advance_amount"))
        if d["purchase_order"] not in seen_pos:
            seen_pos.add(d["purchase_order"])
            total_amount += flt(d.get("amount"))
            total_taxes += flt(d.get("taxes"))
            total_received += flt(d.get("received_amount"))
            total_pending += flt(d.get("pending_amount"))

    total_row = {
        "purchase_order": "TOTAL",
        "amount": total_amount,
        "taxes": total_taxes,
        "advance_amount": total_advance,
        "received_amount": total_received,
        "pending_amount": total_pending,
        "is_total_row": 1,
    }

    return [total_row] + data


def get_po_amount_drill_columns():
    return [
        {
            "label": "Purchase Order",
            "fieldname": "purchase_order",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 220
        },
        {
            "label": "PO Date",
            "fieldname": "po_date",
            "fieldtype": "Date",
            "width": 150
        },
        {
            "label": "Supplier",
            "fieldname": "supplier",
            "fieldtype": "Data",
            "width": 300
        },
        {
            "label": "Amount",
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 150
        },
        {
            "label": "Taxes / Extra Charges",
            "fieldname": "taxes",
            "fieldtype": "Currency",
            "width": 180
        },
        {
            "label": "Grand Total",
            "fieldname": "grand_total",
            "fieldtype": "Currency",
            "width": 160
        },
        {
            "label": "Pending Amount",
            "fieldname": "pending_amount",
            "fieldtype": "Currency",
            "width": 180
        },
    ]


def get_po_amount_drill_data(filters):

    conditions = get_conditions(filters)

    data = frappe.db.sql(f"""
        SELECT
            po.name AS purchase_order,
            po.transaction_date AS po_date,
            po.supplier_name AS supplier,

            -- PO Amount excluding Tax
            po.total AS amount,

            -- Taxes / Extra Charges
            IFNULL(tax.taxes, 0) AS taxes,

            po.grand_total AS grand_total,

            -- Pending Amount = Advance Paid - Material Received (PO-level)
            (IFNULL(adv.advance_paid, 0) - IFNULL(rec.received_amount, 0)) AS pending_amount

        FROM `tabPurchase Order` po
        {PO_ADVANCE_JOIN}
        {PO_RECEIVED_JOIN}
        {PO_TAXES_JOIN}

        WHERE po.docstatus = 1

          AND po.branch = %(drill_branch)s

          AND IFNULL(po.segment, '') = %(drill_segment)s

          AND {QUALIFYING_PENDING_PO_SUBQUERY}

          {conditions}

        ORDER BY po.transaction_date ASC

    """, filters, as_dict=True)

    total_row = {
        "purchase_order": "TOTAL",
        "amount": sum(
            flt(d.get("amount"))
            for d in data
        ),
        "taxes": sum(
            flt(d.get("taxes"))
            for d in data
        ),
        "grand_total": sum(
            flt(d.get("grand_total"))
            for d in data
        ),
        "pending_amount": sum(
            flt(d.get("pending_amount"))
            for d in data
        ),
        "is_total_row": 1
    }

    return [total_row] + data


def get_received_drill_columns():
    return [
        {
            "label": "Purchase Receipt",
            "fieldname": "purchase_receipt",
            "fieldtype": "Link",
            "options": "Purchase Receipt",
            "width": 210
        },
        {
            "label": "Purchase Order",
            "fieldname": "purchase_order",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 230
        },
        {
            "label": "Supplier",
            "fieldname": "supplier_name",
            "fieldtype": "Data",
            "width": 320
        },
        {
            "label": "Received Amount",
            "fieldname": "received_amount",
            "fieldtype": "Currency",
            "width": 170
        },
        {
            "label": "Taxes / Extra Charges",
            "fieldname": "taxes",
            "fieldtype": "Currency",
            "width": 180
        },
        {
            "label": "Receipt Date",
            "fieldname": "receipt_date",
            "fieldtype": "Date",
            "width": 150
        },
        {
            "label": "Pending Amount",
            "fieldname": "pending_amount",
            "fieldtype": "Currency",
            "width": 180
        },
    ]


def get_received_drill_data(filters):

    conditions = get_conditions(filters)

    # Note: taxes/pending are PO-level figures. If a single receipt spans
    # multiple POs they are aggregated with MAX() per receipt row and
    # de-duplicated per PO (not per receipt) when totalling below, so a PO
    # that appears on several receipts isn't double-counted in the TOTAL row.
    data = frappe.db.sql(f"""
        SELECT
            pr.name AS purchase_receipt,
            MAX(po.name) AS purchase_order,
            pr.supplier_name AS supplier_name,
            SUM(pri.base_amount) AS received_amount,
            pr.posting_date AS receipt_date,
            MAX(IFNULL(tax.taxes, 0)) AS taxes,
            MAX(IFNULL(adv.advance_paid, 0) - IFNULL(rec.received_amount, 0)) AS pending_amount

        FROM `tabPurchase Receipt Item` pri
        INNER JOIN `tabPurchase Receipt` pr
            ON pr.name = pri.parent
        INNER JOIN `tabPurchase Order` po
            ON po.name = pri.purchase_order
        {PO_ADVANCE_JOIN}
        {PO_RECEIVED_JOIN}
        {PO_TAXES_JOIN}

        WHERE pr.docstatus = 1
          -- Exclude return receipts - goods sent back are not "received"
          AND IFNULL(pr.is_return, 0) = 0
          AND po.branch = %(drill_branch)s
          AND IFNULL(po.segment, '') = %(drill_segment)s
          AND {QUALIFYING_PENDING_PO_SUBQUERY}
        {conditions}

        GROUP BY pr.name, pr.supplier_name, pr.posting_date
        ORDER BY pr.posting_date ASC
    """, filters, as_dict=True)

    seen_pos = set()
    total_taxes = 0
    total_pending = 0
    for d in data:
        po_name = d.get("purchase_order")
        if po_name and po_name not in seen_pos:
            seen_pos.add(po_name)
            total_taxes += flt(d.get("taxes"))
            total_pending += flt(d.get("pending_amount"))

    total_row = {
        "purchase_receipt": "TOTAL",
        "received_amount": sum(flt(d.get("received_amount")) for d in data),
        "taxes": total_taxes,
        "pending_amount": total_pending,
        "is_total_row": 1
    }

    return [total_row] + data



def get_pending_drill_columns():
    return [
        {"label": "Purchase Order", "fieldname": "purchase_order", "fieldtype": "Link", "options": "Purchase Order", "width": 220},
        {"label": "PO Date", "fieldname": "po_date", "fieldtype": "Date", "width": 140},
        {"label": "Advance Paid", "fieldname": "advance_paid", "fieldtype": "Currency", "width": 160},
        {"label": "Taxes / Extra Charges", "fieldname": "taxes", "fieldtype": "Currency", "width": 180},
        {"label": "Received Amount", "fieldname": "received_amount", "fieldtype": "Currency", "width": 160},
        {"label": "Pending Amount", "fieldname": "pending_amount", "fieldtype": "Currency", "width": 180},
        {"label": "Pending Days", "fieldname": "pending_days", "fieldtype": "Int", "width": 150},
    ]

def get_pending_drill_data(filters):

    conditions = get_conditions(filters)

    data = frappe.db.sql(f"""
        SELECT
            po.name AS purchase_order,
            po.transaction_date AS po_date,
            IFNULL(adv.advance_paid, 0) AS advance_paid,
            IFNULL(tax.taxes, 0) AS taxes,
            IFNULL(rec.received_amount, 0) AS received_amount,
            (IFNULL(adv.advance_paid, 0) - IFNULL(rec.received_amount, 0)) AS pending_amount,
            DATEDIFF(CURDATE(), po.transaction_date) AS pending_days

        FROM `tabPurchase Order` po
        {PO_ADVANCE_JOIN}
        {PO_RECEIVED_JOIN}
        {PO_TAXES_JOIN}

        WHERE po.docstatus = 1
          AND po.branch = %(drill_branch)s
          AND IFNULL(po.segment, '') = %(drill_segment)s
          -- Exclude POs that are already fully received (by qty)
          AND ROUND(IFNULL(po.per_received, 0), 2) < 100
        {conditions}

        -- Goods received (to date) is less than the advance paid
        HAVING ROUND(pending_amount, 2) > 0
        ORDER BY pending_amount DESC
    """, filters, as_dict=True)

    total_row = {
        "purchase_order": "TOTAL",
        "advance_paid": sum(flt(d.get("advance_paid")) for d in data),
        "taxes": sum(flt(d.get("taxes")) for d in data),
        "received_amount": sum(flt(d.get("received_amount")) for d in data),
        "pending_amount": sum(flt(d.get("pending_amount")) for d in data),
        "is_total_row": 1
    }

    return [total_row] + data


def get_conditions(filters):

    conditions = ""

    if filters.get("from_date"):
        conditions += " AND po.transaction_date >= %(from_date)s "

    if filters.get("to_date"):
        conditions += " AND po.transaction_date <= %(to_date)s "

    companies = filters.get("company") or []
    if isinstance(companies, str):
        try:
            companies = json.loads(companies)
        except Exception:
            companies = [companies]

    if companies:
        conditions += f""" AND po.company IN ({",".join(frappe.db.escape(c) for c in companies)}) """

    plants = filters.get("plant") or []
    if isinstance(plants, str):
        try:
            plants = json.loads(plants)
        except Exception:
            plants = [plants]

    if plants:
        conditions += f""" AND po.branch IN ({",".join(frappe.db.escape(p) for p in plants)}) """

    segments = filters.get("segment") or []
    if isinstance(segments, str):
        try:
            segments = json.loads(segments)
        except Exception:
            segments = [segments]

    if segments:
        conditions += f""" AND IFNULL(po.segment, '') IN ({",".join(frappe.db.escape(s) for s in segments)}) """

    return conditions



@frappe.whitelist()
def get_segment_options(txt=None, plant=None, company=None):
    """Distinct Purchase Order segment values, for the Segment MultiSelectList filter."""

    values = {}
    conditions = " WHERE po.docstatus = 1 AND IFNULL(po.segment, '') != '' "

    if txt:
        conditions += " AND po.segment LIKE %(txt)s "
        values["txt"] = f"%{txt}%"

    plants = plant or []
    if isinstance(plants, str):
        try:
            plants = json.loads(plants)
        except Exception:
            plants = [plants]
    if plants:
        conditions += f""" AND po.branch IN ({",".join(frappe.db.escape(p) for p in plants)}) """

    companies = company or []
    if isinstance(companies, str):
        try:
            companies = json.loads(companies)
        except Exception:
            companies = [companies]
    if companies:
        conditions += f""" AND po.company IN ({",".join(frappe.db.escape(c) for c in companies)}) """

    rows = frappe.db.sql(f"""
        SELECT DISTINCT po.segment AS segment
        FROM `tabPurchase Order` po
        {conditions}
        ORDER BY po.segment ASC
    """, values, as_dict=True)

    return [r.segment for r in rows]



@frappe.whitelist()
def get_po_basic_details(purchase_order):

    frappe.has_permission("Purchase Order", ptype="read", throw=True)

    po_info = frappe.db.get_value(
        "Purchase Order", purchase_order, ["supplier", "supplier_name"], as_dict=True
    ) or {}

    items = frappe.db.sql("""
        SELECT item_name, qty, uom, rate, base_amount AS amount
        FROM `tabPurchase Order Item`
        WHERE parent = %(po)s
        ORDER BY idx ASC
    """, {"po": purchase_order}, as_dict=True)

    payments = frappe.db.sql("""
        SELECT pe.name AS payment_entry, per.allocated_amount AS amount, pe.posting_date
        FROM `tabPayment Entry Reference` per
        INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
        WHERE per.reference_doctype = 'Purchase Order'
          AND per.reference_name = %(po)s
          AND pe.docstatus = 1
          AND pe.payment_type = 'Pay'
        ORDER BY pe.posting_date ASC
    """, {"po": purchase_order}, as_dict=True)

    return {
        "supplier": po_info.get("supplier"),
        "supplier_name": po_info.get("supplier_name"),
        "items": items,
        "payments": payments,
    }


@frappe.whitelist()
def get_pr_basic_details(purchase_receipt):

    frappe.has_permission("Purchase Receipt", ptype="read", throw=True)

    items = frappe.db.sql("""
        SELECT
            pri.purchase_order AS purchase_order,
            pri.item_name AS item_name,
            pri.uom AS uom,
            pri.rate AS rate,
            pri.qty AS qty
        FROM `tabPurchase Receipt Item` pri
        WHERE pri.parent = %(pr)s
        ORDER BY pri.idx ASC
    """, {"pr": purchase_receipt}, as_dict=True)

    po_names = sorted({d.purchase_order for d in items if d.purchase_order})

    po_totals = {}
    if po_names:
        rows = frappe.db.sql("""
            SELECT
                po.name AS purchase_order,
                po.total AS po_amount,
                IFNULL(rec.received_amount, 0) AS received_amount
            FROM `tabPurchase Order` po
            LEFT JOIN (
                SELECT pri.purchase_order AS po_name, SUM(pri.base_amount) AS received_amount
                FROM `tabPurchase Receipt Item` pri
                INNER JOIN `tabPurchase Receipt` pr ON pr.name = pri.parent
                WHERE pr.docstatus = 1
                  -- Exclude return receipts entirely (negative amounts) -
                  -- goods sent back are not counted as received at all
                  AND IFNULL(pr.is_return, 0) = 0
                GROUP BY pri.purchase_order
            ) rec ON rec.po_name = po.name
            WHERE po.name IN %(po_names)s
        """, {"po_names": po_names}, as_dict=True)

        for r in rows:
            po_totals[r.purchase_order] = {
                "po_amount": flt(r.po_amount),
                "pending_amount": flt(r.po_amount) - flt(r.received_amount),
            }

    for d in items:
        totals = po_totals.get(d.purchase_order, {})
        d["po_amount"] = totals.get("po_amount")
        d["pending_amount"] = totals.get("pending_amount")

    return {"items": items}