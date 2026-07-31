"""Compatibility namespace for historical migrations.

Runtime staff models live in ``superadmin.staff_management``.  This package
must remain importable because migration 0001 serialized the former module
paths and Django imports those paths whenever it builds the migration graph.
"""
