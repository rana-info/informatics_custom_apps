import frappe
from frappe.utils.data import flt, cint
import unicodedata
from frappe.utils import getdate

def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data

def get_columns():
    return [
        {"fieldname": "provident_fund_account", "label": "UAN", "fieldtype": "Data", "width": 170},
        {"fieldname": "employee_name", "label": "Employee Name", "fieldtype": "Data", "width": 200},
        {"fieldname": "gross_pay", "label": "Gross Pay", "fieldtype": "Currency", "width": 120},
        {"fieldname": "pf_salary", "label": "PF Salary", "fieldtype": "Currency", "width": 120},
        {"fieldname": "pension_salary", "label": "Pension Salary", "fieldtype": "Currency", "width": 120},
        {"fieldname": "edli", "label": "EDLI", "fieldtype": "Currency", "width": 120},
        {"fieldname": "pf_12_per", "label": "PF", "fieldtype": "Currency", "width": 100},
        {"fieldname": "employee_pension_amount", "label": "EPS", "fieldtype": "Currency", "width": 100},
        {"fieldname": "employee_pf", "label": "EPF", "fieldtype": "Currency", "width": 100},
        {"fieldname": "ncp_days", "label": "NCP Days", "fieldtype": "Int", "width": 80},
    ]

def get_data(filters):
    data = []
    slips = frappe.get_list("zzRetaining Salary Slip", filters={
        "docstatus": 1,
        "branch": filters.get("branch"),
        "start_date": [">=", filters.get("from_date")],
        "end_date": ["<=", filters.get("to_date")],
    }, fields=[
        "name", "employee", "employee_name", "gross_pay", "payment_days", 
        "total_working_days", "salary_structure", "retaining_salary"
    ])

    for slip in slips:
        # Check if linked Retaining Salary doc is submitted
        retaining_salary_docstatus = frappe.db.get_value("zzRetaining Salary", slip.retaining_salary, "docstatus")
        if retaining_salary_docstatus != 1:
            continue  # Skip if not submitted

        row = {
            "employee_name": slip.employee_name,
            "gross_pay": slip.gross_pay,
        }

        slip_doc = frappe.get_doc("zzRetaining Salary Slip", slip.name) 
        row["provident_fund_account"] = frappe.db.get_value("Employee", slip.employee, "provident_fund_account")
        row["ncp_days"] = cint(slip.total_working_days) - cint(slip.payment_days)

        data_dict = {}
        add_structure_components(slip_doc, "earnings", data_dict)
        add_structure_components(slip_doc, "deductions", data_dict)

        row["pf_salary"] = flt(data_dict.get("pf_salary"))
        row["pension_salary"] = flt(data_dict.get("pension_salary"))
        row["edli"] = flt(data_dict.get("edli"))
        row["employee_pf"] = flt(data_dict.get("employee_pf"))
        row["employee_pension_amount"] = flt(data_dict.get("employee_pension_amount"))
        row["pf_12_per"] = flt(data_dict.get("pf_12_per"))
        

        data.append(row)

    return data

def add_structure_components(slip, component_type, data_dict):
    slip.data, slip.default_data = get_data_for_retaining_eval(slip)
    if not cint(slip.data.get("is_pf_applicable")):
        return
    structure = frappe.get_doc("Salary Structure", slip.salary_structure)

    for comp in structure.get(component_type):
        amount = eval_condition_and_formula(comp, slip.data)

        if comp.statistical_component:
            slip.default_data[comp.abbr] = flt(amount)
            if comp.depends_on_payment_days and slip.total_working_days:
                amount = (
                    flt(amount) * flt(slip.payment_days) / cint(slip.total_working_days)
                )
            slip.data[comp.abbr] = flt(amount, comp.precision("amount"))

        amount = flt(amount) or 0
        sc = frappe.get_cached_doc("Salary Component", comp.salary_component)
         # Log the details of the component, formula, and calculation



        if sc.custom_pension_salary:
            data_dict["pension_salary"] = amount
            data_dict["edli"] = amount
        if sc.custom_pf_salary:
            data_dict["pf_salary"] = amount
        if sc.custom_pf_12_per:
            data_dict["pf_12_per"] = amount
        if sc.custom_employee_pension_amount:
            data_dict["employee_pension_amount"] = amount
        if sc.custom_employee_pf:
            data_dict["employee_pf"] = amount

def get_data_for_retaining_eval(slip):
    data = frappe._dict()

    employee = frappe.get_cached_doc("Employee", slip.employee).as_dict()
   

    ssa = frappe.db.get_value(
        "Salary Structure Assignment",
        {
            "employee": slip.employee,
            "salary_structure": slip.salary_structure,
            "from_date": ("<=", slip.start_date),
            "docstatus": 1,
        },
        "*",
        order_by="from_date desc",
        as_dict=True,
    )
    if not ssa:
        frappe.throw(f"No valid Salary Structure Assignment found for employee {slip.employee}")

    data.update(ssa)
    data.update(slip.as_dict())
    data.update(employee)
    data.update(get_component_abbr_map())

    data["is_pf_applicable"] = cint(ssa.is_pf_applicable)
    data["special_work_hours"] = data.get("special_work_hours", 0)
    data["total_working_hours"] = data.get("total_working_hours", slip.total_working_days or 0)
    data["holiday_days"] = data.get("holiday_days", 0)
    data["leave_encashment_el"] = data.get("leave_encashment_el", 0)
    data["leave_encashment_casual"] = data.get("leave_encashment_casual", 0)
    data["leave_encashment_sick"] = data.get("leave_encashment_sick", 0)
    data["production_incentive_days"] = data.get("production_incentive_days", 0)
    data["deputation_days"] = data.get("deputation_days", 0)

    default_data = data.copy()
    for key in ("earnings", "deductions"):
        if hasattr(slip, key):
            for d in getattr(slip, key):
                default_data[d.abbr] = d.default_amount or 0
                data[d.abbr] = d.amount or 0

    return data, default_data


def eval_condition_and_formula(struct_row, data):
    whitelisted_globals = {
        "int": int,
        "float": float,
        "long": int,
        "round": round,
    }

    condition, formula, amount = struct_row.condition, struct_row.formula, struct_row.amount

    if condition and not safe_eval(condition, whitelisted_globals, data):
        return None

    if struct_row.amount_based_on_formula and formula:
        amount = flt(
            safe_eval(formula, whitelisted_globals, data),
            struct_row.precision("amount")
        )

    if amount:
        data[struct_row.abbr] = amount

    return amount

def safe_eval(code: str, eval_globals=None, eval_locals=None):
    code = unicodedata.normalize("NFKC", code)

    if not eval_globals:
        eval_globals = {}

    whitelisted_globals = {
        "int": int,
        "float": float,
        "round": round,
        "long": int,
        "getdate": getdate,
    }

    eval_globals["__builtins__"] = {}
    eval_globals.update(whitelisted_globals)

    return eval(code, eval_globals, eval_locals)

def get_component_abbr_map():
    def _fetch_component_values():
        return {
            abbr: 0 for abbr in frappe.get_all("Salary Component", pluck="salary_component_abbr")
            
        }
    return frappe.cache().get_value("SALARY_COMPONENT_VALUES", generator=_fetch_component_values)
