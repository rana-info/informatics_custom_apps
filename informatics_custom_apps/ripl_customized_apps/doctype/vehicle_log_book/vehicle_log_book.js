// Copyright (c) 2026, Monil Kamboj and contributors
// For license information, please see license.txt

// Fields with NO depends_on of their own in the doctype JSON - only these
// need to be controlled from script. Everything else (purpose, person,
// reason, person_v, reason_v, distance, diesel_details_section, in/out
// time+km) already has its own depends_on / mandatory_depends_on in the
// JSON, and Frappe re-evaluates those natively on every field change -
// manually toggling them too just fights with that and causes flicker.
const HIDE_UNTIL_ENTRY_TYPE_FIELDS = ['plant', 'vehicle_number', 'vehicle_type'];
const MOVEMENT_ONLY_DISPLAY_FIELDS = ['from', 'to'];

// Fields to blank out (not just hide) when switching entry_type away from a movement
const MOVEMENT_VALUE_FIELDS = ['purpose', 'from', 'to', 'person', 'reason', 'person_v', 'reason_v', 'distance'];

// Diesel fields have no depends_on of their own (only their parent section
// "diesel_details_section" does), so toggling them individually is safe.
const DIESEL_ONLY_FIELDS = ['required_diesel', 'allocated_diesel', 'slip_number', 'amount', 'date'];

frappe.ui.form.on('Vehicle Log Book', {

	purpose: function (frm) {
		// Visitor trips always open with "In" (visitor enters premises first).
		// Shift / Co-Work can open with either In or Out - these are contract
		// cabs, so a vehicle might already be out (returns -> In first) or about
		// to leave (Out first). We don't force a direction for those.
		if (frm.doc.__islocal && !frm.doc.in_progress && frm.doc.purpose === 'Visitor') {
			frm.set_value('entry_type', 'In');
		}

		// Clear out fields that don't apply to the newly selected purpose
		if (frm.doc.purpose === 'Visitor') {
			frm.set_value('person', '');
			frm.set_value('reason', '');
			frm.set_value('in_km', '');
			frm.set_value('out_km', '');
			frm.set_value('distance', '');
		} else {
			frm.set_value('person_v', '');
			frm.set_value('reason_v', '');
		}
	},

	entry_type: function (frm) {
		if (frm.doc.entry_type === 'Diesel Issue') {
			// Not a vehicle movement - clear anything movement-related
			MOVEMENT_VALUE_FIELDS.forEach(f => frm.set_value(f, ''));
			frm.set_value('in_time', '');
			frm.set_value('in_km', '');
			frm.set_value('out_time', '');
			frm.set_value('out_km', '');
		} else {
			// In / Out - clear diesel-only fields, and whichever leg isn't relevant
			DIESEL_ONLY_FIELDS.forEach(f => frm.set_value(f, ''));
			if (frm.doc.entry_type === 'In') {
				frm.set_value('out_time', '');
				frm.set_value('out_km', '');
			} else if (frm.doc.entry_type === 'Out') {
				frm.set_value('in_time', '');
				frm.set_value('in_km', '');
			}
		}
		toggle_fields_by_entry_type(frm);
	},

	in_km: function (frm) {
		calculate_distance(frm);
	},

	out_km: function (frm) {
		calculate_distance(frm);
	},

	refresh: function (frm) {
		toggle_fields_by_entry_type(frm);

		// Show "Close Entry" only on a submitted, still-open trip
		// (Diesel Issue entries never get in_progress=1, so this naturally excludes them)
		if (frm.doc.docstatus === 1 && frm.doc.in_progress && !frm.doc.is_completed) {
			frm.add_custom_button(__('Close Entry'), function () {
				show_close_entry_dialog(frm);
			}).addClass('btn-primary');
		}
	}
});

function toggle_fields_by_entry_type(frm) {
	let entry_type = frm.doc.entry_type;
	let is_diesel = entry_type === 'Diesel Issue';
	let is_movement = entry_type === 'In' || entry_type === 'Out';
	let has_entry_type = !!entry_type;

	// Nothing shows until an entry type is picked
	HIDE_UNTIL_ENTRY_TYPE_FIELDS.forEach(f => frm.toggle_display(f, has_entry_type));

	// "from"/"to" have no depends_on of their own, so only a movement shows them
	MOVEMENT_ONLY_DISPLAY_FIELDS.forEach(f => frm.toggle_display(f, is_movement));

	// Diesel fields have no depends_on of their own either
	DIESEL_ONLY_FIELDS.forEach(f => frm.toggle_display(f, is_diesel));

	// Deliberately NOT touching: purpose, person, reason, person_v, reason_v,
	// distance, diesel_details_section, in_time/in_km/out_time/out_km.
	// These all have their own depends_on / mandatory_depends_on in the
	// doctype JSON now, and Frappe re-evaluates those automatically on every
	// field change. Toggling them here too fought with that and caused the
	// flicker/disappearing-fields bug.
}

function calculate_distance(frm) {
	let in_km = parseFloat(frm.doc.in_km);
	let out_km = parseFloat(frm.doc.out_km);
	if (!isNaN(in_km) && !isNaN(out_km)) {
		frm.set_value('distance', Math.abs(in_km - out_km));
	}
}

function show_close_entry_dialog(frm) {
	let is_visitor = frm.doc.purpose === 'Visitor';
	// If it opened with "Out", it closes with "In" - and vice versa
	let closing_is_in = frm.doc.entry_type === 'Out';

	let fields = [];

	if (closing_is_in) {
		fields.push({
			fieldname: 'in_time',
			fieldtype: 'Datetime',
			label: __('In Time'),
			reqd: 1,
			default: frappe.datetime.now_datetime()
		});
		if (!is_visitor) {
			fields.push({
				fieldname: 'in_km',
				fieldtype: 'Int',
				label: __('In Km'),
				reqd: 1
			});
		}
	} else {
		fields.push({
			fieldname: 'out_time',
			fieldtype: 'Datetime',
			label: __('Out Time'),
			reqd: 1,
			default: frappe.datetime.now_datetime()
		});
		if (!is_visitor) {
			fields.push({
				fieldname: 'out_km',
				fieldtype: 'Int',
				label: __('Out Km'),
				reqd: 1
			});
		}
	}

	let d = new frappe.ui.Dialog({
		title: __('Close Entry'),
		fields: fields,
		primary_action_label: __('Close'),
		primary_action(values) {
			if (!is_visitor) {
				let opening_km = closing_is_in ? frm.doc.out_km : frm.doc.in_km;
				let closing_km = closing_is_in ? values.in_km : values.out_km;
				if (parseFloat(closing_km) < parseFloat(opening_km)) {
					frappe.throw(__('{0} cannot be less than the recorded {1} ({2}).', [
						closing_is_in ? __('In Km') : __('Out Km'),
						closing_is_in ? __('Out Km') : __('In Km'),
						opening_km
					]));
				}
			}

			frappe.call({
				method: 'informatics_custom_apps.ripl_customized_apps.doctype.vehicle_log_book.vehicle_log_book.close_entry',
				args: {
					docname: frm.doc.name,
					values: values
				},
				freeze: true,
				callback: function (r) {
					if (!r.exc) {
						d.hide();
						frm.reload_doc();
					}
				}
			});
		}
	});

	d.show();
}