from rest_framework.routers import DefaultRouter

from app.viewsets.core_modules.attendance import (
    AttendanceRecordsViewSet,
    DailyAttendanceRegViewSet,
    FaceConfigViewSet,
    RecognizeViewSet,
    RegisterViewSet,
    StaffProfileViewSet,
)


router = DefaultRouter()
router.register("register", RegisterViewSet, basename="attendance-register")
# Lets the app read the active face provider + capture rules, so switching
# FACE_RECOGNITION_PROVIDER in .env needs no mobile release.
router.register("face-config", FaceConfigViewSet, basename="attendance-face-config")
router.register("recognize", RecognizeViewSet, basename="attendance-recognize")
router.register(
    "daily-attendance",
    DailyAttendanceRegViewSet,
    basename="daily-attendance-reg",
)
router.register("records", AttendanceRecordsViewSet, basename="attendance-records")
router.register("staff-profile", StaffProfileViewSet, basename="attendance-staff-profile")

urlpatterns = router.urls
