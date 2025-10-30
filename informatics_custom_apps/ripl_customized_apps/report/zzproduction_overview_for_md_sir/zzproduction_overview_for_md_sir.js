// Copyright (c) 2025, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.query_reports["zzProduction Overview For MD Sir"] = {
	"filters": [
		 {
            "fieldname":"date",
            "label": __("Date"),
            "fieldtype":"Date",
			"default":"Today",
            "reqd":1
        }
	]
};
