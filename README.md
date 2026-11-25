# KaubanTa Coalition

Youth-led volunteer site. The pages are hosted on Vercel. Sign-ups, RSVPs, newsletter subscriptions, contact messages, activities, and newsletters are stored in Supabase.

The original single-file prototype is still in this folder. The site that deploys is `site/index.html`.

## 1. Create the Supabase project

1. Create a project at [supabase.com](https://supabase.com).
2. Open **SQL Editor** and run the whole file `supabase/migrations/20261124160000_kaubanta_init.sql`.
3. In **Project Settings → API Keys**, copy the **Project URL** and the **publishable** key.

Use the publishable key only. The secret key can read every signup and must not go in Vercel or in the browser.

Submissions show up in the Supabase **Table Editor**:

| Table | What it stores |
| --- | --- |
| `members` | Volunteer sign-ups |
| `rsvps` | Activity RSVPs (slots decrease automatically) |
| `subscribers` | Newsletter emails |
| `messages` | Contact form |
| `activities` | Current and past volunteer activities |
| `newsletters` | Weekly and monthly issues |
| `site_stats` | The three numbers on the home page |

Edit activities, newsletters, and stats in the table editor. The site reads them on each visit. Visitors can add rows to the form tables and cannot read other people’s submissions.

## 2. Run it on your computer

```powershell
copy .env.example .env
```

Put your Project URL and publishable key in `.env`, then:

```powershell
npm run dev
```

Open http://localhost:3000. Without `.env`, the sample pages still open and the forms explain that the database is not connected.

## 3. Deploy on Vercel

```powershell
npx vercel login
npx vercel link
npx vercel env add SUPABASE_URL production
npx vercel env add SUPABASE_PUBLISHABLE_KEY production
npx vercel --prod
```

Paste the same Project URL and publishable key when Vercel asks. Add both variables to **Production**. Redeploy after changing them, because the live site reads them from Vercel’s environment.

Vercel project settings if you import the folder from the dashboard instead of the CLI:

- Build command: `npm run build`
- Output directory: `dist`
- Environment variables: `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`
