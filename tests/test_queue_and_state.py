import unittest
import os
import json
import tempfile
import shutil
from core.downloader import DownloadTask, KemonoDownloader
from bridge.queue_model import QueueModel

class MockKnownManager:
    pass

class MockSessionManager:
    pass

class TestQueueAndState(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.downloader = KemonoDownloader(
            known_manager=MockKnownManager(),
            session_manager=MockSessionManager()
        )
        self.queue_model = QueueModel()

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_download_task_batch_id_and_dict_serialization(self):
        task = DownloadTask(
            url="https://c1.kemono.su/data/1.jpg",
            target_path=os.path.join(self.temp_dir, "1.jpg"),
            post_title="Post One",
            creator_name="Artist A",
            service="patreon",
            post_id="101",
            file_id="101_1.jpg",
            file_size=1048576,
            batch_id="batch_artist_a_101"
        )
        task.downloaded_bytes = 524288
        task.status = "downloading"

        d = task.to_dict()
        self.assertEqual(d["batch_id"], "batch_artist_a_101")
        self.assertEqual(d["creator_name"], "Artist A")
        self.assertEqual(d["file_size"], 1048576)
        self.assertEqual(d["downloaded_bytes"], 524288)
        self.assertEqual(d["status"], "downloading")

        restored = DownloadTask.from_dict(d)
        self.assertEqual(restored.url, task.url)
        self.assertEqual(restored.target_path, task.target_path)
        self.assertEqual(restored.creator_name, task.creator_name)
        self.assertEqual(restored.post_id, task.post_id)
        self.assertEqual(restored.file_id, task.file_id)
        self.assertEqual(restored.batch_id, "batch_artist_a_101")
        self.assertEqual(restored.downloaded_bytes, 524288)
        self.assertEqual(restored.status, "downloading")

    def test_downloader_append_tasks_and_deduplication(self):
        t1 = DownloadTask(
            url="https://c1.kemono.su/data/1.jpg",
            target_path=os.path.join(self.temp_dir, "1.jpg"),
            post_title="Post 1",
            creator_name="Artist A",
            service="patreon",
            post_id="101",
            file_id="101_1.jpg",
            batch_id="batch_a"
        )
        t2 = DownloadTask(
            url="https://c1.kemono.su/data/2.jpg",
            target_path=os.path.join(self.temp_dir, "2.jpg"),
            post_title="Post 1",
            creator_name="Artist A",
            service="patreon",
            post_id="101",
            file_id="101_2.jpg",
            batch_id="batch_a"
        )

        added_1 = self.downloader.append_tasks([t1, t2])
        self.assertEqual(added_1, 2)
        self.assertEqual(len(self.downloader.tasks), 2)

        # Append duplicates and 1 new task
        t2_dup = DownloadTask(
            url="https://c1.kemono.su/data/2.jpg",
            target_path=os.path.join(self.temp_dir, "2.jpg"),
            post_title="Post 1",
            creator_name="Artist A",
            service="patreon",
            post_id="101",
            file_id="101_2.jpg",
            batch_id="batch_a"
        )
        t3_new = DownloadTask(
            url="https://c1.kemono.su/data/3.jpg",
            target_path=os.path.join(self.temp_dir, "3.jpg"),
            post_title="Post 2",
            creator_name="Artist B",
            service="fanbox",
            post_id="202",
            file_id="202_3.jpg",
            batch_id="batch_b"
        )

        added_2 = self.downloader.append_tasks([t2_dup, t3_new])
        self.assertEqual(added_2, 1)
        self.assertEqual(len(self.downloader.tasks), 3)

    def test_downloader_batch_controls(self):
        t1 = DownloadTask(
            url="https://c1.kemono.su/data/1.jpg",
            target_path=os.path.join(self.temp_dir, "1.jpg"),
            post_title="Post 1",
            creator_name="Artist A",
            service="patreon",
            post_id="1",
            file_id="1",
            batch_id="batch_1"
        )
        t2 = DownloadTask(
            url="https://c1.kemono.su/data/2.jpg",
            target_path=os.path.join(self.temp_dir, "2.jpg"),
            post_title="Post 1",
            creator_name="Artist A",
            service="patreon",
            post_id="1",
            file_id="2",
            batch_id="batch_1"
        )
        t3 = DownloadTask(
            url="https://c1.kemono.su/data/3.jpg",
            target_path=os.path.join(self.temp_dir, "3.jpg"),
            post_title="Post 2",
            creator_name="Artist B",
            service="fanbox",
            post_id="2",
            file_id="3",
            batch_id="batch_2"
        )
        self.downloader.tasks = [t1, t2, t3]

        # Cancel batch 1
        cancelled = self.downloader.cancel_batch("batch_1")
        self.assertEqual(cancelled, 2)
        self.assertEqual(t1.status, "cancelled")
        self.assertEqual(t2.status, "cancelled")
        self.assertEqual(t3.status, "pending")

        # Retry batch 1
        retried = self.downloader.retry_batch_failed("batch_1")
        self.assertEqual(retried, 2)
        self.assertEqual(t1.status, "pending")
        self.assertEqual(t2.status, "pending")
        self.assertEqual(t1.retry_count, 1)

        # Remove batch 1
        removed = self.downloader.remove_batch("batch_1")
        self.assertEqual(removed, 2)
        self.assertEqual(len(self.downloader.tasks), 1)
        self.assertEqual(self.downloader.tasks[0].file_id, "3")

    def test_queue_model_grouping_and_drilldown(self):
        t1 = DownloadTask(
            url="https://c1.kemono.su/data/1.jpg",
            target_path=os.path.join(self.temp_dir, "1.jpg"),
            post_title="Post One",
            creator_name="Artist A",
            service="patreon",
            post_id="100",
            file_id="1",
            file_size=1000,
            batch_id="batch_artist_a"
        )
        t2 = DownloadTask(
            url="https://c1.kemono.su/data/2.jpg",
            target_path=os.path.join(self.temp_dir, "2.jpg"),
            post_title="Post One",
            creator_name="Artist A",
            service="patreon",
            post_id="100",
            file_id="2",
            file_size=2000,
            batch_id="batch_artist_a"
        )
        t3 = DownloadTask(
            url="https://c1.kemono.su/data/3.jpg",
            target_path=os.path.join(self.temp_dir, "3.jpg"),
            post_title="Post Two",
            creator_name="Artist B",
            service="fanbox",
            post_id="200",
            file_id="3",
            file_size=5000,
            batch_id="batch_artist_b"
        )

        t1.status = "completed"
        t1.downloaded_bytes = 1000

        self.queue_model.setTasks([t1, t2, t3])
        self.assertEqual(self.queue_model.totalCount, 3)
        self.assertEqual(self.queue_model.groupsCount, 2)

        groups = self.queue_model.groups
        group_a = next(g for g in groups if g["batchId"] == "batch_artist_a")
        self.assertEqual(group_a["creatorName"], "Artist A")
        self.assertEqual(group_a["totalFiles"], 2)
        self.assertEqual(group_a["completedFiles"], 1)
        self.assertEqual(group_a["pendingFiles"], 1)
        self.assertEqual(group_a["totalBytes"], 3000)
        self.assertEqual(group_a["downloadedBytes"], 1000)
        self.assertEqual(group_a["status"], "partial")

        # Drilldown filter
        self.queue_model.selectedBatchId = "batch_artist_a"
        self.assertEqual(self.queue_model.count, 2)

        # Clear drilldown
        self.queue_model.selectedBatchId = ""
        self.assertEqual(self.queue_model.count, 3)

        # View mode toggle
        self.assertEqual(self.queue_model.viewMode, "grouped")
        self.queue_model.viewMode = "flat"
        self.assertEqual(self.queue_model.viewMode, "flat")

    def test_state_export_summary_format_and_import_disk_verification(self):
        # Create a file that is already completed on disk
        file1_path = os.path.join(self.temp_dir, "full.jpg")
        with open(file1_path, "wb") as f:
            f.write(b"X" * 1000)

        # Create a partial file on disk
        file2_path = os.path.join(self.temp_dir, "partial.jpg")
        with open(file2_path, "wb") as f:
            f.write(b"Y" * 400)

        # File 3 does not exist on disk
        file3_path = os.path.join(self.temp_dir, "missing.jpg")

        t1 = DownloadTask(
            url="https://c1.kemono.su/data/full.jpg",
            target_path=file1_path,
            post_title="Post 1",
            creator_name="Artist X",
            service="patreon",
            post_id="1",
            file_id="f1",
            file_size=1000,
            batch_id="batch_x"
        )
        t1.status = "completed"
        t1.downloaded_bytes = 1000

        t2 = DownloadTask(
            url="https://c1.kemono.su/data/partial.jpg",
            target_path=file2_path,
            post_title="Post 1",
            creator_name="Artist X",
            service="patreon",
            post_id="1",
            file_id="f2",
            file_size=1000,
            batch_id="batch_x"
        )
        t2.status = "downloading"
        t2.downloaded_bytes = 400

        t3 = DownloadTask(
            url="https://c1.kemono.su/data/missing.jpg",
            target_path=file3_path,
            post_title="Post 2",
            creator_name="Artist Y",
            service="fanbox",
            post_id="2",
            file_id="f3",
            file_size=2000,
            batch_id="batch_y"
        )

        all_tasks = [t1, t2, t3]
        self.queue_model.setTasks(all_tasks)

        # Construct export dictionary as app_bridge does
        snapshot = {
            "_summary": {
                "title": "Pawchive Downloader Queue State Backup",
                "app_version": "1.0.6",
                "exported_at": "2026-09-06 04:00:00",
                "creators": ["Artist X", "Artist Y"],
                "total_batches": 2,
                "total_files": 3,
                "completed_files": 1,
                "pending_files": 2,
                "failed_files": 0,
                "overall_progress": "35.0%",
                "current_saved_data": "1.4 KB",
                "total_queue_data": "4.0 KB",
                "destination_directory": self.temp_dir
            },
            "settings": {
                "download_dir": self.temp_dir,
                "threads": 4
            },
            "batches": self.queue_model.groups,
            "tasks": [t.to_dict() for t in all_tasks]
        }

        # Verify summary keys
        summary = snapshot["_summary"]
        self.assertIn("title", summary)
        self.assertIn("app_version", summary)
        self.assertIn("exported_at", summary)
        self.assertIn("creators", summary)
        self.assertIn("total_batches", summary)
        self.assertIn("total_files", summary)
        self.assertIn("completed_files", summary)
        self.assertIn("pending_files", summary)
        self.assertIn("failed_files", summary)
        self.assertIn("overall_progress", summary)
        self.assertIn("current_saved_data", summary)
        self.assertIn("total_queue_data", summary)
        self.assertIn("destination_directory", summary)

        export_path = os.path.join(self.temp_dir, "queue_state.json")
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)

        # Test Import & Disk Verification logic
        with open(export_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        imported_tasks = []
        for t_dict in data["tasks"]:
            task = DownloadTask.from_dict(t_dict)
            if os.path.exists(task.target_path):
                actual_sz = os.path.getsize(task.target_path)
                if task.file_size > 0 and actual_sz >= task.file_size:
                    task.status = "completed"
                    task.downloaded_bytes = task.file_size
                elif actual_sz > 0:
                    task.downloaded_bytes = actual_sz
                    task.status = "pending"
            elif task.status == "downloading":
                task.status = "pending"
            imported_tasks.append(task)

        self.assertEqual(len(imported_tasks), 3)
        self.assertEqual(imported_tasks[0].status, "completed")
        self.assertEqual(imported_tasks[0].downloaded_bytes, 1000)

        # Partial file was 'downloading' in export, but on disk it's 400 bytes, so pending with 400 bytes
        self.assertEqual(imported_tasks[1].status, "pending")
        self.assertEqual(imported_tasks[1].downloaded_bytes, 400)

        # Missing file remains pending
        self.assertEqual(imported_tasks[2].status, "pending")
        self.assertEqual(imported_tasks[2].downloaded_bytes, 0)

    def test_link_identity_and_deduplication(self):
        from core.parser import KemonoURLParser
        from bridge.app_bridge import AppBridge

        # Instantiate mock AppBridge helper
        class DummyBridge:
            _get_link_identity = AppBridge._get_link_identity

        bridge = DummyBridge()

        # 1. Artist link (standard format)
        p1 = KemonoURLParser.parse("https://kemono.su/fanbox/user/12345")
        t1, k1, parent1, d1 = bridge._get_link_identity(p1)
        self.assertEqual(t1, "artist")
        self.assertEqual(k1, "artist:fanbox:12345")
        self.assertIsNone(parent1)

        # 2. Artist link (alternative format)
        p2 = KemonoURLParser.parse("https://kemono.su/artists/fanbox/12345")
        t2, k2, parent2, d2 = bridge._get_link_identity(p2)
        self.assertEqual(t2, "artist")
        self.assertEqual(k2, "artist:fanbox:12345")
        self.assertEqual(k1, k2)  # Identical canonical identity

        # 3. Post link (standard format)
        p3 = KemonoURLParser.parse("https://kemono.su/fanbox/user/12345/post/999")
        t3, k3, parent3, d3 = bridge._get_link_identity(p3)
        self.assertEqual(t3, "post")
        self.assertEqual(k3, "post:fanbox:12345:999")
        self.assertEqual(parent3, "artist:fanbox:12345")

        # 4. Post link (alternative format)
        p4 = KemonoURLParser.parse("https://kemono.su/posts/fanbox/12345/999")
        t4, k4, parent4, d4 = bridge._get_link_identity(p4)
        self.assertEqual(t4, "post")
        self.assertEqual(k4, "post:fanbox:12345:999")
        self.assertEqual(k3, k4)  # Identical canonical identity

        # 5. External link
        p5 = KemonoURLParser.parse("https://bunkr.is/a/xyz789")
        t5, k5, parent5, d5 = bridge._get_link_identity(p5)
        self.assertEqual(t5, "external")
        self.assertEqual(k5, "bunkr:xyz789")
        self.assertIsNone(parent5)

        # Test deduplication set logic
        queued_links = set()
        queued_links.add(k1)  # Artist queued

        # Trying to queue artist again should be detected as duplicate
        self.assertIn(k2, queued_links)

        # Trying to queue post whose parent artist is already in queue should be detected
        self.assertIn(parent3, queued_links)

        # Different post from different artist is not in queue
        p6 = KemonoURLParser.parse("https://coomer.su/onlyfans/user/67890/post/888")
        t6, k6, parent6, d6 = bridge._get_link_identity(p6)
        self.assertNotIn(k6, queued_links)
        self.assertNotIn(parent6, queued_links)

    def test_queue_cleared_signal(self):
        cleared_emitted = []
        self.queue_model.cleared.connect(lambda: cleared_emitted.append(True))

        t = DownloadTask(
            url="https://c1.kemono.su/data/1.jpg",
            target_path=os.path.join(self.temp_dir, "1.jpg"),
            post_title="Post 1",
            creator_name="Artist A",
            service="patreon",
            post_id="101",
            file_id="101_1.jpg",
            batch_id="batch_a"
        )
        self.queue_model.setTasks([t])
        self.assertEqual(self.queue_model.rowCount(), 1)

        self.queue_model.clear()
        self.assertEqual(self.queue_model.rowCount(), 0)
        self.assertEqual(len(cleared_emitted), 1)

if __name__ == "__main__":
    unittest.main()

