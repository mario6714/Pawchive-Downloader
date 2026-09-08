"""
Watchlist Manager
Tracks followed artists, persists last-download metadata, and detects new posts
for the Watchlist tab. All network operations are intended to be called from a
background thread to keep the GUI responsive.
"""

import json
import os
import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

from core.logger import logger


@dataclass
class WatchlistEntry:
    url: str
    service: str
    domain: str
    user_id: str
    creator_name: str
    last_post_id: str = ""
    last_post_date: str = ""   # ISO date string: "YYYY-MM-DD"
    added_at: str = ""
    auto_check: bool = True
    new_post_count: int = 0    # transient — not persisted, set after checks
    download_dir: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("new_post_count", None)  # don't persist transient field
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WatchlistEntry":
        return cls(
            url=d.get("url", ""),
            service=d.get("service", ""),
            domain=d.get("domain", ""),
            user_id=d.get("user_id", ""),
            creator_name=d.get("creator_name", ""),
            last_post_id=d.get("last_post_id", ""),
            last_post_date=d.get("last_post_date", ""),
            added_at=d.get("added_at", ""),
            auto_check=bool(d.get("auto_check", True)),
            new_post_count=0,
            download_dir=d.get("download_dir", ""),
        )


class WatchlistManager:
    """
    Manages persistent watchlist of followed artists.
    Thread-safe for reads; writes should be serialized on the main thread
    (or protected externally if called from workers).
    """

    VERSION = 1

    def __init__(self, config_dir: str):
        self.config_dir = config_dir
        self.watchlist_file = os.path.join(config_dir, "watchlist.json")
        self.entries: List[WatchlistEntry] = []

    # ── Persistence ────────────────────────────────────────────────────────────

    def load(self):
        """Load entries from disk. Safe to call multiple times."""
        if not os.path.exists(self.watchlist_file):
            self.entries = []
            return

        try:
            with open(self.watchlist_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw_entries = data.get("entries", []) if isinstance(data, dict) else []
            self.entries = [WatchlistEntry.from_dict(e) for e in raw_entries if isinstance(e, dict)]
            logger.info(
                f"Watchlist loaded: {len(self.entries)} artist(s) tracked.",
                category="watchlist"
            )
        except Exception as e:
            logger.warning(f"Could not load watchlist.json: {e}", category="watchlist")
            self.entries = []

    def save(self):
        """Persist current entries to disk."""
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            data = {
                "version": self.VERSION,
                "entries": [e.to_dict() for e in self.entries]
            }
            with open(self.watchlist_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save watchlist: {e}", category="watchlist")

    # ── CRUD ───────────────────────────────────────────────────────────────────

    def _find(self, user_id: str, service: str) -> Optional[WatchlistEntry]:
        """Return existing entry or None."""
        uid = user_id.strip().lower()
        svc = service.strip().lower()
        for e in self.entries:
            if e.user_id.lower() == uid and e.service.lower() == svc:
                return e
        return None

    def add_entry(
        self,
        url: str,
        creator_name: str,
        user_id: str,
        service: str,
        domain: str,
        last_post_id: str = "",
        last_post_date: str = "",
        auto_check: bool = True,
        download_dir: str = "",
    ) -> bool:
        """
        Add or update a watchlist entry.
        Returns True if a new entry was created, False if updated.
        """
        existing = self._find(user_id, service)
        if existing:
            # Update last download info but don't touch auto_check preference
            if last_post_date and (not existing.last_post_date or last_post_date >= existing.last_post_date):
                existing.last_post_id = last_post_id or existing.last_post_id
                existing.last_post_date = last_post_date
            elif last_post_id and not existing.last_post_id:
                existing.last_post_id = last_post_id
            # Update name in case it resolved better
            if creator_name and creator_name != user_id:
                existing.creator_name = creator_name
            if url:
                existing.url = url
            if download_dir:
                existing.download_dir = download_dir
            self.save()
            return False
        else:
            entry = WatchlistEntry(
                url=url,
                service=service,
                domain=domain,
                user_id=user_id,
                creator_name=creator_name,
                last_post_id=last_post_id,
                last_post_date=last_post_date,
                added_at=datetime.datetime.now().isoformat(timespec="seconds"),
                auto_check=auto_check,
                download_dir=download_dir,
            )
            self.entries.insert(0, entry)
            self.save()
            logger.info(
                f"Added to watchlist: {creator_name!r} [{service}] (last post: {last_post_date or 'unknown'})",
                category="watchlist"
            )
            return True

    def remove_entry(self, user_id: str, service: str) -> bool:
        """Remove entry by (user_id, service). Returns True if removed."""
        existing = self._find(user_id, service)
        if existing:
            self.entries.remove(existing)
            self.save()
            logger.info(f"Removed from watchlist: {existing.creator_name!r} [{service}]", category="watchlist")
            return True
        return False

    def update_last_download(self, user_id: str, service: str, post_id: str, post_date: str):
        """Update last-downloaded post metadata after a successful download."""
        existing = self._find(user_id, service)
        if existing:
            existing.last_post_id = post_id
            existing.last_post_date = post_date
            existing.new_post_count = 0
            self.save()

    def set_auto_check(self, user_id: str, service: str, enabled: bool):
        """Toggle the per-entry auto_check flag."""
        existing = self._find(user_id, service)
        if existing:
            existing.auto_check = enabled
            self.save()

    def set_download_dir(self, user_id: str, service: str, download_dir: str) -> bool:
        """Set or update the custom download directory for an entry."""
        existing = self._find(user_id, service)
        if existing:
            existing.download_dir = download_dir
            self.save()
            return True
        return False

    # ── New-Post Detection ─────────────────────────────────────────────────────

    def get_posts_since(self, entry: WatchlistEntry, api_client) -> List[Dict[str, Any]]:
        """
        Fetch posts for an entry and return only those published strictly after entry.last_post_date.
        Paginates page-by-page until the cutoff date/id is reached or all posts are fetched,
        ensuring the exact number of new posts is discovered without artificial caps.
        Results are sorted oldest-first so callers can download in order.
        Runs synchronously — call from a background thread.
        """
        from core.parser import KemonoURLParser

        parsed = KemonoURLParser.parse(entry.url)
        if not parsed.is_valid:
            logger.warning(
                f"Watchlist: could not parse URL for {entry.creator_name!r}: {entry.url}",
                category="watchlist"
            )
            return []

        cutoff = entry.last_post_date  # "YYYY-MM-DD" or ISO string
        if cutoff and "T" in cutoff:
            cutoff = cutoff.split("T")[0]
        elif cutoff:
            cutoff = cutoff[:10]
        cutoff_id = str(entry.last_post_id or "")

        new_posts: List[Dict[str, Any]] = []
        current_page = 1
        page_size = 50
        max_pages = 25  # Up to 1,250 posts to support deep updates while preventing infinite loops

        while current_page <= max_pages:
            try:
                page_posts = api_client.fetch_user_posts(
                    parsed, page_start=current_page, page_end=current_page, page_size=page_size
                )
            except Exception as e:
                logger.warning(
                    f"Watchlist check failed on page {current_page} for {entry.creator_name!r}: {e}",
                    category="watchlist"
                )
                break

            if not page_posts:
                break

            page_oldest_pub = None
            found_cutoff_id_on_page = False

            for p in page_posts:
                pub = p.get("published") or p.get("added") or ""
                if isinstance(pub, (int, float)):
                    try:
                        pub = datetime.datetime.fromtimestamp(pub).strftime("%Y-%m-%d")
                    except Exception:
                        pub = ""
                elif isinstance(pub, str) and "T" in pub:
                    pub = pub.split("T")[0]
                elif isinstance(pub, str):
                    pub = pub[:10]

                post_id = str(p.get("id", ""))

                # Track oldest date seen on this page to decide if we should paginate further
                if pub and (page_oldest_pub is None or pub < page_oldest_pub):
                    page_oldest_pub = pub

                if cutoff:
                    if pub and pub > cutoff:
                        # Strictly newer: always include
                        new_posts.append(p)
                    elif pub == cutoff:
                        if post_id and post_id == cutoff_id:
                            # This is exactly the last-seen post — skip it, mark cutoff reached
                            found_cutoff_id_on_page = True
                        else:
                            # Same date but a different post — include (new post on same day)
                            new_posts.append(p)
                    # pub < cutoff: skip this post (too old)
                else:
                    # No cutoff at all — include everything
                    new_posts.append(p)

            # Stop paginating if:
            # 1. This was the last page (fewer posts than page_size)
            # 2. The oldest post on this page is already before the cutoff (no need to go deeper)
            # 3. We found the exact cutoff post id on this page
            if len(page_posts) < page_size:
                break
            if cutoff and page_oldest_pub and page_oldest_pub < cutoff:
                break
            if found_cutoff_id_on_page:
                break

            current_page += 1

        # Sort oldest first for ordered downloading
        new_posts.sort(key=lambda p: (
            p.get("published") or p.get("added") or "0",
            str(p.get("id", "0"))
        ))

        return new_posts

    def to_json_list(self) -> str:
        """Return JSON string of all entries (for QML consumption)."""
        data = []
        for e in self.entries:
            data.append({
                "url": e.url,
                "creatorName": e.creator_name,
                "service": e.service,
                "domain": e.domain,
                "userId": e.user_id,
                "lastPostDate": e.last_post_date,
                "lastPostId": e.last_post_id,
                "addedAt": e.added_at,
                "autoCheck": e.auto_check,
                "newPostCount": e.new_post_count,
                "downloadDir": e.download_dir,
            })
        return json.dumps(data, ensure_ascii=False)
