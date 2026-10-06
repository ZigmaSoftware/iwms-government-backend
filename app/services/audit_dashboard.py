"""
Audit Dashboard: one summary per audit trail (Common, Login, User Access,
Complaint) over a recent window — headline counts, a per-day trend, a
breakdown for the doughnut, and the matching rows flattened to the same
shape the dashboard table renders.

Ported from the private backend. Government has no Company/Project, so the
private trail's company/project scope becomes district / local body here,
and Static Route Audit (no such trail in government) is left out.

Every trail is read from its own table; nothing is copied or cached. The
viewset hands in a queryset already confined to the requester by that
audit's own list page (see AuditDashboardViewSet._scoped).

Days are bucketed in Python on local time rather than with TruncDate, so
the trend does not depend on MySQL having its timezone tables loaded.
"""
import importlib
from collections import Counter
from datetime import datetime, time, timedelta

from django.db.models import Count, Q
from django.utils import timezone

from app.models.core_modules.complaint_management import (
    ComplaintEscalationHistory,
    ComplaintStatus,
    ComplaintTicket,
)
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.superadmin.audits.login_audit import LoginAudit
from app.models.superadmin.audits.permission_audit import PermissionAuditLog
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.serializers.superadmin.audits.common_audit_serializer import (
    GEO_NAME_ATTRS,
    geo_display,
    geo_ref_name,
)
from app.serializers.superadmin.audits.permission_audit_serializer import (
    LOCAL_BODY_MODELS,
    PermissionAuditLogListSerializer,
)
from app.services.complaint_audit import summarize_tickets
from app.utils.common_audit import CommonAudit
from app.utils.hierarchy import LOCAL_BODY_FIELDS

ALLOWED_DAYS = (7, 30, 90)
DEFAULT_DAYS = 30


def _iso(value):
    return value.isoformat() if value else None


def _local_body_id_q(local_body_ids, field_name=lambda level: f"{level}_id"):
    """Rows whose local-body column, at any level, is one of `local_body_ids`."""
    query = Q()
    for level in LOCAL_BODY_FIELDS:
        query |= Q(**{f"{field_name(level)}__in": local_body_ids})
    return query


def _distinct(queryset, field):
    # order_by() clears Meta.ordering, which would otherwise make DISTINCT
    # apply to (value, ordering column) pairs.
    return {v for v in queryset.order_by().values_list(field, flat=True).distinct() if v}


def _flat_local_body_refs(queryset, field_name=lambda level: f"{level}_id"):
    """{(level, unique_id)} across the five flat local-body columns."""
    return {
        (level, uid)
        for level in LOCAL_BODY_FIELDS
        for uid in _distinct(queryset, field_name(level))
    }


def geo_option(level, unique_id):
    """A district / local body dropdown entry, shaped like the Common Audit
    filter-options entries."""
    return {
        "unique_id": unique_id,
        "name": geo_ref_name(level, unique_id) or unique_id,
        "level": GEO_NAME_ATTRS[level][1],
    }


# ---------------------------------------------------------------------------
# One class per trail. Each names its table's columns and turns rows into
# KPIs, breakdown slices and table rows, and knows how to narrow its rows to
# a district / local body.
# ---------------------------------------------------------------------------


