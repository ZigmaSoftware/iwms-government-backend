from rest_framework import serializers


class TenancyReadSerializerMixin(serializers.Serializer):
    """Expose tenancy context consistently in responses.

    We keep these as read-only fields to avoid clients spoofing tenant ownership.
    """

    company_id = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    project_id = serializers.SerializerMethodField()
    project_name = serializers.SerializerMethodField()

    def get_company_id(self, obj):
        company = getattr(obj, "company_id", None)
        return getattr(company, "unique_id", None)

    def get_company_name(self, obj):
        company = getattr(obj, "company_id", None)
        return getattr(company, "name", None)

    def get_project_id(self, obj):
        project = getattr(obj, "project_id", None)
        return getattr(project, "unique_id", None)

    def get_project_name(self, obj):
        project = getattr(obj, "project_id", None)
        return getattr(project, "name", None)

