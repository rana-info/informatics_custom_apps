// Copyright (c) 2026, Yash and contributors
// For license information, please see license.txt

frappe.ui.form.on("zzBulk Leave Encashment", {
	onload: function(frm) {
		highlight_rows(frm);
	},
	refresh: function(frm) {
		highlight_rows(frm);
		
		frm.set_df_property('bulk_leave_encashment_details', 'cannot_add_rows', true);
		if(frm.doc.docstatus != 2 && frm.doc.docstatus != 1){
			frm.add_custom_button(__("Get Selected Employees"), function() {
				frm.clear_table("bulk_leave_encashment_details");
				frm.refresh_field("bulk_leave_encashment_details");
			
				let d = new frappe.ui.Dialog({
					title: __("Select Employees"),
					fields: [
						{ 
							fieldtype: "MultiSelectList",  
							fieldname: "employees", 
							label: "Employees", 
							reqd: 0,
							get_data: function() {
								return new Promise((resolve, reject) => {
									frappe.call({
										method: "get_all_employees", 
										args:{
											company:frm.doc.company,
											branch:frm.doc.branch,
											work_location:frm.doc.work_location
										},
										doc:frm.doc,
										callback: function(response) {
											if (response.message) {
												let employee_list = response.message.map(emp => ({
													value: emp.name,
													description: emp.employee_name
												}));
												resolve(employee_list);
											} else {
												reject("No employees found");
											}
										}
									});
								});
							}
						}
					],
					primary_action_label: __("Submit"),
					primary_action(values) {
						let employees = values.employees;
						frappe.call({
							method: 'get_emp_data',
							args: { employee: employees },
							doc: frm.doc,
							freeze: true,
							freeze_message: __("Getting Leave Encashment Data ..."),
							callback: function(r) {
								frm.refresh_field("bulk_leave_encashment_details");
								frm.set_value("is_updated", frm.doc.is_updated ? 0 : 1);
								frm.refresh_fields();
								highlight_rows(frm);
							}
						});
						d.hide();
					}
				});
			
				d.show(); 
			}, __("Employee Data"));
			
			
			
			frm.add_custom_button(__("Get Employee Data"),function(){
				frm.clear_table("bulk_leave_encashment_details");
				frm.refresh_field("bulk_leave_encashment_details");
				frappe.call({
					method:'get_emp_data',
					doc:frm.doc,
					freeze:true,
					freeze_message:__("Getting Leave Encashment Data ..."),
					callback:function(r){
						frm.refresh_field("bulk_leave_encashment_details");
						if(!frm.doc.is_updated){
							frm.set_value("is_updated",1);
						}else{
							frm.set_value("is_updated",0);
						}
						frm.refresh_fields();
						highlight_rows(frm);
					}
				});
			},__("Employee Data"));
		}
	},
	season:function(frm){
		frm.clear_table("bulk_leave_encashment_details");
		frm.refresh_field("bulk_leave_encashment_details");
	},
	payroll_date:function(frm){
		frm.clear_table("bulk_leave_encashment_details");
		frm.refresh_field("bulk_leave_encashment_details");
	},
});

frappe.ui.form.on("zzBulk Leave Encashment Details", {
	form_render: function(frm, cdt, cdn) {
		highlight_rows(frm);
	},
	bulk_leave_encashment_details_render: function(frm, cdt, cdn) {
		highlight_rows(frm);
	},
	available_balance: function(frm, cdt, cdn) {
		calculate_encashable_days(frm, cdt, cdn);
	},
	leave_application: function(frm, cdt, cdn) {
		calculate_encashable_days(frm, cdt, cdn);
	},
	encashable_days: function(frm, cdt, cdn) {
		let row = locals[cdt][cdn];
		if (row.encashable_days !== undefined && row.encashable_days !== null) {
			let max_allowed = flt(row.available_balance) - flt(row.leave_application);
			if (flt(row.encashable_days) > max_allowed) {
				frappe.msgprint(__("Row {0}: Encashable Days ({1}) cannot be greater than Available Balance minus Leave Application ({2}).", [row.idx, row.encashable_days, max_allowed]));
				frappe.model.set_value(cdt, cdn, "encashable_days", max_allowed);
			}
		}
	}
});

function calculate_encashable_days(frm, cdt, cdn) {
	let row = locals[cdt][cdn];
	let encashable = flt(row.available_balance) - flt(row.leave_application);
	frappe.model.set_value(cdt, cdn, "encashable_days", encashable);
}

function highlight_rows(frm) {
	if (!frm.fields_dict['bulk_leave_encashment_details']) return;
	let grid = frm.fields_dict['bulk_leave_encashment_details'].grid;
	if (!grid) return;

	setTimeout(() => {
		grid.grid_rows.forEach(grid_row => {
			if (!grid_row.row) return;
			let remarks = (grid_row.doc && grid_row.doc.remarks) ? grid_row.doc.remarks.toString().toLowerCase() : "";
			if (remarks.includes("failed")) {
				$(grid_row.row).css({
					"background-color": "#fee2e2",
					"color": "#991b1b"
				});
				$(grid_row.row).find('.grid-static-col').css({
					"background-color": "#fee2e2",
					"color": "#991b1b"
				});
			} else if (remarks.includes("successful")) {
				$(grid_row.row).css({
					"background-color": "#dcfce7",
					"color": "#166534"
				});
				$(grid_row.row).find('.grid-static-col').css({
					"background-color": "#dcfce7",
					"color": "#166534"
				});
			}
		});
	}, 100);
}


