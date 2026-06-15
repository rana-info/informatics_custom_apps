import frappe

@frappe.whitelist()
def get_item_group_chart():
    """
    Returns two separate datasets:
      - store_items : grouped at direct-child-of-Store Items level (Pesticides excluded)
      - pesticides  : grouped at direct-child-of-Pesticides level (GST slabs)
    """

    store_items = frappe.db.sql("""
        SELECT
            plant,
            item_group,
            ROUND(SUM(qty),         2) AS qty,
            ROUND(SUM(stock_value), 2) AS stock_value
        FROM (
            SELECT
                CASE
                    WHEN IFNULL(TRIM(wh.custom_branch), '') = ''
                    THEN 'Plant Missing'
                    ELSE wh.custom_branch
                END AS plant,

                CASE
                    WHEN ig.parent_item_group = 'Store Items'
                    THEN ig.name
                    ELSE ig.parent_item_group
                END AS item_group,

                b.actual_qty  AS qty,
                b.stock_value AS stock_value

            FROM `tabBin`       b
            INNER JOIN `tabItem`       i  ON i.name  = b.item_code
            INNER JOIN `tabItem Group` ig ON ig.name = i.item_group
            INNER JOIN `tabWarehouse`  wh ON wh.name = b.warehouse

            WHERE
                b.actual_qty > 0
                AND wh.is_group = 0
                AND (
                    ig.parent_item_group = 'Store Items'
                    OR ig.parent_item_group IN (
                        SELECT name FROM `tabItem Group`
                        WHERE parent_item_group = 'Store Items'
                    )
                )
                -- exclude entire Pesticides sub-tree
                AND ig.name              != 'Pesticides'
                AND ig.parent_item_group != 'Pesticides'

        ) base
        GROUP BY plant, item_group
        HAVING SUM(qty) > 0
        ORDER BY plant, qty DESC
    """, as_dict=True)

    pesticides = frappe.db.sql("""
       SELECT
            plant,
            'Pesticides' AS item_group,
            ROUND(SUM(qty), 2) AS qty,
            ROUND(SUM(stock_value), 2) AS stock_value
        FROM (
            SELECT
                CASE
                    WHEN IFNULL(TRIM(wh.custom_branch), '') = ''
                    THEN 'Plant Missing'
                    ELSE wh.custom_branch
                END AS plant,

                b.actual_qty AS qty,
                b.stock_value AS stock_value

            FROM `tabBin` b
            INNER JOIN `tabItem` i
                ON i.name = b.item_code
            INNER JOIN `tabItem Group` ig
                ON ig.name = i.item_group
            INNER JOIN `tabWarehouse` wh
                ON wh.name = b.warehouse

            WHERE
                b.actual_qty > 0
                AND wh.is_group = 0

                -- include entire Pesticides hierarchy
                AND (
                    ig.name = 'Pesticides'
                    OR ig.parent_item_group = 'Pesticides'
                )

        ) base

        GROUP BY plant
        HAVING SUM(qty) > 0
        ORDER BY plant;
    """, as_dict=True)

    return {
        "store_items": store_items,
        "pesticides":  pesticides
    }


@frappe.whitelist()
def get_items_for_group(item_group, category):
    return frappe.db.sql("""
        SELECT
            b.item_code,
            i.item_name,
            i.item_group                  AS real_item_group,
            i.stock_uom                   AS uom,
            ROUND(SUM(b.actual_qty),  2)  AS qty,
            ROUND(SUM(b.stock_value), 2)  AS stock_value
        FROM `tabBin` b
        INNER JOIN `tabItem`       i  ON i.name  = b.item_code
        INNER JOIN `tabItem Group` ig ON ig.name = i.item_group
        INNER JOIN `tabWarehouse`  wh ON wh.name = b.warehouse
        WHERE
            b.actual_qty > 0
            AND wh.is_group = 0
            AND (
                ig.name               = %(item_group)s
                OR ig.parent_item_group = %(item_group)s
            )
            # AND ig.name              != 'Pesticides'
            # AND ig.parent_item_group != 'Pesticides'
        GROUP BY
            b.item_code, i.item_name, i.item_group, i.stock_uom
        HAVING SUM(b.actual_qty) > 0
        ORDER BY qty DESC
        LIMIT 100
    """, {"item_group": item_group}, as_dict=True)