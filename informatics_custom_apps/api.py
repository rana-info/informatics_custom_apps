import frappe
from frappe import _

@frappe.whitelist()
def reopen_loan(loan_name, reason):
    loan = frappe.get_doc("Loan", loan_name)
    
    # Update status
    loan.db_set("status", "Disbursed")

    # Add comment with user input
    loan.add_comment(
        "Comment", 
        _("{0} reopened this loan, Reason: {1}").format(frappe.session.user, reason)
    )

    frappe.db.commit()
    return {"status": "success"}
