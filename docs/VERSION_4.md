# SSRI Version 4

Version 4 adds accounts, dataset history, and an admin view around the existing Stage 2.5 trainer. It does not replace inference, jobs, or the model.

## What talks to what

- **Supabase Auth** is the only end-user identity. Passwords stay in Supabase.
- **Supabase Postgres + RLS** (`supabase/migrations/20260929000000_platform_v4.sql`) holds profiles, datasets, versions, training runs, models, and activities.
- **SSRI API** `/api/v1/platform/*` validates uploads and queues training on the existing job executor and `Trainer`.
- The **assessment map** stays at `/dashboard`. The signed-in home is `/workspace`.

## Local setup

1. Create a Supabase project and run the migration SQL.
2. Create a private Storage bucket named `datasets` if the migration's storage policies did not apply (local SQL editors sometimes skip `storage`).
3. Copy placeholders into `.env` (server) and `frontend/.env.local` (browser):

```
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Never commit `SUPABASE_SERVICE_ROLE_KEY`.

4. Grant an admin in SQL, not in the app:

```sql
update public.profiles set role = 'admin' where email = 'you@example.com';
```

5. Start the API from `model/` and the frontend from `frontend/`.

Unit tests use an in-memory store and do not call your Supabase project:

```bash
cd model
poetry run pytest tests/test_platform_v4.py tests/test_manual_training.py tests/test_api_assess.py
```

## Product limits

- Uploads must be a Stage 2.5 dataset zip (13 channels, labels, manifest). Aeromagnetic or survey rasters are accepted only when they already match that contract. Screenshots are not training data.
- A completed run is `NOT_VALIDATED`. It does not replace the assessment checkpoint unless an operator promotes it.
- New dataset uploads create a new version. They do not overwrite the previous file.
