# Setting up Reddit access

Operator runbook for [UFB-0057](features/UFB-0057-reddit-links.md). Skip it and nothing breaks: Reddit links fall back to the mirror link ([UFB-0013](features/UFB-0013-download-failure-fallback.md)).

## Overview

Reddit blocks anonymous API access, so the bot needs one of these (tried in this order):

| Option                              | Setup effort                          | Notes                                                                     |
|-------------------------------------|---------------------------------------|---------------------------------------------------------------------------|
| 1. OAuth app (client id + secret)   | Create an app, maybe request approval | Recommended. Read-only, no account password stored, no session to expire. |
| 2. Cookies from a logged-in browser | Export a cookies file                 | No Reddit approval needed, but tied to an account and expires.            |
| 3. Nothing                          | none                                  | Reddit usually answers 403; every link uses the mirror fallback.          |

## Option 1: OAuth app

1. **Register for API use first.** Reddit requires it before an app can be created: read the [Responsible Builder Policy](https://support.reddithelp.com/hc/en-us/articles/42728983564564-Responsible-Builder-Policy) and submit the access request it links to (describe it as a personal, read-only, low-volume Telegram link-preview bot). Approval is not instant. Until it is granted, use option 2.
2. Log in to Reddit with the account that will own the app (a dedicated account is cleaner).
3. Open https://www.reddit.com/prefs/apps. The form says "By creating an app, you agree to Reddit's Developer Terms and Data API Terms. You must also register to use the API."
4. Fill in the form:

   | Field        | Value                                                                                                                             |
   |--------------|-----------------------------------------------------------------------------------------------------------------------------------|
   | name         | anything, e.g. `url-fairy-bot`                                                                                                    |
   | type         | **web app**. Not "installed app" (no secret). "script" also works for the bot's app-only login, but is meant for personal scripts |
   | description  | optional                                                                                                                          |
   | about url    | optional                                                                                                                          |
   | redirect uri | required but unused: `http://localhost:8080`                                                                                      |

5. Click **create app**. The card now shows:
   - the **client id**: the short string right under the app name and the words "web app";
   - the **secret**: the line labeled `secret`.
6. Put them in `.env`:

   ```dotenv
   REDDIT_CLIENT_ID=<client id>
   REDDIT_CLIENT_SECRET=<secret>
   # Optional. Reddit asks for a unique, descriptive User-Agent:
   REDDIT_USER_AGENT=url-fairy-bot/1.0 (by u/<your reddit name>)
   ```

7. Restart the bot (`make docker-restart`) and send it a Reddit link.

If **create app** is refused, registration (step 1) has not been approved yet.

The bot uses the app-only `client_credentials` grant: it can read public content only, never acts as your account, and needs no redirect flow. Private, quarantined and NSFW-gated content stays unavailable and falls back to the mirror link.

## Option 2: cookies

1. Log in to reddit.com in a browser.
2. Export the cookies for `reddit.com` in Netscape format (a browser extension such as "Get cookies.txt LOCALLY").
3. Save them as `cookies-reddit.txt` (any `cookies*.txt`) in `COOKIES_DIR` (default `/config/`), next to any existing cookie files. See [Cookie Support](../README.md#cookie-support) for how the files are merged.
4. Leave `REDDIT_CLIENT_ID` / `REDDIT_CLIENT_SECRET` empty.

With `COOKIE_JAR_ENABLED=true` the cookie keepalive ([UFB-0038](features/UFB-0038-cookie-keepalive.md)) checks the Reddit session every `COOKIE_KEEPALIVE_INTERVAL` seconds, saves the cookies Reddit refreshes, and the bot reads them from the jar. A session Reddit has ended (logged out, password changed) still needs a fresh export, and `/health` reports it when `COOKIE_HEALTHCHECK=true`. Without the jar the bot reads `cookies*.txt` as they are, so re-export when Reddit links start falling back to the mirror.

## Check it works

1. Send the bot a post link such as `https://www.reddit.com/r/deckyloader/comments/1wzj4zm/`.
2. A reply with the title, a clickable `👤 u/author` and the text means the API answered. A plain mirror link (`rxddit.com`) means it did not.
3. If it did not, set `LOG_LEVEL=DEBUG` and look for `Reddit answered 401/403/429`: 401 = wrong id or secret, 403 = blocked or no approval, 429 = rate limited.
