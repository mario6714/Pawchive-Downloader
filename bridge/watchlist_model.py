"""
Watchlist Qt Model
Exposes the WatchlistManager's entries as a QAbstractListModel so QML
ListView and Repeater can bind to them reactively.
"""

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt, Signal, Slot, Property
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.watchlist_manager import WatchlistManager


class WatchlistModel(QAbstractListModel):
    # Custom roles
    UrlRole          = Qt.UserRole + 1
    CreatorNameRole  = Qt.UserRole + 2
    ServiceRole      = Qt.UserRole + 3
    DomainRole       = Qt.UserRole + 4
    UserIdRole       = Qt.UserRole + 5
    LastPostDateRole = Qt.UserRole + 6
    LastPostIdRole   = Qt.UserRole + 7
    AddedAtRole      = Qt.UserRole + 8
    AutoCheckRole    = Qt.UserRole + 9
    NewPostCountRole = Qt.UserRole + 10

    countChanged = Signal()

    def __init__(self, watchlist_manager, parent=None):
        super().__init__(parent)
        self._manager = watchlist_manager

    @Property(int, notify=countChanged)
    def count(self) -> int:
        return len(self._manager.entries)

    @Property(int, notify=countChanged)
    def updatedCount(self) -> int:
        """Number of tracked artists that have new posts found since last download."""
        return sum(1 for e in self._manager.entries if (e.new_post_count or 0) > 0)

    @Slot(int, result="QVariantMap")
    def get(self, index: int) -> dict:
        if 0 <= index < len(self._manager.entries):
            e = self._manager.entries[index]
            return {
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
            }
        return {}

    # ── QAbstractListModel interface ───────────────────────────────────────────

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._manager.entries)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or index.row() >= len(self._manager.entries):
            return None
        entry = self._manager.entries[index.row()]
        return {
            self.UrlRole:          entry.url,
            self.CreatorNameRole:  entry.creator_name,
            self.ServiceRole:      entry.service,
            self.DomainRole:       entry.domain,
            self.UserIdRole:       entry.user_id,
            self.LastPostDateRole: entry.last_post_date,
            self.LastPostIdRole:   entry.last_post_id,
            self.AddedAtRole:      entry.added_at,
            self.AutoCheckRole:    entry.auto_check,
            self.NewPostCountRole: entry.new_post_count,
            Qt.DisplayRole:        entry.creator_name,
        }.get(role)

    def roleNames(self):
        return {
            self.UrlRole:          b"url",
            self.CreatorNameRole:  b"creatorName",
            self.ServiceRole:      b"service",
            self.DomainRole:       b"domain",
            self.UserIdRole:       b"userId",
            self.LastPostDateRole: b"lastPostDate",
            self.LastPostIdRole:   b"lastPostId",
            self.AddedAtRole:      b"addedAt",
            self.AutoCheckRole:    b"autoCheck",
            self.NewPostCountRole: b"newPostCount",
            Qt.DisplayRole:        b"display",
        }

    # ── Refresh helpers ────────────────────────────────────────────────────────

    @Slot()
    def refresh(self):
        """Full model reset — call after any add/remove/update."""
        self.beginResetModel()
        self.endResetModel()
        self.countChanged.emit()

    def update_new_counts(self):
        """Emit dataChanged for newPostCount column after a watchlist check."""
        if self._manager.entries:
            top = self.index(0, 0)
            bottom = self.index(len(self._manager.entries) - 1, 0)
            self.dataChanged.emit(top, bottom, [self.NewPostCountRole])
        self.countChanged.emit()  # re-notify updatedCount badge in tab bar
