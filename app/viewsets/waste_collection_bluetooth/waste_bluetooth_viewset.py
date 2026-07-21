from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum
from datetime import datetime, timedelta
from app.models.user_creations.waste_collection_bluetooth import (
    WasteCollectionMain,
    WasteCollectionSub,
    generate_unique_id,
    upload_image,
)
from app.models.assets.wastetype import WasteType
from app.models.masters.customer_masters.customercreation import CustomerCreation



class WasteCollectionBluetoothViewSet(viewsets.ViewSet):
    parser_classes = [JSONParser, FormParser, MultiPartParser]
        # ----------------- API ROOT FOR /waste/ -----------------
    def list(self, request):
        """
        Waste API root endpoint.
        Shows all available waste-related operations.
        """
        base = request.build_absolute_uri().rstrip("/")

        return Response({
            "status": "success",
            "message": "Waste collection API root",
            "available_endpoints": {
                "get_waste_types": f"{base}/get-waste-types/",
                "insert_waste_sub": f"{base}/insert-waste-sub/",
                "get_latest_waste": f"{base}/get-latest-waste/",
                "update_waste_sub": f"{base}/update-waste-sub/",
                "finalize_waste": f"{base}/finalize-waste/",
                "citizen_summary": f"{base}/citizen-summary/",
            "mark_household_status": f"{base}/mark-household-status/",
            }
        })


    # ----------------- MARK HOUSEHOLD STATUS (Missed / Collect later) -----------------
    @action(detail=False, methods=["post"], url_path="mark-household-status")
    def mark_household_status(self, request):
        """Driver/operator marks a household stop Skipped or Missed from the app.

        Writes to the DailyTripHouseholdCollection row for the requester's active
        trip today, so the update stays scoped to the trip (and its hierarchy).
        """
        from app.models.schedule_masters.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )
        from app.viewsets.operator_mobile.helpers import (
            OperatorFlowError,
            find_active_assignment_for_operator,
            resolve_operator_staff,
        )

        customer_id = str(request.data.get("customer_id") or "").strip()
        status_value = str(request.data.get("status") or "").strip().lower()
        reason = str(
            request.data.get("reason") or request.data.get("status_reason") or ""
        ).strip()
        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")

        status_aliases = {
            # "Not available" from the app → canonical "Not Available".
            "not_available": DailyTripHouseholdCollection.STATUS_MISSED,
            "not available": DailyTripHouseholdCollection.STATUS_MISSED,
            "missed": DailyTripHouseholdCollection.STATUS_MISSED,
            # "Collect later" → canonical "Collect Later" (matches the web).
            "collect_later": DailyTripHouseholdCollection.STATUS_COLLECT_LATER,
            "collect later": DailyTripHouseholdCollection.STATUS_COLLECT_LATER,
            "skipped": DailyTripHouseholdCollection.STATUS_COLLECT_LATER,
        }
        normalized_status = status_aliases.get(status_value)

        if not customer_id:
            return Response(
                {"status": "error", "message": "customer_id is required"}, status=400
            )
        if normalized_status is None:
            return Response(
                {
                    "status": "error",
                    "message": "status must be missed/not_available or skipped/collect_later",
                },
                status=400,
            )
        if not reason:
            return Response(
                {"status": "error", "message": "reason is required"}, status=400
            )

        from app.models.schedule_masters.daily_trip_assignment import (
            DailyTripAssignment,
        )

        try:
            staff = resolve_operator_staff(request.user)
            # The app sends the specific trip the household belongs to (a driver
            # can have both a bin AND a household trip today). Use it so the
            # status lands on the correct household assignment; otherwise fall
            # back to the operator's active trip.
            assignment_id = str(request.data.get("assignment_id") or "").strip()
            assignment = None
            if assignment_id:
                assignment = DailyTripAssignment.objects.filter(
                    unique_id=assignment_id, is_deleted=False
                ).first()
            if assignment is None:
                assignment = find_active_assignment_for_operator(staff)
        except OperatorFlowError as exc:
            return Response(
                {"status": "error", "code": exc.code, "message": exc.message},
                status=exc.http_status,
            )

        customer = CustomerCreation.objects.filter(
            unique_id=customer_id, is_deleted=False
        ).first()
        if customer is None:
            return Response(
                {"status": "error", "message": "Customer not found"}, status=404
            )

        # Allow marking ANY customer, even one not pre-listed on the trip: attach
        # them to the requester's active assignment as a household stop on the fly.
        dthc = (
            DailyTripHouseholdCollection.objects
            .filter(
                trip_assignment_id=assignment,
                customer_id=customer,
                is_deleted=False,
            )
            .first()
        )
        if dthc is None:
            last_seq = (
                DailyTripHouseholdCollection.objects
                .filter(trip_assignment_id=assignment)
                .order_by("-sequence")
                .values_list("sequence", flat=True)
                .first()
            )
            dthc = DailyTripHouseholdCollection.objects.create(
                trip_assignment_id=assignment,
                customer_id=customer,
                collection_type=DailyTripHouseholdCollection.COLLECTION_TYPE_HOUSEHOLD,
                sequence=(last_seq or 0) + 1,
                status=DailyTripHouseholdCollection.STATUS_PENDING,
                is_collected=False,
                is_active=True,
                is_deleted=False,
            )
        if dthc.is_collected:
            return Response(
                {"status": "error", "message": "This household is already collected."},
                status=409,
            )

        dthc.status = normalized_status
        dthc.status_reason = reason
        dthc.status_latitude = latitude or None
        dthc.status_longitude = longitude or None
        dthc.is_collected = False
        dthc.save(update_fields=[
            "status",
            "status_reason",
            "status_latitude",
            "status_longitude",
            "is_collected",
            "updated_at",
        ])

        # Notify the customer instantly. Safe no-op if push isn't configured
        # or they have no registered device.
        from app.services.push_notification_service import send_push_to_customer
        if normalized_status == DailyTripHouseholdCollection.STATUS_MISSED:  # "Not Available"
            title, body = "Collection update", "Our driver could not access your location today."
        else:  # Collect Later
            title, body = "Collection update", "Your waste will be collected later today."
        if reason:
            body += f' ("{reason}")'
        send_push_to_customer(
            dthc.customer_id,
            title,
            body,
            data={"event": "household_status", "status": dthc.status, "trip_assignment_id": str(dthc.trip_assignment_id_id)},
        )

        return Response({
            "status": "success",
            "data": {
                "unique_id": dthc.unique_id,
                "customer_id": dthc.customer_id_id,
                "trip_assignment_id": dthc.trip_assignment_id_id,
                "collection_status": dthc.status,
                "reason": dthc.status_reason,
            },
        })


    # ----------------- INSERT WASTE SUB -----------------
    @action(detail=False, methods=["post"], url_path="insert-waste-sub")
    def insert_waste_sub(self, request):
        screen_id = request.data.get("screen_unique_id")
        customer_id = request.data.get("customer_id")
        waste_type = request.data.get("waste_type") or request.data.get(
            "waste_type_id"
        )
        weight = request.data.get("weight")
        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")
        image = request.FILES.get("image")

        if not screen_id:
            return Response({"status": "error", "message": "Missing screen_unique_id"}, status=400)
        if not waste_type:
            return Response({"status": "error", "message": "Missing waste_type"}, status=400)
        if not image:
            return Response({"status": "error", "message": "No image uploaded"}, status=400)

        image_path, image_warning = self._upload_image_or_blank(image)
        record = WasteCollectionSub.objects.create(
            unique_id=generate_unique_id("wcs-"),
            screen_unique_id=screen_id,
            customer_id=customer_id,
            waste_type_id=str(waste_type),
            image=image_path,
            weight=self._to_float(weight),
            latitude=latitude,
            longitude=longitude,
            is_deleted=False,
        )

        return Response({
            "status": "success",
            "unique_id": record.unique_id,
            "screen_unique_id": screen_id,
            "image": image_path,
            **({"image_warning": image_warning} if image_warning else {}),
        })

    # ----------------- GET SAVED WASTE TYPES -----------------
    @action(detail=False, methods=["get"], url_path="get-waste-types")
    def get_saved_waste(self, request):
        rows = WasteType.objects.filter(is_deleted=False).order_by("waste_type_name")

        # Show the primary segregated household streams first — Wet, then Dry —
        # followed by every other type alphabetically. Uses a stable key so the
        # remaining types keep their alphabetical order.
        def sort_key(row):
            name = (row.waste_type_name or "").strip().lower()
            if "wet" in name:
                return (0, name)
            if "dry" in name:
                return (1, name)
            return (2, name)

        rows = sorted(rows, key=sort_key)
        data = [
            {"id": row.unique_id, "waste_type_name": row.waste_type_name}
            for row in rows
        ]
        return Response({"status": "success", "count": len(data), "data": data})

    # ----------------- GET LATEST WASTE SUB -----------------
    @action(detail=False, methods=["post"], url_path="get-latest-waste")
    def get_latest_waste(self, request):
        screen_id = request.data.get("screen_unique_id")
        customer_id = request.data.get("customer_id")
        waste_type = request.data.get("waste_type") or request.data.get(
            "waste_type_id"
        )
        if not waste_type:
            return Response({"status": "error", "message": "Missing waste_type"}, status=400)

        row = (
            WasteCollectionSub.objects
            .filter(
                screen_unique_id=screen_id,
                customer_id=customer_id,
                waste_type_id=waste_type,
                is_deleted=False,
            )
            .order_by("-date_time")
            .first()
        )

        if not row:
            return Response({"status": "error", "message": "No record found"})

        return Response({
            "status": "success",
            "data": {
                "id": row.unique_id,
                "unique_id": row.unique_id,
                "waste_type_id": row.waste_type_id,
                "image": row.image,
                "weight": row.weight,
            }
        })

    # ----------------- FINALIZE WASTE COLLECTION -----------------
    @action(detail=False, methods=["post"], url_path="finalize-waste")
    def finalize_waste_collection(self, request):
        screen_id = request.data.get("screen_unique_id")
        customer_id = request.data.get("customer_id")
        entry_type = request.data.get("entry_type", "app")

        if not screen_id or not customer_id:
            return Response({"status": "error", "message": "Missing parameters"}, status=400)

        collection_rows = WasteCollectionSub.objects.filter(
            screen_unique_id=screen_id,
            customer_id=customer_id,
            is_deleted=False,
        )
        total = collection_rows.aggregate(total=Sum("weight"))["total"] or 0

        if float(total) <= 0:
            return Response({"status": "error", "message": "No waste records found"})

        main_id = generate_unique_id("wcm-")
        now = timezone.now()

        # 1) Legacy aggregate (unchanged): keep writing WasteCollectionMain and
        #    linking the captured sub-rows to it so anything still reading the
        #    old bluetooth tables (desktop CRUD, citizen-summary) does not
        #    regress.
        with transaction.atomic():
            WasteCollectionMain.objects.create(
                unique_id=main_id,
                screen_unique_id=screen_id,
                collected_time=now,
                created=now,
                total_waste_collected=float(total),
                entry_type=entry_type,
                customer_id=customer_id,
                is_deleted=False,
            )
            collection_rows.update(form_unique_id=main_id)

        response = {
            "status": "success",
            "main_unique_id": main_id,
            "total_weight": float(total),
            "collected_time": now,
        }

        # 2) New web backend: mirror the same collection into the canonical
        #    WasteCollection table (wet/dry/mixed split). Saving it with a
        #    trip_assignment fires sync_household_collection_on_waste_save, which
        #    marks the household stop collected and syncs the trip log/dashboards.
        #    Guarded in its own block so a failure here can never break the app's
        #    finalize (the legacy record above is already committed).
        try:
            waste_collection = self._mirror_to_waste_collection(
                customer_id=customer_id,
                collection_rows=collection_rows,
                request=request,
                assignment_id=str(request.data.get("assignment_id") or "").strip(),
            )
            if waste_collection is not None:
                response["waste_collection_unique_id"] = waste_collection.unique_id
        except Exception as exc:  # noqa: BLE001 — never regress the app flow
            import logging

            logging.getLogger(__name__).exception(
                "finalize-waste: mirroring to WasteCollection failed"
            )
            response["waste_collection_error"] = str(exc)

        return Response(response)

    # ----- helpers for the WasteCollection mirror (new web backend) -----
    def _split_waste_by_type(self, collection_rows):
        """Bucket the session's captured sub-rows into wet / dry / mixed by
        waste-type name — same rule the citizen-summary aggregate uses."""
        type_names = {
            wt.unique_id: (wt.waste_type_name or "").lower()
            for wt in WasteType.objects.filter(is_deleted=False)
        }
        wet = dry = mixed = 0.0
        for sub in collection_rows:
            key = str(sub.waste_type_id)
            name = type_names.get(key, "")
            weight = float(sub.weight or 0)
            if key == "1" or "wet" in name or "organic" in name:
                wet += weight
            elif key == "2" or "dry" in name:
                dry += weight
            else:
                mixed += weight
        return wet, dry, mixed

    def _resolve_trip_assignment(self, customer, request, assignment_id=None):
        """Best-effort trip for this collection: the exact assignment the app
        sent (preferred — a driver can hold both a bin and a household trip),
        else the trip where this household is a stop today, else the requester's
        active operator trip. None when nothing applies."""
        from app.models.schedule_masters.daily_trip_assignment import (
            DailyTripAssignment,
        )
        from app.models.schedule_masters.daily_trip_household_collection import (
            DailyTripHouseholdCollection,
        )

        if assignment_id:
            explicit = DailyTripAssignment.objects.filter(
                unique_id=assignment_id, is_deleted=False
            ).first()
            if explicit is not None:
                return explicit

        today = timezone.localdate()
        dthc = (
            DailyTripHouseholdCollection.objects
            .filter(
                customer_id=customer,
                is_deleted=False,
                trip_assignment_id__trip_date=today,
                trip_assignment_id__is_deleted=False,
            )
            .exclude(trip_assignment_id__status=DailyTripAssignment.STATUS_CANCELLED)
            .select_related("trip_assignment_id")
            .order_by("is_collected", "trip_assignment_id")  # prefer a pending stop
            .first()
        )
        if dthc:
            return dthc.trip_assignment_id

        try:
            from app.viewsets.operator_mobile.helpers import (
                find_active_assignment_for_operator,
                resolve_operator_staff,
            )

            return find_active_assignment_for_operator(
                resolve_operator_staff(request.user)
            )
        except Exception:  # noqa: BLE001 — not an operator / no active trip
            return None

    def _mirror_to_waste_collection(self, *, customer_id, collection_rows, request,
                                    assignment_id=None):
        """Create or refresh the canonical WasteCollection row for this
        household so the web backend (dashboards, trip log, household stops)
        sees the app's collection."""
        from app.models.masters.customer_masters.wastecollection import WasteCollection

        customer = CustomerCreation.objects.filter(
            unique_id=customer_id, is_deleted=False
        ).first()
        if customer is None:
            # Nothing to link to; the legacy Main record already stored the data.
            return None

        wet, dry, mixed = self._split_waste_by_type(collection_rows)
        trip_assignment = self._resolve_trip_assignment(
            customer, request, assignment_id=assignment_id
        )

        # De-duplicate: refresh an existing collection for this household+trip
        # (or same day, when there is no trip) rather than piling up rows that
        # would double-count in the trip-log aggregate.
        existing_qs = WasteCollection.objects.filter(
            customer=customer, is_deleted=False
        )
        if trip_assignment is not None:
            existing_qs = existing_qs.filter(trip_assignment_id=trip_assignment)
        else:
            existing_qs = existing_qs.filter(collection_date=timezone.localdate())
        waste_collection = existing_qs.order_by(
            "-collection_date", "-collection_time"
        ).first()

        if waste_collection is None:
            waste_collection = WasteCollection(customer=customer)
        waste_collection.trip_assignment_id = trip_assignment
        waste_collection.wet_waste = wet
        waste_collection.dry_waste = dry
        waste_collection.mixed_waste = mixed
        waste_collection.is_deleted = False
        waste_collection.is_active = True
        # save() auto-calculates total_quantity + inherits geo; the post_save
        # signal handles household-stop completion and trip-log sync.
        waste_collection.save()
        return waste_collection

    # ----------------- UPDATE WASTE SUB -----------------
    @action(detail=False, methods=["post"], url_path="update-waste-sub")
    def update_waste_sub(self, request):
        record_id = request.data.get("unique_id") or request.data.get("id")
        weight = request.data.get("weight")
        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")

        if not record_id:
            return Response({"status": "error", "message": "Missing unique_id"}, status=400)

        row = WasteCollectionSub.objects.filter(
            unique_id=record_id,
            is_deleted=False,
        ).first()

        if row is None:
            return Response({"status": "error", "message": f"No matching record found for unique_id {record_id}"}, status=400)

        image_path = None
        if "image" in request.FILES:
            image_path, image_warning = self._upload_image_or_blank(
                request.FILES["image"]
            )
        else:
            image_warning = None

        row.weight = self._to_float(weight)
        row.latitude = latitude
        row.longitude = longitude
        if image_path:
            row.image = image_path
        row.save()

        return Response({
            "status": "success",
            "message": "Record updated",
            "data": {
                "unique_id": row.unique_id,
                "waste_type_id": row.waste_type_id,
                "image": row.image,
                "weight": row.weight,
                "latitude": row.latitude,
                "longitude": row.longitude,
            }
        })

    # ----------------- CITIZEN WASTE SUMMARY (DAILY / MONTHLY / TOTAL) -----------------
    @action(detail=False, methods=["get"], url_path="citizen-summary")
    def citizen_summary(self, request):
        period = (request.query_params.get("period") or "monthly").lower()
        date_param = request.query_params.get("date")

        try:
            base_date = (
                datetime.strptime(date_param, "%Y-%m-%d").date()
                if date_param
                else timezone.localdate()
            )
        except ValueError:
            return Response(
                {
                    "status": "error",
                    "message": "Invalid date format. Use YYYY-MM-DD.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        start, end = self._get_range_bounds(period, base_date)
        start = self._make_aware(start)
        end = self._make_aware(end)

        rows = WasteCollectionSub.objects.filter(is_deleted=False)
        if start and end:
            rows = rows.filter(date_time__gte=start, date_time__lt=end)

        type_names = {
            waste_type.unique_id: waste_type.waste_type_name.lower()
            for waste_type in WasteType.objects.filter(is_deleted=False)
        }
        weights = {"wet": 0.0, "dry": 0.0, "mixed": 0.0}

        for row in rows.values("waste_type_id").annotate(total=Sum("weight")):
            waste_type_id = row["waste_type_id"]
            total = row["total"]
            key = str(waste_type_id)
            total_value = float(total or 0)
            name = type_names.get(key, key)
            if key == "1" or "wet" in name:
                weights["wet"] = total_value
            elif key == "2" or "dry" in name:
                weights["dry"] = total_value
            else:
                weights["mixed"] += total_value

        trips = WasteCollectionMain.objects.filter(is_deleted=False)
        if start and end:
            trips = trips.filter(collected_time__gte=start, collected_time__lt=end)

        total_trip = trips.count()
        total_net = weights["wet"] + weights["dry"] + weights["mixed"]
        average_per_trip = total_net / total_trip if total_trip > 0 else 0.0

        summary_date = start.date() if start else timezone.localdate()

        return Response(
            {
                "status": "success",
                "data": {
                    "period": period,
                    "date": summary_date.isoformat(),
                    "total_trip": total_trip,
                    "dry_weight": weights["dry"],
                    "wet_weight": weights["wet"],
                    "mix_weight": weights["mixed"],
                    "total_net_weight": total_net,
                    "average_weight_per_trip": average_per_trip,
                },
            }
        )

    @staticmethod
    def _to_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _upload_image_or_blank(image):
        try:
            return upload_image(image), None
        except OSError as exc:
            return "", f"Image could not be saved: {exc}"

    def _get_range_bounds(self, period, base_date):
        if period == "daily":
            start = datetime.combine(base_date, datetime.min.time())
            end = start + timedelta(days=1)
        elif period == "monthly":
            start = datetime(base_date.year, base_date.month, 1)
            if base_date.month == 12:
                end = datetime(base_date.year + 1, 1, 1)
            else:
                end = datetime(base_date.year, base_date.month + 1, 1)
        else:  # total or fallback
            start = None
            end = None
        return start, end

    def _make_aware(self, dt):
        if dt is None:
            return None
        if timezone.is_naive(dt):
            return timezone.make_aware(dt)
        return dt

    # ----------------- LOOKUP CUSTOMER BY UNIQUE ID FOR QR -----------------
    @action(detail=False, methods=["get"], url_path="customer")
    def get_customer_by_unique_id(self, request):
        unique_id = request.query_params.get("unique_id") or request.query_params.get("uid")
        if not unique_id:
            return Response(
                {"status": "error", "message": "unique_id is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Match directly on customer unique_id
        customer = (
            CustomerCreation.objects
            .filter(unique_id=unique_id, is_deleted=False, is_active=True)
            .first()
        )

        if not customer:
            return Response(
                {"status": "error", "message": "Customer not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        data = {
            "unique_id": customer.unique_id,
            "customer_name": customer.customer_name,
            "contact_no": customer.contact_no,
            "latitude": customer.latitude,
            "longitude": customer.longitude,
            "address": {
                "building_no": customer.building_no,
                "street": customer.street,
                "area": customer.area,
                "pincode": customer.pincode,
            },
        }

        return Response({"status": "success", "data": data})
