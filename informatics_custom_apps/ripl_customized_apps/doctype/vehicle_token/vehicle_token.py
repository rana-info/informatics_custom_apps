# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import re
import frappe
from frappe import _
from frappe.model.document import Document

ALLOWED_ITEMS = ["106444", "106446", "106448"]
VEHICLE_REGEX = re.compile(r'^[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}$')

class VehicleToken(Document):
    def validate(self):
        self.validate_vehicle_number()
        self.validate_item()
        self.validate_driver_contact()

    def validate_vehicle_number(self):
        if self.vehicle_number:
            self.vehicle_number = self.vehicle_number.upper().replace(" ", "")
            if not VEHICLE_REGEX.match(self.vehicle_number):
                frappe.throw(_("Invalid Vehicle Number format. Expected e.g. KA01AB1234"))

    def validate_item(self):
        if self.item and self.item not in ALLOWED_ITEMS:
            frappe.throw(_("Item Code must be one of: {0}").format(", ".join(ALLOWED_ITEMS)))

    def validate_driver_contact(self):
        if self.driver_contact:
            contact = str(self.driver_contact)
            if len(contact) != 10 or not contact.isdigit():
                frappe.throw(_("Driver Contact must be a valid 10-digit mobile number."))