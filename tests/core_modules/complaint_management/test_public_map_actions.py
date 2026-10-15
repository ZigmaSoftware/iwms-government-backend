"""Anonymous actions on a public complaint-map pin — "I saw this too" and
"Verify Cleanup" — and the handler's review of a cleanup report
(app/utils/public_grievance_map.py, app/services/complaint_cleanup.py)."""
import io

import pytest
from django.core.cache import caches
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from app.models.core_modules.complaint_management.category_master import ComplaintCategory
from app.models.core_modules.complaint_management.cleanup_report import ComplaintCleanupReport
from app.models.core_modules.complaint_management.comment import ComplaintComment
from app.models.core_modules.complaint_management.notification import ComplaintNotification
from app.models.core_modules.complaint_management.priority_master import ComplaintPriority
from app.models.core_modules.complaint_management.status_master import ComplaintStatus
from app.models.core_modules.complaint_management.ticket import ComplaintTicket
from app.models.core_modules.complaint_management.ticket_attachment import ComplaintAttachment
from app.models.superadmin.staff_management.staffcreation import Staffcreation, StaffcreationOfficeDetails
from app.services import complaint_cleanup
from app.services.complaint_cleanup import CLEANUP_PROOF

BASE = "/api/v1/publicgrievance/map-ticket"


@pytest.fixture(autouse=True)
def _isolate(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    caches["app_cache"].clear()
    caches["default"].clear()  # throttle history
    yield
    caches["app_cache"].clear()


@pytest.fixture
def ticket(db):
    priority = ComplaintPriority.objects.create(priority_code="P2", priority_name="High")
    category = ComplaintCategory.objects.create(category_code="GARBAGE", category_name="Garbage")
    ComplaintStatus.objects.create(status_code="CLOSED", status_name="Closed", is_final=True)
    submitted = ComplaintStatus.objects.create(status_code="SUBMITTED", status_name="Submitted")
    officer = Staffcreation.objects.create(username="officer", employee_name="officer", active_status=True)
    return ComplaintTicket.objects.create(
        category_id=category.unique_id,
        priority_id=priority.unique_id,
        status_id=submitted.unique_id,
        assigned_staff_id=officer.staff_unique_id,
        title="Garbage heap",
    )


def _image(name="clean.png"):
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "green").save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@pytest.mark.django_db
class TestSeen:
    def test_counts_up(self, ticket):
        client = APIClient()
        assert client.post(f"{BASE}/{ticket.ticket_no}/seen/").json() == {"seen_count": 1}
        assert client.post(f"{BASE}/{ticket.ticket_no}/seen/").json() == {"seen_count": 2}

    def test_sensitive_ticket_is_not_found(self, ticket):
        ComplaintTicket.objects.filter(pk=ticket.pk).update(is_sensitive=True)
        assert APIClient().post(f"{BASE}/{ticket.ticket_no}/seen/").status_code == 404


@pytest.mark.django_db
class TestVerifyCleanup:
    def test_second_report_waits_for_the_first(self, ticket):
        client = APIClient()
        assert client.post(f"{BASE}/{ticket.ticket_no}/verify-cleanup/", {"photo": _image()}, format="multipart").status_code == 201
        assert client.post(f"{BASE}/{ticket.ticket_no}/verify-cleanup/", {"photo": _image()}, format="multipart").status_code == 409

    def test_stores_photo_notes_and_notifies_handler(self, ticket):
        response = APIClient().post(
            f"{BASE}/{ticket.ticket_no}/verify-cleanup/", {"photo": _image(), "note": "All clear now"}, format="multipart"
        )
        assert response.status_code == 201, response.content
        proof = ComplaintAttachment.objects.get(ticket_id=ticket.unique_id)
        assert proof.file_type == CLEANUP_PROOF
        report = ComplaintCleanupReport.objects.get(ticket_id=ticket.unique_id)
        assert report.status == ComplaintCleanupReport.STATUS_PENDING
        assert report.attachment_id == proof.unique_id
        assert "All clear now" in ComplaintComment.objects.get(ticket_id=ticket.unique_id).comment_text
        assert ComplaintNotification.objects.filter(
            ticket_id=ticket.unique_id,
            event_type=ComplaintNotification.EVENT_CLEANUP_REPORTED,
            recipient_staff_id=ticket.assigned_staff_id,
        ).exists()
        # status is left to staff
        ticket.refresh_from_db()
        assert ticket.status.status_code == "SUBMITTED"

    def test_photo_required(self, ticket):
        response = APIClient().post(f"{BASE}/{ticket.ticket_no}/verify-cleanup/", {"note": "done"}, format="multipart")
        assert response.status_code == 400

    def test_rejects_non_images(self, ticket):
        doc = SimpleUploadedFile("x.pdf", b"%PDF-1.4", content_type="application/pdf")
        response = APIClient().post(f"{BASE}/{ticket.ticket_no}/verify-cleanup/", {"photo": doc}, format="multipart")
        assert response.status_code == 400

    def test_closed_ticket_rejected(self, ticket):
        ComplaintTicket.objects.filter(pk=ticket.pk).update(
            status_id=ComplaintStatus.objects.get(status_code="CLOSED").unique_id
        )
        response = APIClient().post(f"{BASE}/{ticket.ticket_no}/verify-cleanup/", {"photo": _image()}, format="multipart")
        assert response.status_code == 400


