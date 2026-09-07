# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_months, flt, getdate


class SanctionedLoan(Document):

    # ==========================================================
    # VALIDATE
    # ==========================================================

    def validate(self):
        self.validate_disbursements()
        self.set_amount_disbursed()

        if self.docstatus == 0:
            self.set_outstanding_amount()

    # ==========================================================
    # BEFORE SUBMIT
    # ==========================================================

    def before_submit(self):
        self.validate_disbursements()
        self.set_amount_disbursed()

        if flt(self.amount_disbursed) > 0:
            self.outstanding_amount = flt(self.amount_disbursed)
            self.loan_status = "Active"

            # Generate schedule automatically on first submit
            self.generate_repayment_schedule(from_submit=True)

        else:
            self.outstanding_amount = 0
            self.loan_status = "Draft"

    # ==========================================================
    # CANCEL
    # ==========================================================

    def before_cancel(self):
        """
        Clear transaction/derived information from the loan so that
        an amended document does not inherit old disbursements,
        repayment schedules, balances, or loan status.
        """

        self.set("loan_disbursements", [])
        self.set("repayment_schedule", [])

        self.amount_disbursed = 0
        self.outstanding_amount = 0
        self.loan_status = None

    def on_cancel(self):
        """
        Ensure child records are removed from the cancelled document.

        zzLoan Repayment documents are intentionally not deleted here,
        because they are independent financial transactions and may
        already be submitted.
        """

        frappe.db.delete(
            "zzLoan Disbursement",
            {
                "parent": self.name,
                "parenttype": "Sanctioned Loan",
                "parentfield": "loan_disbursements",
            },
        )

        frappe.db.delete(
            "zzLoan Repayment Schedule",
            {
                "parent": self.name,
                "parenttype": "Sanctioned Loan",
                "parentfield": "repayment_schedule",
            },
        )

        frappe.db.set_value(
            "Sanctioned Loan",
            self.name,
            {
                "amount_disbursed": 0,
                "outstanding_amount": 0,
                "loan_status": None,
            },
            update_modified=False,
        )

    # ==========================================================
    # DISBURSEMENT VALIDATION
    # ==========================================================

    def validate_disbursements(self):
        total_disbursed = sum(
            flt(row.disbursement_amount)
            for row in (self.loan_disbursements or [])
        )

        if total_disbursed > flt(self.sanctioned_amount):
            frappe.throw(
                "Total Disbursed Amount cannot exceed Sanctioned Amount."
            )

    def set_amount_disbursed(self):
        self.amount_disbursed = sum(
            flt(row.disbursement_amount)
            for row in (self.loan_disbursements or [])
        )

    def set_outstanding_amount(self):
        if self.docstatus == 0:
            self.outstanding_amount = flt(self.amount_disbursed)

    # ==========================================================
    # ADD DISBURSEMENT
    # ==========================================================

    @frappe.whitelist()
    def add_disbursement(
        self,
        disbursement_date=None,
        disbursement_amount=0,
        reference_number=None,
    ):

        if self.docstatus != 1:
            frappe.throw(
                "Disbursement can only be added after the loan is submitted."
            )

        disbursement_amount = flt(disbursement_amount)

        if disbursement_amount <= 0:
            frappe.throw(
                "Disbursement Amount must be greater than zero."
            )

        if not disbursement_date:
            frappe.throw(
                "Disbursement Date is required."
            )

        # ------------------------------------------------------
        # Get existing disbursed amount
        # ------------------------------------------------------

        current_disbursed = frappe.db.sql(
            """
            SELECT COALESCE(SUM(disbursement_amount), 0)
            FROM `tabzzLoan Disbursement`
            WHERE
                parent = %s
                AND parenttype = 'Sanctioned Loan'
                AND parentfield = 'loan_disbursements'
            """,
            self.name,
        )[0][0]

        current_disbursed = flt(current_disbursed)

        new_disbursed = (
            current_disbursed + disbursement_amount
        )

        if new_disbursed > flt(self.sanctioned_amount):
            frappe.throw(
                "Total Disbursed Amount cannot exceed Sanctioned Amount."
            )

        # ------------------------------------------------------
        # Insert disbursement
        # ------------------------------------------------------

        frappe.get_doc(
            {
                "doctype": "zzLoan Disbursement",
                "parent": self.name,
                "parenttype": "Sanctioned Loan",
                "parentfield": "loan_disbursements",
                "disbursement_date": disbursement_date,
                "disbursement_amount": disbursement_amount,
                "reference_number": reference_number,
            }
        ).insert(ignore_permissions=True)

        # ------------------------------------------------------
        # Recalculate actual outstanding
        # ------------------------------------------------------
        # No extra_disbursement is added here because the row
        # has already been inserted.

        outstanding = self.get_actual_outstanding()

        frappe.db.set_value(
            "Sanctioned Loan",
            self.name,
            {
                "amount_disbursed": new_disbursed,
                "outstanding_amount": outstanding,
                "loan_status": "Active",
            },
            update_modified=True,
        )

        frappe.db.commit()

        return {
            "amount_disbursed": new_disbursed,
            "outstanding_amount": outstanding,
        }

    # ==========================================================
    # ACTUAL OUTSTANDING
    # ==========================================================

    def get_actual_outstanding(self):

        total_disbursed = frappe.db.sql(
            """
            SELECT COALESCE(SUM(disbursement_amount), 0)
            FROM `tabzzLoan Disbursement`
            WHERE
                parent = %s
                AND parenttype = 'Sanctioned Loan'
                AND parentfield = 'loan_disbursements'
            """,
            self.name,
        )[0][0]

        total_principal_repaid = frappe.db.sql(
            """
            SELECT COALESCE(SUM(principal_paid), 0)
            FROM `tabzzLoan Repayment`
            WHERE
                sanctioned_loan = %s
                AND docstatus = 1
            """,
            self.name,
        )[0][0]

        outstanding = (
            flt(total_disbursed)
            - flt(total_principal_repaid)
        )

        return max(flt(outstanding), 0)

    # ==========================================================
    # TOTAL PAID
    # ==========================================================

    def get_total_paid(self):

        total_paid = frappe.db.sql(
            """
            SELECT COALESCE(SUM(total_paid), 0)
            FROM `tabzzLoan Repayment`
            WHERE
                sanctioned_loan = %s
                AND docstatus = 1
            """,
            self.name,
        )[0][0]

        return flt(total_paid)

    # ==========================================================
    # LOAN SUMMARY
    # ==========================================================

    @frappe.whitelist()
    def get_loan_summary(self):

        outstanding = 0
        paid_amount = 0

        if self.docstatus == 1:
            outstanding = self.get_actual_outstanding()
            paid_amount = self.get_total_paid()

        return {
            "loan_status": self.loan_status,
            "outstanding_amount": outstanding,
            "paid_amount": paid_amount,
        }

    # ==========================================================
    # GENERATE REPAYMENT SCHEDULE
    # ==========================================================

    @frappe.whitelist()
    def generate_repayment_schedule(self, from_submit=False):

        # During before_submit, the document is still docstatus = 0.
        # For manual generation, it must already be submitted.

        if not from_submit and self.docstatus != 1:
            frappe.throw(
                "Sanctioned Loan must be submitted before generating the repayment schedule."
            )

        if not self.repayment_start_date:
            frappe.throw(
                "Please set Repayment Start Date."
            )

        if not self.repayment_interval:
            frappe.throw(
                "Please select Repayment Interval."
            )

        if flt(self.repayment_amount) <= 0:
            frappe.throw(
                "Repayment Amount must be greater than zero."
            )

        if flt(self.loan_interest) < 0:
            frappe.throw(
                "Loan Interest cannot be negative."
            )

        periods_per_year = {
            "Monthly": 12,
            "Quarterly": 4,
            "Half-Yearly": 2,
            "Yearly": 1,
        }

        months_per_period = {
            "Monthly": 1,
            "Quarterly": 3,
            "Half-Yearly": 6,
            "Yearly": 12,
        }

        periods = periods_per_year.get(
            self.repayment_interval
        )

        months = months_per_period.get(
            self.repayment_interval
        )

        if not periods or not months:
            frappe.throw(
                f"Unsupported repayment interval: {self.repayment_interval}"
            )

        # ======================================================
        # FIRST SUBMISSION
        # ======================================================

        if from_submit:

            self.set("repayment_schedule", [])

            outstanding = flt(self.amount_disbursed)

            payment_date = getdate(
                self.repayment_start_date
            )

            return self.create_schedule_rows(
                outstanding=outstanding,
                payment_date=payment_date,
                months=months,
                periods=periods,
                append_to_document=True,
            )

        # ======================================================
        # MANUAL REGENERATION AFTER SUBMISSION
        # ======================================================

        existing_schedule = frappe.get_all(
            "zzLoan Repayment Schedule",
            filters={
                "parent": self.name,
                "parenttype": "Sanctioned Loan",
                "parentfield": "repayment_schedule",
            },
            fields=[
                "name",
                "payment_date",
                "status",
                "idx",
            ],
            order_by="payment_date asc, idx asc",
        )

        # Preserve paid and partially paid schedule rows.
        preserved_rows = [
            row
            for row in existing_schedule
            if row.status in ("Paid", "Partially Paid")
        ]

        pending_rows = [
            row
            for row in existing_schedule
            if row.status == "Pending"
        ]

        # Delete old pending schedule.
        for row in pending_rows:
            frappe.db.delete(
                "zzLoan Repayment Schedule",
                {"name": row.name},
            )

        outstanding = self.get_actual_outstanding()

        # Fully repaid loan.
        if outstanding <= 0.01:

            self.update_loan_status(
                outstanding=0
            )

            self.normalize_schedule_indexes()

            frappe.db.commit()

            return {
                "message": "Loan has no outstanding principal.",
                "created": 0,
                "preserved": len(preserved_rows),
            }

        # Start after the latest preserved payment.
        if preserved_rows:

            latest_preserved = max(
                preserved_rows,
                key=lambda row: (
                    getdate(row.payment_date),
                    row.idx or 0,
                ),
            )

            payment_date = add_months(
                getdate(latest_preserved.payment_date),
                months,
            )

        else:

            payment_date = getdate(
                self.repayment_start_date
            )

        result = self.create_schedule_rows(
            outstanding=outstanding,
            payment_date=payment_date,
            months=months,
            periods=periods,
            append_to_document=False,
        )

        self.normalize_schedule_indexes()

        actual_outstanding = self.get_actual_outstanding()

        self.update_loan_status(
            outstanding=actual_outstanding
        )

        frappe.db.commit()

        result["preserved"] = len(preserved_rows)
        result["outstanding"] = actual_outstanding

        return result

    # ==========================================================
    # CREATE SCHEDULE ROWS
    # ==========================================================

    def create_schedule_rows(
        self,
        outstanding,
        payment_date,
        months,
        periods,
        append_to_document=False,
    ):

        annual_interest_rate = (
            flt(self.loan_interest) / 100
        )

        periodic_interest_rate = (
            annual_interest_rate / periods
        )

        repayment_amount = flt(
            self.repayment_amount
        )

        installment_no = 0
        max_installments = 1000

        while outstanding > 0.01:

            installment_no += 1

            if installment_no > max_installments:
                frappe.throw(
                    "Unable to generate repayment schedule. "
                    "Maximum number of installments exceeded."
                )

            opening_balance = flt(
                outstanding,
                2,
            )

            interest_amount = flt(
                opening_balance * periodic_interest_rate,
                2,
            )

            principal_amount = flt(
                repayment_amount - interest_amount,
                2,
            )

            if principal_amount <= 0:
                frappe.throw(
                    "Repayment Amount is not sufficient to cover "
                    "the interest for the installment."
                )

            if principal_amount > opening_balance:
                principal_amount = opening_balance

            total_payment = flt(
                principal_amount + interest_amount,
                2,
            )

            closing_balance = flt(
                opening_balance - principal_amount,
                2,
            )

            row_data = {
                "payment_date": payment_date,
                "opening_balance": opening_balance,
                "principal_amount": principal_amount,
                "interest_amount": interest_amount,
                "total_payment": total_payment,
                "closing_balance": closing_balance,
                "status": "Pending",
            }

            # During submission, append to the parent document.
            if append_to_document:

                self.append(
                    "repayment_schedule",
                    row_data,
                )

            # After submission, insert directly.
            else:

                frappe.get_doc(
                    {
                        "doctype": "zzLoan Repayment Schedule",
                        "parent": self.name,
                        "parenttype": "Sanctioned Loan",
                        "parentfield": "repayment_schedule",
                        **row_data,
                    }
                ).insert(ignore_permissions=True)

            outstanding = closing_balance

            if outstanding <= 0.01:
                break

            payment_date = add_months(
                payment_date,
                months,
            )

        return {
            "message": "Repayment schedule generated successfully.",
            "created": installment_no,
        }

    # ==========================================================
    # NORMALIZE SCHEDULE INDEX
    # ==========================================================

    def normalize_schedule_indexes(self):

        rows = frappe.get_all(
            "zzLoan Repayment Schedule",
            filters={
                "parent": self.name,
                "parenttype": "Sanctioned Loan",
                "parentfield": "repayment_schedule",
            },
            fields=[
                "name",
                "payment_date",
                "idx",
            ],
            order_by="payment_date asc, idx asc, creation asc",
        )

        for index, row in enumerate(
            rows,
            start=1,
        ):

            frappe.db.set_value(
                "zzLoan Repayment Schedule",
                row.name,
                "idx",
                index,
                update_modified=False,
            )

    # ==========================================================
    # UPDATE LOAN STATUS
    # ==========================================================

    def update_loan_status(self, outstanding=None):

        if outstanding is None:
            outstanding = self.get_actual_outstanding()

        outstanding = flt(outstanding)

        total_disbursed = frappe.db.sql(
            """
            SELECT COALESCE(SUM(disbursement_amount), 0)
            FROM `tabzzLoan Disbursement`
            WHERE
                parent = %s
                AND parenttype = 'Sanctioned Loan'
                AND parentfield = 'loan_disbursements'
            """,
            self.name,
        )[0][0]

        total_disbursed = flt(total_disbursed)

        if total_disbursed <= 0:

            values = {
                "amount_disbursed": 0,
                "outstanding_amount": 0,
                "loan_status": "Draft",
            }

        elif outstanding <= 0.01:

            values = {
                "amount_disbursed": total_disbursed,
                "outstanding_amount": 0,
                "loan_status": "Closed",
            }

        else:

            values = {
                "amount_disbursed": total_disbursed,
                "outstanding_amount": outstanding,
                "loan_status": "Active",
            }

        frappe.db.set_value(
            "Sanctioned Loan",
            self.name,
            values,
            update_modified=True,
        )

    # ==========================================================
    # GET NEXT PENDING REPAYMENT
    # ==========================================================

    @frappe.whitelist()
    def get_next_pending_repayment(self):

        if self.docstatus != 1:
            frappe.throw(
                "Sanctioned Loan must be submitted."
            )

        schedule = frappe.db.sql(
            """
            SELECT
                name,
                payment_date,
                principal_amount,
                interest_amount,
                total_payment,
                status

            FROM `tabzzLoan Repayment Schedule`

            WHERE
                parent = %s
                AND parenttype = 'Sanctioned Loan'
                AND parentfield = 'repayment_schedule'
                AND status = 'Pending'

            ORDER BY
                payment_date ASC,
                idx ASC

            LIMIT 1
            """,
            self.name,
            as_dict=True,
        )

        return (
            schedule[0]
            if schedule
            else None
        )