from rest_framework import serializers
from django.db.models import Q
from app.models.core_modules.complaint_management.ticket import ComplaintTicket
from app.models.core_modules.complaint_management.ticket_extra_detail import ComplaintTicketExtraDetail
from app.models.core_modules.complaint_management.ticket_attachment import ComplaintAttachment
from app.models.core_modules.complaint_management.status_history import ComplaintStatusHistory
from app.models.core_modules.complaint_management.assignment_history import ComplaintAssignmentHistory
from app.models.core_modules.complaint_management.comment import ComplaintComment
from app.models.core_modules.complaint_management.routing_rule import ComplaintRoutingRule
from app.models.core_modules.complaint_management.escalation_history import ComplaintEscalationHistory
from app.models.core_modules.complaint_management.feedback import ComplaintFeedback
from app.models.core_modules.complaint_management.reopen_history import ComplaintReopenHistory
from app.models.core_modules.complaint_management.address_change_request import ComplaintAddressChangeRequest
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.superadmin.user_management.staffcreation import StaffcreationOfficeDetails


class ComplaintTicketSerializer(serializers.ModelSerializer):
    OPERATIONAL_CONTEXT_FIELDS = (
        "incident_type",
        "trip_reference",
        "driver_reference",
        "operator_reference",
        "vehicle_reference",
        "other_reference",
    )

    module = serializers.CharField(source="category.module_id", read_only=True)
    module_code = serializers.CharField(source="category.module.module_code", read_only=True)
    module_name = serializers.CharField(source="category.module.module_name", read_only=True)
    category_name = serializers.CharField(source="category.category_name", read_only=True)
    category_code = serializers.CharField(source="category.category_code", read_only=True)
    waste_type_names = serializers.SerializerMethodField()
    waste_type_name = serializers.SerializerMethodField()
    subcategory_name = serializers.CharField(source="subcategory.subcategory_name", read_only=True)
    priority_code = serializers.CharField(source="priority.priority_code", read_only=True)
    status_code = serializers.CharField(source="status.status_code", read_only=True)
    status_name = serializers.CharField(source="status.status_name", read_only=True)
    source_code = serializers.CharField(source="source.source_code", read_only=True)
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)
    reporter_type = serializers.SerializerMethodField()
    reporter_name = serializers.SerializerMethodField()
    raised_by_name = serializers.SerializerMethodField()
    assigned_team_name = serializers.CharField(source="assigned_team.team_name", read_only=True)
    assigned_staff_name = serializers.CharField(source="assigned_staff.employee_name", read_only=True)
    assigned_department_name = serializers.CharField(source="assigned_team.department.department_name", read_only=True)
    escalation_level = serializers.IntegerField(source="assigned_team.escalation_level", read_only=True)
    state_id = serializers.CharField(read_only=True)
    state_name = serializers.CharField(source="state.name", read_only=True)
    district_id = serializers.CharField(read_only=True)
    district_name = serializers.CharField(source="district.name", read_only=True)
    area_type_id = serializers.CharField(read_only=True)
    area_type_name = serializers.CharField(source="area_type.name", read_only=True)
    city_id = serializers.SerializerMethodField()
    city_name = serializers.SerializerMethodField()
    city_type = serializers.SerializerMethodField()
    sla_time_remaining_seconds = serializers.SerializerMethodField()
    public_timeline = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    close_image_url = serializers.SerializerMethodField()
    operational_context = serializers.SerializerMethodField()
    incident_type = serializers.CharField(write_only=True, required=False, allow_blank=True)
    trip_reference = serializers.CharField(write_only=True, required=False, allow_blank=True)
    driver_reference = serializers.CharField(write_only=True, required=False, allow_blank=True)
    operator_reference = serializers.CharField(write_only=True, required=False, allow_blank=True)
    vehicle_reference = serializers.CharField(write_only=True, required=False, allow_blank=True)
    other_reference = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = ComplaintTicket
        fields = "__all__"
        read_only_fields = [
            "unique_id", "ticket_no", "resolved_at", "closed_at", "reopened_count",
            "sla_breached", "sla_breached_at",
        ]

    def get_waste_type_names(self, obj):
        return [w.waste_type_name for w in obj.waste_types.all()]

    def get_reporter_type(self, obj):
        return "Customer" if obj.customer_id or self._matched_customer_name(obj) else "Public Grievance"

    def get_reporter_name(self, obj):
        return (
            getattr(obj.customer, "customer_name", "")
            or (obj.profile_name or "").strip()
            or self._matched_customer_name(obj)
            or "Anonymous"
        )

    def _matched_customer_name(self, obj):
        phone = (obj.wa_phone or "").strip()
        email = (obj.email or "").strip()
        if not phone and not email:
            return ""
        cache = getattr(self, "_customer_identity_cache", {})
        cache_key = (phone, email.lower())
        if cache_key not in cache:
            identity_filter = Q()
            if phone:
                identity_filter |= Q(contact_no=phone)
            if email:
                identity_filter |= Q(email__iexact=email)
            cache[cache_key] = (
                CustomerCreation.objects.filter(identity_filter, is_deleted=False)
                .values_list("customer_name", flat=True)
                .first()
                or ""
            )
            self._customer_identity_cache = cache
        return cache[cache_key]

    def get_raised_by_name(self, obj):
        account = getattr(obj, "created_by", None)
        user = getattr(account, "user", None)
        account_staff_name = (
            StaffcreationOfficeDetails.objects.filter(pk=account.staff_id)
            .values_list("employee_name", flat=True)
            .first()
            if account and account.staff_id
            else ""
        )
        user_staff_model = (
            user._meta.get_field("staff_id").remote_field.model
            if user and getattr(user, "staff_id_id", None)
            else None
        )
        user_staff_name = (
            user_staff_model.objects.filter(pk=user.staff_id_id)
            .values_list("employee_name", flat=True)
            .first()
            if user_staff_model
            else ""
        )
        user_customer_name = (
            CustomerCreation.objects.filter(pk=user.customer_id_id)
            .values_list("customer_name", flat=True)
            .first()
            if user and getattr(user, "customer_id_id", None)
            else ""
        )
        return (
            account_staff_name
            or user_staff_name
            or user_customer_name
            or getattr(user, "username", "")
            or self.get_reporter_name(obj)
        )

    def _pop_operational_context(self, validated_data):
        return {
            field: validated_data.pop(field, "")
            for field in self.OPERATIONAL_CONTEXT_FIELDS
            if field in validated_data
        }

    def _save_operational_context(self, ticket, values):
        for field, value in values.items():
            cleaned = str(value or "").strip()
            row = ComplaintTicketExtraDetail.objects.filter(
                ticket=ticket,
                field_key=field,
                is_deleted=False,
            ).first()
            if cleaned:
                ComplaintTicketExtraDetail.objects.update_or_create(
                    ticket=ticket,
                    field_key=field,
                    is_deleted=False,
                    defaults={
                        "field_value": cleaned,
                        "field_type": "operational_context",
                        "is_active": True,
                    },
                )
            elif row:
                row.is_deleted = True
                row.is_active = False
                row.save(update_fields=["is_deleted", "is_active"])

    def create(self, validated_data):
        context = self._pop_operational_context(validated_data)
        ticket = super().create(validated_data)
        self._save_operational_context(ticket, context)
        return ticket

    def update(self, instance, validated_data):
        context = self._pop_operational_context(validated_data)
        ticket = super().update(instance, validated_data)
        self._save_operational_context(ticket, context)
        return ticket

    def get_operational_context(self, obj):
        values = {
            row.field_key: row.field_value
            for row in obj.extra_details.all()
            if not row.is_deleted and row.field_key in self.OPERATIONAL_CONTEXT_FIELDS
        }
        incident_type = (values.get("incident_type") or "").strip().lower()
        if not incident_type:
            source_code = (getattr(obj.source, "source_code", "") or "").lower()
            searchable = " ".join(
                str(value or "").lower()
                for value in (
                    obj.title,
                    obj.description,
                    getattr(obj.category, "category_name", ""),
                    getattr(obj.subcategory, "subcategory_name", ""),
                    getattr(getattr(obj.category, "module", None), "module_name", ""),
                )
            )
            if source_code == "public_grievance":
                incident_type = "public"
            else:
                incident_type = next(
                    (
                        kind
                        for kind in ("driver", "operator", "vehicle", "trip")
                        if kind in searchable
                    ),
                    "other",
                )
        return {
            "incident_type": incident_type,
            "trip_reference": values.get("trip_reference") or "",
            "driver_reference": values.get("driver_reference") or "",
            "operator_reference": values.get("operator_reference") or "",
            "vehicle_reference": values.get("vehicle_reference") or "",
            "other_reference": values.get("other_reference") or "",
        }

    def get_waste_type_name(self, obj):
        """Comma-joined display string - kept for table/kanban columns that show one text value."""
        names = self.get_waste_type_names(obj)
        return ", ".join(names) if names else None

    def get_city_id(self, obj):
        _, body, _ = obj.local_body
        return body.unique_id if body else None

    def get_city_name(self, obj):
        _, _, name = obj.local_body
        return name

    def get_city_type(self, obj):
        field, _, _ = obj.local_body
        return field

    def _active_attachments(self, obj):
        """Attachments ordered newest-first (model default ordering)."""
        return [a for a in obj.attachments.all() if not a.is_deleted]

    def get_image_url(self, obj):
        """URL of the original complaint photo (oldest attachment)."""
        request = self.context.get("request")
        attachments = self._active_attachments(obj)
        if not attachments or not request:
            return None
        oldest = attachments[-1]
        return request.build_absolute_uri(oldest.file.url) if oldest.file else None

    def get_close_image_url(self, obj):
        """URL of the resolution/closing photo (most recent attachment, if a later one was added)."""
        request = self.context.get("request")
        attachments = self._active_attachments(obj)
        if len(attachments) < 2 or not request:
            return None
        newest = attachments[0]
        return request.build_absolute_uri(newest.file.url) if newest.file else None

    def get_sla_time_remaining_seconds(self, obj):
        """Seconds until sla_due_at (negative once overdue); None if resolved/closed or no due date."""
        if not obj.sla_due_at or obj.resolved_at or obj.closed_at:
            return None
        from django.utils import timezone
        return int((obj.sla_due_at - timezone.now()).total_seconds())

    def get_public_timeline(self, obj):
        """Citizen-safe, chronological status timeline (visible_to_citizen only)."""
        rows = [
            h for h in obj.status_history.all()
            if h.visible_to_citizen and not h.is_deleted
        ]
        rows.sort(key=lambda h: h.changed_at)
        return [
            {
                "status_code": h.to_status.status_code if h.to_status_id else None,
                "status_name": h.to_status.status_name if h.to_status_id else None,
                "at": h.changed_at,
                "remarks": h.remarks,
            }
            for h in rows
        ]


class ComplaintTicketExtraDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintTicketExtraDetail
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintAttachmentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ComplaintAttachment
        fields = "__all__"
        read_only_fields = ["unique_id"]

    def get_file_url(self, obj):
        request = self.context.get("request")
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None


class ComplaintStatusHistorySerializer(serializers.ModelSerializer):
    from_status_code = serializers.CharField(source="from_status.status_code", read_only=True)
    to_status_code = serializers.CharField(source="to_status.status_code", read_only=True)
    to_status_name = serializers.CharField(source="to_status.status_name", read_only=True)

    class Meta:
        model = ComplaintStatusHistory
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintAssignmentHistorySerializer(serializers.ModelSerializer):
    to_team_name = serializers.CharField(source="to_team.team_name", read_only=True)
    from_team_name = serializers.CharField(source="from_team.team_name", read_only=True)
    to_staff_name = serializers.CharField(source="to_staff.employee_name", read_only=True)
    from_staff_name = serializers.CharField(source="from_staff.employee_name", read_only=True)

    class Meta:
        model = ComplaintAssignmentHistory
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintCommentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintComment
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintRoutingRuleSerializer(serializers.ModelSerializer):
    category_code = serializers.CharField(source="category.category_code", read_only=True)
    team_name = serializers.CharField(source="team.team_name", read_only=True)

    class Meta:
        model = ComplaintRoutingRule
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintEscalationHistorySerializer(serializers.ModelSerializer):
    escalated_from_team_name = serializers.CharField(source="escalated_from_team.team_name", read_only=True)
    escalated_to_team_name = serializers.CharField(source="escalated_to_team.team_name", read_only=True)
    escalated_to_staff_name = serializers.CharField(source="escalated_to_staff.employee_name", read_only=True)

    class Meta:
        model = ComplaintEscalationHistory
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintTicketDetailSerializer(ComplaintTicketSerializer):
    """Ticket retrieve view with the full audit trail nested (for the admin screen)."""
    status_history = ComplaintStatusHistorySerializer(many=True, read_only=True)
    escalation_history = ComplaintEscalationHistorySerializer(many=True, read_only=True)
    assignment_history = ComplaintAssignmentHistorySerializer(many=True, read_only=True)
    comments = ComplaintCommentSerializer(many=True, read_only=True)
    attachments = ComplaintAttachmentSerializer(many=True, read_only=True)

    class Meta(ComplaintTicketSerializer.Meta):
        pass


class ComplaintFeedbackSerializer(serializers.ModelSerializer):
    ticket_no = serializers.CharField(source="ticket.ticket_no", read_only=True)
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)

    class Meta:
        model = ComplaintFeedback
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintReopenHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintReopenHistory
        fields = "__all__"
        read_only_fields = ["unique_id"]


class ComplaintAddressChangeRequestSerializer(serializers.ModelSerializer):
    ticket_no = serializers.CharField(source="ticket.ticket_no", read_only=True)
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)
    proof_file_url = serializers.SerializerMethodField()

    class Meta:
        model = ComplaintAddressChangeRequest
        fields = "__all__"
        read_only_fields = [
            "unique_id",
            "verification_status",
            "verified_by",
            "verified_at",
            "approved_by",
            "approved_at",
        ]

    def get_proof_file_url(self, obj):
        request = self.context.get("request")
        if obj.proof_file and request:
            return request.build_absolute_uri(obj.proof_file.url)
        return None
