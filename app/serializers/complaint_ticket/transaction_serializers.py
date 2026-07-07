from rest_framework import serializers
from app.utils.hierarchy import district_and_city_for_node
from app.models.complaint_ticket.ticket import ComplaintTicket
from app.models.complaint_ticket.ticket_extra_detail import ComplaintTicketExtraDetail
from app.models.complaint_ticket.ticket_attachment import ComplaintAttachment
from app.models.complaint_ticket.status_history import ComplaintStatusHistory
from app.models.complaint_ticket.assignment_history import ComplaintAssignmentHistory
from app.models.complaint_ticket.comment import ComplaintComment
from app.models.complaint_ticket.routing_rule import ComplaintRoutingRule
from app.models.complaint_ticket.escalation_history import ComplaintEscalationHistory
from app.models.complaint_ticket.feedback import ComplaintFeedback
from app.models.complaint_ticket.reopen_history import ComplaintReopenHistory
from app.models.complaint_ticket.address_change_request import ComplaintAddressChangeRequest


class ComplaintTicketSerializer(serializers.ModelSerializer):
    module = serializers.CharField(source="category.module_id", read_only=True)
    module_code = serializers.CharField(source="category.module.module_code", read_only=True)
    module_name = serializers.CharField(source="category.module.module_name", read_only=True)
    category_name = serializers.CharField(source="category.category_name", read_only=True)
    category_code = serializers.CharField(source="category.category_code", read_only=True)
    subcategory_name = serializers.CharField(source="subcategory.subcategory_name", read_only=True)
    priority_code = serializers.CharField(source="priority.priority_code", read_only=True)
    status_code = serializers.CharField(source="status.status_code", read_only=True)
    status_name = serializers.CharField(source="status.status_name", read_only=True)
    source_code = serializers.CharField(source="source.source_code", read_only=True)
    customer_name = serializers.CharField(source="customer.customer_name", read_only=True)
    assigned_team_name = serializers.CharField(source="assigned_team.team_name", read_only=True)
    assigned_staff_name = serializers.CharField(source="assigned_staff.employee_name", read_only=True)
    assigned_department_name = serializers.CharField(source="assigned_team.department.department_name", read_only=True)
    escalation_level = serializers.IntegerField(source="assigned_team.escalation_level", read_only=True)
    location_node_name = serializers.CharField(source="location_node.name", read_only=True)
    district_id = serializers.SerializerMethodField()
    district_name = serializers.SerializerMethodField()
    city_id = serializers.SerializerMethodField()
    city_name = serializers.SerializerMethodField()
    sla_time_remaining_seconds = serializers.SerializerMethodField()
    public_timeline = serializers.SerializerMethodField()
    image_url = serializers.SerializerMethodField()
    close_image_url = serializers.SerializerMethodField()

    class Meta:
        model = ComplaintTicket
        fields = "__all__"
        read_only_fields = [
            "unique_id", "ticket_no", "resolved_at", "closed_at", "reopened_count",
            "sla_breached", "sla_breached_at",
        ]

    def _geo(self, obj):
        cache = self.context.setdefault("_geo_cache", {})
        return district_and_city_for_node(obj.location_node_id, cache)

    def get_district_id(self, obj):
        return self._geo(obj)["district_id"]

    def get_district_name(self, obj):
        return self._geo(obj)["district_name"]

    def get_city_id(self, obj):
        return self._geo(obj)["city_id"]

    def get_city_name(self, obj):
        return self._geo(obj)["city_name"]

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
