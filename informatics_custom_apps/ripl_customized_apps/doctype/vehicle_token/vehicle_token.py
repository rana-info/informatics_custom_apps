# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import re
import frappe
from frappe import _
from frappe.model.document import Document

ALLOWED_ITEMS = ["106444", "106446", "106448"]

class VehicleToken(Document):
    def validate(self):
        self.validate_item()
        self.validate_driver_contact()

    def validate_item(self):
        if self.item and self.item not in ALLOWED_ITEMS:
            frappe.throw(_("Item Code must be one of: {0}").format(", ".join(ALLOWED_ITEMS)))

    def validate_driver_contact(self):
        if self.driver_contact:
            contact = str(self.driver_contact)
            if len(contact) != 10 or not contact.isdigit():
                frappe.throw(_("Driver Contact must be a valid 10-digit mobile number."))