def _submit(ticket):
    return complaint_cleanup.submit(ticket, _image(), "done")


def _handler(ticket):
    return StaffcreationOfficeDetails.objects.get(staff_unique_id=ticket.assigned_staff_id)


@pytest.mark.django_db
class TestReview:
    def test_only_current_handler_may_review(self, ticket):
        other = Staffcreation.objects.create(username="other", employee_name="other", active_status=True)
        assert complaint_cleanup.can_review(ticket, _handler(ticket))
        assert not complaint_cleanup.can_review(
            ticket, StaffcreationOfficeDetails.objects.get(staff_unique_id=other.staff_unique_id)
        )

    def test_approve_closes_ticket(self, ticket):
        report = _submit(ticket)
        complaint_cleanup.approve(ticket, report, _handler(ticket), "Checked on site")
        ticket.refresh_from_db()
        report.refresh_from_db()
        assert ticket.status.status_code == "CLOSED"
        assert ticket.closed_at is not None
        assert ticket.next_escalation_due_at is None
        assert report.status == ComplaintCleanupReport.STATUS_APPROVED
        assert report.reviewed_by_staff_id == ticket.assigned_staff_id
        assert complaint_cleanup.pending_report(ticket) is None

    def test_reject_keeps_ticket_open_and_allows_a_new_report(self, ticket):
        report = _submit(ticket)
        complaint_cleanup.reject(ticket, report, _handler(ticket), "Still garbage there")
        ticket.refresh_from_db()
        assert ticket.status.status_code == "SUBMITTED"
        assert complaint_cleanup.pending_report(ticket) is None
        assert _submit(ticket).status == ComplaintCleanupReport.STATUS_PENDING

    def test_report_reviewed_once(self, ticket):
        report = _submit(ticket)
        complaint_cleanup.reject(ticket, report, _handler(ticket), "Not clean")
        with pytest.raises(complaint_cleanup.CleanupError):
            complaint_cleanup.approve(ticket, report, _handler(ticket), "Clean now")

    @pytest.mark.parametrize("decision", ["approve", "reject"])
    def test_remarks_required(self, ticket, decision):
        report = _submit(ticket)
        with pytest.raises(complaint_cleanup.CleanupError):
            getattr(complaint_cleanup, decision)(ticket, report, _handler(ticket), "   ")
        report.refresh_from_db()
        assert report.status == ComplaintCleanupReport.STATUS_PENDING


@pytest.mark.django_db
@pytest.mark.parametrize("review", [complaint_cleanup.approve, complaint_cleanup.reject])
def test_cleanup_review_requires_remarks(ticket, review):
    report = _submit(ticket)
    with pytest.raises(complaint_cleanup.CleanupError):
        review(ticket, report, _handler(ticket), "   ")
    report.refresh_from_db()
    assert report.status == ComplaintCleanupReport.STATUS_PENDING


@pytest.mark.django_db
def test_cleanup_approval_shows_in_complaint_audit(ticket):
    from app.services.complaint_audit import summarize_tickets, ticket_photos

    report = _submit(ticket)
    complaint_cleanup.approve(ticket, report, _handler(ticket), "Checked on site")
    ticket.refresh_from_db()

    row = summarize_tickets([ticket])[0]
    assert "Checked on site" in row["resolution_remarks"]
    assert row["first_resolution_seconds"] is not None

    photos = ticket_photos(ticket)
    cleanup = [p for p in photos if p["kind"] == "cleanup"]
    assert len(cleanup) == 1
    assert cleanup[0]["cleanup_status"] == ComplaintCleanupReport.STATUS_APPROVED
    assert cleanup[0]["review_remarks"] == "Checked on site"
