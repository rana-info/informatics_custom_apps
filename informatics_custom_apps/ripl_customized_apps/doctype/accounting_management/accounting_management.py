# Copyright (c) 2025, Monil Kamboj and contributors
# For license information, please see license.

import frappe
from frappe.model.document import Document

class AccountingManagement(Document):
    def before_save(self):
        if self.voucher_numbers:
            # Split by comma, strip spaces, and ignore empties
            items = [i.strip() for i in self.voucher_numbers.split(",") if i.strip()]
            self.total_vouchers = len(items)
        else:
            self.total_vouchers = 0

    
    def before_submit(self):
        self.update_vouchers()

    def update_vouchers(self):
        if not self.voucher_numbers:
            return

        vouchers = [v.strip() for v in self.voucher_numbers.split(",") if v.strip()]

        for v in vouchers:
            # Always do normal updates
            self.update_document(self.doctype_name, v)

            # Additionally, payable-account-specific updates
            if (
                self.payable_account_update
                and self.doctype_name == "Payment Entry"
            ):
                self.update_payment_entry_payables(
                    v, self.correct_payable_account, self.wrong_payable_account
                )
            if (
                self.payable_account_update
                and self.doctype_name == "Purchase Invoice"
            ):
                self.update_purchase_invoice_payables(
                    v, self.correct_payable_account, self.wrong_payable_account
                )

    def update_document(self, doctype, voucher_no):
        if not frappe.db.exists(doctype, voucher_no):
            frappe.throw(f"{doctype} {voucher_no} not found")

        doc = frappe.get_doc(doctype, voucher_no)

        # Update header
        self.update_header(doc, doctype)

        # Update child items
        items = getattr(doc, "items", None)
        if items:
            for i in items:
                self.update_child(i)

        # Update GL Entries
        self.update_gl_entries(voucher_no)

    def update_header(self, doc, doctype):
        if self.plant:
            doc.db_set("branch", self.plant, update_modified=False)
        if self.segment:
            doc.db_set("segment", self.segment, update_modified=False)
        if self.section:
            doc.db_set("section", self.section, update_modified=False)
        if self.cost_center and doctype != "Stock Entry":  # Skip cost_center for Stock Entry
            doc.db_set("cost_center", self.cost_center, update_modified=False)

    def update_child(self, child):
        if self.plant:
            child.db_set("branch", self.plant, update_modified=False)
        if self.cost_center:
            child.db_set("cost_center", self.cost_center, update_modified=False)
        if self.segment:
            child.db_set("segment", self.segment, update_modified=False)
        if self.section:
            child.db_set("section", self.section, update_modified=False)
        if self.expense_account and child.expense_account == self.wrong_expense_account:
            child.db_set("expense_account", self.expense_account, update_modified=False)

    def update_gl_entries(self, voucher_no):
        doc_list = frappe.get_all("GL Entry", filters={"voucher_no": voucher_no}, fields=["name"])
        for d in doc_list:
            gl_entry = frappe.get_doc("GL Entry", d.name)
            if self.plant:
                gl_entry.db_set("branch", self.plant, update_modified=False)
            if self.cost_center:
                gl_entry.db_set("cost_center", self.cost_center, update_modified=False)
            if self.segment:
                gl_entry.db_set("segment", self.segment, update_modified=False)
            if self.section:
                gl_entry.db_set("section", self.section, update_modified=False)

            # Expense account replacement
            if self.expense_account and self.wrong_expense_account:
                if gl_entry.account == self.wrong_expense_account:
                    gl_entry.db_set("account", self.expense_account, update_modified=False)
                if gl_entry.against == self.wrong_expense_account:
                    gl_entry.db_set("against", self.expense_account, update_modified=False)

            # Payable account replacement
            if self.payable_account_update and self.correct_payable_account and self.wrong_payable_account:
                if gl_entry.account == self.wrong_payable_account:
                    gl_entry.db_set("account", self.correct_payable_account, update_modified=False)
                if gl_entry.against == self.wrong_payable_account:
                    gl_entry.db_set("against", self.correct_payable_account, update_modified=False)

    # ---------------- Additional payable-account update for Payment Entry ----------------
    def update_payment_entry_payables(self, voucher_no, correct_account, wrong_account):
        if not frappe.db.exists("Payment Entry", voucher_no):
            return

        doc = frappe.get_doc("Payment Entry", voucher_no)

        # Update header field
        if doc.payment_type == "Pay" and doc.paid_to == wrong_account:
            doc.db_set("paid_to", correct_account, update_modified=False)
        if doc.payment_type == "Receive" and doc.paid_from == wrong_account:
            doc.db_set("paid_from", correct_account, update_modified=False)
        # Update references child table
        references = getattr(doc, "references", []) or []
        for ref in references:
            if ref.account == wrong_account:
                ref.db_set("account", correct_account, update_modified=False)

        self.update_payment_ledger_entry(voucher_no, correct_account, wrong_account)
        
    def update_purchase_invoice_payables(self, voucher_no, correct_account, wrong_account):
        if not frappe.db.exists("Purchase Invoice", voucher_no):
            return

        doc = frappe.get_doc("Purchase Invoice", voucher_no)

        # Update header field
        if doc.credit_to == wrong_account:
            doc.db_set("credit_to", correct_account, update_modified=False)

        self.update_payment_ledger_entry(voucher_no, correct_account, wrong_account)

    def update_payment_ledger_entry(self,voucher_no,correct_account,wrong_account):
        # Update Payment Ledger Entry separately
        ple_list = frappe.get_all(
            "Payment Ledger Entry", filters={"voucher_no": voucher_no}, fields=["name"]
        )
        for d in ple_list:
            ple = frappe.get_doc("Payment Ledger Entry", d.name)
            if ple.account == wrong_account:
                ple.db_set("account", correct_account, update_modified=False)
