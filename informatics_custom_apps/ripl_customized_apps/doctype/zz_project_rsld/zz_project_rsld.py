# Copyright (c) 2026, Monil Kamboj and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import (
	now_datetime,
	format_datetime,
	nowdate,
	getdate,
	today
)
from datetime import datetime



class zzProjectRSLD(Document):
	def validate(self):
		if getdate(self.task_target_date)< getdate(self.task_start_date):
					frappe.throw("Target Date Cannot Be Before Task Start Date!")
		self.validate_sub_task_weightage()
		self.validate_completion_date()
	def on_update(self):
		self.update_task_percentage_from_subtasks()

	def validate_sub_task_weightage(self):
		total_weightage = 0

		for row in self.sub_task:
			total_weightage += row.sub_task_weightage or 0

		if total_weightage != 100:
			frappe.throw(
				f"Total Sub-Task Weightage must be exactly 100%. "
				f"Current total is {total_weightage}%."
			)

	def validate_completion_date(self):
		for row in self.sub_task:
			if row.completion_date:
				# Cannot be in the future
				if getdate(row.completion_date) > getdate(today()):
					frappe.throw(
						f"Row {row.idx}: Sub-task Completion Date "
						f"cannot be greater than today's date."
					)

				# Cannot be before task start date
				if self.task_start_date and getdate(row.completion_date) < getdate(self.task_start_date):
					frappe.throw(
						f"Row {row.idx}: Sub-task Completion Date "
						f"cannot be before Task Start Date ({format_datetime(self.task_start_date)})."
					)


	def before_save(self):
		# Assign only if empty (important for edits)
		if not self.task_id:
			self.task_id = self.generate_task_id()
		self.update_target_over_days()
		if self.task_completion_date:
			self.db_set("task_status", "Completed")

	def update_target_over_days(self):
			if self.task_target_date:
				# Compute difference in days
				delta = (getdate(self.task_target_date) - getdate(today())).days
				self.target_over_days = (delta)
				
	def generate_task_id(self):
		today = nowdate()  # yyyy-mm-dd
		month_prefix = datetime.strptime(today, "%Y-%m-%d").strftime("%b")

		# Get latest task_id for the same month
		last_task_id = frappe.db.sql(
			"""
			SELECT task_id
			FROM `tabzz Project RSLD`
			WHERE task_id LIKE %s
			ORDER BY creation DESC
			LIMIT 1
			""",
			(f"{month_prefix}%",),
			as_dict=True
		)

		if last_task_id:
			last_number = int(last_task_id[0].task_id[-4:])
			new_number = last_number + 1
		else:
			new_number = 1

		return f"{month_prefix}{new_number:04d}"
	
	@frappe.whitelist()
	def add_message(self, message):
		if not message:
			frappe.throw("Message cannot be empty")
		timestamp = format_datetime(
            now_datetime(),
            "dd-MM-yyyy HH:mm"
        )
		user = frappe.session.user
		content = f"{user} messaged: `{message}` at {timestamp}."

		self.add_comment(
			text=content
		)

		return "Message added successfully"
	
	def update_task_percentage_from_subtasks(self):
		total_percentage = 0
		print("-------------------->Updating task percentage from subtasks...")
		for row in self.sub_task:
			if row.task_completed:
				total_percentage += row.sub_task_weightage or 0

		# Update directly in DB (important for submitted docs)
		self.db_set(
			"task_percentage",
			total_percentage
		)
		if self.task_percentage < 100:
			self.db_set("task_status", "In Progress")
			self.db_set("task_completion_date", None)
		else:
			self.db_set("task_status", "Completed")
			self.db_set("task_completion_date", nowdate())
