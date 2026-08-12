# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# fieldnames of the 6 Table fields on this doctype -- must match the doctype JSON
CHILD_TABLE_FIELDS = [
   "punjab",
   "belwara",
   "superior_biofuels",
   "rsld"
]


class CompetitorRateComparision(Document):
    def validate(self):
        self.sync_with_master()

    # def before_submit(self):
    #     self.validate_all_rates_entered()

    def sync_with_master(self):
        """Rebuild every child table from the current master
        (Maize Rate Comparison Settings), so rows can never drift from
        the master -- whether the doc was edited from the UI or via API.
        Any rate already entered by the user is preserved by matching
        on (company_name, location)."""
        settings = frappe.get_single("Maize Rate Comparison Settings")

        for fieldname in CHILD_TABLE_FIELDS:
            master_rows = settings.get(fieldname) or []
            existing_rows = self.get(fieldname) or []

            existing_rates = {
                (row.company_name, row.location): row.rate_per_qtl
                for row in existing_rows
            }

            self.set(fieldname, [])
            for m in master_rows:
                self.append(
                    fieldname,
                    {
                        "company_name": m.company_name,
                        "location": m.location,
                        "rate_per_qtl": existing_rates.get(
                            (m.company_name, m.location)
                        ),
                    },
                )

    def validate_all_rates_entered(self):
        missing = []
        for fieldname in CHILD_TABLE_FIELDS:
            for row in self.get(fieldname) or []:
                if row.rate_per_qtl in (None, 0):
                    missing.append(f"{row.company_name} ({row.location})")

        if missing:
            frappe.throw(
                "Please enter Rate per Qtl for all companies before submitting. "
                "Missing: {}".format(", ".join(missing))
            )


@frappe.whitelist()
def get_master_plant_rows():
    """Called by the client script on a new document so the user sees
    company/location rows immediately, before the first save."""
    settings = frappe.get_single("Maize Rate Comparison Settings")
    result = {}
    for fieldname in CHILD_TABLE_FIELDS:
        result[fieldname] = [
            {"company_name": r.company_name, "location": r.location}
            for r in (settings.get(fieldname) or [])
        ]
    return result
