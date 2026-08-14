# OSS LinkedIn Poster

Discover open-source projects and **automatically post** relevant ones to your personal LinkedIn profile every 2–3 days.

**Topics covered:** Data Science, Machine Learning, AI, GenAI, NLP, Research, Audio AI, Vision AI, IoT, Big Data, Open Source.

**Live site (after enabling Pages):**  
https://zuhaibbutt786.github.io/oss-linkedin-poster/

---

## 1. Website (manual discovery + share)

- Search GitHub for OSS projects
- Select → generates LinkedIn-ready text
- Copy or open LinkedIn share dialog

### Enable GitHub Pages
1. Repo → **Settings → Pages**
2. Source: **Deploy from a branch** → `main` / `/ (root)`
3. Save → site goes live in ~1–2 min

---

## 2. Full Automatic Posting (GitHub Actions)

A scheduled workflow runs every **3 days** (or you can trigger it manually) and:

1. Picks a high-quality repo matching your topics
2. Generates a professional post
3. Publishes it to your **personal LinkedIn profile** via the official Posts API

### Setup steps (do this once)

#### A. Get a LinkedIn Access Token with the right scopes

1. Go to [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps) and open (or create) your app.
2. Make sure the product **“Share on LinkedIn”** (and usually **Sign In with LinkedIn**) is enabled.
3. Under **Auth** tab note your **Client ID** and **Client Secret**.
4. Add a redirect URI (e.g. `https://www.linkedin.com/developers/tools/oauth/redirect` or `http://localhost:8080`).
5. Generate an authorization code (3-legged OAuth) with these scopes:
   ```
   w_member_social openid profile email
   ```
6. Exchange the code for an **access token** (and preferably a refresh token if available).

You can use the official LinkedIn OAuth tools or a small script. The access token is what the Action needs.

> **Important:** Regenerate any Client Secret you previously shared publicly.

#### B. Add the token as a GitHub Secret

1. Go to this repo → **Settings → Secrets and variables → Actions**
2. Click **New repository secret**
3. Name: `LINKEDIN_ACCESS_TOKEN`
4. Value: paste your access token
5. Save

#### C. (Optional) Test the workflow

1. Go to **Actions** tab
2. Select **“Auto-post OSS project to LinkedIn”**
3. Click **Run workflow** → **Run workflow**

If everything is configured correctly you will see a successful post on your LinkedIn feed.

### Schedule

- Cron: every 3 days at 09:00 UTC (≈ 2 PM Pakistan time)
- You can change the schedule in `.github/workflows/linkedin-auto-post.yml`

---

## Security reminders

- Never commit the access token or Client Secret to the repository.
- Access tokens expire (typically 60 days). When it expires, generate a new one and update the secret.
- The workflow only has permission to run the Python script and use the secret you provided.

---

## Project structure

```
.
├── index.html          # Frontend website
├── style.css
├── script.js
├── scripts/
│   └── auto_post.py    # The automation script
└── .github/workflows/
    └── linkedin-auto-post.yml
```

---

## License

MIT
