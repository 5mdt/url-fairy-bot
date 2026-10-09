# UFB-0058. Reddit account login for gated content

**Tags:** #reddit #download #config

## User Story

As an operator, I want the bot to read Reddit as a dedicated account, so that NSFW and quarantined posts, comments and subreddits that app-only access hides get a native reply too.

## Behavior

[UFB-0057](UFB-0057-reddit-links.md) reads Reddit with app-only OAuth, a logged-out view: NSFW-gated content is hidden and quarantined subreddits are refused. This feature adds an opt-in account login.

| Settings                                          | Reddit is read as                                                 |
|---------------------------------------------------|-------------------------------------------------------------------|
| `REDDIT_CLIENT_ID` + `REDDIT_CLIENT_SECRET`       | the app, logged out (today, [UFB-0057](UFB-0057-reddit-links.md)) |
| the above + `REDDIT_USERNAME` + `REDDIT_PASSWORD` | that account (`password` grant)                                   |
| `REDDIT_USERNAME` or `REDDIT_PASSWORD` alone      | ignored, with a startup warning; app-only login stays             |
| none of the above                                 | cookies, then anonymous (unchanged)                               |

What the account sees depends on its own Reddit settings: "Show mature content" must be on, and each quarantined subreddit must be opted in once through the website. Content it still cannot see falls back to the mirror link ([UFB-0013](UFB-0013-download-failure-fallback.md)). Replies look exactly as in [UFB-0057](UFB-0057-reddit-links.md); only reading changes. The bot never posts, votes or messages as the account.

## Implementation

- `app/config.py`: `REDDIT_USERNAME`, `REDDIT_PASSWORD` (empty by default); both are passed through `docker-compose.yml`, `.env.example` and the README.
- `app.reddit._token` requests `grant_type=password` with the username and password when both are set, else `client_credentials`. The cached token is keyed by grant, so changing the settings never reuses the other kind. A 401 still triggers one refresh ([UFB-0057](UFB-0057-reddit-links.md)); a failed password login raises `RedditError`, so links fall back to the mirror.
- The account needs a Reddit "script" app (the app owner's own account only), and no two-factor authentication.
- `docs/reddit-setup.md` gets an "NSFW and quarantined content" section; the registration text must say the app acts as an account.

## Quirks & Decisions

- Quirk: the bot stores a Reddit password in `.env`. Decision: document using a dedicated throwaway account, never a personal one.
- Quirk: an account with two-factor authentication cannot use the password grant. Open: support `password:otp` or a refresh token instead.
- Quirk: the account's mature-content and quarantine opt-ins live on Reddit, so the bot cannot check them. Decision: a hidden post is treated like any other Reddit refusal (mirror fallback).
- Quirk: cookies from the same account already unlock gated content ([UFB-0057](UFB-0057-reddit-links.md), cookie option), but expire. Decision: this feature is the stable alternative, not a replacement.

## Testing

### Human

- Set the account variables, then send an NSFW post and a quarantined subreddit link. Each gets a native reply.
- Set a wrong password. Reddit links fall back to the mirror link and the log shows the failed login.

### Unit

- Both variables set requests the `password` grant with the right form fields; otherwise `client_credentials`.
- Only one of the two variables set uses app-only.
- A cached token is not reused across grants.
- A refused password login raises `RedditError`.

### Integration

- A gated post that app-only access refuses is read when the account is configured.

## Status

Planned
