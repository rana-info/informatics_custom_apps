# -*- coding: utf-8 -*-
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate


class SugarDMRSeason(Document):
    """One record per plant per season: fixes Season Start and Period From for the Sugar DMR."""

    def validate(self):
        if getdate(self.period_from) < getdate(self.season_from):
            frappe.throw(_("Period From cannot be before Season Start"))
        if frappe.db.exists("Sugar DMR Season", {
            "company": self.company, "plant": self.plant,
            "season_from": self.season_from, "name": ("!=", self.name),
        }):
            frappe.throw(_("A season starting on {0} is already set up for {1}").format(
                frappe.format(self.season_from, {"fieldtype": "Date"}), self.plant))