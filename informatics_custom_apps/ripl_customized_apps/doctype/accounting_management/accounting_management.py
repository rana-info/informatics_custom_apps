# Copyright (c) 2025, Monil Kamboj and contributors
# For license information, please see license.

import frappe
from frappe.model.document import Document

class AccountingManagement(Document):
    def before_submit(self):
        self.update_vouchers()

    def update_vouchers(self):
        if not self.voucher_numbers:
            return

        # Split voucher numbers
        vouchers = [v.strip() for v in self.voucher_numbers.split(",") if v.strip()]

        for v in vouchers:
            self.update_document(self.doctype_name, v)

    def update_document(self, doctype, voucher_no):
        if not frappe.db.exists(doctype, voucher_no):
            frappe.throw(f"{doctype} {voucher_no} not found")

        doc = frappe.get_doc(doctype, voucher_no)

        # Update header
        self.update_header(doc, doctype)

        # Update child items
        for i in doc.items:
            self.update_child(i)

        # Update GL Entries
        self.update_gl_entries(voucher_no)

    def update_header(self, doc, doctype):
        if self.plant:
            doc.db_set("branch", self.plant)
        if self.segment:
            doc.db_set("segment", self.segment)
        if self.section:
            doc.db_set("section", self.section)
        if self.cost_center and doctype != "Stock Entry":  # Skip cost_center for Stock Entry
            doc.db_set("cost_center", self.cost_center)

    def update_child(self, child):
        if self.plant:
            child.db_set("branch", self.plant)
        if self.cost_center:
            child.db_set("cost_center", self.cost_center)
        if self.segment:
            child.db_set("segment", self.segment)
        if self.section:
            child.db_set("section", self.section)
        if self.expense_account and child.expense_account == self.wrong_expense_account:
            child.db_set("expense_account", self.expense_account)

    def update_gl_entries(self, voucher_no):
        doc_list = frappe.get_all("GL Entry", filters={"voucher_no": voucher_no}, fields=["name"])
        for d in doc_list:
            gl_entry = frappe.get_doc("GL Entry", d.name)
            if self.plant:
                gl_entry.db_set("branch", self.plant)
            if self.cost_center:
                gl_entry.db_set("cost_center", self.cost_center)
            if self.segment:
                gl_entry.db_set("segment", self.segment)
            if self.section:
                gl_entry.db_set("section", self.section)

            if self.expense_account and self.wrong_expense_account:
                if gl_entry.account == self.wrong_expense_account:
                    gl_entry.db_set("account", self.expense_account)
                if gl_entry.against == self.wrong_expense_account:
                    gl_entry.db_set("against", self.expense_account)
