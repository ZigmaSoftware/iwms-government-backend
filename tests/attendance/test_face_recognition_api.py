"""End-to-end attendance face tests against the real HTTP endpoints."""
import glob
import io

import pytest
from django.test import override_settings
from PIL import Image

from app.services import face_recognition as fr


def _reg_photos():
    return sorted(glob.glob("media/attendance/registration/EMP-000008_*.jpg"))


def _bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def _upload(raw, name="face.jpg"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(name, raw, content_type="image/jpeg")


def _variant(raw):
    """A re-encoded copy of the same photo — stands in for 'same person,
    different capture' without needing a second real photo of them."""
    im = Image.open(io.BytesIO(raw)).convert("RGB")
    im = im.resize((int(im.width * 0.8), int(im.height * 0.8)))
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=70)
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _clear_provider_cache():
    fr.reset_provider_cache()
    yield
    fr.reset_provider_cache()


@pytest.fixture
def staff(db):
    from app.models.superadmin.staff_management.staffcreation import Staffcreation

    return Staffcreation.objects.create(
        employee_name="Face Test User",
        staff_unique_id="ST-FACETEST-1",
    )


@override_settings(FACE_RECOGNITION_PROVIDER="insightface")
def test_face_config_reports_active_provider(db, api_client):
    res = api_client.get("/api/v1/attendance/face-config/")
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["provider"] == "insightface"
    assert "compreface" in body["available_providers"]
    assert body["ready"] is True


@override_settings(FACE_RECOGNITION_PROVIDER="compreface")
def test_face_config_switches_with_the_setting(db, api_client):
    body = api_client.get("/api/v1/attendance/face-config/").json()
    assert body["provider"] == "compreface"
    # Each provider carries its own scale — this is the value the old
    # hardcoded 0.95 check used.
    assert body["threshold"] == 0.95


@override_settings(FACE_RECOGNITION_PROVIDER="insightface")
def test_register_then_recognize_same_person_marks_attendance(staff, auth_client):
    photos = _reg_photos()

    res = auth_client.post(
        "/api/v1/attendance/register/",
        {"emp_id": staff.staff_unique_id,
         "source_image": _upload(_bytes(photos[0]))},
        format="multipart",
    )
    assert res.status_code == 200, res.content
    assert res.json()["provider"] == "insightface"

    staff.refresh_from_db()
    # The embedding must be cached at registration so a punch only has to
    # process the incoming selfie.
    assert staff.face_embedding and len(staff.face_embedding) == 512

    res = auth_client.post(
        "/api/v1/attendance/recognize/",
        {"emp_id": staff.staff_unique_id, "name": staff.employee_name,
         "latitude": "12.9", "longitude": "77.6",
         "captured_image": _upload(_variant(_bytes(photos[0])))},
        format="multipart",
    )
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["punch_type"] == "IN"
    assert body["score"] > body["threshold"]


@override_settings(FACE_RECOGNITION_PROVIDER="insightface")
def test_recognize_rejects_a_different_person(staff, auth_client):
    photos = _reg_photos()
    auth_client.post(
        "/api/v1/attendance/register/",
        {"emp_id": staff.staff_unique_id,
         "source_image": _upload(_bytes(photos[0]))},
        format="multipart",
    )
    # photos[4] is a visibly different person from photos[0] in the fixture data.
    res = auth_client.post(
        "/api/v1/attendance/recognize/",
        {"emp_id": staff.staff_unique_id, "name": staff.employee_name,
         "latitude": "12.9", "longitude": "77.6",
         "captured_image": _upload(_bytes(photos[4]))},
        format="multipart",
    )
    assert res.status_code == 400, res.content
    assert res.json()["error"] == "Face Similarity Not Matched"


@override_settings(FACE_RECOGNITION_PROVIDER="insightface")
def test_second_punch_toggles_to_out(staff, auth_client):
    photos = _reg_photos()
    auth_client.post("/api/v1/attendance/register/",
                {"emp_id": staff.staff_unique_id,
                 "source_image": io.BytesIO(_bytes(photos[0]))})
    punch = lambda: auth_client.post(
        "/api/v1/attendance/recognize/",
        {"emp_id": staff.staff_unique_id, "name": staff.employee_name,
         "latitude": "12.9", "longitude": "77.6",
         "captured_image": _upload(_variant(_bytes(photos[0])))},
        format="multipart",
    )
    assert punch().json()["punch_type"] == "IN"
    assert punch().json()["punch_type"] == "OUT"


@override_settings(FACE_RECOGNITION_PROVIDER="insightface")
def test_register_rejects_an_image_with_no_face(staff, api_client):
    blank = io.BytesIO()
    Image.new("RGB", (400, 400), "white").save(blank, "JPEG")
    res = api_client.post(
        "/api/v1/attendance/register/",
        {"emp_id": staff.staff_unique_id, "source_image": _upload(blank.getvalue())},
        format="multipart",
    )
    assert res.status_code == 400
    assert "No face detected" in res.json()["error"]
    staff.refresh_from_db()
    # A rejected photo must not become the reference image.
    assert not staff.attendance_reg_image


