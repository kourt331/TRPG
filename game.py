"""Chapter 1 prototype: top-down, turn-based fantasy RPG. Runs in Pyodide."""
import json, random, math
from js import window

W, H = 960, 600
AREAS = {
    "숲": ("#243b31", "#35543a"), "마을": ("#64513c", "#806647"),
    "교회 밖": ("#394356", "#56617a"), "교회 안": ("#4b5365", "#6b7180"),
    "왕실 상점가": ("#49394c", "#765343"), "왕국 기사단": ("#3d4652", "#56616a"),
    "왕국 안": ("#624d3d", "#806348"), "왕의 방": ("#503b43", "#80605a"),
}
MAP_SIZE = {
    "숲": (2400, 1600), "마을": (1400, 1000), "교회 밖": (1200, 900), "교회 안": (960, 720),
    "왕실 상점가": (1200, 900), "왕국 기사단": (1000, 760), "왕국 안": (1000, 760), "왕의 방": (900, 650),
}
FLOOR_PALETTES = {
    "숲": ("#294633", "#2b4834", "#2d4a35"),
    "마을": ("#78664a", "#79684d", "#7b6a4f"),
    "교회 밖": ("#64605b", "#66625d", "#68645f"),
    "교회 안": ("#747579", "#76777b", "#78797d"),
    "왕실 상점가": ("#69564d", "#6b584f", "#6d5a50"),
    "왕국 기사단": ("#58616a", "#5a636c", "#5c656e"),
    "왕국 안": ("#766047", "#78624a", "#7a644b"),
    "왕의 방": ("#57474c", "#59494e", "#5b4b50"),
}
WEAPON_BONUS = {"낡은 검":0,"고블린 단검":4,"철검":5,"늑대 송곳니검":7,"사냥꾼 활":8}
ARMOR_BONUS = {"여행자 옷":0,"방랑자 외투":2,"가죽 갑옷":3,"늑대 털망토":4,"멧돼지 가죽 갑옷":5,"기사 갑옷":6}
MONSTER_LOOT = {
    "고블린": ("weapon", "고블린 단검", .22),
    "늑대": ("weapon", "늑대 송곳니검", .16),
    "멧돼지": ("armor", "멧돼지 가죽 갑옷", .14),
}
CHAPTER_STORY_BEATS = {
    "church": {
        3:"마물 굴에서 왕실 문양이 찍힌 화살촉을 찾았다. 성직자는 전쟁의 흔적일 수 있다며 기록하라고 한다.",
        7:"숲 폐허의 야영지에서 왕실 장비와 교회 보급 천 조각이 함께 나왔다. 어느 쪽도 이를 쉽게 설명하지 못한다.",
    },
    "royal": {
        3:"마물 굴에서 교회 문양이 찍힌 약초 주머니를 찾았다. 기록관은 교회가 숲에 개입했다는 증거라 주장한다.",
        7:"폐허의 상자에는 양쪽 진영의 표식이 함께 찍혀 있었다. 왕은 보고서를 봉인하고 토벌을 계속하라 명한다.",
    },
}
JOB_SKILLS = {
    "전사":{"name":"회전 베기","cost":7,"multiplier":1.9,"effect":"strike"},
    "기사":{"name":"방패 강타","cost":6,"multiplier":1.7,"effect":"strike"},
    "성전사":{"name":"성스러운 일격","cost":8,"multiplier":2.0,"effect":"holy"},
    "신자":{"name":"기도의 빛","cost":5,"multiplier":1.35,"effect":"heal"},
    "성직자":{"name":"성역의 빛","cost":8,"multiplier":1.7,"effect":"heal"},
    "도둑":{"name":"급소 찌르기","cost":5,"multiplier":1.5,"effect":"critical"},
    "도적":{"name":"기습","cost":7,"multiplier":1.8,"effect":"critical"},
}

