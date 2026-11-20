# Situation Monitor

A private, local dashboard of what is moving on X.

The overview is X's own trend list for the world and for the United States, plus posts from the public trending timeline. Each field lane follows a small set of public accounts and ranks their original posts by engagement and recency:

- Neuroscience
- Cybersecurity
- Chemistry
- Biology
- Drug development
- Physics
- App development, with launch language ranked higher
- Robotics
- AI
- Startups
- New startups, with launch and first-announcement language ranked higher

Lanes also surface any current worldwide or US trend whose name matches the field.

## Run

```bash
python3 server.py
```

Opens [http://127.0.0.1:8787](http://127.0.0.1:8787). Python 3.11 or newer, standard library only. The server listens on localhost.

`/` focuses the filter. `r` refreshes the view you are on. Lists are cached for a few minutes so moving between lanes does not reread X.

To change who a lane follows, edit `monitor/lanes.py`.

## Optional X API token

The account feeds and trend lists work with no key. A bearer token from the [X developer console](https://developer.x.com) adds post counts on the trend lists, X News stories, and a platform-wide recent search inside each lane.

```bash
cp .env.example .env
```

Put the token in `.env` as `X_BEARER_TOKEN`. The file stays out of git.

## Checks

```bash
python3 server.py --check
```

Reads the live trend lists and the AI lane once, then exits.

X changes its logged-out web client from time to time. If a lane comes back empty and the warning mentions a query id, update `USER_TWEETS` and `TRENDING` in `monitor/xclient.py`. Those ids were verified on 2026-11-19.
