// Copyright (c) 2025, Monil Kamboj and contributors
// For license information, please see license.txt

function clear_fields(frm) {
    let fields_to_clear = [
        "vehicle_number","location","card_number","is_manual_weighment", "date", "transporter", "issue", "is_assigned","stock_transfer",
        "is_weighment_required","is_in_progress","custom_w_item_group", "weighment","custom_is_completed1","custom_is_in_progress1","custom_is_manual_weighment1",
        "is_completed","custom_vehicle_number1","vehicle_owner","supplier_name","entry_type","custom_tare_weight","custom_gross_weight","custom_net_weight"
    ];
    
    fields_to_clear.forEach(field => {
        frm.set_value(field, null);
    });
}
function load(frm) {
    if (frm.doc.docstatus === 0 && frm.is_new()) {
        let fields_to_clear = [
            "is_manual_weighment", "is_completed", "custom_is_completed1", "custom_is_in_progress1", "custom_is_manual_weighment1",
            "is_weighment_required", "is_in_progress", "updated","stock_transfer", "is_assigned"
        ];
        
        fields_to_clear.forEach(field => {
            frm.set_value(field, null);
        });
    }
}

function Reset_Weight(frm){
    frappe.call({
        method: "Reset_Weight",
        doc: frm.doc,
        args: {
            docname: frm.doc.name     
        },
        callback: function (response) {
            if (response.message) {
                frappe.show_alert({
                    message: __('Fields Updated Successfully, Kindly Check Details And Proceed For Weighment!'),
                    indicator: 'orange'
                },8);
                frm.set_value("updated",1);
                frm.refresh_field("updated");
                frm.save('Submit');
            }
        }
    });
}
function in_out_manual(frm){
    frappe.call({
        method: "inward_outward",
        doc: frm.doc,
        args: {
            docname: frm.doc.name     
        },
        callback: function (response) {
            if (response.message) {
                frappe.show_alert({
                    message: __('Fields Updated Successfully, Kindly Check Details And Proceed For Weighment!'),
                    indicator: 'orange'
                },8);
                frm.set_value("updated",1);
                frm.refresh_field("updated");
                frm.save('Submit');
            }
        }
    });
}

function item_group(frm){
    frappe.call({
        method: "item_group",
        doc: frm.doc,
        args: {
            docname: frm.doc.name     
        },
        callback: function (response) {
            if (response.message) {
                frappe.show_alert({
                    message: __('Item Group Updated Successfully, Kindly Add Delivery Note To Continue'),
                    indicator: 'blue'
                },7);
                frm.set_value("updated",1);
                frm.refresh_field("updated");
                frm.save('Submit');
            }
        }
    });
}

function change_dn(frm){
    frappe.call({
        method: "change_dn",
        doc: frm.doc,
        args: {
            docname: frm.doc.name     
        },
        callback: function (response) {
            if (response.message) {
                frappe.show_alert({
                    message: __('Fields Updated Successfully, Kindly Check Details And Create Sales Invoice!'),
                    indicator: 'blue'
                },5);
                frm.set_value("updated",1);
                frm.refresh_field("updated");
                frm.save('Submit');
                frappe.show_alert({
                    message: __('Kindly Check Old Delivery Note/Sales Invoice Status And Perform Required Actions If Any!'),
                    indicator: 'orange'
                },10);
                frm.set_value("updated",1);
                frm.refresh_field("updated");
                frm.save('Submit');
            }
        }
    });
}

