"""
Script to clean up binary data in Employee image_path and qr_code_path fields.
Run this with: python manage.py shell < clean_employee_paths.py
Or: python manage.py shell
Then: exec(open('clean_employee_paths.py').read())
"""

from app.models.user_creations.attendance import Employee

print("Starting cleanup of Employee image_path and qr_code_path fields...")

cleaned_count = 0
total_count = Employee.objects.count()

for e in Employee.objects.all():
    updated = False
    
    if isinstance(e.image_path, (bytes, bytearray, memoryview)):
        e.image_path = ""  # or None if field allows
        updated = True
        print(f"Cleaning image_path for Employee ID: {e.unique_id}")
    
    if isinstance(e.qr_code_path, (bytes, bytearray, memoryview)):
        e.qr_code_path = ""
        updated = True
        print(f"Cleaning qr_code_path for Employee ID: {e.unique_id}")
    
    if updated:
        e.save(update_fields=["image_path", "qr_code_path"])
        cleaned_count += 1

print(f"\nCleanup completed!")
print(f"Total employees: {total_count}")
print(f"Employees cleaned: {cleaned_count}")