@override_settings(FACE_RECOGNITION_PROVIDER="insightface")
def test_punch_backfills_embedding_for_staff_enrolled_under_compreface(staff, auth_client):
    """Staff registered while CompreFace was active have a reference image but
    no embedding; the first punch must derive and cache one rather than fail."""
    photos = _reg_photos()
    auth_client.post("/api/v1/attendance/register/",
                {"emp_id": staff.staff_unique_id,
                 "source_image": io.BytesIO(_bytes(photos[0]))})

    staff.refresh_from_db()
    staff.face_embedding = None  # simulate the pre-InsightFace state
    staff.save(update_fields=["face_embedding"])

    res = auth_client.post(
        "/api/v1/attendance/recognize/",
        {"emp_id": staff.staff_unique_id, "name": staff.employee_name,
         "latitude": "12.9", "longitude": "77.6",
         "captured_image": _upload(_variant(_bytes(photos[0])))},
        format="multipart",
    )
    assert res.status_code == 200, res.content
    staff.refresh_from_db()
    assert staff.face_embedding and len(staff.face_embedding) == 512


# ---------------------------------------------------------------------------
# CompreFace path
#
# The hosted API is not reachable from tests, so its HTTP call is stubbed and
# what is asserted is that the *wiring* is intact: the provider is selected,
# it posts both images to the configured URL with the API key, applies its own
# 0.95 cutoff, and stores no embedding. This is the regression guard for
# "InsightFace work broke the CompreFace option".
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


@override_settings(FACE_RECOGNITION_PROVIDER="compreface")
def test_compreface_register_and_punch_still_work(staff, auth_client, monkeypatch):
    import app.services.face_recognition.compre_face as cf

    calls = []

    def fake_post(url, headers=None, files=None, timeout=None):
        calls.append({"url": url, "headers": headers, "files": sorted(files)})
        return _FakeResponse(
            {"result": [{"source_image_face": {},
                         "face_matches": [{"similarity": 0.97}]}]}
        )

    monkeypatch.setattr(cf.requests, "post", fake_post)

    photos = _reg_photos()
    res = auth_client.post(
        "/api/v1/attendance/register/",
        {"emp_id": staff.staff_unique_id, "source_image": _upload(_bytes(photos[0]))},
        format="multipart",
    )
    assert res.status_code == 200, res.content
    assert res.json()["provider"] == "compreface"

    staff.refresh_from_db()
    # CompreFace compares image files on its own server, so nothing is cached.
    assert staff.face_embedding is None

    res = auth_client.post(
        "/api/v1/attendance/recognize/",
        {"emp_id": staff.staff_unique_id, "name": staff.employee_name,
         "latitude": "12.9", "longitude": "77.6",
         "captured_image": _upload(_bytes(photos[0]))},
        format="multipart",
    )
    assert res.status_code == 200, res.content
    body = res.json()
    assert body["provider"] == "compreface"
    assert body["score"] == 0.97
    assert body["threshold"] == 0.95

    assert calls, "CompreFace was never called"
    assert calls[0]["url"].endswith("/api/v1/verification/verify")
    assert calls[0]["headers"]["x-api-key"]
    assert calls[0]["files"] == ["source_image", "target_image"]


@override_settings(FACE_RECOGNITION_PROVIDER="compreface")
def test_compreface_below_threshold_is_rejected(staff, auth_client, monkeypatch):
    import app.services.face_recognition.compre_face as cf

    monkeypatch.setattr(
        cf.requests, "post",
        lambda *a, **k: _FakeResponse(
            {"result": [{"source_image_face": {},
                         "face_matches": [{"similarity": 0.80}]}]}
        ),
    )

    photos = _reg_photos()
    auth_client.post(
        "/api/v1/attendance/register/",
        {"emp_id": staff.staff_unique_id, "source_image": _upload(_bytes(photos[0]))},
        format="multipart",
    )
    res = auth_client.post(
        "/api/v1/attendance/recognize/",
        {"emp_id": staff.staff_unique_id, "name": staff.employee_name,
         "latitude": "12.9", "longitude": "77.6",
         "captured_image": _upload(_bytes(photos[0]))},
        format="multipart",
    )
    assert res.status_code == 400
    assert res.json()["error"] == "Face Similarity Not Matched"


@override_settings(FACE_RECOGNITION_PROVIDER="compreface")
def test_compreface_outage_is_503_not_a_rejected_face(staff, auth_client, monkeypatch):
    """A dead face API must not read as 'your face did not match'."""
    import app.services.face_recognition.compre_face as cf

    def boom(*a, **k):
        raise cf.requests.RequestException("connection refused")

    monkeypatch.setattr(cf.requests, "post", boom)

    res = auth_client.post(
        "/api/v1/attendance/register/",
        {"emp_id": staff.staff_unique_id, "source_image": _upload(_bytes(_reg_photos()[0]))},
        format="multipart",
    )
    assert res.status_code == 503, res.content
