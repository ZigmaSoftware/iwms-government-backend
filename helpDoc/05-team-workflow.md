# 05 — Team Workflow

## The one thing that trips everyone up

Git carries **code**. It does not carry **your database**.

Because migration files are not tracked (see
[02-database-and-env.md](02-database-and-env.md)), pulling a colleague's new
model gives you the Python class but **not** the table. Your machine will
raise `Table 'iwmsdbGovernment.app_xyz' doesn't exist` until you generate
and apply migrations yourself.

So the rule is:

> **After every `git pull`, run `makemigrations` + `migrate`.**
> If the change adds new reference data, also run the matching `seed --group`.

## The overall flow

```text
        DEVELOPER A (builds it)                DEVELOPER B (receives it)
        ───────────────────────                ─────────────────────────

   1. git pull
      makemigrations + migrate
           │
           ▼
   2. write the feature
      model → serializer → viewset
      → register_group → seeder → tests
           │
           ▼
   3. makemigrations app
      migrate                  ┄┄┄┄┄┄▶ creates the table in A's OWN database
           │                                  (this file is NOT committed)
           ▼
   4. pytest + runserver
      check it in Swagger
           │
           ▼
   5. git status  ← READ IT
      git add app/ tests/
      git commit
           │
           ▼
   6. git push ──────────────┐
      PR says which migrate/ │
      seed steps are needed  │
                             │
             ┌───────────────┘
             │   ONLY these travel:
             │   models, serializers,
             │   viewsets, urls, seeders,
             │   tests, settings
             │
             │   These do NOT travel:
             │   migration files, .env,
             │   the database, its rows
             │
             ▼
                                    7. git pull
                                          │
                                          ▼
                                    8. makemigrations app
                                       migrate        ┄┄┄┄▶ NOW the table
                                          │                 exists for B
                                          ▼
                                    9. seed --group <group>
                                       (only if new reference data)
                                          │
                                          ▼
                                   10. it finally works
```

The gap between steps 6 and 8 is where every "but it works on my machine"
in this repo comes from — and this repo has a live example of what happens
when that gap goes unnoticed for too long: two different, differently-named
`0002_...` migration files currently sit on disk because two developers'
local migration graphs diverged (see [02](02-database-and-env.md)).

Two practical consequences:

- **Never assume a pull is enough.** Steps 8 and 9 are yours to run, every
  time, not just when something looks broken.
- **Say so in the PR.** You are the only one who knows whether your change
  needs a plain `migrate` or also a `seed --group customer-masters`. Write
  it in the description.

## Day-to-day: building a feature

```bash
# 1. Start from the latest code
git pull

# 2. Bring your database in line with it
python3 manage.py makemigrations app
python3 manage.py migrate

# 3. Branch
git checkout -b feature/village-master

# 4. Build it — model, serializer, viewset, one register_group line
#    (see 03-app-structure.md for the folder layout — remember the
#    two-tier superadmin/<subfolder> masters/<subfolder> nesting)

# 5. Create the tables for what you just wrote
python3 manage.py makemigrations app
python3 manage.py migrate

# 6. Test it
python -m pytest tests/ -q
python3 manage.py runserver     # check it in Swagger

# 7. Commit — code only. Never .env, never migrations, never __pycache__.
git add app/ tests/
git status                      # READ THIS before committing
git commit -m "Add village master"
git push -u origin feature/village-master
```

Step 7 matters. Run `git status` and actually look at it. If `.env`,
`coverage.xml`, or a `__pycache__` folder appears in the list, something is
wrong with the ignore rules — fix that rather than committing around it. See
[06-gitignore-and-secrets.md](06-gitignore-and-secrets.md) — this repo has
already had `.env` committed once.

## What your teammates must do after you push

```bash
git pull
python3 manage.py makemigrations app
python3 manage.py migrate
```

And, if the feature ships new reference data:

```bash
python3 manage.py seed --group masters   # whichever group you added a seeder to
```

Tell people in the PR description which `seed --group` to run.

## Adding a seeder

1. Write the seeder under
   `app/management/commands/seeders/<group>/<subfolder>/<thing>.py`,
   mirroring the model/serializer/viewset nesting for that group (see
   [03-app-structure.md](03-app-structure.md)).
2. Register it in `app/management/commands/seed.py` — add it to the right
   group's seeder list. Placement matters: check the notes in
   [04-commands-reference.md](04-commands-reference.md) about the
   hand-curated `--group all` ordering (it is not simply `ORDERED_GROUPS`
   flattened; some seeders are deliberately interleaved).
3. Verify from empty:
   ```bash
   python3 manage.py seed --group <your-group>
   ```
4. Seeders must be safe to run twice. Use get-or-create semantics rather
   than blind inserts — people re-run `seed` constantly.

## Changing a model that already has data

Local development: dropping and rebuilding is the normal move (see
[02](02-database-and-env.md)).

Anywhere with real data, that is not available. Because migrations are not
in git, a destructive schema change on a live database needs a deliberate
plan — write the SQL, back up first, and agree it with the team before
running anything.

## Renaming and legacy aliases

Several groups have aliases (`assets` → `waste-types`, `schedule-masters` →
`schedule-setup` + `schedule-operations`, and others). The old names are
kept working in `seed.py` and `base_urls.py` (the `schedule-masters` /
`reports` URL groups are literal duplicate registrations of the same
viewsets under old names) so existing notes, scripts and the seeded
MainScreen data keep working. When you rename something, keep the old alias
for a while rather than breaking everyone's muscle memory in one commit.

## Branch and commit conventions

- Branch off the current main branch; do not commit directly to it.
- One feature per branch, one clear purpose per commit.
- Commit messages describe the change, not the file list.
- Push the branch and open a PR. Say in the description what the reviewer
  must run (`migrate`? which `seed --group`?).

## Before you push — checklist

- [ ] `git status` shows only source files you meant to change
- [ ] No `.env`, no `__pycache__`, no `coverage.xml`
- [ ] No credentials, tokens, IPs or passwords in the code or comments
- [ ] `python -m pytest tests/ -q` passes
- [ ] New master table? A seeder exists and runs clean twice
- [ ] The PR description names the migrate/seed steps for reviewers

Next: [06-gitignore-and-secrets.md](06-gitignore-and-secrets.md).
