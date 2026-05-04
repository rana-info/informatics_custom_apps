# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "As On Date", "fieldname": "as_on_date", "fieldtype": "Date", "width": 120},
        {"label": "Plant", "fieldname": "plant", "fieldtype": "Data", "width": 140},
        {"label": "Warehouse", "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 180},
        {"label": "Account", "fieldname": "account", "fieldtype": "Link", "options": "Account", "width": 180},
        {"label": "Segment", "fieldname": "segment", "fieldtype": "Data", "width": 150},
        {"label": "Material Code", "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 150},
        {"label": "Material Description", "fieldname": "item_name", "fieldtype": "Data", "width": 200},
        {"label": "UOM", "fieldname": "stock_uom", "fieldtype": "Data", "width": 80},
        {"label": "Quantity", "fieldname": "qty", "fieldtype": "Float", "width": 120},
        {"label": "Value", "fieldname": "value", "fieldtype": "Currency", "width": 120},
        {"label": "Rate", "fieldname": "rate", "fieldtype": "Currency", "width": 120},
    ]


def get_data(filters):

    return frappe.db.sql("""
        SELECT
            %(to_date)s AS as_on_date,

            t.Plant AS plant,
            t.Warehouse AS warehouse,
            t.Account AS account,
            t.Segment AS segment,

            t.item_code,
            t.item_name,
            t.stock_uom,

            ROUND(SUM(t.qty), 2) AS qty,
            ROUND(SUM(t.value), 2) AS value,

            CASE 
                WHEN SUM(t.qty) != 0 
                THEN ROUND(SUM(t.value) / SUM(t.qty), 2)
                ELSE 0 
            END AS rate

        FROM (

            SELECT
                wh.custom_branch AS Plant,
                wh.name AS Warehouse,
                wh.account AS Account,
                wh.custom_segment AS Segment,

                sle.item_code,
                i.item_name,
                i.stock_uom,

                sle.actual_qty AS qty,
                sle.stock_value_difference AS value

            FROM `tabStock Ledger Entry` sle

            LEFT JOIN `tabItem` i 
                ON sle.item_code = i.name

            LEFT JOIN `tabWarehouse` wh 
                ON sle.warehouse = wh.name

            WHERE
                sle.docstatus = 1
                AND sle.is_cancelled = 0
                AND sle.posting_date <= %(to_date)s

                AND sle.item_code IN %(item_list)s

                AND (
                    %(company)s IS NULL 
                    OR %(company)s = '' 
                    OR wh.company = %(company)s
                )

                AND (
                    %(plant)s IS NULL 
                    OR %(plant)s = '' 
                    OR wh.custom_branch = %(plant)s
                )

                AND (
                    %(segment)s IS NULL 
                    OR %(segment)s = '' 
                    OR wh.custom_segment = %(segment)s
                )

        ) t

        GROUP BY 
            t.Plant,
            t.Warehouse,
            t.Account,
            t.Segment,
            t.item_code,
            t.item_name,
            t.stock_uom

        HAVING 
            ROUND(SUM(t.qty), 2) >= 0

        ORDER BY 
            SUM(t.value) DESC
    """, {
        "to_date": filters.get("to_date"),
        "company": filters.get("company"),
        "plant": filters.get("plant"),
        "segment": filters.get("segment"),
        "item_list": tuple(get_item_list())
    }, as_dict=1)


def get_item_list():
    return [
        '129749','129129','125533','111523','105741','105740','100152','100151','100150','100149',
        '100148','100147','100146','100145','100108','100107','100105','100104','100103','100102',
        '100096','100095','100093','100091','100086','100085','100082','100079','100077','129946',
        '106657','100142','100141','100140','100139','100138','100137','100136','100134','100133',
        '100132','100131','100130','100129','100128','100126','100125','100124','100123','100122',
        '100121','100120','100118','100117','100116','100115','100114','100113','100112','100106',
        '100101','100100','100099','100022','100021','100020','100019','100018','100017','100016',
        '100008','100007','100006','100005','100004','100003','100002','132407','132406','132405',
        '100489','100488','100487','100486','100485','100484','100483','100482','100481','100480',
        '100479','100229','100228','100227','100226','100225','100224','100222','100221','100220',
        '100219','100218','100217','100216','100215','100214','100213','100211','100210','100209',
        '100207','100206','100205','100203','100202','100201','100199','100198','100197','100187',
        '100186','100185','100183','100182','100181','100180','100179','100178','100177','100176',
        '100175','100174','100173','100172','100168','100167','100166','100164','100163','100162',
        '100160','100159','100158','100156','100155','100154','100196','100195','100194','100192',
        '100191','100190','133844','132087','131959','130196','129853','129122','128539','125335',
        '119510','111708','111650','111600','106985','106984','106983','106443','106442','106441',
        '106440','106439','106437','106436','101077','100094','113401','111801','106981','106977',
        '106448','106447','106446','106444','100478','100477','100476','100475','100474','100097',
        '100087','100080','100078','125312','132413','100092','100084'
    ]