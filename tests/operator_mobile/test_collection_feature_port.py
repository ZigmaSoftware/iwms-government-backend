"""Government collection flow integration tests, isolated from the local MySQL DB."""
from datetime import timedelta
from io import BytesIO
from unittest.mock import patch

import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from app.models.core_modules.daily_operations.daily_trip_assignment import DailyTripAssignment
from app.models.core_modules.daily_operations.daily_trip_household_collection import DailyTripHouseholdCollection
from app.models.core_modules.daily_operations.trip_retrip_request import TripRetripRequest
from app.models.core_modules.daily_operations.trip_delay_report import TripDelayReport
from app.models.core_modules.schedule_setup.trip_plan import TripPlan
from app.models.core_modules.schedule_setup.staff_template import StaffTemplate
from app.models.masters.transport_masters.vehicleCreation import VehicleCreation
from app.models.masters.customer_masters.customercreation import CustomerCreation
from app.models.superadmin.staff_management.staffcreation import Staffcreation
from app.models.superadmin.role_management.governmentStaffUserType import GovernmentStaffUserType
from app.viewsets.core_modules.daily_operations.daily_trip_assignment_viewset import DailyTripAssignmentViewSet
from app.viewsets.core_modules.daily_operations.trip_delay_report_viewset import TripDelayReportViewSet
from app.viewsets.core_modules.complaint_management.citizen_pickup_viewset import CitizenPickupViewSet
from app.viewsets.waste_collection_bluetooth.waste_bluetooth_viewset import WasteCollectionBluetoothViewSet

pytestmark = pytest.mark.django_db


def call(viewset, action, user, data=None, uid=None, method='post', query=''):
    factory = APIRequestFactory()
    request = getattr(factory, method)('/'+query, data=data or {}, format='multipart' if data and 'evidence_image' in data else 'json')
    force_authenticate(request, user=user)
    return viewset.as_view({method: action})(request, **({'unique_id': uid} if uid else {}))


def image():
    stream = BytesIO()
    Image.new('RGB', (8, 8), 'green').save(stream, 'JPEG')
    return SimpleUploadedFile('proof.jpg', stream.getvalue(), content_type='image/jpeg')


