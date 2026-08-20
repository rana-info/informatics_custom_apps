frappe.ui.form.on("zzLeaves Adjustment Tool", {
    setup(frm) {
        frm.set_query("branch", function () {
            return {
                filters: {
                    company: frm.doc.company
                }
            };
        });
        frm.set_query("leave_period", function () {
            return {
                filters: {
                    company: frm.doc.company
                }
            };
        });
    },
    refresh(frm) {
        frm.set_intro();
        frm.set_intro(__("Note: This tool is only used for Leave Allocations, not for Expiry."), "orange");

        if(frm.doc.docstatus !== 1 && frm.doc.docstatus !== 2) {
            frm.add_custom_button(__("Get Selected Employees"), function() {
                if (!frm.doc.company || !frm.doc.branch) {
                    frappe.msgprint(__('Please select Company and Plant first.'));
                    return;
                }

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
                                        method: "frappe.client.get_list", 
                                        args:{
                                            doctype: "Employee",
                                            filters: {
                                                company: frm.doc.company,
                                                branch: frm.doc.branch,
                                                status: "Active"
                                            },
                                            fields: ["name", "employee_name"],
                                            limit_page_length: 0
                                        },
                                        callback: function(response) {
                                            if (response.message) {
                                                let employee_list = response.message.map(emp => ({
                                                    value: emp.name,
                                                    description: emp.employee_name
                                                }));
                                                resolve(employee_list);
                                            } else {
                                                resolve([]);
                                            }
                                        }
                                    });
                                });
                            }
                        }
                    ],
                    primary_action_label: __("Submit"),
                    primary_action(values) {
                        let selected_emp = values.employees || [];
                        if (selected_emp.length > 0) {
                            frappe.call({
                                method: "informatics_custom_apps.ripl_customized_apps.doctype.zzleaves_adjustment_tool.zzleaves_adjustment_tool.get_employee_leave_data",
                                args: {
                                    company: frm.doc.company,
                                    branch: frm.doc.branch,
                                    leave_period: frm.doc.leave_period,
                                    from_date: frm.doc.from_date,
                                    to_date: frm.doc.to_date,
                                    selected_employees: selected_emp
                                },
                                freeze: true,
                                freeze_message: __("Getting Selected Employee Data ..."),
                                callback: function(r) {
                                    frm.clear_table("leaves_data");
                                    if (r.message && r.message.length > 0) {
                                        r.message.forEach(item => {
                                            let row = frm.add_child("leaves_data");
                                            row.employee = item.employee;
                                            row.employee_name = item.employee_name;
                                            row.leave_type = item.leave_type;
                                            row.leave_allocation = item.leave_allocation;
                                            row.current_leave_balance = item.current_leave_balance;
                                        });
                                    } else {
                                        frappe.msgprint(__("No Leave Allocations (Earned Leave / Sick Leave-Sugar) found for selected employees."));
                                    }
                                    frm.refresh_field("leaves_data");
                                }
                            });
                        }
                        d.hide();
                    }
                });
            
                d.show(); 
            }, __("Employee Data"));
            
            frm.add_custom_button(__("Get Employee Data"), function(){
                if (!frm.doc.company || !frm.doc.branch) {
                    frappe.msgprint(__('Please select Company and Plant first.'));
                    return;
                }

                frappe.call({
                    method: "informatics_custom_apps.ripl_customized_apps.doctype.zzleaves_adjustment_tool.zzleaves_adjustment_tool.get_employee_leave_data",
                    args: {
                        company: frm.doc.company,
                        branch: frm.doc.branch,
                        leave_period: frm.doc.leave_period,
                        from_date: frm.doc.from_date,
                        to_date: frm.doc.to_date
                    },
                    freeze: true,
                    freeze_message: __("Getting Employees Data ..."),
                    callback: function(r) {
                        frm.clear_table("leaves_data");
                        if (r.message && r.message.length > 0) {
                            r.message.forEach(item => {
                                let row = frm.add_child("leaves_data");
                                row.employee = item.employee;
                                row.employee_name = item.employee_name;
                                row.leave_type = item.leave_type;
                                row.leave_allocation = item.leave_allocation;
                                row.current_leave_balance = item.current_leave_balance;
                            });
                        } else {
                            frappe.msgprint(__("No Leave Allocations (Earned Leave / Sick Leave-Sugar) found for active employees of the selected Company and Plant."));
                        }
                        frm.refresh_field("leaves_data");
                    }
                });
            }, __("Employee Data"));
        }
    },

    company(frm) {
        frm.set_value("branch", "");
    },

    leave_period(frm) {
        if (frm.doc.leave_period) {
            frappe.db.get_value("Leave Period", frm.doc.leave_period, ["from_date", "to_date"], (r) => {
                if (r) {
                    frm.set_value("from_date", r.from_date);
                    frm.set_value("to_date", r.to_date);
                }
            });
        }
    }
});

frappe.ui.form.on("zzLeaves Data", {
    leave_count(frm, cdt, cdn) {
        let row = locals[cdt][cdn];
        if (row.leave_count && row.leave_count < 0) {
            frappe.model.set_value(cdt, cdn, "leave_count", Math.abs(row.leave_count));
            frappe.show_alert({
                message: __("Negative leave are not allowed"),
                indicator: "red"
            });
        }
    }
});