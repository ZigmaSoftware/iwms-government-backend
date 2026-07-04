from rest_framework import serializers
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
    public_timeline = serializers.SerializerMethodField()

    class Meta:
        model = ComplaintTicket
        fields = "__all__"
        read_only_fields = ["unique_id", "ticket_no", "resolved_at", "closed_at", "reopened_count"]

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
