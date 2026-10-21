"""ComplaintTeam was removed — complaints are assigned and escalated along the
Staff Hierarchy (app/services/complaint_escalation.py).

Only the id default is kept: migrations are generated per environment and
their 0001_initial references `team_master.generate_team_id`, so deleting it
would break loading those migration files.
"""
from app.utils.comfun import generate_unique_id


def generate_team_id():
    return f"CPTTEAM-{generate_unique_id()}"