function cancel(frm){
    frappe.call({
        method: "cancel_record",
        doc: frm.doc,
        args: {
            docname: frm.doc.name     
        },
        callback: function (response) {
            if (response.message) {
                frappe.show_alert({
                    message: __('Data Restored Successfully!'),
                    indicator: 'orange'
                });
                frm.set_value("updated",1);
                frm.refresh_field("updated");
                frm.save('Submit');
            }
        }
    });
}
function reset(frm){
    frappe.call({
        method: "second_weight",
        doc: frm.doc,
        args: {
            docname: frm.doc.name     
        },
        callback: function (response) {
            if (response.message) {
                frappe.show_alert({
                    message: __('Data Updated Successfully, Check Details And Proceed For Weighment! '),
                    indicator: 'orange'
                });
                frm.set_value("updated",1);
                frm.refresh_field("updated");
                frm.save('Submit');
            }
        }
    });
}
function manual(frm){
    frappe.call({
        method: "manual_issue",
        doc: frm.doc,
        args: {
            docname: frm.doc.name     
        },
        callback: function (response) {
            if (response.message) {
                frappe.show_alert({
                    message: __('Data Updated Successfully, Add/Check Delivery Note To Continue!'),
                    indicator: 'green'
                },5);
                frm.set_value("updated",1);
                frm.refresh_field("updated");
                frm.save('Submit');
            }
        }
    });
}
function update(frm) {
        frappe.call({
            method: "update_record",
            doc: frm.doc,
            args: {
                docname: frm.doc.name     
            },
            callback: function (response) {
                if (response.message) {
                    frappe.show_alert({
                        message: __('Data Updated Successfully!'),
                        indicator: 'green'
                    });
                    frm.set_value("updated",1);
                    frm.refresh_field("updated");
                    frm.save('Submit');
                }
            }
        });
    }
   
