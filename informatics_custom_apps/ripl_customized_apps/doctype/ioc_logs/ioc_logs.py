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
from frappe.desk.doctype.notification_log.notification_log import enqueue_create_notification


class IOCLogs(Document):
	def validate(self):
		self.validate_completion_date()

	def on_update(self):
		self.update_task_status_from_subtasks()

	def validate_completion_date(self):
		for row in self.sub_task:
			# Sub-task target date can't be before its own start date
			if row.sub_task_start_date and row.sub_task_target_date:
				if getdate(row.sub_task_target_date) < getdate(row.sub_task_start_date):
					frappe.throw(
						f"Row {row.idx}: Sub-Task Target Date cannot be before Sub-Task Start Date."
					)

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

	def generate_task_id(self):
		today = nowdate()  # yyyy-mm-dd
		month_prefix = datetime.strptime(today, "%Y-%m-%d").strftime("%b")

		# Get latest task_id for the same month
		last_task_id = frappe.db.sql(
			"""
			SELECT task_id
			FROM `tabIOC Logs`
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
	def add_message(self, messages):
		if not messages:
			frappe.throw("Message cannot be empty")

		if isinstance(messages, str):
			messages = frappe.parse_json(messages)

		timestamp = format_datetime(now_datetime(), "yyyy-MM-dd HH:mm")
		user = frappe.session.user

		added = False
		tagged_users = []

		for row in messages:
			if not row.get("message"):
				continue
			self.append("messages", {
				"message": row.get("message"),
				"tagged_user": row.get("tagged_user"),
				"time": timestamp,
				"user": user
			})
			added = True
			if row.get("tagged_user") and row.get("tagged_user") != user:
				tagged_users.append(row.get("tagged_user"))

		if not added:
			frappe.throw("At least one message row is required")

		self.db_set("communication_open", 1)
		self.save()

		# Notify tagged users
		for tagged_user in set(tagged_users):
			notify_tagged_user(self, tagged_user, user, messages)

		return "Message(s) added successfully"

	@frappe.whitelist()
	def close_communication(self):
		self.db_set("communication_open", 0)
		self.save()
		return "Communication closed successfully"

	def update_task_status_from_subtasks(self):
		"""Roll sub-task statuses up into the parent Task Status."""
		if not self.sub_task:
			return

		statuses = [row.sub_task_status for row in self.sub_task]

		if all(status == "Completed" for status in statuses):
			self.db_set("task_status", "Completed")
			self.db_set("task_completion_date", nowdate())
		elif any(status in ("In Progress", "Completed") for status in statuses):
			self.db_set("task_status", "In Progress")
			self.db_set("task_completion_date", None)
		else:
			self.db_set("task_status", "Open")
			self.db_set("task_completion_date", None)

	@frappe.whitelist()
	def assign_sub_task_owners(self, row_name, users):
		if isinstance(users, str):
			users = frappe.parse_json(users)

		if not users:
			frappe.throw("Select at least one user")

		row = self.get("sub_task", {"name": row_name})
		if not row:
			frappe.throw("Sub-task row not found")
		row = row[0]

		full_names = [
			frappe.get_cached_value("User", u, "full_name") or u
			for u in users
		]

		row.sub_task_owner = ", ".join(full_names)
		row.sub_task_owner_emails = ", ".join(users)

		self.save()
		return "Owner(s) assigned successfully"

		
def notify_tagged_user(doc, tagged_user, sender, messages):
	# find the message text meant for this user (fallback: just show the last one)
	msg_text = next(
		(m.get("message") for m in messages if m.get("tagged_user") == tagged_user),
		""
	)
	notification_doc = frappe._dict({
		"type": "Alert",
		"document_type": doc.doctype,
		"document_name": doc.name,
		"subject": f"{frappe.get_cached_value('User', sender, 'full_name') or sender} tagged you in {doc.doctype} {doc.name}",
		"from_user": sender,
		"email_content": msg_text
	})
	enqueue_create_notification(tagged_user, notification_doc)