import frappe
from frappe.utils import flt

# Keep this in sync with EXCLUDE_FROM_GROSS in your salary breakup file
EXCLUDE_FROM_GROSS = ("employer's pf", "employer pf", "employer provident fund")


def execute():
    meta = frappe.get_meta("Salary Structure Assignment")
    field = meta.get_field("custom_salary_detail")

    if not field or not meta.has_field("custom_gross_salary"):
        return

    child_dt = field.options

    # Employer's PF rows in the gross table of draft/submitted assignments (skip cancelled)
    rows = frappe.db.sql(
        f"""
        SELECT child.name, child.parent
        FROM `tab{child_dt}` child
        INNER JOIN `tabSalary Structure Assignment` ssa ON ssa.name = child.parent
        WHERE child.parenttype = 'Salary Structure Assignment'
          AND child.parentfield = 'custom_salary_detail'
          AND LOWER(TRIM(child.salary_component)) IN %(names)s
          AND ssa.docstatus < 2
        """,
        {"names": EXCLUDE_FROM_GROSS},
        as_dict=True,
    )

    if not rows:
        print("No Employer's PF rows found in gross salary detail. Nothing to update.")
        return

    parents = {r.parent for r in rows}

    # 1. Remove Employer's PF rows from the gross table
    frappe.db.delete(child_dt, {"name": ("in", [r.name for r in rows])})

    # 2. Renumber the remaining rows and recalculate gross for each assignment
    for parent in parents:
        remaining = frappe.get_all(
            child_dt,
            filters={
                "parent": parent,
                "parenttype": "Salary Structure Assignment",
                "parentfield": "custom_salary_detail",
            },
            fields=["name", "amount"],
            order_by="idx asc",
        )

        for idx, row in enumerate(remaining, start=1):
            frappe.db.set_value(child_dt, row.name, "idx", idx, update_modified=False)

        gross = sum(flt(row.amount) for row in remaining)
        frappe.db.set_value(
            "Salary Structure Assignment",
            parent,
            "custom_gross_salary",
            gross,
            update_modified=False,
        )

    print(f"Updated gross salary on {len(parents)} Salary Structure Assignment(s).")