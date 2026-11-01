"""Regression checks for the Python game rules (no browser required)."""
import json
import random
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

frames = []
js_module = types.ModuleType("js")
js_module.window = SimpleNamespace(gameBridge=SimpleNamespace(draw=frames.append))
sys.modules.setdefault("js", js_module)
import game


class GameRegressionTests(unittest.TestCase):
    def new_game(self, seed=7):
        random.seed(seed)
        g = game.Game()
        g.start("검증용")
        return g

    def test_random_starts_never_send_beastkin_to_royal_city(self):
        royal_areas = {"왕실 상점가", "왕국 기사단", "왕국 안", "왕의 방"}
        for seed in range(100):
            g = self.new_game(seed)
            self.assertFalse(g.player["race"] == "수인" and g.area in royal_areas)

    def test_humans_can_start_at_each_of_the_four_origins(self):
        for area in ("숲","왕실 상점가","마을","교회 밖"):
            g = game.Game()
            def choose_for_start(options):
                if options == ["인간","수인"]: return "인간"
                if options == ["남성","여성"]: return "여성"
                if "왕실 상점가" in options and "마을" in options: return area
                return options[0]
            with patch("game.random.choice", side_effect=choose_for_start):
                g.start("시작 지점 검증")
            self.assertEqual(g.area, area)

    def test_beastkin_can_start_in_village_as_unaligned_forest_faith(self):
        g = game.Game()
        def choose_for_start(options):
            if options == ["인간","수인"]: return "수인"
            if options == ["남성","여성"]: return "남성"
            if "마을" in options and "왕실 상점가" not in options: return "마을"
            return options[0]
        with patch("game.random.choice", side_effect=choose_for_start):
            g.start("마을 출발")
        self.assertEqual(g.area, "마을")
        self.assertEqual(g.player["faction"], "무소속")
        self.assertEqual(g.player["religion"], "숲의 신앙")
        self.assertIn("경계에 선 마을", g.notice)

    def test_religion_is_assigned_from_the_random_start(self):
        g = game.Game()
        with patch("game.random.choice", side_effect=["인간", "여성", "교회 밖"]):
            g.start("신앙 검증")
        self.assertEqual(g.player["religion"], "교회 신앙")

    def test_all_area_scenes_render(self):
        g = self.new_game()
        for area, (width, height) in game.MAP_SIZE.items():
            g.area = area
            g.player.update(area=area, x=width // 2, y=height // 2)
            g.spawn_enemies()
            g.draw()
            scene=json.loads(frames[-1])
            self.assertEqual((scene[1].get("w"),scene[1].get("h")),(81,81),area)
            self.assertIn(scene[1].get("c"),game.FLOOR_PALETTES[area])
        self.assertTrue(frames)
        self.assertIsInstance(json.loads(frames[-1]), list)

    def test_save_and_resume_preserve_player_area_quest_and_battle(self):
        g = self.new_game()
        g.area = "숲"
        g.player.update(area="숲", x=1234, y=765, gold=137, facing="left",
                        quest={"title":"숲의 마물 퇴치","source":"church","goal":1,"count":0})
        g.enemies = [{"name":"늑대","x":1200,"y":740,"hp":20,"maxhp":40,
                      "atk":6,"level":1,"alive":True}]
        g.start_battle(0)
        g.battle["submenu"] = "attack"
        restored = game.Game()
        self.assertTrue(restored.load_snapshot(g.save_snapshot()))
        self.assertEqual(restored.player["gold"], 137)
        self.assertEqual(restored.player["facing"], "left")
        self.assertEqual(restored.area, "숲")
        self.assertEqual(restored.player["quest"]["title"], "숲의 마물 퇴치")
        self.assertEqual(restored.mode, "battle")
        self.assertEqual(restored.battle["submenu"], "attack")

    def test_legacy_save_defaults_facing_and_rejects_unknown_direction(self):
        source=self.new_game()
        snapshot=json.loads(source.save_snapshot())
        snapshot["player"].pop("facing")
        restored=game.Game()
        self.assertTrue(restored.load_snapshot(json.dumps(snapshot)))
        self.assertEqual(restored.player["facing"],"down")
        snapshot["player"]["facing"]="diagonal"
        self.assertFalse(game.Game().load_snapshot(json.dumps(snapshot)))

    def test_player_turns_toward_movement_and_keeps_direction_after_resume(self):
        g=self.new_game()
        g.area="마을"
        g.player.update(area="마을",x=700,y=500,facing="down")
        g.tick(.05,json.dumps(["ArrowLeft"]),"[]","null")
        self.assertLess(g.player["x"],700)
        self.assertEqual(g.player["facing"],"left")
        self.assertTrue(g.player_walking)
        resumed=game.Game()
        self.assertTrue(resumed.load_snapshot(g.save_snapshot()))
        self.assertEqual(resumed.player["facing"],"left")
        self.assertFalse(resumed.player_walking)

    def test_character_faces_forward_profile_and_back_and_animates_footsteps(self):
        g=self.new_game()
        down=[];g.draw_character(down,100,100,"영웅",facing="down",phase=0)
        left=[];g.draw_character(left,100,100,"영웅",facing="left",walking=True,phase=1.57)
        up=[];g.draw_character(up,100,100,"영웅",facing="up",phase=0)
        eyes=lambda scene:[item for item in scene if item.get("t")=="c" and item.get("r")==1.3]
        self.assertEqual(len(eyes(down)),2)
        self.assertEqual(len(eyes(left)),1)
        self.assertEqual(len(eyes(up)),0)
        boots=lambda scene:[(item["x"],item["y"]) for item in scene
                            if item.get("t")=="r" and item.get("c")=="#342b2a"]
        self.assertNotEqual(boots(down),boots(left))

    def test_corrupt_save_is_rejected_without_starting_game(self):
        g = game.Game()
        self.assertFalse(g.load_snapshot("not valid json"))
        self.assertFalse(g.started)

    def test_incomplete_save_is_rejected_without_partial_game_state(self):
        g = game.Game()
        self.assertFalse(g.load_snapshot(json.dumps({"version":1,"area":"숲","player":{}})))
        self.assertFalse(g.started)
        self.assertEqual(g.player,{})

    def test_malformed_save_progress_is_rejected_without_mutating_game(self):
        source = self.new_game()
        snapshot = json.loads(source.save_snapshot())
        snapshot["walk_meter"] = "not a number"
        target = game.Game()
        target.player = {"keep": "existing"}
        target.area = "마을"
        self.assertFalse(target.load_snapshot(json.dumps(snapshot)))
        self.assertFalse(target.started)
        self.assertEqual(target.player, {"keep": "existing"})
        self.assertEqual(target.area, "마을")

    def test_game_autosaves_after_start_and_during_play(self):
        g = game.Game()
        with patch.object(game.window.gameBridge, "save", create=True) as save:
            g.start("저장 검증")
            save.assert_called_once()
            save.reset_mock()
            g.tick(1.6, "[]", "[]", "null")
            save.assert_called_once()

    def test_seeded_controls_and_resume_smoke(self):
        rng_state = random.getstate()
        held_options=[[],["ArrowUp"],["ArrowDown"],["ArrowLeft"],["ArrowRight"]]
        press_options=[[],[],["e"],["i"],["q"],["1"],["2"],["3"],["4"],["h"],["m"],["Escape"],[" "],["ArrowRight"]]
        click_options=[None,None,{"x":200,"y":318},{"x":480,"y":450},{"x":700,"y":500},{"x":790,"y":111}]
        try:
            with patch.object(game.window.gameBridge, "draw", lambda payload: None):
                for seed in range(24):
                    random.seed(seed)
                    g=game.Game();g.start(f"스모크-{seed}")
                    for frame in range(160):
                        g.tick(.05,json.dumps(random.choice(held_options)),
                               json.dumps(random.choice(press_options)),
                               json.dumps(random.choice(click_options)))
                        p=g.player;mapw,maph=game.MAP_SIZE[g.area]
                        self.assertEqual(p["area"],g.area)
                        self.assertGreaterEqual(p["hp"],0);self.assertLessEqual(p["hp"],p["maxhp"])
                        self.assertGreaterEqual(p["mp"],0);self.assertLessEqual(p["mp"],p["maxmp"])
                        self.assertGreaterEqual(p["x"],0);self.assertLessEqual(p["x"],mapw)
                        self.assertGreaterEqual(p["y"],0);self.assertLessEqual(p["y"],maph)
                        if frame in (39,79,119):
                            resumed=game.Game()
                            self.assertTrue(resumed.load_snapshot(g.save_snapshot()))
                            g=resumed
        finally:
            random.setstate(rng_state)

    def test_prayer_is_limited_by_completed_church_quests(self):
        g = self.new_game()
        p = g.player
        p.update(faction="교회", job="전사", area="교회 안", prayer_count=0,
                 church_quests_completed=1, prayer_due=True, x=480, y=130)
        g.area = "교회 안"
        g.interact()
        self.assertEqual(p["prayer_count"], 1)
        self.assertFalse(p["prayer_due"])
        g.interact()
        self.assertEqual(p["prayer_count"], 1)

    def test_church_faith_restores_mp_when_praying(self):
        g = self.new_game()
        p = g.player
        p.update(faction="교회", job="신자", religion="교회 신앙", area="교회 안",
                 prayer_count=0, church_quests_completed=1, mp=0, x=480, y=130)
        g.area = "교회 안"
        g.interact()
        self.assertEqual(p["mp"], 3)

    def test_kingdom_faith_adds_gold_to_royal_quest_reward(self):
        g = self.new_game()
        p = g.player
        p.update(faction="왕실", religion="왕실 신앙", job="전사", gold=0,
                 quest={"title":"왕실 토벌","source":"kingdom","goal":1,"count":1})
        g.complete_monster_quest()
        self.assertEqual(p["gold"], 30)

    def test_forest_faith_improves_flee_odds(self):
        g = self.new_game()
        g.player["religion"] = "숲의 신앙"
        g.enemies = [{"name":"늑대","x":400,"y":300,"hp":90,"maxhp":90,
                      "atk":1,"level":1,"alive":True}]
        g.start_battle(0)
        with patch("game.random.random", return_value=0.52):
            g.battle_action("flee")
        self.assertEqual(g.mode, "world")

    def test_successful_priest_quest_grants_one_prayer(self):
        g = self.new_game()
        p = g.player
        p.update(faction="교회", job="전사")
        g.after_church_quest("church")
        self.assertEqual(p["church_quests_completed"], 1)
        self.assertTrue(p["prayer_due"])

    def test_prayer_quest_consumes_a_prayer_without_refunding_its_own_limit(self):
        g = self.new_game()
        p = g.player
        p.update(faction="교회", job="신자", area="교회 안", x=480, y=130,
                 prayer_count=0, church_quests_completed=1,
                 quest={"title":"기도","source":"church_simple","goal":1,"count":0})
        g.area = "교회 안"
        g.interact()
        self.assertEqual(p["prayer_count"], 1)
        self.assertEqual(p["church_quests_completed"], 1)
        self.assertIsNone(p["quest"])
        self.assertEqual(p["gold"], 92)
        p.update(x=700, y=230)
        g.interact()
        self.assertNotIn("기도 의뢰", g.dialog["options"])

    def test_non_prayer_church_tasks_grant_another_prayer_credit(self):
        g = self.new_game()
        p = g.player
        p.update(faction="교회", job="신자", area="교회 안", x=760, y=560,
                 church_quests_completed=0,
                 quest={"title":"밭에 물 주기","source":"church_simple","goal":1,"count":0})
        g.area = "교회 안"
        g.interact()
        self.assertEqual(p["church_quests_completed"], 1)
        self.assertIsNone(p["quest"])

    def test_ten_church_services_promote_believer_to_priest_and_finish_chapter(self):
        g=self.new_game()
        p=g.player
        p.update(faction="교회",job="신자",church_quests_completed=0,priest_refusals=0,promoted=False)
        for completed in range(1,11):
            p["quest"]={"title":"밭에 물 주기","source":"church_simple","goal":1,"count":0}
            g.complete_simple_quest("밭에 물 주기")
            if completed<10:g.dialog=None
        self.assertEqual(p["church_quests_completed"],10)
        self.assertEqual(p["job"],"성직자")
        self.assertTrue(p["promoted"])
        self.assertEqual(g.dialog["title"],"직업 승급")
        self.assertIn("chapter1:church:3",p["story_flags"])
        self.assertIn("chapter1:church:7",p["story_flags"])
        resumed=game.Game()
        self.assertTrue(resumed.load_snapshot(g.save_snapshot()))
        self.assertEqual(resumed.player["job"],"성직자")
        self.assertTrue(resumed.player["promoted"])

    def test_three_church_refusals_lock_believer_promotion(self):
        g=self.new_game()
        p=g.player
        p.update(faction="교회",job="신자",church_quests_completed=0,priest_refusals=3,promoted=False)
        for _ in range(10):
            p["quest"]={"title":"교회 청소","source":"church_simple","goal":1,"count":0}
            g.complete_simple_quest("교회 청소")
            g.dialog=None
        self.assertEqual(p["church_quests_completed"],10)
        self.assertEqual(p["job"],"신자")
        self.assertFalse(p["promoted"])

    def test_believer_journal_tracks_service_promotion_requirement(self):
        g=self.new_game()
        g.player.update(faction="교회",job="신자",church_quests_completed=6,priest_refusals=2)
        text=g.quest_journal_text()
        self.assertIn("교회 봉사 6/10",text)
        self.assertIn("거절 2/3",text)

    def test_promoted_priest_cannot_restart_church_training_or_quests(self):
        g=self.new_game()
        g.area="교회 안"
        g.player.update(area="교회 안",faction="교회",job="성직자",promoted=True,x=240,y=260)
        g.interact()
        self.assertIn("제1장을 마쳤다",g.dialog["text"])
        self.assertNotIn("신자로 수련 시작",g.dialog["options"])
        g.player.update(x=700,y=230)
        g.interact()
        self.assertIn("네 봉사와 서품",g.dialog["text"])
        self.assertNotIn("밭에 물 주기 의뢰",g.dialog["options"])

    def test_promoted_knight_cannot_restart_kingdom_chapter_quests(self):
        g=self.new_game()
        g.area="왕국 기사단"
        g.player.update(area="왕국 기사단",faction="왕실",job="기사",promoted=True,
                        king_quests=10,quest=None,x=500,y=330)
        g.interact()
        self.assertIn("제1장을 마쳤다",g.dialog["text"])
        self.assertNotIn("왕실 토벌 의뢰",g.dialog["options"])
        g.area="왕의 방"
        g.player.update(area="왕의 방",x=450,y=225)
        g.interact()
        self.assertIn("제1장의 명령을 거두었다",g.dialog["text"])
        self.assertNotIn("마물 퇴치 의뢰",g.dialog["options"])

    def test_quest_acceptance_notice_matches_the_actual_objective(self):
        g=self.new_game()
        cases=[
            ("church_simple","밭에 물 주기","밭에 물을 주자"),
            ("church_simple","교회 청소","청소 구역을 정리하자"),
            ("church_simple","기도","제단에서 기도하자"),
            ("church","숲의 마물 퇴치","제단에서 기도하자"),
            ("village","숲의 마물 퇴치","마을 주민에게 보고하자"),
            ("kingdom","왕실 토벌","왕실에 보고하자"),
        ]
        for source,title,expected in cases:
            g.accept_quest(title,source)
            self.assertIn(expected,g.notice)
            g.player["quest"]=None

    def test_priest_hides_refusal_option_while_a_church_quest_is_active(self):
        for job in ("전사","신자"):
            g=self.new_game()
            g.area="교회 안"
            g.player.update(area="교회 안",faction="교회",job=job,x=700,y=230,priest_refusals=0,
                            quest={"title":"숲의 마물 퇴치","source":"church","goal":1,"count":0})
            g.interact()
            self.assertEqual(g.dialog["title"],"성직자")
            self.assertIn("먼저 진행 중인 의뢰",g.dialog["text"])
            self.assertNotIn("의뢰 거절",g.dialog["options"])
            self.assertEqual(g.player["priest_refusals"],0)
            self.assertEqual(g.player["quest"]["title"],"숲의 마물 퇴치")

    def test_faction_story_clues_reveal_once_and_survive_resume(self):
        g = self.new_game()
        p=g.player
        p.update(faction="교회",job="전사",church_quests_completed=0,prayer_due=False)
        for _ in range(3):
            g.after_church_quest("church")
            if p["prayer_due"]:p["prayer_due"]=False
            if p["church_quests_completed"]<3:g.dialog=None
        self.assertEqual(g.dialog["title"],"기도 의무")
        self.assertIn("왕실 문양이 찍힌 화살촉",g.dialog["text"])
        self.assertIn("chapter1:church:3",p["story_flags"])
        resumed=game.Game()
        self.assertTrue(resumed.load_snapshot(g.save_snapshot()))
        p=resumed.player
        p.update(faction="왕실",job="전사",king_quests=0,prayer_due=False)
        for _ in range(3):
            resumed.after_church_quest("kingdom")
            if p["king_quests"]<3:resumed.dialog=None
        self.assertEqual(resumed.dialog["title"],"전쟁의 단서")
        self.assertIn("교회 문양이 찍힌 약초 주머니",resumed.dialog["text"])
        self.assertIn("chapter1:royal:3",p["story_flags"])
        self.assertIsNone(resumed.reveal_story_beat("royal",3))

    def test_ten_church_quests_and_prayers_finish_chapter_as_crusader(self):
        g = self.new_game()
        p = g.player
        p.update(faction="교회", job="전사", religion="교회 신앙", area="교회 안",
                 prayer_count=0, church_quests_completed=0, priest_refusals=0, prayer_due=False)
        g.area = "교회 안"
        p.update(x=480, y=130)
        for _ in range(10):
            p["quest"]={"title":"숲의 마물 퇴치","source":"church","goal":1,"count":1}
            g.complete_monster_quest()
            g.dialog=None
            g.interact()
        self.assertEqual(p["prayer_count"], 10)
        self.assertEqual(p["job"], "성전사")
        self.assertTrue(p["promoted"])
        self.assertEqual(g.dialog["title"], "직업 승급")

    def test_ten_royal_quests_finish_chapter_as_knight(self):
        g = self.new_game()
        p = g.player
        p.update(faction="왕실", job="전사", religion="왕실 신앙", king_quests=0)
        for _ in range(10):
            p["quest"]={"title":"왕실 토벌","source":"kingdom","goal":1,"count":1}
            g.complete_monster_quest()
        self.assertEqual(p["king_quests"], 10)
        self.assertEqual(p["job"], "기사")
        self.assertEqual(g.dialog["title"], "직업 승급")

    def test_exiled_church_warrior_can_leave_village_but_not_reenter_church(self):
        g = self.new_game()
        p = g.player
        p.update(faction="교회", area="교회 안", prayer_due=True)
        g.area = "교회 안"
        g.move_area("마을")
        self.assertEqual(g.area, "마을")
        self.assertEqual(p["faction"], "방랑자")
        self.assertEqual(p["visited_faction"], "숲")
        self.assertFalse(p["prayer_due"])
        g.move_area("숲")
        self.assertEqual(g.area, "숲")
        g.move_area("교회 밖")
        self.assertEqual(g.area, "숲")

    def test_death_after_church_exile_returns_to_wanderer_forest(self):
        g = self.new_game()
        p = g.player
        p.update(faction="교회", area="교회 안", prayer_due=True, hp=1, gold=101)
        g.area = "교회 안"
        g.exile_church()
        g.enemies = [{"name":"늑대","x":400,"y":300,"hp":90,"maxhp":90,
                      "atk":40,"level":1,"alive":True}]
        g.start_battle(0)
        g.enemy_turn()
        self.assertEqual(g.area, "숲")
        self.assertEqual(p["visited_faction"], "숲")
        self.assertEqual(p["gold"], 50)

    def test_active_quest_cannot_be_overwritten(self):
        g = self.new_game()
        g.accept_quest("첫 의뢰", "church")
        g.accept_quest("두 번째 의뢰", "kingdom")
        self.assertEqual(g.player["quest"]["title"], "첫 의뢰")

    def test_player_must_leave_current_faction_before_taking_a_new_job(self):
        g = self.new_game()
        p = g.player
        g.area = "왕국 기사단"
        p.update(area="왕국 기사단", faction="교회", job="전사", x=500, y=330)
        g.interact()
        self.assertNotIn("전사로 수련 시작", g.dialog["options"])
        g.choose(0)
        self.assertEqual(p["faction"], "무소속")
        self.assertEqual(p["job"], "전사")

    def test_killing_a_human_does_not_complete_monster_quest(self):
        g = self.new_game()
        p = g.player
        p.update(atk=50, quest={"title":"숲의 마물 퇴치","source":"church","goal":1,"count":0})
        g.enemies = [{"name":"상점 주인","x":400,"y":300,"hp":1,"maxhp":1,
                      "atk":1,"level":1,"alive":True,"human":True}]
        g.start_battle(0)
        g.battle_action("basic")
        self.assertEqual(g.mode, "battle")
        self.assertEqual(g.battle["effect"], "slash")
        g.tick(0.6, "[]", "[]", "null")
        self.assertEqual(p["quest"]["count"], 0)
        self.assertIsNotNone(p["quest"])

    def test_thief_becomes_bandit_after_killing_a_human(self):
        g = self.new_game()
        p = g.player
        p.update(job="도둑", faction="방랑자", atk=50)
        g.enemies = [{"name":"상점 주인","x":400,"y":300,"hp":1,"maxhp":1,
                      "atk":1,"level":1,"alive":True,"human":True}]
        g.start_battle(0)
        g.battle_action("basic")
        g.tick(0.6, "[]", "[]", "null")
        self.assertEqual(p["job"], "도적")
        self.assertEqual(g.dialog["title"], "직업 승급")

    def test_repeat_equipment_purchase_does_not_stack_stats(self):
        g = self.new_game()
        p = g.player
        p["gold"] = 500
        g.open_shop()
        g.choose(1)
        self.assertEqual(g.dialog["title"], "무기 진열장")
        self.assertIn(f"철검 · {g.shop_price(60)}G · 공격 변화 +5",g.dialog["options"])
        g.choose(0)
        attack_after_purchase = p["atk"]
        gold_after_purchase = p["gold"]
        g.open_shop()
        g.choose(1)
        self.assertIn("철검 · 보유",g.dialog["options"])
        g.choose(0)
        self.assertEqual(p["atk"], attack_after_purchase)
        self.assertEqual(p["gold"], gold_after_purchase)

    def test_beastkin_pays_five_percent_more_for_equipment(self):
        g = self.new_game()
        g.player["race"] = "수인"
        self.assertEqual(g.shop_price(20), 21)
        self.assertEqual(g.shop_price(60), 63)
        self.assertEqual(g.shop_price(55), 58)

    def test_equipment_shop_shows_race_adjusted_prices_and_net_stat_changes(self):
        g=self.new_game();g.player["race"]="수인"
        g.open_shop();g.choose(1)
        self.assertIn("철검 · 63G · 공격 변화 +5",g.dialog["options"])
        g.open_shop();g.choose(2)
        self.assertIn("가죽 갑옷 · 58G · 방어 변화 +3",g.dialog["options"])

    def test_equipment_shop_marks_owned_armor_and_prevents_duplicate_charge(self):
        g=self.new_game();g.player["gold"]=500
        g.open_shop();g.choose(2)
        self.assertIn(f"가죽 갑옷 · {g.shop_price(55)}G · 방어 변화 +3",g.dialog["options"])
        g.choose(0)
        defense_after_purchase=g.player["def"];gold_after_purchase=g.player["gold"]
        g.open_shop();g.choose(2)
        self.assertEqual(g.dialog["options"][0],"가죽 갑옷 · 보유")
        g.choose(0)
        self.assertEqual(g.player["def"],defense_after_purchase)
        self.assertEqual(g.player["gold"],gold_after_purchase)

    def test_owned_weapons_can_be_swapped_without_losing_level_stats(self):
        g = self.new_game()
        p = g.player
        p["gold"] = 500
        g.gain_xp(35)
        level_attack = p["atk"]
        g.buy_weapon("철검", 60)
        iron_attack = p["atk"]
        g.buy_weapon("사냥꾼 활", 85)
        self.assertEqual(p["weapon"], "사냥꾼 활")
        self.assertEqual(p["atk"], level_attack + 8)
        g.open_inventory()
        g.choose(1)
        g.choose(1)
        self.assertEqual(p["weapon"], "철검")
        self.assertEqual(p["atk"], iron_attack)

    def test_equipment_selector_pages_reach_every_owned_weapon(self):
        g = self.new_game()
        p = g.player
        p["owned_weapons"] = ["낡은 검", "고블린 단검", "철검", "늑대 송곳니검", "사냥꾼 활"]
        g.open_equipment_selector("weapon")
        self.assertEqual(g.dialog["options"], ["낡은 검", "고블린 단검", "다음", "취소"])
        g.choose(2)
        self.assertEqual(g.dialog["options"], ["철검", "늑대 송곳니검", "이전", "다음"])
        g.choose(3)
        self.assertEqual(g.dialog["options"], ["사냥꾼 활", "이전", "취소"])
        g.choose(0)
        self.assertEqual(p["weapon"], "사냥꾼 활")

    def test_weapon_selector_shows_equipped_marker_and_attack_difference(self):
        g = self.new_game()
        p = g.player
        p.update(weapon="철검",atk=18,owned_weapons=["철검","사냥꾼 활","낡은 검"])
        g.open_equipment_selector("weapon")
        self.assertIn("현재 공격 18 · 장비 보너스 +5",g.dialog["text"])
        self.assertIn("철검 · 착용 중",g.dialog["text"])
        self.assertIn("사냥꾼 활 · 장착 시 공격 +3",g.dialog["text"])
        self.assertEqual(g.dialog["options"],["철검","사냥꾼 활","다음","취소"])
        g.choose(1)
        self.assertEqual((p["weapon"],p["atk"]),("사냥꾼 활",21))

    def test_owned_armor_can_be_swapped_without_losing_level_stats(self):
        g = self.new_game()
        p = g.player
        p["gold"] = 500
        g.gain_xp(35)
        level_defense = p["def"]
        g.buy_armor("가죽 갑옷", 55)
        leather_defense = p["def"]
        g.buy_armor("기사 갑옷", 120)
        self.assertEqual(p["def"], level_defense + 6)
        g.open_inventory()
        g.choose(2)
        g.choose(0)
        self.assertEqual(p["armor"], "여행자 옷")
        self.assertEqual(p["def"], level_defense)
        self.assertGreater(leather_defense, level_defense)

    def test_equipment_selector_pages_reach_all_owned_armor(self):
        g = self.new_game()
        p = g.player
        p["owned_armor"] = ["여행자 옷", "방랑자 외투", "가죽 갑옷", "늑대 털망토", "멧돼지 가죽 갑옷", "기사 갑옷"]
        g.open_equipment_selector("armor")
        g.choose(2)
        g.choose(3)
        self.assertEqual(g.dialog["options"], ["멧돼지 가죽 갑옷", "기사 갑옷", "이전", "취소"])
        g.choose(0)
        self.assertEqual(p["armor"], "멧돼지 가죽 갑옷")
        self.assertEqual(p["def"], 8)

    def test_armor_selector_shows_equipped_marker_and_defense_difference(self):
        g = self.new_game()
        p = g.player
        p["armor"]="기사 갑옷";p["def"]=9;p["owned_armor"]=["기사 갑옷","여행자 옷"]
        g.open_equipment_selector("armor")
        self.assertIn("현재 방어 9 · 장비 보너스 +6",g.dialog["text"])
        self.assertIn("기사 갑옷 · 착용 중",g.dialog["text"])
        self.assertIn("여행자 옷 · 장착 시 방어 -6",g.dialog["text"])
        self.assertEqual(g.dialog["options"],["기사 갑옷","여행자 옷","취소"])

    def test_equipped_weapon_and_armor_change_character_render_data(self):
        g = self.new_game()
        shapes = []
        g.draw_character(shapes, 100, 100, "검증", "전사", "인간", "왕실", 1.0,
                         weapon="사냥꾼 활", armor="기사 갑옷")
        colors = {shape.get("c") for shape in shapes}
        self.assertIn("#9ba5af", colors)
        self.assertIn("#895b38", colors)

    def test_monster_can_drop_unique_equipment_and_auto_equip_upgrade(self):
        g = self.new_game()
        p = g.player
        p.update(atk=10, quest=None)
        g.enemies = [{"name":"늑대","x":400,"y":300,"hp":1,"maxhp":1,
                      "atk":1,"level":1,"alive":True}]
        g.start_battle(0)
        with patch("game.random.randint", return_value=3):
            g.battle_action("basic")
        with patch("game.random.random", return_value=0.0):
            g.tick(0.6, "[]", "[]", "null")
        self.assertIn("늑대 송곳니검", p["owned_weapons"])
        self.assertEqual(p["weapon"], "늑대 송곳니검")
        self.assertEqual(p["atk"], 17)
        self.assertIn("희귀 전리품", g.notice)

    def test_town_inn_restores_health_and_mana_for_a_fair_price(self):
        g = self.new_game()
        p = g.player
        p.update(area="마을", race="인간", gold=80, hp=35, maxhp=100, mp=2, maxmp=30, x=970, y=300)
        g.area = "마을"
        g.interact()
        self.assertEqual(g.dialog["title"], "숲길 여관")
        g.choose(0)
        self.assertEqual((p["hp"],p["mp"],p["gold"]),(100,30,55))

    def test_attack_opens_skill_choices_before_damage(self):
        g = self.new_game()
        g.enemies = [{"name":"늑대","x":400,"y":300,"hp":90,"maxhp":90,
                      "atk":1,"level":1,"alive":True}]
        g.start_battle(0)
        g.battle_action("attack")
        self.assertEqual(g.battle["submenu"], "attack")
        self.assertEqual(g.enemies[0]["hp"], 90)
        g.battle_action("skill")
        self.assertLess(g.enemies[0]["hp"], 90)

    def test_skill_without_enough_mana_keeps_attack_menu_open_without_losing_turn(self):
        g=self.new_game()
        g.player.update(job="전사",mp=0,hp=80)
        g.enemies=[{"name":"늑대","x":400,"y":300,"hp":90,"maxhp":90,
                    "atk":12,"level":1,"alive":True}]
        g.start_battle(0)
        g.battle_action("attack")
        enemy_hp=g.enemies[0]["hp"]
        player_hp=g.player["hp"]
        g.battle_action("skill")
        self.assertEqual(g.battle["submenu"],"attack")
        self.assertEqual(g.enemies[0]["hp"],enemy_hp)
        self.assertEqual(g.player["hp"],player_hp)
        self.assertIn("MP 부족",g.battle["log"])

    def test_attack_lunge_changes_position_over_the_effect_animation(self):
        g=self.new_game()
        g.enemies=[{"name":"늑대","x":400,"y":300,"hp":90,"maxhp":90,
                    "atk":1,"level":1,"alive":True}]
        g.start_battle(0)
        g.battle_action("basic")
        g.battle["effect_t"]=.42
        g.draw()
        start=[item for item in json.loads(frames[-1])
               if item.get("t")=="t" and item.get("s")==g.player["name"] and item.get("y",0)>370]
        self.assertEqual(len(start),1)
        g.battle["effect_t"]=.21
        g.draw()
        impact=[item for item in json.loads(frames[-1])
                if item.get("t")=="t" and item.get("s")==g.player["name"] and item.get("y",0)>370]
        self.assertEqual(len(impact),1)
        self.assertGreater(impact[0]["x"],start[0]["x"])

    def test_combat_skill_name_and_cost_follow_the_job(self):
        g=self.new_game()
        self.assertEqual(g.skill_profile(),{"name":"강타","cost":7,"multiplier":2.0,"effect":"strike"})
        g.player["job"]="기사"
        self.assertEqual(g.skill_profile()["name"],"방패 강타")
        self.assertEqual(g.skill_profile()["cost"],6)
        g.player["job"]="도둑"
        self.assertEqual(g.skill_profile()["name"],"급소 찌르기")
        g.player["job"]="성직자"
        self.assertEqual(g.skill_profile()["name"],"성역의 빛")
        self.assertEqual(g.skill_profile()["cost"],8)

    def test_attack_menu_displays_the_current_job_skill_and_cost(self):
        g=self.new_game()
        g.player["job"]="신자"
        g.enemies=[{"name":"늑대","x":400,"y":300,"hp":90,"maxhp":90,
                     "atk":1,"level":1,"alive":True}]
        g.start_battle(0);g.battle_action("attack");g.draw()
        labels=[item.get("s","") for item in json.loads(frames[-1]) if item.get("t")=="t"]
        self.assertIn("2 기도의 빛 · MP 5",labels)
        g.player["job"]="성직자"
        g.battle_action("attack");g.draw()
        labels=[item.get("s","") for item in json.loads(frames[-1]) if item.get("t")=="t"]
        self.assertIn("2 성역의 빛 · MP 8",labels)

    def test_believer_skill_deals_damage_heals_and_spends_mana(self):
        g=self.new_game()
        g.player.update(job="신자",hp=50,maxhp=100,mp=10)
        g.enemies=[{"name":"늑대","x":400,"y":300,"hp":90,"maxhp":90,
                     "atk":1,"level":1,"alive":True}]
        g.start_battle(0);g.battle_action("attack")
        with patch.object(g,"enemy_turn"):
            g.battle_action("skill")
        self.assertEqual(g.player["mp"],5)
        self.assertEqual(g.player["hp"],58)
        self.assertLess(g.enemies[0]["hp"],90)
        self.assertIn("기도의 빛",g.battle["log"])

    def test_priest_skill_deals_damage_and_restores_fourteen_percent_health(self):
        g=self.new_game()
        g.player.update(job="성직자",hp=40,maxhp=100,mp=16,atk=10)
        g.enemies=[{"name":"늑대","x":400,"y":300,"hp":90,"maxhp":90,
                     "atk":1,"level":1,"alive":True}]
        g.start_battle(0);g.battle_action("attack")
        with patch("game.random.randint",return_value=0),patch.object(g,"enemy_turn"):
            g.battle_action("skill")
        self.assertEqual(g.player["mp"],8)
        self.assertEqual(g.player["hp"],54)
        self.assertLess(g.enemies[0]["hp"],90)
        self.assertIn("성역의 빛",g.battle["log"])

    def test_crusader_holy_skill_has_bonus_against_monsters(self):
        results=[]
        for human in (False,True):
            g=self.new_game();g.player.update(job="성전사",atk=10,mp=20)
            g.enemies=[{"name":"경비병" if human else "늑대","x":400,"y":300,
                        "hp":100,"maxhp":100,"atk":1,"level":1,"alive":True,"human":human}]
            g.start_battle(0);g.battle_action("attack")
            with patch("game.random.randint",return_value=0),patch.object(g,"enemy_turn"):
                g.battle_action("skill")
            results.append(100-g.enemies[0]["hp"])
        self.assertGreater(results[0],results[1])

    def test_defense_blocks_the_enemy_turn(self):
        g = self.new_game()
        g.player["hp"] = 55
        g.enemies = [{"name":"멧돼지","x":400,"y":300,"hp":90,"maxhp":90,
                      "atk":30,"level":1,"alive":True}]
        g.start_battle(0)
        g.battle_action("defend")
        self.assertEqual(g.player["hp"], 55)
        self.assertFalse(g.battle["defending"])

    def test_bandage_does_not_consume_a_combat_turn(self):
        g = self.new_game()
        g.player.update(hp=50, maxhp=100, bandages=2)
        g.enemies = [{"name":"늑대","x":400,"y":300,"hp":90,"maxhp":90,
                      "atk":30,"level":1,"alive":True}]
        g.start_battle(0)
        g.battle_action("item")
        self.assertEqual(g.player["hp"], 62)
        self.assertEqual(g.player["bandages"], 1)
        self.assertEqual(g.enemies[0]["hp"], 90)

    def test_bandage_is_not_wasted_at_full_health(self):
        g = self.new_game()
        p = g.player
        p.update(hp=100, maxhp=100, bandages=1)
        g.enemies = [{"name":"늑대","x":400,"y":300,"hp":90,"maxhp":90,
                      "atk":1,"level":1,"alive":True}]
        g.start_battle(0)
        g.battle_action("item")
        self.assertEqual(p["bandages"], 1)
        self.assertEqual(g.enemies[0]["hp"], 90)

    def test_forest_walk_triggers_an_immediate_ambush(self):
        g = self.new_game()
        g.area = "숲"
        g.player.update(area="숲", x=1200, y=800)
        g.spawn_enemies()
        g.walk_meter = 189
        with patch("game.random.random", return_value=0.0):
            g.update_world_ai(0.1, 2)
        self.assertEqual(g.mode, "battle")
        self.assertIn(g.enemies[g.battle["index"]]["name"], {"멧돼지", "늑대", "고블린"})

    def test_forest_tree_trunks_block_movement(self):
        g=self.new_game();g.area="숲";g.player.update(area="숲",x=90,y=372)
        self.assertTrue(g.collides(40,372))
        with patch.object(g,"update_world_ai"):
            for _ in range(10):g.tick(.05,'["ArrowLeft"]',"[]","null")
        self.assertGreaterEqual(g.player["x"],56)
        self.assertEqual(g.player["y"],372)

    def test_town_shop_is_reachable_through_the_building_door(self):
        g=self.new_game();g.area="마을";g.player.update(area="마을",x=240,y=330)
        self.assertFalse(g.collides(240,270))
        self.assertTrue(g.collides(200,270))
        for _ in range(3):g.tick(.05,'["ArrowUp"]',"[]","null")
        g.interact()
        self.assertEqual(g.dialog["title"],"상점")

    def test_fled_ambush_enemy_can_resume_patrolling(self):
        g = self.new_game()
        g.area = "숲"
        g.player["area"] = "숲"
        g.start_ambush()
        ambush = g.enemies[-1]
        ambush.pop("turn", None)  # Older saved ambushes did not have an AI timer.
        with patch("game.random.random", return_value=0.0):
            g.battle_action("flee")
        self.assertEqual(g.mode, "world")
        with patch("game.random.uniform", return_value=2.0):
            g.update_world_ai(0.1, 0)
        self.assertIn("turn", ambush)

    def test_click_on_visible_attack_skill_option_selects_it(self):
        g = self.new_game()
        g.enemies = [{"name":"늑대","x":400,"y":300,"hp":90,"maxhp":90,
                      "atk":1,"level":1,"alive":True}]
        g.start_battle(0)
        g.battle_action("attack")
        g.tick(0.03, "[]", "[]", '{"x":480,"y":450}')
        self.assertIsNone(g.battle.get("submenu"))
        self.assertLess(g.enemies[0]["hp"], 90)

    def test_battle_resolves_only_one_pointer_or_keyboard_action_per_frame(self):
        g = self.new_game()
        g.enemies = [{"name":"늑대","x":400,"y":300,"hp":90,"maxhp":90,
                      "atk":20,"level":1,"alive":True}]
        g.start_battle(0)
        # A defend click and an attack key in the same frame must not spend
        # the defended turn and then immediately start a second turn.
        g.tick(0.03, "[]", '["1"]', '{"x":400,"y":502}')
        self.assertEqual(g.player["hp"], g.player["maxhp"])
        self.assertEqual(g.enemies[0]["hp"], 90)
        g.tick(0.03, "[]", '["1"]', "null")
        self.assertEqual(g.battle.get("submenu"), "attack")
        g.tick(0.03, "[]", '["1"]', "null")
        self.assertLess(g.enemies[0]["hp"], 90)
        self.assertLess(g.player["hp"], g.player["maxhp"])

    def test_canvas_click_selects_a_dialog_option(self):
        g = self.new_game()
        g.promote("기사")
        # Promotion endings include the clue-dependent chapter epilogue, so
        # advance through any text pages before choosing the final option.
        for _ in range(g.dialog_page_count() - 1):
            g.tick(0.03, "[]", '[" "]', "null")
        option_y = g.dialog_options_y()
        g.tick(0.03, "[]", "[]", json.dumps({"x":200,"y":option_y+18}))
        self.assertIsNone(g.dialog)
        self.assertIn("1장 완료", g.notice)

    def test_long_dialog_uses_pages_before_enabling_choices(self):
        g = self.new_game()
        text=" ".join(["기록관은 왕실과 교회가 감춘 전쟁의 흔적을 숲의 폐허에서 더 찾아보라고 말했다."]*8)
        g.open_dialog("전쟁의 기록",text,["계속","닫기"])
        wrapped=g.wrap_text(text,44)
        self.assertGreater(len(wrapped),7)
        self.assertEqual(" ".join(wrapped),text)
        self.assertEqual(g.dialog_page_count(),2)
        self.assertEqual(len(g.dialog_page_lines()),7)
        option_y=g.dialog_options_y()
        self.assertGreater(option_y,300)
        g.tick(.03,"[]","[]",json.dumps({"x":200,"y":option_y+18}))
        self.assertEqual(g.dialog["text_page"],0)
        g.tick(.03,"[]",'[" "]',"null")
        self.assertEqual(g.dialog["text_page"],1)
        option_y=g.dialog_options_y()
        g.tick(.03,"[]","[]",json.dumps({"x":200,"y":option_y+18}))
        self.assertIsNone(g.dialog)

    def test_dialog_page_survives_resume_and_invalid_page_is_rejected(self):
        g = self.new_game()
        text=" ".join(["기록관은 왕실과 교회가 감춘 전쟁의 흔적을 숲의 폐허에서 더 찾아보라고 말했다."]*8)
        g.open_dialog("전쟁의 기록",text,["계속"])
        g.dialog["text_page"]=1
        resumed=game.Game()
        self.assertTrue(resumed.load_snapshot(g.save_snapshot()))
        self.assertEqual(resumed.dialog["text_page"],1)
        snapshot=json.loads(g.save_snapshot());snapshot["dialog"]["text_page"]=5
        invalid=game.Game()
        self.assertFalse(invalid.load_snapshot(json.dumps(snapshot)))

    def test_dialog_page_buttons_support_pointer_and_touch(self):
        g = self.new_game()
        text=" ".join(["기록관은 왕실과 교회가 감춘 전쟁의 흔적을 숲의 폐허에서 더 찾아보라고 말했다."]*8)
        g.open_dialog("전쟁의 기록",text,["계속"])
        g.tick(.03,"[]","[]",json.dumps({"x":790,"y":111}))
        self.assertEqual(g.dialog["text_page"],1)
        g.tick(.03,"[]","[]",json.dumps({"x":670,"y":111}))
        self.assertEqual(g.dialog["text_page"],0)

    def test_notice_text_wraps_without_losing_words(self):
        g = self.new_game()
        wrapped=g.wrap_text(g.notice,40)
        self.assertGreater(len(wrapped),1)
        self.assertEqual(" ".join(" ".join(wrapped).split())," ".join(g.notice.split()))

    def test_mobile_controls_include_quest_and_inventory_actions(self):
        html=(ROOT/"index.html").read_text(encoding="utf-8")
        mobile=html.split('<div class="mobile"',1)[1].split('</div></div>',1)[0]
        for action in ("e","1","2","3","h","q","i","m"):
            self.assertIn(f'data-press="{action}"',mobile)
        for direction in ("ArrowUp","ArrowDown","ArrowLeft","ArrowRight"):
            self.assertIn(f'data-hold="{direction}"',mobile)

    def test_web_shell_keeps_form_keys_out_of_game_and_clears_held_keys_on_blur(self):
        html=(ROOT/"index.html").read_text(encoding="utf-8")
        self.assertIn('src="https://cdn.jsdelivr.net/pyodide/v314.0.7/full/pyodide.js"',html)
        self.assertIn("if(isTextEntry(e.target))return;",html)
        self.assertIn("e.target.closest('button')&&['Enter',' '].includes(k)",html)
        self.assertIn("window.addEventListener('blur',()=>{held.clear();presses.length=0;click=null})",html)
        self.assertIn("addEventListener('click',e=>{e.preventDefault();presses.push(b.dataset.press)})",html)

    def test_title_screen_uses_a_local_optimized_chapter_illustration(self):
        html=(ROOT/"index.html").read_text(encoding="utf-8")
        artwork=ROOT/"assets/chapter1-title.jpg"
        self.assertIn('url("./assets/chapter1-title.jpg")',html)
        self.assertTrue(artwork.is_file())
        self.assertLess(artwork.stat().st_size,750_000)

    def test_area_map_pauses_movement_and_escape_closes_it(self):
        g = self.new_game()
        p = g.player
        g.area = "왕국 안"
        p.update(area="왕국 안",x=500,y=400)
        start_x=p["x"]
        g.tick(.03,'["ArrowRight"]','["m"]',"null")
        self.assertTrue(g.map_open)
        self.assertEqual(p["x"],start_x)
        labels=[item.get("s","") for item in json.loads(frames[-1]) if item.get("t")=="t"]
        self.assertIn("현재 구역 지도 · 왕국 안",labels)
        self.assertIn("왕의 방",labels)
        g.tick(.03,'["ArrowRight"]',"[]","null")
        self.assertEqual(p["x"],start_x)
        g.tick(.03,"[]",'["Escape"]',"null")
        self.assertFalse(g.map_open)
        g.tick(.05,'["ArrowRight"]',"[]","null")
        self.assertGreater(p["x"],start_x)

    def test_open_area_map_survives_save_and_resume(self):
        g = self.new_game()
        g.tick(.03,"[]",'["m"]',"null")
        resumed=game.Game()
        self.assertTrue(resumed.load_snapshot(g.save_snapshot()))
        self.assertTrue(resumed.map_open)

    def test_long_map_exit_labels_stay_inside_the_map_panel(self):
        g = self.new_game()
        g.area = "숲"
        out=[]
        g.draw_area_map(out)
        label=next(item for item in out if item.get("t")=="t" and item.get("s")=="마을로 가는 길")
        self.assertLessEqual(label["x"]+len(label["s"])*10,820)

    def test_area_map_highlights_the_active_church_task(self):
        g = self.new_game()
        g.area="교회 안"
        g.player.update(area="교회 안",quest={"title":"교회 청소","source":"church_simple","goal":1,"count":0})
        out=[];g.draw_area_map(out)
        label=next(item for item in out if item.get("t")=="t" and item.get("s")=="목표: 청소 구역")
        target=next(item for item in out if item.get("t")=="c" and item.get("c")=="#f08a5b")
        self.assertTrue(label)
        self.assertTrue(target)

    def test_area_map_highlights_live_monsters_for_kill_quests(self):
        g = self.new_game()
        g.area="숲"
        g.player.update(area="숲",quest={"title":"왕실 토벌","source":"kingdom","goal":1,"count":0})
        g.spawn_enemies()
        out=[];g.draw_area_map(out)
        target_labels=[item["s"] for item in out if item.get("t")=="t" and item.get("s","").startswith("의뢰 대상:")]
        self.assertEqual(len(target_labels),sum(e["alive"] and not e.get("human") for e in g.enemies))

    def test_malformed_map_state_is_rejected(self):
        g = self.new_game()
        snapshot=json.loads(g.save_snapshot())
        snapshot["map_open"]="yes"
        resumed=game.Game()
        self.assertFalse(resumed.load_snapshot(json.dumps(snapshot)))

    def test_quest_journal_shows_progress_and_next_action(self):
        g = self.new_game()
        g.area="교회 밖";g.player.update(area="교회 밖",job="미정",faction="교회")
        self.assertIn("목표: 교회 안 수련관에서 전사 또는 신자 직업 선택",g.quest_journal_text())
        g.player["quest"]={"title":"숲의 마물 퇴치","source":"church","goal":1,"count":0}
        text=g.quest_journal_text()
        self.assertIn("숲의 마물 퇴치 · 0/1",text)
        self.assertIn("숲의 마물을 처치한 뒤 교회 제단에서 기도",text)
        g.player["quest"]={"title":"교회 청소","source":"church_simple","goal":1,"count":0}
        self.assertIn("교회 안의 청소 구역을 조사",g.quest_journal_text())

    def test_untrained_journal_guides_each_start_to_its_first_job(self):
        cases=[
            ("교회 안","교회","수련관에서 전사 또는 신자 직업 선택"),
            ("왕실 상점가","왕실","왕국 기사단 교관에게서 전사 직업 선택"),
            ("숲","방랑자","야영지에서 도둑 직업 선택 또는 동쪽 길로 마을 이동"),
            ("마을","무소속","주민에게 의뢰를 받거나 교회·왕실 진영으로 이동"),
        ]
        for area,faction,expected in cases:
            g=self.new_game();g.area=area
            g.player.update(area=area,faction=faction,job="미정")
            self.assertIn("목표: "+expected,g.quest_journal_text())

    def test_journal_prioritizes_church_prayer_due_before_a_new_quest(self):
        g=self.new_game();g.player.update(faction="교회",job="전사",prayer_due=True,quest=None)
        self.assertIn("목표: 교회 안 제단에서 기도",g.quest_journal_text())

    def test_hud_and_quest_journal_show_experience_progress(self):
        g = self.new_game()
        g.player.update(level=2,xp=17)
        self.assertIn("경험치 17/70",g.quest_journal_text())
        self.assertIn("다음 레벨까지 53",g.quest_journal_text())
        g.draw()
        scene=json.loads(frames[-1])
        labels=[item.get("s","") for item in scene if item.get("t")=="t"]
        self.assertTrue(any("Lv.2 XP 17/70" in label for label in labels))
        fill=next(item for item in scene if item.get("t")=="r" and item.get("x")==690 and item.get("y")==59 and item.get("c")=="#e2c783")
        self.assertAlmostEqual(fill["w"],230*17/70)

    def test_chapter_completion_is_visible_after_resume(self):
        g = self.new_game()
        g.promote("성전사")
        self.assertIn("제1장 완료",g.quest_journal_text())
        self.assertIn("목표: 제1장 완료",g.quest_journal_text())
        self.assertIn("전쟁의 배후를 밝힐 단서는 아직 부족하다",g.dialog["text"])
        resumed = game.Game()
        self.assertTrue(resumed.load_snapshot(g.save_snapshot()))
        self.assertIn("제1장 완료",resumed.quest_journal_text())

    def test_chapter_ending_uses_faction_clues_and_remains_in_journal_after_resume(self):
        cases=[
            (["chapter1:church:3"],"교회 기록에는 왕실 문양과 교회 보급품이 함께 남았다"),
            (["chapter1:royal:3"],"왕실 보고서에는 교회 문양과 양쪽 진영의 표식이 함께 남았다"),
            (["chapter1:church:7","chapter1:royal:7"],"양쪽 진영의 기록은 서로를 전쟁의 원인으로 지목한다"),
        ]
        for flags,expected in cases:
            g=self.new_game()
            g.player["story_flags"]=flags
            g.promote("기사")
            self.assertIn(expected,g.dialog["text"])
            self.assertIn("제1장 결말: "+expected,g.quest_journal_text())
            resumed=game.Game()
            self.assertTrue(resumed.load_snapshot(g.save_snapshot()))
            self.assertIn("제1장 결말: "+expected,resumed.quest_journal_text())

    def test_quest_journal_keeps_discovered_story_clues_after_resume(self):
        g=self.new_game()
        g.player["story_flags"]=["chapter1:church:3","chapter1:royal:7","chapter1:unknown:99"]
        text=g.quest_journal_text()
        self.assertIn("전쟁 단서 2/4",text)
        self.assertIn("교회 기록: 마물 굴에서 왕실 문양이 찍힌 화살촉",text)
        self.assertIn("왕실 기록: 폐허의 상자에는 양쪽 진영의 표식이 함께 찍혀 있었다",text)
        resumed=game.Game()
        self.assertTrue(resumed.load_snapshot(g.save_snapshot()))
        resumed_text=resumed.quest_journal_text()
        self.assertIn("전쟁 단서 2/4",resumed_text)
        self.assertIn("양쪽 진영의 표식이 함께 찍혀 있었다",resumed_text)

    def test_wanderer_groups_move_automatically(self):
        g = self.new_game()
        g.area = "숲"
        g.player["area"] = "숲"
        g.spawn_enemies()
        before = (g.wanderers[0]["x"], g.wanderers[0]["y"])
        g.update_world_ai(0.5, 0)
        after = (g.wanderers[0]["x"], g.wanderers[0]["y"])
        self.assertNotEqual(before, after)

    def test_forest_random_spawns_are_clear_of_trees_player_and_each_other(self):
        g = self.new_game()
        g.area = "숲"
        g.player.update(area="숲", x=1200, y=800)
        for seed in range(40):
            random.seed(seed)
            g.spawn_enemies()
            actors = list(g.wanderers) + [e for e in g.enemies if not e.get("human")]
            for actor in actors:
                x,y=actor["x"],actor["y"]
                self.assertFalse(g.collides(x,y), f"spawned inside a tree at {(x,y)} for seed {seed}")
                self.assertGreaterEqual(((x-g.player["x"])**2+(y-g.player["y"])**2)**.5,160)
            for i,(x,y) in enumerate((a["x"],a["y"]) for a in actors):
                for ox,oy in ((a["x"],a["y"]) for a in actors[:i]):
                    self.assertGreaterEqual(((x-ox)**2+(y-oy)**2)**.5,84)

    def test_ambush_enemy_spawns_outside_nearby_tree_trunk(self):
        g=self.new_game()
        g.area="숲";g.player.update(area="숲",x=320,y=413)
        g.start_ambush()
        enemy=g.enemies[g.battle["index"]]
        self.assertFalse(g.collides(enemy["x"],enemy["y"]))
        self.assertLess(((enemy["x"]-320)**2+(enemy["y"]-413)**2)**.5,100)

    def test_forest_save_migrates_actors_trapped_inside_tree_trunks(self):
        g=self.new_game()
        g.area="숲";g.player.update(area="숲",x=1200,y=800)
        g.enemies=[{"name":"늑대","x":360,"y":413,"hp":20,"maxhp":20,
                    "atk":5,"level":1,"alive":True,"vx":20,"vy":10,"turn":2}]
        g.wanderers=[{"x":760,"y":1183,"vx":20,"vy":10,"turn":2,"size":3}]
        resumed=game.Game()
        self.assertTrue(resumed.load_snapshot(g.save_snapshot()))
        self.assertFalse(resumed.collides(resumed.enemies[0]["x"],resumed.enemies[0]["y"]))
        self.assertFalse(resumed.collides(resumed.wanderers[0]["x"],resumed.wanderers[0]["y"]))

    def test_forest_wanderers_and_monsters_stop_at_tree_trunks(self):
        g = self.new_game()
        g.area = "숲"
        g.wanderers = [{"x":320,"y":413,"vx":42,"vy":0,"turn":100,"size":3}]
        g.enemies = [{"name":"늑대","x":1670,"y":1293,"hp":20,"maxhp":20,
                      "atk":5,"level":1,"alive":True,"vx":25,"vy":0,"turn":100}]
        for _ in range(20):
            g.update_world_ai(.1,0)
        self.assertLess(g.wanderers[0]["x"], 345)
        self.assertLessEqual(g.enemies[0]["x"], 1695)

    def test_e_dismisses_the_notice_without_interacting(self):
        g = self.new_game()
        g.notice = "닫을 안내"
        g.notice_t = 3
        g.tick(0.03, "[]", '["e"]', "null")
        self.assertEqual(g.notice_t, 0)
        self.assertIsNone(g.dialog)

    def test_royal_route_is_connected_in_order(self):
        g = self.new_game()
        g.area = "마을"
        g.player.update(area="마을", race="인간", faction="왕실")
        route = ("왕실 상점가", "왕국 기사단", "왕국 안", "왕의 방")
        for area in route:
            g.move_area(area)
            self.assertEqual(g.area, area)

    def test_neutral_village_does_not_replace_last_faction_respawn(self):
        g = self.new_game()
        g.player.update(hp=1, maxhp=100, gold=101, faction="교회", area="교회 안", visited_faction="교회 안")
        g.area = "교회 안"
        g.move_area("마을")
        self.assertEqual(g.player["visited_faction"], "교회 안")
        g.enemies = [{"name":"늑대","x":400,"y":300,"hp":90,"maxhp":90,
                      "atk":40,"level":1,"alive":True}]
        g.start_battle(0)
        g.enemy_turn()
        self.assertEqual(g.area, "교회 안")
        self.assertEqual(g.player["gold"], 50)
        self.assertEqual(g.player["hp"], g.player["maxhp"])
        self.assertEqual((g.player["x"], g.player["y"]), (480, 640))


if __name__ == "__main__":
    unittest.main()
