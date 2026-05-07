from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import json
import re
import math


app = FastAPI()


# =========================
# 🧩 SETUP
# =========================


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
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
    """Convert text to lowercase and map leetspeak to letters (e.g. z33u3ss → zeus)."""
    text = text.lower()
    text = (
        text.replace("0", "o")
        .replace("1", "i")
        .replace("2", "z")
        .replace("3", "e")
        .replace("4", "a")
        .replace("5", "s")
        .replace("6", "g")
        .replace("7", "t")
        .replace("8", "b")
        .replace("9", "g")
    )
    text = re.sub(r"[^a-z\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()




def levenshtein(a: str, b: str) -> int:
    """Compute Levenshtein distance (edit distance)."""
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
        name = normalize(god["name"])
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
        # try fuzzy matching words
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
    if "wife" in text:
        return "wife"
    if "husband" in text:
        return "husband"
    if "brother" in text:
        return "brother"
    if "sister" in text:
        return "sister"
    if "parent" in text or "parents" in text:
        return "parents"
    if "child" in text or "children" in text:
        return "children"
    return None




def detect_mode(text: str):
    text = normalize(text)
    if "vs" in text or "versus" in text or "stronger" in text:
        return "comparison"
    if "rank" in text or "powerful" in text or "strongest" in text:
        return "power"
    if "god of" in text:
        return "domain"
    if "who is" in text or "tell me" in text or "describe" in text:
        return "general"
    return "general"




# =========================
# ⚡ POWER SYSTEM
# =========================


power_rankings = {
    "zeus": 10,
    "cronus": 10,
    "poseidon": 9,
    "hades": 9,
    "rhea": 8,
    "hera": 8,
    "athena": 8,
    "apollo": 7,
    "artemis": 7,
    "demeter": 7,
    "ares": 7,
    "persephone": 7,
    "hermes": 6,
    "aphrodite": 6,
    "hephaestus": 6,
    "dionysus": 6,
    "hestia": 5,
}


def get_power_rank(god):
    key = normalize(god["name"])
    return power_rankings.get(key, 5)


def get_power_ranking_list():
    sorted_gods = sorted(greek_gods, key=lambda g: get_power_rank(g), reverse=True)
    out = ["🔥 GOD POWER RANKING:\n"]
    for i, god in enumerate(sorted_gods, 1):
        out.append(f"{i}. {god['name']} (Power {get_power_rank(god)})")
    return "\n".join(out)


def compare_gods(god1, god2):
    r1, r2 = get_power_rank(god1), get_power_rank(god2)
    if r1 > r2:
        return f"⚔️ {god1['name']} is stronger than {god2['name']}."
    elif r2 > r1:
        return f"⚔️ {god2['name']} is stronger than {god1['name']}."
    else:
        return f"⚔️ {god1['name']} and {god2['name']} are equally powerful."




# =========================
# 📘 RESPONSE BUILDERS
# =========================


def format_general_info(god):
    return (
        f"🏛️ {god['name']} — {god['description']}\n"
        f"{god['name']} belongs to the Olympian pantheon."
    )




def format_relation(god, relation):
    if relation in ["wife", "husband"]:
        return f"💍 {god['name']}'s spouse: {', '.join(god.get('spouse', ['Unknown']))}"
    if relation in ["brother", "sister"]:
        return f"👥 {god['name']}'s siblings: {', '.join(god.get('siblings', ['Unknown']))}"
    if relation == "parents":
        return f"👨‍👩‍👧 {god['name']}'s parents: {', '.join(god.get('parents', ['Unknown']))}"
    if relation == "children":
        return f"👶 {god['name']}'s children: {', '.join(god.get('children', ['Unknown']))}"
    return f"ℹ️ No relation info available for {god['name']}."




# =========================
# 🚀 MAIN ENDPOINT
# =========================


@app.post("/ask")
async def ask_god(query: Query):
    text = query.message
    normalized = normalize(text)
    mode = detect_mode(text)
    relation = detect_relation(text)


    # POWER MODE
    if mode == "power":
        response = get_power_ranking_list()


    # COMPARISON MODE
    elif mode == "comparison":
        gods = extract_two_gods(text)
        if len(gods) == 2:
            response = compare_gods(gods[0], gods[1])
        else:
            response = "⚠️ Please mention two gods (e.g. Zeus vs Hades)."


    # RELATION INFO
    elif relation:
        god = extract_single_god(text)
        if god:
            response = format_relation(god, relation)
        else:
            response = "❌ God not found."


    # DOMAIN INFO ("What is Apollo god of?")
    elif mode == "domain":
        god = extract_single_god(text)
        if god:
            response = f"⚡ {god['name']} is associated with: {god['description']}"
        else:
            response = "❌ God not found."


    # GENERAL INFO (default)
    else:
        god = extract_single_god(text)
        if god:
            response = format_general_info(god)
        else:
            response = "❌ God not found."


    # Save log
    try:
        await db.chats.insert_one({"user": query.message, "bot": response})
    except Exception as e:
        print("MongoDB error:", e)


    return {"response": response}