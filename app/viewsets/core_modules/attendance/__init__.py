from .attendance_records_viewset import AttendanceRecordsViewSet
from .daily_attendance_viewset import DailyAttendanceRegViewSet
from .face_config_viewset import FaceConfigViewSet
from .recognize_viewset import RecognizeViewSet
from .register_viewset import RegisterViewSet
from .staff_profile_viewset import StaffProfileViewSet

__all__ = [
    "AttendanceRecordsViewSet",
    "DailyAttendanceRegViewSet",
    "FaceConfigViewSet",
    "RecognizeViewSet",
    "RegisterViewSet",
    "StaffProfileViewSet",
]
