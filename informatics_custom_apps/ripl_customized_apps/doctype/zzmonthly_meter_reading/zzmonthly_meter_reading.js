// Copyright (c) 2025, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.ui.form.on('zzMonthly Meter Reading', {
	get_data: function(frm) {
		frappe.call({
			method:"get_data",
			doc:frm.doc,
			freeze: true,
            freeze_message: __('Fetching Data'),
			callback:function(r){
				// frm.fields_dict.meter_reading.grid.toggle_reqd
				// 			("employee", "reqd",1)
				frm.refresh_field("meter_reading")
			}
		})
	},
	
	month: function(frm) {
		frappe.call({
			method:"get_last_date",
			doc:frm.doc,
			callback:function(r){
				if(r.message){
					frm.set_value("date",r.message)
					frm.refresh_field("date")
				}
			}
		})
	},
});
frappe.ui.form.on('zzMeter Reading', {
	closing_reading:function(frm,cdt,cdn){
		let child=locals[cdt][cdn]

		child.consumed_units =child.closing_reading-child.opening_reading

		if(child.consumed_units >child.allowed_units){
			child.chargeable_units=child.consumed_units-child.allowed_units
			child.amount=child.chargeable_units * child.unit_rate
		}
		
		frm.refresh_field("meter_reading")


	}
});