function debug(frm){
    frappe.call({
        method: "debug",
        doc: frm.doc,
        args: {
            docname: frm.doc.name     
        },
        callback: function (response) {
            if (response.message) {
                frappe.show_alert({
                    message: __('Check Terminal'),
                    
                });
            }
        }
    });
}
frappe.ui.form.on("Weighment Issue Management", {
    onload(frm){
        if (frm.is_new()) {
        load(frm);
       }
       frm.set_query("gate_entry", function(doc) {
                    return {
                        filters: {
                            docstatus:1
                        }
                    };
                });
    },
    // validate(frm){
    //     if(frm.doc.issue=="Reset Second Weight(Not Manual)" && frm.doc.custom_is_completed1==1){

    //     }
    // },
   refresh: function(frm) {
        // Show alert only if not already shown
        if (frm.doc.updated && !frm.doc.alert_shown) {
            const issue = frm.doc.issue;
            if (issue === "Vehicle Number Issue") {
                frappe.show_alert({ message: __("Data Updated Successfully!"), indicator: "green" }, 5);
            }
            else if (issue === "Reset Second Weight(Manual)") {
                frappe.show_alert({ message: __("Fields Updated Successfully, Kindly Check Details And Proceed For Weighment!"), indicator: "orange" }, 8);
            }
            else if (issue === "Unlink/Free Card Inward(Not Manual)") {
                frappe.show_alert({ message: __("Card Unlinked Successfully"), indicator: "orange" }, 8);
            }
            else if (issue === "Outward Manual Issue") {
                frappe.show_alert({ message: __("Data Updated Successfully, Add/Check Delivery Note To Continue!"), indicator: "green" }, 7);
            }
            else if (issue === "Reset Second Weight(Not Manual)") {
                frappe.show_alert({ message: __("Fields Updated Successfully, Kindly Check Details And Proceed For Weighment!"), indicator: "orange" }, 5);
            }
            else if (issue === "Unlink Old & Link New Delivery Note(Weighment Completed)") {
                frappe.show_alert({ message: __("Fields Updated Successfully, Kindly Check Details And Create Sales Invoice!"), indicator: "blue" }, 6);
            }
            else if (issue === "Inward/Outward Wrong Entry(Manual)") {
                frappe.show_alert({ message: __("Fields Updated Successfully, Kindly Check Details And Proceed For Weighment!"), indicator: "green" }, 6);
            }
            else if (issue === "Wrong Item Group Selected(Outward)") {
                frappe.show_alert({ message: __("Item Group Updated Successfully, Kindly Add Delivery Note To Continue"), indicator: "blue" }, 6);
            }
            frm.set_value("alert_shown", 1);
            frm.save('Submit');
        }
    },
    // on_submit: function(frm) { 
    //     if (!frm.doc.updated) {  // Triggers only when moving to Approved
            
    //         if (
    //             frm.doc.issue === "Vehicle Number Issue" 
    //         ) {
    //             update(frm);
    //             frm.refresh_field("updated");
    //             // frm.save('Submit');
    //         }

    //         if (
    //             frm.doc.issue === "Inward/Outward Wrong Entry(Manual)"
    //         ) {
    //             in_out_manual(frm);
    //             frm.refresh_field("updated");
    //             // frm.save('Submit'); 
    //         }
    //         if (
    //             frm.doc.issue === "Wrong Item Group Selected(Outward)" 
    //         ) {
    //             item_group(frm);
    //             frm.refresh_field("updated");
    //             // frm.save('Submit');
    //         }

    //         if (
    //             frm.doc.issue === "Unlink Old & Link New Delivery Note(Weighment Completed)"
    //         ) {
    //             change_dn(frm);
    //             frm.refresh_field("updated");
    //             // frm.save('Submit');
    //         }


    //         if (
    //             frm.doc.issue === "Reset Second Weight(Manual)"
    //         ) {
    //             reset(frm);
    //             frm.refresh_field("updated");
    //             // frm.save('Submit');
    //         }

    //         if (
    //             frm.doc.issue === "Outward Manual Issue" 
    //         ) {
    //             manual(frm);
    //             frm.refresh_field("updated");
    //             // frm.save('Submit');
    //         }
    //         if (
    //             frm.doc.issue === "Reset Second Weight(Not Manual)" ) {
    //             Reset_Weight(frm);
    //             frm.refresh_field("updated");
    //             // frm.save('Submit');
    //         }
    //     }},
        // if (frm.doc.docstatus === 1) {  // Ensure the document is submitted before overriding cancel
        //     frm.page.set_secondary_action('Cancel', function() {
        //         if (frm.doc.status === "Approved") {
        //             frappe.confirm(
        //                 'Are You Sure? The Old Values Will Be Restored!',
        //                 () => {
        //                     // Fetch the latest document before making any changes
        //                     frappe.call({
        //                         method: "frappe.client.get",
        //                         args: {
        //                             doctype: frm.doctype,
        //                             name: frm.doc.name
        //                         },
        //                         callback: function(response) {
        //                             let doc = response.message;

        //                             // Convert doc to a valid dictionary before applying workflow
        //                             frappe.call({
        //                                 method: "frappe.model.workflow.apply_workflow",
        //                                 args: {
        //                                     doc: JSON.parse(JSON.stringify(doc)),  // Ensure it's a plain dict
        //                                     action: "Cancel"  // Ensure this matches the exact Workflow Action name
        //                                 },
        //                                 callback: function(res) {
        //                                     if (!res.exc) {
        //                                         // Reload document first
        //                                         frm.reload_doc();

        //                                         // Wait for UI to refresh completely before calling cancel(frm)
        //                                         setTimeout(() => {
        //                                             cancel(frm);
        //                                             frm.refresh();                                                    
        //                                         }, 1000);  // Small delay to ensure all changes are applied
        //                                     } else {
        //                                         frappe.msgprint("Error while applying workflow action.");
        //                                     }
        //                                 }
        //                             });
        //                         }
        //                     });
        //                 },
        //                 () => {
        //                     frappe.msgprint("Cancellation aborted.");
        //                 }
        //             );
        //         }
        //     });
        // },
    issue(frm) {
        if (frm.doc.issue!="Vehicle Number Issue") {
            frm.set_value("update_field", "");
            frm.refresh_field("update_field");
        }
        if (frm.doc.issue === "Vehicle Number Issue") {
            frm.set_value("update_field", "vehicle_number");
            frm.refresh_field("vehicle_number");
        }
        if (frm.doc.issue === "Outward Manual Issue") {
            frm.set_value("update_field", "");
            frm.refresh_field("update_field");
        }
        if(frm.doc.issue=="Reset Second Weight(Not Manual)" || frm.doc.issue=="Unlink Old & Link New Delivery Note(Weighment Completed)"){
            frm.set_query("custom_delivery_note", function(doc) {
                return {
                    filters: {
                        // company: doc.company,
                        status: "Draft",
                        item_group: doc.custom_w_item_group,
                        custom_weighment: ""
                    }
                };
            });}
            if(frm.doc.issue=="Outward Manual Issue"){
                frm.set_query("custom_delivery_note", function(doc) {
                    return {
                        filters: {
                            // company: doc.company,
                            status: "Draft",
                            item_group: doc.item_group1,
                            custom_weighment: "",
                        }
                    };
                });
                frm.set_query("item_group1", function(doc) {
                    return {
                        filters: {
                            custom_is_weighment_required:"Yes"
                        }
                    };
                });
        }
        if(frm.doc.issue=="Wrong Item Group Selected(Outward)"){
            frm.set_query("item_group1", function(doc) {
                return {
                    filters: {
                        custom_allow_on_weighment:1
                    }
                };//
            });
        }
    },
    is_assigned(frm){
        frm.set_query("new_card", function(doc) {
            return {
                filters: {
                    is_assigned:0,
                    location:doc.location
                }
            };
        });
    },
    custom_items_group_(frm){
        frm.set_query("custom_delivery_note", function(doc) {
            return {
                filters: {
                    // company: doc.company,
                    status: "Draft",
                    item_group: doc.custom_items_group_,
                    custom_weighment: ""
                }
            };
        });
    },
    gate_entry_date(frm){
        if(!frm.gate_entry_date){
            frm.set_value("gate_entry",null);
            frm.set_value("company",null);
            frm.refresh_field("gate_entry");
            frm.refresh_field("company");
        }
    },
    company(frm) {
            frm.set_value("gate_entry",null);
            frm.refresh_field("gate_entry");
            clear_fields(frm);

        frm.set_query("gate_entry", function(doc) {
            return {
                filters: {
                    company: doc.company,
                    date: doc.gate_entry_date
                }
            };
        });
    },
    gate_entry(frm) {
        if (!frm.doc.gate_entry) {
            clear_fields(frm); 
            return;
        }

        frappe.call({
            method: "fetch_record",
            doc: frm.doc,
            args: {
                docname: frm.doc.name
            },
            callback: function(response) {
                if (response.message) {
                    frm.set_value("vehicle_number", response.message.vehicle_number);
                    frm.set_value("date", response.message.date);
                    frm.set_value("transporter", response.message.transporter_name);
                    frm.set_value("item_group_g", response.message.item_group);
                    frm.set_value("is_weighment_required", response.message.is_weighment_required);
                    frm.set_value("is_completed", response.message.is_completed);
                    frm.set_value("is_in_progress", response.message.is_in_progress);
                    frm.set_value("entry_type", response.message.entry_type);
                    frm.set_value("is_manual_weighment", response.message.is_manual_weighment);
                    frm.set_value("vehicle_owner", response.message.vehicle_owner);
                    frm.set_value("supplier_name", response.message.supplier_name);
                    frm.set_value("is_manual_weighment", response.message.is_manual_weighment);
                    frm.set_value("weighment", response.message.weighment);
                    frm.set_value("is_assigned", response.message.is_assigned);
                    frm.set_value("custom_w_item_group", response.message.custom_w_item_group);
                    frm.set_value("custom_tare_weight", response.message.custom_tare_weight);
                    frm.set_value("custom_gross_weight", response.message.custom_gross_weight);
                    frm.set_value("custom_net_weight", response.message.custom_net_weight);
                    frm.set_value("location", response.message.loc);
                    frm.set_value("card_number", response.message.cn);
                    frm.set_value("custom_is_completed1", response.message.custom_is_completed1);
                    frm.set_value("custom_is_in_progress1", response.message.custom_is_in_progress1);
                    frm.set_value("custom_is_manual_weighment1", response.message.custom_is_manual_weighment1);
                    frm.set_value("custom_vehicle_number1", response.message.custom_vehicle_number1);
                    frm.set_value("stock_transfer", response.message.stock_transfer);
                    
                    frappe.show_alert({
                        message: __('Data Fetched Successfully!')
                    });

                    frm.doc.save();
                }
            }
        });
    },
    entry_type: function(frm) {
        // All Issue List:
        // Vehicle Number Issue
        // Reset Second Weight(Manual)
        // Outward Manual Issue
        // Reset Second Weight(Not Manual)
        // Unlink Old & Link New Delivery Note(Weighment Completed)
        // Inward/Outward Wrong Entry(Manual)
        // Wrong Item Group Selected(Outward)
        // Working On-> Unlink/Free Card Inward(Not Manual)

        let options = [];
        if (frm.doc.entry_type === "Outward" && frm.doc.custom_is_manual_weighment1 ==1 && frm.doc.is_completed == 0) {
            options = ["Outward Manual Issue", "Vehicle Number Issue","Inward/Outward Wrong Entry(Manual)"];
        } 
        else if(frm.doc.entry_type === "Outward" && frm.doc.custom_is_manual_weighment1 ==1 && frm.doc.custom_is_completed1 == 1){
            options = ["Outward Manual Issue", "Vehicle Number Issue","Reset Second Weight(Manual)"];
        }
        else if(frm.doc.entry_type === "Outward" && frm.doc.custom_is_manual_weighment1 ==0 && frm.doc.is_completed == 0){
            options = ["Vehicle Number Issue","Wrong Item Group Selected(Outward)"];
        }
        else if(frm.doc.entry_type === "Outward" && frm.doc.custom_is_completed1 == 1 && frm.doc.custom_is_manual_weighment1==0){
            options = ["Vehicle Number Issue","Reset Second Weight(Not Manual)","Unlink Old & Link New Delivery Note(Weighment Completed)"];
        }
        else if(frm.doc.entry_type === "Inward" && frm.doc.custom_is_completed1==1 && frm.doc.custom_is_manual_weighment1==0) {
            options = ["Vehicle Number Issue","Reset Second Weight(Not Manual)"];
        }
        else if(frm.doc.entry_type === "Inward" && frm.doc.custom_is_completed1==1 && frm.doc.custom_is_manual_weighment1==1) {
            options = ["Vehicle Number Issue","Reset Second Weight(Manual)"];
        }
        else if(frm.doc.entry_type === "Inward" && frm.doc.custom_is_in_progress1==1 && frm.doc.custom_is_manual_weighment1 ==1) {
            options = ["Vehicle Number Issue","Inward/Outward Wrong Entry(Manual)"];
        }
        else if(frm.doc.entry_type == "Inward" && frm.doc.is_weighment_required=="Yes" && frm.doc.stock_transfer==0 && frm.doc.is_manual_weighment==0 && frm.doc.is_assigned==1 && frm.doc.custom_is_completed1 == 0) {
            options = ["Vehicle Number Issue","Unlink/Free Card Inward(Not Manual)"];
        }
        // else if(frm.doc.entry_type === "Inward" && frm.doc.custom_is_in_progress1==1) {
        //     options = ["Vehicle Number Issue"];
        // }
        else if(frm.doc.entry_type === "Outward" && frm.doc.custom_is_completed1==0) {
            options = ["Vehicle Number Issue"];
        }
        
        else{
            options = ["Vehicle Number Issue"];
        }
        frm.set_df_property('issue', 'options', options);
    }
});
