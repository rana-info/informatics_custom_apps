// Copyright (c) 2025, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.ui.form.on('Accounting Management', {

    plant_update: function(frm) {
        if (!frm.doc.plant_update) {
            frm.set_value('plant', '');
        }
    },

    cost_center_update: function(frm) {
        if (!frm.doc.cost_center_update) {
            frm.set_value('wrong_cost_center', '');
            frm.set_value('cost_center', '');
        }
    },

    segment_update: function(frm) {
        if (!frm.doc.segment_update) {
            frm.set_value('wrong_segment', '');
            frm.set_value('segment', '');
        }
    },

    section_update: function(frm) {
        if (!frm.doc.section_update) {
            frm.set_value('wrong_section', '');
            frm.set_value('section', '');
        }
    },

    expense_account_update: function(frm) {
        if (!frm.doc.expense_account_update) {
            frm.set_value('wrong_expense_account', '');
            frm.set_value('expense_account', '');
        }
    },

    income_account_update: function(frm) {
        if (!frm.doc.income_account_update) {
            frm.set_value('wrong_income_account', '');
            frm.set_value('correct_income_account', '');
        }
    },

    payable_account_update: function(frm) {
        if (!frm.doc.payable_account_update) {
            frm.set_value('wrong_payable_account', '');
            frm.set_value('correct_payable_account', '');
        }
    },

    only_gl_update: function(frm) {
        if (!frm.doc.only_gl_update) {
            frm.set_value('wrong_gl', '');
            frm.set_value('correct_gl', '');
        }
    }

});