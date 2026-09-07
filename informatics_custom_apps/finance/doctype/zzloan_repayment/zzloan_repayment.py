# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt, getdate


class zzLoanRepayment(Document):

    def validate(self):

        self.fetch_loan_details()
        self.calculate_total()
        self.calculate_payment_timing()
        self.validate_loan()
        self.validate_amounts()
        self.validate_schedule()

    # ------------------------------------------------------------------
    # FETCH LOAN INFORMATION
    # ------------------------------------------------------------------

    def fetch_loan_details(self):

        if not self.sanctioned_loan:
            return

        loan = frappe.db.get_value(
            "Sanctioned Loan",
            self.sanctioned_loan,
            [
                "bank",
                "loan_type",
                "company",
                "plant"
            ],
            as_dict=True
        )

        if not loan:
            frappe.throw(
                "Sanctioned Loan not found."
            )

        self.bank = loan.bank
        self.loan_type = loan.loan_type
        self.company = loan.company
        self.plant = loan.plant

    # ------------------------------------------------------------------
    # VALIDATION
    # ------------------------------------------------------------------

    def validate_loan(self):

        loan = frappe.get_doc(
            "Sanctioned Loan",
            self.sanctioned_loan
        )

        if loan.docstatus != 1:
            frappe.throw(
                "Only a submitted Sanctioned Loan can have repayments."
            )

        if loan.loan_status == "Closed":
            frappe.throw(
                "This loan is already closed."
            )

        if flt(self.principal_paid) > flt(
            loan.outstanding_amount
        ):
            frappe.throw(
                "Principal Paid cannot exceed the current "
                "loan outstanding amount."
            )

    def calculate_total(self):

        self.total_paid = flt(
            self.principal_paid
        ) + flt(
            self.interest_paid
        )

    def calculate_payment_timing(self):

        if not self.due_date:
            self.payment_timing = "Unscheduled"
            self.days_early = 0
            self.days_late = 0
            return

        if not self.payment_date:
            return

        due_date = getdate(
            self.due_date
        )

        payment_date = getdate(
            self.payment_date
        )

        difference = (
            payment_date - due_date
        ).days

        self.days_early = 0
        self.days_late = 0

        if difference < 0:

            self.payment_timing = "Early"
            self.days_early = abs(difference)

        elif difference == 0:

            self.payment_timing = "On Time"

        else:

            self.payment_timing = "Late"
            self.days_late = difference

    def validate_amounts(self):

        if flt(self.principal_paid) < 0:
            frappe.throw(
                "Principal Paid cannot be negative."
            )

        if flt(self.interest_paid) < 0:
            frappe.throw(
                "Interest Paid cannot be negative."
            )

        if (
            flt(self.principal_paid) == 0
            and flt(self.interest_paid) == 0
        ):
            frappe.throw(
                "Principal Paid or Interest Paid must be greater than zero."
            )

    def validate_schedule(self):

        # Schedule reference is optional.
        # This allows future support for advance/unscheduled repayments.

        if not self.schedule_reference:
            return

        schedule = frappe.db.get_value(
            "zzLoan Repayment Schedule",
            self.schedule_reference,
            [
                "name",
                "parent",
                "payment_date",
                "principal_amount",
                "interest_amount",
                "total_payment",
                "status"
            ],
            as_dict=True
        )

        if not schedule:
            frappe.throw(
                "Repayment Schedule entry not found."
            )

        if schedule.parent != self.sanctioned_loan:
            frappe.throw(
                "Selected repayment schedule does not belong "
                "to the selected Sanctioned Loan."
            )

        if schedule.status == "Paid":
            frappe.throw(
                "This repayment schedule entry has already been paid."
            )

        if flt(self.principal_paid) > flt(
            schedule.principal_amount
        ):
            frappe.throw(
                "Principal Paid cannot exceed the scheduled "
                "principal amount."
            )

        if flt(self.interest_paid) > flt(
            schedule.interest_amount
        ):
            frappe.throw(
                "Interest Paid cannot exceed the scheduled "
                "interest amount."
            )

    # ------------------------------------------------------------------
    # SUBMIT
    # ------------------------------------------------------------------

    def on_submit(self):

        loan = frappe.get_doc(
            "Sanctioned Loan",
            self.sanctioned_loan
        )

        principal_paid = flt(
            self.principal_paid
        )

        interest_paid = flt(
            self.interest_paid
        )

        new_outstanding = flt(
            loan.outstanding_amount
        ) - principal_paid

        if new_outstanding < 0:
            new_outstanding = 0

        # --------------------------------------------------------------
        # Update schedule
        # --------------------------------------------------------------

        if self.schedule_reference:

            schedule = frappe.db.get_value(
                "zzLoan Repayment Schedule",
                self.schedule_reference,
                [
                    "principal_amount",
                    "interest_amount"
                ],
                as_dict=True
            )

            if schedule:

                principal_remaining = (
                    flt(schedule.principal_amount)
                    - principal_paid
                )

                interest_remaining = (
                    flt(schedule.interest_amount)
                    - interest_paid
                )

                if (
                    principal_remaining <= 0.01
                    and interest_remaining <= 0.01
                ):

                    frappe.db.set_value(
                        "zzLoan Repayment Schedule",
                        self.schedule_reference,
                        "status",
                        "Paid"
                    )

                else:

                    frappe.db.set_value(
                        "zzLoan Repayment Schedule",
                        self.schedule_reference,
                        "status",
                        "Partially Paid"
                    )

        # --------------------------------------------------------------
        # Update loan
        # --------------------------------------------------------------

        if new_outstanding <= 0.01:

            frappe.db.set_value(
                "Sanctioned Loan",
                loan.name,
                {
                    "outstanding_amount": 0,
                    "loan_status": "Closed",
                    "is_closed": 1,
                    "is_active": 0
                }
            )

        else:

            frappe.db.set_value(
                "Sanctioned Loan",
                loan.name,
                {
                    "outstanding_amount": new_outstanding,
                    "loan_status": "Active",
                    "is_closed": 0,
                    "is_active": 1
                }
            )

        frappe.db.commit()

    # ------------------------------------------------------------------
    # CANCEL
    # ------------------------------------------------------------------

    def on_cancel(self):

        loan = frappe.get_doc(
            "Sanctioned Loan",
            self.sanctioned_loan
        )

        principal_paid = flt(
            self.principal_paid
        )

        new_outstanding = (
            flt(loan.outstanding_amount)
            + principal_paid
        )

        frappe.db.set_value(
            "Sanctioned Loan",
            loan.name,
            {
                "outstanding_amount": new_outstanding,
                "loan_status": "Active",
                "is_closed": 0,
                "is_active": 1
            }
        )

        if self.schedule_reference:

            frappe.db.set_value(
                "zzLoan Repayment Schedule",
                self.schedule_reference,
                "status",
                "Pending"
            )

        frappe.db.commit()