# Adaptive Fitness Agent - naive baseline (v0-baseline)
#
# This is the deliberate "before" version for our metrics: one file, one God
# object, big if/else blocks and copy-pasted prompts. It has the same features
# and rules as the final version (FUNCTIONAL_FLOW.md), but no structure.
#
# Run:  python coach.py   (needs a running Ollama with the qwen3 model)

import copy
import json
import os

from langchain_ollama import ChatOllama

STATE_FILE = os.path.join("data", "baseline_state.json")

CATALOG = [
    {"id": "bw_squat", "name": "Bodyweight squat", "pattern": "squat", "equipment": ["bodyweight"], "contra": ["knee"], "compound": True, "load_type": "bw", "level": "beginner"},
    {"id": "goblet_squat", "name": "Goblet squat", "pattern": "squat", "equipment": ["dumbbells"], "contra": ["knee"], "compound": True, "load_type": "kg", "level": "beginner"},
    {"id": "back_squat", "name": "Barbell back squat", "pattern": "squat", "equipment": ["barbell"], "contra": ["knee", "lower_back"], "compound": True, "load_type": "kg", "level": "intermediate"},
    {"id": "split_squat", "name": "Dumbbell split squat", "pattern": "squat", "equipment": ["dumbbells"], "contra": ["knee"], "compound": True, "load_type": "kg", "level": "intermediate"},
    {"id": "wall_sit", "name": "Wall sit", "pattern": "squat", "equipment": ["bodyweight"], "contra": [], "compound": False, "load_type": "time", "level": "beginner"},
    {"id": "glute_bridge", "name": "Glute bridge", "pattern": "hinge", "equipment": ["bodyweight"], "contra": [], "compound": True, "load_type": "bw", "level": "beginner"},
    {"id": "kb_deadlift", "name": "Kettlebell deadlift", "pattern": "hinge", "equipment": ["kettlebell"], "contra": ["lower_back"], "compound": True, "load_type": "kg", "level": "beginner"},
    {"id": "romanian_deadlift", "name": "Dumbbell Romanian deadlift", "pattern": "hinge", "equipment": ["dumbbells"], "contra": ["lower_back"], "compound": True, "load_type": "kg", "level": "intermediate"},
    {"id": "barbell_deadlift", "name": "Barbell deadlift", "pattern": "hinge", "equipment": ["barbell"], "contra": ["lower_back"], "compound": True, "load_type": "kg", "level": "advanced"},
    {"id": "hip_thrust", "name": "Barbell hip thrust", "pattern": "hinge", "equipment": ["barbell"], "contra": [], "compound": True, "load_type": "kg", "level": "intermediate"},
    {"id": "push_up", "name": "Push-up", "pattern": "push", "equipment": ["bodyweight"], "contra": ["wrist", "shoulder"], "compound": True, "load_type": "bw", "level": "beginner"},
    {"id": "band_chest_press", "name": "Band chest press", "pattern": "push", "equipment": ["bands"], "contra": [], "compound": True, "load_type": "bw", "level": "beginner"},
    {"id": "db_bench_press", "name": "Dumbbell bench press", "pattern": "push", "equipment": ["dumbbells"], "contra": ["shoulder"], "compound": True, "load_type": "kg", "level": "beginner"},
    {"id": "db_shoulder_press", "name": "Dumbbell shoulder press", "pattern": "push", "equipment": ["dumbbells"], "contra": ["shoulder", "neck"], "compound": True, "load_type": "kg", "level": "intermediate"},
    {"id": "barbell_bench_press", "name": "Barbell bench press", "pattern": "push", "equipment": ["barbell"], "contra": ["shoulder"], "compound": True, "load_type": "kg", "level": "intermediate"},
    {"id": "superman", "name": "Superman hold", "pattern": "pull", "equipment": ["bodyweight"], "contra": ["lower_back"], "compound": False, "load_type": "bw", "level": "beginner"},
    {"id": "band_row", "name": "Band row", "pattern": "pull", "equipment": ["bands"], "contra": [], "compound": True, "load_type": "bw", "level": "beginner"},
    {"id": "db_row", "name": "Dumbbell row", "pattern": "pull", "equipment": ["dumbbells"], "contra": ["lower_back"], "compound": True, "load_type": "kg", "level": "beginner"},
    {"id": "lat_pulldown", "name": "Lat pulldown", "pattern": "pull", "equipment": ["machines"], "contra": ["shoulder"], "compound": True, "load_type": "kg", "level": "beginner"},
    {"id": "pull_up", "name": "Pull-up", "pattern": "pull", "equipment": ["pullup_bar"], "contra": ["shoulder"], "compound": True, "load_type": "bw", "level": "advanced"},
    {"id": "farmer_carry", "name": "Farmer carry", "pattern": "carry", "equipment": ["dumbbells"], "contra": ["wrist"], "compound": True, "load_type": "time", "level": "beginner"},
    {"id": "suitcase_carry", "name": "Kettlebell suitcase carry", "pattern": "carry", "equipment": ["kettlebell"], "contra": [], "compound": True, "load_type": "time", "level": "intermediate"},
    {"id": "plank", "name": "Plank", "pattern": "core", "equipment": ["bodyweight"], "contra": ["shoulder"], "compound": False, "load_type": "time", "level": "beginner"},
    {"id": "dead_bug", "name": "Dead bug", "pattern": "core", "equipment": ["bodyweight"], "contra": [], "compound": False, "load_type": "bw", "level": "beginner"},
    {"id": "side_plank", "name": "Side plank", "pattern": "core", "equipment": ["bodyweight"], "contra": ["shoulder"], "compound": False, "load_type": "time", "level": "intermediate"},
    {"id": "brisk_walk", "name": "Brisk walk", "pattern": "cardio", "equipment": ["bodyweight"], "contra": [], "compound": False, "load_type": "time", "level": "beginner"},
    {"id": "jumping_jacks", "name": "Jumping jacks", "pattern": "cardio", "equipment": ["bodyweight"], "contra": ["ankle", "knee"], "compound": False, "load_type": "time", "level": "beginner"},
    {"id": "burpee", "name": "Burpee", "pattern": "cardio", "equipment": ["bodyweight"], "contra": ["wrist", "knee"], "compound": True, "load_type": "time", "level": "intermediate"},
]

