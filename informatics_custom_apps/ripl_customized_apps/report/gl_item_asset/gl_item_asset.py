import frappe
from frappe import _


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters or {})
    return columns, data


# =========================================================
# COLUMNS
# =========================================================

def get_columns():

    return [

        {
            "label": _("Posting Date"),
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 110
        },

        {
            "label": _("Company"),
            "fieldname": "company",
            "fieldtype": "Link",
            "options": "Company",
            "width": 180
        },

        {
            "label": _("Account"),
            "fieldname": "account",
            "fieldtype": "Link",
            "options": "Account",
            "width": 240
        },

        {
            "label": _("Voucher Type"),
            "fieldname": "voucher_type",
            "fieldtype": "Data",
            "width": 160
        },

        {
            "label": _("Voucher No"),
            "fieldname": "voucher_no",
            "fieldtype": "Dynamic Link",
            "options": "voucher_type",
            "width": 190
        },

        {
            "label": _("Party"),
            "fieldname": "party",
            "fieldtype": "Dynamic Link",
            "options": "party_type",
            "width": 180
        },

        {
            "label": _("Plant"),
            "fieldname": "branch",
            "fieldtype": "Link",
            "options": "Branch",
            "width": 150
        },

        {
            "label": _("Cost Center"),
            "fieldname": "cost_center",
            "fieldtype": "Link",
            "options": "Cost Center",
            "width": 180
        },

        {
            "label": _("Segment"),
            "fieldname": "segment",
            "fieldtype": "Link",
            "options": "Segment",
            "width": 140
        },

        {
            "label": _("Debit"),
            "fieldname": "debit",
            "fieldtype": "Currency",
            "width": 140
        },

        {
            "label": _("Credit"),
            "fieldname": "credit",
            "fieldtype": "Currency",
            "width": 140
        },

        {
            "label": _("Item Code"),
            "fieldname": "item_code",
            "fieldtype": "Link",
            "options": "Item",
            "width": 150
        },

        {
            "label": _("Item Name"),
            "fieldname": "item_name",
            "fieldtype": "Data",
            "width": 260
        },

        {
            "label": _("Qty"),
            "fieldname": "qty",
            "fieldtype": "Float",
            "width": 120
        },

        {
            "label": _("Rate"),
            "fieldname": "rate",
            "fieldtype": "Currency",
            "width": 130
        },

        {
            "label": _("Amount"),
            "fieldname": "amount",
            "fieldtype": "Currency",
            "width": 140
        },

        # =====================================================
        # ASSET
        # =====================================================

        {
            "label": _("Asset"),
            "fieldname": "asset",
            "fieldtype": "Link",
            "options": "Asset",
            "width": 180
        },

        {
            "label": _("Asset Name"),
            "fieldname": "asset_name",
            "fieldtype": "Data",
            "width": 240
        },

        {
            "label": _("Asset Category"),
            "fieldname": "asset_category",
            "fieldtype": "Data",
            "width": 180
        },

        {
            "label": _("Gross Purchase Amount"),
            "fieldname": "gross_purchase_amount",
            "fieldtype": "Currency",
            "width": 180
        },

        {
            "label": _("Purchase Invoice"),
            "fieldname": "purchase_invoice",
            "fieldtype": "Link",
            "options": "Purchase Invoice",
            "width": 180
        },

        {
            "label": _("Sales Invoice"),
            "fieldname": "sales_invoice",
            "fieldtype": "Link",
            "options": "Sales Invoice",
            "width": 180
        },

        # =====================================================
        # CONTRACT
        # =====================================================

        {
            "label": _("Contract"),
            "fieldname": "custom_contract",
            "fieldtype": "Link",
            "options": "Contract",
            "width": 180
        },

        {
            "label": _("Contract Asset"),
            "fieldname": "contract_asset",
            "fieldtype": "Link",
            "options": "Asset",
            "width": 180
        },

        {
            "label": _("Contract Asset Name"),
            "fieldname": "contract_asset_name",
            "fieldtype": "Data",
            "width": 220
        },

        # =====================================================
        # CAPITALIZATION
        # =====================================================

        {
            "label": _("Asset Capitalization"),
            "fieldname": "asset_capitalization",
            "fieldtype": "Link",
            "options": "Asset Capitalization",
            "width": 220
        },

        {
            "label": _("Capitalization Item"),
            "fieldname": "capitalization_item",
            "fieldtype": "Link",
            "options": "Item",
            "width": 200
        },

        {
            "label": _("Capitalization Amount"),
            "fieldname": "capitalization_amount",
            "fieldtype": "Currency",
            "width": 180
        },

        # =====================================================
        # REPAIR
        # =====================================================

        {
            "label": _("Asset Repair"),
            "fieldname": "asset_repair",
            "fieldtype": "Link",
            "options": "Asset Repair",
            "width": 200
        },

        {
            "label": _("Repair Item"),
            "fieldname": "repair_item",
            "fieldtype": "Link",
            "options": "Item",
            "width": 180
        },

        {
            "label": _("Repair Item Name"),
            "fieldname": "repair_item_name",
            "fieldtype": "Data",
            "width": 240
        },

        {
            "label": _("Repair Qty"),
            "fieldname": "repair_qty",
            "fieldtype": "Float",
            "width": 120
        },

        {
            "label": _("Repair Rate"),
            "fieldname": "repair_rate",
            "fieldtype": "Currency",
            "width": 140
        },

        {
            "label": _("Repair Amount"),
            "fieldname": "repair_amount",
            "fieldtype": "Currency",
            "width": 160
        }

    ]


