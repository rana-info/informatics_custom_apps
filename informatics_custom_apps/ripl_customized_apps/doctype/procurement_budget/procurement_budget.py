# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class ProcurementBudget(Document):

    def autoname(self):

        company_abbr = frappe.db.get_value(
            "Company",
            self.company,
            "abbr"
        )

        account_name = frappe.db.get_value(
            "Account",
            self.gl,
            "account_name"
        )

        gl_abbr = self.generate_gl_abbr(account_name)

        fiscal_year = self.fiscal_year

        self.name = (
            f"PB-{company_abbr}-{gl_abbr}-{fiscal_year}"
        )

    def generate_gl_abbr(self, account_name):

        words = account_name.split()

        abbr = ""

        for word in words:

            if word:
                abbr += word[0].upper()

        return abbr

    def validate(self):

        self.validate_duplicate_rows()
    
    def on_update_after_submit(self):

        self.validate_budget_consumption()

    def validate_duplicate_rows(self):

        combinations = set()

        for row in self.budget_details:

            key = (
                row.cost_center,
                row.plant,
                row.segment
            )

            if key in combinations:

                frappe.throw(
                    f"""
                    Duplicate Row Found:<br><br>

                    Cost Center: <b>{row.cost_center}</b><br>
                    Plant: <b>{row.plant}</b><br>
                    Segment: <b>{row.segment}</b>
                    """
                )

            combinations.add(key)

    def validate_budget_consumption(self):

        if not self.fiscal_year:
            return

        fy_doc = frappe.get_doc(
            "Fiscal Year",
            self.fiscal_year
        )

        for row in self.budget_details:

            mr_consumed = self.get_consumed_amount(
                doctype="Material Request",
                cost_center=row.cost_center,
                plant=row.plant,
                segment=row.segment,
                from_date=fy_doc.year_start_date,
                to_date=fy_doc.year_end_date
            )

            po_consumed = self.get_consumed_amount(
                doctype="Purchase Order",
                cost_center=row.cost_center,
                plant=row.plant,
                segment=row.segment,
                from_date=fy_doc.year_start_date,
                to_date=fy_doc.year_end_date
            )

            total_consumed = mr_consumed + po_consumed

            if total_consumed > row.budget_amount:

                frappe.msgprint(
                    f"""
                    Budget Already Consumed More Than Entered Budget
                    For Row #{row.idx}<br><br>

                    Cost Center: <b>{row.cost_center}</b><br>
                    Plant: <b>{row.plant}</b><br>
                    Segment: <b>{row.segment}</b><br><br>

                    Budget Amount: <b>{row.budget_amount}</b><br>
                    MR Budget Consumed: <b>{mr_consumed}</b><br>
                    PO Budget Consumed: <b>{po_consumed}</b><br>
                    Total Consumed: <b>{total_consumed}</b>
                    """,
                    title="Budget Consumption Warning",
                    indicator="orange"
                )

    def get_consumed_amount(
        self,
        doctype,
        cost_center,
        plant,
        segment,
        from_date,
        to_date
    ):

        extra_condition = ""
        if doctype == "Material Request":

            extra_condition += """
                AND parent.material_request_type = 'Purchase'
            """

        query = f"""
            SELECT
                SUM(child.amount)
            FROM
                `tab{doctype} Item` child
            INNER JOIN
                `tab{doctype}` parent
                ON parent.name = child.parent
            WHERE
                parent.docstatus = 1
                AND parent.company = %(company)s
                AND parent.transaction_date BETWEEN %(from_date)s AND %(to_date)s
                AND child.cost_center = %(cost_center)s
                AND child.branch = %(plant)s
                AND child.segment = %(segment)s
                AND child.expense_account = %(gl)s
                {extra_condition}
        """

        result = frappe.db.sql(
            query,
            {
                "company": self.company,
                "from_date": from_date,
                "to_date": to_date,
                "cost_center": cost_center,
                "plant": plant,
                "segment": segment,
                "gl": self.gl
            }
        )

        return result[0][0] or 0