import time
import subprocess
import json
import os
import requests
import re
import urllib.parse
import sys
import traceback
import argparse
from datetime import datetime, timezone

# Setup Global Logging
import pathlib
base_dir = os.path.expanduser("~/.cache/pathoftrading-v1.0")
os.makedirs(base_dir, exist_ok=True)
LOG_FILE = os.path.join(base_dir, "script.log")
sys.stdout = open(LOG_FILE, "a")
sys.stderr = sys.stdout
print(f"\n--- Script Started at {time.ctime()} ---")
print(f"WAYLAND_DISPLAY: {os.environ.get('WAYLAND_DISPLAY')}")
print(f"DISPLAY: {os.environ.get('DISPLAY')}")

DATA_PATH = os.path.join(base_dir, "price_data.json")
STATS_CACHE_PATH = os.path.join(base_dir, "trade_stats.json")
ITEMS_CACHE_PATH = os.path.join(base_dir, "trade_items.json")
LEAGUES_CACHE_PATH = os.path.join(base_dir, "trade_leagues.json")
REQUEST_HISTORY_PATH = os.path.join(base_dir, "request_history.json")

config_dir = os.path.expanduser("~/.config/pathoftrading-v1.0")
os.makedirs(config_dir, exist_ok=True)
SETTINGS_PATH = os.path.join(config_dir, "settings.json")
LOCK_PATH = os.path.join(base_dir, "price_check.lock")
LOCKOUT_FILE = os.path.join(base_dir, "lockout.txt")
HISTORY_LOG_FILE = os.path.join(base_dir, "query_history.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) PathOfTrading/1.0",
    "Content-Type": "application/json"
}

# Global League cache
DEFAULT_LEAGUE = "Fate of the Vaal"

CATEGORY_MAPPING = {
    "Gloves": "armour.gloves", "Body Armours": "armour.chest", "Helmets": "armour.helmet",
    "Boots": "armour.boots", "Amulets": "accessory.amulet", "Rings": "accessory.ring",
    "Belts": "accessory.belt", "Quivers": "armour.quiver", "Shields": "armour.shield",
    "Foci": "armour.focus", "Focus": "armour.focus", "Bucklers": "armour.buckler",
    "Buckler": "armour.buckler", "Bows": "weapon.bow", "Crossbows": "weapon.crossbow",
    "Wands": "weapon.wand", "Sceptres": "weapon.sceptre", "Staves": "weapon.staff",
    "Two Hand Maces": "weapon.twomace", "Two Hand Swords": "weapon.twosword",
    "Two Hand Axes": "weapon.twoaxe", "One Hand Maces": "weapon.onemace",
    "One Hand Swords": "weapon.onesword", "One Hand Axes": "weapon.oneaxe",
    "Claws": "weapon.claw", "Daggers": "weapon.dagger", "Spears": "weapon.spear",
    "Flails": "weapon.flail", "Quarterstaves": "weapon.warstaff", "Life Flasks": "flask.life",
    "Mana Flasks": "flask.mana", "Jewels": "jewel", "Waystones": "map.waystone",
    "Tablet": "map.tablet"
}

def load_settings():
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, 'r') as f: return json.load(f)
        except: pass
    return {"selected_league": DEFAULT_LEAGUE}

def save_settings(selected_league):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    try:
        with open(SETTINGS_PATH, 'w') as f: json.dump({"selected_league": selected_league}, f)
    except: pass