@pytest.fixture
def graph(settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    supervisor_role = GovernmentStaffUserType.objects.create(name='govt_corporation_supervisor')
    driver_role = GovernmentStaffUserType.objects.create(name='govt_corporation_driver')
    supervisor = Staffcreation.objects.create(employee_name='Supervisor', governmentusertype_id=supervisor_role.unique_id)
    driver = Staffcreation.objects.create(employee_name='Driver', governmentusertype_id=driver_role.unique_id)
    other = Staffcreation.objects.create(employee_name='Other', governmentusertype_id=supervisor_role.unique_id)
    template = StaffTemplate.objects.create(display_code='PORT-TEAM', driver_id=driver.staff_unique_id, operator_id=driver.staff_unique_id)
    vehicle = VehicleCreation.objects.create(vehicle_no='TN-PORT-01')
    plan = TripPlan.objects.create(display_code='PORT-PLAN', supervisor_id=supervisor.staff_unique_id,
        staff_template_id=template.unique_id, vehicle_id=vehicle.unique_id, scheduled_time='06:30',
        collection_type=TripPlan.COLLECTION_TYPE_HOUSEHOLD, repeat_days=list(range(7)),
        is_auto_assign=True, status=TripPlan.Status.ACTIVE, approval_status=TripPlan.ApprovalStatus.APPROVED)
    assignment = DailyTripAssignment.objects.create(trip_plan_id=plan.unique_id, trip_date=timezone.localdate())
    customer = CustomerCreation.objects.create(customer_name='Citizen', contact_no='9000000001')
    stop = DailyTripHouseholdCollection.objects.create(trip_assignment_id=assignment.unique_id, customer_id=customer.unique_id)
    return supervisor, driver, other, plan, assignment, customer, stop


def test_real_government_driver_role_and_trip_payload(graph):
    from app.permissions.operator_permission import IsOperatorRole
    from app.serializers.operator_mobile.trip_today_serializer import MyTripTodaySerializer
    from app.serializers.core_modules.daily_operations.daily_trip_assignment_serializer import DailyTripAssignmentSerializer
    supervisor, driver, _, plan, assignment, customer, stop = graph
    assert IsOperatorRole().has_permission(type('Request', (), {'user': driver})(), None)
    payload = MyTripTodaySerializer(assignment).data
    assert payload['vehicle']['vehicle_no'] == 'TN-PORT-01'
    assert payload['crew']['driver']['unique_id'] == driver.staff_unique_id
    assert payload['household_collections'][0]['customer']['unique_id'] == customer.unique_id
    payload = DailyTripAssignmentSerializer(assignment).data
    assert {'trip_events', 'service_notice', 'trip_log_summary', 'actual_start_at'} <= payload.keys()
    assert payload['trip_plan_id'] == plan.unique_id
    assert payload['household_collection_points'][0]['customer_available_at'] is None


def test_plan_options_and_generate_are_owned_and_idempotent(graph):
    supervisor, _, other, plan, assignment, _, _ = graph
    response = call(DailyTripAssignmentViewSet, 'today_plan_options', supervisor, method='get')
    assert response.status_code == 200, response.data
    assert response.data['results'][0]['team_members'][0]['name'] == 'Driver'
    for _ in range(2):
        response = call(DailyTripAssignmentViewSet, 'generate_selected', supervisor, {'trip_plan_ids': [plan.unique_id]})
        assert response.status_code == 200, response.data
        assert response.data['created'] == []
        assert response.data['existing'] == [assignment.unique_id]
    response = call(DailyTripAssignmentViewSet, 'generate_selected', other, {'trip_plan_ids': [plan.unique_id]})
    assert response.status_code == 403


def test_no_collection_restore_and_generation_skip(graph):
    supervisor, _, other, plan, assignment, customer, stop = graph
    from app.management.commands.generate_daily_trips import run_for_date
    with patch('app.services.daily_service_notice._dispatch_notice'):
        response = call(DailyTripAssignmentViewSet, 'no_collection', supervisor,
            {'trip_plan_ids': [plan.unique_id], 'reason_code': 'WEATHER'})
    assert response.status_code == 200, response.data
    notice = response.data['results'][0]
    assignment.refresh_from_db()
    assert assignment.status == 'Cancelled'
    assert run_for_date(force=True)['created'] == 0
    assert call(DailyTripAssignmentViewSet, 'revoke_service_notice', other, {'notice_id': notice['unique_id']}).status_code == 404
    with patch('app.services.daily_service_notice._dispatch_restoration'):
        response = call(DailyTripAssignmentViewSet, 'revoke_service_notice', supervisor, {'notice_id': notice['unique_id']})
    assert response.status_code == 200, response.data
    assignment.refresh_from_db()
    assert assignment.status == 'Scheduled'


def test_no_collection_cannot_cancel_started_trip(graph):
    supervisor, _, _, plan, assignment, _, _ = graph
    DailyTripAssignment.objects.filter(pk=assignment.pk).update(status='In Progress', actual_start_at=timezone.now())
    response = call(DailyTripAssignmentViewSet, 'no_collection', supervisor,
        {'trip_plan_ids': [plan.unique_id], 'reason_code': 'WEATHER'})
    assert response.status_code == 409


def test_household_and_bin_require_evidence_and_coordinates(graph):
    from app.serializers.operator_mobile.scan_serializers import ScanBinRequestSerializer
    _, driver, _, _, _, customer, _ = graph
    response = call(WasteCollectionBluetoothViewSet, 'mark_household_status', driver,
        {'customer_id': customer.unique_id, 'status': 'not_available', 'reason': 'Locked'})
    assert response.status_code == 400
    assert {'evidence_image', 'latitude', 'longitude'} <= response.data.keys()
    serializer = ScanBinRequestSerializer(data={'bin_qr': 'BIN1', 'action': 'not_available', 'status_reason': 'Locked'})
    assert not serializer.is_valid()
    assert {'evidence_image', 'latitude', 'longitude'} <= serializer.errors.keys()
    serializer = ScanBinRequestSerializer(data={'bin_qr': 'BIN1', 'action': 'not_available', 'status_reason': 'Locked',
        'latitude': 'NaN', 'longitude': 'Infinity', 'evidence_image': image()})
    assert not serializer.is_valid()


def test_delay_create_evidence_notify_and_supervisor_review(graph):
    supervisor, driver, other, _, assignment, _, _ = graph
    payload = {'trip_assignment_id': assignment.unique_id, 'delay_reason': 'TRAFFIC', 'delay_remarks': 'Road closed'}
    response = call(TripDelayReportViewSet, 'create', driver, payload)
    assert response.status_code == 400
    assert 'evidence_image' in response.data
    with patch('app.viewsets.core_modules.daily_operations.trip_delay_report_viewset.notify_staff') as notify:
        response = call(TripDelayReportViewSet, 'create', driver,
            {**payload, 'evidence_image': image(), 'delay_lat': '13.01', 'delay_lng': '80.01'})
    assert response.status_code == 201, response.data
    assert notify.call_count == 1
    uid = response.data['unique_id']
    assert call(TripDelayReportViewSet, 'acknowledge', driver, uid=uid, method='patch').status_code == 403
    assert call(TripDelayReportViewSet, 'acknowledge', other, uid=uid, method='patch').status_code == 404
    assert call(TripDelayReportViewSet, 'acknowledge', supervisor, uid=uid, method='patch').status_code == 200
    assert call(TripDelayReportViewSet, 'resolve', supervisor, uid=uid, method='patch').status_code == 200
    assert TripDelayReport.objects.get(pk=uid).status == 'RESOLVED'


def test_retrip_timeouts_are_idempotent(graph, monkeypatch):
    from app.services.retrip_timeout_service import process_retrip_timeouts
    supervisor, driver, _, _, assignment, _, _ = graph
    now = timezone.now()
    retrip = TripRetripRequest.objects.create(assignment_id=assignment.unique_id, requested_by_id=driver.staff_unique_id)
    TripRetripRequest.objects.filter(pk=retrip.pk).update(created_at=now, expires_at=now+timedelta(minutes=30))
    with patch('app.services.retrip_timeout_service.notify_staff'):
        assert process_retrip_timeouts(now+timedelta(minutes=11))['reminded'] == 1
        assert process_retrip_timeouts(now+timedelta(minutes=12))['reminded'] == 0
        assert process_retrip_timeouts(now+timedelta(minutes=21))['escalated'] == 1
        assert process_retrip_timeouts(now+timedelta(minutes=31))['expired'] == 1
        assert process_retrip_timeouts(now+timedelta(minutes=32))['expired'] == 0
    retrip.refresh_from_db()
    assert retrip.status == 'Expired'


def test_citizen_pickup_shape_and_im_home_idempotent(graph):
    _, driver, _, _, assignment, customer, stop = graph
    DailyTripAssignment.objects.filter(pk=assignment.pk).update(status='In Progress', actual_start_at=timezone.now())
    DailyTripHouseholdCollection.objects.filter(pk=stop.pk).update(status=stop.STATUS_COLLECT_LATER)
    response = call(CitizenPickupViewSet, 'list', customer, method='get')
    assert response.status_code == 200, response.data
    assert {'collection_image_url', 'status_evidence_image_url', 'waste_breakdown', 'customer_available_at', 'missed_pickup_ticket_no'} <= response.data['stop'].keys()
    with patch('app.services.customer_availability._alert_crew'):
        assert call(CitizenPickupViewSet, 'im_home', customer, {'note': 'At home'}).data['notified']
        assert not call(CitizenPickupViewSet, 'im_home', customer, {'note': 'At home'}).data['notified']
    outsider = CustomerCreation.objects.create(customer_name='Other citizen', contact_no='9000000002')
    assert call(CitizenPickupViewSet, 'list', outsider, method='get').data['stop'] is None


def test_citizen_summary_cannot_read_other_customer(graph):
    from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteCollectionSub
    from app.models.masters.waste_masters.wastetype import WasteType
    _, _, _, _, _, customer, _ = graph
    waste = WasteType.objects.create(waste_type_name='Wet Waste')
    WasteCollectionSub.objects.create(customer_id=customer.unique_id, screen_unique_id='s', waste_type_id=waste.unique_id, weight=2)
    WasteCollectionSub.objects.create(customer_id='other', screen_unique_id='s', waste_type_id=waste.unique_id, weight=90)
    response = call(WasteCollectionBluetoothViewSet, 'citizen_summary', customer, method='get', query='?customer_id=other')
    assert response.status_code == 200, response.data
    assert response.data['data']['total_net_weight'] == 2


def test_retrip_selected_live_households_and_unknown_ids(graph):
    from app.services.retrip_service import approve_retrip
    supervisor, driver, _, _, assignment, customer, stop = graph
    DailyTripAssignment.objects.filter(pk=assignment.pk).update(status='In Progress', actual_start_at=timezone.now())
    second = CustomerCreation.objects.create(customer_name='Second', contact_no='9000000003')
    unselected = DailyTripHouseholdCollection.objects.create(trip_assignment_id=assignment.unique_id, customer_id=second.unique_id)
    DailyTripHouseholdCollection.objects.filter(pk=stop.pk).update(customer_available_at=timezone.now(), customer_available_note='Waiting')
    retrip = TripRetripRequest.objects.create(assignment_id=assignment.unique_id, requested_by_id=driver.staff_unique_id,
        expires_at=timezone.now()+timedelta(minutes=30))
    with pytest.raises(ValueError, match='not pending'):
        approve_retrip(retrip, reviewed_by=supervisor, collection_point_ids=['foreign-stop'])
    with patch('app.services.retrip_service.notify_staff'):
        continuation = approve_retrip(retrip, reviewed_by=supervisor, collection_point_ids=[stop.unique_id])
    carried = DailyTripHouseholdCollection.objects.filter(trip_assignment_id=continuation.unique_id)
    assert carried.count() == 1
    assert carried.get().customer_id == customer.unique_id
    assert carried.get().customer_available_note == 'Waiting'
    unselected.refresh_from_db()
    assert unselected.carried_to_assignment_id is None


def test_retrip_api_expired_decision_and_scope(graph):
    from app.viewsets.core_modules.daily_operations.trip_retrip_viewset import TripRetripRequestViewSet
    supervisor, driver, other, _, assignment, _, _ = graph
    retrip = TripRetripRequest.objects.create(assignment_id=assignment.unique_id, requested_by_id=driver.staff_unique_id,
        expires_at=timezone.now()-timedelta(minutes=1))
    assert call(TripRetripRequestViewSet, 'approve', driver, uid=retrip.unique_id).status_code == 403
    assert call(TripRetripRequestViewSet, 'approve', other, uid=retrip.unique_id).status_code == 404
    with patch('app.services.retrip_timeout_service.notify_staff'):
        response = call(TripRetripRequestViewSet, 'approve', supervisor, uid=retrip.unique_id)
    assert response.status_code == 409, response.data
    retrip.refresh_from_db()
    assert retrip.status == 'Expired'


def test_not_available_photo_is_stored_and_missed_ticket_is_idempotent(graph):
    from app.models.core_modules.complaint_management import ComplaintCategory, ComplaintPriority, ComplaintStatus, ComplaintTicket
    from app.services.customer_availability import raise_missed_pickup_ticket
    supervisor, driver, _, _, assignment, customer, stop = graph
    priority = ComplaintPriority.objects.create(priority_code='NORMAL', priority_name='Normal')
    ComplaintCategory.objects.create(category_code='MISSED_PICKUP', category_name='Missed pickup', default_priority_id=priority.unique_id)
    ComplaintStatus.objects.create(status_code='SUBMITTED', status_name='Submitted')
    DailyTripAssignment.objects.filter(pk=assignment.pk).update(status='In Progress', actual_start_at=timezone.now())
    DailyTripHouseholdCollection.objects.filter(pk=stop.pk).update(customer_available_at=timezone.now())
    with patch('app.services.push_notification_service.send_push_to_customer'):
        response = call(WasteCollectionBluetoothViewSet, 'mark_household_status', driver,
            {'customer_id': customer.unique_id, 'assignment_id': assignment.unique_id,
             'status': 'not_available', 'reason': 'Gate locked', 'latitude': '13', 'longitude': '80', 'evidence_image': image()})
    assert response.status_code == 200, response.data
    assert response.data['data']['evidence_image_url'].startswith('http://testserver/')
    stop.refresh_from_db()
    assert stop.status_evidence_image
    assert stop.status == 'Not Available'
    assert ComplaintTicket.objects.filter(customer_id=customer.unique_id).count() == 1
    assert raise_missed_pickup_ticket(stop)
    assert ComplaintTicket.objects.filter(customer_id=customer.unique_id).count() == 1


def test_notice_recipients_and_citizen_notice(graph, django_capture_on_commit_callbacks):
    from app.models.core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPoint
    from app.services.daily_service_notice import declare_no_collection
    supervisor, driver, _, plan, _, customer, _ = graph
    TripPlanCollectionPoint.objects.create(trip_plan_id=plan.unique_id, collection_type=plan.collection_type, customer_id=customer.unique_id, sequence=1)
    with patch('app.services.daily_service_notice.notify_staff') as staff_push, patch('app.services.daily_service_notice.send_push_to_customer', return_value=True) as customer_push:
        with django_capture_on_commit_callbacks(execute=True):
            notice = declare_no_collection(plan, timezone.localdate(), 'HOLIDAY', '', supervisor.pk)
    assert set(notice.recipient_staff_ids) == {supervisor.staff_unique_id, driver.staff_unique_id}
    assert notice.recipient_customer_ids == [customer.unique_id]
    assert staff_push.call_count == 2
    assert customer_push.call_count == 1
    response = call(CitizenPickupViewSet, 'list', customer, method='get')
    assert response.data['service_notice']['reason_code'] == 'HOLIDAY'


def test_generate_selected_creates_and_clones_household_stops(graph):
    from app.models.core_modules.schedule_setup.trip_plan_collection_point import TripPlanCollectionPoint
    supervisor, _, _, plan, assignment, customer, _ = graph
    DailyTripHouseholdCollection.objects.filter(trip_assignment_id=assignment.unique_id).delete()
    DailyTripAssignment.objects.filter(pk=assignment.pk).delete()
    TripPlanCollectionPoint.objects.create(trip_plan_id=plan.unique_id, collection_type=plan.collection_type, customer_id=customer.unique_id, sequence=1)
    response = call(DailyTripAssignmentViewSet, 'generate_selected', supervisor, {'trip_plan_ids': [plan.unique_id]})
    assert response.status_code == 200, response.data
    assert len(response.data['created']) == 1
    assert DailyTripHouseholdCollection.objects.get(trip_assignment_id=response.data['created'][0]).customer_id == customer.unique_id


@pytest.mark.parametrize(('action', 'expected'), [('collect', 'Collected'), ('collect_later', 'Skipped'), ('not_available', 'Missed')])
def test_bin_status_multipart_persists_and_refreshes(graph, action, expected):
    from app.viewsets.operator_mobile.scan_bin_viewset import ScanBinViewSet
    from app.models.core_modules.schedule_setup.collection_point import Collection_point
    from app.models.masters.waste_masters.bins import Bins
    from app.models.masters.waste_masters.wastetype import WasteType
    from app.models.core_modules.daily_operations.daily_trip_collection_point import DailyTripCollectionPoint
    from app.models.core_modules.daily_operations.secondary_bin_collection_event import BinCollectionEvent
    _, driver, _, plan, assignment, _, _ = graph
    waste = WasteType.objects.create(waste_type_name='Wet Waste')
    TripPlan.objects.filter(pk=plan.pk).update(collection_type=TripPlan.COLLECTION_TYPE_BIN)
    DailyTripAssignment.objects.filter(pk=assignment.pk).update(status='In Progress', actual_start_at=timezone.now(), panchayat_id='PANCH-PORT', waste_type_ids=[waste.unique_id])
    cp = Collection_point.objects.create(cp_name='Port point', panchayat_id='PANCH-PORT', latitude='13.01', longitude='80.01')
    bin_row = Bins.objects.create(collection_point_id=cp.unique_id, wastetype_id=waste.unique_id, bin_name='Port bin', bin_capacity=100, bin_type='small')
    stop = DailyTripCollectionPoint.objects.create(trip_assignment_id=assignment.unique_id, collection_point_id=cp.unique_id, bin_id=bin_row.unique_id)
    response = call(ScanBinViewSet, 'create', driver, {'bin_qr': bin_row.unique_id, 'action': action,
        'status_reason': 'Locked', 'latitude': '13.01', 'longitude': '80.01', 'evidence_image': image()})
    assert response.status_code == 201, response.data
    assert response.data['event']['evidence_image_url']
    assert BinCollectionEvent.objects.get(trip_assignment_id=assignment.unique_id).status_evidence_image
    stop.refresh_from_db()
    assert stop.status == expected

    from app.serializers.operator_mobile.trip_today_serializer import TripCollectionPointSerializer
    from app.serializers.core_modules.daily_operations.daily_trip_assignment_serializer import DailyTripAssignmentSerializer
    assert TripCollectionPointSerializer(stop).data['status_evidence_image_url']
    assignment.refresh_from_db()
    assert DailyTripAssignmentSerializer(assignment).data['trip_log_summary']['vehicle_no'] == 'TN-PORT-01'

    from app.viewsets.operator_mobile.my_trip_today_viewset import MyTripsTodayViewSet
    response = call(MyTripsTodayViewSet, 'list', driver, method='get')
    row = response.data['results'][0]['collection_points'][0]
    assert row['status'] == expected
    assert row['is_collected'] == (action == 'collect')


def test_household_finalize_updates_driver_home_and_citizen_card(graph):
    from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteCollectionSub
    from app.models.core_modules.daily_operations.waste_collection import WasteCollection
    from app.models.masters.waste_masters.wastetype import WasteType
    from app.viewsets.operator_mobile.my_trip_today_viewset import MyTripsTodayViewSet
    _, driver, _, _, assignment, customer, stop = graph
    DailyTripAssignment.objects.filter(pk=assignment.pk).update(status='In Progress', actual_start_at=timezone.now())
    waste = WasteType.objects.create(waste_type_name='Wet Waste')
    WasteCollectionSub.objects.create(screen_unique_id='visit', customer_id=customer.unique_id, waste_type_id=waste.unique_id, weight=2.5)
    with patch('app.services.push_notification_service.send_push_to_customer'):
        response = call(WasteCollectionBluetoothViewSet, 'finalize_waste_collection', driver,
            {'screen_unique_id': 'visit', 'customer_id': customer.unique_id, 'assignment_id': assignment.unique_id})
    assert response.status_code == 200, response.data
    assert 'waste_collection_error' not in response.data
    stop.refresh_from_db()
    assert stop.is_collected and stop.status == 'Collected'
    assert float(stop.collected_weight_kg) == 2.5
    assert WasteCollection.objects.get(customer_id=customer.unique_id).trip_assignment_id == assignment.unique_id
    response = call(MyTripsTodayViewSet, 'list', driver, method='get')
    row = response.data['results'][0]['household_collections'][0]
    assert row['is_collected'] and row['status'] == 'Collected'
    assert float(row['collected_weight_kg']) == 2.5
    assert response.data['results'][0]['progress']['collected'] == 1
    assert call(CitizenPickupViewSet, 'list', customer, method='get').data['stop']['is_collected']


def test_finalize_failure_cannot_return_success_or_commit_partial_visit(graph):
    from app.models.waste_collection_bluetooth.waste_collection_bluetooth import WasteCollectionSub, WasteCollectionMain
    _, driver, _, _, assignment, customer, stop = graph
    DailyTripAssignment.objects.filter(pk=assignment.pk).update(status='In Progress', actual_start_at=timezone.now())
    row = WasteCollectionSub.objects.create(screen_unique_id='failed-visit', customer_id=customer.unique_id, waste_type_id='wet', weight=2)
    with patch.object(WasteCollectionBluetoothViewSet, '_mirror_to_waste_collection', side_effect=ValueError('cannot write stop')):
        response = call(WasteCollectionBluetoothViewSet, 'finalize_waste_collection', driver,
            {'screen_unique_id': 'failed-visit', 'customer_id': customer.unique_id, 'assignment_id': assignment.unique_id})
    assert response.status_code == 500
    assert response.data['status'] == 'error'
    assert not WasteCollectionMain.objects.filter(screen_unique_id='failed-visit').exists()
    row.refresh_from_db()
    assert row.form_unique_id is None
    stop.refresh_from_db()
    assert not stop.is_collected


@pytest.mark.parametrize(('action', 'expected'), [('collect_later', 'Collect Later'), ('not_available', 'Not Available')])
def test_household_status_is_returned_to_driver_home(graph, action, expected):
    from app.viewsets.operator_mobile.my_trip_today_viewset import MyTripsTodayViewSet
    _, driver, _, _, assignment, customer, _ = graph
    DailyTripAssignment.objects.filter(pk=assignment.pk).update(status='In Progress', actual_start_at=timezone.now())
    data = {'customer_id': customer.unique_id, 'assignment_id': assignment.unique_id, 'status': action, 'reason': 'Gate closed'}
    if action == 'not_available':
        data.update(evidence_image=image(), latitude='13.01', longitude='80.01')
    with patch('app.services.push_notification_service.send_push_to_customer'):
        response = call(WasteCollectionBluetoothViewSet, 'mark_household_status', driver, data)
    assert response.status_code == 200, response.data
    response = call(MyTripsTodayViewSet, 'list', driver, method='get')
    row = response.data['results'][0]['household_collections'][0]
    assert row['status'] == expected
    assert not row['is_collected']
    assert row['status_reason'] == 'Gate closed'


def test_trip_log_exposes_not_available_photo_in_detail_and_list(graph):
    from app.models.core_modules.daily_operations.daily_trip_log import DailyTripLog
    from app.serializers.core_modules.daily_operations.daily_trip_log_serializer import DailyTripLogSerializer
    _, _, _, _, assignment, _, stop = graph
    stop.status = stop.STATUS_MISSED
    stop.status_reason = 'Gate locked'
    stop.status_evidence_image = image()
    stop.save()
    log = DailyTripLog.objects.create(trip_assignment_id=assignment.unique_id)
    request = APIRequestFactory().get('/api/v1/schedule-operations/daily-trip-logs/')
    detail = DailyTripLogSerializer(log, context={'request': request}).data
    listing = DailyTripLogSerializer([log], many=True, context={'request': request}).data
    for payload in [detail, listing[0]]:
        row = payload['household_collections'][0]
        assert row['status'] == 'Not Available'
        assert row['status_reason'] == 'Gate locked'
        assert row['status_evidence_image_url'].startswith('http://testserver/media/household_status_evidence/')


@pytest.mark.parametrize('granted', [True, False])
def test_vehicle_breakdown_post_uses_catalog_grant(graph, granted):
    from app.middleware.module_permission_middleware import ModulePermissionMiddleware
    from app.viewsets.core_modules.daily_operations.vehicle_breakdown_viewset import VehicleBreakdownViewSet
    _, driver, _, _, assignment, _, _ = graph
    request = APIRequestFactory().post('/api/v1/schedule-operations/vehicle-breakdowns/', {
        'trip_assignment_id': assignment.unique_id,
        'breakdown_vehicle_id': assignment.vehicle_id,
        'breakdown_reason': 'ENGINE_FAILURE',
    }, format='json')
    request.user = driver
    force_authenticate(request, user=driver)
    view = VehicleBreakdownViewSet.as_view({'post': 'create'})
    permissions = {'daily-operations': {'vehicle-breakdown': ['view', 'add'] if granted else ['view']}}
    middleware = ModulePermissionMiddleware(lambda request: None)
    with patch('app.middleware.module_permission_middleware._authenticate_request', return_value=None), patch(
        'app.middleware.module_permission_middleware._resolve_permissions_for_request', return_value=permissions
    ):
        denied = middleware.process_view(request, view, (), {})
    if not granted:
        assert denied.status_code == 403
        return
    assert denied is None
    with patch('app.viewsets.core_modules.daily_operations.vehicle_breakdown_viewset.notify_staff') as notify:
        response = view(request)
    assert response.status_code == 201, response.data
    assert response.data['approval_status'] == 'PENDING'
    assert notify.call_count == 1


def test_completed_household_run_is_replaced_by_scheduled_reassignment(graph):
    from app.viewsets.operator_mobile.my_trip_today_viewset import MyTripsTodayViewSet
    supervisor, driver, _, plan, completed, _, _ = graph
    DailyTripAssignment.objects.filter(pk=completed.pk).update(status='Completed')
    scheduled = DailyTripAssignment.objects.create(trip_plan_id=plan.unique_id, trip_date=timezone.localdate(), scheduled_time='15:00')
    response = call(MyTripsTodayViewSet, 'list', driver, method='get')
    assert response.status_code == 200
    assert [a['assignment_unique_id'] for a in response.data['results']] == [scheduled.unique_id]
    response = call(DailyTripAssignmentViewSet, 'today_plan_options', supervisor, method='get')
    assert response.data['results'][0]['assignment_id'] == scheduled.unique_id
    assert response.data['results'][0]['state'] == 'Scheduled'


def test_new_routes_are_wired_for_mobile_roles(graph):
    """Delay reports have a catalog owner (driver.delays grants it) and the
    supervisor day-planning POSTs do not need the generic "add" grant —
    the actions gate themselves on role + plan ownership."""
    from app.utils.permission_catalog import ROUTE_OWNERS
    from app.utils.app_feature_grants import ROLE_SCREEN_TEMPLATES, SCREEN_PERMISSIONS

    assert ROUTE_OWNERS["schedule-operations/trip-delay-reports"] == (
        "daily-operations", "trip-delay-reports",
    )
    assert SCREEN_PERMISSIONS["driver.delays"] == ("daily-operations", "trip-delay-reports", "view")
    assert "add" in ROLE_SCREEN_TEMPLATES["driver"]["daily-operations"]["trip-delay-reports"]
    assert "edit" in ROLE_SCREEN_TEMPLATES["supervisor"]["daily-operations"]["trip-delay-reports"]
    assert {
        "today_plan_options", "generate_selected", "no_collection", "revoke_service_notice",
    } <= set(DailyTripAssignmentViewSet.permission_exempt_actions)


def test_plan_option_shape_uses_government_geography(graph):
    supervisor, _, _, plan, _, _, _ = graph
    response = call(DailyTripAssignmentViewSet, 'today_plan_options', supervisor, method='get')
    assert response.status_code == 200, response.data
    option = response.data['results'][0]
    assert {
        'trip_plan_id', 'display_code', 'collection_type', 'scheduled_time', 'state',
        'assignment_id', 'blocking_reason', 'vehicle_no', 'team_code', 'driver_name',
        'operator_name', 'ward_names', 'local_body_name', 'notice', 'team_members',
    } <= option.keys()
    assert option['vehicle_no'] == 'TN-PORT-01'
    assert option['team_code'] == 'PORT-TEAM'