# =========================================================
# DATA
# =========================================================

def get_data(filters):

    conditions = ""
    values = {}

    if filters.get("company"):
        conditions += " AND gl.company = %(company)s "
        values["company"] = filters.get("company")

    if filters.get("from_date"):
        conditions += " AND gl.posting_date >= %(from_date)s "
        values["from_date"] = filters.get("from_date")

    if filters.get("to_date"):
        conditions += " AND gl.posting_date <= %(to_date)s "
        values["to_date"] = filters.get("to_date")

    if filters.get("account"):
        conditions += " AND gl.account = %(account)s "
        values["account"] = filters.get("account")

    query = f"""

        SELECT

            gl.posting_date,
            gl.company,
            gl.account,
            gl.voucher_type,
            gl.voucher_no,
            gl.party,
            gl.party_type,
            gl.branch,
            gl.cost_center,
            gl.segment,

            CASE
                WHEN ROW_NUMBER() OVER (
                    PARTITION BY gl.name
                    ORDER BY item_data.item_code
                ) = 1
                THEN gl.debit
                ELSE 0
            END AS debit,

            CASE
                WHEN ROW_NUMBER() OVER (
                    PARTITION BY gl.name
                    ORDER BY item_data.item_code
                ) = 1
                THEN gl.credit
                ELSE 0
            END AS credit,

            item_data.item_code,
            item_data.item_name,
            item_data.qty,
            item_data.rate,
            item_data.amount,

            item_data.asset,

            asset.asset_name,
            asset.asset_category,
            asset.gross_purchase_amount,
            asset.purchase_invoice,

            CASE
                WHEN gl.voucher_type = 'Sales Invoice'
                THEN gl.voucher_no
                ELSE NULL
            END AS sales_invoice,

            item_data.custom_contract,

            contract.asset AS contract_asset,
            contract.asset_name AS contract_asset_name,

            cap.asset_capitalization,
            cap.capitalization_item,
            cap.capitalization_amount,

            rep.asset_repair,
            rep.repair_item,
            rep.repair_item_name,
            rep.repair_qty,
            rep.repair_rate,
            rep.repair_amount

        FROM `tabGL Entry` gl

        LEFT JOIN (

            # =====================================================
            # PURCHASE INVOICE
            # =====================================================

            SELECT

                pii.parent,
                pii.item_code,
                pii.item_name,
                pii.qty,
                pii.rate,
                pii.amount,

                con.asset AS asset,

                pii.custom_contract,

                'Purchase Invoice' AS voucher_type

            FROM `tabPurchase Invoice Item` pii

            LEFT JOIN `tabContract` con
                ON con.name = pii.custom_contract

            UNION ALL

            # =====================================================
            # SALES INVOICE
            # =====================================================

            SELECT

                sii.parent,
                sii.item_code,
                sii.item_name,
                sii.qty,
                sii.rate,
                sii.amount,

                sii.asset,

                NULL AS custom_contract,

                'Sales Invoice' AS voucher_type

            FROM `tabSales Invoice Item` sii

            UNION ALL

            # =====================================================
            # PURCHASE RECEIPT
            # =====================================================

            SELECT

                pri.parent,
                pri.item_code,
                pri.item_name,
                pri.qty,
                pri.rate,
                pri.amount,

                NULL AS asset,

                NULL AS custom_contract,

                'Purchase Receipt' AS voucher_type

            FROM `tabPurchase Receipt Item` pri

            UNION ALL

            # =====================================================
            # DELIVERY NOTE
            # =====================================================

            SELECT

                dni.parent,
                dni.item_code,
                dni.item_name,
                dni.qty,
                dni.rate,
                dni.amount,

                NULL AS asset,

                NULL AS custom_contract,

                'Delivery Note' AS voucher_type

            FROM `tabDelivery Note Item` dni

            UNION ALL

            # =====================================================
            # MATERIAL REQUEST
            # =====================================================

            SELECT

                mri.parent,
                mri.item_code,
                mri.item_name,
                mri.qty,
                mri.rate,
                mri.amount,

                NULL AS asset,

                NULL AS custom_contract,

                'Material Request' AS voucher_type

            FROM `tabMaterial Request Item` mri

        ) item_data

            ON item_data.parent = gl.voucher_no
            AND item_data.voucher_type = gl.voucher_type

        # =====================================================
        # ASSET MASTER
        # =====================================================

        LEFT JOIN `tabAsset` asset
            ON asset.name = item_data.asset

        # =====================================================
        # CONTRACT
        # =====================================================

        LEFT JOIN `tabContract` contract
            ON contract.name = item_data.custom_contract

        # =====================================================
        # ASSET CAPITALIZATION
        # =====================================================

        LEFT JOIN (

            SELECT

                ac.name AS asset_capitalization,

                ac.target_asset AS asset,

                acsi.item_code AS capitalization_item,

                acsi.amount AS capitalization_amount

            FROM `tabAsset Capitalization` ac

            LEFT JOIN `tabAsset Capitalization Stock Item` acsi
                ON acsi.parent = ac.name

            WHERE ac.docstatus = 1

        ) cap

            ON cap.asset = item_data.asset

        # =====================================================
        # ASSET REPAIR
        # =====================================================

        LEFT JOIN (

            SELECT

                ar.name AS asset_repair,

                ar.asset,

                ari.item_code AS repair_item,

                ari.custom_item_name AS repair_item_name,

                ari.custom_to_be_consumed AS repair_qty,

                ari.valuation_rate AS repair_rate,

                ari.total_value AS repair_amount

            FROM `tabAsset Repair` ar

            LEFT JOIN `tabAsset Repair Consumed Item` ari
                ON ari.parent = ar.name

            WHERE ar.docstatus = 1

        ) rep

            ON rep.asset = item_data.asset

        WHERE

            gl.is_cancelled = 0

            {conditions}

            AND (
                gl.debit != 0
                OR gl.credit != 0
            )

        ORDER BY
            gl.posting_date DESC,
            gl.voucher_no DESC

    """

    return frappe.db.sql(query, values, as_dict=True)