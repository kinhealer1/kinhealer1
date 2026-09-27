"""Upload to YouTube with the free YouTube Data API v3.

One-time setup (free): create an OAuth "Desktop app" client in Google Cloud,
then run `python -m faceless auth client_secret.json` on your own computer to
get a refresh token. Store YT_CLIENT_ID, YT_CLIENT_SECRET and YT_REFRESH_TOKEN
as GitHub secrets.

Default quota is 10,000 units/day; one upload costs ~1,600, so ~6 videos/day max.
"""
import os

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def authorize(client_secret_file):
    from google_auth_oauthlib.flow import InstalledAppFlow

    flow = InstalledAppFlow.from_client_secrets_file(client_secret_file, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")
    print("\nAdd these as GitHub repository secrets:\n")
    print(f"YT_CLIENT_ID={creds.client_id}")
    print(f"YT_CLIENT_SECRET={creds.client_secret}")
    print(f"YT_REFRESH_TOKEN={creds.refresh_token}")


def _client():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        None,
        refresh_token=os.environ["YT_REFRESH_TOKEN"],
        client_id=os.environ["YT_CLIENT_ID"],
        client_secret=os.environ["YT_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def upload(video, script, cfg):
    from googleapiclient.http import MediaFileUpload

    title = script["title"][:100]
    description = script["description"]
    tags = list(dict.fromkeys(t[:30] for t in script.get("tags", [])))[:15]
    if cfg["format"] == "short":
        title = title if "#shorts" in title.lower() or len(title) > 90 else f"{title} #shorts"
        description += "\n\n#shorts"
    body = {
        "snippet": {"title": title, "description": description, "tags": tags, "categoryId": str(cfg["category_id"])},
        "status": {
            "privacyStatus": cfg["privacy"],
            "selfDeclaredMadeForKids": bool(cfg["made_for_kids"]),
            # YouTube requires disclosing realistic synthetic media; an AI voice reading facts is fine to flag.
            "containsSyntheticMedia": True,
        },
    }
    req = _client().videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(str(video), resumable=True, chunksize=8 << 20))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    print(f"[upload] https://youtu.be/{resp['id']}")
    return resp["id"]
