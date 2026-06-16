import datetime
import os
import random
import string
from app.utils.base_models import BaseMaster
from django.conf import settings
from django.db import models
from app.models.superadmin_masters.company import Company
from app.models.superadmin_masters.project import Project



def generate_unique_id(prefix):
    year = datetime.datetime.now().strftime("%Y")
    chars = string.ascii_lowercase + string.digits
    rand = "".join(random.choice(chars) for _ in range(10))
    sec = datetime.datetime.now().strftime("%S")
    return f"{prefix}{year}{rand}{sec}".lower()


def generate_waste_type_id():
    return generate_unique_id("wst-")


def generate_waste_collection_sub_id():
    return generate_unique_id("wcs-")


def generate_waste_collection_main_id():
    return generate_unique_id("wcm-")


def upload_image(image):
    upload_path = os.path.join(settings.MEDIA_ROOT, "waste_collection_images")
    os.makedirs(upload_path, exist_ok=True)

    filename = f"{datetime.datetime.now().timestamp()}_{image.name}"
    fullpath = os.path.join(upload_path, filename)

    with open(fullpath, "wb") as f:
        for chunk in image.chunks():
            f.write(chunk)

    return f"uploads/waste_collection_images/{filename}"


class WasteType(BaseMaster,models.Model):
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="project_id",
    )
    unique_id = models.CharField(
        max_length=100,
        primary_key=True,
        default=generate_waste_type_id,
        editable=False,
    )
    waste_type_name = models.CharField(max_length=255)
    is_deleted = models.BooleanField(default=False)


class WasteCollectionSub(models.Model):
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="project_id",
    )
    unique_id = models.CharField(
        max_length=100,
        primary_key=True,
        default=generate_waste_collection_sub_id,
        editable=False,
    )
    screen_unique_id = models.CharField(max_length=100)
    customer_id = models.CharField(max_length=100)
    waste_type_id = models.CharField(max_length=100)
    image = models.CharField(max_length=255, null=True, blank=True)
    weight = models.FloatField(default=0)
    latitude = models.CharField(max_length=100, null=True, blank=True)
    longitude = models.CharField(max_length=100, null=True, blank=True)
    form_unique_id = models.CharField(max_length=100, null=True, blank=True)
    is_deleted = models.BooleanField(default=False)
    date_time = models.DateTimeField(auto_now=True)



class WasteCollectionMain(models.Model):
    company_id = models.ForeignKey(
        Company,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="company_id",
    )
    project_id = models.ForeignKey(
        Project,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        db_column="project_id",
    )
    unique_id = models.CharField(
        max_length=100,
        primary_key=True,
        default=generate_waste_collection_main_id,
        editable=False,
    )
    screen_unique_id = models.CharField(max_length=100)
    collected_time = models.DateTimeField()
    created = models.DateTimeField()
    total_waste_collected = models.FloatField(default=0)
    entry_type = models.CharField(max_length=20, default="app")
    customer_id = models.CharField(max_length=100)
    is_deleted = models.BooleanField(default=False)
