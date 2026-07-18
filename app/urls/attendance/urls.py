from rest_framework.routers import DefaultRouter

from app.viewsets.attendance import (
    AttendanceRecordsViewSet,
    DailyAttendanceRegViewSet,
    RecognizeViewSet,
    RegisterViewSet,
    StaffProfileViewSet,
)


router = DefaultRouter()
router.register("register", RegisterViewSet, basename="attendance-register")
router.register("recognize", RecognizeViewSet, basename="attendance-recognize")
router.register(
    "daily-attendance",
    DailyAttendanceRegViewSet,
    basename="daily-attendance-reg",
)
router.register("records", AttendanceRecordsViewSet, basename="attendance-records")
router.register("staff-profile", StaffProfileViewSet, basename="attendance-staff-profile")

urlpatterns = router.urls
