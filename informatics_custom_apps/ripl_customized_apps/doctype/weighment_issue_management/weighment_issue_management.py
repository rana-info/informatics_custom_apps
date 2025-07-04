# Copyright (c) 2025, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.workflow import apply_workflow
   
class WeighmentIssueManagement(Document):
    def validate(self):
        if self.issue == "Reset Second Weight(Not Manual)" and self.custom_is_completed1 == 1 and self.stock_transfer==0:
            if self.gate_entry and self.entry_type=="Inward":
                doc2 = frappe.get_doc("Gate Entry", {"name": self.gate_entry})
                doc3 = frappe.get_doc("Weighment", {"gate_entry_number": self.gate_entry})

                for i in doc2.purchase_orders:
                    po = frappe.get_doc("Purchase Order", {"name": i.purchase_orders})
                    print("---------111111------------------------>>>>>>>>>>po",po)
                for j in doc2.items:
                    ge_rec = j.received_quantity
                    print("---------111111------------------------>>>>>>>>>>ge_rec",ge_rec)
                for k in po.items:
                    ic = k.item_code.split(":")[0].strip()
                    qty = k.qty
                    print("---------111111------------------------>>>>>>>>>>qty",qty)

                item = frappe.get_doc("Item", {"name": ic})
                tl = (item.over_delivery_receipt_allowance/100)
                print("---------111111------------------------>>>>>>>>>>tl",tl)
                f_value = (qty+(qty * tl) - ge_rec)
                print("---------111111------------------------>>>>>>>>>>f_value",f_value)
                if self.bill_quantity == 0:
                    frappe.throw("Bill Quantity cannot be 0.")

                if self.bill_quantity > f_value:
                    frappe.throw(f"Bill Quantity cannot be more than the allowed value ({f_value}).")

    def before_submit(self):
        # Run only if current workflow state is "Approved"
        if self.workflow_state and self.workflow_state != "Approved":
            return

        if not self.updated:
            if self.issue == "Vehicle Number Issue":
                self.update_record()

            elif self.issue == "Inward/Outward Wrong Entry(Manual)":
                self.inward_outward()

            elif self.issue == "Wrong Item Group Selected(Outward)":
                self.item_group()

            elif self.issue == "Unlink Old & Link New Delivery Note(Weighment Completed)":
                self.change_dn()

            elif self.issue == "Reset Second Weight(Manual)":
                self.second_weight()

            elif self.issue == "Outward Manual Issue":
                self.manual_issue()

            elif self.issue == "Reset Second Weight(Not Manual)":
                self.Reset_Weight()

            self.updated = 1
        
    @frappe.whitelist()
    def fetch_record(self, docname):   
        doc1 = frappe.get_doc("Gate Entry", self.gate_entry)
        doc2 = None  
        if doc1.is_weighment_required == "Yes":
            doc2 = frappe.get_doc("Weighment", {"gate_entry_number": self.gate_entry})
            doc3 = frappe.get_doc("Card Details", {"name": doc1.card_number})

        if doc1.is_weighment_required == "No" and doc1.docstatus==1:
            return {
                "vehicle_number": doc1.vehicle_number,
                "date": doc1.date,
                "transporter_name": doc1.transporter_name,
                "item_group": doc1.item_group,
                "is_weighment_required": doc1.is_weighment_required,
                "is_completed": doc1.is_completed,
                "is_in_progress": doc1.is_in_progress, 
                "vehicle_owner": doc1.vehicle_owner,  
                "entry_type": doc1.entry_type,
                "is_manual_weighment": doc1.is_manual_weighment, 
                "loc":doc1.location
            }  
        
        if doc1.is_weighment_required == "Yes" and doc2.docstatus==1:
            return {
                "vehicle_number": doc1.vehicle_number,
                "date": doc1.date,
                "loc":doc2.location,
                "is_assigned":doc3.is_assigned,
                "vehicle_owner": doc1.vehicle_owner,
                "custom_w_item_group":doc2.item_group,  
                "custom_tare_weight": doc2.tare_weight,
                "custom_gross_weight": doc2.gross_weight,
                "custom_is_completed1": doc2.is_completed,
                "custom_is_in_progress1": doc2.is_in_progress,   
                "custom_vehicle_number1": doc2.vehicle_number,
                "custom_is_manual_weighment1": doc2.is_manual_weighment,
                "custom_net_weight": doc2.net_weight,
                "transporter_name": doc1.transporter_name,
                "item_group": doc1.item_group,
                "is_weighment_required": doc1.is_weighment_required,
                "is_completed": doc1.is_completed,
                "is_in_progress": doc1.is_in_progress,   
                "entry_type": doc1.entry_type,
                "is_manual_weighment": doc1.is_manual_weighment, 
                "weighment": doc2.name,   
                "stock_transfer":doc1.is_stock_transfer       
            }

    @frappe.whitelist()
    def inward_outward(self):
        doc2 = frappe.get_doc("Gate Entry", self.gate_entry)
        doc3 = frappe.get_doc("Weighment", {"gate_entry_number": self.gate_entry})
        print("----->xcv",self.as_dict())
        if doc2.entry_type == "Outward" and doc2.is_manual_weighment == 1 and doc3.is_in_progress==1:
            print("----->first",self.as_dict())
            doc2.db_set("entry_type","Inward")
            doc3.db_set("entry_type","Inward")
            doc3.db_set("tare_weight",0)
            doc3.db_set("gross_weight",self.custom_tare_weight)
            # self.db_set("updated",True)
            # frappe.db.sql("""
            # UPDATE `tabWeighment Issue Management`
            # SET updated = 1
            # WHERE name = %s
            # """, (self.name,))
            # frappe.db.commit()
            # print("----->second",self.as_dict())
            self.db_set("updated",True)
            #frappe.msgprint("Data Updated Successfully!")
            return True


        if doc2.entry_type == "Inward" and doc2.is_manual_weighment == 1 and doc3.is_in_progress==1:
            doc2.db_set("entry_type","Outward")
            doc3.db_set("entry_type","Outward")
            doc3.db_set("gross_weight",0)
            doc3.db_set("tare_weight",self.custom_gross_weight) 
            # self.db_set("updated",True) 
            # frappe.db.sql("""
            # UPDATE `tabWeighment Issue Management`
            # SET updated = 1
            # WHERE name = %s
            # """, (self.name,))
            # frappe.db.commit()
            self.db_set("updated",True)
            #frappe.msgprint("Data Updated Successfully!")
            return True


    @frappe.whitelist()
    def change_dn(self):
        doc2 = frappe.get_doc("Gate Entry", self.gate_entry)
        doc3 = frappe.get_doc("Weighment", {"gate_entry_number": self.gate_entry})
        doc_si = None
        try:
            si = frappe.db.get_value(
                "Sales Invoice Item", 
                {"custom_weighment": doc3.name,"docstatus":1},
                "parent"
            )

            if si:
                if len(si)==1:    
                    # Check if the parent Sales Invoice has docstatus = 1 (Submitted)
                    docstatus = frappe.db.get_value("Sales Invoice", si, "docstatus")
                    if docstatus != 2 and not is_return:
                        print("------------------------>si", si)
                        doc_si = frappe.get_doc("Sales Invoice", si)
                        print("----------------!!!!!!!!----------->Invoice", doc_si)
                
        except Exception as e:
            print(f"Error fetching Sales Invoice from Weighment: {e}")

        if doc_si is not None:
            frappe.throw("Kindly remove/manage existing Sales Invoice Before Requesting To Update!")

        # Only proceed if conditions match
        if doc2.entry_type == "Outward" and doc2.is_manual_weighment == 0 and doc3.is_completed == 1:

            doc5 = frappe.get_all(
                "Delivery Note",
                filters={"custom_weighment": doc3.name, "docstatus": ["!=", 2]},
                fields=["name"]
            )
            print("----------->Existing D.N", doc5)

            doc3.delivery_notes = []
            doc3.delivery_note_details = []

            doc_d = frappe.get_doc("Delivery Note", {"name": self.custom_delivery_note})
            doc_d.db_set("custom_weighment", doc3.name)  # Link D.N
            doc_d.db_set("vehicle_no", doc3.vehicle_number)
            doc_d.save(ignore_permissions=True)

            print("########################--------------New D.N--->", self.custom_delivery_note)

            data = frappe.get_all(
                "Delivery Note Item",
                {"parent": self.custom_delivery_note},
                ["parent", "item_code", "item_name", "qty", "uom", "custom_total_package_weight", "total_weight"]
            )

            if data:
                new_row = doc3.append("delivery_notes", {})
                new_row.delivery_note = self.custom_delivery_note

                for item in data:
                    doc3.append("delivery_note_details", {
                        "delivery_note": item.get("parent"),
                        "item": item.get("item_code"),
                        "item_name": item.get("item_name"),
                        "qty": item.get("qty"),
                        "uom": item.get("uom"),
                        "total_weight": (item.get("custom_total_package_weight") or 0) + (item.get("total_weight") or 0)
                    })

            for doc6 in doc5:
                delivery_note = frappe.get_doc("Delivery Note", doc6["name"])
                delivery_note.db_set("custom_weighment", "")  # Unlink D.N
                delivery_note.db_set("vehicle_no", "")
                delivery_note.save(ignore_permissions=True)

            doc3.save(ignore_permissions=True)

        self.db_set("updated", True)
        #frappe.msgprint("Data Updated Successfully!")
        return True

    
    @frappe.whitelist()
    def debug(self):
        print("!!!!!!!!!!!!!!!!!!!!!!!!11", self.workflow_state)
        print("!!!!!!!!!!!!!!!!!!!!!!!!11", self.docstatus)
        self.db_set("updated",True)
        return True
    @frappe.whitelist()
    def Reset_Weight(self):
        try:
            doc2 = frappe.get_doc("Gate Entry", self.gate_entry)
            doc3 = frappe.get_doc("Weighment", {"gate_entry_number": self.gate_entry})
            doc4 = frappe.get_doc("Card Details", {"name": doc2.card_number})

            if doc2.entry_type == "Inward" and doc2.is_completed == 1 and doc2.is_stock_transfer==0:
                doc3.db_set("tare_weight", 0)
                doc3.db_set("net_weight", 0)
                doc2.db_set("is_in_progress", 1)
                doc2.db_set("is_completed", 0)
                doc3.db_set("is_in_progress", 1)
                doc3.db_set("is_completed", 0)
                doc_pr=None
                doc_pi=None
                try:
                    prg=None
                    prg = frappe.get_value("Purchase Receipt Item", {"custom_gate_entry": doc2.name}, 'parent')
                    print("------------------------>prg", prg)
                    if prg!=None:
                        doc_pr = frappe.get_doc("Purchase Receipt", prg)
                    pi = None
                    pi = frappe.get_value("Purchase Invoice Item", {"purchase_receipt": doc_pr.name}, 'parent')
                    if pi!= None:
                        doc_pi = frappe.get_doc("Purchase Invoice", pi)
                                    
                except Exception as e:
                    print(f"Error fetching Purchase Receipt from Gate Entry: {e}")
                if doc_pr!=None or doc_pi!=None:
                    # wim= frappe.get_doc("Weighment Issue Management",{"name":self.name})
                    # wim.db_set("workflow_state","Cancelled")
                    # print("----------------->wim",wim)
                    # self.db_set("error_message","Error Occured While Processing, Kindly Check Error Log")
                    frappe.throw("Kindly remove existing Purchase Receipt/Purchase Invoice Before Requesting To Update!")
                    
                #Fetch PO from child table
                for i in doc3.purchase_orders:
                    po = frappe.get_doc("Purchase Order",{"name":i.purchase_orders})
                    print("------The--PO--Is ----____--->",po)
                #To fetch received qty
                
                for j in doc2.items:
                    ge_rec=j.received_quantity
                    print("------The--GE--Recceived---qty--Is----____--->",ge_rec)
                
                for k in po.items:
                    ic=k.item_code.split(":")[0].strip()
                    qty=k.qty
                    ge_rec_draft = k.gate_entry_received_qty
                    a=ge_rec-self.bill_quantity
                    print("------Old__-__New---bill-quantity----____--->",a)
                    if a<0:
                        new_ge_draft = ge_rec_draft + a
                        print("!!!!!!!!!!!!!!!IF--is--called--!!!!!!!!!!!!")
                    else:
                        new_ge_draft = ge_rec_draft - a
                        print("!!!!!!!!!!!!!!!Else--is--called--!!!!!!!!!!!!")
                    gerp = new_ge_draft/qty*100
                    print("------The--Item--Code--Is----____--->",ic)
                    print("------The--Item--Quantity--Is----____--->",qty)
                    print("------The--Existing--Ge_Rec_Quantity----____--->",ge_rec_draft)
                    print("------The--New--Ge_Rec_Quantity----____--->",new_ge_draft)
                    print("------The--New--Ge_Rec_percentage----____--->",gerp)
                    k.db_set("gate_entry_received_qty",new_ge_draft)
                po.db_set("gate_entry_received_percentage",gerp)
                #To fetch Item And It's Tolerance
                item = frappe.get_doc("Item",{"name":ic})
                tl=(item.over_delivery_receipt_allowance/100)
                print("------The--Item---Is----____--->",item)
                print("------The--Item--tolerance--Is----____--->",tl)

                #Add Formula for bill_quantity validation
                f_value = (qty+(qty * tl) - ge_rec)
                print("------The--Formula--Value--Is----____--->",f_value)
                # Fetch document names first
                doc7_name = frappe.get_value("Purchase Details", {"parent": doc2.name}, "name")
                doc8_name = frappe.get_value("Purchase Details", {"parent": doc3.name}, "name")

                # Fetch full document objects and update fields if they exist
                if doc7_name:
                    doc7 = frappe.get_doc("Purchase Details", doc7_name)
                    doc7.db_set("received_quantity", self.bill_quantity)
                    doc7.db_set("accepted_quantity", self.bill_quantity)


                if doc8_name:
                    doc8 = frappe.get_doc("Purchase Details", doc8_name)
                    doc8.db_set("received_quantity", self.bill_quantity)
                    doc8.db_set("accepted_quantity", self.bill_quantity)
                if self.new_card:
                    doc2.db_set("card_number",self.new_card)
                    doc5 = frappe.get_doc("Card Details", {"name": self.new_card})
                    doc5.db_set("is_assigned", True)
                if not self.new_card and doc4.is_assigned==0:
                    doc4.db_set("is_assigned", True)
                elif doc4.is_assigned==1 and self.is_completed==1:
                    frappe.msgprint("Card Might Be In Use By Other Vehicle, Kindly Check And Assign New Card And Proceed For Weighment!")
                    # To check if card is assigned to someone else, then assign a new card
                self.db_set("updated",True)
                #frappe.msgprint("Data Updated Successfully!")
                return True

            # if doc2.entry_type == "Inward" and doc2.is_completed == 1 and doc2.is_stock_transfer==1:
            #     doc3.db_set("tare_weight", 0)
            #     doc3.db_set("net_weight", 0)
            #     doc2.db_set("is_in_progress", 1)
            #     doc2.db_set("is_completed", 0)
            #     doc3.db_set("is_in_progress", 1)
            #     doc3.db_set("is_completed", 0)
            #     if self.new_card:
            #         doc2.db_set("card_number",self.new_card)
            #         doc5 = frappe.get_doc("Card Details", {"name": self.new_card})
            #         doc5.db_set("is_assigned", True)
            #     if not self.new_card and doc4.is_assigned==0:
            #         doc4.db_set("is_assigned", True)
            #     doc_se=None
            #     try:
            #         se = frappe.get_value("Stock Entry Detail", {"custom_gate_entry": doc2.name}, 'parent')
            #         print("------------------------>se", se)
            #         doc_se = frappe.get_doc("Stock Entry", se)                                  
            #     except Exception as e:
            #         print(f"Error fetching Stock Entry from Gate Entry: {e}")
            #     if doc_se!=None:
            #         frappe.throw("Kindly remove existing Stock Entry Before Requesting To Update!")
            #     return True
            if doc2.entry_type == "Inward" and doc2.is_completed == 1 and doc2.is_stock_transfer==1:
                doc3.db_set("tare_weight", 0)
                doc3.db_set("net_weight", 0)
                doc2.db_set("is_in_progress", 1)
                doc2.db_set("is_completed", 0)
                doc3.db_set("is_in_progress", 1)
                doc3.db_set("is_completed", 0)
                if self.new_card:
                    doc2.db_set("card_number",self.new_card)
                    doc5 = frappe.get_doc("Card Details", {"name": self.new_card})
                    doc5.db_set("is_assigned", True)
                if not self.new_card and doc4.is_assigned==0:
                    doc4.db_set("is_assigned", True)
                doc_se = None
                try:
                    se = frappe.db.get_value(
                        "Stock Entry Detail", 
                        {"custom_gate_entry": doc2.name},
                        "parent"
                    )

                    if se:
                        # Check if the parent Stock Entry has docstatus = 1 (Submitted)
                        docstatus = frappe.db.get_value("Stock Entry", se, "docstatus")
                        if docstatus != 2:
                            print("------------------------>se", se)
                            doc_se = frappe.get_doc("Stock Entry", se)
                except Exception as e:
                    print(f"Error fetching Stock Entry from Gate Entry: {e}")

                if doc_se is not None:
                    frappe.throw("Kindly remove existing Stock Entry Before Requesting To Update!")
                else:
                    self.db_set("updated",True)
                    #frappe.msgprint("Data Updated Successfully!")
                    return True

            if doc2.entry_type == "Outward" and doc3.is_completed ==1 and doc2.is_manual_weighment==0: # may need to build different logic for sugar,others are fine
                print(">>> delivery_notes list:", doc3.delivery_notes)
                doc_si = None
                try:
                    si = frappe.db.get_value(
                        "Sales Invoice Item", 
                        {"custom_weighment": doc3.name},
                        "parent"
                    )
                    if si:
                        # Check if the parent Stock Entry has docstatus = 1 (Submitted)
                        docstatus = frappe.db.get_value("Sales Invoice", si, "docstatus")
                        if docstatus != 2:
                            print("------------------------>si", si)
                            doc_si = frappe.get_doc("Sales Invoice", si)
                except Exception as e:
                    print(f"Error fetching Sales Invoice from Weighment: {e}")
                if doc_si is not None:
                    frappe.throw("Kindly remove/manage existing Sales Invoice Before Requesting To Update!")
                for i in doc3.delivery_notes:
                    print("!!!!!!!------------1!!!!!---->Entered For Loop")
                    if i.delivery_note:
                        doc9 = frappe.get_doc("Delivery Note", i.delivery_note)
                        print("------------------------>DN",doc9)
                        doc9.db_set("custom_weighment", "")
                        doc9.db_set("vehicle_no", "")
                        # doc9.cancel(ignore_permissions=True)
                doc3.delivery_notes = []
                doc3.delivery_note_details = []
                    
                doc3.db_set("gross_weight",0)
                doc3.db_set("net_weight",0)
                doc2.db_set("is_in_progress",1)
                doc2.db_set("is_completed",0)
                doc3.db_set("is_in_progress",1)
                doc3.db_set("is_completed",0)
                doc2.save(ignore_permissions=True)
                doc3.save(ignore_permissions=True)
                

                if self.new_card:
                    doc2.db_set("card_number",self.new_card)
                    doc5 = frappe.get_doc("Card Details", {"name": self.new_card})
                    doc5.db_set("is_assigned", True)
                if not self.new_card and doc4.is_assigned==0:
                    doc4.db_set("is_assigned", True)
                # else:
                #      frappe.msgprint("Card Might Be In Use By Other Vehicle, Kindly Check And Assign New Card And Proceed For Weighment!")#To check if card is assigned to someone else,then assign new card
                self.db_set("updated",True)
                #frappe.msgprint("Data Updated Successfully!")
                return True
            # else:
            #     frappe.msgprint("Item Group is Different!")
        except Exception as e:
            print("---------------------->Entered Except Block-----------")

            error_text = frappe.get_traceback()
            frappe.log_error(error_text, "Error During Processing Wrong Card Issue")

            try:
                print("---------------------->Entered Inner Try Block-----------")
                wim_doc = frappe.get_doc("Weighment Issue Management", self.name)

                # Save to field and add comment
                # wim_doc.db_set("error_message", error_text)
                # wim_doc.add_comment("Comment", f"Automatic Error Logged:\n\n{error_text}")
                # wim_doc.save(ignore_permissions=True)
                # wim_doc.reload()
                # print("--------------------Successfully added error to field and comment----------------------")
            except Exception as wf_error:
                # Print + log full traceback from this specific block
                frappe.log_error(frappe.get_traceback(), "Failed to log error on Weighment Issue Management document")
                print("!!!!!!!!!!!!!Inner try block failed:!!!!!!!!!!!!!!!!!!")
                print(frappe.get_traceback())
                print("_______-----------___________--------->Actual Exception Object:", wf_error)

            frappe.throw("An Error Occured While Processing, Kindly Check Error Log!")



    @frappe.whitelist()
    def update_record(self):
        doc2 = frappe.get_doc("Gate Entry", self.gate_entry)
        if(doc2.vehicle_owner !="Company Owned"):
            doc2.db_set(self.update_field,self.value_to_update)
        if(doc2.vehicle_owner =="Company Owned"):
            doc2.db_set(self.update_field,self.vehicle)
            doc2.db_set("vehicle",self.vehicle)
        doc2.save(ignore_permissions=True)  # Save the document

        if doc2.is_weighment_required == "Yes":
            doc3 = frappe.get_doc("Weighment", {"gate_entry_number": self.gate_entry})
            if(doc2.vehicle_owner !="Company Owned"):
                doc3.db_set(self.update_field,self.value_to_update)
            if(doc2.vehicle_owner =="Company Owned"):
                doc3.db_set(self.update_field,self.vehicle)
                doc3.db_set("vehicle",self.vehicle)
            doc3.save(ignore_permissions=True)

        if (
            doc2.is_weighment_required == "Yes" 
            and doc2.is_completed 
            and not doc2.is_manual_weighment 
            and doc2.entry_type == "Outward"
        ):
            doc4 = frappe.get_doc("Delivery Note", {"custom_weighment": doc3.name})
            si = frappe.get_value("Sales Invoice Item", {"delivery_note": doc4.name}, 'parent')
            print("---------------->doc4",doc4)
            print("---------------->si",si)
            doc5=None
            if si:
                doc5 = frappe.get_doc("Sales Invoice", {"name":si})
            if(doc2.vehicle_owner !="Company Owned" and doc5 is not None):
                doc5.db_set("vehicle_no", self.value_to_update)
                doc4.db_set("vehicle_no", self.value_to_update)
                doc5.save(ignore_permissions=True)
            elif(doc2.vehicle_owner !="Company Owned" and doc5 is None):
                doc4.db_set("vehicle_no", self.vehicle)
            doc4.save(ignore_permissions=True)
            

        if (
            doc2.is_weighment_required == "No"  
            and not doc2.is_manual_weighment 
            and doc2.entry_type == "Inward"
        ):
            try:
                prg = frappe.get_value("Purchase Receipt Item", {"custom_gate_entry": doc2.name}, 'parent')
                print("------------------------>prg", prg)
                doc4 = frappe.get_doc("Purchase Receipt", prg)
                # doc4.db_set("vehicle_no", self.value_to_update)
                pi = frappe.get_value("Purchase Invoice Item", {"purchase_receipt": doc4.name}, 'parent')
                doc5 = frappe.get_doc("Purchase Invoice", pi)
                # doc5.db_set("vehicle_no", self.value_to_update)
                qc = frappe.get_all("Quality Inspection",filters={"reference_name":prg},fields=["name"])
                print("------------------------>qc", qc)
                if(doc2.vehicle_owner !="Company Owned"):
                    doc4.db_set("vehicle_no", self.value_to_update)
                    doc5.db_set("vehicle_no", self.value_to_update)
                else:
                    doc4.db_set("vehicle_no", self.vehicle)
                    doc5.db_set("vehicle_no", self.vehicle)
                for q in qc:
                    a = frappe.get_doc("Quality Inspection",q.name)
                    if(doc2.vehicle_owner !="Company Owned"):
                        a.db_set("custom_vehicle_no",self.value_to_update)
                    else:
                        a.db_set("custom_vehicle_no",self.vehicle)
            except Exception as e:
                print(f"Error fetching Purchase Receipt from Gate Entry: {e}")
            
        if (
            doc2.is_weighment_required == "Yes" 
            and doc2.is_completed 
            and not doc2.is_manual_weighment 
            and doc2.entry_type == "Inward"
        ):
            doc3 = frappe.get_doc("Weighment", {"gate_entry_number": self.gate_entry})
            try:
                prg = frappe.get_value("Purchase Receipt Item", {"custom_gate_entry": doc2.name}, 'parent')
                print("------------------------>prg", prg)
            except Exception as e:
                print(f"Error fetching Purchase Receipt from Gate Entry: {e}")
                prg = None

            if not prg:
                try:
                    pr = frappe.get_value("Purchase Receipt Item", {"custom_weighment": doc3.name}, 'parent')
                    print("------------------------>", pr)
                except Exception as e:
                    print(f"Error fetching Purchase Receipt from Weighment: {e}")
                    pr = None

            if prg:
                try:
                    doc4 = frappe.get_doc("Purchase Receipt", prg)
                    if(doc2.vehicle_owner !="Company Owned"):
                        doc4.db_set("vehicle_no", self.value_to_update)
                    else:
                        doc4.db_set("vehicle_no", self.vehicle)
                    qc = frappe.get_all("Quality Inspection",filters={"reference_name":prg},fields=["name"])
                    print("------------------------>qc", qc)#
                    if qc:
                        for q in qc:
                            a = frappe.get_doc("Quality Inspection",q.name)
                            if(doc2.vehicle_owner !="Company Owned"):
                                a.db_set("custom_vehicle_no",self.value_to_update)
                            else:
                                a.db_set("custom_vehicle_no",self.vehicle)
                    try:
                        pi = frappe.get_value("Purchase Invoice Item", {"purchase_receipt": doc4.name}, 'parent')
                        if pi:
                            doc5 = frappe.get_doc("Purchase Invoice", pi)
                        if(doc2.vehicle_owner !="Company Owned"):
                            doc5.db_set("vehicle_no", self.value_to_update)
                        else:
                            doc5.db_set("vehicle_no", self.vehicle)
                    except Exception as e:
                        print(f"Error updating Invoice (pi):{e}")
                except Exception as e:
                    print(f"Error updating Purchase Receipt/Invoice (prg): {e}")
            elif not prg and pr:
                try:
                    doc4 = frappe.get_doc("Purchase Receipt", pr)
                    if(doc2.vehicle_owner !="Company Owned"):
                        doc4.db_set("vehicle_no", self.value_to_update)
                    else:
                        doc4.db_set("vehicle_no", self.vehicle)
                    qc = frappe.get_all("Quality Inspection",filters={"reference_name":pr},fields=["name"])
                    print("------------------------>qc", qc)
                    for q in qc:
                        a = frappe.get_doc("Quality Inspection",q.name)
                        if(doc2.vehicle_owner !="Company Owned"):
                            a.db_set("custom_vehicle_no",self.value_to_update)
                        else:
                            a.db_set("custom_vehicle_no",self.vehicle)
                    try:
                        pi = frappe.get_value("items", {"purchase_receipt": doc4.name}, 'parent')
                        doc5 = frappe.get_doc("Purchase Invoice", pi)
                        if(doc2.vehicle_owner !="Company Owned"):
                            doc5.db_set("vehicle_no", self.value_to_update)
                        else:
                            doc5.db_set("vehicle_no", self.vehicle)
                    except Exception as e:
                        print(f"Error updating invoice(pi):{e}")
                except Exception as e:
                    print(f"Error updating Purchase Receipt/Invoice (pr): {e}")

            else:
                pass
        frappe.db.commit()  # Commit once after all updates
        self.db_set("updated",True) 
        # frappe.msgprint("Vehicle number updated successfully.")
        return True

    @frappe.whitelist()
    def cancel_record(self):
        doc2 = frappe.get_doc("Gate Entry", self.gate_entry)
        doc2.db_set(self.update_field, self.vehicle_number)
        doc2.save(ignore_permissions=True)
        
        if doc2.is_weighment_required == "Yes":
            doc3 = frappe.get_doc("Weighment", {"gate_entry_number": self.gate_entry})
            doc3.db_set(self.update_field, self.vehicle_number)
            doc3.save(ignore_permissions=True)
        
        frappe.db.commit()
        self.db_set("updated",True)
        #frappe.msgprint("Data Updated Successfully!")
        return True

    @frappe.whitelist()
    def manual_issue(self):
        doc2 = frappe.get_doc("Gate Entry", self.gate_entry)
        if doc2.is_weighment_required == "Yes" and doc2.entry_type == "Outward" and doc2.is_manual_weighment ==1 and doc2.is_completed ==0:
            doc3 = frappe.get_doc("Weighment", {"gate_entry_number": self.gate_entry})
            doc4 = frappe.get_doc("Card Details", {"name": doc2.card_number})
            doc2.db_set("is_manual_weighment",False)
            # doc3.db_set("gross_weight",0)
            # doc3.db_set("net_weight",0)
            doc2.db_set("item_group",self.item_group1)
            doc3.db_set("item_group",self.item_group1)
            doc3.db_set("is_manual_weighment",False)
            if self.new_card:
                doc2.db_set("card_number",self.new_card)
                doc5 = frappe.get_doc("Card Details", {"name": self.new_card})
                doc5.db_set("is_assigned", True)
            if not self.new_card and doc4.is_assigned==0:
                 doc4.db_set("is_assigned", True)
            self.db_set("updated",True)
            #frappe.msgprint("Data Updated Successfully!")
            return True
        if doc2.is_weighment_required == "Yes" and doc2.entry_type == "Outward" and doc2.is_manual_weighment ==1 and doc2.is_completed==1:
            doc3 = frappe.get_doc("Weighment", {"gate_entry_number": self.gate_entry})
            doc4 = frappe.get_doc("Card Details", {"name": doc2.card_number})

            doc2.db_set("is_manual_weighment",False)
            doc3.db_set("is_manual_weighment",False)
            doc2.db_set("item_group",self.item_group1)
            doc3.db_set("item_group",self.item_group1)
            doc3.db_set("gross_weight",0)
            doc3.db_set("net_weight",0)
            doc2.db_set("is_in_progress",True)
            doc2.db_set("is_completed",False) 
            doc3.db_set("is_in_progress",True)
            doc3.db_set("is_completed",False)
            if self.new_card:
                doc2.db_set("card_number",self.new_card)
                doc5 = frappe.get_doc("Card Details", {"name": self.new_card})
                doc5.db_set("is_assigned", True)
            if not self.new_card and doc4.is_assigned==0:
                 doc4.db_set("is_assigned", True)
            # doc5 = frappe.get_all("Delivery Note", filters={"custom_weighment": doc3.name}, fields=["name"])
            # print("----------->Existing D.N", doc5)
            # doc3.delivery_notes = []
            # doc3.delivery_note_details =[]

            
        if self.custom_delivery_note:
            doc_d=frappe.get_doc("Delivery Note", {"name": self.custom_delivery_note})
            doc_d.db_set("custom_weighment",doc3.name)#To Link D.N
            doc_d.db_set("vehicle_no",doc3.vehicle_number)
            doc_d.save(ignore_permissions=True)
            print("########################--------------New D.N--->",self.custom_delivery_note)
            data = frappe.get_all(
            "Delivery Note Item",
            {"parent": self.custom_delivery_note},
            ["parent","item_code","item_name","qty","uom","custom_total_package_weight","total_weight"]
            )
            if data:
                new_row = doc3.append("delivery_notes", {})
                new_row.delivery_note = self.custom_delivery_note 
                for item in data:
                    doc3.append("delivery_note_details",
                        {
                            "delivery_note": item.get("parent"),
                            "item": item.get("item_code"),
                            "item_name": item.get("item_name"),
                            "qty": item.get("qty"),
                            "uom": item.get("uom"),
                            "total_weight": (item.get("custom_total_package_weight") or 0) + (item.get("total_weight") or 0)
                        }
                    )
            # else:
            #     pass


            # for doc6 in doc5:   
            #     delivery_note = frappe.get_doc("Delivery Note", doc6["name"])
            #     delivery_note.db_set("custom_weighment", "")#To Unlink D.N
            #     delivery_note.db_set("vehicle_no", "")
            #     delivery_note.save(ignore_permissions=True)
            #     doc3.save(ignore_permissions=True)
            # if self.new_card:
            #     doc2.db_set("card_number",self.new_card)
            #     doc5 = frappe.get_doc("Card Details", {"name": self.new_card})
            #     doc5.db_set("is_assigned", True)
            # if not self.new_card and doc4.is_assigned==0:
            #      doc4.db_set("is_assigned", True)
        doc2.save(ignore_permissions=True)
        doc3.save(ignore_permissions=True)
        self.db_set("updated",True)
        #frappe.msgprint("Data Updated Successfully!") 
        return True   
        # try:
        #     if self.custom_delivery_note:  
        #         # new_row = doc3.append("delivery_notes", {})
        #         # print("########################----------------->DN",self.custom_delivery_note)
        #         # new_row.delivery_note = self.custom_delivery_note  # Assign the value
        #         data = frappe.get_all(
        #         "Delivery Note Item",
        #         {"parent": self.custom_delivery_note},
        #         ["parent","item_code","item_name","qty","uom","custom_total_package_weight","total_weight"]
        #     )
        #     if data:
        #         new_row = doc3.append("delivery_notes", {})
        #         new_row.delivery_note = self.custom_delivery_note 
        #         for item in data:
        #             doc3.append("delivery_note_details",
        #                 {
        #                     "delivery_note": item.get("parent"),
        #                     "item": item.get("item_code"),
        #                     "item_name": item.get("item_name"),
        #                     "qty": item.get("qty"),
        #                     "uom": item.get("uom"),
        #                     "total_weight": (item.get("custom_total_package_weight") or 0) + (item.get("total_weight") or 0)
        #                 }
        #             )
            
        #     doc3.db_set("is_in_progress",True)
        #     doc3.db_set("is_completed",False) 
        #     doc3.save(ignore_permissions=True)
        #     doc2.save(ignore_permissions=True)
        #     return True
        # except Exception as e:
        #         print(f"Error: {e}")
        
        # return True
    @frappe.whitelist()
    def second_weight(self):
        doc2 = frappe.get_doc("Gate Entry", self.gate_entry)
        if doc2.is_weighment_required == "Yes" and doc2.entry_type in ["Outward", "Inward"] and doc2.is_completed and doc2.is_manual_weighment==1:
            doc3 = frappe.get_doc("Weighment", {"gate_entry_number": self.gate_entry})
            doc4 = frappe.get_doc("Card Details", {"name": doc2.card_number})
            doc3.db_set("is_completed", False)
            doc3.db_set("is_in_progress", True)
            doc2.db_set("is_completed", False)
            doc2.db_set("is_in_progress", True)
            if doc2.entry_type == "Inward":
                doc3.db_set("tare_weight",0)
                doc3.db_set("net_weight",0)
            else:
                doc3.db_set("gross_weight",0)
                doc3.db_set("net_weight",0)  
            if self.new_card:
                doc2.db_set("card_number",self.new_card)
                doc5 = frappe.get_doc("Card Details", {"name": self.new_card})
                doc5.db_set("is_assigned", True)
            if not self.new_card and doc4.is_assigned==0:
                 doc4.db_set("is_assigned", True)
            self.db_set("updated",True) 
            #frappe.msgprint("Data Updated Successfully!")
            return True
    @frappe.whitelist()
    def item_group(self):
        doc2 = frappe.get_doc("Gate Entry", self.gate_entry)
        if(doc2.is_completed==0):
            try:
                doc3 = frappe.get_doc("Weighment", {"gate_entry_number": self.gate_entry}) 
                doc3.db_set("item_group",self.item_group1)
                doc3.delivery_notes = []
                doc3.delivery_note_details =[]
                doc2.db_set("item_group",self.item_group1)
                doc2.save(ignore_permissions=True)
                doc3.save(ignore_permissions=True)
                self.db_set("updated",True) 
                #frappe.msgprint("Data Updated Successfully!")
                return True
            except Exception as e:
                print(f"Error Changing Item Group:{e}")
        else:
            pass
