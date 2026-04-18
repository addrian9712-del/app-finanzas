import unittest

from repository import Repo


class RepoTests(unittest.TestCase):
    def setUp(self):
        self.repo = Repo(":memory:")
        self.repo.init_schema()
        self.user_id = "usr_test"

    def test_create_and_list_card(self):
        card = self.repo.create_user_card(
            self.user_id,
            {
                "type": "routine",
                "title": "Tomar agua",
                "config": {"frequency": {"kind": "daily"}},
            },
        )
        self.assertEqual(card["title"], "Tomar agua")
        cards = self.repo.list_user_cards(self.user_id)
        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["id"], card["id"])

    def test_update_and_soft_delete(self):
        card = self.repo.create_user_card(self.user_id, {"type": "task", "title": "Plan del día"})
        updated = self.repo.update_user_card(self.user_id, card["id"], {"title": "Plan diario"})
        self.assertEqual(updated["title"], "Plan diario")

        self.repo.delete_user_card(self.user_id, card["id"])
        cards = self.repo.list_user_cards(self.user_id)
        self.assertEqual(cards, [])

    def test_push_and_pull_sync_changes(self):
        result = self.repo.push_sync_changes(
            self.user_id,
            [
                {
                    "change_id": "chg_1",
                    "entity": "user_card",
                    "entity_id": "uc_1",
                    "operation": "update",
                    "version": 2,
                    "payload": {"title": "Gym"},
                }
            ],
        )
        self.assertEqual(result["accepted"], ["chg_1"])
        pulled = self.repo.pull_sync_changes(self.user_id)
        self.assertEqual(len(pulled), 1)
        self.assertEqual(pulled[0]["entity_id"], "uc_1")

    def test_templates_seeded_and_filter(self):
        all_templates = self.repo.list_card_templates()
        self.assertGreaterEqual(len(all_templates), 4)
        routine_templates = self.repo.list_card_templates("routine")
        self.assertTrue(all(t["type"] == "routine" for t in routine_templates))

    def test_generate_and_complete_card_instances(self):
        card = self.repo.create_user_card(
            self.user_id,
            {"type": "routine", "title": "Tomar agua", "config": {"frequency": {"kind": "daily"}}},
        )
        created = self.repo.generate_daily_instances(self.user_id, "2026-04-20")
        self.assertEqual(created, 1)

        instances = self.repo.list_card_instances(self.user_id, "2026-04-20")
        self.assertEqual(len(instances), 1)
        self.assertEqual(instances[0]["user_card_id"], card["id"])

        done = self.repo.complete_card_instance(self.user_id, instances[0]["id"], "completado temprano")
        self.assertEqual(done["status"], "done")
        self.assertEqual(done["completion_pct"], 100)


if __name__ == "__main__":
    unittest.main()
