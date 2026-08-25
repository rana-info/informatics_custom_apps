import os
import sys
sys.path.append("/home/yash/frappe-bench/apps/frappe")
os.chdir("/home/yash/frappe-bench/sites")
import frappe
frappe.init(site="erp3.com")
frappe.connect()

ads = frappe.get_all("Additional Salary", filters={"ref_doctype": "Leave Encashment"}, fields=["name", "salary_component", "docstatus"], limit=5)
for a in ads:
    print(a)
