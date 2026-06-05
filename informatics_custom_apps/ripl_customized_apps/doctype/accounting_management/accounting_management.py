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
            if (
                self.payable_account_update
                and self.doctype_name == "Sales Invoice"
            ):
                self.update_sales_invoice_payables(
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
        #Taxes child update
        taxes = getattr(doc, "taxes", None)
        if taxes:
            for t in taxes:
                self.update_child(t)
        # Update GL Entries
        self.update_gl_entries(voucher_no)
        # Update Stock Ledger Entries for Purchase Receipt
        if doctype == "Purchase Receipt" or doctype == "Delivery Note":
            self.update_stock_ledger_entries(voucher_no)
        # Update Payment Ledger Entries for Purchase Invoice
        if doctype == "Purchase Invoice":
            self.update_purchase_invoice_payment_ledger_entries(voucher_no)
        if self.only_gl_update:
            self.update_gl_entries_only(voucher_no)


    def update_header(self, doc, doctype):
        def set_if_exists(fieldname, value):
            if value and frappe.get_meta(doctype).has_field(fieldname):
                doc.db_set(fieldname, value, update_modified=False)

        set_if_exists("branch", self.plant)
        set_if_exists("custom_branch", self.plant)

        set_if_exists("segment", self.segment)
        set_if_exists("custom_segment", self.segment)

        set_if_exists("section", self.section)
        set_if_exists("custom_section", self.section)

        if doctype != "Stock Entry":
            set_if_exists("cost_center", self.cost_center)
            set_if_exists("custom_cost_center", self.cost_center)

    def update_child(self, child):
        if self.plant and hasattr(child, "branch"):
            child.db_set("branch", self.plant, update_modified=False)
        if self.cost_center and hasattr(child, "cost_center"):
            child.db_set("cost_center", self.cost_center, update_modified=False)
        if self.segment and hasattr(child, "segment"):
            child.db_set("segment", self.segment, update_modified=False)
        if self.section and hasattr(child, "section"):
            child.db_set("section", self.section, update_modified=False)

        # Change expense_account only if field exists in child doctype
        if hasattr(child, "expense_account") and self.expense_account and self.wrong_expense_account:
            if child.expense_account == self.wrong_expense_account:
                child.db_set("expense_account", self.expense_account, update_modified=False)
        # Change income_account only if field exists in child doctype
        if hasattr(child, "income_account") and self.correct_income_account and self.wrong_income_account:
            if child.income_account == self.wrong_income_account:
                child.db_set(
                    "income_account",
                    self.correct_income_account,
                    update_modified=False
                )


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
            # Income account replacement
            if self.correct_income_account and self.wrong_income_account:
                if gl_entry.account == self.wrong_income_account:
                    gl_entry.db_set(
                        "account",
                        self.correct_income_account,
                        update_modified=False
                    )
                if gl_entry.against == self.wrong_income_account:
                    gl_entry.db_set(
                        "against",
                        self.correct_income_account,
                        update_modified=False
                    )

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
    # ---------------- Additional payable-account update for Purchase Invoice ----------------     
    def update_purchase_invoice_payables(self, voucher_no, correct_account, wrong_account):
        if not frappe.db.exists("Purchase Invoice", voucher_no):
            return

        doc = frappe.get_doc("Purchase Invoice", voucher_no)

        # Update header field
        if doc.credit_to == wrong_account:
            doc.db_set("credit_to", correct_account, update_modified=False)

        self.update_payment_ledger_entry(voucher_no, correct_account, wrong_account)
    #Sales Invoice Payable Account Update
    def update_sales_invoice_payables(self, voucher_no, correct_account, wrong_account):
        if not frappe.db.exists("Sales Invoice", voucher_no):
            return

        doc = frappe.get_doc("Sales Invoice", voucher_no)

        # Update header field
        if doc.debit_to == wrong_account:
            doc.db_set("debit_to", correct_account, update_modified=False)

        self.update_payment_ledger_entry(voucher_no, correct_account, wrong_account)
    # ---------------- Update Payment Ledger Entry ----------------
    def update_payment_ledger_entry(self,voucher_no,correct_account,wrong_account):
        # Update Payment Ledger Entry separately
        ple_list = frappe.get_all(
            "Payment Ledger Entry", filters={"voucher_no": voucher_no}, fields=["name"]
        )
        for d in ple_list:
            ple = frappe.get_doc("Payment Ledger Entry", d.name)
            if ple.account == wrong_account:
                ple.db_set("account", correct_account, update_modified=False)
    # ---------------- Update Stock Ledger Entry only for Purchase Receipt----------------
    def update_stock_ledger_entries(self, voucher_no):
        if not any([self.plant, self.cost_center, self.segment, self.section]):
            return

        try:
            sle_list = frappe.get_all(
                "Stock Ledger Entry",
                filters={
                    "voucher_type": ["in", ["Purchase Receipt", "Delivery Note"]],  
                    "voucher_no": voucher_no
                },
                fields=["name"]
            )

            for d in sle_list:
                sle = frappe.get_doc("Stock Ledger Entry", d.name)

                if self.plant and hasattr(sle, "branch"):
                    sle.db_set("branch", self.plant, update_modified=False)
                if self.cost_center and hasattr(sle, "cost_center"):
                    sle.db_set("cost_center", self.cost_center, update_modified=False)
                if self.segment and hasattr(sle, "segment"):
                    sle.db_set("segment", self.segment, update_modified=False)
                if self.section and hasattr(sle, "section"):
                    sle.db_set("section", self.section, update_modified=False)

        except Exception as e:
            frappe.log_error(
                title="AccountingManagement: SLE Update Failed",
                message=f"Voucher: {voucher_no}\nError: {frappe.get_traceback()}"
            )
    # ---------------- Update Payment Ledger Entry for Purchase Invoice ----------------
    def update_purchase_invoice_payment_ledger_entries(self, voucher_no):
        if not any([self.plant, self.cost_center, self.segment, self.section]):
            return

        try:
            ple_list = frappe.get_all(
                "Payment Ledger Entry",
                filters={
                    "voucher_type": "Purchase Invoice",
                    "voucher_no": voucher_no
                },
                fields=["name"]
            )

            for d in ple_list:
                ple = frappe.get_doc("Payment Ledger Entry", d.name)

                if self.plant and hasattr(ple, "branch"):
                    ple.db_set("branch", self.plant, update_modified=False)
                if self.cost_center and hasattr(ple, "cost_center"):
                    ple.db_set("cost_center", self.cost_center, update_modified=False)
                if self.segment and hasattr(ple, "segment"):
                    ple.db_set("segment", self.segment, update_modified=False)
                if self.section and hasattr(ple, "section"):
                    ple.db_set("section", self.section, update_modified=False)

        except Exception:
            frappe.log_error(
                title="AccountingManagement: PI Payment Ledger Update Failed",
                message=f"Voucher: {voucher_no}\n{frappe.get_traceback()}"
            )
    def update_gl_entries_only(self, voucher_no):
        try:
            gl_entries = frappe.get_all(
                "GL Entry",
                filters={
                    "voucher_no": voucher_no
                },
                or_filters=[
                    {"account": self.wrong_gl},
                    {"against": self.wrong_gl}
                ],
                fields=["name"]
            )
            for entry in gl_entries:
                gl_entry = frappe.get_doc("GL Entry", entry.name)
                if gl_entry.account == self.wrong_gl:
                    gl_entry.db_set("account", self.correct_gl, update_modified=False)
                if gl_entry.against == self.wrong_gl:
                    gl_entry.db_set("against", self.correct_gl, update_modified=False)

        except Exception as e:
            frappe.log_error(frappe.get_traceback(), "GL Entry Fetch Error")
