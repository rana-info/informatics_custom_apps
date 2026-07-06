// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

frappe.ui.form.on("IOC Logs", {
  onload(frm) {
    frm.set_query("task_owner", function () {
        return {
            filters: {
                branch: frm.doc.plant
            }
        };
    });
  },
  refresh(frm) {

    // Assign owners to a selected sub-task row
    if (frm.fields_dict.sub_task) {
      frm.fields_dict.sub_task.grid.add_custom_button(__('Assign Owner(s)'), () => {
        const selected = frm.fields_dict.sub_task.grid.get_selected();

        if (selected.length !== 1) {
          frappe.msgprint(__('Please select exactly one Sub Task row (checkbox) to assign owners to.'));
          return;
        }

        const row_name = selected[0];
        const row = frappe.get_doc('zz Project RSLD Sub-Task Detail', row_name);
        const existing_emails = row.sub_task_owner_emails
          ? row.sub_task_owner_emails.split(',').map(e => e.trim()).filter(Boolean)
          : [];

        const dialog = new frappe.ui.Dialog({
          title: __('Assign Sub-Task Owner(s)'),
          fields: [
            {
              fieldname: 'users',
              fieldtype: 'MultiSelectPills',
              label: __('Users'),
              reqd: 1,
              get_data: function (txt) {
                return frappe.db.get_link_options('User', txt);
              }
            }
          ],
          primary_action_label: __('Assign'),
          primary_action(values) {
            if (!values.users || !values.users.length) {
              frappe.msgprint(__('Please select at least one user'));
              return;
            }
            frappe.call({
              method: 'assign_sub_task_owners',
              doc: frm.doc,
              args: {
                row_name: row_name,
                users: values.users
              },
              callback() {
                frappe.msgprint(__('Owner(s) assigned'));
                dialog.hide();
                frm.reload_doc();
              }
            });
          }
        });

        dialog.set_value('users', existing_emails);
        dialog.show();
      });
    }

    if (frm.doc.task_id) {
      frm.add_custom_button(__('Add Message'), () => {
        show_message_dialog(frm);
      });
    }

    function show_message_dialog(frm) {
      const dialog = new frappe.ui.Dialog({
        title: __('Send Message'),
        size: 'large',
        fields: [
          {
            fieldname: 'messages_grid',
            fieldtype: 'Table',
            label: __('Messages'),
            reqd: 1,
            in_place_edit: false,
            fields: [
              {
                fieldname: 'tagged_user',
                fieldtype: 'Link',
                options: 'User',
                label: __('Tag User'),
                in_list_view: 1,
                columns: 2
              },
              {
                fieldname: 'message',
                fieldtype: 'Small Text',
                label: __('Message'),
                reqd: 1,
                in_list_view: 1,
                columns: 6
              }
            ],
            data: []
          }
        ],
        primary_action_label: __('Send'),
        primary_action(values) {
          const rows = (values.messages_grid || []).filter(r => r.message);
          if (!rows.length) {
            frappe.msgprint(__('Please add at least one message'));
            return;
          }
          frappe.call({
            method: 'add_message',
            doc: frm.doc,
            args: {
              messages: rows
            },
            callback() {
              frappe.msgprint(__('Message added'));
              dialog.hide();
              frm.reload_doc();
            }
          });
        }
      });

      dialog.show();
    }

    if (frm.doc.communication_open) {
      frm.add_custom_button(__('Close Communication'), () => {
        frappe.call({
          method: 'close_communication',
          doc: frm.doc,
          callback() {
            frappe.msgprint(__('Communication closed'));
            frm.reload_doc();
          }
        });
      });
    }
  }
});