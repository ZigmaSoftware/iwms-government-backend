
Before reading the task, my core motive is to create a dynamic heirarchy model with permission, view and action assignable forms and launch it as a completely configurable project. I want forms that decide heirarchy. 
Carefully plan this first and make it fully functional and userfuul. 



Task:
I want a form where I can CRUD constants like "state", "city" etc, There is a form for entering variables to this "tamilnadu" but  if I want to create a constant "ward"/"zone" I need a form.
IWMS Enhancement: Trip Point Management & Automated Daily Job Scheduler
Objective
Enhance the IWMS Trip Planning module to support automatic generation of daily operational data based on predefined Trip Plans. The system should support Urban and Rural administrative hierarchies, multiple collection types, and automated daily scheduling.

1. Rename Existing Module
Rename the following modules throughout the application (Frontend, Backend, APIs, Database labels, Navigation, Reports, and Permissions):

Trip Plan Collection Points → Trip Points

Daily Trip Collection Points → Daily Trip Points

The Trip Points module should represent only Secondary Collection Points.

2. Collection Categories
The system should support three different operational categories.

Secondary Collection Points

Household Collection

Bulk Waste Collection

Each Trip Plan must belong to one of these categories.

3. Administrative Hierarchy
The Trip Plan should be created using the following hierarchy.

State
    ↓
District
    ↓
Area Type
Area Type has two options:

Urban

Rural

Urban Hierarchy
If Area Type = Urban

Display

Corporation
Municipality
Town Panchayat
Only one of the above can be selected.

Rural Hierarchy
If Area Type = Rural

Display

Panchayat Union
Panchayat
Only one of the above can be selected.

The UI should dynamically display only the relevant fields depending on the selected Area Type.

4. Collection Type Selection
After selecting the administrative hierarchy, the user should select the Collection Type.

Options:

Secondary Collection Point

Household

Bulk Waste Collection

The remaining fields should change based on this selection.

Secondary Collection Point
Display only Secondary Collection Points belonging to the selected administrative area.

These will become Trip Points.

Household
Display Household locations within the selected administrative area.

Bulk Waste Collection
Display Bulk Waste Collection locations within the selected administrative area.

5. Geo Mapping
Every master entity already contains Geo Coordinates.

Examples:

Corporation

Municipality

Town Panchayat

Panchayat Union

Panchayat

Secondary Collection Point

Household

Bulk Waste Collection

Use these coordinates to:

Display locations on a map.

Validate whether the selected point belongs to the chosen administrative boundary.

Support future route optimization.

6. Designation Assignment
Each Trip Plan should also contain:

Designation

Staff Template

Vehicle Type (if applicable)

Vehicle

Driver

Helper

This determines which workforce executes the trip.

7. Trip Plan Master
The Trip Plan should contain:

Trip Name

Area Type

Administrative Hierarchy

Collection Type

Trip Points

Designation

Staff Template

Vehicle Details

Working Days

Start Time

End Time

Active Status

Once configured, the Trip Plan acts as the master template.

8. Automated Daily Scheduler
Create a background Job Scheduler.

Example:

Run every day at 12:05 AM.

The scheduler should:

Step 1
Find all Active Trip Plans.

Step 2
Check whether the Trip Plan is scheduled for today's weekday.

Step 3
Generate Daily Trip Assignment.

If today's assignment already exists, skip it.

Step 4
Generate Daily Trip Points.

For each generated Daily Trip Assignment:

Copy all configured Trip Points.

Preserve sequence/order.

Mark status as Pending.

Step 5
Generate operational records according to Collection Type.

Secondary Collection Point
Generate Daily Trip Points using Secondary Collection Points.

Household
Generate Daily Household Collection records.

Bulk Waste Collection
Generate Daily Bulk Waste Collection records.

9. Duplicate Prevention
The scheduler must never create duplicate records.

Before inserting:

Check

Trip Plan
+
Operation Date
If records already exist:

Skip generation.

10. Scheduler Configuration
Implement using the existing scheduling framework (Celery Beat, APScheduler, Django-Q, or Cron).

Execution Time:

Every day
12:05 AM
The scheduler should also support manual execution for testing.

11. Database Flow
Trip Plan
        │
        ▼
Daily Job Scheduler
        │
        ▼
Daily Trip Assignment
        │
        ▼
Daily Trip Points
        │
        ├── Secondary Collection Point
        ├── Household Collection
        └── Bulk Waste Collection
12. Future Enhancements
The design should support future additions without schema changes:

GPS Route Optimization

Geo-fencing

Live Vehicle Tracking

Attendance Validation

Missed Collection Alerts

Route Deviation Detection

Automatic Route Assignment

Analytics & Reports

Expected Outcome
Administrators configure each Trip Plan only once.

Every day, the scheduler automatically:

Creates Daily Trip Assignments.

Creates Daily Trip Points.

Generates operational records for Secondary Collection Points, Household Collection, or Bulk Waste Collection.

Prevents duplicate generation.

Uses the configured administrative hierarchy and geo-coordinates.

Produces ready-to-use data for daily field operations.


