# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    filters = frappe._dict(filters or {})

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def get_columns():
    return [
        {
            "label": "Legal Case",
            "fieldname": "legal_case",
            "fieldtype": "Link",
            "options": "Legal Cases",
            "width": 150,
        },
        {
            "label": "Company",
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 150,
        },
        {
            "label": "Plant",
            "fieldname": "plant",
            "fieldtype": "Link",
            "options": "Branch",
            "width": 120,
        },
        {
            "label": "Case No.",
            "fieldname": "case_no",
            "width": 150,
        },
        {
            "label": "First Hearing Date",
            "fieldname": "first_hearing_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": "Next Hearing Date",
            "fieldname": "next_hearing_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": "Case Type",
            "fieldname": "case_type",
            "width": 120,
        },
        {
            "label": "Filed By / Against",
            "fieldname": "filed_by_against",
            "width": 120,
        },
        {
            "label": "Civil/Criminal",
            "fieldname": "civil_criminal",
            "width": 100,
        },
        {
            "label": "Under Sections",
            "fieldname": "under_sections",
            "width": 150,
        },
        {
            "label": "Action Required by Site",
            "fieldname": "action_required_by_site",
            "width": 200,
        },
        {
            "label": "HO / Management Intervention Required",
            "fieldname": "management_intervention_required",
            "width": 180,
        },
        {
            "label": "Party Name",
            "fieldname": "party_name",
            "width": 180,
        },
        {
            "label": "Court / Forum / Authority",
            "fieldname": "court_forum_authority",
            "width": 180,
        },
        {
            "label": "Amount Involved",
            "fieldname": "amount_involved",
            "fieldtype": "Currency",
            "width": 120,
        },
        {
            "label": "Current Status",
            "fieldname": "current_status",
            "width": 120,
        },
        {
            "label": "Advocate / Consultant",
            "fieldname": "advocate_consultant",
            "width": 180,
        },
        {
            "label": "Risk Level",
            "fieldname": "risk_level",
            "width": 100,
        },
        {
            "label": "Owner",
            "fieldname": "owners",
            "width": 150,
        },
        {
            "label": "Target Date",
            "fieldname": "target_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": "Remarks",
            "fieldname": "remarks",
            "width": 250,
        },

        # History
        {
            "label": "Last Hearing Date",
            "fieldname": "history_last_hearing_date",
            "fieldtype": "Date",
            "width": 120,
        },
        {
            "label": "Last Order / Update",
            "fieldname": "history_last_order_update",
            "width": 180,
        },
        {
            "label": "History Advocate / Consultant",
            "fieldname": "history_advocate_consultant",
            "width": 180,
        },
        {
            "label": "History Action Required by Site",
            "fieldname": "history_action_required_by_site",
            "width": 200,
        },
        {
            "label": "History Owner",
            "fieldname": "history_owners",
            "width": 150,
        },
        {
            "label": "History Remarks",
            "fieldname": "history_remarks",
            "width": 150,
        },
        {
            "label": "History Next Hearing Date",
            "fieldname": "history_next_hearing_date",
            "fieldtype": "Date",
            "width": 120,
        },
    ]


def get_data(filters):
    conditions = []
    values = {}

    # ---------------------------------------------------------
    # Optional Company Filter
    # ---------------------------------------------------------
    if filters.get("company"):
        conditions.append("lc.company = %(company)s")
        values["company"] = filters.company

    # ---------------------------------------------------------
    # Optional From Date Filter
    # ---------------------------------------------------------
    if filters.get("from_date"):
        conditions.append("lc.next_hearing_date >= %(from_date)s")
        values["from_date"] = filters.from_date

    # ---------------------------------------------------------
    # Optional To Date Filter
    # ---------------------------------------------------------
    if filters.get("to_date"):
        conditions.append("lc.next_hearing_date <= %(to_date)s")
        values["to_date"] = filters.to_date

    # If filters exist, prepend AND
    where_clause = ""

    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        WITH case_history AS (
            SELECT
                lch.*,
                ROW_NUMBER() OVER (
                    PARTITION BY lch.parent
                    ORDER BY lch.idx
                ) AS child_row
            FROM `tabLegal Cases History` lch
            WHERE lch.parenttype = 'Legal Cases'
              AND lch.parentfield = 'legal_cases_history'
        )

        SELECT

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.name
                ELSE ''
            END AS legal_case,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.company
                ELSE ''
            END AS company,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.plant
                ELSE ''
            END AS plant,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.case_no
                ELSE ''
            END AS case_no,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.first_hearing_date
                ELSE NULL
            END AS first_hearing_date,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.next_hearing_date
                ELSE NULL
            END AS next_hearing_date,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.case_type
                ELSE ''
            END AS case_type,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.filed_by__against
                ELSE ''
            END AS filed_by_against,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.provision_made
                ELSE ''
            END AS civil_criminal,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.under_sections
                ELSE ''
            END AS under_sections,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.action_required_by_site
                ELSE ''
            END AS action_required_by_site,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.ho__management_intervention_required
                ELSE ''
            END AS management_intervention_required,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.party_name
                ELSE ''
            END AS party_name,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.court__forum__authority
                ELSE ''
            END AS court_forum_authority,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.amount_involved
                ELSE NULL
            END AS amount_involved,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.current_status
                ELSE ''
            END AS current_status,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.advocate__consultant
                ELSE ''
            END AS advocate_consultant,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.risk_level
                ELSE ''
            END AS risk_level,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.owners
                ELSE ''
            END AS owners,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.target_date
                ELSE NULL
            END AS target_date,

            CASE
                WHEN ch.child_row = 1 OR ch.child_row IS NULL
                THEN lc.remarks
                ELSE ''
            END AS remarks,

            ch.last_hearing_date AS history_last_hearing_date,
            ch.last_order__update AS history_last_order_update,
            ch.advocate__consultant AS history_advocate_consultant,
            ch.action_required_by_site AS history_action_required_by_site,
            ch.owners AS history_owners,
            ch.remarks AS history_remarks,
            ch.next_hearing_date AS history_next_hearing_date

        FROM `tabLegal Cases` lc

        LEFT JOIN case_history ch
            ON ch.parent = lc.name

        {where_clause}

        ORDER BY
            lc.name,
            ch.child_row
    """

    return frappe.db.sql(
        query,
        values,
        as_dict=True
    )