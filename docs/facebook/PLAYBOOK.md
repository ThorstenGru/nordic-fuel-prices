# Daily Facebook post: playbook (standing OK from the owner, 2026-11-11)

> **Status:** the primary route is now the GitHub Actions routine (`.github/workflows/facebook.yml`, see GRAPH_API_SETUP.md and docs/ARCHITECTURE.md). This browser-based playbook belongs to the Claude-app task, which is **disabled**; it is kept as a documented fallback and its rules (one post a day, only as the Page, no ads/boost/tags/replies except the town replies of the bot) still apply to any manual or fallback posting.

Page: **Euro Fuel Prices**, https://www.facebook.com/eurofuelprices (admin is the owner's logged-in Chrome profile).
Scope of the standing OK: **one public post per day**, produced by `tools/fb_daily.py`, nothing else. No ads, no boosts, no invitations,
no messages, no personal data, no changes to Page settings, no replies to people (see "Comments").

## Each run
1. `cd "C:\Users\thgrund\OneDrive - Digia\Desktop\Claude Code Folder\EuroFuelPrices"`, run `git pull --rebase origin main` (GitHub may already have posted today), then `python tools/fb_daily.py`.
   NOTE: this browser route is only the stop-gap until the GitHub route (docs/facebook/GRAPH_API_SETUP.md) has its secrets; then this task is disabled.
2. It prints one JSON line. If it contains `"skip"`: do **not** post. Append `date,skip,<reason>` to `docs/facebook/post_log.csv` and finish with a one-line report.
3. Otherwise post exactly `text` with the picture at `image` (do not edit the wording; do not add hashtags or tags).
   Using the Claude in Chrome tools (load them with ToolSearch if deferred):
   - `tabs_context_mcp` (createIfEmpty), open `https://www.facebook.com/eurofuelprices` in the MCP tab.
   - If the page shows "Switch Now" (viewing as the owner's personal profile), click it to switch into the Page, then wait.
     The composer **must** say "Euro Fuel Prices" and "Public"; if it shows the owner's personal name, stop (never post as the person).
   - Click "What's on your mind?" to open "Create post".
   - Click "Photo/video" in the dialog, `find` the file inputs, `file_upload` the image to the one inside "Create post" (tested 2026-11-11).
   - Type the text into the post box, click **Next**, check "Post audience: Public", "Publish now", **Boost post off**, click **Post**.
   - Confirm on the timeline that the post with today's text exists ("Just now").
4. Append `date,format,key` to `docs/facebook/post_log.csv` (header: `date,format,key`), then `git add` that file, commit
   ("Facebook post log <date>") and push to main.
5. Report in 2-3 lines: what was posted (text), and the number of new comments if visible (do not answer them).

## Stop conditions (post nothing, log `skip`, report)
- Facebook asks to log in, shows a checkpoint, captcha, identity or payment/ads prompt, or the composer is not "Euro Fuel Prices".
- The script says skip, or two attempts to post fail, or a post for today already exists on the timeline.
- Anything unexpected: never improvise; never click Advertise/Boost/Create ad.

## Comments
Do not reply automatically. The report lists how many new comments there are; the owner decides replies
(drafts can be prepared on request). Never delete or hide comments.

## Content rules (enforced by the script)
One post per day; weekday plan Mon ranking, Tue border pair, Wed quiz, Thu feature tip, Fri local spotlight (cheapest within 10 km of a town), Sat "comment your town" (answered by the GitHub bot),
Sun feature tip. Country medians with >= 300 priced stations are quoted (grade D too, marked as estimates), always as
"median station price", with a note when the source is unofficial. No "like/share" bait. Pairs/features are not repeated within 14 days.
