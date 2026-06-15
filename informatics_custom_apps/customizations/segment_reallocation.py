import frappe
from frappe.utils import flt
import traceback


SEGMENT_FIELDNAME = "segment"
WAREHOUSE_SEGMENT_FIELD = "custom_segment"

APPLICABLE_TYPES = ["Material Transfer"]

warehouse_cache = {}


def on_stock_entry_submit(doc, method=None):
    """
    Queue processing after Stock Entry submit.
    """

    if doc.stock_entry_type not in APPLICABLE_TYPES:
        return

    frappe.enqueue(
        process_stock_entry,
        queue="short",
        timeout=300,
        enqueue_after_commit=True,
        stock_entry_name=doc.name
    )


@frappe.whitelist()
def process_stock_entry(stock_entry_name):

    try:

        se = frappe.get_doc(
            "Stock Entry",
            stock_entry_name
        )

        if se.docstatus != 1:
            return

        if se.stock_entry_type not in APPLICABLE_TYPES:
            return

        # Prevent duplicate JE
        if frappe.db.exists(
            "Journal Entry",
            {
                "custom_stock_entry_reference": se.name
            }
        ):
            return

        case1_rows = []

        for row in se.items:

            if not row.s_warehouse or not row.t_warehouse:
                continue

            src_gl, src_seg = get_warehouse_gl_and_segment(
                row.s_warehouse,
                se.company
            )

            tgt_gl, tgt_seg = get_warehouse_gl_and_segment(
                row.t_warehouse,
                se.company
            )

            if not src_seg or not tgt_seg:
                continue

            if src_seg == tgt_seg:
                continue

            if src_gl != tgt_gl:
                continue

            case1_rows.append(
                frappe._dict({
                    "item_code": row.item_code,
                    "qty": row.qty,
                    "amount": flt(row.amount),
                    "s_warehouse": row.s_warehouse,
                    "t_warehouse": row.t_warehouse,
                    "src_gl": src_gl,
                    "tgt_gl": tgt_gl,
                    "src_seg": src_seg,
                    "tgt_seg": tgt_seg,
                    "cost_center": row.cost_center,
                    "branch": row.branch,
                })
            )

        if not case1_rows:
            return

        handle_case1(
            case1_rows,
            se
        )

    except Exception:

        error = traceback.format_exc()

        frappe.log_error(
            title=f"Segment Reallocation Failed - {stock_entry_name}",
            message=error
        )

        try:

            frappe.db.rollback()

            se = frappe.get_doc(
                "Stock Entry",
                stock_entry_name
            )

            se.reload()

            if se.docstatus == 1:

                se.flags.ignore_permissions = True
                se.flags.ignore_links = True

                # Cancel Stock Entry
                se.cancel()

                # Add comment
                se.add_comment(
                    "Comment",
                    text=(
                        "Automatically cancelled because "
                        "Segment Reallocation Journal Entry "
                        "creation failed.\n\n"
                        f"Reason:\n{error}"
                    )
                )

        except Exception:

            frappe.db.rollback()

            frappe.log_error(
                title=f"Stock Entry Auto Cancel Failed - {stock_entry_name}",
                message=frappe.get_traceback()
            )

        raise


def handle_case1(rows, se):

    currency = frappe.get_cached_value(
        "Company",
        se.company,
        "default_currency"
    )

    je = frappe.new_doc(
        "Journal Entry"
    )

    je.voucher_type = "Journal Entry"
    je.posting_date = se.posting_date
    je.company = se.company

    je.user_remark = (
        f"Segment reallocation "
        f"(Case 1 - same GL) "
        f"for {se.name}"
    )

    je.cheque_no = se.name
    je.cheque_date = se.posting_date
    for row in rows:

        # Debit target segment
        je.append(
            "accounts",
            {
                "account": row.tgt_gl,
                "debit_in_account_currency": flt(
                    row.amount,
                    2
                ),
                "credit_in_account_currency": 0,
                SEGMENT_FIELDNAME: row.tgt_seg,
                "account_currency": currency,
                "cost_center": row.cost_center,
                "branch": row.branch,
            }
        )

        # Credit source segment
        je.append(
            "accounts",
            {
                "account": row.src_gl,
                "debit_in_account_currency": 0,
                "credit_in_account_currency": flt(
                    row.amount,
                    2
                ),
                SEGMENT_FIELDNAME: row.src_seg,
                "account_currency": currency,
                "cost_center": row.cost_center,
                "branch": row.branch,
            }
        )

    if not je.accounts:
        return

    je.flags.ignore_permissions = True
    je.flags.ignore_mandatory = True

    je.insert()
    je.submit()

    return je.name


def get_warehouse_gl_and_segment(
    warehouse,
    company
):

    if warehouse in warehouse_cache:
        return warehouse_cache[
            warehouse
        ]

    wh = frappe.get_cached_value(
        "Warehouse",
        warehouse,
        [
            "account",
            WAREHOUSE_SEGMENT_FIELD
        ],
        as_dict=True
    )

    if not wh:
        return (
            None,
            None
        )

    gl = wh.get("account")

    seg = wh.get(
        WAREHOUSE_SEGMENT_FIELD
    )

    warehouse_cache[
        warehouse
    ] = (
        gl,
        seg
    )

    return (
        gl,
        seg
    )