class _Trail:
    model = None
    date_field = None
    search_fields = ()

    def unique(self, queryset):
        """A requester scope may come back as a DISTINCT union (complaint
        tickets); re-select it by pk so the per-column value counts below
        are not collapsed by that DISTINCT."""
        if queryset.query.distinct:
            return self.model.objects.filter(pk__in=queryset.order_by().values("pk"))
        return queryset

    def search(self, queryset, term):
        query = Q()
        for field in self.search_fields:
            query |= Q(**{f"{field}__icontains": term})
        return queryset.filter(query)

    def ordered(self, queryset):
        return queryset.order_by(f"-{self.date_field}", "-pk")

    def narrow(self, queryset, district_ids, local_body_ids):
        """Only rows in `district_ids` / `local_body_ids` (either may be
        empty). Applied on top of the requester scope, so it can only
        narrow, never widen."""
        raise NotImplementedError

    def district_ids(self, queryset):
        raise NotImplementedError

    def local_body_refs(self, queryset):
        """{(level, unique_id)} of the local bodies `queryset` touches."""
        raise NotImplementedError

    def kpis(self, queryset):
        raise NotImplementedError

    def breakdown(self, queryset):
        raise NotImplementedError

    def rows(self, records):
        raise NotImplementedError

    @staticmethod
    def _slices(counts, labels=None):
        labels = labels or {}
        return [
            {"key": key, "label": labels.get(key, key), "count": count}
            for key, count in sorted(counts.items(), key=lambda kv: -kv[1])
            if key is not None
        ]

    @staticmethod
    def _counts(queryset, field):
        """{value: row count} for one column, grouped in the database."""
        return Counter(dict(
            queryset.order_by().values(field).annotate(n=Count("pk")).values_list(field, "n")
        ))


class CommonTrail(_Trail):
    model = CommonAudit
    date_field = "createdAt"
    search_fields = ("module_name", "endpoint_name", "createdBy", "created_by_name", "object_id")

    # Writes are recorded by HTTP method; UPLOAD/DOWNLOAD are the manual
    # Excel events, which change no record.
    ACTIONS = {"POST": "CREATE", "PUT": "UPDATE", "PATCH": "UPDATE", "DELETE": "DELETE"}

    def _action(self, method):
        return self.ACTIONS.get((method or "").upper(), "OTHER")

    def _actions(self, queryset):
        actions = Counter()
        for method, count in self._counts(queryset, "method").items():
            actions[self._action(method)] += count
        return actions

    # CommonAudit's geo columns are bare-named (district, corporation, ...),
    # matching the Common Audit list's own ?district_id= / ?local_body_id=.
    def narrow(self, queryset, district_ids, local_body_ids):
        if district_ids:
            queryset = queryset.filter(district__in=district_ids)
        if local_body_ids:
            queryset = queryset.filter(_local_body_id_q(local_body_ids, field_name=str))
        return queryset

    def district_ids(self, queryset):
        return _distinct(queryset, "district")

    def local_body_refs(self, queryset):
        return _flat_local_body_refs(queryset, field_name=str)

    def kpis(self, queryset):
        actions = self._actions(queryset)
        # Rows from before actor capture only carry the createdBy string.
        actors = {
            actor_id or created_by
            for actor_id, created_by in queryset.order_by()
            .values_list("created_by_id", "createdBy")
            .distinct()
        }
        actors.discard(None)
        actors.discard("")
        return {
            "total": sum(actions.values()),
            "updates": actions["UPDATE"],
            "deletions": actions["DELETE"],
            "active_users": len(actors),
        }

    def breakdown(self, queryset):
        return self._slices(self._actions(queryset))

    def rows(self, records):
        rows = []
        for r in records:
            geo = geo_display(r)
            rows.append({
                "id": r.uuid,
                "date": _iso(r.createdAt),
                "user": r.created_by_name or r.createdBy,
                "module": r.module_name,
                "action": self._action(r.method),
                "record": r.object_id,
                "district": geo["district_name"],
                "local_body": geo["local_body_name"],
                "success": r.success,
            })
        return rows


