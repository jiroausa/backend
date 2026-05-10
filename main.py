from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import json
import re
import math

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

with open("gods.json") as f:
    greek_gods = json.load(f)

client = AsyncIOMotorClient("mongodb://localhost:27017")
db = client["mythbot"]

class Query(BaseModel):
    message: str


# =========================
# 🧠 NORMALIZER & FUZZY MATCHERS
# =========================

def normalize(text: str) -> str:
    text = text.lower()
    text = (
        text.replace("0", "o").replace("1", "i").replace("2", "z")
            .replace("3", "e").replace("4", "a").replace("5", "s")
            .replace("6", "g").replace("7", "t").replace("8", "b")
            .replace("9", "g")
    )
    text = re.sub(r"[^a-z\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def levenshtein(a: str, b: str) -> int:
    if len(a) < len(b):
        return levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    prev_row = range(len(b) + 1)
    for i, ca in enumerate(a):
        curr_row = [i + 1]
        for j, cb in enumerate(b):
            insertions = prev_row[j + 1] + 1
            deletions = curr_row[j] + 1
            substitutions = prev_row[j] + (ca != cb)
            curr_row.append(min(insertions, deletions, substitutions))
        prev_row = curr_row
    return prev_row[-1]


def find_closest_god(text: str):
    text = normalize(text).replace(" ", "")
    best = None
    best_score = math.inf
    for god in greek_gods:
        name = normalize(god["name"]).replace(" ", "")
        dist = levenshtein(text, name)
        overlap = len([c for c in text if c in name])
        score = dist - overlap * 0.5
        if score < best_score:
            best = god
            best_score = score
    return best if best_score <= 4 else None


def extract_two_gods(text: str):
    cleaned = normalize(text)
    found = []
    for god in greek_gods:
        name = normalize(god["name"])
        if name in cleaned:
            found.append(god)
    if len(found) < 2:
        for word in cleaned.split():
            god = find_closest_god(word)
            if god and god not in found:
                found.append(god)
                if len(found) == 2:
                    break
    return found[:2]


def extract_single_god(text: str):
    cleaned = normalize(text)
    for god in greek_gods:
        if normalize(god["name"]) in cleaned:
            return god
    for word in cleaned.split():
        god = find_closest_god(word)
        if god:
            return god
    return None


# =========================
# ⚡ DETECTION LOGIC
# =========================

def detect_relation(text: str):
    text = normalize(text)
    if "wife" in text or "spouse" in text or "married to" in text:
        return "spouse"
    if "husband" in text:
        return "spouse"
    if "brother" in text or "sister" in text or "sibling" in text:
        return "siblings"
    if "parent" in text or "mother" in text or "father" in text:
        return "parents"
    if "child" in text or "children" in text or "son" in text or "daughter" in text:
        return "children"
    if "lover" in text or "affair" in text or "romance" in text:
        return "lovers"
    if "roman" in text or "roman equivalent" in text or "roman name" in text:
        return "roman"
    return None


def detect_mode(text: str):
    t = normalize(text)
    if "vs" in t or "versus" in t or "stronger" in t or "compare" in t or "beat" in t or "fight" in t:
        return "comparison"
    if "rank" in t or "powerful" in t or "strongest" in t or "power list" in t or "ranking" in t:
        return "power"
    if "symbol" in t or "symbols" in t:
        return "symbols"
    if "myth" in t or "myths" in t or "story" in t or "stories" in t or "legend" in t:
        return "myths"
    if "power" in t or "ability" in t or "abilities" in t or "can do" in t:
        return "abilities"
    if "weakness" in t or "weaknesses" in t or "flaw" in t or "flaws" in t:
        return "weaknesses"
    if "personality" in t or "character" in t or "like" in t and "what is" in t:
        return "personality"
    if "animal" in t or "sacred animal" in t:
        return "animals"
    if "home" in t or "live" in t or "where" in t:
        return "home"
    if "god of" in t or "goddess of" in t or "domain" in t or "rules over" in t:
        return "domain"
    if "who is" in t or "tell me" in t or "describe" in t or "about" in t or "info" in t:
        return "general"
    return "general"


# =========================
# ⚡ POWER SYSTEM
# =========================

power_rankings = {
    "zeus": 10, "cronus": 10, "rhea": 8,
    "poseidon": 9, "hades": 9,
    "hera": 8, "athena": 8,
    "apollo": 7, "artemis": 7, "demeter": 7, "ares": 7, "persephone": 7,
    "hermes": 6, "aphrodite": 6, "hephaestus": 6, "dionysus": 6,
    "hestia": 5, "asclepius": 5, "eros": 5, "nemesis": 6,
    "nike": 5, "pan": 4, "hypnos": 5, "thanatos": 6,
    "morpheus": 4, "tyche": 5,
}

def get_power_rank(god):
    return power_rankings.get(normalize(god["name"]), 4)

def get_power_ranking_list():
    sorted_gods = sorted(greek_gods, key=lambda g: get_power_rank(g), reverse=True)
    out = ["🔱 OLYMPIAN POWER RANKING:\n"]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for i, god in enumerate(sorted_gods, 1):
        rank = get_power_rank(god)
        bar = "█" * rank + "░" * (10 - rank)
        medal = medals.get(i, f"{i}.")
        title = god.get("title", "")
        out.append(f"{medal} {god['name']} — {title}\n   Power: [{bar}] {rank}/10")
    return "\n\n".join(out)

def compare_gods(god1, god2):
    r1, r2 = get_power_rank(god1), get_power_rank(god2)
    name1, name2 = god1["name"], god2["name"]
    title1 = god1.get("title", "")
    title2 = god2.get("title", "")
    domains1 = ", ".join(god1.get("domain", [])[:3])
    domains2 = ", ".join(god2.get("domain", [])[:3])
    bar1 = "█" * r1 + "░" * (10 - r1)
    bar2 = "█" * r2 + "░" * (10 - r2)

    result = (
        f"⚔️ DIVINE BATTLE: {name1} vs {name2}\n\n"
        f"🏛️ {name1} — {title1}\n"
        f"   Domains: {domains1}\n"
        f"   Power: [{bar1}] {r1}/10\n\n"
        f"🏛️ {name2} — {title2}\n"
        f"   Domains: {domains2}\n"
        f"   Power: [{bar2}] {r2}/10\n\n"
    )
    if r1 > r2:
        diff = r1 - r2
        result += f"⚡ VERDICT: {name1} wins with a power advantage of {diff} point{'s' if diff > 1 else ''}!"
    elif r2 > r1:
        diff = r2 - r1
        result += f"⚡ VERDICT: {name2} wins with a power advantage of {diff} point{'s' if diff > 1 else ''}!"
    else:
        result += f"⚡ VERDICT: {name1} and {name2} are equally matched — an eternal standoff!"
    return result


# =========================
# 📘 RESPONSE BUILDERS
# =========================

def format_general_info(god):
    name = god["name"]
    title = god.get("title", "")
    desc = god.get("description", god.get("description", ""))
    domains = ", ".join(god.get("domain", []))
    symbols = ", ".join(god.get("symbols", []))
    roman = god.get("roman_equivalent", "Unknown")
    home = god.get("home", "Unknown")
    personality = god.get("personality", "")

    return (
        f"🏛️ {name} — {title}\n\n"
        f"📖 {desc}\n\n"
        f"⚡ Domains: {domains}\n"
        f"🔮 Symbols: {symbols}\n"
        f"🏠 Home: {home}\n"
        f"🏺 Roman Equivalent: {roman}\n"
        f"🧠 Personality: {personality}"
    )


def format_myths(god):
    myths = god.get("myths", [])
    if not myths:
        return f"📜 No recorded myths found for {god['name']}."
    out = [f"📜 MYTHS & LEGENDS OF {god['name'].upper()}:\n"]
    for i, myth in enumerate(myths, 1):
        out.append(f"{i}. {myth}")
    return "\n\n".join(out)


def format_abilities(god):
    powers = god.get("powers", [])
    if not powers:
        return f"⚡ No specific powers recorded for {god['name']}."
    out = [f"⚡ POWERS & ABILITIES OF {god['name'].upper()}:\n"]
    for p in powers:
        out.append(f"• {p}")
    return "\n".join(out)


def format_weaknesses(god):
    weaknesses = god.get("weaknesses", [])
    if not weaknesses:
        return f"🛡️ No recorded weaknesses for {god['name']}."
    out = [f"🛡️ WEAKNESSES OF {god['name'].upper()}:\n"]
    for w in weaknesses:
        out.append(f"• {w}")
    return "\n".join(out)


def format_symbols(god):
    symbols = god.get("symbols", [])
    if not symbols:
        return f"🔮 No symbols recorded for {god['name']}."
    return f"🔮 {god['name']}'s sacred symbols: {', '.join(symbols)}"


def format_animals(god):
    animals = god.get("sacred_animals", [])
    if not animals:
        return f"🐾 No sacred animals recorded for {god['name']}."
    return f"🐾 {god['name']}'s sacred animals: {', '.join(animals)}"


def format_home(god):
    home = god.get("home", "Unknown")
    return f"🏠 {god['name']} resides at: {home}"


def format_domain(god):
    domain = god.get("domain", [])
    title = god.get("title", "")
    if not domain:
        return f"⚡ {god['name']} is {title}."
    return f"⚡ {god['name']} ({title}) is the god/goddess of: {', '.join(domain)}"


def format_relation(god, relation):
    name = god["name"]
    if relation == "spouse":
        val = god.get("spouse", [])
        lovers = god.get("lovers", [])
        resp = f"💍 {name}'s spouse: {', '.join(val) if val else 'None'}"
        if lovers:
            resp += f"\n💘 Known lovers: {', '.join(lovers[:5])}"
        return resp
    if relation == "siblings":
        val = god.get("siblings", [])
        return f"👥 {name}'s siblings: {', '.join(val) if val else 'None known'}"
    if relation == "parents":
        val = god.get("parents", [])
        return f"👨‍👩‍👧 {name}'s parents: {', '.join(val) if val else 'Unknown'}"
    if relation == "children":
        val = god.get("children", [])
        return f"👶 {name}'s children: {', '.join(val) if val else 'None recorded'}"
    if relation == "lovers":
        val = god.get("lovers", [])
        return f"💘 {name}'s known lovers: {', '.join(val) if val else 'None recorded'}"
    if relation == "roman":
        val = god.get("roman_equivalent", "Unknown")
        return f"🏺 {name}'s Roman equivalent: {val}"
    return f"ℹ️ No relation info available for {name}."


def list_all_gods():
    out = ["📚 KNOWN GREEK GODS & TITANS IN MY KNOWLEDGE:\n"]
    for god in greek_gods:
        title = god.get("title", "")
        out.append(f"• {god['name']} — {title}")
    return "\n".join(out)


# =========================
# 🚀 MAIN ENDPOINT
# =========================

@app.get("/")
async def root():
    return {"message": "AskGreekGodsBot backend is running ⚡"}


@app.post("/ask")
async def ask_god(query: Query):
    text = query.message
    normalized = normalize(text)
    mode = detect_mode(text)
    relation = detect_relation(text)

    # LIST ALL GODS
    if any(phrase in normalized for phrase in ["list all", "all gods", "who do you know", "show all"]):
        response = list_all_gods()

    # POWER RANKING
    elif mode == "power":
        response = get_power_ranking_list()

    # COMPARISON
    elif mode == "comparison":
        gods = extract_two_gods(text)
        if len(gods) == 2:
            response = compare_gods(gods[0], gods[1])
        else:
            response = "⚠️ Please mention two gods to compare (e.g. 'Zeus vs Hades')."

    # MYTHS
    elif mode == "myths":
        god = extract_single_god(text)
        if god:
            response = format_myths(god)
        else:
            response = "❌ God not found. Try asking about Zeus, Athena, Hades, etc."

    # ABILITIES / POWERS
    elif mode == "abilities":
        god = extract_single_god(text)
        if god:
            response = format_abilities(god)
        else:
            response = "❌ God not found."

    # WEAKNESSES
    elif mode == "weaknesses":
        god = extract_single_god(text)
        if god:
            response = format_weaknesses(god)
        else:
            response = "❌ God not found."

    # SYMBOLS
    elif mode == "symbols":
        god = extract_single_god(text)
        if god:
            response = format_symbols(god)
        else:
            response = "❌ God not found."

    # SACRED ANIMALS
    elif mode == "animals":
        god = extract_single_god(text)
        if god:
            response = format_animals(god)
        else:
            response = "❌ God not found."

    # HOME / LOCATION
    elif mode == "home":
        god = extract_single_god(text)
        if god:
            response = format_home(god)
        else:
            response = "❌ God not found."

    # RELATION INFO
    elif relation:
        god = extract_single_god(text)
        if god:
            response = format_relation(god, relation)
        else:
            response = "❌ God not found."

    # DOMAIN
    elif mode == "domain":
        god = extract_single_god(text)
        if god:
            response = format_domain(god)
        else:
            response = "❌ God not found."

    # GENERAL INFO (default)
    else:
        god = extract_single_god(text)
        if god:
            response = format_general_info(god)
        else:
            response = (
                "❌ I couldn't find that god. Try asking about:\n"
                "Zeus, Hera, Poseidon, Hades, Athena, Apollo, Artemis, Ares,\n"
                "Hephaestus, Aphrodite, Hermes, Demeter, Persephone, Dionysus,\n"
                "Hestia, Eros, Nike, Nemesis, Pan, Hypnos, Morpheus, Thanatos,\n"
                "Tyche, Asclepius, Rhea, or Cronus.\n\n"
                "You can also ask:\n"
                "• 'Zeus vs Poseidon' for a comparison\n"
                "• 'Show power ranking'\n"
                "• 'What are Zeus's myths?'\n"
                "• 'What is Apollo's weakness?'\n"
                "• 'Who are Hades's children?'"
            )

    # Save log to MongoDB
    try:
        await db.chats.insert_one({"user": query.message, "bot": response})
    except Exception as e:
        print("MongoDB error:", e)

    return {"response": response}