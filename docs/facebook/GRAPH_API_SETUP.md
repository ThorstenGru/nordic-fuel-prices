# One-time setup: let GitHub post for the Page (about 15 minutes, owner only)

After this, GitHub Actions posts every day and answers "comment your town" comments **by itself** — no computer, no Claude app, no person.
Everything is posted with a **Page access token**, so it always comes from the Page "Euro Fuel Prices", never from a person.
The workflow is already installed (`.github/workflows/facebook.yml`); until the two secrets below exist it does nothing.

What only the owner can do (it involves logins and secret keys): create a Meta app, create the token, store it as a GitHub secret.

## 1. Meta developer app (free)
1. https://developers.facebook.com -> log in with the Facebook account that administers the Page -> register as a developer if asked.
2. **My Apps -> Create app** -> name `EuroFuelPrices bot`, use case **Other / Business** (or "Manage everything on your Page"), type **Business**.
   Leave the app in **Development mode**. You are its admin and the Page's admin, so no app review is needed for your own Page.

## 2. Page access token that does not expire
1. https://developers.facebook.com/tools/explorer -> pick your app -> **User Token** -> add permissions:
   `pages_show_list`, `pages_manage_posts`, `pages_read_engagement`, `pages_manage_engagement`, `read_insights` -> **Generate Access Token**,
   approve, and choose the Page **Euro Fuel Prices**.
2. Make a long-lived user token (replace the CAPITALS; App ID and App Secret are under App settings -> Basic; do not share the secret):
   `https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_TOKEN`
3. With the long-lived token open `https://graph.facebook.com/me/accounts?access_token=LONG_USER_TOKEN`. Find the Page "Euro Fuel Prices":
   its `access_token` is the **Page token (it does not expire)**, its `id` is the **Page id**.
4. Check: `https://graph.facebook.com/me?fields=id,name&access_token=PAGE_TOKEN` must answer name "Euro Fuel Prices" and the same id.

## 3. Store both as GitHub secrets
Repository `ThorstenGru/nordic-fuel-prices` -> Settings -> Secrets and variables -> Actions -> **New repository secret**:
- `FB_PAGE_ID` = the Page id from step 2.3
- `FB_PAGE_TOKEN` = the Page token from step 2.3

(or in a terminal: `gh secret set FB_PAGE_ID` and `gh secret set FB_PAGE_TOKEN`, paste when asked). Never put either value in a file or a commit.

## 4. Test, then it runs forever
Actions -> **Facebook — daily post and replies** -> **Run workflow** -> mode `post`, dry run **on**: the log shows the post it would make.
Then run again with dry run **off** (only if today has no post yet). From then on:
- 07:00 UTC daily: the day's post (retry at 11:00 UTC if the first run had to skip); never two posts a day (`docs/facebook/post_log.csv`).
- Every hour at :30: replies to comments on the latest "comment your town" post (Saturdays), at most 15 per run, once per comment.

## 5. Afterwards
Tell Claude "disable the app-based Facebook task" so the old browser task cannot duplicate posts (the log check already prevents duplicates).

## Limits and honest caveats
- Posting to your own Page from an app in Development mode works without review. Reading **other people's comments** (needed for the replies) may be
  restricted until the app passes Meta's review; if replies do nothing, check the Actions log. Posting is unaffected.
- Follower-city insight needs enough followers; until then the town rotates through larger towns. Only aggregate numbers are used.
- Meta can change or retire API fields; if a run fails, the workflow log says why, and the site and the other automation are unaffected.
