from rest_framework.viewsets import ViewSet
from rest_framework.response import Response
# from attendance.models import Employee
from app.models.user_creations.attendance import Employee
import os

class EmployeeViewSet(ViewSet):

    def list(self, request):
        employees = Employee.objects.all().values()
        return Response(list(employees))

    def retrieve(self, request, pk=None):
        employee = Employee.objects.filter(emp_id=pk).values().first()
        if not employee:
            return Response({"error": "Employee not found"}, status=404)

        return Response(employee)