class Game:
    def __init__(self):
        self.started = False
        self.keys_last = set()
        self.player = {}
        self.area = "숲"
        self.dialog = None
        self.map_open = False
        self.notice = ""
        self.notice_t = 0
        self.enemies = []
        self.wanderers = []
        self.walk_meter = 0
        self.encounter_meter = 0
        self.tick_n = 0
        self.save_elapsed = 0
        self.player_walking = False
        self.walk_phase = 0.0

    def start(self, name):
        race = random.choice(["인간", "수인"])
        gender = random.choice(["남성", "여성"])
        starts = ["숲", "교회 밖", "왕실 상점가", "마을"] if race == "인간" else ["숲", "교회 밖", "마을"]
        area = random.choice(starts)
        faction = {"숲":"방랑자", "교회 밖":"교회", "왕실 상점가":"왕실", "마을":"무소속"}[area]
        religion = {"숲":"숲의 신앙", "교회 밖":"교회 신앙", "왕실 상점가":"왕실 신앙", "마을":"숲의 신앙"}[area]
        mw,mh=MAP_SIZE[area]
        self.player = {
            "name": (name or "이름 없는 여행자")[:14], "race":race, "gender":gender,"religion":religion,
            "area":area,"faction":faction,"job":"미정","x":mw//2,"y":mh//2,"facing":"down",
            "hp":100,"maxhp":100,"mp":30,"maxmp":30,"level":1,"xp":0,
            "gold":80,"bandages":1,"weapon":"낡은 검","armor":"여행자 옷",
            "atk":10,"def":3,"quest":None,"quest_kills":0,"priest_refusals":0,
            "prayer_count":0,"church_quests_completed":0,"prayer_due":False,"king_quests":0,"exiled":False,
            "bandit_unlocked":False,"visited_faction":faction,"promoted":False,
            "owned_weapons":["낡은 검"],"owned_armor":["여행자 옷"],
            "inventory":["낡은 검","여행자 옷","회복 붕대 ×1"],"story_flags":[]
        }
        self.player["visited_faction"]=area
        self.area=area; self.enemies=[]; self.wanderers=[]; self.dialog=None; self.map_open=False; self.started=True
        self.mode="world";self.walk_meter=0;self.encounter_meter=0
        self.player_walking=False;self.walk_phase=0.0
        self.notice = self.intro_text(); self.notice_t=9
        self.spawn_enemies()
        self.draw()
        self.persist()

    def save_snapshot(self):
        data={"version":1,"player":self.player,"area":self.area,"enemies":self.enemies,
              "wanderers":self.wanderers,"walk_meter":self.walk_meter,"encounter_meter":self.encounter_meter,
              "mode":getattr(self,"mode","world"),"battle":getattr(self,"battle",None),
              "dialog":self.dialog,"map_open":self.map_open,
              "notice":self.notice,"notice_t":self.notice_t,"tick_n":self.tick_n}
        return json.dumps(data,ensure_ascii=False,separators=(",",":"))

    def persist(self):
        if not self.started:return
        try:window.gameBridge.save(self.save_snapshot())
        except Exception:pass

    def load_snapshot(self, raw):
        try:
            data=json.loads(str(raw))
            p=data["player"];area=data["area"]
            if not isinstance(data,dict) or not isinstance(p,dict) or area not in AREAS: return False
            p=dict(p)
            required=("name","race","gender","faction","job","x","y","hp","maxhp","mp","maxmp",
                      "level","xp","gold","bandages","weapon","armor","atk","def","prayer_count",
                      "church_quests_completed","priest_refusals","king_quests")
            if any(key not in p for key in required):return False
            if p["race"] not in ("인간","수인") or p["gender"] not in ("남성","여성"):return False
            if p["faction"] not in ("교회","왕실","방랑자","무소속"):return False
            numbers=("x","y","hp","maxhp","mp","maxmp","level","xp","gold","bandages","atk","def",
                     "prayer_count","church_quests_completed","priest_refusals","king_quests")
            if any(isinstance(p[key],bool) or not isinstance(p[key],(int,float)) or not math.isfinite(p[key]) for key in numbers):return False
            if p["maxhp"]<=0 or p["maxmp"]<0 or p["level"]<1 or p["gold"]<0 or p["bandages"]<0:return False
            if p["hp"]<0 or p["hp"]>p["maxhp"] or p["mp"]<0 or p["mp"]>p["maxmp"]:return False
            text_fields=("name","job","weapon","armor")
            if any(not isinstance(p[key],str) or not p[key] for key in text_fields):return False
            mapw,maph=MAP_SIZE[area]
            if not (0<=p["x"]<=mapw and 0<=p["y"]<=maph):return False
            p.setdefault("facing","down")
            if p["facing"] not in ("up","down","left","right"):return False
            p.setdefault("religion",{"숲":"숲의 신앙","교회 밖":"교회 신앙","교회 안":"교회 신앙",
                                      "왕실 상점가":"왕실 신앙","왕국 기사단":"왕실 신앙","왕국 안":"왕실 신앙","왕의 방":"왕실 신앙"}.get(area,"숲의 신앙"))
            p.setdefault("owned_weapons",[p.get("weapon","낡은 검")]);p.setdefault("owned_armor",[p.get("armor","여행자 옷")])
            p.setdefault("quest",None);p.setdefault("exiled",False);p.setdefault("prayer_due",False)
            p.setdefault("visited_faction",area);p["area"]=area
            p.setdefault("inventory",[]);p.setdefault("story_flags",[])
            for key in ("owned_weapons","owned_armor","inventory","story_flags"):
                if not isinstance(p[key],list) or any(not isinstance(item,str) for item in p[key]):return False
            if p["weapon"] not in p["owned_weapons"]:p["owned_weapons"].append(p["weapon"])
            if p["armor"] not in p["owned_armor"]:p["owned_armor"].append(p["armor"])
            if not isinstance(p["religion"],str) or p["religion"] not in ("교회 신앙","왕실 신앙","숲의 신앙"):return False
            if any(not isinstance(p[key],bool) for key in ("exiled","prayer_due")):return False
            enemies=data.get("enemies",[]);wanderers=data.get("wanderers",[])
            if not isinstance(enemies,list) or not isinstance(wanderers,list):return False
            enemy_fields=("name","x","y","hp","maxhp","atk","level","alive")
            for enemy in enemies:
                if not isinstance(enemy,dict) or any(field not in enemy for field in enemy_fields):return False
                if not isinstance(enemy["name"],str) or not isinstance(enemy["alive"],bool):return False
                enemy_numbers=("x","y","hp","maxhp","atk","level")+tuple(k for k in ("vx","vy","turn") if k in enemy)
                if any(isinstance(enemy[k],bool) or not isinstance(enemy[k],(int,float)) or not math.isfinite(enemy[k]) for k in enemy_numbers):return False
                if enemy["maxhp"]<=0 or enemy["hp"]<0 or enemy["hp"]>enemy["maxhp"] or enemy["level"]<1:return False
                if "human" in enemy and not isinstance(enemy["human"],bool):return False
            for group in wanderers:
                if not isinstance(group,dict) or any(field not in group for field in ("x","y","vx","vy","turn")):return False
                group_numbers=("x","y","vx","vy","turn")+tuple(k for k in ("size",) if k in group)
                if any(isinstance(group[k],bool) or not isinstance(group[k],(int,float)) or not math.isfinite(group[k]) for k in group_numbers):return False
            quest=p["quest"]
            if quest is not None:
                if not isinstance(quest,dict) or any(field not in quest for field in ("title","source","goal","count")):return False
                if not isinstance(quest["title"],str) or not isinstance(quest["source"],str):return False
                if any(isinstance(quest[k],bool) or not isinstance(quest[k],(int,float)) or not math.isfinite(quest[k]) for k in ("goal","count")):return False
                if quest["goal"]<1 or quest["count"]<0:return False
            dialog=data.get("dialog")
            if dialog is not None:
                if not isinstance(dialog,dict) or not isinstance(dialog.get("options"),list):return False
                if not isinstance(dialog.get("title"),str) or not isinstance(dialog.get("text"),str):return False
                if any(not isinstance(option,str) for option in dialog["options"]):return False
                dialog=dict(dialog);text_page=dialog.get("text_page",0)
                page_count=max(1,math.ceil(len(self.wrap_text(dialog["text"],44))/7))
                if isinstance(text_page,bool) or not isinstance(text_page,int) or not 0<=text_page<page_count:return False
                dialog["text_page"]=text_page
            mode=data.get("mode","world")
            battle=data.get("battle")
            if mode not in ("world","battle"):return False
            map_open=data.get("map_open",False)
            if not isinstance(map_open,bool):return False
            if mode=="battle":
                if not isinstance(battle,dict) or not isinstance(battle.get("index"),int) or not 0<=battle["index"]<len(enemies):return False
                if not isinstance(battle.get("defending"),bool) or not isinstance(battle.get("log"),str):return False
                if battle.get("submenu") not in (None,"attack"):return False
                for key in ("effect_t","counter_t"):
                    value=battle.get(key,0)
                    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):return False
            progress={}
            for key in ("walk_meter","encounter_meter","notice_t"):
                value=data.get(key,0)
                if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):return False
                progress[key]=max(0,float(value))
            tick_n=data.get("tick_n",0)
            if isinstance(tick_n,bool) or not isinstance(tick_n,int) or tick_n<0:return False
            self.player=p;self.area=area;self.enemies=enemies;self.wanderers=wanderers
            self.player_walking=False;self.walk_phase=0.0
            self.walk_meter=progress["walk_meter"];self.encounter_meter=progress["encounter_meter"]
            self.mode=mode
            self.dialog=dialog;self.notice=str(data.get("notice",""));self.notice_t=progress["notice_t"]
            self.map_open=map_open and mode=="world" and dialog is None
            self.tick_n=tick_n;self.save_elapsed=0;self.started=True
            if self.mode=="battle" and isinstance(battle,dict) and isinstance(battle.get("index"),int) and 0<=battle["index"]<len(enemies):
                self.battle=battle
            else:
                self.mode="world"
                if hasattr(self,"battle"):del self.battle
            self.draw();self.persist()
            return True
        except Exception:
            return False

    def intro_text(self):
        p=self.player
        lines={"교회 밖":"성직자가 전쟁의 불길이 번진 숲을 바라본다. 교회 안으로 들어가 전사나 신자의 길을 얻을 수 있다.",
               "왕실 상점가":"왕실 도시의 상점가. 기사단으로 향하는 길과 궁성으로 향하는 성문이 있다.",
               "숲":"숲의 방랑자들이 불가에 모여 있다. 마을과 교회는 숲의 마물 때문에 긴장하고, 왕실은 방랑자의 출입을 금한다.",
               "마을":"왕실과 교회의 경계에 선 마을. 어느 진영에도 속하지 않은 채 주민과 상인에게서 전쟁의 소문을 들을 수 있다."}
        faith={"교회 신앙":"기도는 교회에 힘을 보탠다.","왕실 신앙":"왕실의 서약은 전쟁의 승리를 약속한다.","숲의 신앙":"숲의 옛 신앙은 방랑자와 수인 사이에 남아 있다."}
        return f"{p['race']} · {p['gender']} · {p['religion']}\n{lines[p['area']]} {faith[p['religion']]}"

    def say(self, text, seconds=4): self.notice=str(text); self.notice_t=seconds
    def gain_xp(self, amount):
        p=self.player;p["xp"]+=amount;level_message=[]
        while p["xp"]>=p["level"]*35:
            p["xp"]-=p["level"]*35;p["level"]+=1;p["maxhp"]+=8;p["maxmp"]+=3
            p["hp"]=p["maxhp"];p["mp"]=p["maxmp"];p["atk"]+=2;p["def"]+=1
            level_message.append(f"레벨 {p['level']}!")
        if level_message:self.say(" ".join(level_message)+" 능력치가 올랐다.")
    def spawn_enemies(self):
        self.enemies=[]
        self.wanderers=[]
        if self.area=="숲":
            names=["멧돼지","늑대","고블린"]
            for i in range(7):
                self.enemies.append({"name":random.choice(names),"x":random.randint(160,2200),"y":random.randint(130,1450),"hp":random.choice([26,34,42]),"maxhp":42,"atk":random.randint(5,9),"level":random.choice([1,1,2]),"alive":True,"vx":random.choice([-1,1])*random.randint(10,22),"vy":random.choice([-1,1])*random.randint(8,18),"turn":random.uniform(1,5)})
            for _ in range(random.randint(3,5)):
                self.wanderers.append({"x":random.randint(180,2200),"y":random.randint(150,1400),"vx":random.choice([-1,1])*random.randint(20,38),"vy":random.choice([-1,1])*random.randint(12,26),"turn":random.uniform(1,4),"size":random.randint(2,4)})
        elif self.area in ("왕실 상점가","왕국 기사단","왕국 안","왕의 방") and self.player.get("job") in ("도둑","도적"):
            self.enemies.append({"name":"왕실 경비","x":MAP_SIZE[self.area][0]//2,"y":MAP_SIZE[self.area][1]//2-90,"hp":52,"maxhp":52,"atk":11,"level":2,"alive":True,"human":True})

    def entities(self):
        data=[]
        if self.area=="숲":
            data=[("방랑자 야영지",240,210,"camp"),("마을로 가는 길",2310,800,"exit_village"),("숲길 표지판",120,780,"sign")]
            for i,g in enumerate(self.wanderers):data.append(("방랑자 집단",g["x"],g["y"],"wanderer_party",i))
        if self.area=="마을":
            data=[("상점",260,280,"shop"),("주민",700,300,"villager"),("여관",970,300,"inn"),("숲",55,500,"exit_forest"),("교회로",700,55,"exit_church"),("왕실 상점가",1350,500,"exit_kingdom")]
            if self.player.get("job")=="기사" and self.player.get("faction")=="방랑자":data.append(("기사단 추격대",700,780,"knight_hunters"))
        if self.area=="교회 밖":data=[("교회 입구",600,95,"enter_church"),("마을로",60,450,"exit_village"),("신자들",820,470,"villager")]
        if self.area=="교회 안":data=[("성직자",700,230,"priest"),("수련관",240,260,"trainer_church"),("기도 제단",480,130,"altar"),("밭",760,560,"field"),("청소 구역",210,540,"cleaning"),("교회 밖",480,680,"exit_churchyard")]
        if self.area=="왕실 상점가":data=[("상점",330,300,"shop"),("왕국 기사단으로",1120,450,"exit_barracks"),("마을로",50,450,"exit_village")]
        if self.area=="왕국 기사단":data=[("왕실 교관",500,330,"trainer_kingdom"),("왕실 상점가",500,710,"exit_market"),("왕국 안으로",500,65,"exit_city")]
        if self.area=="왕국 안":data=[("왕의 방",500,70,"exit_throne"),("왕실 상점가",500,710,"exit_market"),("기사단",80,360,"exit_barracks"),("주민",780,400,"villager")]
        if self.area=="왕의 방":data=[("왕",450,225,"king"),("왕국 안",450,610,"exit_palace")]
        for i,e in enumerate(self.enemies):
            if e["alive"]: data.append((e["name"],e["x"],e["y"],"enemy",i))
        return data

    def nearest(self):
        px,py=self.player["x"],self.player["y"]
        near=None; best=70
        for e in self.entities():
            d=math.hypot(px-e[1],py-e[2])
            if d<best: best=d; near=e
        return near

    def collides(self,x,y):
        if self.area=="숲":
            ix0=int((x-16)//80);ix1=int((x+16)//80)
            iy0=int((y-26)//80);iy1=int((y+26)//80)
            for iy in range(iy0,iy1+1):
                for ix in range(ix0,ix1+1):
                    if (ix*13+iy*7)%4==0:
                        tx=ix*80+40;ty=iy*80+52
                        if abs(x-tx)<16 and abs(y-ty)<26:return True
            for tx,ty in ((360,413),(760,1183),(1250,323),(1710,1293),(2060,573),(1900,1073)):
                if abs(x-tx)<15 and abs(y-ty)<27:return True
        elif self.area=="마을":
            for cx,cy in ((240,230),(550,215),(970,235),(1090,700),(350,720)):
                inside=cx-72<=x<=cx+72 and cy-30<=y<=cy+76
                doorway=cx-28<=x<=cx+28 and cy+18<=y<=cy+80
                if inside and not doorway:return True
        return False

    def move_forest_actor(self, actor, dt):
        old_x,old_y=actor["x"],actor["y"]
        dx=actor["vx"]*dt;dy=actor["vy"]*dt
        steps=max(1,math.ceil(max(abs(dx),abs(dy))/10))
        for _ in range(steps):
            next_x=max(95,min(2300,actor["x"]+dx/steps))
            next_y=max(100,min(1500,actor["y"]+dy/steps))
            if not self.collides(next_x,actor["y"]):actor["x"]=next_x
            if not self.collides(actor["x"],next_y):actor["y"]=next_y
        if actor["x"]==old_x and actor["y"]==old_y and (dx or dy):
            actor["turn"]=0

    def move_area(self, dest):
        p=self.player
        royal_areas=("왕실 상점가","왕국 기사단","왕국 안","왕의 방")
        church_areas=("교회 밖","교회 안")
        if p["prayer_due"] and p["faction"] == "교회" and dest not in church_areas+ ("마을",):
            self.exile_church();return
        if p["prayer_due"] and p["faction"] == "교회" and p["area"] in church_areas and dest=="마을":
            self.exile_church();return
        if dest in royal_areas and (p["race"]=="수인" or p["faction"]=="방랑자"):
            self.say("성문 경비가 길을 막는다. 수인과 방랑자 진영은 왕실 구역에 들어갈 수 없다.");p["x"]=max(80,min(MAP_SIZE[self.area][0]-80,p["x"]));return
        if dest in church_areas and p["exiled"]:
            self.say("교회에서 추방된 방랑자는 교회 땅에 들어갈 수 없다.");return
        entry={
            "숲":(2200,800),"마을":(100,500),"교회 밖":(600,790),"교회 안":(480,640),
            "왕실 상점가":(100,450),"왕국 기사단":(500,680),"왕국 안":(500,680),"왕의 방":(450,590)
        }
        p["area"]=dest;p["visited_faction"]=dest;self.area=dest
        p["x"],p["y"]=entry[dest]
        self.walk_meter=0
        self.spawn_enemies()
        intro={
            "숲":"나무와 바위가 이어지는 넓은 숲. 방랑자 무리가 숲길을 떠돌고, 마물이 배회한다.",
            "마을":"왕실과 교회의 사이에 놓인 마을. 상점과 주민들의 집이 모여 있다.",
            "교회 밖":"교회 앞마당. 성당 안으로 들어가려면 정문에 다가가 E를 눌러라.",
            "교회 안":"촛불이 켜진 성당 안. 성직자와 수련관, 기도 제단이 있다.",
            "왕실 상점가":"왕국의 상점가. 기사단과 왕국 안쪽으로 이어지는 길이 있다.",
            "왕국 기사단":"왕실 기사단의 훈련 구역. 교관에게 전사 직업과 토벌 의뢰를 얻을 수 있다.",
            "왕국 안":"왕국의 중심 구역. 궁성으로 가는 길은 북쪽에 있다.",
            "왕의 방":"왕이 머무는 궁성 안쪽. 왕에게 직접 의뢰를 받을 수 있다."
        }
        if dest in royal_areas and p["race"]=="인간" and p["job"] in ("도둑","도적"):
            self.say("경비가 네 직업을 알아보고 경계한다. 왕국 안의 주민과 상점에서 적대적인 반응을 보일 수 있다.")
        else:self.say(intro[dest])

    def wrap_text(self,text,width):
        lines=[]
        for paragraph in str(text).split("\n"):
            words=paragraph.split();current=""
            if not words:lines.append("");continue
            for word in words:
                if current and len(current)+len(word)+1>width:
                    lines.append(current);current=word
                else:current=word if not current else current+" "+word
                while len(current)>width:
                    lines.append(current[:width]);current=current[width:]
            if current:lines.append(current)
        return lines

    def visible_text_lines(self,text,width,max_lines):
        lines=self.wrap_text(text,width)
        if len(lines)>max_lines:
            lines=lines[:max_lines]
            lines[-1]=lines[-1].rstrip(" .")+"…"
        return lines

    def dialog_page_count(self):
        if not self.dialog:return 1
        return max(1,math.ceil(len(self.wrap_text(self.dialog.get("text",""),44))/7))

    def dialog_page_lines(self):
        if not self.dialog:return []
        lines=self.wrap_text(self.dialog.get("text",""),44)
        start=self.dialog.get("text_page",0)*7
        return lines[start:start+7]

    def dialog_options_y(self):
        if not self.dialog:return 300
        return max(300,151+len(self.dialog_page_lines())*22+18)

    def open_dialog(self, title, text, options): self.dialog={"title":title,"text":text,"options":options,"text_page":0}

    def next_step_guidance(self):
        p=self.player
        if p.get("promoted"):return "제1장 완료"
        if p.get("prayer_due") and p.get("faction")=="교회":return "교회 안 제단에서 기도"
        if p.get("job")=="미정":
            first_steps={
                "교회 밖":"교회 안 수련관에서 전사 또는 신자 직업 선택",
                "교회 안":"수련관에서 전사 또는 신자 직업 선택",
                "왕실 상점가":"왕국 기사단 교관에게서 전사 직업 선택",
                "왕국 기사단":"왕실 교관에게서 전사 직업 선택",
                "왕국 안":"기사단으로 가서 왕실 전사 직업 선택",
                "왕의 방":"기사단으로 돌아가 왕실 전사 직업 선택",
                "숲":"야영지에서 도둑 직업 선택 또는 동쪽 길로 마을 이동",
                "마을":"주민에게 의뢰를 받거나 교회·왕실 진영으로 이동",
            }
            return first_steps.get(self.area,"교회·왕실·야영지에서 원하는 직업 선택")
        faction=p.get("faction")
        if faction=="교회":
            if p.get("job")=="신자":return f"성직자에게 봉사 의뢰를 받아 승급용 10회 중 {p.get('church_quests_completed',0)}회 완료"
            return "성직자에게 마물 의뢰를 받아 처치한 뒤 교회 제단에서 기도"
        if faction=="왕실":return f"왕실 의뢰를 받아 기사 승급용 10회 중 {p.get('king_quests',0)}회 완료"
        if faction=="방랑자":
            if p.get("job")=="도둑":return "야영지에서 길을 살피고 상점에서 물건 훔치기를 시도"
            return "숲 야영지에서 도둑 직업을 얻거나 방랑자 무리와 대화"
        return "다른 진영의 수련관에서 원하는 직업 선택"

    def quest_journal_text(self):
        p=self.player;q=p.get("quest")
        if q:
            objectives={
                "church":"숲의 마물을 처치한 뒤 교회 제단에서 기도",
                "village":"숲으로 가서 주민을 위협하는 마물 처치",
                "kingdom":"숲의 마물을 처치해 왕실 토벌 진행",
            }
            simple_objectives={
                    "밭에 물 주기":"교회 안의 밭을 조사",
                    "교회 청소":"교회 안의 청소 구역을 조사",
                    "기도":"교회 안의 제단에서 기도",
            }
            progress=f"의뢰: {q['title']} · {q['count']}/{q['goal']}"
            guide=simple_objectives.get(q.get("title"),"교회 안의 의뢰 장소를 조사") if q.get("source")=="church_simple" else objectives.get(q.get("source"),"의뢰 내용을 확인")
            objective=f"목표: {guide}"
        else:
            progress="의뢰: 진행 중인 의뢰 없음"
            objective=f"목표: {self.next_step_guidance()}"
        if p["job"]=="신자":church=f"교회 봉사 {p['church_quests_completed']}/10 · 거절 {p['priest_refusals']}/3"
        else:church=f"교회 의뢰 {p['church_quests_completed']}/10 · 기도 {p['prayer_count']}/10 · 거절 {p['priest_refusals']}/3"
        if p.get("prayer_due"):church+=" · 제단 기도 필요"
        flags=set(p.get("story_flags",[]));discovered=[]
        for route,label in (("church","교회 기록"),("royal","왕실 기록")):
            for milestone,text in sorted(CHAPTER_STORY_BEATS[route].items()):
                if f"chapter1:{route}:{milestone}" in flags:discovered.append(f"{label}: {text}")
        clues=len(discovered)
        chapter="제1장 완료 · 다음 장은 추후 공개" if p.get("promoted") else "제1장 진행 중"
        next_level_xp=p["level"]*35
        experience=f"레벨 {p['level']} · 경험치 {p['xp']}/{next_level_xp} · 다음 레벨까지 {max(0,next_level_xp-p['xp'])}"
        clue_lines=[f"전쟁 단서 {clues}/4"]
        if discovered:clue_lines.extend(discovered)
        else:clue_lines[0]+=" · 아직 발견하지 않음"
        epilogue=self.chapter1_epilogue_text() if p.get("promoted") else None
        if epilogue:clue_lines.append(f"제1장 결말: {epilogue}")
        return "\n".join([
            f"진영: {p['faction']} · 직업: {p['job']} · 종교: {p['religion']}",
            chapter,experience,progress,objective,church,
            f"왕실 의뢰: {p['king_quests']}/10",*clue_lines,
        ])

    def reveal_story_beat(self, route, milestone):
        text=CHAPTER_STORY_BEATS.get(route,{}).get(milestone)
        if not text:return None
        p=self.player;flags=p.setdefault("story_flags",[]);key=f"chapter1:{route}:{milestone}"
        if key in flags:return None
        flags.append(key)
        return text

    def chapter1_epilogue_text(self):
        flags=set(self.player.get("story_flags",[]))
        church=any(f"chapter1:church:{milestone}" in flags for milestone in CHAPTER_STORY_BEATS["church"])
        royal=any(f"chapter1:royal:{milestone}" in flags for milestone in CHAPTER_STORY_BEATS["royal"])
        if church and royal:return "양쪽 진영의 기록은 서로를 전쟁의 원인으로 지목한다. 폐허에서는 두 표식이 함께 발견됐지만, 어느 쪽도 전쟁을 끝낼 진실을 밝히지 못했다."
        if church:return "교회 기록에는 왕실 문양과 교회 보급품이 함께 남았다. 성직자들은 답을 얻지 못했고 전쟁은 숲의 마을까지 번진다."
        if royal:return "왕실 보고서에는 교회 문양과 양쪽 진영의 표식이 함께 남았다. 왕은 보고서를 봉인하고 전쟁은 숲으로 이어진다."
        return "전쟁의 배후를 밝힐 단서는 아직 부족하다. 왕실과 교회의 군대는 숲을 향해 진군한다."

    def shop_price(self, base):
        return base if self.player["race"]=="인간" else math.ceil(base*1.05)

    def open_shop(self):
        p=self.player;price=self.shop_price(20)
        last="물건 훔치기" if p["job"] in ("도둑","도적") else "나가기"
        self.open_dialog("상점",f"회복 붕대는 최대 체력의 12%를 회복해. 수인 가격 +5%. 현재 {p['gold']}G.",
                         [f"회복 붕대 구매 · {price}G","무기 진열장","방어구 진열장",last])

    def open_inventory(self):
        p=self.player
        text=f"무기: {p['weapon']} (공격 {p['atk']})\n방어구: {p['armor']} (방어 {p['def']})\n종교: {p['religion']}\n회복 붕대: {p['bandages']}개 · {p['gold']}G"
        self.open_dialog("소지품",text,["회복 붕대 사용","무기 바꾸기","방어구 바꾸기","닫기"])

    def open_equipment_selector(self, slot, page=0):
        p=self.player;weapon=slot=="weapon"
        collection=p.setdefault("owned_weapons" if weapon else "owned_armor",
                                [p.get("weapon" if weapon else "armor","낡은 검" if weapon else "여행자 옷")])
        title="무기 장착" if weapon else "방어구 장착"
        equipped=p["weapon" if weapon else "armor"]
        pages=max(1,math.ceil(len(collection)/2));page=max(0,min(int(page),pages-1))
        options=collection[page*2:(page+1)*2]
        bonuses=WEAPON_BONUS if weapon else ARMOR_BONUS
        if page>0:options.append("이전")
        if page<pages-1:options.append("다음")
        if page==0 or page==pages-1:options.append("취소")
        stat="공격" if weapon else "방어"
        current=p["atk"] if weapon else p["def"]
        current_bonus=bonuses.get(equipped,0)
        details=[f"현재 {stat} {current} · 장비 보너스 {current_bonus:+d}",
                 f"보유 장비 {len(collection)}종 · {page+1}/{pages} 페이지"]
        for name in collection[page*2:(page+1)*2]:
            if name==equipped:details.append(f"{name} · 착용 중")
            else:details.append(f"{name} · 장착 시 {stat} {bonuses.get(name,0)-current_bonus:+d}")
        self.open_dialog(title,"\n".join(details),options)
        self.dialog["page"]=page

    def equip_weapon(self, name):
        p=self.player;owned=p.setdefault("owned_weapons",[p.get("weapon","낡은 검")])
        if name not in owned:self.say("가지고 있지 않은 무기다.");return
        if name==p["weapon"]:self.say(f"{name}을(를) 이미 장착했다.");return
        change=WEAPON_BONUS.get(name,0)-WEAPON_BONUS.get(p["weapon"],0)
        p["weapon"]=name;p["atk"]+=change;self.say(f"{name} 장착. 공격력이 {change:+d} 변했다.")

    def equip_armor(self, name):
        p=self.player;owned=p.setdefault("owned_armor",[p.get("armor","여행자 옷")])
        if name not in owned:self.say("가지고 있지 않은 방어구다.");return
        if name==p["armor"]:self.say(f"{name}을(를) 이미 장착했다.");return
        change=ARMOR_BONUS.get(name,0)-ARMOR_BONUS.get(p["armor"],0)
        p["armor"]=name;p["def"]+=change;self.say(f"{name} 장착. 방어력이 {change:+d} 변했다.")

    def buy_weapon(self, name, base_price):
        p=self.player;owned=p.setdefault("owned_weapons",[p.get("weapon","낡은 검")]);price=self.shop_price(base_price)
        if name in owned:self.say(f"{name}은(는) 이미 가지고 있다.");return
        if p["gold"]<price:self.say("소지금이 부족하다.");return
        p["gold"]-=price;owned.append(name);p.setdefault("inventory",[]).append(name);self.equip_weapon(name)

    def buy_armor(self, name, base_price):
        p=self.player;owned=p.setdefault("owned_armor",[p.get("armor","여행자 옷")]);price=self.shop_price(base_price)
        if name in owned:self.say(f"{name}은(는) 이미 가지고 있다.");return
        if p["gold"]<price:self.say("소지금이 부족하다.");return
        p["gold"]-=price;owned.append(name);p.setdefault("inventory",[]).append(name);self.equip_armor(name)

    def award_monster_loot(self, enemy):
        p=self.player;drop=MONSTER_LOOT.get(enemy.get("name"))
        if not drop or random.random()>=drop[2]:return None
        slot,name,_=drop
        owned=p.setdefault("owned_weapons",[p.get("weapon","낡은 검")]) if slot=="weapon" else p.setdefault("owned_armor",[p.get("armor","여행자 옷")])
        if name in owned:
            p["gold"]+=12
            return f"{name} 대신 전리품을 팔아 12G를 얻었다."
        owned.append(name);p.setdefault("inventory",[]).append(name)
        if slot=="weapon":
            previous=p["weapon"]
            if WEAPON_BONUS[name]>WEAPON_BONUS.get(previous,0):self.equip_weapon(name)
            return f"희귀 전리품: {name}을(를) 획득했다." + (" 자동 장착했다." if p["weapon"]==name else " 소지품에서 장착할 수 있다.")
        previous=p["armor"]
        if ARMOR_BONUS[name]>ARMOR_BONUS.get(previous,0):self.equip_armor(name)
        return f"희귀 전리품: {name}을(를) 획득했다." + (" 자동 장착했다." if p["armor"]==name else " 소지품에서 장착할 수 있다.")

    def interact(self):
        ent=self.nearest()
        if not ent: self.say("주변에 상호작용할 대상이 없어. 사람이나 시설 가까이 가서 E를 눌러봐.");return
        name,x,y,kind,*extra=ent; p=self.player
        transitions={
            "exit_village":"마을","exit_forest":"숲","exit_church":"교회 밖",
            "enter_church":"교회 안","exit_churchyard":"교회 밖",
            "exit_kingdom":"왕실 상점가","exit_barracks":"왕국 기사단",
            "exit_city":"왕국 안","exit_market":"왕실 상점가",
            "exit_throne":"왕의 방","exit_palace":"왕국 안"
        }
        if kind in transitions:self.move_area(transitions[kind]);return
        if kind=="sign":self.say("숲은 넓다. 길을 잃지 않도록 동쪽 끝의 마을 길을 찾아가자.");return
        if kind=="enemy": self.start_battle(extra[0]);return
        if kind=="wanderer_party":
            welcome="숲의 신앙을 가진 수인에게 무리가 반갑게 길을 내준다." if p["religion"]=="숲의 신앙" or p["race"]=="수인" else "숲의 방랑자들이 낯선 신앙을 살피며 조심스럽게 지켜본다."
            if p["faction"]=="방랑자":self.open_dialog("방랑자 집단",f"{welcome} 떠돌이 무리가 숲길을 따라 이동 중이다.",["함께 이동하기","나가기"])
            else:self.open_dialog("방랑자 집단",f"{welcome} 함께하려면 현재 진영에서 먼저 탈퇴해야 한다.",["방랑자 진영에 합류","대화하기","나가기"])
            return
        if kind=="knight_hunters":
            self.open_dialog("기사단 추격대","왕실에서 방랑 기사를 추격해왔다. 싸우거나 기사단으로 돌아갈 수 있다.",["기사단과 싸운다","기사단에 다시 들어간다"]);return
        if kind=="shop":
            self.open_shop();return
        if kind=="inn":
            self.open_dialog("숲길 여관","전쟁 소식은 여기까지 따라왔어. 잠시 쉬면 체력과 마력을 모두 회복할 수 있네.",
                             [f"하룻밤 묵기 · {self.shop_price(25)}G","나가기"]);return
        if kind=="camp":
            if p["faction"]!="방랑자": self.open_dialog("방랑자 야영지","방랑자와 함께하거나, 이 진영을 떠나 다른 길을 찾을 수 있다.",["방랑자 진영에 합류","도둑 직업 얻기","다른 진영으로 떠나기"])
            elif p["job"]!="도둑": self.open_dialog("방랑자 야영지","숲의 방랑자들은 왕실을 피해 떠돌아. 도둑의 길을 배울 수 있다.",["도둑 직업 얻기","마을로 향하기","방랑자 진영에서 탈퇴"])
            else:self.open_dialog("방랑자 야영지","야영지에서 잠시 숨을 돌린다.",["마을로 향하기","방랑자 진영에서 탈퇴"])
            return
        if kind=="trainer_church":
            if p.get("promoted"):
                self.open_dialog("교회 수련관","직업 승급으로 제1장을 마쳤다. 다음 여정은 추후 이어진다.",["나가기"]);return
            if p["faction"] not in ("교회", "무소속"):
                self.open_dialog("교회 수련관","다른 진영의 직업을 버린 뒤에만 교회 직업을 얻을 수 있다. 먼저 현재 진영에서 탈퇴하자.",["다른 진영을 찾아 떠나기","나가기"]);return
            if p["prayer_due"]:self.open_dialog("교회 수련관","완료한 의뢰에 대한 기도를 먼저 마쳐야 한다.",["나가기"])
            else:self.open_dialog("교회 수련관",f"교회 직업은 전사와 신자야. 현재 직업 {p['job']} · 기도 {p['prayer_count']}/10. 다른 진영에서 왔다면 교회 직업을 새로 선택할 수 있어.",["전사로 수련 시작","신자로 수련 시작","다른 진영을 찾아 떠나기"])
            return
        if kind=="priest":
            if p["faction"]=="교회" and p.get("quest"):
                active=p["quest"]["title"]
                self.open_dialog("성직자",f"먼저 진행 중인 의뢰 '{active}'를 마무리하게. 새 의뢰를 고를 수 없으니 거절 횟수도 늘지 않는다.",["나가기"]);return
            faith_note="자네의 왕실 신앙은 교회의 가르침과 다르네. 그래도 교회에 서약한 동안은 의뢰를 맡을 수 있네." if p["religion"]=="왕실 신앙" else "숲의 신앙을 가진 이도 교회에 서약하면 의뢰를 맡을 수 있네." if p["religion"]=="숲의 신앙" else "기도의 뜻을 아는 자로군."
            if p["faction"]!="교회":self.open_dialog("성직자","교회 진영에 속한 직업만 교회 스토리 의뢰를 받을 수 있다. 교회 수련관에서 합류할 수 있다.",["나가기"])
            elif p["job"]=="신자":
                prayer_option="기도 의뢰" if p["prayer_count"]<p["church_quests_completed"] else "나가기"
                self.open_dialog("성직자",f"{faith_note} 교회 일을 도와주게. 완료한 성직자 의뢰 횟수만큼 기도할 수 있다. 세 번 이상 거절하면 직업 승급 자격을 잃는다.",["밭에 물 주기 의뢰","교회 청소 의뢰",prayer_option,"의뢰 거절"])
            elif p["job"]=="성직자":self.open_dialog("성직자","네 봉사와 서품은 제1장을 마무리했다. 발견한 전쟁 단서는 Q 기록에서 다시 볼 수 있다.",["나가기"])
            elif p["job"]=="전사":self.open_dialog("성직자",f"{faith_note} 숲에서 마물을 퇴치해주게. 성공하면 반드시 제단에서 기도해야 하네.",["마물 퇴치 의뢰","의뢰 거절","나가기"])
            else:self.open_dialog("성직자","교회 직업을 얻으려면 수련관에서 수련해야 하네. 다른 진영 직업으로는 교회 스토리 의뢰를 받을 수 없어.",["나가기"])
            return
        if kind=="altar":
            if p["prayer_count"]>=p["church_quests_completed"]:
                self.say(f"기도할 수 있는 횟수가 부족하다. 성직자 의뢰 완료 {p['church_quests_completed']}회 / 기도 {p['prayer_count']}회.");return
            p["prayer_count"]+=1
            if p["religion"]=="교회 신앙":p["mp"]=min(p["maxmp"],p["mp"]+3)
            if p["prayer_due"]: p["prayer_due"]=False;self.say(f"기도를 마쳤다. 성전사 승급을 향한 기도 {p['prayer_count']}/10.")
            else:self.say(f"조용히 기도했다. 기도 횟수 {p['prayer_count']}/10.")
            if p["job"]=="전사" and p["prayer_count"]>=10 and p["priest_refusals"]<3 and not p["promoted"]:self.promote("성전사")
            if p["quest"] and p["quest"]["title"]=="기도":self.complete_simple_quest("기도")
            return
        if kind=="field": self.complete_simple_quest("밭에 물 주기");return
        if kind=="cleaning": self.complete_simple_quest("교회 청소");return
        if kind=="villager":
            if p["job"] in ("전사","기사"):
                text="수인 여행자라면 더 조심해주게." if p["race"]=="수인" else "숲에서 마물이 내려와 가축과 주민을 위협하고 있어."
                self.open_dialog("마을 주민",text,["마물 퇴치 의뢰","의뢰 거절","나가기"])
            else:
                text="수인에게는 낯선 시선을 보낸다. 숲의 방랑자들은 너를 반갑게 맞는다." if p["race"]=="수인" else "숲에서 마물이 내려와 가축과 주민을 위협하고 있어."
                self.open_dialog("마을 주민",text,["마물 퇴치 의뢰","의뢰 거절","나가기"])
            return
        if kind=="trainer_kingdom":
            if p.get("promoted"):
                self.open_dialog("왕실 교관","기사 승급으로 제1장을 마쳤다. 새로운 왕실 훈련과 의뢰는 다음 여정에서 이어진다.",["나가기"]);return
            if p["faction"] not in ("왕실", "무소속"):
                self.open_dialog("왕실 교관","다른 진영의 직업을 버린 뒤에만 왕실 직업을 얻을 수 있다. 먼저 현재 진영에서 탈퇴하자.",["방랑자로 탈출하기","나가기"]);return
            if p["faction"]=="왕실" and p["job"]=="미정":self.open_dialog("왕실 교관","왕실 도시에서 전쟁에 참여할 전사를 모집한다.",["전사로 수련 시작","왕실 토벌 의뢰","방랑자로 탈출하기"])
            elif p["faction"]=="왕실":self.open_dialog("왕실 교관",f"왕실 직업은 전사에서 시작해 기사로 승급해. 현재 직업 {p['job']} · 왕실 의뢰 {p['king_quests']}/10.",["왕실 토벌 의뢰","승급 진행도 확인","방랑자로 탈출하기"])
            else:self.open_dialog("왕실 교관","왕실 직업은 전사로 합류해 시작한다. 방랑자 진영 소속은 왕실에 들어올 수 없다.",["전사로 수련 시작","나가기"])
            return
        if kind=="king":
            if p.get("promoted"):
                self.open_dialog("왕","왕은 제1장의 명령을 거두었다. 기사단은 숲의 전쟁에 관한 새 소식을 기다린다.",["나가기"]);return
            if p["faction"]=="왕실":
                faith_note="왕실 신앙의 서약을 기억하라." if p["religion"]=="왕실 신앙" else "교회와 다른 신앙을 가진 자라면 네 충성을 행동으로 보여라." if p["religion"]=="교회 신앙" else "숲의 신앙을 지녔어도 왕실에 서약했다면 백성을 지켜라."
                self.open_dialog("왕",f"전쟁은 끝날 기미가 없다. {faith_note} 왕실의 이름으로 숲과 방랑자의 문제를 해결하라.",["마물 퇴치 의뢰","나가기"])
            else:self.open_dialog("왕","왕실 소속이 아닌 자는 왕의 명령을 받을 수 없다.",["나가기"])
            return

    def accept_quest(self, title, source):
        if self.player.get("quest"):
            self.say(f"이미 진행 중인 의뢰가 있다: {self.player['quest']['title']}. 먼저 마무리하자.")
            return
        self.player["quest"]={"title":title,"source":source,"goal":1,"count":0}
        self.player["quest_kills"]=0
        simple_guides={
            "밭에 물 주기":"교회 안 밭에 물을 주자",
            "교회 청소":"교회 안 청소 구역을 정리하자",
            "기도":"교회 안 제단에서 기도하자",
        }
        guides={
            "church":"숲의 마물을 처치하고 교회 제단에서 기도하자",
            "village":"숲의 마물을 처치하고 마을 주민에게 보고하자",
            "kingdom":"숲의 마물을 처치하고 왕실에 보고하자",
        }
        guide=simple_guides.get(title,"교회 안에서 의뢰 장소를 찾자") if source=="church_simple" else guides.get(source,"의뢰 장소를 확인하자")
        self.say(f"의뢰 수락: {title}. {guide}.")

    def complete_simple_quest(self,title):
        p=self.player
        if not p["quest"]: self.say("먼저 성직자에게 의뢰를 받아야 해.");return
        if p["quest"].get("source")!="church_simple":self.say("이 의뢰는 여기서 완료할 수 없어.");return
        if p["quest"]["title"]!=title:self.say("이곳에서 완료할 수 있는 의뢰가 아니야.");return
        source=p["quest"]["source"]
        p["quest"]=None;p["gold"]+=12;self.gain_xp(8)
        self.say(f"{title} 완료! 12G와 경험치를 얻었다.")
        self.after_church_quest(source,title)

    def after_church_quest(self, source=None, completed_title=None):
        p=self.player
        prayer_task=source=="church_simple" and completed_title=="기도"
        if p["faction"]=="교회" and source in ("church","church_simple") and not prayer_task:
            p["church_quests_completed"]+=1
        if p["faction"]=="교회" and p["job"]=="전사" and source=="church":
            p["prayer_due"]=True
            beat=self.reveal_story_beat("church",p["church_quests_completed"])
            text="의뢰를 완료했다. 교회 안 제단에서 기도해야 한다.\n기도 없이 교회 진영을 떠나면 방랑자로 추방된다."
            if beat:text+="\n전쟁 단서: "+beat
            self.open_dialog("기도 의무",text,["알겠어"])
        elif p["faction"]=="교회" and p["job"]=="신자" and source=="church_simple":
            beat=self.reveal_story_beat("church",p["church_quests_completed"])
            if beat:self.open_dialog("전쟁의 단서",beat,["계속"])
            if p["church_quests_completed"]>=10 and p["priest_refusals"]<3 and not p["promoted"]:
                self.promote("성직자")
        if p["faction"]=="왕실" and p["job"] in ("전사","기사") and source=="kingdom":
            p["king_quests"]+=1
            beat=self.reveal_story_beat("royal",p["king_quests"])
            if beat:self.open_dialog("전쟁의 단서",beat,["계속"])
            if p["king_quests"]>=10 and p["job"]=="전사":self.promote("기사")

    def complete_monster_quest(self):
        p=self.player; q=p["quest"]
        if not q: return
        source=q.get("source");title=q.get("title")
        reward=30 if source=="kingdom" and p.get("religion")=="왕실 신앙" else 25
        p["quest"]=None;p["gold"]+=reward;self.gain_xp(20)
        self.say(f"마물 퇴치 의뢰 완료! {reward}G와 경험치를 얻었다.")
        self.after_church_quest(source,title)

    def promote(self, job):
        p=self.player;p["job"]=job;p["promoted"]=True
        endings={
            "성전사":"열 번의 기도 끝에 교회는 너를 성전사로 인정했다. 왕실과 교회의 전쟁은 이제 숲의 마을까지 번져간다.",
            "성직자":"열 건의 교회 봉사를 마친 너는 성직자로 서품되었다. 숲에서 발견한 전쟁의 흔적을 더는 외면할 수 없다.",
            "기사":"왕실 토벌 열 건을 마친 너는 기사단의 일원이 되었다. 왕의 명령은 숲 너머의 전쟁을 예고한다.",
            "도적":"사람의 피를 묻힌 순간, 너는 더는 단순한 도둑이 아니게 되었다. 방랑자의 길은 점점 깊어진다."
        }
        epilogue=self.chapter1_epilogue_text()
        self.open_dialog("직업 승급",f"새로운 직업을 얻었다: {job}.\n{endings.get(job,'너의 선택이 제1장의 끝을 장식했다.')}\n\n{epilogue}\n제1장 완료.",["1장 마무리"])

    def choose(self, idx):
        if not self.dialog:return
        d=self.dialog;p=self.player
        if idx<0 or idx>=len(d["options"]):return
        self.dialog=None
        title=d["title"]; opt=d["options"][idx]
        if "enemy_index" in d and title not in ("직업 승급",):
            if idx==0:
                i=d["enemy_index"]
                if i<len(self.enemies) and self.enemies[i]["alive"]: self.start_battle(i)
            else:self.say("전투를 피했다.")
            return
        if title=="상점":
            if idx==0:
                bandage_price=self.shop_price(20)
                if p["gold"]>=bandage_price:p["gold"]-=bandage_price;p["bandages"]+=1;p["inventory"].append("회복 붕대");self.say("회복 붕대를 샀다.")
                else:self.say("소지금이 부족하다.")
            elif idx==1:
                items=(("철검",60),("사냥꾼 활",85));owned=p.get("owned_weapons",[])
                current_bonus=WEAPON_BONUS.get(p.get("weapon"),0)
                options=[f"{name} · 보유" if name in owned else
                         f"{name} · {self.shop_price(price)}G · 공격 변화 {WEAPON_BONUS[name]-current_bonus:+d}"
                         for name,price in items]
                options.append("상점으로 돌아가기")
                self.open_dialog("무기 진열장",f"현재 공격 {p['atk']} · 구매한 무기는 즉시 장착해. 보유 무기는 소지품에서 교체할 수 있어.",options)
            elif idx==2:
                items=(("가죽 갑옷",55),("방랑자 외투",75),("기사 갑옷",120));owned=p.get("owned_armor",[])
                current_bonus=ARMOR_BONUS.get(p.get("armor"),0)
                options=[f"{name} · 보유" if name in owned else
                         f"{name} · {self.shop_price(price)}G · 방어 변화 {ARMOR_BONUS[name]-current_bonus:+d}"
                         for name,price in items]
                options.append("상점으로 돌아가기")
                self.open_dialog("방어구 진열장",f"현재 방어 {p['def']} · 구매한 방어구는 즉시 장착해. 보유 장비는 소지품에서 교체할 수 있어.",options)
            elif idx==3 and opt=="물건 훔치기":
                if random.random()<.55:
                    self.enemies.append({"name":"상점 주인","x":280,"y":300,"hp":48,"maxhp":48,"atk":8,"level":1,"alive":True,"human":True})
                    self.open_dialog("발각!","물건을 훔치다 들켰다. 상점 주인이 길을 막는다.",["맞서 싸운다","도망친다"]);self.dialog["enemy_index"]=len(self.enemies)-1
                else:
                    p["gold"]+=25;p["inventory"].append("훔친 물건");self.say("들키지 않고 물건을 훔쳤다. 25G 상당의 물건을 챙겼다.")
            return
        if title=="숲길 여관":
            if idx==0:
                price=self.shop_price(25)
                if p["gold"]<price:self.say(f"여관비 {price}G가 부족하다.")
                else:
                    p["gold"]-=price;p["hp"]=p["maxhp"];p["mp"]=p["maxmp"]
                    self.say("긴 밤의 휴식으로 체력과 마력이 모두 회복됐다.")
            return
        if title=="무기 진열장":
            items=(("철검",60),("사냥꾼 활",85))
            if idx<len(items):
                name,price=items[idx]
                if name in p.get("owned_weapons",[]):self.say(f"{name}은(는) 이미 가지고 있다.")
                else:self.buy_weapon(name,price)
            elif idx==len(items):self.open_shop()
            return
        if title=="방어구 진열장":
            items=(("가죽 갑옷",55),("방랑자 외투",75),("기사 갑옷",120))
            if idx<len(items):
                name,price=items[idx]
                if name in p.get("owned_armor",[]):self.say(f"{name}은(는) 이미 가지고 있다.")
                else:self.buy_armor(name,price)
            elif idx==len(items):self.open_shop()
            return
        if title=="소지품":
            if opt=="회복 붕대 사용":
                if p["bandages"]>0:
                    if p["hp"]>=p["maxhp"]:self.say("체력이 가득 차 있어 회복 붕대를 아꼈다.")
                    else:
                        healed=max(1,round(p["maxhp"]*.12));p["hp"]=min(p["maxhp"],p["hp"]+healed);p["bandages"]-=1;self.say(f"회복 붕대를 사용해 HP {healed} 회복.")
                else:self.say("회복 붕대가 없어.")
            elif opt=="무기 바꾸기":
                self.open_equipment_selector("weapon")
            elif opt=="방어구 바꾸기":
                self.open_equipment_selector("armor")
            return
        if title=="무기 장착":
            if opt=="취소":self.open_inventory()
            elif opt in ("이전","다음"):
                page=d.get("page",0)+(-1 if opt=="이전" else 1);self.open_equipment_selector("weapon",page)
            else:self.equip_weapon(opt)
            return
        if title=="방어구 장착":
            if opt=="취소":self.open_inventory()
            elif opt in ("이전","다음"):
                page=d.get("page",0)+(-1 if opt=="이전" else 1);self.open_equipment_selector("armor",page)
            else:self.equip_armor(opt)
            return
        if title=="방랑자 야영지":
            if opt=="방랑자 진영에 합류":
                if p["faction"] in ("교회","왕실"):self.say("먼저 현재 진영에서 탈퇴해야 한다. 야영지의 '다른 진영으로 떠나기'를 선택하자.")
                else:p["faction"]="방랑자";self.say("방랑자 진영에 합류했다. 왕실 구역에는 들어갈 수 없다.")
            elif opt=="도둑 직업 얻기":
                if p["faction"] in ("교회","왕실"):self.say("먼저 현재 진영에서 탈퇴해야 도둑의 길을 택할 수 있다.")
                else:p["job"]="도둑";p["faction"]="방랑자";self.say("도둑의 길을 택했다. 사람을 죽이면 도적으로 승급할 수 있다.")
            elif opt=="마을로 향하기":self.move_area("마을")
            elif opt=="다른 진영으로 떠나기" or opt=="방랑자 진영에서 탈퇴":p["faction"]="무소속";self.say("방랑자 진영을 떠나 무소속이 되었다. 인간이라면 왕실에도 들어갈 수 있다.")
            return
        if title=="기사단 추격대":
            if idx==0:
                self.enemies.append({"name":"기사단 추격자","x":560,"y":340,"hp":56,"maxhp":56,"atk":10,"level":2,"alive":True,"human":True})
                self.open_dialog("추격전","기사단 추격자가 검을 뽑았다.",["맞서 싸운다","도망친다"]);self.dialog["enemy_index"]=len(self.enemies)-1
            elif idx==1:
                p["faction"]="왕실";self.move_area("왕국 기사단");self.say("기사단에 다시 들어갔다. 왕실 진영으로 돌아왔다.")
            return
        if title=="방랑자 집단":
            if opt in ("방랑자 진영에 합류","함께 이동하기"):
                p["faction"]="방랑자";self.say("방랑자 무리와 함께 숲길을 걷는다. 왕실 구역에 들어갈 수 없게 되었다.")
            elif opt=="대화하기":self.say("방랑자들이 왕실과 교회의 전쟁 소문을 나눈다.")
            return
        if title=="교회 수련관":
            if opt=="전사로 수련 시작":p["job"]="전사";p["faction"]="교회";self.say("교회 전사가 되었다. 의뢰를 성공할 때마다 제단에서 기도하자.")
            elif opt=="신자로 수련 시작":p["job"]="신자";p["faction"]="교회";self.say("교회 신자가 되었다. 성직자에게 교회 일을 받자.")
            elif opt=="교회에서 나가기":self.exile_church()
            elif opt=="다른 진영을 찾아 떠나기":
                if p["faction"]=="교회" and p["prayer_due"]:self.exile_church()
                else:p["faction"]="무소속";self.move_area("마을")
            elif opt=="기도 횟수 확인":self.say(f"현재 기도 횟수 {p['prayer_count']}/10. 교회 퀘스트 거절 {p['priest_refusals']}회.")
            return
        if title=="성직자":
            if opt=="의뢰 거절":
                p["priest_refusals"]+=1
                if p["priest_refusals"]>=3:self.say("의뢰를 세 번 이상 거절했다. 교회 직업의 승급 자격을 잃었다.")
                else:self.say(f"의뢰를 거절했다. 거절 {p['priest_refusals']}/3.")
            elif opt=="마물 퇴치 의뢰":self.accept_quest("숲의 마물 퇴치","church")
            elif opt=="밭에 물 주기 의뢰" or opt=="교회 청소 의뢰" or opt=="기도 의뢰":self.accept_quest(opt.replace(" 의뢰",""),"church_simple")
            return
        if title=="마을 주민":
            if opt=="의뢰 거절":self.say("의뢰를 거절했다.")
            elif opt=="마물 퇴치 의뢰":self.accept_quest("숲의 마물 퇴치","village")
            return
        if title=="왕실 교관" or title=="왕":
            if opt=="전사로 수련 시작":p["job"]="전사";p["faction"]="왕실";self.say("왕실 전사가 되었다. 왕실 의뢰를 수행해 기사단에 입대할 수 있다.")
            elif opt=="왕실 토벌 의뢰" or opt=="마물 퇴치 의뢰":self.accept_quest("왕실 토벌","kingdom")
            elif opt=="승급 진행도 확인":self.say(f"왕실 의뢰 {p['king_quests']}/10. 전사로 왕실 의뢰를 10번 완료하면 기사가 된다.")
            elif opt=="방랑자로 탈출하기":p["faction"]="무소속";self.move_area("마을");self.say("왕실을 탈출했다. 이제 무소속으로 다른 진영에 들어갈 수 있다.")
            elif opt=="의뢰 거절":self.say("왕실 의뢰를 거절했다.")
            return
        if title=="기도 의무":
            if idx==0:self.say("교회 안의 제단으로 돌아가 기도하자.")
            return
        if title=="직업 승급": self.say("1장 완료. 이후 파트는 추후 추가 예정.");return
        if title=="교회 수련관" and opt=="교회에서 나가기":self.exile_church()

    def exile_church(self):
        p=self.player;p["faction"]="방랑자";p["exiled"]=True;p["prayer_due"]=False
        self.area="마을";p["area"]="마을";p["x"]=700;p["y"]=500;p["visited_faction"]="마을";self.spawn_enemies()
        self.say("교회에서 추방되었다. 방랑자 진영으로 편입되어 교회에 다시 들어갈 수 없다.")

    def start_battle(self, idx):
        e=self.enemies[idx];self.battle={"index":idx,"enemy_turn":True,"log":f"{e['name']}와 마주쳤다!","defending":False,"turn":0,"effect":None}
        self.mode="battle"

    def skill_profile(self):
        return JOB_SKILLS.get(self.player.get("job"),{"name":"강타","cost":7,"multiplier":2.0,"effect":"strike"})

    def start_ambush(self):
        name=random.choice(["멧돼지","늑대","고블린"])
        enemy={"name":name,"x":self.player["x"]+45,"y":self.player["y"],"hp":random.choice([28,36,44]),"maxhp":44,"atk":random.randint(6,10),"level":random.choice([1,1,2]),"alive":True,"vx":0,"vy":0,"turn":random.uniform(1.2,3.5)}
        self.enemies.append(enemy)
        self.say(f"숲의 {name}가 갑자기 습격했다!",3)
        self.start_battle(len(self.enemies)-1)

    def update_world_ai(self, dt, distance):
        if self.area!="숲":return
        for g in self.wanderers:
            g["turn"]-=dt
            if g["turn"]<=0:
                g["vx"]=random.uniform(-42,42);g["vy"]=random.uniform(-28,28);g["turn"]=random.uniform(1.5,4)
            self.move_forest_actor(g,dt)
        for e in self.enemies:
            if not e.get("alive") or e.get("human"):continue
            e.setdefault("vx",0);e.setdefault("vy",0);e.setdefault("turn",random.uniform(1.2,3.5))
            e["turn"]-=dt
            if e["turn"]<=0:
                e["vx"]=random.uniform(-25,25);e["vy"]=random.uniform(-20,20);e["turn"]=random.uniform(1.2,3.5)
            self.move_forest_actor(e,dt)
        if distance>0:
            self.walk_meter+=distance
            while self.walk_meter>=190:
                self.walk_meter-=190
                if random.random()<.12:
                    self.start_ambush();break

    def battle_action(self, action):
        if not hasattr(self,"battle"):return
        b=self.battle;p=self.player;e=self.enemies[b["index"]]
        if b.get("won"):return
        if action=="attack":
            b["submenu"]="attack";b["log"]="사용할 공격 기술을 선택해."
            return
        if action=="basic":
            dmg=max(1,p["atk"]+random.randint(-2,3));e["hp"]-=dmg;b["log"]=f"{p['weapon']}으로 공격! {dmg} 피해."
            b["effect"]="slash";b["effect_t"]=.42;b["submenu"]=None
        elif action=="skill":
            skill=self.skill_profile();cost=skill["cost"]
            if p["mp"]<cost:
                b["log"]=f"MP 부족: {skill['name']} 사용에는 {cost}가 필요하다. 다른 공격을 선택해."
                b["submenu"]="attack"
                return
            else:
                p["mp"]-=cost
                dmg=max(2,round(p["atk"]*skill["multiplier"])+random.randint(-2,4))
                detail=""
                if skill["effect"]=="holy" and not e.get("human"):
                    dmg=round(dmg*1.25);detail=" 마물에게 성력 피해가 증폭됐다."
                elif skill["effect"]=="critical" and random.random()<.3:
                    dmg=round(dmg*1.6);detail=" 급소를 꿰뚫는 치명타!"
                e["hp"]-=dmg
                if skill["effect"]=="heal":
                    heal_ratio=.14 if p["job"]=="성직자" else .08
                    healed=min(p["maxhp"]-p["hp"],max(1,round(p["maxhp"]*heal_ratio)))
                    p["hp"]+=healed
                    if healed:detail=f" 체력도 {healed} 회복했다."
                b["log"]=f"{skill['name']}! {dmg} 피해. MP -{cost}.{detail}"
                b["effect"]="skill";b["effect_t"]=.5
            b["submenu"]=None
        elif action=="defend":b["defending"]=True;b["log"]="방어 자세를 취했다. 이번 적의 공격은 무효가 된다.";b["effect"]="shield";b["effect_t"]=.4
        elif action=="item":
            if p["bandages"]>0:
                if p["hp"]>=p["maxhp"]:b["log"]="체력이 가득 차 있어 회복 붕대를 아꼈다."
                else:
                    healed=max(1,round(p["maxhp"]*.12));p["hp"]=min(p["maxhp"],p["hp"]+healed);p["bandages"]-=1;b["log"]=f"회복 붕대를 사용해 HP {healed} 회복."
            else:b["log"]="회복 붕대가 없다. 마을 상점에서 구매할 수 있다."
            return
        elif action=="flee":
            faith_bonus=.05 if p.get("religion")=="숲의 신앙" else 0
            chance=max(.1,min(.9,.5+(p["level"]-e["level"])*.15+faith_bonus))
            if random.random()<chance:
                b["log"]="도주에 성공했다.";self.mode="world";del self.battle;return
            b["log"]="도주에 실패했다!";b["effect"]="miss";b["effect_t"]=.25;b["submenu"]=None
        if e["hp"]<=0:
            e["hp"]=0;e["alive"]=False;b["won"]=True;b["effect"]="slash";b["effect_t"]=.55
            b["submenu"]=None;b["log"]=f"{e['name']}에게 결정타를 날렸다!"
            return
        self.enemy_turn()

    def finish_battle_victory(self):
        if not hasattr(self,"battle"):return
        b=self.battle;p=self.player;e=self.enemies[b["index"]]
        self.mode="world";del self.battle
        self.gain_xp(12);p["gold"]+=random.randint(8,16)
        loot=self.award_monster_loot(e) if not e.get("human") else None
        if not e.get("human") and p.get("quest") and p["quest"].get("source") in ("church","village","kingdom"):
            p["quest"]["count"]+=1
            if p["quest"]["count"]>=p["quest"]["goal"]:self.complete_monster_quest()
        if e.get("human") and p["job"]=="도둑":
            self.promote("도적");return
        if loot and self.dialog:self.dialog["text"]+="\n"+loot
        self.say(f"{e['name']} 처치! 경험치와 골드를 얻었다."+(f"\n{loot}" if loot else ""))

    def enemy_turn(self):
        b=self.battle;p=self.player;e=self.enemies[b["index"]]
        if b["defending"]:
            b["defending"]=False;b["log"]+=" 적의 공격을 완전히 막았다.";b["effect"]="shield";b["effect_t"]=.4
        else:
            dmg=max(1,e["atk"]-p["def"]+random.randint(-1,2));p["hp"]-=dmg;b["log"]+=f" {e['name']}의 반격! {dmg} 피해.";b["counter_t"]=.35
        if p["hp"]<=0:
            p["hp"]=p["maxhp"];p["gold"]//=2
            self.area=p["visited_faction"] if p["visited_faction"] in AREAS else "숲"
            p["area"]=self.area
            entry={"숲":(2200,800),"마을":(100,500),"교회 밖":(600,790),"교회 안":(480,640),
                   "왕실 상점가":(100,450),"왕국 기사단":(500,680),"왕국 안":(500,680),"왕의 방":(450,590)}
            p["x"],p["y"]=entry[self.area]
            self.mode="world";del self.battle
            self.walk_meter=0;self.spawn_enemies()
            self.say(f"쓰러졌다. 마지막으로 방문한 진영({p['visited_faction']})에서 눈을 떴다. 보유금 절반을 잃었다.",7)

    def handle_dialog_input(self, presses, click):
        page=self.dialog.get("text_page",0);last_page=self.dialog_page_count()-1
        if click:
            x,y=click
            if 95<=y<=128 and 642<=x<=835:
                if x<=700 and page>0:self.dialog["text_page"]-=1
                elif x>=754 and page<last_page:self.dialog["text_page"]+=1
                return
            if page==last_page:
                options_y=self.dialog_options_y()
                for i in range(len(self.dialog["options"])):
                    row_y=options_y+i*43
                    if 125<=x<=835 and row_y<=y<=row_y+35:self.choose(i);return
        for k in presses:
            if k in ("Escape","e","E"):self.dialog=None;return
            if k=="ArrowLeft" and page>0:self.dialog["text_page"]-=1;return
            if k in ("ArrowRight"," ","Space","Enter") and page<last_page:self.dialog["text_page"]+=1;return
            if page==last_page and k in ("1","2","3","4"):self.choose(int(k)-1);return

    def tick(self, dt, held_json, press_json, click_json):
        try:
            held=set(json.loads(held_json)); presses=json.loads(press_json); click=json.loads(click_json) if click_json else None
        except Exception: held=set();presses=[];click=None
        if isinstance(click,dict):click=(click.get("x"),click.get("y"))
        if not isinstance(click,(list,tuple)) or len(click)<2 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in click[:2]):click=None
        elif click is not None:click=(float(click[0]),float(click[1]))
        if not self.started:return
        self.player_walking=False
        self.save_elapsed+=max(0,float(dt))
        if self.save_elapsed>=1.5:
            self.save_elapsed=0;self.persist()
        self.tick_n+=1
        if self.notice_t>0:self.notice_t-=dt
        if self.dialog:
            self.handle_dialog_input(presses,click);self.draw();return
        if getattr(self,"mode","world")=="battle":
            b=self.battle
            b["effect_t"]=max(0,b.get("effect_t",0)-dt);b["counter_t"]=max(0,b.get("counter_t",0)-dt)
            if b.get("won"):
                if b["effect_t"]<=0:self.finish_battle_victory()
                self.draw();return
            pointer_action=False
            if click:
                x,y=click
                if b.get("submenu")=="attack" and 430<=y<=470:
                    if 260<=x<=400:self.battle_action("basic");pointer_action=True
                    elif 410<=x<=550:self.battle_action("skill");pointer_action=True
                    elif 560<=x<=700:b["submenu"]=None;pointer_action=True
                elif 475<=y<=532:
                    if x<310:self.battle_action("attack");pointer_action=True
                    elif x<490:self.battle_action("defend");pointer_action=True
                    elif x<670:self.battle_action("flee");pointer_action=True
                    else:self.battle_action("item");pointer_action=True
            # A click and a key can arrive in the same animation frame. Resolve
            # the pointer action alone so one frame can never spend two turns.
            if not pointer_action:
                for k in presses:
                    if b.get("submenu")=="attack":
                        if k=="1":self.battle_action("basic")
                        elif k=="2":self.battle_action("skill")
                        elif k in ("3","Escape"):b["submenu"]=None
                        break
                    acts={"1":"attack","2":"defend","3":"flee","4":"item","h":"item"}
                    if k in acts:self.battle_action(acts[k]);break
            self.draw();return
        p=self.player
        if self.map_open:
            if any(k in presses for k in ("m","M","Escape")):self.map_open=False
            self.draw();return
        if any(k in presses for k in ("m","M")):
            self.map_open=True;self.draw();return
        if any(k in presses for k in ("e","E","Enter")) and self.notice_t>0:
            self.notice_t=0;self.draw();return
        speed=220*min(dt,.05); dx=dy=0
        if any(k in held for k in ("ArrowLeft","a","A")):dx-=speed
        if any(k in held for k in ("ArrowRight","d","D")):dx+=speed
        if any(k in held for k in ("ArrowUp","w","W")):dy-=speed
        if any(k in held for k in ("ArrowDown","s","S")):dy+=speed
        if dx and dy:dx*=.707;dy*=.707
        if dx or dy:
            if abs(dx)>=abs(dy):p["facing"]="right" if dx>0 else "left"
            else:p["facing"]="down" if dy>0 else "up"
        mapw,maph=MAP_SIZE[self.area]
        old_x,old_y=p["x"],p["y"]
        next_x=max(32,min(mapw-32,old_x+dx))
        next_y=max(80,min(maph-32,old_y+dy))
        if not self.collides(next_x,old_y):p["x"]=next_x
        if not self.collides(p["x"],next_y):p["y"]=next_y
        moved_distance=math.hypot(p["x"]-old_x,p["y"]-old_y)
        self.player_walking=moved_distance>0
        if moved_distance:self.walk_phase=(self.walk_phase+moved_distance*.04)%math.tau
        self.update_world_ai(dt,moved_distance)
        if self.mode=="battle":self.draw();return
        for k in presses:
            if k in ("e","E","Enter"):self.interact()
            elif k in ("i","I"):self.open_inventory()
            elif k in ("q","Q"):
                self.open_dialog("퀘스트 기록",self.quest_journal_text(),["닫기"])
            elif k in ("h","H"):
                healed=max(1,round(p["maxhp"]*.12))
                if p["bandages"] and p["hp"]>=p["maxhp"]:self.say("체력이 가득 차 있어 회복 붕대를 아꼈다.")
                elif p["bandages"]:p["bandages"]-=1;p["hp"]=min(p["maxhp"],p["hp"]+healed);self.say(f"회복 붕대 사용: HP {healed} 회복.")
                else:self.say("회복 붕대가 없어.")
        self.draw()

    def rect(self,x,y,w,h,fill,outline=None):return {"t":"r","x":x,"y":y,"w":w,"h":h,"c":fill,"o":outline}
    def circle(self,x,y,r,fill,outline=None):return {"t":"c","x":x,"y":y,"r":r,"c":fill,"o":outline}
    def oval(self,x,y,w,h,fill,outline=None):return {"t":"o","x":x,"y":y,"w":w,"h":h,"c":fill,"o":outline}
    def line(self,x1,y1,x2,y2,color,width=2):return {"t":"l","x1":x1,"y1":y1,"x2":x2,"y2":y2,"c":color,"w":width}
    def polygon(self,points,fill,outline=None):return {"t":"p","pts":points,"c":fill,"o":outline}
    def text(self,x,y,s,size=16,color="#f6eddb",align="left"):return {"t":"t","x":x,"y":y,"s":str(s),"size":size,"c":color,"a":align}

    def draw_character(self,out,x,y,name,job="주민",race="인간",faction="마을",scale=1.0,weapon=None,armor=None,
                       facing="down",walking=False,phase=None):
        s=scale
        facing=facing if facing in ("up","down","left","right") else "down"
        if phase is None:phase=self.tick_n*.075+(x+y)*.001
        bob=(abs(math.sin(phase))*1.6 if walking else math.sin(phase)*.8)*s
        ground_y=y;y-=bob
        step=math.sin(phase)*3.2*s if walking else 0
        palettes={"교회":("#d8d8cd","#566782","#cfb66d"),"왕실":("#9a4e47","#ddd2b6","#d9b96d"),"방랑자":("#594a3c","#292b31","#a9784f"),"마을":("#6d7651","#9b7558","#d1b27c")}
        coat,trim,metal=palettes.get(faction,palettes["마을"])
        if job in ("성직자","교황","성인"):coat,trim,metal="#e1ddcd","#536183","#e7cf84"
        if job in ("기사","기사단장","전사"):coat,trim,metal="#77808b","#d7d0c1","#c9aa67"
        if job in ("도둑","도적","암살자"):coat,trim,metal="#35343e","#514553","#a87855"
        armor_colors={"가죽 갑옷":("#795239","#b48456","#e0c18a"),"방랑자 외투":("#334b3a","#687a50","#b89b62"),"늑대 털망토":("#535b62","#8d9998","#d5d4c9"),"멧돼지 가죽 갑옷":("#774831","#a66c43","#d4ad72"),"기사 갑옷":("#9ba5af","#d9dedc","#e4c979")}
        if armor in armor_colors:coat,trim,metal=armor_colors[armor]
        skin="#dfb999" if race=="인간" else "#d5a982"
        hair="#382b2a" if race=="인간" else "#593d35"
        vertical=facing in ("up","down")
        left_dx=0 if vertical else step
        right_dx=0 if vertical else -step
        left_dy=step if vertical else 0
        right_dy=-step if vertical else 0
        arm_sway=step*.55
        out.append(self.oval(x-15*s,ground_y+10*s,30*s,8*s,"#10171288"))
        out.append(self.rect(x-9*s+left_dx,y+6*s+left_dy,6*s,9*s,"#342b2a"))
        out.append(self.rect(x+3*s+right_dx,y+6*s+right_dy,6*s,9*s,"#342b2a"))
        out.append(self.polygon([x-9*s,y-7*s,x+9*s,y-7*s,x+13*s,y+8*s,x+8*s,y+14*s,x-8*s,y+14*s,x-13*s,y+8*s],coat,"#24252a"))
        out.append(self.rect(x-7*s,y-2*s,14*s,13*s,trim))
        out.append(self.rect(x-14*s+left_dx*.35,y-5*s+left_dy*.35,6*s,12*s,coat))
        out.append(self.rect(x+8*s+right_dx*.35,y-5*s+right_dy*.35,6*s,12*s,coat))
        out.append(self.circle(x,y-13*s,8*s,skin,"#473732"));out.append(self.oval(x-8*s,y-21*s,16*s,10*s,hair))
        if race=="수인":
            out.append(self.polygon([x-6*s,y-18*s,x-13*s,y-29*s,x-1*s,y-22*s],hair))
            out.append(self.polygon([x+6*s,y-18*s,x+13*s,y-29*s,x+1*s,y-22*s],hair))
            out.append(self.line(x+10*s,y+4*s,x+17*s,y+12*s,hair,3*s))
        else:out.append(self.oval(x-7*s,y-20*s,14*s,7*s,hair))
        if facing=="down":
            out.append(self.circle(x-3*s,y-13*s,1.3*s,"#292323"));out.append(self.circle(x+3*s,y-13*s,1.3*s,"#292323"))
        elif facing in ("left","right"):
            eye_side=-1 if facing=="left" else 1
            out.append(self.circle(x+eye_side*4*s,y-13*s,1.3*s,"#292323"))
            out.append(self.circle(x+eye_side*7*s,y-11*s,1.2*s,"#9c6951"))
        else:
            out.append(self.oval(x-5*s,y-19*s,10*s,4*s,"#241f20"))
        if job in ("성직자","교황","성인") and facing!="up":
            out.append(self.line(x,y-4*s,x,y+5*s,metal,2*s));out.append(self.line(x-3*s,y,x+3*s,y,metal,2*s))
        if job in ("전사","기사","기사단장","도둑","도적","암살자"):
            weapon_side=1 if facing in ("down","right") else -1
            if weapon=="사냥꾼 활":
                bow_x=x+weapon_side*13*s
                out.append(self.line(bow_x,y-12*s,bow_x+weapon_side*8*s,y-6*s,"#895b38",3*s))
                out.append(self.line(bow_x+weapon_side*8*s,y-6*s,bow_x+weapon_side*8*s,y+5*s,"#b18452",3*s))
                out.append(self.line(bow_x+weapon_side*8*s,y+5*s,bow_x,y+11*s,"#895b38",3*s))
                out.append(self.line(bow_x,y-12*s,bow_x,y+11*s,"#ead8ad",1.3*s))
            else:
                length=24 if weapon in ("철검","늑대 송곳니검") else 22 if weapon=="고블린 단검" else 20
                out.append(self.line(x+weapon_side*13*s,y+4*s,x+weapon_side*(13+length*.35)*s,y-length*.8*s,metal,2.4*s))
                out.append(self.line(x+weapon_side*10*s,y+6*s,x+weapon_side*16*s,y+9*s,"#49352b",3*s))
        if job in ("왕","군주"):out.append(self.polygon([x-7*s,y-19*s,x-6*s,y-27*s,x-2*s,y-22*s,x+2*s,y-28*s,x+5*s,y-21*s,x+8*s,y-25*s,x+8*s,y-18*s],"#d2ad55"))
        out.append(self.text(x,ground_y+27*s,name,11*s,"#fff3d9","center"))

    def draw_monster(self,out,x,y,name,scale=1.0):
        s=scale
        if name=="멧돼지":
            out.append(self.oval(x-25*s,y-13*s,48*s,27*s,"#805238","#382c27"));out.append(self.circle(x+18*s,y-2*s,13*s,"#946447"));out.append(self.circle(x+22*s,y-4*s,2*s,"#ffdf94"));out.append(self.polygon([x+15*s,y+8*s,x+19*s,y+16*s,x+24*s,y+7*s],"#e7d7b6"))
        elif name=="늑대":
            out.append(self.oval(x-28*s,y-11*s,52*s,22*s,"#72777a","#30373b"));out.append(self.polygon([x+13*s,y-8*s,x+31*s,y-4*s,x+22*s,y+8*s],"#8c9190"));out.append(self.polygon([x+13*s,y-11*s,x+12*s,y-25*s,x+23*s,y-14*s],"#555c60"));out.append(self.polygon([x+22*s,y-10*s,x+30*s,y-22*s,x+31*s,y-7*s],"#555c60"));out.append(self.circle(x+23*s,y-5*s,2*s,"#f1d578"))
        else:
            out.append(self.oval(x-17*s,y-10*s,34*s,26*s,"#5d9852","#253c29"));out.append(self.circle(x,y-16*s,11*s,"#75a95d"));out.append(self.polygon([x-7*s,y-22*s,x-17*s,y-32*s,x-11*s,y-15*s],"#54854b"));out.append(self.polygon([x+7*s,y-22*s,x+17*s,y-32*s,x+11*s,y-15*s],"#54854b"));out.append(self.circle(x-4*s,y-17*s,1.5*s,"#2d211b"));out.append(self.circle(x+4*s,y-17*s,1.5*s,"#2d211b"))

    def draw_tree(self,out,x,y,scale=1.0):
        s=scale
        out.append(self.oval(x-24*s,y+13*s,48*s,11*s,"#14291f99"))
        out.append(self.rect(x-6*s,y+1*s,12*s,26*s,"#57402d","#3b3028"))
        out.append(self.rect(x-2*s,y+4*s,4*s,20*s,"#755137"))
        out.append(self.oval(x-29*s,y-17*s,58*s,48*s,"#183329","#213b2c"))
        out.append(self.circle(x-9*s,y-17*s,18*s,"#315c38"))
        out.append(self.circle(x+11*s,y-12*s,15*s,"#244934"))
        out.append(self.circle(x-14*s,y-26*s,8*s,"#527448"))
        out.append(self.circle(x+2*s,y-29*s,7*s,"#42683f"))

    def draw_ground_detail(self,out,x,y,ix,iy):
        seed=(ix*92837111+iy*689287499+0x9E3779B9)&0xFFFFFFFF
        for mark in range(2):
            seed=(1664525*seed+1013904223)&0xFFFFFFFF
            px=x+9+(seed&63);py=y+9+((seed>>8)&63)
            if self.area=="숲":
                if seed%4==0:
                    out.append(self.oval(px-4,py-2,9,4,"#40583a"))
                    out.append(self.line(px-2,py+2,px-5,py+6,"#66834b",1))
                else:
                    out.append(self.circle(px,py,1.5,"#61774a" if seed%3 else "#91a365"))
            elif self.area=="마을":
                shade="#9a8563" if seed%2 else "#675a43"
                out.append(self.polygon([px-4,py,px-1,py-2,px+4,py-1,px+3,py+2,px-2,py+3],shade))
            elif self.area in ("교회 밖","왕실 상점가","왕국 안","왕국 기사단"):
                shade="#858078" if self.area=="교회 밖" else "#a08c6d"
                out.append(self.oval(px-2,py-1,5,3,shade))
            else:
                out.append(self.line(px-3,py,px+3,py,"#93807866",1))

    def draw_area_map(self,out):
        x0,y0,w,h=105,90,750,430
        left,top,plot_w,plot_h=132,145,696,315
        map_w,map_h=MAP_SIZE[self.area]
        scale=min(plot_w/map_w,plot_h/map_h)
        drawn_w,drawn_h=map_w*scale,map_h*scale
        map_x=left+(plot_w-drawn_w)/2
        map_y=top+(plot_h-drawn_h)/2
        def point(x,y):return map_x+x*scale,map_y+y*scale
        out.append(self.rect(0,0,W,H,"#080e15aa"))
        out.append(self.rect(x0,y0,w,h,"#17232cf5","#e2c783"))
        out.append(self.text(W/2,112,f"현재 구역 지도 · {self.area}",21,"#f2d696","center"))
        out.append(self.rect(map_x,map_y,drawn_w,drawn_h,"#263a35","#899186"))
        for i in range(1,5):
            gx=map_x+drawn_w*i/5;gy=map_y+drawn_h*i/5
            out.append(self.line(gx,map_y,gx,map_y+drawn_h,"#74847766",1))
            out.append(self.line(map_x,gy,map_x+drawn_w,gy,"#74847766",1))
        exit_kinds={"exit_village","exit_forest","exit_church","enter_church","exit_churchyard",
                    "exit_kingdom","exit_barracks","exit_city","exit_market","exit_throne","exit_palace"}
        quest=self.player.get("quest") or {}
        simple_targets={"밭에 물 주기":"field","교회 청소":"cleaning","기도":"altar"}
        simple_target=simple_targets.get(quest.get("title")) if quest.get("source")=="church_simple" else None
        monster_targets=self.area=="숲" and quest.get("source") in ("church","village","kingdom")
        for name,x,y,kind,*extra in self.entities():
            is_monster_target=False
            if kind=="enemy":
                enemy=self.enemies[extra[0]]
                is_monster_target=monster_targets and not enemy.get("human")
                if not is_monster_target:continue
            is_simple_target=kind==simple_target
            is_quest_target=is_monster_target or is_simple_target
            mx,my=point(x,y)
            if is_quest_target:color="#f08a5b"
            elif kind in exit_kinds:color="#e5c16e"
            elif kind=="wanderer_party":color="#86c995"
            else:color="#80b6bf"
            out.append(self.circle(mx,my,5,color,"#17232c"))
            if kind not in ("wanderer_party",):
                label=f"의뢰 대상: {name}" if is_monster_target else f"목표: {name}" if is_simple_target else name
                label_left=left+8;label_right=left+plot_w-8;label_width=len(label)*10
                label_x=mx+8;align="left"
                if label_x+label_width>label_right:
                    if mx-8-label_width>=label_left:label_x=mx-8;align="right"
                    else:label_x=label_left
                label_y=max(map_y+12,min(map_y+drawn_h-12,my-2))
                out.append(self.text(label_x,label_y,label,10,"#f3eee2",align))
        mx,my=point(self.player["x"],self.player["y"])
        out.append(self.circle(mx,my,7,"#e76c5e","#fff0d0"))
        out.append(self.text(x0+24,y0+h-18,"금색: 출구   주황색: 의뢰 목표   청록색: 시설   초록색: 방랑자   붉은색: 나",12,"#d8d2c5"))
        out.append(self.text(x0+w-20,y0+h-18,"M / Esc 닫기",12,"#e4c783","right"))

    def draw(self):
        if not self.started:return
        p=self.player;out=[];top,_=AREAS[self.area];mapw,maph=MAP_SIZE[self.area]
        camx=max(0,min(mapw-W,p["x"]-W/2));camy=max(0,min(maph-H,p["y"]-H/2))
        def sx(x):return x-camx
        def sy(y):return y-camy
        out.append(self.rect(0,0,W,H,top))
        gx=int(camx//80)*80;gy=int(camy//80)*80
        for wy in range(gy,gy+H+100,80):
            for wx in range(gx,gx+W+100,80):
                ix,iy=int(wx//80),int(wy//80)
                shade=(ix*7+iy*11)%3
                out.append(self.rect(sx(wx),sy(wy),81,81,FLOOR_PALETTES[self.area][shade]))
                self.draw_ground_detail(out,sx(wx),sy(wy),ix,iy)
                if self.area=="숲":
                    if (ix*13+iy*7)%4==0:
                        self.draw_tree(out,sx(wx+40),sy(wy+38),.86)
        # Distinct landmarks by zone
        if self.area=="숲":
            out.append(self.rect(sx(140),sy(730),2100,76,"#8a7651"))
            out.append(self.rect(sx(140),sy(730),2100,4,"#b49a68"))
            out.append(self.rect(sx(1390),sy(430),65,650,"#81704e"))
            out.append(self.rect(sx(1390),sy(430),65,4,"#b49a68"))
            for x,y in [(360,390),(760,1160),(1250,300),(1710,1270),(2060,550),(1900,1050)]:
                self.draw_tree(out,sx(x),sy(y),1.12)
        elif self.area=="마을":
            # The village's stone roads connect its three exits and meet at the common square.
            out.append(self.rect(sx(0),sy(456),1400,90,"#5c4c3b"))
            out.append(self.rect(sx(0),sy(463),1400,76,"#927b58"))
            out.append(self.rect(sx(646),sy(0),108,500,"#5c4c3b"))
            out.append(self.rect(sx(653),sy(0),94,500,"#927b58"))
            for px in range(18,1400,72):
                X=sx(px);Y=sy(479+(px//72%2)*23)
                out.append(self.polygon([X-15,Y,X-10,Y-5,X+11,Y-4,X+15,Y+2,X+8,Y+6,X-13,Y+5],"#ac966d","#83704f"))
            for py in range(18,500,68):
                X=sx(672+(py//68%2)*25);Y=sy(py)
                out.append(self.polygon([X,Y-14,X+5,Y-9,X+5,Y+10,X-2,Y+14,X-6,Y+7,X-5,Y-10],"#ac966d","#83704f"))
            # A working stone well gives the village square a recognizable center.
            wx,wy=sx(790),sy(635)
            out.append(self.oval(wx-38,wy+17,76,15,"#382f2788"))
            out.append(self.circle(wx,wy,26,"#76674f","#c1aa7a"))
            out.append(self.circle(wx,wy-2,18,"#263c45","#4d4a3c"))
            out.append(self.circle(wx-5,wy-7,5,"#668d91"))
            out.append(self.rect(wx+19,wy-20,5,24,"#785a38"))
            houses=[
                (240,230,"#8b6646","#a74e42"),(550,215,"#725a6d","#554761"),
                (970,235,"#775f4b","#8a6548"),(1090,700,"#705341","#6d4d42"),
                (350,720,"#806349","#9a6746"),
            ]
            for x,y,c,roof in houses:
                X,Y=sx(x),sy(y)
                out.append(self.oval(X-72,Y+51,144,22,"#29251f77"))
                out.append(self.rect(X-60,Y-18,120,82,c,"#49392f"))
                out.append(self.rect(X-56,Y-14,112,7,"#d2b778"))
                out.append(self.rect(X+29,Y-56,15,34,"#59453b"))
                out.append(self.polygon([X-68,Y-18,X,Y-72,X+68,Y-18],roof,"#4d332e"))
                out.append(self.line(X-58,Y-22,X,Y-67,"#d08a60",2))
                for window_x in (X-42,X+22):
                    out.append(self.rect(window_x,Y+1,20,21,"#344c55","#d8c18a"))
                    out.append(self.line(window_x+10,Y+2,window_x+10,Y+20,"#b7a77e",1))
                    out.append(self.line(window_x+1,Y+11,window_x+19,Y+11,"#b7a77e",1))
                out.append(self.rect(X-17,Y+20,34,44,"#342b31","#c3a879"))
                out.append(self.circle(X+10,Y+43,2,"#e2c47f"))
                out.append(self.rect(X-24,Y+61,48,5,"#b59a70"))
        elif self.area=="교회 밖":
            X,Y=sx(600),sy(300);out.append(self.rect(X-170,Y-45,340,150,"#85858a"));out.append(self.polygon([X-195,Y-45,X,Y-155,X+195,Y-45],"#777b87"));out.append(self.rect(X-50,Y-220,100,180,"#a19b8d"));out.append(self.polygon([X-60,Y-220,X,Y-290,X+60,Y-220],"#72798b"));out.append(self.rect(sx(130),sy(630),180,95,"#6e624e"))
        elif self.area=="교회 안":
            out.append(self.rect(sx(440),sy(95),80,510,"#873d49"));out.append(self.rect(sx(240),sy(130),55,270,"#594d4a"));out.append(self.rect(sx(665),sy(130),55,270,"#594d4a"))
            for y in (280,350,420):out.append(self.rect(sx(270),sy(y),150,14,"#674c42"));out.append(self.rect(sx(540),sy(y),150,14,"#674c42"))
            out.append(self.rect(sx(410),sy(95),140,42,"#d0b678"))
        elif self.area=="왕실 상점가":
            for x,y,c in [(260,230,"#805941"),(540,220,"#674b5c"),(850,230,"#76634a"),(960,650,"#735543")]:
                X,Y=sx(x),sy(y);out.append(self.rect(X-75,Y-15,150,100,c));out.append(self.polygon([X-85,Y-15,X,Y-75,X+85,Y-15],"#b47950"));out.append(self.rect(X-35,Y+26,70,12,"#d1b675"))
        elif self.area=="왕국 기사단":
            for x in (240,760):
                out.append(self.rect(sx(x),sy(150),10,380,"#8c7c63"));out.append(self.circle(sx(x),sy(130),18,"#a34c42"))
            for x in (350,500,650):out.append(self.rect(sx(x-30),sy(420),60,20,"#76523e"));out.append(self.rect(sx(x-4),sy(390),8,30,"#c8b178"))
        elif self.area=="왕국 안":
            out.append(self.rect(sx(480),sy(0),40,700,"#b59b68"));out.append(self.rect(sx(0),sy(350),1000,40,"#b59b68"));out.append(self.rect(sx(350),sy(150),300,190,"#89704e"))
        elif self.area=="왕의 방":
            out.append(self.rect(0,0,W,H,"#493740"));out.append(self.rect(sx(360),sy(80),180,560,"#8a3c48"))
            for x in (150,750):out.append(self.rect(sx(x),sy(100),28,470,"#c9b67b"))
        # Zone labels and actors; world coordinates are translated through the camera.
        for ent in self.entities():
            name,x,y,kind,*extra=ent;X,Y=sx(x),sy(y)
            if X < -75 or X > W+75 or Y < 65 or Y > H+40:continue
            if kind=="enemy":
                e=self.enemies[extra[0]]
                if e.get("human"):self.draw_character(out,X,Y,name,"기사","인간","왕실",.9)
                else:self.draw_monster(out,X,Y,name,.78);out.append(self.text(X,Y+31,name,11,"#fff0d4","center"))
            elif kind=="wanderer_party":
                for j in range(extra[0]%3+2):self.draw_character(out,X+(j-(extra[0]%3+1)/2)*26,Y+8,"", "방랑자", "인간", "방랑자",.72)
                out.append(self.text(X,Y+40,name,11,"#fff0d4","center"))
            elif kind in ("exit_village","exit_forest","exit_church","enter_church","exit_churchyard","exit_kingdom","exit_barracks","exit_city","exit_market","exit_throne","exit_palace"):
                out.append(self.circle(X,Y,19,"#d7b971"));out.append(self.text(X,Y,name,11,"#1f2928","center"))
            else:
                role={"priest":"성직자","trainer_church":"전사","trainer_kingdom":"기사","king":"왕","shop":"상인","inn":"여관주인","villager":"주민","camp":"방랑자 집단","field":"신자","cleaning":"신자","altar":"성직자","knight_hunters":"기사"}.get(kind,"주민")
                faction="교회" if kind in ("priest","trainer_church","altar","field","cleaning") else "왕실" if kind in ("trainer_kingdom","king","knight_hunters") else "방랑자" if kind in ("camp","wanderer_party") else "마을"
                race="수인" if kind in ("villager","wanderer_party") and (int(x+y)//80)%3==0 else "인간"
                self.draw_character(out,X,Y,name,role,race,faction,.86)
        self.draw_character(out,sx(p["x"]),sy(p["y"]),p["name"],p["job"],p["race"],p["faction"],1.0,
                            p.get("weapon"),p.get("armor"),facing=p.get("facing","down"),
                            walking=self.player_walking,phase=self.walk_phase if self.player_walking else None)
        out.append(self.rect(0,0,W,67,"#111b24"));out.append(self.text(20,18,"왕실과 교회의 전쟁 · 제1장",18,"#f1d39a"));out.append(self.text(20,45,f"{p['name']} · {p['race']} · {p['gender']} · {p['religion']} · {p['faction']} / {p['job']}",12))
        next_level_xp=max(1,p["level"]*35);xp_ratio=max(0,min(1,p["xp"]/next_level_xp))
        out.append(self.text(690,20,f"HP {p['hp']}/{p['maxhp']}   MP {p['mp']}/{p['maxmp']}",14,"#e7e9dc"));out.append(self.text(690,45,f"Lv.{p['level']} XP {p['xp']}/{next_level_xp} · {p['gold']}G · 붕대 {p['bandages']}개",13,"#e7e9dc"))
        out.append(self.rect(690,59,230,5,"#303b42"));out.append(self.rect(690,59,230*xp_ratio,5,"#e2c783"))
        out.append(self.rect(20,557,920,30,"#111b24dd"));out.append(self.text(32,572,f"{self.area}  ·  WASD/방향키 이동  ·  E 상호작용  ·  M 지도  ·  Q 퀘스트  ·  I 소지품  ·  H 붕대",13,"#e8ddc8"))
        if self.notice_t>0:
            out.append(self.rect(150,444,660,104,"#101923ef","#d8c08d"))
            for i,line in enumerate(self.visible_text_lines(self.notice,40,4)):out.append(self.text(170,458+i*19,line,15,"#f2ead9"))
            out.append(self.text(790,536,"E 닫기",11,"#e4c783","right"))
        if getattr(self,"mode","world")=="battle" and hasattr(self,"battle"):
            b=self.battle;e=self.enemies[b["index"]]
            out.append(self.rect(0,67,W,490,"#10151deE"));out.append(self.rect(65,90,830,445,"#252d36","#d7bb7c"));out.append(self.rect(65,90,830,445,"#38404a"))
            out.append(self.text(480,112,"전투",16,"#e8cc8f","center"))
            out.append(self.text(245,150,p["name"],17,"#f5ecd9","center"));out.append(self.text(705,150,e["name"],17,"#f5ecd9","center"))
            out.append(self.rect(145,170,200,13,"#351f25"));out.append(self.rect(145,170,200*max(0,p["hp"])/p["maxhp"],13,"#76ae77"));out.append(self.text(245,194,f"HP {p['hp']}/{p['maxhp']} · MP {p['mp']}/{p['maxmp']}",12,"#e7e3da","center"))
            out.append(self.rect(605,170,200,13,"#351f25"));out.append(self.rect(605,170,200*max(0,e["hp"])/e["maxhp"],13,"#c8564d"));out.append(self.text(705,194,f"HP {max(0,e['hp'])}/{e['maxhp']} · Lv.{e['level']}",12,"#e7e3da","center"))
            effect=b.get("effect");effect_t=max(0,b.get("effect_t",0))
            effect_duration=.55 if b.get("won") else {"slash":.42,"skill":.5,"shield":.4,"miss":.25}.get(effect,.4)
            progress=max(0,min(1,1-effect_t/effect_duration))
            impact=math.sin(progress*math.pi)
            lunge=30*impact if effect in ("slash","skill") else 0
            player_x=285+lunge
            enemy_x=675-18*math.sin(max(0,min(1,1-b.get("counter_t",0)/.35))*math.pi) if b.get("counter_t",0)>0 else 675
            self.draw_character(out,player_x,325,p["name"],p["job"],p["race"],p["faction"],1.85,
                                p.get("weapon"),p.get("armor"),facing="right")
            if e.get("human"):self.draw_character(out,enemy_x,325,e["name"],"기사" if "기사" in e["name"] else "상인","인간","왕실",1.65,facing="left")
            else:self.draw_monster(out,enemy_x,325,e["name"],1.65)
            if b.get("effect_t",0)>0:
                if effect=="slash":
                    offset=progress*72
                    out.append(self.circle(enemy_x-16,325,12+22*impact,"#ffe4a455"))
                    out.append(self.line(350+offset,300,555+offset,350,"#fff1c1",13))
                    out.append(self.line(375+offset,285,565+offset,335,"#e9aa55",4))
                elif effect=="skill":
                    out.append(self.circle(enemy_x-12,322,18+24*impact,"#f6cf7555","#ffe7a2"))
                    for i in range(8):
                        angle=i*math.tau/8
                        radius=12+progress*42
                        px=enemy_x+math.cos(angle)*radius
                        py=320+math.sin(angle)*radius*.72
                        out.append(self.circle(px,py,3+2*impact,"#ffd56f"))
                    out.append(self.line(player_x+75,300,enemy_x-35,335,"#ffe7a2",7+10*impact))
                elif effect=="shield":out.append(self.circle(player_x,310,53+8*impact,"#78c7d566","#a4e6e6"))
                elif effect=="miss":out.append(self.text(player_x,260-progress*26,"빗나감",15,"#e3b6a2","center"))
            if b.get("counter_t",0)>0:
                counter_progress=max(0,min(1,1-b["counter_t"]/.35));counter_x=630-counter_progress*125
                out.append(self.line(counter_x,315,counter_x-135,340,"#e85d50",11))
            out.append(self.text(480,410,b["log"],15,"#fff5df","center"))
            if b.get("submenu")=="attack":
                skill=self.skill_profile()
                choices=[("1 기본 공격","#405348"),(f"2 {skill['name']} · MP {skill['cost']}","#67503c"),("3 돌아가기","#454451")]
                for i,(label,c) in enumerate(choices):out.append(self.rect(260+i*150,430,140,40,c,"#a79774"));out.append(self.text(330+i*150,450,label,13,"#fff5df","center"))
            for i,(label,c) in enumerate([("1 공격","#59464a"),("2 방어","#40524e"),("3 도주","#424a5c"),("4 붕대","#685044")]):
                out.append(self.rect(130+i*180,480,165,44,c,"#a79774"));out.append(self.text(212+i*180,502,label,15,"#fff5df","center"))
            out.append(self.text(480,542,"아이템은 턴을 소비하지 않아 · 공격을 고르면 사용할 기술을 선택",12,"#d7d4c9","center"))
        if self.dialog:
            d=self.dialog;page=d.get("text_page",0);page_count=self.dialog_page_count()
            out.append(self.rect(100,83,760,442,"#131b26f5","#e2c783"));out.append(self.text(135,112,d["title"],23,"#f2d696"))
            if page_count>1:
                out.append(self.text(726,112,f"{page+1}/{page_count}",12,"#ded4c0","center"))
                if page>0:out.append(self.rect(642,95,58,34,"#344252","#a79774"));out.append(self.text(671,112,"←",15,"#f3eee2","center"))
                if page<page_count-1:out.append(self.rect(754,95,81,34,"#344252","#a79774"));out.append(self.text(794,112,"다음 →",12,"#f3eee2","center"))
            for i,line in enumerate(self.dialog_page_lines()):out.append(self.text(135,151+i*22,line,14,"#e9e5dc"))
            if page==page_count-1:
                options_y=self.dialog_options_y()
                for i,opt in enumerate(d["options"][:4]):out.append(self.rect(125,options_y+i*43,710,35,"#293747","#748494"));out.append(self.text(140,options_y+18+i*43,f"{i+1}. {opt}",15,"#f3eee2"))
            out.append(self.text(135,507,"숫자 키 선택 · ←/→ 또는 Space 페이지 이동 · E 닫기",11,"#c6bdad"))
        if self.map_open and getattr(self,"mode","world")=="world":self.draw_area_map(out)
        window.gameBridge.draw(json.dumps(out,ensure_ascii=False,separators=(",",":")))

game=Game()
def start_game(name): game.start(str(name))
def resume_game(snapshot): return game.load_snapshot(str(snapshot))
def save_game(): game.persist()
def tick(dt,held,presses,click): game.tick(float(dt),str(held),str(presses),str(click))