class LoginTrail(_Trail):
    """LoginAudit carries no geography of its own: a login sits where the
    staff member / customer who made it sits, matched the same way the Login
    Audit list scopes it (user_unique_id, or the username tried for a failed
    attempt)."""

    model = LoginAudit
    date_field = "timestamp"
    search_fields = ("username", "ip_address", "reason")

    ACCOUNTS = (
        (Staffcreation, "staff_unique_id"),
        (CustomerCreation, "unique_id"),
    )

    @staticmethod
    def device(user_agent):
        ua = (user_agent or "").lower()
        if not ua:
            return "Unknown"
        if "android" in ua or "okhttp" in ua:
            return "Android"
        if any(token in ua for token in ("iphone", "ipad", "ios", "darwin")):
            return "iOS"
        if "dart" in ua:
            return "Mobile app"
        return "Web"

    @staticmethod
    def _of_accounts(queryset, accounts, id_field):
        return Q(user_unique_id__in=accounts.values(id_field)) | Q(
            user_unique_id__isnull=True,
            username__in=accounts.exclude(username__isnull=True).values("username"),
        )

    def _accounts_behind(self, queryset):
        """Per account model, the accounts the login rows belong to."""
        failed = queryset.filter(user_unique_id__isnull=True).order_by().values("username")
        return [
            model.objects.filter(
                Q(**{f"{id_field}__in": queryset.order_by().values("user_unique_id")})
                | Q(username__in=failed)
            )
            for model, id_field in self.ACCOUNTS
        ]

    def narrow(self, queryset, district_ids, local_body_ids):
        if not district_ids and not local_body_ids:
            return queryset
        query = Q()
        for model, id_field in self.ACCOUNTS:
            accounts = model.objects.all()
            if district_ids:
                accounts = accounts.filter(district_id__in=district_ids)
            if local_body_ids:
                accounts = accounts.filter(_local_body_id_q(local_body_ids))
            query |= self._of_accounts(queryset, accounts, id_field)
        return queryset.filter(query)

    def district_ids(self, queryset):
        ids = set()
        for accounts in self._accounts_behind(queryset):
            ids |= _distinct(accounts, "district_id")
        return ids

    def local_body_refs(self, queryset):
        refs = set()
        for accounts in self._accounts_behind(queryset):
            refs |= _flat_local_body_refs(accounts)
        return refs

    def kpis(self, queryset):
        total = queryset.count()
        succeeded = queryset.filter(success=True).count()
        return {
            "total": total,
            "success_rate": round(succeeded / total * 100) if total else None,
            "failed": total - succeeded,
            "unique_users": queryset.filter(success=True).order_by().values("username").distinct().count(),
        }

    def breakdown(self, queryset):
        return self._slices(Counter({
            ("SUCCESS" if ok else "FAILED"): count
            for ok, count in self._counts(queryset, "success").items()
        }))

    def _account_geo(self, records):
        """{user_unique_id or username: geo_display} for the rows' accounts."""
        ids = {r.user_unique_id for r in records if r.user_unique_id}
        usernames = {r.username for r in records if not r.user_unique_id and r.username}
        geo = {}
        for model, id_field in self.ACCOUNTS:
            for account in model.objects.filter(
                Q(**{f"{id_field}__in": ids}) | Q(username__in=usernames)
            ):
                display = geo_display(account)
                geo.setdefault(getattr(account, id_field), display)
                if account.username:
                    geo.setdefault(("username", account.username), display)
        return geo

    def rows(self, records):
        records = list(records)
        geo = self._account_geo(records)
        rows = []
        for r in records:
            account = (
                geo.get(r.user_unique_id) if r.user_unique_id else geo.get(("username", r.username))
            ) or {}
            rows.append({
                "id": r.unique_id,
                "date": _iso(r.timestamp),
                "user": r.username,
                "device": self.device(r.user_agent),
                "ip": r.ip_address,
                "status": "SUCCESS" if r.success else "FAILED",
                "reason": r.reason,
                "login_module": r.module_name,
                "district": account.get("district_name"),
                "local_body": account.get("local_body_name"),
            })
        return rows


