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
    response = requests.get(
        ROBLOX_FRIENDS_URL,
        timeout=30,
        headers={
            "User-Agent": "RobloxFriendMonitor/1.0"
        },
    )

    response.raise_for_status()

    data = response.json()

    friends = {}

    for friend in data.get("data", []):
        user_id = str(friend["id"])

        friends[user_id] = {
            "id": user_id,
            "name": friend.get("name", "Unknown"),
            "display_name": friend.get("displayName", friend.get("name", "Unknown")),
        }

    return friends


def load_snapshot():
    if not os.path.exists(SNAPSHOT_FILE):
        return None

    try:
        with open(SNAPSHOT_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    except (json.JSONDecodeError, OSError):
        return None


def save_snapshot(friends):
    with open(SNAPSHOT_FILE, "w", encoding="utf-8") as file:
        json.dump(friends, file, indent=2, sort_keys=True)


def send_discord(title, description, color):
    payload = {
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "footer": {
                    "text": "Roblox Friend Monitor"
                },
            }
        ]
    }

    response = requests.post(
        DISCORD_WEBHOOK,
        json=payload,
        timeout=30,
    )

    response.raise_for_status()


def format_friend(friend):
    user_id = friend["id"]
    username = friend["name"]
    display_name = friend["display_name"]

    if username == display_name:
        return f"**{username}**\nID: `{user_id}`"

    return (
        f"**{username}** ({display_name})\n"
        f"ID: `{user_id}`"
    )


def main():
    print("Getting current Roblox friends...")

    try:
        current = get_friends()
    except Exception as error:
        print(f"Failed to get friends: {error}")
        sys.exit(1)

    print(f"Found {len(current)} friends.")

    previous = load_snapshot()

    # First run = establish baseline.
    if previous is None:
        save_snapshot(current)

        print(
            "No previous snapshot found. "
            "Saved the current friend list as the baseline."
        )

        return

    previous_ids = set(previous.keys())
    current_ids = set(current.keys())

    added_ids = current_ids - previous_ids
    removed_ids = previous_ids - current_ids

    added = [current[user_id] for user_id in added_ids]
    removed = [previous[user_id] for user_id in removed_ids]

    added.sort(key=lambda friend: friend["name"].lower())
    removed.sort(key=lambda friend: friend["name"].lower())

    print(f"Added: {len(added)}")
    print(f"Removed: {len(removed)}")

    # Save immediately after successfully getting the current list.
    save_snapshot(current)

    # Nothing changed.
    if not added and not removed:
        print("No friend changes.")
        return

    # Discord has message/embed size limits, so send changes in chunks.
    if added:
        lines = [
            f"🟢 {format_friend(friend)}"
            for friend in added
        ]

        send_discord(
            "Friend(s) Added",
            "\n\n".join(lines),
            0x57F287,
        )

    if removed:
        lines = [
            f"🔴 {format_friend(friend)}"
            for friend in removed
        ]

        send_discord(
            "Friend(s) Removed",
            "\n\n".join(lines),
            0xED4245,
        )


if __name__ == "__main__":
    main()
