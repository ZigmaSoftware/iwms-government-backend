from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.response import Response
from django.utils import timezone
from django.db import connection
from datetime import datetime, timedelta
from app.models.user_creations.waste_collection_bluetooth import generate_unique_id, upload_image
from app.models.customers.customercreation import CustomerCreation



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
            }
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

        unique_id = generate_unique_id("wcs")
        image_path = upload_image(image)
        now = timezone.now()

        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO waste_collection_sub
                (unique_id, screen_unique_id, customer_id, waste_type_id, image, weight,
                 latitude, longitude, date_time, is_deleted)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,0)
            """, [unique_id, screen_id, customer_id, waste_type, image_path,
                  weight, latitude, longitude, now])

        return Response({
            "status": "success",
            "unique_id": unique_id,
            "screen_unique_id": screen_id,
            "image": image_path
        })

    # ----------------- GET SAVED WASTE TYPES -----------------
    @action(detail=False, methods=["get"], url_path="get-waste-types")
    def get_saved_waste(self, request):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, waste_type_name
                FROM waste_type_creation_master
                WHERE is_deleted=0
                ORDER BY id ASC
            """)
            rows = cursor.fetchall()
        data = [{"id": r[0], "waste_type_name": r[1]} for r in rows]
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

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, unique_id, waste_type_id, image, weight
                FROM waste_collection_sub
                WHERE screen_unique_id=%s
                AND customer_id=%s
                AND waste_type_id=%s
                AND is_deleted=0
                ORDER BY id DESC LIMIT 1
            """, [screen_id, customer_id, waste_type])
            row = cursor.fetchone()

        if not row:
            return Response({"status": "error", "message": "No record found"})

        return Response({
            "status": "success",
            "data": {
                "id": row[0],
                "unique_id": row[1],
                "waste_type_id": row[2],
                "image": row[3],
                "weight": row[4],
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

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COALESCE(SUM(weight), 0)
                FROM waste_collection_sub
                WHERE screen_unique_id=%s AND customer_id=%s AND is_deleted=0
            """, [screen_id, customer_id])
            total = cursor.fetchone()[0]

        if float(total) <= 0:
            return Response({"status": "error", "message": "No waste records found"})

        main_id = generate_unique_id("wcm")
        now = timezone.now()

        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO waste_collection_main
                (unique_id, screen_unique_id, collected_time, created,
                 total_waste_collected, entry_type, customer_id, is_deleted)
                VALUES (%s,%s,%s,%s,%s,%s,%s,0)
            """, [main_id, screen_id, now, now, total, entry_type, customer_id])

        with connection.cursor() as cursor:
            cursor.execute("""
                UPDATE waste_collection_sub
                SET form_unique_id=%s
                WHERE screen_unique_id=%s AND customer_id=%s AND is_deleted=0
            """, [main_id, screen_id, customer_id])

        return Response({
            "status": "success",
            "main_unique_id": main_id,
            "total_weight": float(total),
            "collected_time": now
        })

    # ----------------- UPDATE WASTE SUB -----------------
    @action(detail=False, methods=["post"], url_path="update-waste-sub")
    def update_waste_sub(self, request):
        record_id = request.data.get("unique_id") or request.data.get("id")
        weight = request.data.get("weight")
        latitude = request.data.get("latitude")
        longitude = request.data.get("longitude")

        if not record_id:
            return Response({"status": "error", "message": "Missing unique_id"}, status=400)

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT unique_id
                FROM waste_collection_sub
                WHERE unique_id=%s AND is_deleted=0
            """, [record_id])
            row = cursor.fetchone()

        if row is None:
            return Response({"status": "error", "message": f"No matching record found for unique_id {record_id}"}, status=400)

        image_path = None
        if "image" in request.FILES:
            image_path = upload_image(request.FILES["image"])

        now = timezone.now()

        sql = """
            UPDATE waste_collection_sub
            SET weight=%s, latitude=%s, longitude=%s, date_time=%s
        """
        params = [weight, latitude, longitude, now]

        if image_path:
            sql += ", image=%s"
            params.append(image_path)

        sql += " WHERE unique_id=%s AND is_deleted=0"
        params.append(record_id)

        with connection.cursor() as cursor:
            cursor.execute(sql, params)

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT unique_id, waste_type_id, image, weight, latitude, longitude
                FROM waste_collection_sub
                WHERE unique_id=%s
            """, [record_id])
            updated = cursor.fetchone()

        return Response({
            "status": "success",
            "message": "Record updated",
            "data": {
                "unique_id": updated[0],
                "waste_type_id": updated[1],
                "image": updated[2],
                "weight": updated[3],
                "latitude": updated[4],
                "longitude": updated[5],
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

        weights = {"wet": 0.0, "dry": 0.0, "mixed": 0.0}
        params = []
        date_filter = ""

        if start and end:
            date_filter = " AND date_time >= %s AND date_time < %s"
            params.extend([start, end])

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT waste_type_id, COALESCE(SUM(weight), 0)
                FROM waste_collection_sub
                WHERE is_deleted=0 {date_filter}
                GROUP BY waste_type_id
            """,
                params,
            )
            rows = cursor.fetchall()

        for waste_type_id, total in rows:
            key = str(waste_type_id)
            total_value = float(total or 0)
            if key == "1":
                weights["wet"] = total_value
            elif key == "2":
                weights["dry"] = total_value
            else:
                weights["mixed"] += total_value

        trips_params = []
        trips_filter = ""
        if start and end:
            trips_filter = " AND collected_time >= %s AND collected_time < %s"
            trips_params.extend([start, end])

        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT COUNT(*)
                FROM waste_collection_main
                WHERE is_deleted=0 {trips_filter}
            """,
                trips_params,
            )
            trips_row = cursor.fetchone()

        total_trip = int(trips_row[0]) if trips_row and trips_row[0] is not None else 0
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
