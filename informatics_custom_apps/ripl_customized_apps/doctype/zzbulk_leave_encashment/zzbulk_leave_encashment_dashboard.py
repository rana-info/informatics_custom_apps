import frappe
from frappe import _

def get_data():
	return {
		"fieldname": "custom_bulk_leave_encashment",
		"transactions": [
			{"label": _("Payments"), "items": ["Leave Encashment"]},
		],
	}