class AccessTrail(_Trail):
    model = PermissionAuditLog
    date_field = "timestamp"
    search_fields = ("updated_by_id", "target_id", "source", "action_type")

    SOURCE_LABELS = dict(PermissionAuditLog.SOURCE_CHOICES)

    def narrow(self, queryset, district_ids, local_body_ids):
        if district_ids:
            # Older per-grant rows carry only the local body, so match the
            # local bodies inside the district as well as the row's own geo
            # (as the User Access Audit's own scope does).
            query = Q(district_id__in=district_ids)
            for level in LOCAL_BODY_MODELS:
                query |= Q(
                    local_body_type=level,
                    local_body_id__in=self._local_body_model(level)
                    .objects.filter(district_id__in=district_ids)
                    .values("unique_id"),
                )
            queryset = queryset.filter(query)
        if local_body_ids:
            queryset = queryset.filter(local_body_id__in=local_body_ids)
        return queryset

    @staticmethod
    def _local_body_model(level):
        module_path, class_name = LOCAL_BODY_MODELS[level].rsplit(".", 1)
        return getattr(importlib.import_module(module_path), class_name)

    def district_ids(self, queryset):
        return _distinct(queryset, "district_id")

    def local_body_refs(self, queryset):
        return {
            (level, uid)
            for level, uid in queryset.order_by()
            .exclude(local_body_id__isnull=True)
            .values_list("local_body_type", "local_body_id")
            .distinct()
            if level in LOCAL_BODY_FIELDS and uid
        }

    def kpis(self, queryset):
        actions = self._counts(queryset, "action_type")
        return {
            "total": sum(actions.values()),
            "created": actions["CREATED"],
            "updated": actions["UPDATED"],
            "deleted": actions["DELETED"],
        }

    def breakdown(self, queryset):
        return self._slices(self._counts(queryset, "source"), self.SOURCE_LABELS)

    def rows(self, records):
        records = list(records)
        # The User Access Audit list's own serializer: names, and the
        # granted/revoked counts of access-save rows.
        data = PermissionAuditLogListSerializer(records, many=True).data
        return [
            {
                "id": s["id"],
                "date": _iso(r.timestamp),
                "user": s["updated_by_name"] or s["updated_by_id"],
                # Local-body / role grants have no single recipient; the
                # serializer names the local body / role instead.
                "target": s["target_name"] or s["target_id"],
                "source": s["source"],
                "source_label": s["source_label"],
                "change": s["action_type"],
                "granted": s["granted_count"],
                "revoked": s["revoked_count"],
                "district": geo_ref_name("district", r.district_id),
                "local_body": s["local_body_name"],
            }
            for r, s in zip(records, data)
        ]


class ComplaintTrail(_Trail):
    model = ComplaintTicket
    date_field = "created"
    search_fields = ("ticket_no", "title", "profile_name", "wa_phone")

    def narrow(self, queryset, district_ids, local_body_ids):
        # The Complaint Audit list's ?district= / ?city= filters.
        if district_ids:
            queryset = queryset.filter(district_id__in=district_ids)
        if local_body_ids:
            queryset = queryset.filter(_local_body_id_q(local_body_ids))
        return queryset

    def district_ids(self, queryset):
        return _distinct(queryset, "district_id")

    def local_body_refs(self, queryset):
        return _flat_local_body_refs(queryset)

    def kpis(self, queryset):
        rows = list(queryset.values_list("created", "resolved_at", "closed_at"))
        # Matches the Complaint Audit's "completed": closed, else resolved.
        hours = [
            ((closed or resolved) - created).total_seconds() / 3600
            for created, resolved, closed in rows
            if created and (closed or resolved)
        ]
        total = len(rows)
        escalated = queryset.filter(
            unique_id__in=ComplaintEscalationHistory.objects.filter(is_deleted=False).values("ticket_id")
        ).count()
        return {
            "total": total,
            "resolved_rate": round(len(hours) / total * 100) if total else None,
            "avg_resolution_hours": round(sum(hours) / len(hours), 1) if hours else None,
            "escalated": escalated,
        }

    def breakdown(self, queryset):
        statuses = dict(ComplaintStatus.objects.values_list("unique_id", "status_code"))
        names = dict(ComplaintStatus.objects.values_list("status_code", "status_name"))
        counts = Counter()
        for status_id, count in self._counts(queryset, "status_id").items():
            counts[statuses.get(status_id)] += count
        return self._slices(counts, names)

    def rows(self, records):
        rows = []
        for s in summarize_tickets(records):
            seconds = s["total_resolution_seconds"] or s["open_seconds"]
            rows.append({
                "id": s["unique_id"],
                "date": _iso(s["created"]),
                "ticket_no": s["ticket_no"],
                "category": s["category_name"],
                "user": s["assigned_staff_name"],
                "status": s["status_code"],
                "status_label": s["status_name"],
                # Created -> resolution, or time open so far if unresolved.
                "tat_hours": round(seconds / 3600) if seconds is not None else None,
                "resolved": s["total_resolution_seconds"] is not None,
                "district": s["district_name"],
                "local_body": s["local_body_name"],
            })
        return rows