REGIONS = ["knee", "shoulder", "lower_back", "wrist", "ankle", "neck", "hip"]
EQUIPMENT = ["bodyweight", "dumbbells", "barbell", "kettlebell", "bands", "pullup_bar", "machines"]
LEVELS = ["beginner", "intermediate", "advanced"]
GOALS = ["strength", "fat_loss", "endurance"]
PAIN_TEXT = ("You reported pain. We changed the exercise and lowered the load. If the pain is sharp, "
             "in a joint, or still there at your next session, stop training that area and see a doctor "
             "or physiotherapist. This app does not diagnose injuries.")


class FitnessCoach:
    def __init__(self):
        self.llm = ChatOllama(model="qwen3", temperature=0, reasoning=False, num_predict=2000)
        self.mode = "onboarding"
        self.profile = None
        self.plan = None
        self.feedbacks = []
        self.history = []
        self.last_feedback = None
        self.last_changed = []
        self.load_state()

    # ------------------------------------------------------------------ state
    def load_state(self):
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            self.profile = data["profile"]
            self.plan = data["plan"]
            self.feedbacks = data["feedbacks"]
            self.history = data["history"]
            if self.plan is not None:
                self.mode = "menu"
            elif self.profile is not None:
                self.mode = "plan"

    def save_state(self):
        os.makedirs("data", exist_ok=True)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({"profile": self.profile, "plan": self.plan, "feedbacks": self.feedbacks,
                       "history": self.history}, f, indent=2)

    # ------------------------------------------------------------------- main
    def run(self):
        print("=== Adaptive Fitness Coach (baseline) ===")
        while True:
            if self.mode == "onboarding":
                print("\nLet's set up your profile.")
                answers = {}
                answers["age"] = input("How old are you? ")
                answers["fitness_level"] = input("What is your fitness level (beginner, intermediate, advanced)? ")
                answers["goal"] = input("What is your goal (strength, fat loss, endurance)? ")
                answers["days"] = input("How many days per week can you train? ")
                answers["equipment"] = input("What equipment do you have? ")
                answers["injuries"] = input("Do you have any injuries or limitations? ")
                profile = None
                error = ""
                for attempt in range(3):
                    prompt = ("You are a fitness coach assistant. Answer ONLY with a JSON object, no other text.\n"
                              "Turn the user's onboarding answers into this JSON: "
                              '{"age": int, "fitness_level": "beginner|intermediate|advanced", '
                              '"goal": "strength|fat_loss|endurance", "days_per_week": int, '
                              '"equipment": [list of: bodyweight, dumbbells, barbell, kettlebell, bands, pullup_bar, machines], '
                              '"injuries": [{"region": "knee|shoulder|lower_back|wrist|ankle|neck|hip", "note": str}], '
                              '"injury_notes": [str]}\n'
                              "Answers: " + json.dumps(answers) + "\n" + error)
                    try:
                        text = self.llm.invoke(prompt).content
                        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
                        age = int(data["age"])
                        if age < 14 or age > 90:
                            raise ValueError("age must be 14-90")
                        if data["fitness_level"] not in LEVELS:
                            raise ValueError("fitness_level must be one of " + str(LEVELS))
                        if data["goal"] not in GOALS:
                            raise ValueError("goal must be one of " + str(GOALS))
                        days = int(data["days_per_week"])
                        if days < 1 or days > 7:
                            raise ValueError("days_per_week must be 1-7")
                        equipment = [e for e in data.get("equipment", []) if e in EQUIPMENT]
                        if "bodyweight" not in equipment:
                            equipment.append("bodyweight")
                        injuries = []
                        notes = list(data.get("injury_notes", []))
                        for inj in data.get("injuries", []):
                            if inj.get("region") in REGIONS:
                                injuries.append({"region": inj["region"], "note": inj.get("note", "")})
                            elif inj.get("region"):
                                notes.append(str(inj.get("region")) + " " + str(inj.get("note", "")))
                        profile = {"age": age, "fitness_level": data["fitness_level"], "goal": data["goal"],
                                   "days_per_week": days, "equipment": equipment, "injuries": injuries,
                                   "injury_notes": notes}
                        break
                    except Exception as e:
                        error = "Your last answer was invalid: " + str(e) + ". Fix it."
                if profile is None:
                    print("I could not understand all answers. Please answer each question again.")
                    while True:
                        try:
                            age = int(input("Age (14-90): "))
                            if 14 <= age <= 90:
                                break
                        except ValueError:
                            pass
                    level = ""
                    while level not in LEVELS:
                        level = input("Fitness level " + str(LEVELS) + ": ").strip()
                    goal = ""
                    while goal not in GOALS:
                        goal = input("Goal " + str(GOALS) + ": ").strip()
                    while True:
                        try:
                            days = int(input("Days per week (1-7): "))
                            if 1 <= days <= 7:
                                break
                        except ValueError:
                            pass
                    equipment = [e.strip() for e in input("Equipment, comma separated " + str(EQUIPMENT) + ": ").split(",") if e.strip() in EQUIPMENT]
                    if "bodyweight" not in equipment:
                        equipment.append("bodyweight")
                    injuries = [{"region": r.strip(), "note": ""} for r in input("Injured regions, comma separated " + str(REGIONS) + " (empty for none): ").split(",") if r.strip() in REGIONS]
                    profile = {"age": age, "fitness_level": level, "goal": goal, "days_per_week": days,
                               "equipment": equipment, "injuries": injuries, "injury_notes": []}
                self.profile = profile
                self.save_state()
                print("Profile saved:", json.dumps(self.profile))
                self.mode = "plan"

            elif self.mode == "plan":
                p = self.profile
                minor = p["age"] < 18
                # goal rules (if/else per goal)
                if p["goal"] == "strength":
                    rep_range = (4, 6)
                    sets = 4
                    rest = 150
                    seconds = 30
                    patterns = ["squat", "push", "hinge", "pull", "core"]
                elif p["goal"] == "fat_loss":
                    rep_range = (8, 12)
                    sets = 3
                    rest = 60
                    seconds = 40
                    patterns = ["squat", "push", "pull", "cardio", "core"]
                else:
                    rep_range = (12, 20)
                    sets = 2
                    rest = 45
                    seconds = 60
                    patterns = ["cardio", "squat", "push", "pull", "core"]
                if p["fitness_level"] == "beginner" or minor:
                    max_weekly_sets = 40
                elif p["fitness_level"] == "intermediate":
                    max_weekly_sets = 60
                else:
                    max_weekly_sets = 80
                n_sessions = min(p["days_per_week"], 6)
                if minor:
                    n_sessions = min(n_sessions, 4)
                days_table = {1: [1], 2: [1, 4], 3: [1, 3, 5], 4: [1, 2, 4, 5], 5: [1, 2, 3, 5, 6], 6: [1, 2, 3, 4, 5, 6]}
                days = days_table[n_sessions]
                # allowed pool
                pool = []
                for ex in CATALOG:
                    ok = True
                    for eq in ex["equipment"]:
                        if eq not in p["equipment"]:
                            ok = False
                    for inj in p["injuries"]:
                        if inj["region"] in ex["contra"]:
                            ok = False
                    if LEVELS.index(ex["level"]) > LEVELS.index(p["fitness_level"]):
                        ok = False
                    if minor and ex["level"] == "advanced":
                        ok = False
                    if ok:
                        pool.append(ex)
                pool_ids = [ex["id"] for ex in pool]
                week1 = None
                error = ""
                for attempt in range(3):
                    prompt = ("You are a fitness coach assistant. Answer ONLY with a JSON object, no other text.\n"
                              "Create week 1 of a training plan as JSON: "
                              '{"sessions": [{"focus": str, "exercises": [{"id": str, "sets": int, "reps": int, "load": number, "rest": int}]}]}\n'
                              "Rules: exactly " + str(n_sessions) + " sessions, 3 to 5 exercises per session, "
                              "only use these exercise ids: " + ", ".join(pool_ids) + ". "
                              "Reps between " + str(rep_range[0]) + " and " + str(rep_range[1]) + ", sets between 2 and " + str(sets) + ". "
                              "Load is kg for weights, 0 for bodyweight, seconds for timed exercises. "
                              "Goal: " + p["goal"] + ", level: " + p["fitness_level"] + ".\n" + error)
                    try:
                        text = self.llm.invoke(prompt).content
                        data = json.loads(text[text.find("{"): text.rfind("}") + 1])
                        if len(data["sessions"]) != n_sessions:
                            raise ValueError("there must be exactly " + str(n_sessions) + " sessions")
                        sessions = []
                        for i, s in enumerate(data["sessions"]):
                            exercises = []
                            seen = []
                            for e in s["exercises"]:
                                if e["id"] not in pool_ids:
                                    raise ValueError(e["id"] + " is not an allowed exercise id")
                                if e["id"] in seen:
                                    raise ValueError(e["id"] + " appears twice in one session")
                                seen.append(e["id"])
                                if int(e["reps"]) < rep_range[0] or int(e["reps"]) > rep_range[1]:
                                    raise ValueError("reps out of range for " + e["id"])
                                if int(e["sets"]) < 2 or int(e["sets"]) > sets:
                                    raise ValueError("sets out of range for " + e["id"])
                                lt = [c for c in CATALOG if c["id"] == e["id"]][0]["load_type"]
                                load = float(e.get("load", 0))
                                if lt == "bw":
                                    load = 0
                                elif lt == "time" and load <= 0:
                                    load = seconds
                                elif lt == "kg" and load <= 0:
                                    load = 10
                                rest_s = int(e.get("rest", rest))
                                if rest_s <= 0:
                                    rest_s = rest
                                exercises.append({"id": e["id"], "sets": int(e["sets"]), "reps": int(e["reps"]),
                                                  "load": load, "rest": rest_s})
                            if len(exercises) < 3 or len(exercises) > 5:
                                raise ValueError("each session needs 3 to 5 exercises")
                            sessions.append({"day": days[i], "focus": s.get("focus", "full body"), "status": "planned",
                                             "exercises": exercises})
                        week1 = sessions
                        llm_generated = True
                        break
                    except Exception as e:
                        error = "Your last answer was invalid: " + str(e) + ". Fix it."
                if week1 is None:
                    week1 = []
                    for i in range(n_sessions):
                        exercises = []
                        for pat in patterns:
                            options = [ex for ex in pool if ex["pattern"] == pat]
                            if options and len(exercises) < 4:
                                ex = options[i % len(options)]
                                if ex["load_type"] == "kg":
                                    load = 10
                                elif ex["load_type"] == "time":
                                    load = seconds
                                else:
                                    load = 0
                                exercises.append({"id": ex["id"], "sets": sets, "reps": rep_range[0], "load": load, "rest": rest})
                        week1.append({"day": days[i], "focus": "full body", "status": "planned", "exercises": exercises})
                    llm_generated = False
                weeks = [{"number": 1, "sessions": week1}]
                for w in range(2, 5):
                    week = copy.deepcopy(weeks[-1])
                    week["number"] = w
                    for s in week["sessions"]:
                        for e in s["exercises"]:
                            lt = [c for c in CATALOG if c["id"] == e["id"]][0]["load_type"]
                            if lt == "time":
                                e["load"] = e["load"] + 5
                            elif e["reps"] < rep_range[1]:
                                e["reps"] = e["reps"] + 1
                    weeks.append(week)
                self.plan = {"weeks": weeks, "llm_generated": llm_generated, "held_patterns": {},
                             "last_increase_week": {}, "rep_range": list(rep_range),
                             "max_weekly_sets": max_weekly_sets, "min_weekly_sets": 6, "summary": ""}
                prompt = ("You are a fitness coach assistant. Answer in plain text, at most three sentences.\n"
                          "Explain why this plan fits the user. Profile: " + json.dumps(self.profile) +
                          " Week 1: " + json.dumps(week1))
                try:
                    self.plan["summary"] = self.llm.invoke(prompt).content.strip()
                except Exception:
                    self.plan["summary"] = "This " + p["goal"] + " plan has " + str(n_sessions) + " sessions per week for 4 weeks."
                if p["injury_notes"]:
                    self.plan["summary"] += " Note on your limitations (" + "; ".join(p["injury_notes"]) + "): see a professional if unsure."
                if minor:
                    self.plan["summary"] += " Because you are under 18, the volume is kept low."
                self.save_state()
                self.last_changed = []
                self.mode = "show"

            elif self.mode == "show":
                print("\n" + self.plan["summary"])
                for week in self.plan["weeks"]:
                    print("\nWeek " + str(week["number"]))
                    for s in week["sessions"]:
                        print("  Day " + str(s["day"]) + " (" + s["focus"] + ") [" + s["status"] + "]")
                        for e in s["exercises"]:
                            lt = [c for c in CATALOG if c["id"] == e["id"]][0]["load_type"]
                            mark = "*" if e["id"] in self.last_changed else " "
                            if lt == "kg":
                                load = str(e["load"]) + " kg"
                            elif lt == "time":
                                load = str(int(e["load"])) + " s"
                            else:
                                load = "bodyweight"
                            print("   " + mark + " " + e["id"] + ": " + str(e["sets"]) + " x " + str(e["reps"]) + ", " + load + ", rest " + str(e["rest"]) + " s")
                self.mode = "menu"

            elif self.mode == "menu":
                print("\n1) Show plan  2) Give feedback  3) Undo last change  4) Show history  5) Redo onboarding  6) Quit")
                choice = input("> ").strip()
                if choice == "1":
                    self.mode = "show"
                elif choice == "2":
                    self.mode = "feedback"
                elif choice == "3":
                    if self.history:
                        entry = self.history.pop()
                        self.plan = entry["snapshot"]
                        self.save_state()
                        print("Undone: " + "; ".join(entry["changes"]))
                    else:
                        print("Nothing to undo.")
                elif choice == "4":
                    if not self.history:
                        print("No changes yet.")
                    for i, entry in enumerate(self.history):
                        print(str(i + 1) + ". " + "; ".join(entry["changes"]))
                elif choice == "5":
                    self.profile = None
                    self.plan = None
                    self.history = []
                    self.feedbacks = []
                    self.mode = "onboarding"
                elif choice == "6":
                    print("Bye.")
                    return
                else:
                    print("Unknown choice.")

            elif self.mode == "feedback":
                planned = []
                for week in self.plan["weeks"]:
                    for s in week["sessions"]:
                        if s["status"] == "planned":
                            planned.append((week["number"], s))
                if not planned:
                    print("All sessions are done. Choose 'Redo onboarding' for a new plan.")
                    self.mode = "menu"
                    continue
                for i, (wn, s) in enumerate(planned[:7]):
                    print(str(i + 1) + ") Week " + str(wn) + " day " + str(s["day"]) + " (" + s["focus"] + ")")
                pick = input("Which session did you do? [1] ").strip()
                try:
                    index = int(pick) - 1 if pick else 0
                    if index < 0 or index >= min(7, len(planned)):
                        index = 0
                except ValueError:
                    index = 0
                week_number, session = planned[index]
                text = input("How did it go? Describe it in your own words: ")
                fb = None
                error = ""
                for attempt in range(3):
                    prompt = ("You are a fitness coach assistant. Answer ONLY with a JSON object, no other text.\n"
                              "Turn the user's workout feedback into this JSON: "
                              '{"rpe": int 1-10, "pain": bool, "pain_region": "knee|shoulder|lower_back|wrist|ankle|neck|hip" or null, '
                              '"all_sets_done": bool, "completed_sets": int or null, "missed_sessions": int}\n'
                              "Feedback: " + text + "\n" + error)
                    try:
                        out = self.llm.invoke(prompt).content
                        data = json.loads(out[out.find("{"): out.rfind("}") + 1])
                        rpe = int(data["rpe"])
                        if rpe < 1 or rpe > 10:
                            raise ValueError("rpe must be 1-10")
                        if data["pain"] and data.get("pain_region") not in REGIONS:
                            raise ValueError("pain_region must be one of " + str(REGIONS))
                        if int(data.get("missed_sessions", 0)) < 0:
                            raise ValueError("missed_sessions must be >= 0")
                        fb = {"rpe": rpe, "pain": bool(data["pain"]), "pain_region": data.get("pain_region") if data["pain"] else None,
                              "all_sets_done": bool(data["all_sets_done"]), "completed_sets": data.get("completed_sets"),
                              "missed_sessions": int(data.get("missed_sessions", 0))}
                        break
                    except Exception as e:
                        error = "Your last answer was invalid: " + str(e) + ". Fix it."
                if fb is None:
                    print("I could not understand that. Four short questions:")
                    while True:
                        try:
                            rpe = int(input("How hard was it (1-10)? "))
                            if 1 <= rpe <= 10:
                                break
                        except ValueError:
                            pass
                    pain = input("Did anything hurt (y/n)? ").strip().lower().startswith("y")
                    region = None
                    while pain and region not in REGIONS:
                        region = input("Which region " + str(REGIONS) + "? ").strip()
                    all_done = input("Did you complete all sets (y/n)? ").strip().lower().startswith("y")
                    completed = None
                    if not all_done:
                        try:
                            completed = int(input("How many sets did you complete? "))
                        except ValueError:
                            completed = 0
                    try:
                        missed = max(0, int(input("How many planned sessions did you miss? ")))
                    except ValueError:
                        missed = 0
                    fb = {"rpe": rpe, "pain": pain, "pain_region": region, "all_sets_done": all_done,
                          "completed_sets": completed, "missed_sessions": missed}
                fb["week"] = week_number
                fb["day"] = session["day"]
                self.last_feedback = fb
                self.mode = "adapt"

            elif self.mode == "adapt":
                fb = self.last_feedback
                week_number = fb["week"]
                week = [w for w in self.plan["weeks"] if w["number"] == week_number][0]
                session = [s for s in week["sessions"] if s["day"] == fb["day"] and s["status"] == "planned"][0]
                snapshot = copy.deepcopy(self.plan)
                previous = self.feedbacks[-1] if self.feedbacks else None
                self.feedbacks.append(fb)
                session["status"] = "done"
                changes = []
                messages = []
                changed = []
                no_increase = False
                see_professional = False
                rep_range = self.plan["rep_range"]
                minor = self.profile["age"] < 18
                try:
                    # ---------------- pain (safety)
                    if fb["pain"]:
                        region = fb["pain_region"]
                        offending = []
                        for e in session["exercises"]:
                            if region in [c for c in CATALOG if c["id"] == e["id"]][0]["contra"]:
                                offending.append(e["id"])
                        if offending:
                            for ex_id in offending:
                                old = [c for c in CATALOG if c["id"] == ex_id][0]
                                replacement = None
                                for c in CATALOG:
                                    ok = c["pattern"] == old["pattern"] and region not in c["contra"]
                                    if c["id"] in [x["id"] for x in session["exercises"]]:
                                        ok = False
                                    for eq in c["equipment"]:
                                        if eq not in self.profile["equipment"]:
                                            ok = False
                                    for inj in self.profile["injuries"]:
                                        if inj["region"] in c["contra"]:
                                            ok = False
                                    if LEVELS.index(c["level"]) > LEVELS.index(self.profile["fitness_level"]):
                                        ok = False
                                    if minor and c["level"] == "advanced":
                                        ok = False
                                    if ok:
                                        replacement = c
                                        break
                                for w in self.plan["weeks"]:
                                    for s in w["sessions"]:
                                        if s["status"] != "planned":
                                            continue
                                        for e in list(s["exercises"]):
                                            if e["id"] != ex_id:
                                                continue
                                            if replacement is None:
                                                s["exercises"].remove(e)
                                                continue
                                            if replacement["load_type"] == "kg" and old["load_type"] == "kg":
                                                e["load"] = round(e["load"] * 0.7 * 2) / 2
                                            elif replacement["load_type"] == "kg":
                                                e["load"] = 10
                                                e["reps"] = rep_range[0]
                                            elif replacement["load_type"] == "time":
                                                e["load"] = 30
                                                e["reps"] = rep_range[0]
                                            else:
                                                e["load"] = 0
                                                e["reps"] = rep_range[0]
                                            e["id"] = replacement["id"]
                                if replacement is None:
                                    changes.append("removed " + ex_id + " (no safe alternative)")
                                else:
                                    changes.append("swapped " + ex_id + " for " + replacement["id"] + " because of " + region + " pain")
                                    changed.append(replacement["id"])
                                self.plan["held_patterns"][old["pattern"]] = week_number + 1
                        else:
                            for e in session["exercises"]:
                                lt = [c for c in CATALOG if c["id"] == e["id"]][0]["load_type"]
                                for w in self.plan["weeks"]:
                                    for s in w["sessions"]:
                                        if s["status"] != "planned":
                                            continue
                                        for o in s["exercises"]:
                                            if o["id"] != e["id"]:
                                                continue
                                            if lt == "kg":
                                                o["load"] = round(o["load"] * 0.9 * 2) / 2
                                            elif lt == "time":
                                                o["load"] = max(5, round(o["load"] * 0.9 / 5) * 5)
                                            else:
                                                o["reps"] = max(1, o["reps"] - 2)
                                changes.append("lowered " + e["id"] + " by one step because of " + region + " pain")
                                changed.append(e["id"])
                        no_increase = True
                        see_professional = True
                    # ---------------- missed sessions (schedule)
                    if fb["missed_sessions"] > 0:
                        before = [s for s in week["sessions"] if s["status"] == "planned" and s["day"] < session["day"]]
                        missed = before[-fb["missed_sessions"]:]
                        for m in missed:
                            m["status"] = "missed"
                            used = [s["day"] for s in week["sessions"] if s["status"] in ("planned", "done")]
                            free = [d for d in range(session["day"] + 1, 8) if d not in used]
                            if free and len(used) + 1 <= 6:
                                moved = copy.deepcopy(m)
                                moved["day"] = free[0]
                                moved["status"] = "planned"
                                week["sessions"].append(moved)
                                changes.append("moved the missed day " + str(m["day"]) + " session to day " + str(free[0]))
                            else:
                                m["status"] = "dropped"
                                no_increase = True
                                changes.append("dropped the missed day " + str(m["day"]) + " session (no free day)")
                        week["sessions"].sort(key=lambda s: s["day"])
                    # ---------------- load
                    rpe = fb["rpe"]
                    if fb["pain"]:
                        category = "SAFETY"
                    elif rpe >= 9 or (rpe >= 8 and previous is not None and previous["rpe"] >= 8):
                        category = "TOO_HARD_SEVERE"
                    elif rpe == 8:
                        category = "TOO_HARD"
                    elif not fb["all_sets_done"] and rpe == 7:
                        category = "TOO_HARD"
                    elif not fb["all_sets_done"] and rpe <= 6:
                        category = "INCOMPLETE_LOW"
                    elif rpe >= 5:
                        category = "ON_TARGET"
                    else:
                        category = "TOO_EASY"
                    weekly_sets = sum(e["sets"] for s in week["sessions"] for e in s["exercises"] if s["status"] in ("planned", "done"))
                    if category == "TOO_HARD_SEVERE":
                        for e in session["exercises"]:
                            lt = [c for c in CATALOG if c["id"] == e["id"]][0]["load_type"]
                            if weekly_sets - 1 < self.plan["min_weekly_sets"]:
                                messages.append("Kept " + e["id"] + ": the weekly minimum volume is reached.")
                                continue
                            for w in self.plan["weeks"]:
                                for s in w["sessions"]:
                                    if s["status"] != "planned":
                                        continue
                                    for o in s["exercises"]:
                                        if o["id"] != e["id"]:
                                            continue
                                        if o["sets"] > 2:
                                            o["sets"] = o["sets"] - 1
                                        elif lt == "kg":
                                            o["load"] = round(o["load"] * 0.9 * 2) / 2
                                        elif lt == "time":
                                            o["load"] = max(5, round(o["load"] * 0.9 / 5) * 5)
                                        else:
                                            o["reps"] = max(1, o["reps"] - 2)
                            weekly_sets = weekly_sets - 1
                            changes.append("deload: " + e["id"] + " -1 set (or -1 load step at 2 sets)")
                            changed.append(e["id"])
                    elif category == "TOO_HARD":
                        hardest = None
                        for e in session["exercises"]:
                            if hardest is None or e["sets"] * e["reps"] > hardest["sets"] * hardest["reps"]:
                                hardest = e
                        if hardest is not None:
                            lt = [c for c in CATALOG if c["id"] == hardest["id"]][0]["load_type"]
                            if weekly_sets - 1 < self.plan["min_weekly_sets"]:
                                messages.append("Kept " + hardest["id"] + ": the weekly minimum volume is reached.")
                            else:
                                for w in self.plan["weeks"]:
                                    for s in w["sessions"]:
                                        if s["status"] != "planned":
                                            continue
                                        for o in s["exercises"]:
                                            if o["id"] != hardest["id"]:
                                                continue
                                            if o["sets"] > 2:
                                                o["sets"] = o["sets"] - 1
                                            elif lt == "kg":
                                                o["load"] = round(o["load"] * 0.9 * 2) / 2
                                            elif lt == "time":
                                                o["load"] = max(5, round(o["load"] * 0.9 / 5) * 5)
                                            else:
                                                o["reps"] = max(1, o["reps"] - 2)
                                changes.append(hardest["id"] + " -1 set (or -1 load step at 2 sets) because it was too hard")
                                changed.append(hardest["id"])
                    elif category == "INCOMPLETE_LOW":
                        messages.append("Plan unchanged. If time is the problem, choose 'Redo onboarding' with fewer days per week.")
                    elif category == "TOO_EASY":
                        for e in session["exercises"]:
                            c = [c for c in CATALOG if c["id"] == e["id"]][0]
                            if no_increase:
                                messages.append("No increase for " + e["id"] + " this cycle.")
                                continue
                            if self.plan["held_patterns"].get(c["pattern"], 0) >= week_number:
                                messages.append(e["id"] + " is held after a pain event.")
                                continue
                            if self.plan["last_increase_week"].get(e["id"]) == week_number:
                                messages.append(e["id"] + " was already increased this week.")
                                continue
                            if not fb["all_sets_done"]:
                                continue
                            adds_set = c["load_type"] == "bw" and e["reps"] >= rep_range[1]
                            if adds_set and weekly_sets + 1 > self.plan["max_weekly_sets"]:
                                messages.append(e["id"] + ": the weekly maximum volume is reached.")
                                continue
                            for w in self.plan["weeks"]:
                                for s in w["sessions"]:
                                    if s["status"] != "planned":
                                        continue
                                    for o in s["exercises"]:
                                        if o["id"] != e["id"]:
                                            continue
                                        if c["load_type"] == "kg":
                                            if minor or not (c["compound"] and c["pattern"] in ("squat", "hinge")):
                                                new = round(o["load"] * 1.025 * 2) / 2
                                            else:
                                                new = round(o["load"] * 1.05 * 2) / 2
                                            if new == o["load"] or new > o["load"] * 1.10:
                                                if o["reps"] < rep_range[1]:
                                                    o["reps"] = o["reps"] + 1
                                            else:
                                                o["load"] = new
                                        elif c["load_type"] == "time":
                                            o["load"] = round(o["load"] * 1.1 / 5) * 5
                                        else:
                                            if o["reps"] < rep_range[1]:
                                                o["reps"] = o["reps"] + 1
                                            else:
                                                o["sets"] = o["sets"] + 1
                            if adds_set:
                                weekly_sets = weekly_sets + 1
                            self.plan["last_increase_week"][e["id"]] = week_number
                            changes.append(e["id"] + " +1 load step because it was too easy")
                            changed.append(e["id"])
                except Exception as e:
                    self.plan = snapshot
                    self.save_state()
                    print("Sorry, the plan could not be adapted (" + str(e) + "). The plan was not changed; your feedback is saved.")
                    self.mode = "menu"
                    continue
                if changes:
                    self.history.append({"snapshot": snapshot, "changes": changes})
                self.save_state()
                if changes:
                    prompt = ("You are a fitness coach assistant. Answer in plain text, exactly two sentences.\n"
                              "Explain to the user what changed in their plan and why: " + "; ".join(changes))
                    try:
                        explanation = self.llm.invoke(prompt).content.strip()
                    except Exception:
                        explanation = "We changed your plan: " + "; ".join(changes) + "."
                else:
                    explanation = "Your plan stays the same; keep going."
                self.last_changed = changed
                print("\n" + explanation)
                for m in messages:
                    print("- " + m)
                if see_professional:
                    print("\n" + PAIN_TEXT)
                self.mode = "show"


if __name__ == "__main__":
    FitnessCoach().run()
