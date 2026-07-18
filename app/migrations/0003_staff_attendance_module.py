import django.db.models.deletion
from django.db import migrations, models

import app.models.attendance.daily_attendance_reg


def migrate_attendance_data(apps, schema_editor):
    Staff = apps.get_model("app", "StaffcreationOfficeDetails")
    Employee = apps.get_model("app", "Employee")
    DailyAttendanceReg = apps.get_model("app", "DailyAttendanceReg")

    staff_members = list(Staff.objects.order_by("created_at", "staff_unique_id"))
    for sequence, staff in enumerate(staff_members, start=1):
        staff.emp_id = f"TMP-{sequence:06d}"
        staff.save(update_fields=["emp_id"])

    for sequence, staff in enumerate(staff_members, start=1):
        staff.emp_id = f"EMP-{sequence:06d}"
        registration = Employee.objects.filter(staff_id=staff.pk).first()
        if registration and registration.image_path:
            image_path = registration.image_path
            if not isinstance(image_path, (bytes, bytearray, memoryview)):
                staff.attendance_reg_image = str(image_path)
        staff.save(update_fields=["emp_id", "attendance_reg_image"])

    employee_ids = dict(Staff.objects.values_list("staff_unique_id", "emp_id"))
    for record in DailyAttendanceReg.objects.all().iterator():
        record.emp_id = employee_ids.get(record.staff_id, record.emp_id)
        record.save(update_fields=["emp_id"])


class Migration(migrations.Migration):
    dependencies = [("app", "0002_remove_tripplan_property_id_and_more")]

    operations = [
        migrations.AddField(
            model_name="staffcreationofficedetails",
            name="attendance_reg_image",
            field=models.ImageField(
                blank=True,
                help_text="Reference face image used for attendance recognition.",
                null=True,
                upload_to="attendance/registration/",
            ),
        ),
        migrations.AlterField(
            model_name="staffcreationofficedetails",
            name="emp_id",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=10,
                null=True,
                unique=True,
            ),
        ),
        migrations.AlterField(
            model_name="userscreen",
            name="model_name",
            field=models.CharField(
                blank=True,
                help_text="Django model name. Example: StaffcreationOfficeDetails",
                max_length=100,
                null=True,
            ),
        ),
        migrations.RenameModel(
            old_name="Recognized",
            new_name="DailyAttendanceReg",
        ),
        migrations.AlterModelTable(
            name="dailyattendancereg",
            table="app_trip_attendance",
        ),
        migrations.AlterModelOptions(
            name="dailyattendancereg",
            options={"ordering": ["-records"]},
        ),
        migrations.AlterField(
            model_name="dailyattendancereg",
            name="unique_id",
            field=models.CharField(
                default=app.models.attendance.daily_attendance_reg.generate_daily_attendance_reg_id,
                editable=False,
                max_length=30,
                primary_key=True,
                serialize=False,
            ),
        ),
        migrations.AlterField(
            model_name="dailyattendancereg",
            name="emp_id",
            field=models.CharField(max_length=10),
        ),
        migrations.AlterField(
            model_name="dailyattendancereg",
            name="emp_id_raw",
            field=models.CharField(blank=True, max_length=50, null=True),
        ),
        migrations.AlterField(
            model_name="dailyattendancereg",
            name="staff",
            field=models.ForeignKey(
                db_column="staff_id",
                on_delete=django.db.models.deletion.PROTECT,
                related_name="daily_attendance_regs",
                to="app.staffcreationofficedetails",
            ),
        ),
        migrations.RemoveIndex(
            model_name="dailyattendancereg",
            name="app_recogni_emp_id_d0de10_idx",
        ),
        migrations.RemoveIndex(
            model_name="dailyattendancereg",
            name="app_recogni_staff_i_6bffac_idx",
        ),
        migrations.AddIndex(
            model_name="dailyattendancereg",
            index=models.Index(fields=["emp_id"], name="app_trip_at_emp_id_c6d336_idx"),
        ),
        migrations.AddIndex(
            model_name="dailyattendancereg",
            index=models.Index(fields=["staff"], name="app_trip_at_staff_i_b82dc0_idx"),
        ),
        migrations.AddIndex(
            model_name="dailyattendancereg",
            index=models.Index(
                fields=["recognition_date", "punch_type"],
                name="app_trip_at_recogni_29d493_idx",
            ),
        ),
        migrations.RunPython(migrate_attendance_data, migrations.RunPython.noop),
        migrations.DeleteModel(name="Employee"),
    ]
