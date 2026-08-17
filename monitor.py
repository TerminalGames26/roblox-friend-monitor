import json
import os
import sys
from datetime import datetime, timezone

import requests

ROBLOX_USER_ID = os.environ["ROBLOX_USER_ID"]
DISCORD_WEBHOOK = os.environ["DISCORD_WEBHOOK"]

SNAPSHOT_FILE = "friend_snapshot.json"

ROBLOX_FRIENDS_URL = (
    f"https://friends.roblox.com/v1/users/{ROBLOX_USER_ID}/friends"
)


def get_friends():
    """Get the complete Roblox friend list, including all pagination pages."""

    friends = {}
    cursor = None

    while True:
        params = {
            "limit": 100
        }

        if cursor:
            params["cursor"] = cursor

        response = requests.get(
            ROBLOX_FRIENDS_URL,
            params=params,
            timeout=30,
            headers={
                "User-Agent": "RobloxFriendMonitor/1.0"
            },
        )

        response.raise_for_status()

        data = response.json()

        for friend in data.get("data", []):
            user_id = str(friend["id"])

            friends[user_id] = {
                "id": user_id,
                "username": friend.get("name", "Unknown"),
                "display_name": friend.get(
                    "displayName",
                    friend.get("name", "Unknown")
                ),
            }

        cursor = data.get("nextPageCursor")

        if not cursor:
            break

    return friends


def load_snapshot():
    """Load the previous friend list."""

    if not os.path.exists(SNAPSHOT_FILE):
        return None

    try:
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as file:
            return json.load(file)

    except (json.JSONDecodeError, OSError):
        return None


def save_snapshot(friends):
    """Save the current friend list."""

    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as file:
        json.dump(
            friends,
            file,
            indent=2,
            sort_keys=True
        )


def send_discord(title, description, color):
    """Send an embed to Discord."""

    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "footer": {
                    "text": "Roblox Friend Monitor"
                }
            }
        ]
    }

    response = requests.post(
        DISCORD_WEBHOOK,
        json=payload,
        timeout=30
    )

    response.raise_for_status()


def format_friend(friend):
    """Format a friend for Discord."""

    user_id = friend["id"]
    username = friend["username"]
    display_name = friend["display_name"]

    profile_url = f"https://www.roblox.com/users/{user_id}/profile"

    return (
        f"**Username:** `{username}`\n"
        f"**Display Name:** `{display_name}`\n"
        f"**User ID:** `{user_id}`\n"
        f"**Profile:** [View Roblox Profile]({profile_url})"
    )


def send_changes(title, friends, color, emoji):
    """Send changes to Discord in manageable chunks."""

    if not friends:
        return

    # Discord embeds have a maximum description size.
    chunk = []
    chunk_length = 0

    for friend in friends:
        text = f"{emoji} {format_friend(friend)}"

        if chunk and chunk_length + len(text) > 5500:
            send_discord(
                title,
                "\n\n".join(chunk),
                color
            )

            chunk = []
            chunk_length = 0

        chunk.append(text)
        chunk_length += len(text)

    if chunk:
        send_discord(
            title,
            "\n\n".join(chunk),
            color
        )


def main():
    print("Getting complete Roblox friend list...")

    try:
        current = get_friends()

    except Exception as error:
        print(f"Failed to get Roblox friends: {error}")
        sys.exit(1)

    print(f"Found {len(current)} total friends.")

    previous = load_snapshot()

    # First run / empty snapshot:
    # Save the current list without sending notifications.
    if previous is None or previous == {}:
        save_snapshot(current)

        print(
            "No previous snapshot found."
        )
        print(
            "Current friend list saved as the baseline."
        )
        print(
            "No Discord notifications were sent."
        )

        return

    previous_ids = set(previous.keys())
    current_ids = set(current.keys())

    added_ids = current_ids - previous_ids
    removed_ids = previous_ids - current_ids

    added = [
        current[user_id]
        for user_id in added_ids
    ]

    removed = [
        previous[user_id]
        for user_id in removed_ids
    ]

    added.sort(
        key=lambda friend: friend["username"].lower()
    )

    removed.sort(
        key=lambda friend: friend["username"].lower()
    )

    print(f"Friends added: {len(added)}")
    print(f"Friends removed: {len(removed)}")

    # Update the snapshot.
    save_snapshot(current)

    if not added and not removed:
        print("No friend changes detected.")
        return

    if added:
        send_changes(
            "🟢 Friend Added",
            added,
            0x57F287,
            "🟢"
        )

    if removed:
        send_changes(
            "🔴 Friend Removed",
            removed,
            0xED4245,
            "🔴"
        )

    print("Discord notifications sent successfully.")


if __name__ == "__main__":
    main()
