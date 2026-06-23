from hrms.payroll.doctype.salary_structure.salary_structure import make_salary_slip
from erpnext.accounts.general_ledger import make_gl_entries
from datetime import datetime, timedelta
import calendar
import frappe
from frappe.model.document import Document
from frappe.utils import flt, nowdate, money_in_words, cint

class zzRetainingSalary(Document):
    def before_save(self):
        self.validate_duplicate_retaining_salary()
        self.fill_employee_working_days()
        self.create_retaining_salary_slips_and_fill_tables()
        self.calculate_net_differences()
        if self.is_new():
            self.create_salary_slips_from_cache()

    def on_submit(self):
        self.submit_retaining_salary_slips()
        if self.pay_via_salary_slip:
            self.create_additional_salary_entry()
        else:
            self.make_retaining_salary_je()
            
    def on_trash(self):
        slips = frappe.get_all(
			"zzRetaining Salary Slip",
			filters={
				"retaining_salary": self.name,
				"docstatus": 0
			},
			pluck="name"
		)
        for slip_name in slips:
            slip = frappe.get_doc("zzRetaining Salary Slip", slip_name)
            if slip.docstatus != 0:
                frappe.throw(
					f"Cannot delete Retaining Salary because "
					f"Retaining Salary Slip {slip.name} is already submitted."
				)
            frappe.delete_doc(
				"zzRetaining Salary Slip", slip_name, force=True,ignore_permissions=True
			)

    def get_pf_deductions(self, assn, total_days_month, days, end_date=None):
        if not cint(assn.get("is_pf_applicable")):
            return {}

        pf_on = (assn.get("pf_on") or "Basic").strip()
        is_pf_ceiling = cint(assn.get("is_pf_ceiling"))
        pf_ceiling_limit = flt(
            assn.get("pf_ceiling_limit")
            or assn.get("custom_pf_celing_amount")
            or 0
        )

        basic = 0

        for comp_row in assn.get("custom_salary_detail", []):
            amount = flt(comp_row.amount)
            if comp_row.salary_component == "Basic":
                basic += amount

        if (
            is_pf_ceiling
            and pf_ceiling_limit
            and basic >= pf_ceiling_limit
        ):
            pf_wages = pf_ceiling_limit
        else:
            pf_wages = basic

        pf_wages = (pf_wages / total_days_month) * days
        employee_pf = pf_wages * 0.12

        family_pension = 0
        if cint(assn.get("custom_is_family_pension_applicable")):
            retirement_date = (
                assn.get("date_of_retirement")
                or getattr(self, "date_of_retirement", None)
            )
            if not (
                retirement_date
                and end_date
                and end_date > retirement_date
            ):
                family_pension = pf_wages * 0.0833

        employer_pf = employee_pf - family_pension
        
        frappe.errprint({
            "basic": basic,
            "pf_wages": pf_wages,
            "employee_pf": employee_pf,
            "family_pension": family_pension,
            "employer_pf": employer_pf
        })

        return {
            "Employee Provident Fund": round(employee_pf, 2),
            "Family Pension": round(family_pension, 2),
            "Employer Provident Fund": round(employer_pf, 2),
        }

    def validate_duplicate_retaining_salary(self):
        selected_periods = [
            row for row in (self.paid_off_periods or [])
            if cint(row.is_selected)
        ]

        for period in selected_periods:
            existing_docs = frappe.get_all(
                "zzRetaining Salary",
                filters={
                    "employee": self.employee,
                    "docstatus": ["!=", 2],
                    "name": ["!=", self.name]
                },
                fields=["name"]
            )

            for doc in existing_docs:
                rs_doc = frappe.get_doc("zzRetaining Salary", doc.name)

                existing_selected = [
                    r for r in (rs_doc.paid_off_periods or [])
                    if cint(r.is_selected)
                ]

                for existing_period in existing_selected:
                    if (
                        frappe.utils.getdate(existing_period.from_date)
                        == frappe.utils.getdate(period.from_date)
                        and
                        frappe.utils.getdate(existing_period.to_date)
                        == frappe.utils.getdate(period.to_date)
                    ):
                        rs_link = frappe.utils.get_link_to_form(
                            "zzRetaining Salary",
                            rs_doc.name
                        )
                        frappe.throw(
                            f"Retaining Salary already exists for Employee "
                            f"<b>{self.employee}</b> for Paid Off Period "
                            f"<b>{period.from_date} to {period.to_date}</b>.<br><br>"
                            f"Existing Document: {rs_link}"
                        )

    def fill_employee_working_days(self):
        self.employees = []
        if not self.employee:
            return

        selected = [
            row for row in (self.paid_off_periods or [])
            if cint(row.is_selected) and row.from_date and row.to_date
        ]

        selected_open = [
            row for row in (self.paid_off_periods or [])
            if cint(row.is_selected) and row.from_date and not row.to_date
        ]

        if not selected and not selected_open:
            frappe.throw(
                "Please select at least one Paid Off Period "
                "with a From Date before saving."
            )

        for row in selected:
            from_date = frappe.utils.getdate(row.from_date)
            to_date = frappe.utils.getdate(row.to_date)
            current = from_date

            while current <= to_date:
                y, m = current.year, current.month
                month_end = datetime(y, m, calendar.monthrange(y, m)[1]).date()
                end = min(month_end, to_date)
                days = (end - current).days + 1
                self.append("employees", {
                    "employee_id": self.employee,
                    "from_date": current,
                    "to_date": end,
                    "total_working_days": days,
                })
                current = end + timedelta(days=1)

        for row in selected_open:
            from_date = frappe.utils.getdate(row.from_date)
            to_date = frappe.utils.getdate(nowdate())
            days = (to_date - from_date).days + 1
            self.append("employees", {
                "employee_id": self.employee,
                "from_date": from_date,
                "to_date": to_date,
                "total_working_days": days,
            })

    @staticmethod
    def _is_retained(comp_doc):
        return cint(comp_doc.get("custom_retaining_salary"))

    def create_retaining_salary_slips_and_fill_tables(self):
        self.set("earnings", [])
        self.set("deductions", [])
        earn, ded = {}, {}
        self._slip_cache = []

        for row in self.employees:
            start, end, days = row.from_date, row.to_date, row.total_working_days
            total_days_month = self.get_days_in_month(start)

            assn_list = frappe.get_all(
                "Salary Structure Assignment",
                fields=["name", "salary_structure", "custom_retaining_"],
                filters={
                    "employee": self.employee,
                    "from_date": ["<=", start],
                    "docstatus": 1,
                },
                order_by="from_date desc",
                limit=1,
            )
            if not assn_list:
                continue

            assn = frappe.get_doc("Salary Structure Assignment", assn_list[0].name)
            struct = frappe.get_doc("Salary Structure", assn.salary_structure)

            ret_pct = flt(assn.custom_retaining_)
            if not ret_pct:
                assignment_link = frappe.utils.get_link_to_form(
                    "Salary Structure Assignment", assn.name
                )
                frappe.throw(
                    f"Retaining percentage not set for Salary Structure Assignment "
                    f"{assignment_link}."
                )

            self._slip_cache.append({
                "from_date": start,
                "to_date": end,
                "days": days,
                "assn": assn.name,
                "struct": struct.name,
                "ret_pct": ret_pct,
            })

            # for comp_row in assn.get("custom_salary_detail", []):
            #     sc = comp_row.salary_component
            #     sc_doc = frappe.get_cached_doc("Salary Component", sc)
            #     if not self._is_retained(sc_doc):
            #         continue
            #     monthly = flt(comp_row.amount)
            #     prorated = (monthly / total_days_month) * days
            #     retained = prorated * ret_pct / 100

            #     data = earn.setdefault(sc, {"amount": 0.0, "old_amount": 0.0})
            #     data["amount"] += retained
            #     data["old_amount"] += prorated
            
            pf_map = self.get_pf_deductions(
                assn=assn,
                total_days_month=total_days_month,
                days=days,
                end_date=end
            )

            for comp_row in assn.get("custom_salary_detail", []):
                sc = comp_row.salary_component
                sc_doc = frappe.get_cached_doc("Salary Component", sc)

                if not self._is_retained(sc_doc):
                    continue
                
                frappe.errprint(f"Salary Cmponent Found: {sc}")
                if sc == "Employer's PF":

                    actual = flt(pf_map.get("Employee Provident Fund", 0))
                    retained = actual * ret_pct / 100

                    data = earn.setdefault(sc, {
                        "amount": 0.0,
                        "old_amount": 0.0
                    })

                    data["amount"] += retained
                    data["old_amount"] += actual
                    continue

                monthly = flt(comp_row.amount)
                prorated = (monthly / total_days_month) * days
                retained = prorated * ret_pct / 100

                data = earn.setdefault(sc, {
                    "amount": 0.0,
                    "old_amount": 0.0
                })

                data["amount"] += retained
                data["old_amount"] += prorated

            deductions_map = pf_map

            for sc, actual in deductions_map.items():
                retained = actual * ret_pct / 100
                data = ded.setdefault(sc, {"amount": 0.0, "old_amount": 0.0})
                data["amount"] += retained
                data["old_amount"] += actual

        for sc, vals in earn.items():
            self.append("earnings", {
                "salary_component": sc,
                "amount": round(vals["amount"], 2),
                "old_amount": round(vals["old_amount"], 2),
            })
        for sc, vals in ded.items():
            self.append("deductions", {
                "salary_component": sc,
                "amount": round(vals["amount"], 2),
                "old_amount": round(vals["old_amount"], 2),
            })

    def submit_retaining_salary_slips(self):
        slips = frappe.get_all(
            "zzRetaining Salary Slip",
            filters={
                "retaining_salary": self.name,
                "docstatus": 0
            },
            pluck="name"
        )

        for slip_name in slips:
            slip = frappe.get_doc("zzRetaining Salary Slip", slip_name)
            slip.posting_date = self.posting_date or nowdate()
            slip.flags.ignore_validate_update_after_submit = True
            slip.save(ignore_permissions=True)
            slip.submit()

    def create_salary_slips_from_cache(self):
        if not getattr(self, "_slip_cache", None):
            return

        for idx, meta in enumerate(self._slip_cache):
            existing = frappe.get_all(
                "zzRetaining Salary Slip",
                filters={
                    "employee": self.employee,
                    "docstatus": ("<", 2),
                    "start_date": ("<=", meta["to_date"]),
                    "end_date": (">=", meta["from_date"]),
                },
                pluck="name",
            )
            if existing:
                continue

            slip = frappe.new_doc("zzRetaining Salary Slip")
            slip.employee = self.employee
            slip.company = self.company
            slip.salary_structure = meta.get("struct")

            month_start = datetime(
                meta["from_date"].year, meta["from_date"].month, 1
            ).date()
            month_end = datetime(
                meta["from_date"].year,
                meta["from_date"].month,
                calendar.monthrange(meta["from_date"].year, meta["from_date"].month)[1]
            ).date()
            slip.start_date = month_start
            slip.end_date = month_end

            slip.payment_days = meta["days"]
            slip.total_working_days = self.get_days_in_month(meta["from_date"])
            slip.currency = self.currency or frappe.defaults.get_global_default("currency")
            slip.posting_date = self.posting_date or nowdate()
            slip.exchange_rate = 1
            slip.payroll_frequency = "Monthly"

            gross = ded = 0.0
            employee_row = self.employees[idx]
            total_days_month = self.get_days_in_month(employee_row.from_date)
            assn = frappe.get_doc("Salary Structure Assignment", meta["assn"])
            ret_pct = flt(meta["ret_pct"])
            days = meta["days"]

            # for comp_row in assn.get("custom_salary_detail", []):
            #     sc = comp_row.salary_component
            #     sc_doc = frappe.get_cached_doc("Salary Component", sc)
            #     if not self._is_retained(sc_doc):
            #         continue
            #     monthly = flt(comp_row.amount)
            #     if not monthly:
            #         continue
            #     actual = (monthly / total_days_month) * days
            #     retained = actual * ret_pct / 100
            #     slip.append("earnings", {
            #         "salary_component": sc,
            #         "amount": round(retained, 2),
            #         "old_amount": round(actual, 2)
            #     })
            #     gross += retained
            
            pf_map = self.get_pf_deductions(
                assn=assn,
                total_days_month=total_days_month,
                days=days,
                end_date=meta["to_date"]
            )

            for comp_row in assn.get("custom_salary_detail", []):

                sc = comp_row.salary_component
                sc_doc = frappe.get_cached_doc("Salary Component", sc)

                if not self._is_retained(sc_doc):
                    continue
                
                frappe.errprint(f"Salary Component Found: {sc}")
                if sc == "Employer's PF":

                    actual = flt(pf_map.get("Employee Provident Fund", 0))
                    # frappe.errprint({
                    #     "component": sc,
                    #     "employee_pf": pf_map.get("Employee Provident Fund"),
                    #     "family_pension": pf_map.get("Family Pension"),
                    #     "employer_pf": pf_map.get("Employer Provident Fund"),
                    #     "actual_used": actual
                    # })
                    retained = actual * ret_pct / 100

                    slip.append("earnings", {
                        "salary_component": sc,
                        "amount": round(retained, 2),
                        "old_amount": round(actual, 2)
                    })

                    gross += retained
                    continue

                monthly = flt(comp_row.amount)

                if not monthly:
                    continue

                actual = (monthly / total_days_month) * days
                retained = actual * ret_pct / 100

                slip.append("earnings", {
                    "salary_component": sc,
                    "amount": round(retained, 2),
                    "old_amount": round(actual, 2)
                })

                gross += retained

            deductions_map = pf_map

            for sc, actual in deductions_map.items():
                retained = actual * ret_pct / 100
                slip.append("deductions", {
                    "salary_component": sc,
                    "amount": round(retained, 2),
                    "old_amount": round(actual, 2)
                })
                ded += retained

            slip.gross_pay = gross
            slip.total_deduction = ded
            slip.net_pay = gross - ded
            slip.rounded_total = round(slip.net_pay)
            slip.base_gross_pay = gross
            slip.base_total_deduction = ded
            slip.base_net_pay = slip.net_pay
            slip.base_rounded_total = slip.rounded_total
            slip.total_in_words = money_in_words(slip.rounded_total, slip.currency)
            slip.base_total_in_words = money_in_words(slip.base_rounded_total, slip.currency)
            slip.net_pay_info = "Net\u00A0Pay\u00A0=\u00A0Gross\u00A0―\u00A0Deductions"

            bank = frappe.get_cached_value(
                "Employee", self.employee,
                ["bank_name", "bank_ac_no", "salary_mode"],
                as_dict=True
            )
            if bank:
                slip.mode_of_payment = bank.salary_mode
                slip.bank_name = bank.bank_name
                slip.bank_account_no = bank.bank_ac_no

            slip.insert()
            if self.name:
                slip.db_set("retaining_salary", self.name)

    def calculate_net_differences(self):
        self.net_earnings = sum(flt(e.amount) for e in self.earnings)
        self.net_deductions = sum(flt(d.amount) for d in self.deductions)
        self.net_retaining_salary = self.net_earnings - self.net_deductions
        self.total_amount = self.net_retaining_salary

    def create_additional_salary_entry(self):
        payroll_date = None
        for row in (self.paid_off_periods or []):
            if cint(row.is_selected) and row.to_date:
                d = frappe.utils.getdate(row.to_date)
                if not payroll_date or d > payroll_date:
                    payroll_date = d

        if not payroll_date:
            payroll_date = frappe.utils.getdate(self.posting_date)

        ad = frappe.new_doc("Additional Salary")
        ad.employee = self.employee
        ad.employee_name = self.employee_name
        ad.department = frappe.db.get_value("Employee", self.employee, "department")
        ad.company = self.company
        ad.payroll_date = self.posting_date or nowdate()
        ad.from_date = str(payroll_date)
        ad.to_date = str(payroll_date)
        ad.salary_component = self.salary_component
        ad.currency = self.currency
        ad.amount = abs(self.total_amount)
        ad.ref_doctype = "zzRetaining Salary"
        ad.ref_docname = self.name
        ad.insert()
        ad.submit()
        self.flags.ignore_validate_update_after_submit = True
        self.status = "Submitted"
        self.save(ignore_permissions=True)

    def make_retaining_salary_je(self):
        amount = self.total_amount
        expense_acct = self.expense_account
        payable_acct = self.payable_account
        cost_center = self.cost_center
        employee = self.employee

        je = frappe.new_doc("Journal Entry")
        je.voucher_type = "Journal Entry"
        je.posting_date = self.posting_date or nowdate()
        je.company = self.company
        je.branch = self.branch
        je.company_gstin = getattr(self, "company_gstin", "")
        je.segment = getattr(self, "segment", "")
        je.section = getattr(self, "section", "")
        je.mode_of_payment = getattr(self, "mode_of_payment", None)

        formatted_amount = f"{amount:,.2f}"
        remark_text = (
            f"Retaining amount - {formatted_amount} "
            f"created from zzRetaining Salary {self.name}"
        )
        je.remark = remark_text
        je.user_remark = remark_text
        je.cheque_no = self.name
        je.cheque_date = nowdate()

        je.append("accounts", {
            "account": expense_acct,
            "debit_in_account_currency": amount,
            "credit_in_account_currency": 0,
            "cost_center": cost_center,
        })

        je.append("accounts", {
            "account": payable_acct,
            "party_type": "Employee",
            "party": employee,
            "debit_in_account_currency": 0,
            "credit_in_account_currency": amount,
            "cost_center": cost_center,
        })

        je.insert(ignore_permissions=True)
        je.submit()
        return je

    @staticmethod
    def get_days_in_month(d):
        if isinstance(d, str):
            d = datetime.strptime(d, "%Y-%m-%d").date()
        return calendar.monthrange(d.year, d.month)[1]