def fetch_leagues():
    if os.path.exists(LEAGUES_CACHE_PATH):
        if time.time() - os.path.getmtime(LEAGUES_CACHE_PATH) < 86400:
            try:
                with open(LEAGUES_CACHE_PATH, 'r') as f: return json.load(f)
            except: pass
    try:
        # Try poe.ninja for best metadata
        resp = requests.get("https://poe.ninja/poe2/api/data/index-state", headers=HEADERS, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            # economyLeagues contains active ones. We want their names.
            leagues = [l["name"] for l in data.get("economyLeagues", [])]
            if leagues:
                with open(LEAGUES_CACHE_PATH, 'w') as f: json.dump(leagues, f)
                return leagues
    except: pass
    
    # Fallback to GGG API
    try:
        resp = requests.get("https://www.pathofexile.com/api/trade2/data/leagues", headers=HEADERS, timeout=2)
        if resp.status_code == 200:
            leagues = [l["id"] for l in resp.json().get("result", []) if l.get("realm") == "poe2"]
            if leagues:
                with open(LEAGUES_CACHE_PATH, 'w') as f: json.dump(leagues, f)
                return leagues
    except: pass
    
    return ["Fate of the Vaal", "HC Fate of the Vaal", "Standard", "Hardcore"]

LOCKOUT_FILE = "/tmp/poe2_lockout.txt"

def check_lockout():
    if os.path.exists(LOCKOUT_FILE):
        try:
            with open(LOCKOUT_FILE, "r") as f:
                lockout_until = float(f.read().strip())
            now = time.time()
            if lockout_until > now: return int(lockout_until - now)
        except: pass
    return 0

def apply_lockout_from_headers(headers):
    state = headers.get("X-Rate-Limit-Ip-State", "")
    rules = headers.get("X-Rate-Limit-Ip", "")
    if not state or not rules: return
    try:
        max_wait = 0
        for s_part, r_part in zip(state.split(","), rules.split(",")):
            count = int(s_part.split(":")[0])
            limit = int(r_part.split(":")[0])
            window = int(r_part.split(":")[1])
            if limit - count <= 1:
                wait = window / limit
                if wait > max_wait: max_wait = wait
        if max_wait > 0:
            with open(LOCKOUT_FILE, "w") as f: f.write(str(time.time() + max_wait))
    except: pass

def get_api_urls(league_name):
    encoded = urllib.parse.quote(league_name)
    return {
        "search": f"https://www.pathofexile.com/api/trade2/search/poe2/{encoded}",
        "fetch": "https://www.pathofexile.com/api/trade2/fetch/",
        "ninja": f"https://poe.ninja/poe2/api/economy/exchange/current/overview?league={encoded}&type=Currency"
    }

def format_age(indexed_str):
    try:
        indexed_time = datetime.strptime(indexed_str, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = now - indexed_time
        secs = diff.total_seconds()
        if secs < 60: return f"{int(secs)}s"
        mins = secs / 60
        if mins < 60: return f"{int(mins)}m"
        hours = mins / 60
        if hours < 24: return f"{int(hours)}h"
        days = hours / 24
        return f"{int(days)}d"
    except: return ""

# --- STAT MAPPING LOGIC ---

class StatMapper:
    def __init__(self):
        self.trade_stats = []
        self._load_trade_stats()
        self.pseudo_map = {
            "to maximum life": "pseudo.pseudo_total_life",
            "to maximum mana": "pseudo.pseudo_total_mana",
            "to maximum energy shield": "pseudo.pseudo_total_energy_shield",
            "to fire resistance": "pseudo.pseudo_total_fire_resistance",
            "to cold resistance": "pseudo.pseudo_total_cold_resistance",
            "to lightning resistance": "pseudo.pseudo_total_lightning_resistance",
            "to chaos resistance": "pseudo.pseudo_total_chaos_resistance",
            "to all elemental resistances": "pseudo.pseudo_total_all_elemental_resistances",
            "to strength": "pseudo.pseudo_total_strength",
            "to dexterity": "pseudo.pseudo_total_dexterity",
            "to intelligence": "pseudo.pseudo_total_intelligence",
            "to all attributes": "pseudo.pseudo_total_all_attributes",
            "increased movement speed": "pseudo.pseudo_increased_movement_speed"
        }
        self.synonym_map = {
            "chancetodazeonhit": "dazesonhit",
            "chancetoblindenemiesonhit": "blindenemiesonhit",
            "chancetoigniteonhit": "igniteonhit",
            "chancetofreezeonhit": "freezeonhit",
            "chancetoshockonhit": "shockonhit"
        }

    def _load_trade_stats(self):
        if os.path.exists(STATS_CACHE_PATH):
            if time.time() - os.path.getmtime(STATS_CACHE_PATH) < 86400:
                try:
                    with open(STATS_CACHE_PATH, 'r') as f:
                        self.trade_stats = json.load(f)
                        return
                except: pass
        try:
            resp = requests.get("https://www.pathofexile.com/api/trade2/data/stats", headers=HEADERS, timeout=5)
            if resp.status_code == 200:
                self.trade_stats = resp.json().get("result", [])
                with open(STATS_CACHE_PATH, 'w') as f: json.dump(self.trade_stats, f)
        except Exception as e: print(f"Failed to fetch trade stats: {e}")

    def _normalize_for_search(self, text):
        clean = text.lower()
        clean = clean.replace("in map", "in your maps")
        clean = clean.replace("in area", "in your maps")
        
        clean = re.sub(r'[^a-z]', '', clean)
        
        prefixes = ["maphas", "mapcontains", "areahas", "areacontains", "yourmapshave", "yourmapscontain"]
        for p in prefixes:
            if clean.startswith(p):
                clean = clean[len(p):]
                break
                
        if clean.endswith("usesremaining") or clean.endswith("useremaining"):
            clean = clean.replace("usesremaining", "").replace("useremaining", "")
            
        return clean

    def _perform_api_lookup(self, pattern, is_equipment, preferred_source=None):
        best_match = None
        target = self._normalize_for_search(pattern)
        for category in self.trade_stats:
            for entry in category.get("entries", []):
                stat_text = entry.get("text", "")
                if "(enchant)" in stat_text.lower() or "(fractured)" in stat_text.lower(): continue
                is_local_id = "(local)" in stat_text.lower()
                clean_stat = self._normalize_for_search(stat_text)
                clean_stat_no_local = clean_stat
                if is_local_id and clean_stat.endswith("local"): clean_stat_no_local = clean_stat[:-5]
                
                if clean_stat == target or clean_stat_no_local == target:
                    entry_id = entry.get("id")
                    if preferred_source and entry_id.startswith(preferred_source + "."):
                        if is_equipment and is_local_id: return {"id": entry_id}
                        if not is_equipment and not is_local_id: return {"id": entry_id}
                    if is_equipment and is_local_id: return {"id": entry_id}
                    if not is_equipment and not is_local_id: 
                        if best_match is None: best_match = {"id": entry_id}
                    elif best_match is None: best_match = {"id": entry_id}
        return best_match

    def find_trade_id(self, line, is_equipment=True, source=None, allow_pseudo=True):
        clean_line = re.sub(r'\s*\([^)]+\)\s*', '', line)
        clean_line = re.split(r' \u2014 | \u2013 | \u2012 | - ', clean_line)[0].strip()
        numbers = re.findall(r"([+-]?\d+(?:\.\d+)?)", clean_line)
        val = float(numbers[0]) if numbers else None
        
        # Hardcoded Intercepts for badly formatted Tablet modifiers
        lower_line = clean_line.lower()
        if "additional rare chest" in lower_line: return {"id": "explicit.stat_231864447", "value": val}
        if "chance to contain three additional breaches" in lower_line: return {"id": "explicit.stat_2440265466", "value": val}
        if "chance to contain an additional breach" in lower_line: return {"id": "explicit.stat_3049505189", "value": val}
        if "effect of expedition remnants" in lower_line: return {"id": "explicit.stat_3078574625", "value": val}
        
        match_pattern = self._normalize_for_search(clean_line)
        if allow_pseudo:
            for text, pseudo_id in self.pseudo_map.items():
                if self._normalize_for_search(text) == match_pattern:
                    return {"id": pseudo_id, "value": val if val is not None else 1.0}
        res = self._perform_api_lookup(match_pattern, is_equipment, preferred_source=source)
        if res: return {"id": res["id"], "value": val}
        if "reduced" in clean_line.lower() and val is not None:
            alt = match_pattern.replace("reduced", "increased")
            res = self._perform_api_lookup(alt, is_equipment, preferred_source=source)
            if res: return {"id": res["id"], "value": -val, "is_negative": True}
        if "less" in clean_line.lower() and val is not None:
            alt = match_pattern.replace("less", "more")
            res = self._perform_api_lookup(alt, is_equipment, preferred_source=source)
            if res: return {"id": res["id"], "value": -val, "is_negative": True}
        if match_pattern in self.synonym_map:
            res = self._perform_api_lookup(self.synonym_map[match_pattern], is_equipment, preferred_source=source)
            if res: return {"id": res["id"], "value": val}
        if match_pattern.startswith("chanceto"):
            alt = match_pattern[8:]
            res = self._perform_api_lookup(alt, is_equipment, preferred_source=source)
            if not res: res = self._perform_api_lookup(alt.replace("onhit", "sonhit"), is_equipment, preferred_source=source)
            if res: return {"id": res["id"], "value": val}
        return None

# --- ITEM MAPPING ---

class ItemMapper:
    def __init__(self):
        self.item_types = []
        self._load_item_types()

    def _load_item_types(self):
        if os.path.exists(ITEMS_CACHE_PATH):
            if time.time() - os.path.getmtime(ITEMS_CACHE_PATH) < 86400:
                try:
                    with open(ITEMS_CACHE_PATH, 'r') as f: self.item_types = json.load(f); return
                except: pass
        try:
            resp = requests.get("https://www.pathofexile.com/api/trade2/data/items", headers=HEADERS, timeout=5)
            if resp.status_code == 200:
                data = resp.json().get("result", [])
                self.item_types = []
                for cat in data:
                    for entry in cat.get("entries", []):
                        if entry.get("type"): self.item_types.append(entry["type"])
                self.item_types.sort(key=len, reverse=True)
                with open(ITEMS_CACHE_PATH, 'w') as f: json.dump(self.item_types, f)
        except: pass

    def get_base_name(self, name_line):
        for itype in self.item_types:
            if itype in name_line: return itype
        return name_line

# --- ECONOMY LOGIC ---

RATES_CACHE = {
    "whetstone": 2.21, "exalted": 1.0, "exalt": 1.0,
    "divine": 193.0, "vaal": 4.45, "chaos": 7.70, "alch": 0.32,
    "regal": 0.38, "mirror": 1640154.0
}

NINJA_CURRENCY_MAP = {
    "Chaos Orb": "chaos", "Exalted Orb": "exalted", "Divine Orb": "divine",
    "Orb of Alchemy": "alch", "Orb of Transmutation": "transmute", "Orb of Augmentation": "aug",
    "Orb of Annulment": "annul", "Regal Orb": "regal", "Vaal Orb": "vaal",
    "Gemcutter's Prism": "gcp", "Glassblower's Bauble": "bauble", "Blacksmith's Whetstone": "whetstone",
    "Armourer's Scrap": "scrap", "Mirror of Kalandra": "mirror", "Orb of Chance": "chance",
    "Artificer's Orb": "artificers", "Orb of Extraction": "orb-of-extraction",
    "Arcanist's Etcher": "etcher", "Scroll of Wisdom": "wisdom", "Fracturing Orb": "fracturing-orb",
    "Hinekora's Lock": "hinekoras-lock", "Lesser Jeweller's Orb": "lesser-jewellers-orb",
    "Greater Jeweller's Orb": "greater-jewellers-orb", "Perfect Jeweller's Orb": "perfect-jewellers-orb",
    "Crystallised Corruption": "crystallised-corruption"
}

def fetch_exchange_rates(urls):
    global RATES_CACHE
    try:
        resp = requests.get(urls["ninja"], timeout=0.5)
        if resp.status_code == 200:
            data = resp.json()
            lines = data.get("lines", [])
            exalt_divine_val = next((i.get("primaryValue", 0) for i in lines if i.get("id") == "exalted"), None)
            if exalt_divine_val:
                for item in lines:
                    name = item.get("id", "").lower()
                    val = item.get("primaryValue", 0)
                    if val > 0:
                        ev = val / exalt_divine_val
                        RATES_CACHE[name] = ev
                        if name == "exalted": RATES_CACHE["exalt"] = ev
                        if name == "orb-of-alchemy": RATES_CACHE["alch"] = ev
    except: pass
    return RATES_CACHE

def get_exalt_value(amount, currency, rates):
    return amount * rates.get(currency.lower(), 0.0)

# --- CORE LOGIC ---

def get_clipboard():
    # Retry loop to combat clipboard synchronization delays
    for i in range(15):
        for cmd in [['wl-paste'], ['xclip', '-selection', 'clipboard', '-o']]:
            try:
                result = subprocess.run(cmd, text=True, capture_output=True, check=True)
                data = result.stdout
                if data and data.strip() and "Rarity:" in data: return data
            except subprocess.CalledProcessError as e:
                print(f"[Attempt {i}] {cmd[0]} failed (code {e.returncode}). Error: {e.stderr.strip()}")
            except Exception as e:
                print(f"[Attempt {i}] {cmd[0]} exception: {str(e)}")
        time.sleep(0.1)
        
    # Fallback to whatever is there if we never see a valid item
    for cmd in [['wl-paste'], ['xclip', '-selection', 'clipboard', '-o']]:
        try:
            data = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
            if data and data.strip(): return data
        except: pass
    return None

def parse_item(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines: return None
    item = {"itemClass": "", "rarity": "", "name": "", "baseType": "", "isBulk": False, "raw": text, "stats": [], "ilvl": None, "quality": None, "sockets": None, "gemLevel": None}
    for line in lines:
        if line.startswith("Item Class:"): item["itemClass"] = line.split(":")[1].strip()
        if line.startswith("Rarity:"): item["rarity"] = line.split(":")[1].strip()
        if line.startswith("Item Level:"): item["ilvl"] = line.split(":")[1].strip()
        if line.startswith("Level:"):
            l_match = re.search(r'Level:\s*(\d+)', line)
            if l_match: item["gemLevel"] = l_match.group(1)
        if line.startswith("Quality:"):
            q_match = re.search(r'\+(\d+)', line)
            if q_match: item["quality"] = q_match.group(1)
        if line.startswith("Sockets:"): item["sockets"] = len(re.findall(r'[A-Za-z]', line.split(":")[1]))
    bulk_classes = ["Currency", "Stackable Currency", "Omen", "Essence", "Fragment", "Rune", "Idol", "Soul Core", "Uncut Skill Gem", "Uncut Support Gem", "Augment"]
    if item["itemClass"] in bulk_classes or not item["rarity"]:
        item["isBulk"] = True
        item["name"] = next((l for l in lines if ":" not in l), "Unknown")
        item["baseType"] = item["name"]
    else:
        try:
            ridx = next(i for i, l in enumerate(lines) if l.startswith("Rarity:"))
            name_line = lines[ridx+1]
            if item["rarity"] in ["Unique", "Rare"]: item["name"], item["baseType"] = name_line, lines[ridx+2]
            else:
                mapper = ItemMapper()
                item["name"] = name_line
                item["baseType"] = mapper.get_base_name(name_line)
        except: item["name"] = item["baseType"] = lines[0]
        metadata_keywords = ["Item Class:", "Rarity:", "--------", "Requirements:", "Item Level:", "Requires:", "Stack Size:", "Quality:", "Sockets:"]
        current_tier, current_source = None, "explicit"
        for line in lines:
            if any(line.startswith(k) for k in metadata_keywords): continue
            if "uses remaining" in line.lower(): continue
            if line.startswith("{") and "Modifier" in line:
                tag = line.lower()
                if "implicit" in tag: current_source = "implicit"
                elif "prefix" in tag or "suffix" in tag or "unique" in tag or "rune" in tag:
                    current_source = "explicit"
                elif "fractured" in tag: current_source = "fractured"
                elif "enchant" in tag: current_source = "enchant"
                tier_match = re.search(r'tier: (\d+)', tag)
                if tier_match: current_tier = int(tier_match.group(1))
                continue
            if ":" in line and not any(line.startswith(k) for k in ["Grants Skill:", "Bonded:", "Adds"]): continue
            item["stats"].append({"text": line, "tier": current_tier, "source": current_source})
            current_tier = None
    return item

session = requests.Session()
session.headers.update(HEADERS)

def fetch_real_price(item):
    try:
        wait = check_lockout()
        if wait > 0:
            return {"item": item.get("name", ""), "price": f"Limit approaching. Wait {wait}s", "listings": [], "parsed_stats": item.get("parsed_stats", []), "base_properties": item.get("base_properties", []), "raw_item": item, "leagues": fetch_leagues(), "selected_league": item.get("selected_league", DEFAULT_LEAGUE)}
            
        mapper = StatMapper()
        stat_filters = []
        cat_id = CATEGORY_MAPPING.get(item.get("itemClass"), "")
        is_equip = cat_id.startswith("armour.") or cat_id.startswith("weapon.")
        settings = load_settings()
        league = item.get("selected_league", settings.get("selected_league", DEFAULT_LEAGUE))
        save_settings(league)
        urls = get_api_urls(league)
        leagues, rates = fetch_leagues(), fetch_exchange_rates(urls)
        
        # --- BULK ITEM INTERCEPT (poe.ninja cache) ---
        if item.get("isBulk") and "waystone" not in item.get("name", "").lower():
            ninja_id = item.get("name", "").lower().replace(" ", "-").replace("'", "")
            exalt_val = rates.get(ninja_id)
            
            # If not in the base Currency cache, fetch its specific category on-demand
            if exalt_val is None:
                item_name_lower = item.get("name", "").lower()
                types_to_check = []
                if "omen" in item_name_lower: types_to_check = ["Ritual"]
                elif "essence" in item_name_lower: types_to_check = ["Essences"]
                elif "soul core" in item_name_lower: types_to_check = ["SoulCores"]
                elif "rune" in item_name_lower: types_to_check = ["Runes"]
                elif "idol" in item_name_lower: types_to_check = ["Idols"]
                elif "uncut" in item_name_lower: types_to_check = ["UncutGems"]
                elif "lineage" in item_name_lower: types_to_check = ["LineageSupportGems"]
                elif "abyss" in item_name_lower: types_to_check = ["Abyss"]
                elif "breach" in item_name_lower: types_to_check = ["Breach"]
                elif "expedition" in item_name_lower: types_to_check = ["Expedition"]
                elif "delirium" in item_name_lower: types_to_check = ["Delirium"]
                elif "fragment" in item.get("itemClass", "").lower() or "splinter" in item_name_lower: types_to_check = ["Fragments"]
                else: types_to_check = ["Currency", "Fragments", "Essences", "Ritual", "SoulCores", "Runes", "Expedition", "Delirium", "Breach", "Abyss", "Idols"]
                
                league_encoded = urllib.parse.quote(league)
                for t in types_to_check:
                    endpoint = f"https://poe.ninja/poe2/api/economy/exchange/current/overview?league={league_encoded}&type={t}"
                    try:
                        r = requests.get(endpoint, headers=HEADERS, timeout=2.0)
                        if r.status_code == 200:
                            for line in r.json().get("lines", []):
                                if line.get("id") == ninja_id or line.get("name", "").lower() == item_name_lower:
                                    exalt_val = line.get("primaryValue")
                                    if exalt_val is not None:
                                        # Normalize to exalt value using our existing divine/exalt cache
                                        if rates.get("exalt", 1.0) != 1.0:
                                            exalt_val = exalt_val / rates.get("exalt", 1.0)
                                        break
                        if exalt_val is not None: break
                    except: pass
            
            if exalt_val is not None:
                # Format a display string based on value
                if ninja_id == "exalted": disp = "1 E"
                elif ninja_id == "divine": disp = "1 D"
                elif exalt_val >= rates.get("divine", 193.0): 
                    disp = f"{round(exalt_val / rates.get('divine', 193.0), 2)} D"
                else: 
                    disp = f"{round(exalt_val, 2)} E"
                
                listing = {"display": disp, "exalt_val": exalt_val, "age": "poe.ninja avg"}
                return {"status": "success", "item": item.get("name"), "listings": [listing], "parsed_stats": [], "base_properties": [], "raw_item": item, "leagues": leagues, "selected_league": league}
            # Note: We NO LONGER have a fallback 'else' here, so if poe.ninja fails, it falls through to the GGG Auction API
                
        parsed_stats = item.get("parsed_stats")
        if parsed_stats is None:
            temp_stats, ele_res_sum, best_ele_tier = [], 0, None
            ELE_IDS = ["stat_3372524247", "stat_4220027924", "stat_1671376347"]
            ALL_RES_ID = "stat_2901986750"
            for stat_entry in item.get("stats", []):
                line, tier, source = stat_entry["text"], stat_entry.get("tier"), stat_entry.get("source")
                res = mapper.find_trade_id(line, is_equipment=is_equip, source=source, allow_pseudo=False)
                if res:
                    sid = res["id"].split(".")[-1]
                    if sid in ELE_IDS:
                        ele_res_sum += res["value"]; best_ele_tier = tier if tier and (best_ele_tier is None or tier < best_ele_tier) else best_ele_tier; continue
                    elif sid == ALL_RES_ID:
                        ele_res_sum += (res["value"] * 3); best_ele_tier = tier if tier and (best_ele_tier is None or tier < best_ele_tier) else best_ele_tier; continue
                res = mapper.find_trade_id(line, is_equipment=is_equip, source=source, allow_pseudo=True)
                if res:
                    is_neg = res.get("is_negative", False) or (res["value"] is not None and res["value"] < 0)
                    val = res["value"]
                    cval = round(val * (1.0 if any(k in line for k in ["Grants Skill:", "Bonded:", "Adds"]) or val is None else 0.8)) if val is not None else ""
                    temp_stats.append({"id": res["id"], "text": line, "tier": tier, "value": val, "min": "" if is_neg else str(cval), "max": str(cval) if is_neg else "", "active": True})
            if ele_res_sum > 0:
                cval = round(ele_res_sum * 0.8)
                temp_stats.insert(0, {"id": "pseudo.pseudo_total_elemental_resistance", "text": f"+{int(ele_res_sum)}% total Elemental Resistance", "tier": best_ele_tier, "value": ele_res_sum, "min": str(cval), "max": "", "active": True})
            parsed_stats = temp_stats
        for ps in parsed_stats:
            if ps.get("active"):
                f_val = {}
                if ps.get("min") not in [None, ""]: f_val["min"] = float(ps["min"])
                if ps.get("max") not in [None, ""]: f_val["max"] = float(ps["max"])
                if f_val: stat_filters.append({"id": ps["id"], "value": f_val})
                else: stat_filters.append({"id": ps["id"]})
        base_properties = item.get("base_properties")
        if base_properties is None:
            base_properties = []
            is_magic_rare = item["rarity"] in ["Magic", "Rare"]
            base_properties.append({"id": "class", "text": item["itemClass"], "value": item["itemClass"], "active": is_magic_rare})
            base_properties.append({"id": "rarity", "text": item["rarity"], "value": item["rarity"], "active": False})
            base_properties.append({"id": "base", "text": item["baseType"], "value": item["baseType"], "active": not is_magic_rare})
            if item.get("rarity") == "Unique": base_properties.append({"id": "name", "text": item["name"], "value": item["name"], "active": True})
            if item.get("ilvl"): base_properties.append({"id": "ilvl", "text": f"iLvl {item['ilvl']}", "value": int(item["ilvl"]), "active": False})
            if item.get("gemLevel"): base_properties.append({"id": "gemLevel", "text": f"Level {item['gemLevel']}", "value": int(item["gemLevel"]), "active": True})
            if item.get("quality"): base_properties.append({"id": "quality", "text": f"+{item['quality']}% Quality", "value": int(item["quality"]), "active": False})
            if item.get("sockets"): 
                if item.get("itemClass") in ["Skill Gems", "Support Gems"]:
                    base_properties.append({"id": "gem_sockets", "text": f"{item['sockets']} Sockets", "value": int(item["sockets"]), "active": False})
                else:
                    base_properties.append({"id": "sockets", "text": f"{item['sockets']} Sockets", "value": int(item["sockets"]), "active": False})
        
        display_name = item["name"]
        if item["rarity"] == "Rare" and item["name"] != item["baseType"]: display_name = f"{item['name']} ({item['baseType']})"
        
        query = {"query": {"status": {"option": "securable"}, "filters": {"trade_filters": {"filters": {"sale_type": {"option": "any"}}}, "type_filters": {"filters": {}}, "misc_filters": {"filters": {}}, "equipment_filters": {"filters": {}}}}, "sort": {"price": "asc"}}
        type_filters, misc_filters, equipment_filters = query["query"]["filters"]["type_filters"]["filters"], query["query"]["filters"]["misc_filters"]["filters"], query["query"]["filters"]["equipment_filters"]["filters"]
        for bp in base_properties:
            if not bp.get("active"): continue
            b_id, b_val = bp["id"], bp["value"]
            if b_id == "rarity": type_filters["rarity"] = {"option": b_val.lower()}
            elif b_id == "class":
                cat = CATEGORY_MAPPING.get(b_val)
                if cat: type_filters["category"] = {"option": cat}
            elif b_id == "base": query["query"]["type"] = b_val
            elif b_id == "name": query["query"]["name"] = b_val
            elif b_id == "ilvl": misc_filters["ilvl"] = {"min": b_val}
            elif b_id == "gemLevel": misc_filters["gem_level"] = {"min": b_val}
            elif b_id == "quality": misc_filters["quality"] = {"min": b_val}
            elif b_id == "sockets": equipment_filters["rune_sockets"] = {"min": b_val}
            elif b_id == "gem_sockets": misc_filters["gem_sockets"] = {"min": b_val}
        if stat_filters: query["query"]["stats"] = [{"type": "and", "filters": stat_filters}]
        if not type_filters: del query["query"]["filters"]["type_filters"]
        if not misc_filters: del query["query"]["filters"]["misc_filters"]
        if not equipment_filters: del query["query"]["filters"]["equipment_filters"]
        
        # LOG HISTORY
        log_data = []
        if os.path.exists(HISTORY_LOG_FILE):
            try:
                with open(HISTORY_LOG_FILE, "r") as f: log_data = json.load(f)
            except: pass
        log_data.insert(0, {"timestamp": time.ctime(), "item": display_name, "query": query})
        with open(HISTORY_LOG_FILE, "w") as f: json.dump(log_data[:20], f, indent=2)
        
        # EXECUTE SEARCH
        response = session.post(urls["search"], json=query)
        apply_lockout_from_headers(response.headers)
        
        if response.status_code == 429:
            retry = response.headers.get("Retry-After", "60")
            return {"item": display_name, "price": f"Rate Limit Exceeded. Try again in {retry}s", "listings": [], "parsed_stats": parsed_stats, "base_properties": base_properties, "raw_item": item, "leagues": leagues, "selected_league": league}
        elif response.status_code == 400: return {"item": display_name, "price": "Invalid Search (Check Base Type)", "listings": [], "parsed_stats": parsed_stats, "base_properties": base_properties, "raw_item": item, "leagues": leagues, "selected_league": league}
        elif response.status_code != 200: return {"item": display_name, "price": f"Search Error {response.status_code}", "listings": [], "parsed_stats": parsed_stats, "base_properties": base_properties, "raw_item": item, "leagues": leagues, "selected_league": league}
        
        data = response.json()
        result_ids, query_id = data.get("result", []), data.get("id")
        if not result_ids: return {"item": display_name, "price": "No matching listings", "listings": [], "parsed_stats": parsed_stats, "base_properties": base_properties, "raw_item": item, "leagues": leagues, "selected_league": league}
        
        all_results = []
        if result_ids:
            batch = ",".join(result_ids[:10])
            resp = session.get(f"{urls['fetch']}{batch}", params={"query": query_id})
            apply_lockout_from_headers(resp.headers)
            
            if resp.status_code == 429:
                retry = resp.headers.get("Retry-After", "60")
                return {"item": display_name, "price": f"Fetch Limit Exceeded. Wait {retry}s", "listings": [], "parsed_stats": parsed_stats, "base_properties": base_properties, "raw_item": item, "leagues": leagues, "selected_league": league}
            elif resp.status_code == 200:
                batch_json = resp.json()
                if batch_json and "result" in batch_json: all_results = batch_json.get("result", [])

        prices, norm = [], {"chaos": "C", "divine": "D", "alch": "A", "orb-of-alchemy": "A", "annul": "An", "exalt": "E", "exalty": "E", "exalted": "E", "regal": "R", "vaal": "V"}
        for res in all_results:
            if not isinstance(res, dict): continue
            listing = res.get("listing")
            if not listing or not listing.get("price"): continue
            p = listing.get("price")
            amt, cur = p.get("amount"), p.get("currency", "").lower()
            if amt is not None and cur:
                ev = get_exalt_value(amt, cur, rates)
                disp = f"{amt} {norm.get(cur, cur[:1].upper())}"
                if norm.get(cur, cur[:1].upper()) not in ["E", "D"]: disp += f" ({round(ev, 2)} E)"
                prices.append({"display": disp, "exalt_val": ev, "age": format_age(listing.get("indexed", ""))})
        prices.sort(key=lambda x: x["exalt_val"])
        return {"status": "success", "item": display_name, "listings": prices[:10], "parsed_stats": parsed_stats, "base_properties": base_properties, "raw_item": item, "leagues": leagues, "selected_league": league}
    except Exception as e:
        traceback.print_exc()
        return {"item": item.get("name", "Error"), "price": f"Error: {str(e)}", "listings": [], "parsed_stats": parsed_stats if 'parsed_stats' in locals() else [], "base_properties": base_properties if 'base_properties' in locals() else [], "raw_item": item, "leagues": fetch_leagues(), "selected_league": DEFAULT_LEAGUE}

def send_to_ui_loading(item, is_requery=False):
    display_name = item.get("name", "Unknown")
    if item.get("rarity") == "Rare" and item.get("name") != item.get("baseType"): display_name = f"{item['name']} ({item['baseType']})"
    settings, leagues = load_settings(), fetch_leagues()
    data = {"status": "loading", "item": display_name, "price": "Searching market...", "listings": [], "parsed_stats": item.get("parsed_stats", []), "base_properties": item.get("base_properties", []), "leagues": leagues, "selected_league": item.get("selected_league", settings.get("selected_league", DEFAULT_LEAGUE)), "raw_item": item}
    with open(DATA_PATH, 'w') as f: json.dump(data, f); os.system(f"touch {DATA_PATH}")
    if not is_requery:
        # Check if it's already running to avoid duplicates
        subprocess.run(['pkill', '-f', 'PathofTrading.qml'])
        qml_path = os.path.join(os.path.dirname(__file__), "PathofTrading.qml")
        subprocess.Popen(['quickshell', '-p', qml_path])

def send_to_ui_final(data):
    with open(DATA_PATH, 'w') as f: json.dump(data, f); os.system(f"touch {DATA_PATH}")

def main():
    if os.path.exists(LOCK_PATH):
        try:
            with open(LOCK_PATH, 'r') as f: pid = int(f.read().strip())
            os.kill(pid, 0); return
        except: pass
    with open(LOCK_PATH, 'w') as f: f.write(str(os.getpid()))
    try:
        parser = argparse.ArgumentParser()
        parser.add_argument('--requery-data', type=str)
        args = parser.parse_args(); settings = load_settings()
        if args.requery_data:
            payload = json.loads(args.requery_data); item = payload.get("raw_item", {})
            item["parsed_stats"], item["base_properties"] = payload.get("parsed_stats", []), payload.get("base_properties", [])
            item["selected_league"] = payload.get("selected_league", settings.get("selected_league", DEFAULT_LEAGUE))
            send_to_ui_loading(item, is_requery=True); send_to_ui_final(fetch_real_price(item)); return
        raw = get_clipboard()
        if not raw: subprocess.run(['notify-send', 'PoE 2 Price Check', 'Clipboard is empty. Copy an item first!']); return
        item = parse_item(raw)
        if not item: subprocess.run(['notify-send', 'PoE 2 Price Check', 'Clipboard does not contain a valid item.']); return
        item["selected_league"] = settings.get("selected_league", DEFAULT_LEAGUE)
        send_to_ui_loading(item, is_requery=False); send_to_ui_final(fetch_real_price(item))
    finally:
        if os.path.exists(LOCK_PATH): os.remove(LOCK_PATH)

if __name__ == "__main__": main()
