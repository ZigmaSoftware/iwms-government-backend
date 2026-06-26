# Dynamic Hierarchy — Walkthrough & Tutorial

This guide explains the new closure-table hierarchy that **replaces the static
geographical masters** (Continent / Country / State / District / Area Type /
Panchayat …). Geography is now *dynamic*: you build the tree yourself and attach
**any master to any node**.

---

## 1. The big picture (mental model)

**Before:** every master had hard-coded geo columns (`state_id`, `district_id`,
`country_id`). Each new client with a different geography meant new
tables/columns.

**Now:** there are just three building blocks:

| Concept | What it is | Example |
|--------|------------|---------|
| **Level** | A tier template | Country, State, District, Ward, Street |
| **Node**  | An actual entry at a level | India, Tamil Nadu, Erode, Ward 12 |
| **Assignment** | Link from any master record → a node | "Sanitation Dept" → Erode |

Nodes are stored in a **closure table**, so every node knows its full ancestry.
Attach a Department to *Erode* and it automatically rolls up to *Tamil Nadu*,
*India*, *Asia* for reporting/filtering/permissions — no extra work.

Three screens under **Masters**:
1. **Hierarchy Tree** — build/edit the tree (create, rename, move, delete nodes; skip levels).
2. **Assign Hierarchy** — attach any master record to any node.
3. **Hierarchy Node** — the per-node detail screen ("This screen shows data of <node>").

---

## 2. Where do I create "Country", "State", "District" now?

> **You no longer create them in separate master screens. They are *nodes* in the Hierarchy Tree.**

### Example: add a new country "Sri Lanka" under Asia
1. Go to **Masters → Hierarchy Tree**.
2. Find **Asia** (a *Continent* node). Hover → click the green **＋ (Add child)**.
3. In the dialog: **Level = Country**, **Name = Sri Lanka**, Save.
4. Done. "Sri Lanka" is now a Country node under Asia. Its closure path is
   `Asia → Sri Lanka`.

### Example: add a state, then a district under it
1. Add child of **Sri Lanka** → Level **State**, Name **Western Province**.
2. Add child of **Western Province** → Level **District**, Name **Colombo**.

### Skip levels (your special requirement)
You can attach a deeper level directly under a shallow one. On **India** (Country),
Add child → Level **Street**, Name **Some Street**. Allowed because *Street*'s
level order is greater than *Country*'s. (You cannot put a shallower level under
a deeper one — that's blocked with a clear error.)

### Editing / moving / deleting
- **Edit** (pencil): rename, change level, toggle active.
- **Delete** (trash): removes the node **and everything beneath it** (confirmation shown). Closure rows are cleaned up automatically.

> Your existing geography was **already mirrored into the tree** by the seeder
> (15 continents, 15 countries, 15 states, 5 districts, area types, panchayats),
> so you start with your real data as nodes.

---

## 3. How do I assign a hierarchy to a master? (the form you asked for)

Go to **Masters → Assign Hierarchy**. Three dropdowns:

1. **Master type** — Department, Designation, Customer, Staff, Panchayat Leader, Bin, Collection Point…
2. **Record** — the specific row (e.g. a specific Department).
3. **Hierarchy node** — any node from the tree (indented to show depth).

Click **Assign**. The right panel shows the record's current assignments with
the full ancestry chain (e.g. `Asia → India → Tamil Nadu → Erode`). Remove an
assignment with the trash icon.

### Worked example
- Master type **Department** → Record **Sanitation** → Node **Erode** → **Assign**.
- Now query the node above it (Tamil Nadu) and "Sanitation" appears, tagged with
  its actual node "Erode" (closure roll-up).

---

## 4. How do I make a NEW master assignable?

One line. Open `app/utils/hierarchy_entities.py` and add to `ASSIGNABLE_ENTITIES`:

```python
"vehicle": {
    "label": "Vehicle",
    "model_path": "app.models.transport_masters.vehicleCreation.VehicleCreation",
    "pk_field": "unique_id",
    "name_attr": "vehicle_number",   # field shown in the dropdown
},
```

It instantly appears in the **Assign Hierarchy** "Master type" dropdown. No model
change, no migration, no frontend change.

---

## 5. API reference (for code / mobile / integrations)

Base: `/api/v1/masters/`

| Purpose | Method & URL |
|--------|--------------|
| List levels | `GET hierarchy-levels/` |
| CRUD a level | `POST/PATCH/DELETE hierarchy-levels/{id}/` |
| The whole tree (nested) | `GET hierarchy-nodes/tree/` |
| Create / move / edit a node | `POST hierarchy-nodes/` · `PATCH hierarchy-nodes/{id}/` |
| Delete a node + subtree | `DELETE hierarchy-nodes/{id}/` |
| A node's ancestry | `GET hierarchy-nodes/{id}/path/` |
| Everything under a node | `GET hierarchy-nodes/{id}/descendants/` |
| Assignable master types | `GET hierarchy-assignments/entity-types/` |
| Records for a master | `GET hierarchy-assignments/entity-records/?entity_type=department` |
| Assign | `POST hierarchy-assignments/` `{ "node": "...", "entity_type": "department", "entity_id": "..." }` |
| What is X attached to | `GET hierarchy-assignments/for-entity/?entity_type=department&entity_id=...` |
| Everything under a node (rolled up) | `GET hierarchy-assignments/under-node/?node=...` |

Every node/level/assignment has a prefixed unique id: `HNODE-…`, `HLVL-…`,
`HASN-…` (consistent with the rest of the project's id scheme).

---

## 6. Migration status & how to finish removing the old tables

This was done as **expand → migrate → contract** so nothing breaks:

- **Expand (done):** new hierarchy + assignment tables; nullable `location_node`
  FK added to CustomerCreation, StaffcreationOfficeDetails, User, PanchayatLeaderLogin.
- **Migrate (done):** `seed --group masters` mirrors all geo rows into nodes and
  backfills `location_node` + assignments. Old geo tables are **untouched** and
  still work, so the app keeps running.
- **Contract (gated — you run when ready):**

```bash
# 1. See whether every dependent has a location_node yet:
python manage.py drop_legacy_geo --check

# 2. Dry run (changes nothing, shows what would happen):
python manage.py drop_legacy_geo

# 3. When you're satisfied, retire the legacy geo rows (soft-delete, reversible):
python manage.py drop_legacy_geo --apply
```

To **physically drop the columns/tables** afterwards (optional, final step):
remove the old `district/state/country` / `district_id` / `panchayat_id` FK
fields from these model files, then `makemigrations && migrate`:
`customers/customercreation.py`, `user_creations/staffcreation.py`,
`superadmin_masters/auth_user.py`, `masters/panchayat_leader_login.py`, and the
geo model files themselves. Until you do that, the old columns simply sit unused.

---

## 7. Re-seeding from scratch

```bash
python manage.py migrate
python manage.py seed --group masters   # mirrors geo → hierarchy, backfills assignments
```

Seeders are idempotent and non-destructive to real geo data. The demo Erode
chain uses separate "Demo …" levels so it never collides with your real geography.