TRAILS = {
    "common": CommonTrail(),
    "login": LoginTrail(),
    "access": AccessTrail(),
    "complaint": ComplaintTrail(),
}


# ---------------------------------------------------------------------------
# Window helpers
# ---------------------------------------------------------------------------


def parse_days(value):
    try:
        days = int(value)
    except (TypeError, ValueError):
        return DEFAULT_DAYS
    return days if days in ALLOWED_DAYS else DEFAULT_DAYS


def window(days):
    """The last `days` local days including today, and the same-length
    window just before it, as aware [start, end) datetimes."""
    today = timezone.localdate()
    start_day = today - timedelta(days=days - 1)
    tz = timezone.get_current_timezone()

    def at(day):
        return timezone.make_aware(datetime.combine(day, time.min), tz)

    end = at(today + timedelta(days=1))
    start = at(start_day)
    previous_start = at(start_day - timedelta(days=days))
    return start_day, today, start, end, previous_start


def in_range(trail, queryset, start, end):
    return queryset.filter(**{f"{trail.date_field}__gte": start, f"{trail.date_field}__lt": end})


def trend(trail, queryset, start_day, end_day):
    counts = Counter(
        timezone.localtime(value).date()
        for value in queryset.order_by().values_list(trail.date_field, flat=True)
        if value
    )
    days = (end_day - start_day).days + 1
    return [
        {"date": (day := start_day + timedelta(days=i)).isoformat(), "count": counts.get(day, 0)}
        for i in range(days)
    ]


def summary(trail, scoped, days):
    """Headline numbers for the window. The table's search does not narrow
    these, so the comparison with the previous window stays like-for-like."""
    start_day, end_day, start, end, previous_start = window(days)
    current = in_range(trail, scoped, start, end)
    return {
        "date_from": start_day.isoformat(),
        "date_to": end_day.isoformat(),
        "days": days,
        "kpis": trail.kpis(current),
        "previous_total": in_range(trail, scoped, previous_start, start).count(),
        "trend": trend(trail, current, start_day, end_day),
        "breakdown": trail.breakdown(current),
    }


def geo_options(trail, scoped, district_ids=()):
    """District / local body dropdown entries drawn from the trail's scoped
    rows, so a scoped user is never offered an area outside their hierarchy.
    Local bodies narrow to `district_ids`, as on the Common Audit list."""
    local_body_source = trail.narrow(scoped, district_ids, ()) if district_ids else scoped
    by_name = lambda o: (o["name"] or "").lower()  # noqa: E731
    return {
        "districts": sorted(
            (geo_option("district", uid) for uid in trail.district_ids(scoped)), key=by_name
        ),
        "local_bodies": sorted(
            (geo_option(level, uid) for level, uid in trail.local_body_refs(local_body_source)),
            key=by_name,
        ),
    }
