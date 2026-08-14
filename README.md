# OSS LinkedIn Poster

A simple static website that discovers open-source projects on GitHub and helps you share them on LinkedIn.

**Live site (after enabling Pages):**  
https://zuhaibbutt786.github.io/oss-linkedin-poster/

## Features

- Search GitHub repositories (stars, language, keywords)
- Clean cards with stars, forks, language and description
- One-click “Select for LinkedIn” → generates a ready-to-post text
- Copy text + open LinkedIn’s official share dialog
- Fully static → free hosting on GitHub Pages

## How to enable GitHub Pages

1. Go to the repository **Settings → Pages**
2. Under **Source** choose **Deploy from a branch**
3. Branch: `main` / folder: `/ (root)`
4. Save. The site will be live in 1–2 minutes at  
   `https://zuhaibbutt786.github.io/oss-linkedin-poster/`

## Important Security Notes (please read)

You previously shared a LinkedIn **Client ID** and what looks like a **Client Secret / token** in chat.

1. **Immediately regenerate** the Client Secret in the [LinkedIn Developer Portal](https://www.linkedin.com/developers/apps).
2. **Never** put Client Secret or Access Tokens in frontend JavaScript or a public GitHub repository.
3. GitHub Pages is static only. Full automatic posting (background jobs, scheduled posts) requires a backend or GitHub Actions + repository secrets.

### For real automation (recommended next steps)

- Use **GitHub Actions** with secrets (`LINKEDIN_ACCESS_TOKEN`, etc.) to post on a schedule.
- Or deploy a small serverless function (Vercel / Netlify / Cloudflare Workers) that keeps the secret server-side and uses LinkedIn’s Posts API (`/rest/posts`).
- Required LinkedIn products & scopes usually include “Share on LinkedIn” + `w_member_social` (or organization scopes for company pages).

This website intentionally uses only the public LinkedIn share URL so it is safe to host publicly.

## Local development

Just open `index.html` in a browser or use any static server:

```bash
npx serve .
```

## License

MIT – feel free to fork and improve.
