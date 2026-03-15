#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║              D E M O N S  /  Б Е С Ы                        ║
║     A Text Adventure in Provincial Nihilism                  ║
║     After Fyodor Mikhailovich Dostoevsky, 1872               ║
╚══════════════════════════════════════════════════════════════╝
"""

import sys
import time
import random
import select
import termios
import tty
import json
import os
from pathlib import Path

# ─── CONSTANTS ───────────────────────────────────────────────

CLEAR = "\033[2J\033[H"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
BLINK = "\033[5m"
REVERSE = "\033[7m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
WHITE = "\033[37m"
MAGENTA = "\033[35m"


class GameOverException(Exception):
    """Raised when a fatal decision ends the run."""
    pass


# ─── TEXT SKIP SYSTEM ───────────────────────────────────────
# Press ENTER during scrolling text to display all remaining
# text in the current scene instantly. Resets at each choice
# or "Press ENTER to continue" prompt.

_skip_text = False

# ─── GAME STATE ──────────────────────────────────────────────

state = {
    "ennui": 40,
    "revolutionary_fervor": 0,
    "soul": 50,
    "notoriety": 30,
    "tea_consumed": 0,
    "decisions": [],
    # Relationship trackers
    "shatov_bond": 0,
    "pyotr_entangled": 0,
    "marya_bond": 0,
    "stepan_bond": 0,
    "liza_bond": 0,
    # Plot flags
    "warned_shatov": False,
    "took_fedkas_offer": False,
    "gave_money_to_lebyadkin": False,
    "confessed_to_tikhon": False,
}


def clear_screen():
    print(CLEAR, end="")


def _is_interactive():
    """Check if stdin is a real terminal (not piped input)."""
    try:
        return sys.stdin.isatty()
    except AttributeError:
        return False


def _reset_skip():
    """Reset skip mode and flush any buffered keypresses."""
    global _skip_text
    _skip_text = False
    if _is_interactive():
        try:
            termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
        except (termios.error, ValueError, OSError):
            pass


def slow_print(text, delay=0.018):
    """Print text character-by-character. Press ENTER to skip to instant."""
    global _skip_text

    if _skip_text:
        print(text)
        return

    interactive = _is_interactive()
    fd = None
    old_settings = None

    if interactive:
        try:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            tty.setcbreak(fd)
        except (termios.error, ValueError, OSError):
            interactive = False

    try:
        for i, char in enumerate(text):
            sys.stdout.write(char)
            sys.stdout.flush()
            if interactive:
                if select.select([sys.stdin], [], [], delay)[0]:
                    sys.stdin.read(1)  # consume the keypress
                    sys.stdout.write(text[i + 1:])
                    sys.stdout.flush()
                    _skip_text = True
                    break
            else:
                time.sleep(delay)
    finally:
        if interactive and old_settings is not None:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    print()


def dramatic_pause(seconds=1.5):
    """Pause for dramatic effect. Skippable with ENTER."""
    global _skip_text

    if _skip_text:
        return

    interactive = _is_interactive()
    fd = None
    old_settings = None

    if interactive:
        try:
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            tty.setcbreak(fd)
        except (termios.error, ValueError, OSError):
            interactive = False

    try:
        if interactive:
            if select.select([sys.stdin], [], [], seconds)[0]:
                sys.stdin.read(1)
                _skip_text = True
        else:
            time.sleep(seconds)
    finally:
        if interactive and old_settings is not None:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def press_enter():
    _reset_skip()
    input(f"\n{DIM}  [ Press ENTER to continue ]{RESET}")


def get_choice(options):
    _reset_skip()
    print()
    for i, option in enumerate(options, 1):
        print(f"  {YELLOW}{i}{RESET}) {option}")
    print()
    print(f"  {DIM}[S] Save game{RESET}")
    print()
    while True:
        try:
            raw = input(f"  {GREEN}>{RESET} ").strip()
            if raw.lower() == "s":
                save_to_slot()
                continue
            choice = int(raw)
            if 1 <= choice <= len(options):
                return choice
        except (ValueError, EOFError):
            pass
        print(f"  {RED}Invalid choice. Try again.{RESET}")


def show_status():
    bar_len = 20
    ennui_bars = min(int(state["ennui"] / 100 * bar_len), bar_len)
    fervor_bars = min(int(state["revolutionary_fervor"] / 100 * bar_len), bar_len)
    soul_bars = min(int(state["soul"] / 100 * bar_len), bar_len)
    notoriety_bars = min(int(state["notoriety"] / 100 * bar_len), bar_len)

    ennui_color = GREEN if state["ennui"] < 40 else YELLOW if state["ennui"] < 70 else RED
    soul_color = RED if state["soul"] < 30 else YELLOW if state["soul"] < 50 else GREEN
    fervor_color = GREEN if state["revolutionary_fervor"] < 40 else YELLOW if state["revolutionary_fervor"] < 70 else RED

    tea_display = min(state["tea_consumed"], 10)
    print(f"""
  {DIM}╔══════════════════════════════════════════════════╗
  ║{RESET} {BOLD}СОСТОЯНИЕ ДУШИ{RESET}  {DIM}(State of the Soul){RESET}         {DIM}║
  ╠══════════════════════════════════════════════════╣{RESET}
  {DIM}║{RESET} Ennui:       {ennui_color}[{"█" * ennui_bars}{"░" * (bar_len - ennui_bars)}]{RESET} {state["ennui"]:>3}%  {DIM}║{RESET}
  {DIM}║{RESET} Rev. Fervor: {fervor_color}[{"█" * fervor_bars}{"░" * (bar_len - fervor_bars)}]{RESET} {state["revolutionary_fervor"]:>3}%  {DIM}║{RESET}
  {DIM}║{RESET} Soul:        {soul_color}[{"█" * soul_bars}{"░" * (bar_len - soul_bars)}]{RESET} {state["soul"]:>3}%  {DIM}║{RESET}
  {DIM}║{RESET} Notoriety:   {CYAN}[{"█" * notoriety_bars}{"░" * (bar_len - notoriety_bars)}]{RESET} {state["notoriety"]:>3}%  {DIM}║{RESET}
  {DIM}║{RESET} Tea:         {"🍵" * tea_display}{" " * (10 - tea_display)}              {DIM}║{RESET}
  {DIM}╚══════════════════════════════════════════════════╝{RESET}
""")


def clamp_stats():
    for key in ["ennui", "revolutionary_fervor", "soul", "notoriety"]:
        state[key] = max(0, min(100, state[key]))
    # Track peak marya_bond (she dies mid-game, bond resets to 0)
    state["marya_bond_peak"] = max(state.get("marya_bond_peak", 0), state["marya_bond"])


# ─── GAME OVER ───────────────────────────────────────────────

def game_over(death_lines):
    """Fatal decision — show death scene and end the run."""
    print()
    for line in death_lines:
        slow_print(line)
    print()
    slow_print(f"  {RED}{BOLD}  ★ ☆ ☆ ☆ ☆  GAME OVER  ★ ☆ ☆ ☆ ☆{RESET}")
    print()
    slow_print(f"  {DIM}The silk cord was not needed after all.{RESET}")
    slow_print(f"  {DIM}Load a save to try again.{RESET}")
    print()
    press_enter()
    raise GameOverException()


# ─── SAVE SYSTEM ──────────────────────────────────────────────

SAVE_FILE = Path.home() / ".demons_save.json"

# Tracks current chapter index so save_to_slot() knows where we are
_current_chapter_index = 0


def _load_save_file():
    """Load the full save file. Returns dict or empty structure."""
    try:
        with open(SAVE_FILE, "r") as f:
            data = json.load(f)
            # Migrate old format (flat dict with "chapter_index") to new format
            if "chapter_index" in data and "auto" not in data:
                return {"auto": data, "slot_1": None, "slot_2": None, "slot_3": None}
            return data
    except (OSError, json.JSONDecodeError):
        return {"auto": None, "slot_1": None, "slot_2": None, "slot_3": None}


def _write_save_file(data):
    """Write the full save file."""
    try:
        with open(SAVE_FILE, "w") as f:
            json.dump(data, f)
    except OSError:
        pass


def save_game(chapter_index):
    """Auto-save current state and chapter index."""
    data = _load_save_file()
    data["auto"] = {"chapter_index": chapter_index, "state": dict(state)}
    _write_save_file(data)


def save_to_slot():
    """Show save slot menu, let player pick a slot."""
    global _current_chapter_index
    data = _load_save_file()
    print()
    print(f"  {BOLD}SAVE GAME{RESET}")
    print(f"  {DIM}{'─' * 40}{RESET}")
    for i in range(1, 4):
        slot = data.get(f"slot_{i}")
        if slot:
            label = slot.get("label", "Unknown")
            print(f"  {YELLOW}{i}{RESET}) {label}")
        else:
            print(f"  {YELLOW}{i}{RESET}) {DIM}(empty){RESET}")
    print(f"  {YELLOW}0{RESET}) Cancel")
    print()
    while True:
        try:
            raw = input(f"  {GREEN}Save to slot: {RESET}").strip()
            choice = int(raw)
            if choice == 0:
                print(f"  {DIM}Cancelled.{RESET}")
                return
            if 1 <= choice <= 3:
                # Build label from current chapter
                # CHAPTERS isn't defined yet at module level when this runs,
                # but it will be by the time the game is playing
                try:
                    ch_name = CHAPTERS[_current_chapter_index][0]
                except (NameError, IndexError):
                    ch_name = "Unknown"
                data[f"slot_{choice}"] = {
                    "chapter_index": _current_chapter_index,
                    "state": dict(state),
                    "label": f"Ch.{_current_chapter_index + 1} {ch_name}",
                }
                _write_save_file(data)
                print(f"  {GREEN}Saved to slot {choice}.{RESET}")
                return
        except (ValueError, EOFError):
            pass
        print(f"  {RED}Enter 1-3 or 0 to cancel.{RESET}")


def load_game():
    """Load auto-save. Returns dict with 'chapter_index' and 'state', or None."""
    data = _load_save_file()
    return data.get("auto")


def load_slot(slot_num):
    """Load a specific save slot. Returns dict or None."""
    data = _load_save_file()
    return data.get(f"slot_{slot_num}")


def delete_save():
    """Remove auto-save on game completion (keep slots)."""
    data = _load_save_file()
    data["auto"] = None
    _write_save_file(data)


# ═══════════════════════════════════════════════════════════════
#  TITLE SCREEN
# ═══════════════════════════════════════════════════════════════

def title_screen():
    """Returns 'continue' if player chooses to resume a save, else 'new'."""
    clear_screen()
    print(f"""{RED}


    ██████╗ ███████╗███╗   ███╗ ██████╗ ███╗   ██╗███████╗
    ██╔══██╗██╔════╝████╗ ████║██╔═══██╗████╗  ██║██╔════╝
    ██║  ██║█████╗  ██╔████╔██║██║   ██║██╔██╗ ██║███████╗
    ██║  ██║██╔══╝  ██║╚██╔╝██║██║   ██║██║╚██╗██║╚════██║
    ██████╔╝███████╗██║ ╚═╝ ██║╚██████╔╝██║ ╚████║███████║
    ╚═════╝ ╚══════╝╚═╝     ╚═╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝
{RESET}
                   {YELLOW}     Б  Е  С  Ы{RESET}
                   {DIM}   The Possessed{RESET}

{DIM}          ┌────────────────────────────────────┐
          │                                    │
          │       ╬         ╬         ╬        │
          │       ║         ║         ║        │
          │      ═╬═       ═╬═       ═╬═       │
          │       ║         ║         ║        │
          │       ║         ║         ║        │
          │                                    │
          │    A Provincial Town, 186-         │
          │    Translated by Constance Garnett  │
          │                                    │
          └────────────────────────────────────┘{RESET}

{DIM}   "And there was there one herd of many swine feeding on
    the mountain; and they besought him that he would suffer
    them to enter into them. And he suffered them."
                                           — Luke viii. 32-36

   You are Nikolai Vsevolodovich Stavrogin:
   aristocrat, officer, husband, destroyer.
   Everyone you have ever met is waiting for you
   to tell them what their life means.

   You have no answer.

   Rated Д for Достоевский.{RESET}

   {DIM}(c) 186- The Provincial Chronicle Press{RESET}
""")

    save_data = _load_save_file()
    auto = save_data.get("auto")
    slots = [save_data.get(f"slot_{i}") for i in range(1, 4)]
    has_saves = auto or any(slots)

    if has_saves:
        print(f"  {BOLD}SAVED GAMES{RESET}")
        print(f"  {DIM}{'─' * 40}{RESET}")
        if auto:
            try:
                ch_name = CHAPTERS[auto["chapter_index"]][0]
            except (IndexError, KeyError):
                ch_name = "Unknown"
            print(f"  {YELLOW}C{RESET}) Continue — Ch.{auto['chapter_index'] + 1} {ch_name}")
        for i in range(3):
            if slots[i]:
                label = slots[i].get("label", "Unknown")
                print(f"  {YELLOW}{i + 1}{RESET}) Load {label}")
            else:
                print(f"  {DIM}  {i + 1}) (empty slot){RESET}")
        print(f"  {YELLOW}N{RESET}) New Game")
        print()
        _reset_skip()
        while True:
            raw = input(f"  {GREEN}>{RESET} ").strip().lower()
            if raw == "c" and auto:
                return "load:auto"
            if raw in ("1", "2", "3") and slots[int(raw) - 1]:
                return f"load:{raw}"
            if raw == "n":
                return "new"
            if raw in ("1", "2", "3") and not slots[int(raw) - 1]:
                print(f"  {DIM}That slot is empty.{RESET}")
            else:
                print(f"  {RED}Enter C, 1-3, or N.{RESET}")
    else:
        press_enter()

    return "new"


# ═══════════════════════════════════════════════════════════════
#  PART I: THE RETURN
# ═══════════════════════════════════════════════════════════════

def chapter_1_return():
    """Part I, Ch.1-2: Stavrogin returns to the provincial town."""
    clear_screen()
    print(f"""{CYAN}
                         .              *        .          *
           *       .          .                        .
      .                  _____________________________
                        /                             \\        {WHITE}Autumn, 186-{CYAN}
           .           /  Skvoreshniki                 \\       {WHITE}Estate of Varvara{CYAN}
     *                /   Estate                        \\      {WHITE}Petrovna Stavrogina{CYAN}
                     /                                   \\
       _.---._      |  _____    _____    _____    _____   |
      / ,---. \\     | |     |  |     |  |     |  |     |  |
     / /     \\ \\    | | [ ] |  | [ ] |  | [ ] |  | [ ] |  |
    | |       | |   | |     |  |     |  |     |  |     |  |
    | |  {WHITE}CHAPEL{CYAN} | |   | |_____|  |_____|  |_____|  |_____|  |
    | |       | |   |   __     ___     ___     ___        |
     \\ \\  +  / /    |  |  |   |   |   |   |   |   |       |
      \\ '---' /     |  |  |   |   |   |   |   |   |       |
       '-----'      |  |__|   |___|   |___|   |___|       |
    ______|_______   |____________ __ _______________ _____|
   /       \\      \\  |            |  |               |
  / {DIM}birches{CYAN}  \\      \\_|____________|  |_______________|
  \\ {DIM}turning{CYAN}  /      /            ____
   \\ {DIM}gold{CYAN}   /     _/         ___/    \\___        ___/
    \\______/     /      ____/    {DIM}gate{CYAN}    \\______/
  ~~~~~~~~~~~~~~/ _____/ .  .  .  .  .  . \\_________
  .:. .:. .:. .:/.:. .:. .:. .:. .:. .:. .:. .:. .:\\
               /    {DIM}A carriage approaches...{CYAN}          \\{RESET}
""")

    slow_print(f"  {BOLD}PART I")
    slow_print(f"  CHAPTER I: INTRODUCTORY — THE RETURN{RESET}")
    print()
    slow_print("  Four years abroad. Perhaps five. It ceased to matter somewhere")
    slow_print("  around Naples, or was it Geneva? You have been everywhere and")
    slow_print("  nowhere. You have studied philosophy in German universities,")
    slow_print("  fought two duels, been degraded from officer's rank, married")
    slow_print("  a lame beggar-woman on a bet — or perhaps out of some")
    slow_print("  monstrous curiosity about your own capacity for abasement.")
    print()
    slow_print("  Now: the provincial town. The old estate at Skvoreshniki.")
    slow_print("  Your mother Varvara Petrovna waits in the drawing room.")
    slow_print("  She has been keeping your old tutor, Stepan Trofimovich")
    slow_print("  Verkhovensky, like a lapdog in a waistcoat for twenty years.")
    slow_print("  He is a liberal, a man of the forties, who has not published")
    slow_print("  anything in two decades but still gestures as though ideas")
    slow_print("  are leaving his fingertips.")
    print()
    slow_print("  The town remembers you. Before you left, you pulled a")
    slow_print("  respected old man named Gaganov across the room by his nose")
    slow_print("  — in front of the entire club. You bit the Governor's ear")
    slow_print("  at a birthday party. You kissed another man's wife in public.")
    slow_print("  No one could explain these acts. Neither could you.")
    print()
    slow_print(f"  {DIM}The carriage halts. The door opens. Russia receives you back.{RESET}")
    print()
    slow_print("  The house smells of beeswax and camphor.")
    slow_print("  A servant you do not recognize takes your coat.")
    slow_print("  Another — old Alexei, who carried you as a child —")
    slow_print("  stares at you from the passage with an expression")
    slow_print("  that contains twenty years of gossip, fear, and hope.")
    slow_print("  He crosses himself. You pretend not to see.")
    print()
    slow_print("  Through the open door of the drawing room, you see them:")
    slow_print("  your mother, upright as a bayonet in her black silk,")
    slow_print("  and Stepan Trofimovich beside her, already preparing")
    slow_print("  to produce the emotion the moment requires.")
    slow_print("  He has been rehearsing this scene for months.")
    slow_print("  Your mother has been rehearsing it for years.")
    print()

    slow_print("  How do you present yourself?")

    choice = get_choice([
        "Kiss your mother's hand. Be the prodigal son returned.",
        "Walk past everyone in silence. Close the door to your wing.",
        "Greet old Stepan Trofimovich first. He will weep; let him.",
        "Announce that you intend to make public your marriage to the cripple.",
    ])

    if choice == 1:
        state["notoriety"] += 5
        state["ennui"] += 5
        state["stepan_bond"] += 0
        state["decisions"].append("dutiful_return")
        slow_print('\n  "Maman." You kiss her hand. She trembles.')
        slow_print("  Varvara Petrovna's eyes fill with tears she will")
        slow_print("  never acknowledge. Twenty servants watch in silence.")
        slow_print("  You note that the wallpaper has been changed.")
        slow_print("  You note that Stepan Trofimovich has grown fatter.")
        slow_print("  You note that you feel precisely nothing.")
        slow_print(f"  {DIM}The performance is flawless. That is the horror of it.{RESET}")
    elif choice == 2:
        state["ennui"] += 15
        state["notoriety"] += 10
        state["decisions"].append("cold_return")
        slow_print("\n  You walk through the vestibule, past the servants,")
        slow_print("  past your mother, past Stepan Trofimovich who has")
        slow_print("  prepared a three-page welcome speech in French.")
        slow_print("  You close the door to your old rooms.")
        slow_print("  You sit on the bed and look at the ceiling.")
        slow_print("  The ceiling looks back. It has been doing this for years.")
        slow_print(f"  {DIM}Outside, you hear your mother say to no one in particular:")
        slow_print(f'  "He is tired from the journey."{RESET}')
        slow_print(f"  {DIM}She will defend you until it destroys her.{RESET}")
    elif choice == 3:
        state["stepan_bond"] += 10
        state["ennui"] += 5
        state["soul"] += 5
        state["decisions"].append("greeted_stepan")
        slow_print('\n  "Stepan Trofimovich." You take his hand.')
        slow_print("  The old man's eyes fill immediately. His lip trembles.")
        slow_print('  "Nicolas! Mon cher enfant! You remember your old teacher!"')
        slow_print("  He weeps openly, without shame. He is absurd.")
        slow_print("  He is also the only person in this house who ever")
        slow_print("  read you bedtime stories. In Latin, naturally.")
        slow_print("  Your mother watches from across the room, jealous")
        slow_print("  of an emotion she cannot permit herself.")
        slow_print(f"  {DIM}For a moment, you almost feel something.{RESET}")
        slow_print(f"  {DIM}It passes. These things always pass.{RESET}")
    elif choice == 4:
        state["notoriety"] += 20
        state["soul"] -= 5
        state["ennui"] -= 5
        state["marya_bond"] += 5
        state["decisions"].append("announced_marriage")
        slow_print("\n  The drawing room goes silent.")
        slow_print('  "I intend to make a public announcement," you say.')
        slow_print('  "Marya Timofeyevna Lebyadkina is my lawful wife.')
        slow_print('   We were married in Petersburg four and a half years ago."')
        slow_print("  Your mother grips the arm of her chair.")
        slow_print("  Stepan Trofimovich drops his lorgnette.")
        slow_print("  Somewhere, distantly, a dog barks.")
        slow_print('  "The cripple?" your mother whispers.')
        slow_print("  You do not correct her. The word is accurate enough.")
        slow_print(f"  {DIM}You married her because the shame and senselessness{RESET}")
        slow_print(f"  {DIM}of it reached the pitch of genius. Shatov said that.{RESET}")
        slow_print(f"  {DIM}Shatov was right.{RESET}")

    # Interior monologue
    print()
    slow_print(f"  {DIM}Later, in your old rooms, you sit in a chair{RESET}")
    slow_print(f"  {DIM}that still remembers the shape of you at sixteen.{RESET}")
    slow_print(f"  {DIM}Outside the window: the lime trees, the path to the pond,{RESET}")
    slow_print(f"  {DIM}the distant roof of the church where you were baptized.{RESET}")
    slow_print(f"  {DIM}You have been to Naples, to Iceland, to Egypt.{RESET}")
    slow_print(f"  {DIM}You have read everything, tried everything, felt nothing.{RESET}")
    slow_print(f"  {DIM}And now you are here, and here is exactly like everywhere else:{RESET}")
    slow_print(f"  {DIM}a room containing you, which is to say, containing nothing.{RESET}")

    clamp_stats()
    show_status()
    press_enter()


# ═══════════════════════════════════════════════════════════════
#  THE DRAWING ROOM / SCANDAL SUNDAY
# ═══════════════════════════════════════════════════════════════

def chapter_2_drawing_room():
    """Part I, Ch.5: The Subtle Serpent — the explosive drawing-room scene."""
    clear_screen()
    print(f"""{CYAN}
  ╔══════════════════════════════════════════════════════════════════╗
  ║  {WHITE}THE DRAWING ROOM{CYAN}                    {DIM}Sunday Afternoon{CYAN}              ║
  ╠══════════════════════════════════════════════════════════════════╣
  ║                                                                  ║
  ║     {WHITE}|{CYAN}  .---.  .---.  .---.         _____         .---.  .---. {WHITE}|{CYAN}  ║
  ║     {WHITE}|{CYAN}  |{DIM}   {CYAN}|  |{DIM}   {CYAN}|  |{DIM}   {CYAN}|        / ___ \\        |{DIM}   {CYAN}|  |{DIM}   {CYAN}| {WHITE}|{CYAN}  ║
  ║     {WHITE}|{CYAN}  '---'  '---'  '---'       | |   | |       '---'  '---' {WHITE}|{CYAN}  ║
  ║     {WHITE}|{CYAN}  {DIM}chairs{CYAN}                     | |{WHITE}////{CYAN}| |      {DIM}chairs{CYAN}       {WHITE}|{CYAN}  ║
  ║     {WHITE}|{CYAN}                             | |{WHITE}////{CYAN}| |                    {WHITE}|{CYAN}  ║
  ║     {WHITE}|{CYAN}    o   o              o     |_|____|_|    o        o    {WHITE}|{CYAN}  ║
  ║     {WHITE}|{CYAN}   /|\\ /|\\            /|\\     {WHITE}SAMOVAR{CYAN}    /|\\      /|\\   {WHITE}|{CYAN}  ║
  ║     {WHITE}|{CYAN}   {DIM}Liza Mavriky    Stepan{CYAN}               {DIM}Varvara   ???{CYAN}  {WHITE}|{CYAN}  ║
  ║     {WHITE}|{CYAN}                                                         {WHITE}|{CYAN}  ║
  ║     {WHITE}|{CYAN}  ===={WHITE}[  THE DIVAN  ]{CYAN}====    .------.                   {WHITE}|{CYAN}  ║
  ║     {WHITE}|{CYAN}                             | {WHITE}DOOR{CYAN} |<-- {DIM}it swings open{CYAN}  {WHITE}|{CYAN}  ║
  ║     {WHITE}|{CYAN}_____________________________|______|____________________{WHITE}|{CYAN}  ║
  ║                                                                  ║
  ║     {DIM}"Who is this woman?" Varvara demands.{CYAN}                       ║
  ║     {DIM}Every eye turns to you.{CYAN}                                     ║
  ╚══════════════════════════════════════════════════════════════════╝{RESET}
""")

    slow_print(f"  {BOLD}CHAPTER II: THE SUBTLE SERPENT{RESET}")
    print()
    slow_print("  Your mother has arranged one of her Sundays.")
    slow_print("  The drawing room is full. Everyone who matters in the province")
    slow_print("  is here, and everyone who does not matter is here also,")
    slow_print("  because in a provincial town these categories overlap entirely.")
    print()
    slow_print("  Present: Varvara Petrovna, rigid with propriety.")
    slow_print("  Stepan Trofimovich on the divan, gesturing at Schiller.")
    slow_print("  Lizaveta Nikolaevna Tushina — Liza — beautiful, nervous,")
    slow_print("  watching you with an intensity that borders on illness.")
    slow_print("  Her fiancé Mavriky Nikolaevich, loyal as a large dog.")
    print()
    slow_print("  And then — the door opens.")
    slow_print("  Captain Lebyadkin enters, drunk, reciting his own poetry.")
    slow_print("  Behind him, led by the hand: Marya Timofeyevna.")
    slow_print("  Your wife. The lame woman. The holy fool.")
    slow_print("  She looks around the room with the serenity of a child.")
    print()
    slow_print("  Varvara Petrovna's face turns to stone.")
    slow_print('  "Who is this woman?" she demands.')
    print()
    slow_print("  Every eye turns to you.")
    print()

    slow_print("  How do you handle the catastrophe?")

    choice = get_choice([
        "Acknowledge her publicly. Tell the truth, simply.",
        "Say nothing. Let the room draw its own conclusions.",
        "Lead Marya Timofeyevna gently out. Protect her from this.",
        "Turn to Lebyadkin: 'Remove yourself and your sister immediately.'",
    ])

    if choice == 1:
        state["notoriety"] += 15
        state["soul"] += 10
        state["marya_bond"] += 10
        state["decisions"].append("acknowledged_marya")
        slow_print('\n  "This is Marya Timofeyevna," you say quietly.')
        slow_print('  "She is my wife."')
        slow_print("  The room does not gasp. It does something worse:")
        slow_print("  it goes utterly, completely silent.")
        slow_print("  Liza's face drains of color. Stepan Trofimovich")
        slow_print("  makes a small sound like a man stepping on a cat.")
        slow_print("  Your mother grips the arm of her chair so hard")
        slow_print("  that her knuckles turn the color of bone.")
        slow_print("  Marya Timofeyevna smiles at everyone and says:")
        slow_print(f'  {DIM}"What nice people. Is there tea?"{RESET}')
    elif choice == 2:
        state["ennui"] += 15
        state["notoriety"] += 10
        state["decisions"].append("silence_in_salon")
        slow_print("\n  You say nothing. The room holds its breath.")
        slow_print("  Varvara Petrovna looks from you to the cripple")
        slow_print("  and back again, searching for some explanation")
        slow_print("  that does not exist.")
        slow_print("  Lebyadkin, encouraged by the silence, begins to recite:")
        slow_print(f'  {DIM}"Oh, she\'s a sweet queen, Lizaveta Tushin!"{RESET}')
        slow_print("  — terrible poetry, directed at Liza, of all people.")
        slow_print("  Your silence fills the room like smoke.")
        slow_print("  Everyone assigns it the meaning they most fear.")
    elif choice == 3:
        state["soul"] += 15
        state["marya_bond"] += 15
        state["ennui"] -= 5
        state["decisions"].append("protected_marya")
        slow_print("\n  You cross the room. Thirty people watch.")
        slow_print("  You take Marya Timofeyevna's hand — gently,")
        slow_print("  the way one handles something precious and breakable.")
        slow_print('  "Come," you say softly. "This is no place for you."')
        slow_print("  She looks up at you with her lame, luminous smile.")
        slow_print('  "My prince," she whispers. "You came back."')
        slow_print("  Something moves in your chest. You are not sure what.")
        slow_print("  You lead her out. Behind you, the room erupts.")
        slow_print(f"  {DIM}For a moment, your hand in hers, you were almost human.{RESET}")
    elif choice == 4:
        state["soul"] -= 10
        state["notoriety"] += 10
        state["marya_bond"] -= 10
        state["decisions"].append("dismissed_lebyadkins")
        slow_print('\n  "Remove yourself," you say to Lebyadkin,')
        slow_print("  in a voice so cold it could frost glass.")
        slow_print("  Lebyadkin stammers. He is used to being dismissed")
        slow_print("  but not like this, not in front of society.")
        slow_print("  Marya Timofeyevna looks at you. Her face changes.")
        slow_print('  "You are not my prince," she says suddenly.')
        slow_print('  "My prince would not speak so. You are someone else.')
        slow_print('   You are an impostor."')
        slow_print("  The holy fool sees what no one else can see:")
        slow_print("  the emptiness behind the beautiful face.")
        slow_print(f"  {DIM}She is the only one who has ever looked through you.{RESET}")
        slow_print(f"  {DIM}It is the most terrifying thing that has ever happened to you.{RESET}")

    # Shatov's slap — happens regardless
    print()
    slow_print(f"  {RED}  Then Shatov enters.{RESET}")
    slow_print(f"  {RED}  Ivan Pavlovich Shatov — your former disciple,{RESET}")
    slow_print(f"  {RED}  the man you taught about God and Russia,{RESET}")
    slow_print(f"  {RED}  whose wife you seduced because you could.{RESET}")
    print()
    slow_print("  He walks up to you in front of thirty people.")
    slow_print("  He slaps you across the face.")
    slow_print("  Hard. The sound is like a gunshot in the drawing room.")
    print()
    slow_print("  The room is frozen. Your cheek burns.")
    slow_print("  Your hands do not move.")
    print()

    slow_print("  What do you do?")

    choice2 = get_choice([
        "Put your hands behind your back. Accept it.",
        "Seize his arms. Hold them. Look into his eyes.",
        "Walk away without a word.",
        "Smile.",
    ])

    if choice2 == 1:
        state["soul"] += 15
        state["notoriety"] += 15
        state["shatov_bond"] += 10
        state["decisions"].append("accepted_the_slap")
        slow_print('\n  "Enough," you say, quietly, and put your hands')
        slow_print("  behind your back. Shatov's fist trembles.")
        slow_print("  He wants to hit you again. He cannot.")
        slow_print("  The whole room watches a man accept punishment")
        slow_print("  from someone weaker. It is the most shocking thing")
        slow_print("  any of them have ever witnessed.")
        slow_print("  Liza faints. Mavriky Nikolaevich catches her.")
        slow_print(f"  {DIM}Your restraint will be interpreted as superhuman.{RESET}")
        slow_print(f"  {DIM}It is not. You simply deserved it.{RESET}")
    elif choice2 == 2:
        state["soul"] += 10
        state["shatov_bond"] += 15
        state["decisions"].append("seized_shatovs_arms")
        slow_print("\n  You catch both his wrists. Your grip is iron.")
        slow_print("  Shatov struggles. He is shaking.")
        slow_print('  "Ivan," you say. Just his name.')
        slow_print("  His eyes are wild — not with hatred but with")
        slow_print("  a grief so enormous it has curdled into violence.")
        slow_print('  "Because of your fall," he whispers. "Your lie.')
        slow_print('   I didn\'t know I would strike you until I did."')
        slow_print('  "I know," you say. "I understand."')
        slow_print(f"  {DIM}You hold him until the shaking stops.{RESET}")
        slow_print(f"  {DIM}In Russia, this counts as an embrace.{RESET}")
    elif choice2 == 3:
        state["ennui"] += 15
        state["notoriety"] += 10
        state["decisions"].append("walked_away_from_slap")
        slow_print("\n  You turn and walk out of the drawing room.")
        slow_print("  Through the vestibule. Past the servants.")
        slow_print("  Into the garden, where the birches are turning.")
        slow_print("  Behind you, chaos. Shouts. A woman screaming.")
        slow_print("  You keep walking until you reach the gate.")
        slow_print("  The evening air smells of woodsmoke and damp earth.")
        slow_print("  Your cheek throbs. It is the most alive")
        slow_print("  you have felt in four years.")
        slow_print(f"  {DIM}You do not go back inside for eight days.{RESET}")
    elif choice2 == 4:
        state["ennui"] += 10
        state["notoriety"] += 20
        state["soul"] -= 15
        state["decisions"].append("smiled_at_slap")
        slow_print("\n  You smile. Not a mocking smile. Not a kind one.")
        slow_print("  Just — a smile. The expression of a man who has")
        slow_print("  been given something he has been waiting for.")
        slow_print("  Shatov recoils as though burned.")
        slow_print("  The room is horrified. Three women faint.")
        slow_print("  Stepan Trofimovich later tells the narrator")
        slow_print('  that he saw "something diabolical" in it.')
        slow_print("  You disagree. Diabolical implies purpose.")
        slow_print(f"  {DIM}There was no purpose. Only the reflex{RESET}")
        slow_print(f"  {DIM}of a man who has forgotten what faces are for.{RESET}")

    clamp_stats()
    show_status()
    press_enter()


# ═══════════════════════════════════════════════════════════════
#  THE DUEL
# ═══════════════════════════════════════════════════════════════

def chapter_new_duel():
    """Part II, Ch.3: The duel with Gaganov Jr."""
    clear_screen()
    print(f"""{RED}
                                  {DIM}. Dawn .{RED}
                              .              .
               {DIM}~~trees~~{RED}   .    {WHITE}Brykov Forest{RED}    .   {DIM}~~trees~~{RED}
              /|||||||\\                           /|||||||\\
             /|||||||||\\   .                 .   /|||||||||\\
            /|||||||||||\\                       /|||||||||||\\
           /|||||||||||||\\                     /|||||||||||||\\
          /|||||||||||||||\\        {DIM}fog{RED}        /|||||||||||||||\\
         /|||||||||||||||||\\   . . . . . .   /|||||||||||||||||\\
        .:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:

              o                           o
             /|\\     <--- {WHITE}20 paces{RED} --->  /|\\
             / \\                          / \\
           {WHITE}STAVROGIN{RED}                    {WHITE}GAGANOV{RED}

                        o         o
                       /|\\       /|\\
                       / \\       / \\
                     {DIM}Kirillov   Mavriky{RED}
                      {DIM}(seconds){RED}

        .:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:.:
        {DIM}Three exchanges. He aims to kill. You aim to miss.{RED}
        {DIM}The question is: what does that prove?{RESET}
""")

    slow_print(f"  {BOLD}CHAPTER III: THE DUEL{RESET}")
    print()
    slow_print("  Three days after the scandal in the drawing room.")
    slow_print("  A letter arrives at Skvoreshniki, carried by a second:")
    slow_print("  Artemy Pavlovich Gaganov — the son — demands satisfaction.")
    slow_print("  You pulled his father across a room by the nose,")
    slow_print("  years ago, in the club, in front of everyone.")
    slow_print("  The old man never recovered. He weeps at dinner parties.")
    slow_print("  The son has sworn to avenge the family honor.")
    print()
    slow_print("  You had apologized already — a written apology,")
    slow_print("  polite, correct, admitting that you had acted")
    slow_print('  "under the influence of illness." Gaganov Jr.')
    slow_print("  threw the letter in the fire. He will have blood.")
    print()
    slow_print("  Kirillov agrees to act as your second.")
    slow_print("  He has never mounted a horse before.")
    slow_print("  The ride to the forest takes an hour;")
    slow_print("  he clings to the saddle with grim determination,")
    slow_print("  bouncing like a sack of philosophy.")
    slow_print('  "I agreed because I do not accept conventions,"')
    slow_print("  he says, teeth rattling. You almost smile.")
    print()
    slow_print("  Brykov forest. A clearing among the birches.")
    slow_print("  The seconds pace out twenty steps.")
    slow_print("  Gaganov stands at his mark: young, trembling,")
    slow_print("  his face white with an emotion that is half courage")
    slow_print("  and half the nausea of a man about to do violence.")
    slow_print("  Mavriky Nikolaevich — Liza's fiancé — serves as his second.")
    print()
    slow_print(f"  {BOLD}First exchange.{RESET}")
    slow_print("  The signal is given. Gaganov fires first.")
    slow_print("  The bullet whirs past your head.")
    slow_print("  You raise your pistol. The clearing is silent.")
    slow_print("  Every bird has stopped singing.")
    print()
    slow_print("  You fire into the air.")
    print()
    slow_print("  Gaganov stares. The seconds exchange glances.")
    slow_print('  "You fired in the air!" Gaganov shouts.')
    slow_print('  "That is an insult! You treat me like a child!"')
    slow_print('  "I have no wish to kill you," you say.')
    slow_print('  "Then why did you accept the duel?"')
    slow_print("  You do not answer. There is no answer.")
    print()
    slow_print(f"  {BOLD}Second exchange.{RESET}")
    slow_print("  Gaganov's hands are shaking now. He fires again —")
    slow_print("  the bullet clips a branch above your shoulder.")
    slow_print("  Splinters of bark rain down on your coat.")
    slow_print("  You raise your pistol. Again, deliberately,")
    slow_print("  you aim above his head and fire into the trees.")
    print()
    slow_print('  "He is playing with me!" Gaganov screams.')
    slow_print("  He is weeping now — not from fear but from rage.")
    slow_print("  The shame of it: a man who will not fight back.")
    slow_print("  Worse than being shot. Worse than being hated.")
    slow_print("  To be treated as though you do not matter enough to kill.")
    print()
    slow_print(f"  {BOLD}Third exchange.{RESET}")
    slow_print("  This time Gaganov takes careful aim.")
    slow_print("  The pistol steadies. He fires.")
    slow_print("  The bullet punches through the crown of your hat.")
    slow_print("  An inch lower and you would be dead.")
    slow_print("  You remove the hat. Examine the hole.")
    slow_print("  Put it back on.")
    print()

    slow_print("  How do you take your final shot?")

    choice = get_choice([
        "Fire into the air a third time. Let him have his rage.",
        "Fire into the ground at Gaganov's feet. Make a point.",
        "Fire into a tree stump and remark on the splendid morning.",
        "Walk toward him, pistol lowered, and offer your hand.",
        "Step forward into his line of fire.",
    ])

    if choice == 5:
        state["decisions"].append("walked_into_bullet")
        game_over([
            f"  {RED}You step forward. One step. Two.{RESET}",
            f"  {RED}Not toward Gaganov. Into the space between you.{RESET}",
            f"  {RED}Into the path of the next bullet.{RESET}",
            "",
            "  Gaganov does not understand. Kirillov does.",
            '  "Stop!" Kirillov shouts. But you do not stop.',
            "  You have never stopped at anything in your life.",
            "  That was always the problem.",
            "",
            "  The pistol fires. The birches witness.",
            "  You fall in the wet grass.",
            "  The seconds stand over you. Gaganov is screaming.",
            "  Kirillov kneels beside you and says nothing.",
            "  He understands perfectly.",
            "",
            f"  {DIM}At the inquest, the doctors noted the angle of entry.{RESET}",
            f"  {DIM}They called it an accident. Kirillov did not correct them.{RESET}",
            f"  {DIM}He had his own appointment with a pistol to keep.{RESET}",
        ])

    if choice == 1:
        state["soul"] += 10
        state["notoriety"] += 10
        state["decisions"].append("fired_air_three_times")
        slow_print("\n  You fire into the air. A third time.")
        slow_print('  "I declare that I fire in the air on purpose!"')
        slow_print("  you say, loud enough for all to hear.")
        slow_print("  Gaganov collapses to his knees in the wet grass.")
        slow_print("  He is sobbing. Not with relief. With humiliation.")
        slow_print("  You have given him something worse than a wound:")
        slow_print("  the knowledge that he was not worth wounding.")
        slow_print(f"  {DIM}The seconds lead him away.{RESET}")
        slow_print(f"  {DIM}Kirillov studies your face on the ride home.{RESET}")
        slow_print(f'  {DIM}"You did not fire because you did not care," he says.{RESET}')
        slow_print(f'  {DIM}"Not because you were merciful."{RESET}')
        slow_print(f"  {DIM}You do not contradict him.{RESET}")
    elif choice == 2:
        state["ennui"] += 5
        state["notoriety"] += 15
        state["decisions"].append("fired_at_gaganovs_feet")
        slow_print("\n  You lower the pistol and fire into the ground")
        slow_print("  six inches from Gaganov's boots.")
        slow_print("  Dirt sprays across his trousers.")
        slow_print("  He staggers backward, white as paper.")
        slow_print('  "Next time," you say quietly, "I will aim lower still."')
        slow_print("  It is a lie. You would never aim at him.")
        slow_print("  But the cruelty of the gesture is exquisite —")
        slow_print("  not violence, but the theater of violence.")
        slow_print(f"  {DIM}Gaganov will never challenge you again.{RESET}")
        slow_print(f"  {DIM}He will also never forgive you.{RESET}")
        slow_print(f"  {DIM}These are the same thing.{RESET}")
    elif choice == 3:
        state["ennui"] += 10
        state["notoriety"] += 15
        state["soul"] -= 5
        state["decisions"].append("fired_at_stump")
        slow_print("\n  You turn ninety degrees and fire into a tree stump")
        slow_print("  at the edge of the clearing. The bark explodes.")
        slow_print('  "What a splendid morning," you say.')
        slow_print('  "The birches are particularly fine at this hour."')
        slow_print("  The seconds stare at you as though you have gone mad.")
        slow_print("  Perhaps you have. The distinction between madness")
        slow_print("  and perfect indifference is academic.")
        slow_print("  Gaganov throws his pistol on the ground and weeps.")
        slow_print(f"  {DIM}The ride home is silent.{RESET}")
        slow_print(f"  {DIM}Even Kirillov has nothing to say.{RESET}")
        slow_print(f"  {DIM}The birches really are very fine.{RESET}")
    elif choice == 4:
        state["soul"] += 15
        state["ennui"] -= 10
        state["shatov_bond"] += 5
        state["decisions"].append("offered_hand_to_gaganov")
        slow_print("\n  You lower the pistol. You walk forward.")
        slow_print("  Twenty paces. Past the mark. Past the rules.")
        slow_print("  Gaganov watches you come, pistol forgotten in his hand.")
        slow_print("  You stop in front of him and extend your hand.")
        slow_print('  "Forgive me," you say.')
        slow_print("  Not for the duel. For the nose. For his father.")
        slow_print("  For the casual cruelty of a bored aristocrat.")
        slow_print("  Gaganov stares at your hand. His lip trembles.")
        slow_print("  He does not take it. He turns and walks away.")
        slow_print(f"  {DIM}But something moved in his face before he turned.{RESET}")
        slow_print(f"  {DIM}Something that might have been — in another life —{RESET}")
        slow_print(f"  {DIM}the beginning of forgiveness.{RESET}")

    print()
    slow_print("  On the ride back, Kirillov is quiet for a long time.")
    slow_print("  Then he says, very softly, without looking at you:")
    slow_print(f'  {DIM}"You had better not come to me tonight.{RESET}')
    slow_print(f'  {DIM} You are not a strong person, Stavrogin.{RESET}')
    slow_print(f'  {DIM} I can see that now."{RESET}')
    slow_print(f"  {DIM}He is wrong. Or he is right.{RESET}")
    slow_print(f"  {DIM}Strength and emptiness look the same from outside.{RESET}")

    clamp_stats()
    show_status()
    press_enter()


# ═══════════════════════════════════════════════════════════════
#  PART II: NIGHT — THE VISITS
# ═══════════════════════════════════════════════════════════════

def chapter_3_night_kirillov():
    """Part II, Ch.1: Night — Stavrogin visits Kirillov."""
    clear_screen()
    print(f"""{MAGENTA}
  {DIM}Monday Night                          Filipov's House{MAGENTA}
  ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~  {DIM}Bogoyavlensky Street{MAGENTA}

         _____________________________________________
        |  .     .     .     .     .     .     .     |
        | .     .     .     .     .     .     .    . |
        |_____________________________________________|
        |          |              |                   |
        |          |              |                   |
        |  {WHITE}Kirillov's Room{MAGENTA}       |     {DIM}(Shatov{MAGENTA}       |
        |          |              |      {DIM}upstairs){MAGENTA}    |
        |    ___   |   _          |                   |
        |   | . |  |  ( )  o     |                   |
        |   | . |  |  |_| /|\\   |                   |
        |   |___|  |       / \\   |                   |
        |  {DIM}samovar{MAGENTA}  | {DIM}ball{MAGENTA}         |                   |
        |          |              |                   |
        |__________|______________|___________________|
                   |
           ________|________
          |  {DIM}A bare room.{MAGENTA}    |
          |  {DIM}One candle.{MAGENTA}     |
          |  {DIM}Tea. An india-{MAGENTA}  |
          |  {DIM}rubber ball.{MAGENTA}    |
          |_________________|{RESET}
""")

    slow_print(f"  {BOLD}CHAPTER III: NIGHT — KIRILLOV{RESET}")
    print()
    slow_print("  Eight days after the scandal. Monday night, seven o'clock.")
    slow_print("  You have been in your rooms at Skvoreshniki, seeing no one,")
    slow_print("  not even your mother. The swelling on your face has gone down.")
    slow_print("  Tonight, finally, you go out.")
    print()
    slow_print("  Filipov's house. A ramshackle building on Bogoyavlensky Street.")
    slow_print("  Kirillov lodges on the ground floor. Shatov lives upstairs.")
    slow_print("  The staircase smells of cabbage and philosophical despair.")
    print()
    slow_print("  Alexei Nilych Kirillov opens his door. He has been doing")
    slow_print("  his exercises — he is always doing exercises, or drinking tea,")
    slow_print("  or bouncing an india-rubber ball against the wall.")
    slow_print("  His room is bare. A table. A candle. The samovar.")
    slow_print("  He pours you tea without being asked.")
    print()
    slow_print('  "I walk about the room," Kirillov says matter-of-factly.')
    slow_print('  "I walk and I think. I have thought of something extraordinary."')
    print()
    slow_print('  He pauses. His eyes are calm and bright.')
    slow_print('  "If there is no God, then I am God. If I am God,')
    slow_print('   then I must express my self-will to the highest degree.')
    slow_print('   The highest degree of self-will is to kill oneself.')
    slow_print('   Not from despair. From freedom."')
    print()
    slow_print("  He pours more tea. His hands are steady.")
    slow_print("  This is a man who has resolved to die and has found")
    slow_print("  perfect peace in the resolution.")
    print()

    slow_print("  How do you respond to the logical suicide?")

    choice = get_choice([
        '"Your logic is madness, Kirillov."',
        "Listen in silence. Drink the tea. Let him speak.",
        '"If you are so free, why haven\'t you done it yet?"',
        '"Remember what you have meant in my life, Kirillov."',
    ])

    if choice == 1:
        state["soul"] += 10
        state["ennui"] -= 5
        state["decisions"].append("called_kirillov_mad")
        slow_print('\n  "That is what they all say," Kirillov answers calmly.')
        slow_print('  "But name one act more rational than choosing')
        slow_print('   the moment and manner of your own end."')
        slow_print('  "Living," you say, surprising yourself.')
        slow_print("  Kirillov considers this with genuine interest,")
        slow_print("  like a mathematician presented with a new proof.")
        slow_print('  "But you do not live, Stavrogin. You endure.')
        slow_print('   That is not the same."')
        slow_print(f"  {DIM}The candle gutters. Neither of you has a rebuttal.{RESET}")
        state["tea_consumed"] += 1
    elif choice == 2:
        state["ennui"] += 10
        state["tea_consumed"] += 3
        state["decisions"].append("listened_to_kirillov")
        slow_print("\n  You listen. Kirillov talks for two hours.")
        slow_print("  About God. About freedom. About a spider he watched")
        slow_print("  for three days, trying to determine if it chose")
        slow_print("  to build its web or was merely compelled.")
        slow_print("  About the moment between sleep and waking")
        slow_print("  when all things are possible and nothing is true.")
        slow_print("  His logic is airtight and insane —")
        slow_print("  a perfect closed system, like a clock that only")
        slow_print("  tells the time of its own unwinding.")
        slow_print(f"  {DIM}The tea grows cold. Dawn approaches.{RESET}")
        slow_print(f"  {DIM}He has promised to kill himself and leave a note{RESET}")
        slow_print(f"  {DIM}taking responsibility for the group's crimes.{RESET}")
        slow_print(f"  {DIM}Pyotr Verkhovensky arranged this. Of course he did.{RESET}")
    elif choice == 3:
        state["ennui"] += 5
        state["soul"] -= 5
        state["decisions"].append("challenged_kirillov")
        slow_print("\n  Kirillov's smile fades. Then returns, wider.")
        slow_print('  "The moment must be right. It must be an act')
        slow_print("   of pure will, not despair. I am waiting for the")
        slow_print('   right moment — when it will mean the most."')
        slow_print('  "Mean the most to whom? You will be dead."')
        slow_print("  A very long pause. The india-rubber ball")
        slow_print("  sits motionless on the floor between you.")
        slow_print('  "To humanity," he says at last.')
        slow_print(f"  {DIM}You have planted a seed of doubt in a man{RESET}")
        slow_print(f"  {DIM}who was perfectly certain. Whether this is mercy{RESET}")
        slow_print(f"  {DIM}or cruelty, you genuinely cannot say.{RESET}")
        state["tea_consumed"] += 1
    elif choice == 4:
        state["soul"] += 5
        state["ennui"] += 5
        state["decisions"].append("acknowledged_kirillov")
        slow_print("\n  Kirillov's face softens — the only time you have")
        slow_print("  seen it do so.")
        slow_print('  "I know what I meant," he says quietly.')
        slow_print('  "You told me about the God-bearing people. And then')
        slow_print("   you told me there was no God. Both at the same time.")
        slow_print('   Both with perfect sincerity."')
        slow_print('  "I was not lying either time."')
        slow_print('  "I know. That is why you are the most dangerous')
        slow_print('   man alive, Stavrogin."')
        slow_print(f"  {DIM}He says it without malice. As a fact.{RESET}")
        slow_print(f"  {DIM}Like reporting the weather, or the time.{RESET}")
        state["tea_consumed"] += 2

    # Second beat: Kirillov shows the view from his window
    print()
    slow_print("  Before you leave, Kirillov does something unexpected.")
    slow_print("  He takes the candle and walks to the window.")
    slow_print('  "Come here," he says. "I want to show you something."')
    slow_print("  You stand beside him. The window faces east.")
    slow_print("  Beyond the rooftops: the river, the bridge, the fields.")
    slow_print("  The moon is full. Everything is silver and black.")
    print()
    slow_print('  "There are seconds," Kirillov says,')
    slow_print('  "they come five or six at a time —')
    slow_print("   and you suddenly feel the presence of eternal harmony.")
    slow_print("   It's something not earthly. Not that it's heavenly,")
    slow_print("   but a man in his earthly form can't endure it.")
    slow_print('   He must be physically changed or die."')
    print()
    slow_print('  "Five seconds of it — and you would give')
    slow_print('   your whole life for it."')
    print()
    slow_print("  He is looking at the moonlit river.")
    slow_print("  His face, in the candlelight, is transformed —")
    slow_print("  not ecstatic but perfectly still, perfectly present,")
    slow_print("  as though for this one moment the gap between")
    slow_print("  logic and feeling has closed.")
    print()
    slow_print("  You look at the river. You feel nothing.")
    slow_print("  But you remember what feeling felt like,")
    slow_print("  and for a man in your condition,")
    slow_print("  that is something.")
    print()
    slow_print(f'  "Good-bye, Kirillov."')
    slow_print(f'  "Come again at night. I know how to wake up.')
    slow_print(f"   I say 'seven o'clock' and I wake at seven.")
    slow_print(f'   I say \'ten o\'clock\' and I wake at ten."')
    slow_print(f'  "You have remarkable powers," you say,')
    slow_print(f"   looking at his pale face in the candlelight.")

    clamp_stats()
    show_status()
    press_enter()


def chapter_4_night_shatov():
    """Part II, Ch.1 continued: Night — Stavrogin visits Shatov."""
    clear_screen()
    print(f"""{CYAN}
  {DIM}Same Night                                 Upstairs{CYAN}
  ~~~~~~~~~~~                          {DIM}Filipov's House{CYAN}

              ___________________________________________
             /                                           \\
            /  {WHITE}SHATOV'S GARRET{CYAN}                             \\
           /                                               \\
          |  .------. .------. .------.                     |
          |  | {WHITE}BOOK{CYAN} | | {WHITE}BOOK{CYAN} | | {WHITE}BOOK{CYAN} |   .____________.  |
          |  | {WHITE}BOOK{CYAN} | | {WHITE}BOOK{CYAN} | | {WHITE}BOOK{CYAN} |   | //////////// |  |
          |  | {WHITE}BOOK{CYAN} | | {WHITE}BOOK{CYAN} | | {WHITE}BOOK{CYAN} |   | ///{WHITE}BED{CYAN}////// |  |
          |  '------' '------' '------'   | //////////// |  |
          |                                '____________'  |
          |                                                |
          |      o               o                         |
          |     /|\\             /|\\      .---.             |
          |     / \\             / \\      | {RED}*{CYAN} |  {DIM}revolver{CYAN}   |
          |   {DIM}Stavrogin{CYAN}       {DIM}Shatov{CYAN}      '---'  {DIM}on shelf{CYAN}   |
          |                                                |
           \\______________________________________________/
             {DIM}"Do you know," he begins, trembling,{CYAN}
             {DIM}"do you know that you told me —"{RESET}
""")

    slow_print(f"  {BOLD}CHAPTER IV: NIGHT — SHATOV{RESET}")
    print()
    slow_print("  Up the stairs. Utter darkness in the passage.")
    slow_print("  A door opens above. Light appears.")
    slow_print("  Shatov does not come out, but stands at his table, waiting.")
    slow_print("  He has been waiting for eight days. Perhaps longer.")
    slow_print("  Perhaps he has been waiting for you his entire life.")
    print()
    slow_print("  His garret is small. Three bookshelves. A revolver")
    slow_print("  on the uppermost shelf — bought from Lyamshin")
    slow_print("  in a delirium that you were coming to kill him.")
    print()
    slow_print("  He has grown thinner. He seems feverish.")
    slow_print('  "You\'ve been worrying me to death," he says softly.')
    slow_print('  "Why didn\'t you come?"')
    print()
    slow_print("  You sit. He sits. The candle between you.")
    slow_print("  You tell him what you have come to tell him:")
    slow_print("  that you are a member of the same secret society,")
    slow_print("  and that they may murder him.")
    print()
    slow_print("  Shatov stares at you, wild-eyed.")
    slow_print('  "You... you are a member of the society?"')
    print()
    slow_print("  Then the real conversation begins.")
    slow_print("  Not about danger. About everything else.")
    slow_print("  About God, and Russia, and the god-bearing people.")
    slow_print("  About words you spoke to him years ago")
    slow_print("  that rearranged his entire soul.")
    print()
    slow_print('  "You told me," Shatov says, pacing, trembling,')
    slow_print('  "that the Russian people are the only')
    slow_print("   god-bearing people on earth, destined to regenerate")
    slow_print('   and save the world in the name of a new God."')
    slow_print('  "I remember."')
    slow_print('  "You said it with such conviction — such fire —')
    slow_print("   that I left everything. My wife, my work,")
    slow_print("   my whole life in Geneva. I came back to Russia")
    slow_print('   because of what you said to me."')
    print()
    slow_print("  He stops pacing. His hands grip the back of a chair.")
    slow_print("  The knuckles are white. A candle on the shelf")
    slow_print("  throws his shadow enormous against the wall.")
    print()
    slow_print('  "And then — in the same breath, the same evening —')
    slow_print("   you told Kirillov there was no God at all.")
    slow_print("   That man must become God through self-will.")
    slow_print('   Both! At the same time! With the same sincerity!"')
    print()
    slow_print("  His voice rises. He is shaking.")
    slow_print('  "Do you believe in God, Stavrogin?')
    slow_print('   You — who told me everything I now believe —')
    slow_print('   do you yourself believe in God?"')
    print()

    slow_print("  What do you answer?")

    choice = get_choice([
        '"I believe in Russia... I believe in her orthodoxy..."',
        '"I shall not lie to you. I do not believe."',
        '"I... I will believe in God." (Shatov\'s own answer.)',
        "Change the subject. Ask about Marya Timofeyevna instead.",
        '"There is nothing. No God. No Russia. No you. Nothing."',
    ])

    if choice == 5:
        state["decisions"].append("destroyed_shatov")
        game_over([
            '  "There is nothing," you say.',
            '  "No God. No Russia. No people that bear God.',
            '   No faith. No future tense. Nothing."',
            "",
            "  Shatov stares at you.",
            "  You have never spoken to him with such honesty.",
            "  This is the man who built his entire faith on your words.",
            "  Who left his wife because you said Russia would be saved.",
            "  Who believed because you told him to believe.",
            "",
            "  Something breaks in his face. Not anger — that would be better.",
            "  Something deeper. The foundation giving way.",
            '  He sits down on the bed, very slowly, and says:',
            '  "Then I have wasted my life."',
            "",
            "  You have destroyed the only person who believed in you.",
            "  The emptiness at your center has finally consumed",
            "  the last thing that was real.",
            "",
            f"  {BOLD}THE VOID{RESET}",
            f"  {DIM}There is nothing left to play for.{RESET}",
        ])

    if choice == 1:
        state["soul"] += 10
        state["shatov_bond"] += 15
        state["ennui"] -= 10
        state["decisions"].append("believed_in_russia")
        slow_print("\n  The words come out before you can stop them.")
        slow_print("  Shatov stares. His whole body trembles.")
        slow_print('  "Those are my words. You gave them to me')
        slow_print('   and now you speak them back to me as your own?"')
        slow_print('  "Perhaps they were always yours."')
        slow_print("  Shatov's eyes fill with tears.")
        slow_print('  "And in God? In God?"')
        slow_print("  You do not answer. But you do not deny.")
        slow_print(f"  {DIM}The silence between you is more honest{RESET}")
        slow_print(f"  {DIM}than any words in any language.{RESET}")
    elif choice == 2:
        state["ennui"] += 10
        state["soul"] -= 5
        state["shatov_bond"] -= 5
        state["decisions"].append("declared_atheism")
        slow_print('\n  "Are you an atheist now?" Shatov whispers.')
        slow_print('  "Yes."')
        slow_print('  "And then? When you told me those things?"')
        slow_print('  "Just as I was then."')
        slow_print("  Shatov flinches as though struck a second time.")
        slow_print('  "You were an atheist even when you told me about')
        slow_print('   the god-bearing people? About the body of Christ?"')
        slow_print('  "I was not lying. In persuading you I was perhaps')
        slow_print('   more concerned with myself than with you."')
        slow_print(f"  {DIM}This is the most honest thing you have ever said.{RESET}")
        slow_print(f"  {DIM}It is also the most terrible.{RESET}")
    elif choice == 3:
        state["soul"] += 15
        state["ennui"] -= 10
        state["shatov_bond"] += 10
        state["decisions"].append("will_believe")
        slow_print('\n  "I... I will believe in God."')
        slow_print("  The words fall into the room like stones into water.")
        slow_print("  Shatov stares at you. His mouth opens. Closes.")
        slow_print("  Not one muscle moves in your face.")
        slow_print("  He cannot tell if this is mockery or revelation.")
        slow_print("  Neither can you.")
        slow_print(f"  {DIM}The future tense is the most dangerous verb form{RESET}")
        slow_print(f"  {DIM}in the Russian language. It promises everything.{RESET}")
        slow_print(f"  {DIM}It delivers nothing. But it keeps the door open.{RESET}")
    elif choice == 4:
        state["marya_bond"] += 5
        state["shatov_bond"] += 5
        state["decisions"].append("asked_about_marya")
        slow_print("\n  You cannot answer the question. You change course.")
        slow_print('  "I have a favor to ask about Marya Timofeyevna.')
        slow_print("   You are the only person who has influence over her")
        slow_print('   poor brain. I want you to look after her."')
        slow_print("  Shatov is thrown off balance.")
        slow_print('  "You speak so calmly... Your wife... and you ask me—"')
        slow_print('  "Yes. I ask you."')
        slow_print("  Something passes between you — not understanding,")
        slow_print("  exactly, but the acknowledgment of a shared wound.")
        slow_print(f"  {DIM}He nods. Once. That is enough.{RESET}")

    # Shatov's emotional breakdown — the weight of it
    print()
    slow_print("  The room is very quiet. The candle has burned low.")
    slow_print("  Shatov sinks into a chair. He puts his face in his hands.")
    slow_print('  "I was nothing before you spoke to me," he says,')
    slow_print("  his voice muffled through his fingers.")
    slow_print('  "And now I am nothing again. But at least')
    slow_print('   I know what everything looks like."')
    slow_print("  He looks up. His eyes are red.")
    slow_print('  "You created a soul in me, Stavrogin.')
    slow_print('   And you don\'t even have one of your own."')
    slow_print("  The words hang in the air between you.")
    slow_print("  You should be angry. You are not.")
    slow_print("  You should deny it. You cannot.")
    slow_print(f"  {DIM}The man who slapped you eight days ago{RESET}")
    slow_print(f"  {DIM}is the man who understands you best.{RESET}")
    slow_print(f"  {DIM}This is how it works in Dostoevsky.{RESET}")

    # The warning about murder
    print()
    slow_print("  Before you leave, you lean close:")
    slow_print('  "I told you that they may murder you.')
    slow_print("   Pyotr Verkhovensky is authorized to do it.")
    slow_print('   You know too much, and they think you are a spy."')
    slow_print('  "I\'ve broken with them!" Shatov cries.')
    slow_print('  "He\'s a bug, an ignoramus!"')
    slow_print('  "Verkhovensky is an enthusiast," you reply.')
    slow_print('  "There is a point when he ceases to be a buffoon')
    slow_print('   and becomes a madman."')
    state["warned_shatov"] = True

    clamp_stats()
    show_status()
    press_enter()


def chapter_5_night_lebyadkins():
    """Part II, Ch.2: Night continued — the visit to the Lebyadkins and Fedka."""
    clear_screen()
    print(f"""{CYAN}
  {DIM}Past Midnight                       Across the River{CYAN}
  ~~~~~~~~~~~~~                    {DIM}Lebyadkin's Rooms{CYAN}

      ~  ~  ~  ~  ~  ~  ~ {DIM}river{CYAN} ~  ~  ~  ~  ~  ~  ~  ~
     ~  ~  ~  ~  ~  ~  ~  ~  ~  ~  ~  ~  ~  ~  ~  ~  ~

         ________________________________________________
        |            |                |                   |
        |  .------. |                |      .----.       |
        |  |{DIM}candle{CYAN}| |    o     o     |      |{DIM}icon{CYAN}  |      |
        |  | {YELLOW}*{CYAN}    | |   /|\\   /|\\    |      '----'       |
        |  '------' |   / \\   / \\    |                   |
        |            |  {WHITE}MARYA{CYAN} {WHITE}CAPTAIN{CYAN}  |   .---. .---. .-. |
        |  .-------. |                |   |{DIM}///|{CYAN} |{DIM}///|{CYAN} |{DIM}/|{CYAN} |
        |  | {WHITE}CHAIR{CYAN} | |    {DIM}papers &{CYAN}    |   |{DIM}///|{CYAN} |{DIM}///|{CYAN} |{DIM}/|{CYAN} |
        |  '-------' |    {DIM}terrible{CYAN}   |   '---' '---' '-' |
        |            |    {DIM}poetry{CYAN}     |     {DIM}BOTTLES{CYAN}       |
        |____________|________________|___________________|
                           |
                    _______|_______
                   |  {DIM}Thin walls.{CYAN}   |
                   |  {DIM}Cheap rooms.{CYAN}  |
                   |_______________|{RESET}
""")

    slow_print(f"  {BOLD}CHAPTER V: NIGHT — THE LEBYADKINS AND FEDKA{RESET}")
    print()
    slow_print("  You cross the river to the new lodgings.")
    slow_print("  Captain Lebyadkin — your brother-in-law, God help you —")
    slow_print("  opens the door drunk, in his undershirt.")
    slow_print('  "Prince! Your Excellency!" He is instantly fawning.')
    slow_print("  Behind him: empty bottles, the smell of herring,")
    slow_print("  and terrible poetry scattered across the table.")
    print()
    slow_print("  But you are here for Marya Timofeyevna.")
    slow_print("  She sits in the far room, wearing a clean white dress,")
    slow_print("  her hair neatly combed, as though expecting you.")
    slow_print("  She always seems to be expecting someone.")
    print()
    slow_print("  She looks at you with her strange, penetrating eyes.")
    slow_print("  There is a long silence.")
    print()
    slow_print('  "You are not he," she says suddenly.')
    slow_print('  "Not who?"')
    slow_print('  "Not my prince. My prince was bright as the sun.')
    slow_print('   You look like him, but you are not him.')
    slow_print('   You are an impostor."')
    print()
    slow_print("  She has seen through you. The holy fool,")
    slow_print("  the lame woman, the beggar you married on a dare —")
    slow_print("  she is the only person alive who can see")
    slow_print("  that behind your face there is no one.")
    print()

    slow_print("  How do you respond?")

    choice = get_choice([
        '"You are right. I am not your prince."',
        '"Marya Timofeyevna, I came to tell you I will provide for you."',
        "Say nothing. Stand there and let her see what she sees.",
        "Leave. You cannot bear it.",
    ])

    if choice == 1:
        state["soul"] += 15
        state["marya_bond"] += 10
        state["ennui"] -= 10
        state["decisions"].append("admitted_impostor")
        slow_print('\n  Her face softens. Almost with pity.')
        slow_print('  "I knew. I always knew. But sometimes')
        slow_print('   you looked so much like him that I forgot."')
        slow_print("  She reaches out and touches your cheek —")
        slow_print("  the cheek Shatov slapped.")
        slow_print('  "Poor impostor," she whispers.')
        slow_print(f"  {DIM}No one has ever pitied you before.{RESET}")
        slow_print(f"  {DIM}You are not sure you can survive it.{RESET}")
    elif choice == 2:
        state["ennui"] += 5
        state["soul"] += 5
        state["decisions"].append("promised_provision")
        slow_print("\n  She waves this away like a child waving away a fly.")
        slow_print('  "Money, money. The Captain always talks about money.')
        slow_print('   I do not want money. I want the prince."')
        slow_print('  "Marya Timofeyevna—"')
        slow_print('  "Do you know, I had a baby once," she says dreamily.')
        slow_print('  "It was very small. I brought it to a pond in the night')
        slow_print('   and drowned it, and I have been crying ever since."')
        slow_print("  She never had a baby. Marya Timofeyevna is a virgin.")
        slow_print("  But she speaks of it as though reporting the weather.")
        slow_print(f"  {DIM}You sit with her until dawn. The Captain snores.{RESET}")
        slow_print(f"  {DIM}Neither of you speaks again. It is enough.{RESET}")
    elif choice == 3:
        state["ennui"] += 10
        state["marya_bond"] += 5
        state["decisions"].append("stood_before_marya")
        slow_print("\n  You stand. She looks at you.")
        slow_print("  Minutes pass. The candle burns lower.")
        slow_print("  She is reading you like a book in a language")
        slow_print("  only she understands.")
        slow_print('  "There is a knife in your heart," she says finally.')
        slow_print('  "Someone put it there. Maybe you."')
        slow_print("  She crosses herself and turns away.")
        slow_print(f"  {DIM}You leave. On the stairs, your hands are trembling.{RESET}")
        slow_print(f"  {DIM}You do not know why. You never know why.{RESET}")
    elif choice == 4:
        state["ennui"] += 15
        state["soul"] -= 10
        state["decisions"].append("fled_from_marya")
        slow_print("\n  You turn on your heel and walk out.")
        slow_print("  Lebyadkin calls after you, something about money.")
        slow_print("  You do not answer. The night air hits your face.")
        slow_print("  You are walking fast, almost running.")
        slow_print("  From a lame woman in a clean white dress.")
        slow_print(f"  {DIM}She is the only person who terrifies you.{RESET}")
        slow_print(f"  {DIM}Not because of what she says,{RESET}")
        slow_print(f"  {DIM}but because she sees.{RESET}")

    # Fedka on the bridge
    print()
    slow_print(f"  {RED}  On the bridge: a figure in the dark.{RESET}")
    slow_print(f"  {RED}  Fedka the Convict — an escaped prisoner,{RESET}")
    slow_print(f"  {RED}  a man Pyotr Verkhovensky has been using{RESET}")
    slow_print(f"  {RED}  as a weapon with legs.{RESET}")
    print()
    slow_print('  "Your Honor," Fedka says, showing his teeth,')
    slow_print('  "I could relieve you of certain... difficulties.')
    slow_print('   The Captain and his sister. An accident, perhaps.')
    slow_print('   Fire is so common in the riverside quarter."')
    print()

    slow_print("  What do you do?")

    choice2 = get_choice([
        '"Get away from me." Strike him and walk on.',
        "Give him nothing. But do not refuse clearly either.",
        '"Here are three roubles. Now leave me alone."',
        "Turn your back on him. Walk slowly.",
    ])

    if choice2 == 4:
        state["decisions"].append("turned_back_on_fedka")
        game_over([
            f"  {RED}You turn your back on the convict.{RESET}",
            f"  {RED}You walk. Slowly. Deliberately.{RESET}",
            f"  {RED}The way you do everything — as a performance{RESET}",
            f"  {RED}for an audience that does not exist.{RESET}",
            "",
            "  Fedka is a practical man.",
            "  He has killed before. The motion is familiar.",
            "  The knife enters between the ribs with the ease",
            "  of long practice. You feel a curious warmth.",
            "",
            "  The river is very black below the bridge.",
            "  Fedka rifles your pockets with professional speed.",
            '  "Forgive me, Your Honor," he says, crossing himself.',
            "  He pushes you over the railing.",
            "  The splash is very small for such a large man.",
            "",
            f"  {DIM}They will find you downstream in three days.{RESET}",
            f"  {DIM}Pyotr Verkhovensky will use even this.{RESET}",
        ])

    if choice2 == 1:
        state["soul"] += 10
        state["decisions"].append("struck_fedka")
        slow_print("\n  You hit Fedka hard enough that he staggers.")
        slow_print('  "I told you before. I won\'t give you money."')
        slow_print("  Fedka spits blood and grins. He has been hit")
        slow_print("  by better men. He will wait.")
        slow_print(f"  {DIM}Later, Pyotr Verkhovensky will use this refusal{RESET}")
        slow_print(f"  {DIM}against you. Everything becomes leverage.{RESET}")
    elif choice2 == 2:
        state["pyotr_entangled"] += 10
        state["ennui"] += 5
        state["decisions"].append("ambiguous_with_fedka")
        slow_print("\n  You walk past him without a word.")
        slow_print("  Fedka falls into step beside you.")
        slow_print('  "Your Honor will think about it?"')
        slow_print("  You say nothing. Silence, again.")
        slow_print("  Fedka takes the silence as he pleases.")
        slow_print(f"  {DIM}Ambiguity, again. Your specialty.{RESET}")
        slow_print(f"  {DIM}The gap between a yes and a no is where{RESET}")
        slow_print(f"  {DIM}murders get committed.{RESET}")
        state["took_fedkas_offer"] = True
    elif choice2 == 3:
        state["soul"] -= 5
        state["pyotr_entangled"] += 15
        state["decisions"].append("paid_fedka")
        slow_print("\n  You give him three roubles. He takes them")
        slow_print("  with the dignity of a man accepting his due.")
        slow_print('  "God bless you, Your Honor."')
        slow_print("  He disappears into the darkness under the bridge.")
        slow_print(f"  {DIM}Three roubles. The price of nothing.{RESET}")
        slow_print(f"  {DIM}Or the price of everything.{RESET}")
        slow_print(f"  {DIM}Pyotr Verkhovensky will later say you gave Fedka{RESET}")
        slow_print(f"  {DIM}the money as payment for the Lebyadkins.{RESET}")
        slow_print(f"  {DIM}This is a lie. But lies are load-bearing walls{RESET}")
        slow_print(f"  {DIM}in Pyotr Verkhovensky's architecture.{RESET}")
        state["took_fedkas_offer"] = True

    clamp_stats()
    show_status()
    press_enter()


# ═══════════════════════════════════════════════════════════════
#  IVAN THE TSAREVITCH
# ═══════════════════════════════════════════════════════════════

def chapter_6_ivan_tsarevitch():
    """Part II, Ch.8: Ivan the Tsarevitch — Pyotr's grand proposal."""
    clear_screen()
    print(f"""{RED}
  {DIM}Late Night                      Returning to Skvoreshniki{RED}

     *          .          *              .            *
         .            .         .                 .
              *                       .       *

    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ~~~~ {DIM}the mud road{RED} ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

              o  <--  o
             /|\\     /|\\
             / \\     / \\
                     {DIM}Pyotr clutches{RED}
                     {DIM}your sleeve{RED}

    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

     {DIM}trees{RED} /||\\    /||\\    /||\\    /||\\    /||\\  {DIM}trees{RED}
          /||||\\  /||||\\  /||||\\  /||||\\  /||||\\
         /||||||\\                         /||||||\\

    {DIM}"Listen," he raves. "You shall be our sun.{RED}
    {DIM} Ivan Tsarevitch... the new leader...{RED}
    {DIM} I am only your secretary, your Mavriky..."{RESET}
""")

    slow_print(f"  {BOLD}CHAPTER VI: IVAN THE TSAREVITCH{RESET}")
    print()
    slow_print("  The meeting at Virginsky's is over. Pyotr Verkhovensky's")
    slow_print("  revolutionary cell — the five — have been harangued,")
    slow_print("  manipulated, bound together with mutual suspicion.")
    slow_print("  Shigalyov presented his system: starting from unlimited")
    slow_print("  freedom, he arrives at unlimited despotism.")
    slow_print("  No one found this alarming.")
    print()
    slow_print("  Now Pyotr Stepanovich catches up to you on the road.")
    slow_print("  Mud to his knees. Eyes bright with ideology.")
    slow_print("  He clutches your sleeve and will not let go.")
    print()
    slow_print('  "Listen, Stavrogin!" he says, gasping, rapid.')
    slow_print('  "We are going to make a revolution! Such an upheaval')
    slow_print('   that everything will be uprooted from its foundation!"')
    print()
    slow_print("  He tells you about Shigalovism: every member spies on")
    slow_print("  every other. Total equality through total slavery.")
    slow_print("  Great intellects banished. Shakespeare stoned.")
    slow_print("  Cicero's tongue cut out. Copernicus blinded.")
    print()
    slow_print('  "But I\'ve given up Shigalov!" he cries.')
    slow_print('  "I need something more everyday.')
    slow_print('   The Pope shall be for the west.')
    slow_print('   And you — you shall be for us!"')
    print()
    slow_print("  He is trembling. He clutches your arm.")
    slow_print('  "Stavrogin, you are beautiful!" he says,')
    slow_print("  almost ecstatically. He kisses your hand.")
    slow_print("  A shiver runs down your spine.")
    print()
    slow_print('  "You are the leader, you are the sun,')
    slow_print('   and I am your worm!"')
    print()
    slow_print('  He reveals his plan: you will be Ivan the Tsarevitch.')
    slow_print("  The hidden prince. The legend. The face of revolution.")
    slow_print('  "He exists, but no one has seen him.')
    slow_print("   Oh, what a legend one can set going!\"")
    print()

    slow_print("  What do you make of this madman?")

    choice = get_choice([
        '"Madman!" Pull your hand away and leave.',
        '"I won\'t give up Shatov to you." Refuse the blood price.',
        '"Then have you been seriously reckoning on me?"',
        "Listen to all of it. Let him empty himself.",
        '"Yes. I will be your Ivan Tsarevitch."',
    ])

    if choice == 5:
        state["decisions"].append("became_ivan_tsarevitch")
        game_over([
            '  "Yes," you say.',
            "  One word. The most dangerous word in the Russian language.",
            "",
            "  Pyotr Verkhovensky's face transforms.",
            "  Not joy — something beyond joy.",
            "  The ecstasy of a man whose God has finally answered.",
            '  He falls to his knees in the mud.',
            '  "My prince! My Tsarevitch! I knew — I always knew!"',
            "",
            "  He is kissing your hand. Weeping. Planning.",
            "  Already the machinery is turning in his mind —",
            "  the leaflets, the signals, the murders to come,",
            "  all of them bearing your face.",
            "",
            "  You are no longer Nikolai Vsevolodovich Stavrogin.",
            "  You are a mask. A banner. A puppet with a crown.",
            "  The emptiness has been filled with someone else's purpose.",
            "  That is the worst kind of death.",
            "",
            f"  {BOLD}CONSUMED{RESET}",
            f"  {DIM}Columbus has found his America at last.{RESET}",
        ])

    if choice == 1:
        state["soul"] += 10
        state["pyotr_entangled"] -= 10
        state["revolutionary_fervor"] -= 5
        state["decisions"].append("called_pyotr_madman")
        slow_print('\n  "Madman!" You pull your hand away.')
        slow_print("  But Pyotr runs after you. He always runs after you.")
        slow_print('  "Let us make it up!" he whispers, spasmodic.')
        slow_print('  "Let us make it up! I\'ll bring you Lizaveta')
        slow_print('   Nikolaevna tomorrow — shall I?"')
        slow_print("  You shrug. You walk on. He trails behind.")
        slow_print("  He is a man from whom the most precious thing")
        slow_print("  is being taken — your attention.")
        slow_print(f"  {DIM}Pyotr Verkhovensky without Stavrogin{RESET}")
        slow_print(f"  {DIM}is Columbus without America.{RESET}")
        slow_print(f"  {DIM}He said that himself. He believes it.{RESET}")
    elif choice == 2:
        state["soul"] += 15
        state["shatov_bond"] += 10
        state["pyotr_entangled"] -= 5
        state["decisions"].append("refused_shatovs_blood")
        slow_print('\n  "I won\'t give up Shatov to you."')
        slow_print("  Pyotr starts. You look at each other.")
        slow_print('  "I told you this evening why you needed Shatov\'s blood.')
        slow_print("   It's the cement to bind your groups together.")
        slow_print('   I will not be party to it."')
        slow_print("  Pyotr's face changes — something raw underneath")
        slow_print("  the performance. Fear, perhaps. Or love.")
        slow_print("  It is hard to tell with men like this.")
        slow_print('  "Let us make it up!" he begs.')
        slow_print('  "I have a knife in my boot, but I\'ll make it up!"')
        slow_print(f"  {DIM}The most dangerous man in the province{RESET}")
        slow_print(f"  {DIM}is begging you not to leave him.{RESET}")
        slow_print(f"  {DIM}You leave him anyway.{RESET}")
    elif choice == 3:
        state["pyotr_entangled"] += 10
        state["revolutionary_fervor"] += 10
        state["ennui"] -= 5
        state["decisions"].append("questioned_the_plan")
        slow_print('\n  "A pretender?" You look at him with surprise.')
        slow_print('  "So that is your plan at last."')
        slow_print("  Pyotr's face shines.")
        slow_print('  "We shall say he is \'in hiding.\' Do you know')
        slow_print("   the magic of that phrase? He exists, but no one")
        slow_print("   has seen him. We'll set a legend going!")
        slow_print('   We only need one lever to lift the earth!"')
        slow_print("  You listen. Against your will, you are interested.")
        slow_print("  Not in the revolution — in the mechanism.")
        slow_print("  The clockwork of belief. The engineering of hope.")
        slow_print(f"  {DIM}You are the most dangerous possible audience{RESET}")
        slow_print(f"  {DIM}for a man like Pyotr Verkhovensky:{RESET}")
        slow_print(f"  {DIM}intelligent enough to see the game,{RESET}")
        slow_print(f"  {DIM}empty enough to play it.{RESET}")
    elif choice == 4:
        state["ennui"] += 10
        state["pyotr_entangled"] += 15
        state["revolutionary_fervor"] += 5
        state["decisions"].append("let_pyotr_rave")
        slow_print("\n  You let him talk. He talks for the entire walk home.")
        slow_print("  Revolution. Destruction. Teachers who laugh at God.")
        slow_print("  Lawyers who defend murderers. Peasants drunk on vodka.")
        slow_print("  One or two generations of vice, he says, are necessary.")
        slow_print("  Monstrous, abject vice. Fresh blood.")
        slow_print("  He says all of this while clutching your sleeve")
        slow_print("  in the mud, in the dark, on a provincial road.")
        slow_print(f"  {DIM}He is in a fever. He is raving.{RESET}")
        slow_print(f"  {DIM}He is also, perhaps, the future.{RESET}")
        slow_print(f"  {DIM}That is the terrible thing.{RESET}")

    clamp_stats()
    show_status()
    press_enter()


# ═══════════════════════════════════════════════════════════════
#  THE CONSPIRATORS' MEETING
# ═══════════════════════════════════════════════════════════════

def chapter_7_meeting():
    """Part II, Ch.7: A Meeting — the revolutionary quintet at Virginsky's."""
    clear_screen()
    print(f"""{RED}
  {DIM}Virginsky's House                          The Back Room{RED}
  ~~~~~~~~~~~~~~~~~~

         __________________________________________________
        |                                                    |
        |     .-------.                                      |
        |     | {YELLOW}*{RED}     |  {DIM}one candle{RED}                           |
        |     '-------'                                      |
        |                                                    |
        |        o    o    o        {WHITE}THE QUINTET{RED}              |
        |       /|\\  /|\\  /|\\                                |
        |                                                    |
        |        o    o    o    o                             |
        |       /|\\  /|\\  /|\\  /|\\                           |
        |                                                    |
        |  {DIM}Virginsky  Liputin  Shigalyov  Lyamshin{RED}           |
        |  {DIM}Tolkatchenko  Erkel{RED}                                |
        |                                                    |
        |     {DIM}"Starting from unlimited freedom,"{RED}               |
        |     {DIM}"I arrive at unlimited despotism." - Shigalyov{RED}  |
        |____________________________________________________|{RESET}
""")

    slow_print(f"  {BOLD}CHAPTER VII: A MEETING{RESET}")
    print()
    slow_print("  The meeting at Virginsky's. The famous gathering of the five.")
    slow_print("  Or seven. Or however many Pyotr Verkhovensky needs tonight.")
    print()
    slow_print("  They are here: Virginsky, the pure-hearted liberal.")
    slow_print("  Liputin, the rogue with one good point.")
    slow_print("  Shigalyov, with his ears like donkey-ears")
    slow_print("  and his manuscript on the reorganization of society.")
    slow_print("  Lyamshin, who will break first.")
    slow_print("  And Pyotr Stepanovich, the spider at the center.")
    print()
    slow_print("  Shigalyov presents his system. He speaks for ten minutes.")
    slow_print("  The room is baffled. He concludes:")
    slow_print(f'  {REVERSE}  "Starting from unlimited freedom,   {RESET}')
    slow_print(f'  {REVERSE}   I arrive at unlimited despotism."  {RESET}')
    print()
    slow_print("  He acknowledges this is a contradiction.")
    slow_print("  He believes there is no other solution.")
    print()
    slow_print("  Pyotr steers the meeting toward the real purpose:")
    slow_print("  binding the group. Creating mutual complicity.")
    slow_print('  He asks: "Would each of you inform the authorities')
    slow_print('   if you discovered a planned political murder?"')
    print()
    slow_print("  Shatov stands up and shouts: 'I refuse to answer")
    slow_print("  such a question!' He leaves, slamming the door.")
    print()
    slow_print("  The room looks at Pyotr. Pyotr looks at you.")
    slow_print("  The candle flickers.")
    print()

    slow_print("  What is your role here?")

    choice = get_choice([
        "Observe. You are collecting data, not taking sides.",
        '"Shatov is right. This meeting is a farce."',
        "Stay silent. Your silence binds them as much as any words.",
        "Leave. Follow Shatov out.",
        '"Shatov is a traitor. Do what must be done."',
    ])

    if choice == 5:
        state["decisions"].append("endorsed_murder")
        game_over([
            '  "Shatov is a traitor," you say.',
            "  Your voice is calm. Aristocratic. Final.",
            '  "He will inform. Do what must be done."',
            "",
            "  The room goes silent.",
            "  Virginsky turns white. Lyamshin makes a sound",
            "  like a small animal. Even Pyotr stares —",
            "  he expected to manipulate you into this,",
            "  not to hear you volunteer.",
            "",
            "  You have just authorized a murder.",
            "  Not through ambiguity. Not through silence.",
            "  Through clear, deliberate words witnessed by seven people.",
            "  The moral event horizon has been crossed.",
            "",
            "  Pyotr recovers first. His smile is radiant.",
            '  "You see?" he says to the room. "He understands."',
            "  No one in the room will ever be clean again.",
            "  Least of all you.",
            "",
            f"  {BOLD}THE ACCOMPLICE{RESET}",
            f"  {DIM}The cement has been mixed. Shatov's blood is on your hands.{RESET}",
        ])

    if choice == 1:
        state["ennui"] += 10
        state["pyotr_entangled"] += 5
        state["decisions"].append("observed_meeting")
        slow_print("\n  You watch. Pyotr talks. The conspirators shuffle,")
        slow_print("  argue, posture. Virginsky pleads for principles.")
        slow_print("  Liputin calculates odds. Shigalyov reads his manuscript")
        slow_print("  to no one in particular.")
        slow_print("  You see it all clearly: a handful of fools")
        slow_print("  magnifying their own significance.")
        slow_print("  And Pyotr, the only one among them who is dangerous,")
        slow_print("  because he alone has no ideology — only will.")
        slow_print(f"  {DIM}You are the sanest person in the room.{RESET}")
        slow_print(f"  {DIM}This does not comfort you.{RESET}")
    elif choice == 2:
        state["soul"] += 10
        state["revolutionary_fervor"] -= 10
        state["pyotr_entangled"] -= 5
        state["decisions"].append("called_meeting_farce")
        slow_print('\n  "This is a farce," you say, evenly.')
        slow_print("  The room falls silent.")
        slow_print("  Pyotr laughs — too quickly, too loudly.")
        slow_print('  "Stavrogin jokes! He is above our petty planning."')
        slow_print("  But his eyes are not laughing.")
        slow_print("  You have said the quiet part aloud.")
        slow_print("  That none of this has any plan beyond destruction.")
        slow_print("  That the new world they imagine is a blank page")
        slow_print("  they are terrified to fill.")
        slow_print(f"  {DIM}The truth, in a room full of revolutionaries,{RESET}")
        slow_print(f"  {DIM}is the most revolutionary act of all.{RESET}")
    elif choice == 3:
        state["ennui"] += 15
        state["pyotr_entangled"] += 10
        state["notoriety"] += 10
        state["decisions"].append("silent_at_meeting")
        slow_print("\n  You sit in the corner. Silent. Everyone steals")
        slow_print("  glances at you. Pyotr references you constantly:")
        slow_print('  "Stavrogin knows... Stavrogin understands..."')
        slow_print("  You have said nothing. You have endorsed nothing.")
        slow_print("  But your presence is a signature on a blank check.")
        slow_print("  They will fill in the amount later.")
        slow_print(f"  {DIM}In the darkness of the room, emptiness{RESET}")
        slow_print(f"  {DIM}and depth are indistinguishable.{RESET}")
    elif choice == 4:
        state["shatov_bond"] += 10
        state["soul"] += 5
        state["pyotr_entangled"] -= 10
        state["decisions"].append("followed_shatov_out")
        slow_print("\n  You stand and walk out after Shatov.")
        slow_print("  The room erupts behind you. Pyotr calls your name.")
        slow_print("  You do not turn around.")
        slow_print("  In the street, Shatov is walking fast.")
        slow_print('  "You followed me out," he says, not looking at you.')
        slow_print('  "Yes."')
        slow_print('  "Does that mean something?"')
        slow_print('  "I don\'t know."')
        slow_print("  You walk together in silence for a long time.")
        slow_print(f"  {DIM}Two men who cannot believe in anything{RESET}")
        slow_print(f"  {DIM}walking side by side in the dark.{RESET}")

    clamp_stats()
    show_status()
    press_enter()


# ═══════════════════════════════════════════════════════════════
#  THE FETE
# ═══════════════════════════════════════════════════════════════

def chapter_8_fete():
    """Part III, Ch.1-2: The Fete — the charity ball and its disaster."""
    clear_screen()
    print(f"""{CYAN}
             {WHITE}THE GOVERNOR'S CHARITY FETE{CYAN}
            {DIM}For the Benefit of Governesses{CYAN}

   ._______________________________________________________________.
   |   *     *     *     *     *     *     *     *     *     *     |
   |  .-.   .-.   .-.   .-.   .-.   .-.   .-.   .-.   .-.   .-.  |
   |  |{YELLOW}o{CYAN}|   |{YELLOW}o{CYAN}|   |{YELLOW}o{CYAN}|   |{YELLOW}o{CYAN}|   |{YELLOW}o{CYAN}|   |{YELLOW}o{CYAN}|   |{YELLOW}o{CYAN}|   |{YELLOW}o{CYAN}|   |{YELLOW}o{CYAN}|   |{YELLOW}o{CYAN}|  |
   |  '-'   '-'   '-'   '-'   '-'   '-'   '-'   '-'   '-'   '-'  |
   |   {DIM}chandeliers{CYAN}                                                |
   |                                                               |
   |    o  o  o  o  o  o  o  o  o  o  o  o  o  o  o  o  o  o     |
   |    o  o  o  o  o  o  o  o  o  o  o  o  o  o  o  o  o  o     |
   |    o  o  o  o  o  o  o  o  o  o  o  o  o  o  o  o  o  o     |
   |    {DIM}the crowd, three roubles a ticket{CYAN}                        |
   |                                                               |
   |   .========================================================. |
   |   ||  {WHITE}S T A G E{CYAN}                                          || |
   |   ||                                                        || |
   |   ||       {DIM}Karmazinov drones. Stepan weeps.{CYAN}                || |
   |   ||       {DIM}The champagne has run out.{CYAN}                      || |
   |   '========================================================' |
   '_______________________________________________________________'{RESET}
""")

    slow_print(f"  {BOLD}CHAPTER VIII: THE FETE{RESET}")
    print()
    slow_print("  Yulia Mihailovna — the Governor's wife — has been planning")
    slow_print("  this fete for months. It will raise money for governesses.")
    slow_print("  It will feature a literary matinée. Karmazinov,")
    slow_print("  the famous author, will read his farewell piece.")
    slow_print("  Stepan Trofimovich will give an address on beauty.")
    slow_print("  There will be a ball. There will not be champagne.")
    slow_print("  This last fact will become important.")
    print()
    slow_print("  The entire town has subscribed. Everyone is here.")
    slow_print("  But underneath the gaiety there is a feeling")
    slow_print("  of implacable resentment — a forced, strained cynicism.")
    slow_print("  The ladies all despise Yulia Mihailovna.")
    slow_print("  The men are drunk by noon.")
    slow_print("  Pyotr Verkhovensky's people are in the crowd,")
    slow_print("  waiting for their signal.")
    print()
    slow_print("  First: Karmazinov, the famous writer, reads his farewell.")
    slow_print("  He calls it 'Merci' — a saccharine reminiscence")
    slow_print("  of his childhood nurse, his first love, the Rhine,")
    slow_print("  and a blade of grass that taught him the meaning of life.")
    slow_print("  It goes on for an hour. The audience grows restless.")
    slow_print("  Someone in the back row falls asleep.")
    slow_print("  Karmazinov bows to scattered, confused applause")
    slow_print("  and exits with the air of a man who has given")
    slow_print("  humanity its final gift.")
    print()
    slow_print("  Then: Stepan Trofimovich takes the stage.")
    slow_print("  He is trembling. His waistcoat is buttoned wrong.")
    slow_print("  His speech is crumpled in his hand.")
    slow_print("  He looks out at the crowd — three hundred faces,")
    slow_print("  most of them already hostile from Karmazinov's ordeal.")
    print()
    slow_print("  He begins to speak — not the speech he prepared,")
    slow_print("  but something else. Something honest. Something mad.")
    slow_print("  His voice cracks. He waves his arms.")
    print()
    slow_print('  "I declare," he cries, his lorgnette trembling,')
    slow_print('  "that Shakespeare and Raphael are higher than')
    slow_print('   the emancipation of the serfs! Higher than Socialism!')
    slow_print('   Higher than the coming generation!')
    slow_print('   Higher than chemistry!')
    slow_print('   Higher, perhaps, than almost everything!"')
    print()
    slow_print('  "Beauty will save the world!"')
    print()
    slow_print("  The crowd erupts. Not with agreement — with fury.")
    slow_print('  "That is reactionary!" someone shouts.')
    slow_print('  "Aesthetics are the privilege of parasites!"')
    slow_print("  A shoe flies through the air.")
    slow_print("  Stepan Trofimovich catches it — or rather,")
    slow_print("  it hits him in the chest, and he stares at it")
    slow_print("  as though a shoe from the audience is a new phenomenon")
    slow_print("  that requires careful philosophical analysis.")
    slow_print("  He begins to weep, still holding the shoe.")
    slow_print("  Yulia Mihailovna's face is a mask of horror.")
    print()
    slow_print("  Then the literary quadrille begins. Pyotr arranged it.")
    slow_print("  Dancers in costumes symbolizing 'Great Thoughts':")
    slow_print("  someone is dressed as 'The Spirit of Local Government.'")
    slow_print("  Someone else represents 'The Honest Russian Journalist'")
    slow_print("  and carries a sign no one can read.")
    slow_print("  It is chaos dressed as allegory.")
    print()

    slow_print("  What do you do during the catastrophe?")

    choice = get_choice([
        "Go to Stepan Trofimovich. Lead him off the stage.",
        "Watch from the back. This is not your disaster.",
        "Find Liza. Something is happening between you tonight.",
        "Leave the fete entirely. Walk into the night.",
        "Walk to the river. The fire across the water is calling.",
    ])

    if choice == 5:
        state["decisions"].append("walked_into_fire")
        game_over([
            "  The glow across the river is wrong. Too bright. Too hungry.",
            "  You know what burns there — the riverside quarter.",
            "  The Lebyadkins' lodgings. Your wife's room.",
            "",
            f"  {RED}You run.{RESET}",
            "",
            "  Past the bridge. Past the crowd gathering to watch.",
            "  Past the men with buckets who have already given up.",
            "  Into the house. Up the stairs. Through the smoke.",
            "",
            "  Marya Timofeyevna is in her room, in her white dress,",
            "  sitting calmly, as though she has been expecting you.",
            '  "My prince," she says. "You came."',
            "",
            "  The ceiling collapses.",
            "",
            f"  {DIM}They found two bodies in the ash.{RESET}",
            f"  {DIM}The Captain's was found by the door, throat cut —{RESET}",
            f"  {DIM}Fedka's work, not the fire's.{RESET}",
            f"  {DIM}Yours they found beside your wife's.{RESET}",
            f"  {DIM}No one could explain what you were doing there.{RESET}",
            f"  {DIM}No one ever could explain you.{RESET}",
        ])

    if choice == 1:
        state["soul"] += 15
        state["stepan_bond"] += 15
        state["ennui"] -= 10
        state["decisions"].append("rescued_stepan")
        slow_print("\n  You walk to the stage. Through the crowd.")
        slow_print("  Three hundred people watch you do it.")
        slow_print("  Stepan Trofimovich is weeping, still quoting Shakespeare,")
        slow_print("  still insisting that beauty matters more than bread.")
        slow_print("  You take his arm.")
        slow_print('  "Come, Stepan Trofimovich. That is enough."')
        slow_print("  He looks at you with the eyes of a drowning man.")
        slow_print('  "Nicolas... did I speak well?"')
        slow_print('  "You spoke the truth. That is always badly received."')
        slow_print("  You lead him out. Behind you, the fete collapses.")
        slow_print(f"  {DIM}He will remember this kindness until the day he dies.{RESET}")
        slow_print(f"  {DIM}That day is not far off.{RESET}")
    elif choice == 2:
        state["ennui"] += 15
        state["notoriety"] += 5
        state["decisions"].append("watched_fete_collapse")
        slow_print("\n  You stand at the back. Arms crossed.")
        slow_print("  Watching the provincial world tear itself apart.")
        slow_print("  Stepan Trofimovich is booed off stage.")
        slow_print("  Karmazinov reads his interminable farewell.")
        slow_print("  Someone sets off firecrackers — Pyotr's signal.")
        slow_print("  The literary quadrille begins, absurd,")
        slow_print("  with costumes symbolizing thoughts no one understands.")
        slow_print("  A fight breaks out near the buffet.")
        slow_print("  Yulia Mihailovna leaves in tears.")
        slow_print(f"  {DIM}From the back of the room, civilization looks exactly{RESET}")
        slow_print(f"  {DIM}like a building that has been burning for some time{RESET}")
        slow_print(f"  {DIM}without anyone noticing.{RESET}")
    elif choice == 3:
        state["liza_bond"] += 15
        state["ennui"] -= 10
        state["soul"] -= 5
        state["decisions"].append("found_liza_at_fete")
        slow_print("\n  You find Liza near the exit. She is pale, shaking.")
        slow_print("  Mavriky Nikolaevich hovers nearby, loyal and miserable.")
        slow_print("  She looks at you and everything in the room stops.")
        slow_print('  "Take me away from here," she says.')
        slow_print("  It is not a request. It is a confession.")
        slow_print("  You take her hand. Mavriky Nikolaevich watches you")
        slow_print("  lead her away and does not follow.")
        slow_print("  The fete burns behind you.")
        slow_print(f"  {DIM}Tonight she will come to your rooms.{RESET}")
        slow_print(f"  {DIM}Tomorrow she will know the truth about you.{RESET}")
        slow_print(f"  {DIM}She will not survive the knowing.{RESET}")
    elif choice == 4:
        state["ennui"] += 10
        state["decisions"].append("left_the_fete")
        slow_print("\n  You walk out into the night.")
        slow_print("  Behind you, the sounds of the fete —")
        slow_print("  shouts, music, a crash of crockery.")
        slow_print("  The air outside is cold and clean.")
        slow_print("  You walk for a long time.")
        slow_print("  Past the church. Past the river. Past the bridge")
        slow_print("  where Fedka waited for you.")
        slow_print(f"  {DIM}The provincial town is destroying itself.{RESET}")
        slow_print(f"  {DIM}You are not responsible. Or you are.{RESET}")
        slow_print(f"  {DIM}The distinction no longer seems important.{RESET}")

    clamp_stats()
    show_status()
    press_enter()


# ═══════════════════════════════════════════════════════════════
#  LIZA
# ═══════════════════════════════════════════════════════════════

def chapter_new_liza():
    """Part III, Ch.3: The night Liza comes to Stavrogin."""
    clear_screen()
    print(f"""{MAGENTA}
  {DIM}Before Dawn                               Skvoreshniki{MAGENTA}
  ~~~~~~~~~~~~                              {DIM}Your Rooms{MAGENTA}

         ______________________________________________
        |                                              |
        |                                              |
        |       {YELLOW}*{MAGENTA}                                      |
        |      {DIM}candle{MAGENTA}                                    |
        |                                              |
        |                                              |
        |           o               o                  |
        |          /|\\             /|\\                 |
        |          / \\             / \\                 |
        |                                              |
        |                                              |
        |        .================================.    |
        |        |  /////////////{WHITE}BED{MAGENTA}//////////////  |    |
        |        |  ////////////////////////////////  |    |
        |        '================================'    |
        |______________________________________________|

           {DIM}She came to you in the night.{MAGENTA}
           {DIM}She will leave before morning.{MAGENTA}
           {DIM}Both of you know what this costs.{RESET}
""")

    slow_print(f"  {BOLD}CHAPTER X: LIZA{RESET}")
    print()
    slow_print("  She came to you.")
    slow_print("  Lizaveta Nikolaevna Tushina — Liza — came to Skvoreshniki")
    slow_print("  in the night, alone, without her fiancé,")
    slow_print("  without her reputation, without anything")
    slow_print("  except the green dress she was wearing")
    slow_print("  and the terrible clarity of a woman")
    slow_print("  who knows exactly what she is destroying.")
    print()
    slow_print("  Now: dawn. Grey light through the curtains.")
    slow_print("  She stands at the window, not looking at you.")
    slow_print("  The green dress is crumpled on the chair.")
    slow_print("  She is wearing your dressing gown.")
    slow_print("  Her hair is loose. Her back is very straight.")
    print()
    slow_print('  "I was a dead woman when I came in yesterday,"')
    slow_print("  she says, to the window, not to you.")
    slow_print('  "I knew it was the end. But I wanted')
    slow_print('   to have this one thing. Even knowing."')
    print()
    slow_print("  You sit on the edge of the bed.")
    slow_print("  You look at her and feel — what?")
    slow_print("  Not love. You have tried love; it did not take.")
    slow_print("  Not desire. That passed in the night.")
    slow_print("  Something more like recognition.")
    slow_print("  She is as doomed as you are, and she knows it,")
    slow_print("  and she came anyway. That takes a kind of courage")
    slow_print("  you have never possessed.")
    print()
    slow_print("  She turns from the window. Her face is pale.")
    slow_print("  Her eyes are dry — she is past tears.")
    slow_print('  "Tell me the truth, Stavrogin.')
    slow_print("   You have lied to everyone. Lie to me too,")
    slow_print('   if you must. But at least tell me the truth first."')
    print()
    slow_print('  "What truth?"')
    print()
    slow_print('  "Do you love me?"')
    print()
    slow_print("  The question hangs in the grey dawn light.")
    slow_print("  Outside, a bird begins to sing.")
    slow_print("  The most ordinary sound in the world.")
    print()

    slow_print("  What do you tell her?")

    choice = get_choice([
        '"I knew I did not love you, and yet I ruined you."',
        '"I am not capable of what you are asking."',
        "Take her hand. Say nothing. Let the silence be the answer.",
        '"Perhaps. I cannot tell the difference anymore."',
    ])

    if choice == 1:
        state["soul"] += 5
        state["liza_bond"] -= 10
        state["ennui"] += 5
        state["decisions"].append("told_liza_the_truth")
        slow_print('\n  "I knew I did not love you," you say,')
        slow_print('  "and yet I ruined you."')
        slow_print("  Liza's face does not change. She expected this.")
        slow_print("  That is the worst part — she came knowing.")
        slow_print('  "You are a monster," she says, without heat.')
        slow_print('  "A beautiful, empty monster."')
        slow_print("  She begins to dress. Her movements are precise,")
        slow_print("  mechanical, the gestures of a woman")
        slow_print("  who has already left the room in her mind.")
        slow_print(f"  {DIM}The honesty costs you nothing.{RESET}")
        slow_print(f"  {DIM}It costs her everything.{RESET}")
    elif choice == 2:
        state["ennui"] += 10
        state["liza_bond"] -= 5
        state["decisions"].append("told_liza_incapable")
        slow_print("\n  She stares at you for a long time.")
        slow_print('  "I know," she says. "I have always known.')
        slow_print("   Everyone sees it — the emptiness behind your eyes.")
        slow_print("   But I thought — I hoped — that with me,")
        slow_print('   something might —"')
        slow_print("  She stops. She will not finish the sentence.")
        slow_print("  To finish it would be to hear herself beg,")
        slow_print("  and Liza does not beg.")
        slow_print("  She sits very still, her hands in her lap.")
        slow_print(f"  {DIM}You watch a woman's last illusion die.{RESET}")
        slow_print(f"  {DIM}It makes the same sound as everything else:{RESET}")
        slow_print(f"  {DIM}silence.{RESET}")
    elif choice == 3:
        state["soul"] += 10
        state["liza_bond"] += 10
        state["ennui"] -= 5
        state["decisions"].append("held_lizas_hand")
        slow_print("\n  You take her hand. You say nothing.")
        slow_print("  She looks at your hand holding hers.")
        slow_print("  Something moves across her face —")
        slow_print("  not hope, exactly, but the memory of hope.")
        slow_print("  You sit together in the grey light.")
        slow_print("  For five minutes, perhaps ten, there is peace.")
        slow_print("  Not happiness. Not love. Just two people")
        slow_print("  sitting together in the ruins of everything.")
        slow_print(f"  {DIM}It is the most tender thing you have done in years.{RESET}")
        slow_print(f"  {DIM}It is also insufficient. It is always insufficient.{RESET}")
    elif choice == 4:
        state["ennui"] += 5
        state["soul"] += 5
        state["liza_bond"] += 5
        state["decisions"].append("told_liza_perhaps")
        slow_print('\n  "Perhaps," you say. And then: "I cannot tell')
        slow_print('   the difference anymore. Between love and its absence.')
        slow_print("   Between what I feel and what I perform.")
        slow_print('   I have been acting for so long that the actor"')
        slow_print('  "— has eaten the man," she finishes. "I know."')
        slow_print("  She looks at you with something that is not quite pity")
        slow_print("  and not quite contempt and not quite love.")
        slow_print("  It is, perhaps, the only honest emotion left in the room.")
        slow_print(f"  {DIM}Two people who cannot love, failing to love each other.{RESET}")
        slow_print(f"  {DIM}Dostoevsky would call this the human condition.{RESET}")

    # Pyotr arrives with news of the fire
    print()
    slow_print(f"  {RED}  Then: a knock at the door.{RESET}")
    slow_print(f"  {RED}  Pyotr Stepanovich. Of course.{RESET}")
    slow_print(f"  {RED}  He enters without waiting, sees Liza,{RESET}")
    slow_print(f"  {RED}  and his face arranges itself into something{RESET}")
    slow_print(f"  {RED}  between triumph and calculation.{RESET}")
    print()
    slow_print('  "There has been a fire," he says, almost cheerfully.')
    slow_print('  "The Zarechye district. And — well —')
    slow_print('   Captain Lebyadkin and his sister..."')
    slow_print("  He trails off. He is watching your face.")
    slow_print("  Liza understands before you do.")
    print()
    slow_print('  "The cripple?" she whispers. "Your wife?')
    slow_print('   She is dead?"')
    print()
    slow_print("  Pyotr says nothing. His silence is an answer.")
    slow_print("  Liza looks at you. Then at Pyotr. Then at you.")
    slow_print("  Something terrible assembles itself in her mind —")
    slow_print("  the connection between this death and this night,")
    slow_print("  between the convenient fire and the convenient lover.")
    print()
    slow_print('  "Did you — " she begins.')
    slow_print('  "No." But your voice comes too late, too flat.')
    print()
    slow_print("  She runs. Out of the room, out of the house,")
    slow_print("  into the grey morning, toward the smoke")
    slow_print("  still rising from the riverside quarter.")
    slow_print("  You do not follow. Pyotr watches you not follow.")
    print()
    slow_print(f"  {RED}  The fire. The Lebyadkin house.{RESET}")
    slow_print(f"  {RED}  Captain Lebyadkin and Marya Timofeyevna.{RESET}")
    slow_print(f"  {RED}  Their throats cut. Fedka's work.{RESET}")
    print()
    slow_print(f"  {DIM}  Your wife is dead.{RESET}")
    slow_print(f"  {DIM}  Murdered by a man you gave three roubles to.{RESET}" if state["took_fedkas_offer"] else f"  {DIM}  Murdered by a man Pyotr Verkhovensky unleashed.{RESET}")
    slow_print(f"  {DIM}  Or refused. It doesn't matter. She is dead.{RESET}")
    print()
    slow_print(f"  {DIM}Mavriky Nikolaevich will find Liza at the fire.{RESET}")
    slow_print(f"  {DIM}He will be waiting, loyal as always.{RESET}")
    slow_print(f"  {DIM}The crowd will recognize her — Stavrogin's woman —{RESET}")
    slow_print(f"  {DIM}and they will not be kind.{RESET}")

    state["marya_bond"] = 0

    clamp_stats()
    show_status()
    press_enter()


# ═══════════════════════════════════════════════════════════════
#  THE MURDER OF SHATOV
# ═══════════════════════════════════════════════════════════════

def chapter_9_shatov_murder():
    """Part III, Ch.5-6: The murder of Shatov and Kirillov's suicide."""
    clear_screen()
    print(f"""{RED}
                          {DIM}Night{RED}
             {DIM}Skvoreshniki Park     The Grotto{RED}

    /||\\      /||\\      /||\\      /||\\      /||\\
   /||||\\    /||||\\    /||||\\    /||||\\    /||||\\
  /||||||\\  /||||||\\  /||||||\\  /||||||\\  /||||||\\
  ||||||||  ||||||||  ||||||||  ||||||||  ||||||||
     ||        ||        ||        ||        ||

               o     o
              /|\\   /|\\
               o  o  o  o            {DIM}five men{RED}
              /|\\/|\\/|\\/|\\           {DIM}one victim{RED}
                   |
          ~~~~~~~~~~~~~~~~~~~~~~~~
         ~  ~  ~  ~ {WHITE}THE POND{RED} ~  ~  ~
        ~   ~   ~   ~   ~   ~   ~   ~
         ~  ~  ~  ~  ~  ~  ~  ~  ~
          ~~~~~~~~~~~~~~~~~~~~~~~~

          {DIM}A printing press that never existed.{RED}
          {DIM}A crime that cannot be undone.{RESET}
""")

    slow_print(f"  {BOLD}CHAPTER IX: A BUSY NIGHT{RESET}")
    print()
    slow_print("  You are not present for the murder.")
    slow_print("  But you know it is happening. You warned him.")
    if state["warned_shatov"]:
        slow_print(f"  {DIM}You warned him and it was not enough.{RESET}")
    print()
    slow_print("  At this moment, in Skvoreshniki park, by the grotto:")
    slow_print("  Pyotr Verkhovensky leads Shatov to a spot")
    slow_print("  where a printing press is supposedly buried.")
    slow_print("  Shatov bends down to dig.")
    slow_print("  Pyotr shoots him in the head.")
    print()
    slow_print("  Virginsky cries: 'It's not right! It's not right at all!'")
    slow_print("  They weigh the body with stones and sink it in the pond.")
    slow_print("  Shatov's cap is left behind — an extraordinary carelessness.")
    print()
    slow_print("  Shatov had just hours earlier held his newborn baby.")
    slow_print("  His estranged wife had returned to him.")
    slow_print("  For one night, he had been happy —")
    slow_print("  the only genuine happiness in this entire story.")
    slow_print("  And then: the knock on the door.")
    print()
    slow_print("  Meanwhile, Kirillov fulfills his promise.")
    slow_print("  He writes the note taking responsibility.")
    slow_print("  Pyotr dictates: 'I killed Shatov.'")
    slow_print("  Then Kirillov goes into the next room")
    slow_print("  and shoots himself.")
    print()
    slow_print("  His hand trembled. He bit Pyotr's finger first.")
    slow_print("  In the end, the logical suicide was not so logical.")
    slow_print("  In the end, the body made its own argument.")
    print()

    slow_print("  You are alone in your rooms at Skvoreshniki.")
    slow_print("  What do you do with this night?")

    choice = get_choice([
        "Write a letter. To Dasha. To anyone. Put words on paper.",
        "Walk to the bridge over the river. Stand in the dark.",
        "Sit in the dark. Let it press down on you.",
        "Prepare to leave. There is nothing left here.",
        "Go to the pond. Watch them do it.",
    ])

    if choice == 5:
        state["decisions"].append("watched_murder")
        game_over([
            "  You put on your coat. You walk through the park.",
            "  You know exactly where they will be — the grotto,",
            "  by the pond, where the printing press is supposedly buried.",
            "",
            "  You stand behind the birches. You watch.",
            "  Shatov arrives. He bends down to dig.",
            "  Pyotr raises the pistol.",
            "",
            "  Shatov sees you. In the last moment, past Pyotr's shoulder,",
            "  his eyes find yours in the dark.",
            '  "Stavrogin —" he says.',
            "",
            "  The pistol fires.",
            "",
            "  You watch them weigh the body with stones.",
            "  You watch them push it into the pond.",
            "  You do not move. You do not speak.",
            "  You are the audience for your own evil.",
            "",
            f"  {BOLD}THE WITNESS{RESET}",
            f"  {DIM}He saw you. In the last moment, he saw you watching.{RESET}",
        ])

    if choice == 1:
        state["soul"] += 5
        state["ennui"] -= 5
        state["decisions"].append("wrote_a_letter")
        slow_print("\n  You write. The pen scratches in the silence.")
        slow_print("  To Darya Pavlovna — Dasha — Shatov's sister.")
        slow_print("  The one person who offered to be your nurse,")
        slow_print("  your keeper, your last connection to anything human.")
        slow_print('  "Dear Darya Pavlovna — at one time you expressed')
        slow_print('   a wish to be my nurse. I am going away.')
        slow_print('   Will you go with me?"')
        slow_print("  You write about Uri, in Switzerland. A small house.")
        slow_print("  A dull place. Mountains that restrict vision and thought.")
        slow_print('  "I expect nothing of Uri. I am simply going."')
        slow_print(f"  {DIM}The letter runs to several pages.{RESET}")
        slow_print(f"  {DIM}You will not send it. Or you will. It does not matter.{RESET}")
    elif choice == 2:
        state["ennui"] += 15
        state["soul"] -= 5
        state["decisions"].append("stood_on_bridge")
        slow_print("\n  The bridge over the river. Three in the morning.")
        slow_print("  The water is black and fast and utterly indifferent.")
        slow_print("  You stand where Fedka stood, weeks ago,")
        slow_print("  offering to solve your problems with fire.")
        slow_print("  The railing is cold under your hands.")
        slow_print("  You think about Kirillov's logic —")
        slow_print("  the ultimate act of freedom, the proof of self-will.")
        slow_print("  But you are not Kirillov. You have no logic.")
        slow_print("  You have only this: the water, the cold, the dark.")
        slow_print(f"  {DIM}You stand there for an hour. Then two.{RESET}")
        slow_print(f"  {DIM}Then you walk home. Not out of hope.{RESET}")
        slow_print(f"  {DIM}Out of the same inertia that keeps the earth spinning.{RESET}")
    elif choice == 3:
        state["ennui"] += 20
        state["soul"] -= 10
        state["decisions"].append("sat_in_darkness")
        slow_print("\n  You sit in the dark of your rooms.")
        slow_print("  The house creaks around you. Skvoreshniki is old.")
        slow_print("  Somewhere your mother is awake, worrying.")
        slow_print("  Somewhere Shatov is at the bottom of a pond.")
        slow_print("  Somewhere Kirillov is cooling on the floor.")
        slow_print("  Somewhere Marya Timofeyevna's clean white dress")
        slow_print("  is stained with blood that is not her own.")
        slow_print("  The darkness presses down.")
        slow_print("  You let it.")
        slow_print(f"  {DIM}You have tried your strength everywhere.{RESET}")
        slow_print(f"  {DIM}As long as you were experimenting, it seemed infinite.{RESET}")
        slow_print(f"  {DIM}But to what to apply your strength —{RESET}")
        slow_print(f"  {DIM}that you have never seen, and do not see now.{RESET}")
    elif choice == 4:
        state["ennui"] += 10
        state["decisions"].append("prepared_to_leave")
        slow_print("\n  You pack a small bag. Almost nothing.")
        slow_print("  You have bought a house in the canton of Uri.")
        slow_print("  A narrow valley. Mountains that restrict thought.")
        slow_print("  You chose it because there was nothing there.")
        slow_print("  Not beauty. Not ugliness. Not ideas. Not people.")
        slow_print("  Just mountains and silence and a door you can close.")
        slow_print(f"  {DIM}I don't like vice and I didn't want it, you think.{RESET}")
        slow_print(f"  {DIM}My desires are too weak to guide me.{RESET}")
        slow_print(f"  {DIM}On a log one may cross a river but not on a chip.{RESET}")

    clamp_stats()
    show_status()
    press_enter()


# ═══════════════════════════════════════════════════════════════
#  SECRET CHAPTER: AT TIKHON'S (SUPPRESSED/DELETED CHAPTER)
# ═══════════════════════════════════════════════════════════════

def check_tikhon_unlock():
    """Check if the player has made enough soul-positive choices to unlock
    the secret Tikhon chapter. Requires at least 3 'humane' decisions."""
    humane_choices = [
        "accepted_the_slap", "seized_shatovs_arms",   # humility at the slap
        "protected_marya", "acknowledged_marya",       # genuine feeling for Marya
        "admitted_impostor",                            # honesty before the holy fool
        "believed_in_russia", "will_believe",          # reaching toward faith
        "struck_fedka",                                # rejecting the path of murder
        "greeted_stepan",                              # human warmth
        "acknowledged_kirillov",                       # connection to another soul
        "called_kirillov_mad",                         # choosing life over death-logic
        "asked_about_marya",                           # care for another person
        "offered_hand_to_gaganov",                     # mercy in the duel
        "fired_air_three_times",                       # refusing to wound
        "held_lizas_hand",                             # tenderness with Liza
        "refused_shatovs_blood",                       # refusing Pyotr's blood price
        "called_meeting_farce",                        # truth in the meeting
        "followed_shatov_out",                         # solidarity with Shatov
        "rescued_stepan",                              # saving Stepan at the fete
    ]
    count = sum(1 for d in state["decisions"] if d in humane_choices)
    return count >= 3


def chapter_secret_tikhon():
    """The suppressed chapter: 'At Tikhon's'. Stavrogin's confession."""
    clear_screen()

    # Dramatic reveal
    print(f"""{BLINK}{RED}
    ╔═══════════════════════════════════════════════════════╗
    ║                                                       ║
    ║         ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░         ║
    ║         ░                                   ░         ║
    ║         ░   S E C R E T   C H A P T E R     ░         ║
    ║         ░                                   ░         ║
    ║         ░         U N L O C K E D           ░         ║
    ║         ░                                   ░         ║
    ║         ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░         ║
    ║                                                       ║
    ╚═══════════════════════════════════════════════════════╝{RESET}
""")
    slow_print(f"  {DIM}This chapter was suppressed by the editor Katkov in 1872.{RESET}")
    slow_print(f"  {DIM}Dostoevsky never restored it in his lifetime.{RESET}")
    slow_print(f"  {DIM}It is the missing center of the novel —{RESET}")
    slow_print(f"  {DIM}the confession that explains everything.{RESET}")
    print()
    slow_print(f"  {DIM}Your choices have unlocked it.{RESET}")
    press_enter()

    clear_screen()
    print(f"""{YELLOW}
              _____       _____       _____
             /     \\     /     \\     /     \\
            | {WHITE}ICON{YELLOW}  |   | {WHITE}ICON{YELLOW}  |   | {WHITE}ICON{YELLOW}  |
            |  {WHITE}+{YELLOW}   |   |  {WHITE}+{YELLOW}   |   |  {WHITE}+{YELLOW}   |
             \\_____/     \\_____/     \\_____/
                |            |           |
               {YELLOW}*{YELLOW}            {YELLOW}*{YELLOW}           {YELLOW}*{YELLOW}
              {DIM}candle{YELLOW}       {DIM}candle{YELLOW}       {DIM}candle{YELLOW}

      {WHITE}THE BOGORODSKY MONASTERY{YELLOW}
     ______________________________________________
    |                                              |
    |    o                          o              |
    |   /|\\                        /|\\            |
    |   / \\                        / \\            |
    |  {DIM}Stavrogin{YELLOW}                   {DIM}Tikhon{YELLOW}            |
    |                                              |
    |   {DIM}A bare cell. A crucifix. Your pages.{YELLOW}       |
    |   {DIM}The old man reads in silence.{YELLOW}               |
    |______________________________________________|

    {DIM}This chapter was suppressed in 1872.{YELLOW}
    {DIM}Your choices have unlocked it.{RESET}
""")

    slow_print(f"  {BOLD}AT TIKHON'S — У ТИХОНА{RESET}")
    slow_print(f"  {DIM}(The Suppressed Chapter){RESET}")
    print()
    slow_print("  Before dawn. You leave Skvoreshniki on foot.")
    slow_print("  Not toward the town. The other direction —")
    slow_print("  toward the Bogorodsky monastery, three versts east,")
    slow_print("  where the retired Bishop Tikhon lives in a cell.")
    print()
    slow_print("  You have been told about Tikhon. A holy man,")
    slow_print("  some say; a lunatic, others say. He was retired")
    slow_print("  from his episcopal see due to illness and a certain")
    slow_print("  eccentricity of behavior. He receives visitors.")
    slow_print("  He listens. He has a stammer that appears and")
    slow_print("  disappears depending on what is said to him.")
    print()
    slow_print("  You carry in your breast pocket several sheets of paper,")
    slow_print("  closely written, folded and refolded many times.")
    slow_print("  Your written confession. You have been carrying it")
    slow_print("  for months. Perhaps years.")
    print()
    slow_print("  The monastery is quiet. An old monk leads you")
    slow_print("  through a corridor that smells of incense and cold stone.")
    slow_print("  Tikhon's door is open.")
    press_enter()

    clear_screen()
    print(f"""{YELLOW}
    ╔═══════════════════════════════════════════════════════╗
    ║                                                       ║
    ║     {WHITE}Tikhon's Cell{YELLOW}                                    ║
    ║                                                       ║
    ║     ┌──────────────────────────────────────┐          ║
    ║     │                                      │          ║
    ║     │    ☦       🕯                        │          ║
    ║     │                                      │          ║
    ║     │      ○                ○              │          ║
    ║     │     /|\\              /|\\             │          ║
    ║     │     / \\              / \\             │          ║
    ║     │    {WHITE}TIKHON{YELLOW}           {WHITE}STAVROGIN{YELLOW}          │          ║
    ║     │                                      │          ║
    ║     │    ┌────────────┐                    │          ║
    ║     │    │  ░░░░░░░░  │  {DIM}A small table.{YELLOW}    │          ║
    ║     │    │  ░░░░░░░░  │  {DIM}The pages lie{YELLOW}     │          ║
    ║     │    │  ░░░░░░░░  │  {DIM}between them.{YELLOW}     │          ║
    ║     │    └────────────┘                    │          ║
    ║     └──────────────────────────────────────┘          ║
    ║                                                       ║
    ╚═══════════════════════════════════════════════════════╝{RESET}
""")

    slow_print("  He is not what you expected.")
    slow_print("  Tall, lean, about fifty-five. An illness in his legs")
    slow_print("  gives him an uncertain gait. Long, narrow face.")
    slow_print("  His eyes are what strike you — clear, almost merry,")
    slow_print("  the eyes of a man who has looked at the worst of himself")
    slow_print("  and has not been destroyed by it.")
    print()
    slow_print('  "Sit down," Tikhon says. His voice is gentle.')
    slow_print("  On his table: a novel, a volume of Hegel,")
    slow_print("  and a breviary. An unusual combination.")
    slow_print('  "I have heard you are ill," you say.')
    slow_print('  "Ill enough," he replies, smiling.')
    print()
    slow_print("  You do not sit. You pace.")
    slow_print("  Tikhon watches with the patience of a man who has")
    slow_print("  seen a thousand confessions begin exactly like this —")
    slow_print("  with pacing, with anger, with the inability to begin.")
    print()
    slow_print("  Finally, you take out the pages.")
    slow_print("  You put them on the table without a word.")
    slow_print("  Tikhon looks at you, then at the pages.")
    slow_print("  He picks them up and begins to read.")
    print()

    slow_print(f"  {BOLD}The confession contains:{RESET}")
    slow_print(f"  {DIM}  In Petersburg, in a furnished room on Gorokhovaya Street,{RESET}")
    slow_print(f"  {DIM}  you lived next to a girl named Matryosha.{RESET}")
    slow_print(f"  {DIM}  She was eleven or twelve years old.{RESET}")
    slow_print(f"  {DIM}  Her mother beat her. She was thin and afraid.{RESET}")
    print()
    slow_print(f"  {DIM}  You committed an act of unspeakable evil against her.{RESET}")
    slow_print(f"  {DIM}  Not from desire. Not from compulsion.{RESET}")
    slow_print(f"  {DIM}  From the wish to test whether you could feel anything at all.{RESET}")
    print()
    slow_print(f"  {DIM}  Afterwards, she told you that she had killed God.{RESET}")
    slow_print(f"  {DIM}  You sat and waited. You heard a buzzing sound.{RESET}")
    slow_print(f"  {DIM}  A fly in the window. You examined the red spider{RESET}")
    slow_print(f"  {DIM}  on a geranium leaf and fell into a sort of reverie.{RESET}")
    print()
    slow_print(f"  {DIM}  When you went back, you knew what you would find.{RESET}")
    slow_print(f"  {DIM}  You saw her tiny fist shaking at you from behind the door.{RESET}")
    slow_print(f"  {DIM}  You walked away. You did not stop it.{RESET}")
    print()
    slow_print(f"  {DIM}  She hanged herself.{RESET}")
    print()
    slow_print(f"  {DIM}  You have never forgotten the red spider on the geranium.{RESET}")
    slow_print(f"  {DIM}  Or the fly. Or the tiny fist.{RESET}")
    slow_print(f"  {DIM}  You dream of them every night.{RESET}")
    slow_print(f"  {DIM}  This is why you feel nothing:{RESET}")
    slow_print(f"  {DIM}  you are already in hell.{RESET}")
    press_enter()

    clear_screen()
    print(f"""{YELLOW}
    ╔═══════════════════════════════════════════════════════╗
    ║                                                       ║
    ║     {WHITE}Tikhon reads. His face changes.{YELLOW}                   ║
    ║                                                       ║
    ╚═══════════════════════════════════════════════════════╝{RESET}
""")

    slow_print("  Tikhon reads slowly. His hands do not tremble.")
    slow_print("  But his face — you watch his face —")
    slow_print("  it passes through something.")
    slow_print("  Not disgust. Not horror.")
    slow_print("  Something worse: understanding.")
    print()
    slow_print("  When he finishes, he puts the pages down carefully.")
    slow_print("  A long silence. The candle flickers.")
    slow_print("  Somewhere in the monastery, a bell rings for matins.")
    print()
    slow_print('  "Can you forgive me?" you ask.')
    slow_print("  You are surprised to hear your own voice.")
    slow_print("  It sounds like someone else's.")
    print()
    slow_print("  Tikhon looks at you with those terrible, clear eyes.")
    slow_print('  "God can forgive all things," he says.')
    slow_print("  Then his stammer appears:")
    slow_print('  "B-but... the question is whether you can b-bear')
    slow_print('   your own forgiveness."')
    print()
    slow_print("  He pauses. When he speaks again, the stammer is gone.")
    slow_print("  His voice is quiet and precise:")
    print()
    slow_print(f'  {BOLD}"I see pride in this document."{RESET}')
    print()
    slow_print("  You stiffen.")
    print()
    slow_print('  "You confess not from repentance," Tikhon continues,')
    slow_print('  "but from the need for a new sensation.')
    slow_print('   You wish to publish this confession. You told me so.')
    slow_print('   You want to provoke them — society — into hating you.')
    slow_print('   You want their blows. Their disgust.')
    slow_print('   Because even their hatred would be something to feel."')
    print()

    choice = get_choice([
        '"You are wrong, old man."',
        "Say nothing. Let the words land.",
        '"Then what would you have me do?"',
        '"Perhaps you are right. Perhaps even this is vanity."',
    ])

    if choice == 1:
        state["ennui"] += 5
        state["soul"] += 5
        state["decisions"].append("denied_tikhons_truth")
        slow_print('\n  "Am I?" Tikhon says gently.')
        slow_print('  "Then tell me: in this confession,')
        slow_print('   you describe the child\'s suffering in great detail.')
        slow_print("   But your own? Almost nothing.")
        slow_print('   The style is cold. Almost literary.')
        slow_print('   You have made your sin into a document."')
        slow_print("  He pauses.")
        slow_print('  "There are even grammatical corrections in the margins."')
        slow_print(f"  {DIM}You look down. He is right. You corrected the prose.{RESET}")
        slow_print(f"  {DIM}Even your worst moment has been edited for style.{RESET}")
    elif choice == 2:
        state["soul"] += 15
        state["ennui"] -= 10
        state["decisions"].append("accepted_tikhons_truth")
        slow_print("\n  You say nothing. The silence fills the cell.")
        slow_print("  Tikhon watches you.")
        slow_print("  Something is happening in your chest —")
        slow_print("  not an emotion, exactly, but the space")
        slow_print("  where an emotion might be, if the walls came down.")
        slow_print("  It is the closest thing to feeling you have experienced")
        slow_print("  since Matryosha. Since the red spider.")
        slow_print(f"  {DIM}Tikhon sees it. His eyes are bright with tears.{RESET}")
        slow_print(f"  {DIM}Not pity. Recognition.{RESET}")
    elif choice == 3:
        state["soul"] += 20
        state["ennui"] -= 15
        state["decisions"].append("asked_tikhon_for_way")
        slow_print("\n  Tikhon leans forward. His whole face changes.")
        slow_print('  "There is a way. Not publication.')
        slow_print("   Not public degradation.")
        slow_print('   That is only pride wearing the mask of humility."')
        slow_print("  He speaks of an elder — a staretz —")
        slow_print("  living in a remote monastery.")
        slow_print('  "Submit yourself to his guidance.')
        slow_print("   Five years. Perhaps seven.")
        slow_print("   Not punishment — discipline.")
        slow_print('   The slow, patient work of rebuilding a soul."')
        slow_print("  He pauses.")
        slow_print('  "It will be the hardest thing you have ever done.')
        slow_print('   Harder than any duel. Harder than any confession.')
        slow_print('   Because it will be boring, and quiet,')
        slow_print('   and you will receive no admiration for it."')
        slow_print(f"  {DIM}Boring. Quiet. No admiration.{RESET}")
        slow_print(f"  {DIM}The perfect antidote to everything you are.{RESET}")
    elif choice == 4:
        state["soul"] += 10
        state["ennui"] -= 5
        state["decisions"].append("admitted_vanity")
        slow_print("\n  Tikhon's face softens with something close to wonder.")
        slow_print('  "You see it yourself. That is... that is more')
        slow_print('   than I expected. More than most can manage."')
        slow_print("  His stammer returns:")
        slow_print('  "The f-fact that you can see the pride in your')
        slow_print("   own confession means there is something")
        slow_print('   b-beneath the pride. Something alive."')
        slow_print(f"  {DIM}Something alive. Underneath all of it.{RESET}")
        slow_print(f"  {DIM}You are not sure you believe him.{RESET}")
        slow_print(f"  {DIM}But for the first time in years,{RESET}")
        slow_print(f"  {DIM}you want to.{RESET}")

    print()
    slow_print("  Then Tikhon says one more thing.")
    slow_print("  The thing that breaks you:")
    print()
    slow_print(f'  {BOLD}"I am most afraid for you," he says,')
    slow_print(f'  "because I am not sure you can bear their laughter.')
    slow_print(f'   You can bear their hatred. Their horror. Their pity.')
    slow_print(f'   But if they laugh — if even one person laughs —')
    slow_print(f'   you will commit a new crime to escape the shame.')
    slow_print(f'   A crime worse than what is written here."{RESET}')
    print()
    slow_print("  The words hit you like a blow.")
    slow_print("  Not because they are cruel.")
    slow_print("  Because they are true.")
    slow_print("  Because this old man in a bare cell has seen through")
    slow_print("  every mask, every performance, every layer of your")
    slow_print("  carefully constructed emptiness, and has found —")
    slow_print("  not nothing — but a terrified child hiding from laughter.")
    print()
    slow_print("  You stand. Your chair scrapes the stone floor.")
    slow_print("  Your hands are shaking.")
    print()
    slow_print('  "I will come back," you say.')
    slow_print("  Tikhon nods. He does not believe you.")
    slow_print("  Neither do you.")
    print()
    slow_print(f"  {DIM}You walk out into the dawn. The monastery bell{RESET}")
    slow_print(f"  {DIM}is still ringing. Smoke rises from the kitchen.{RESET}")
    slow_print(f"  {DIM}A monk is feeding chickens in the yard.{RESET}")
    slow_print(f"  {DIM}The world is ordinary. It is unbearable.{RESET}")
    print()
    slow_print(f"  {DIM}Dostoevsky's editor cut this chapter from the novel.{RESET}")
    slow_print(f"  {DIM}Perhaps because it revealed too much.{RESET}")
    slow_print(f"  {DIM}Perhaps because even fiction has limits{RESET}")
    slow_print(f"  {DIM}on how much truth it can bear.{RESET}")

    state["confessed_to_tikhon"] = True
    state["decisions"].append("went_to_tikhon")
    state["soul"] += 10
    state["ennui"] -= 10

    clamp_stats()
    show_status()
    press_enter()


# ═══════════════════════════════════════════════════════════════
#  THE AFTERMATH
# ═══════════════════════════════════════════════════════════════

def chapter_new_aftermath():
    """The town in the aftermath: arrests, collapse, confrontation."""
    clear_screen()
    print(f"""{CYAN}
  {WHITE}THE PROVINCIAL TOWN{CYAN}                     {DIM}Three Days Later{CYAN}
  ~~~~~~~~~~~~~~~~~~~

    .----.  .----.  .----.  .----.  .----.  .----.  .----.
    |    |  |    |  |    |  |    |  |    |  |    |  |    |
    | [] |  | [] |  | [] |  | [] |  | [] |  | [] |  | [] |
    |    |  |    |  |    |  |    |  |    |  |    |  |    |
    |____|  |____|  |____|  |____|  |____|  |____|  |____|
   __|  |___|  |___|  |___|  |___|  |___|  |___|  |__|
  |  ====  ====  ====  ====  ====  ====  ====  ====  |
  |___________________________________________________|
  {DIM}                  the main street{CYAN}

         o  o  o  o                   o  o
        /|\\/|\\/|\\/|\\                 /|\\/|\\
         {DIM}police{CYAN}                       {DIM}arrested{CYAN}

         .-------------------------------------------.
         | {DIM}Lyamshin breaks. Crawls to the station.{CYAN}   |
         | {DIM}The body in the pond. Arrests. Collapse.{CYAN}  |
         | {DIM}Varvara Petrovna: "I have no son."{CYAN}        |
         '-------------------------------------------'{RESET}
""")

    slow_print(f"  {BOLD}CHAPTER XII: THE AFTERMATH{RESET}")
    print()
    slow_print("  The town wakes up.")
    slow_print("  Not all at once — slowly, painfully,")
    slow_print("  the way a man wakes from a dream of falling")
    slow_print("  and discovers that the floor is real.")
    print()
    slow_print("  Lyamshin breaks first. He crawls to the police station")
    slow_print("  on his hands and knees at two in the morning,")
    slow_print("  sobbing so hard they cannot understand him.")
    slow_print("  When they finally piece together his confession,")
    slow_print("  the officer on duty crosses himself.")
    slow_print("  He has been in the service for twenty-three years.")
    slow_print("  He has never heard anything like this.")
    print()
    slow_print("  Then: the pond at Skvoreshniki park.")
    slow_print("  Divers go in at dawn. They find Shatov's body")
    slow_print("  weighted with stones, the cap left behind on the shore.")
    slow_print("  The pistol is still in his coat — Pyotr's mistake,")
    slow_print("  one of many, committed in haste and darkness.")
    print()
    slow_print("  The arrests come quickly after that.")
    slow_print("  Virginsky weeps when they take him. He says:")
    slow_print('  "It was not right! I said so at the time!')
    slow_print('   It was not right at all!"')
    slow_print("  Liputin is found packing his bags.")
    slow_print("  Tolkatchenko makes it as far as the train station.")
    slow_print("  Erkel says nothing. His face is blank —")
    slow_print("  the face of a young man who followed orders")
    slow_print("  because the orders were all he had.")
    print()
    slow_print("  And Pyotr Stepanovich?")
    slow_print("  Gone. Escaped by the evening train,")
    slow_print("  with forged papers and a third-class ticket.")
    slow_print("  He will resurface in Switzerland,")
    slow_print("  organizing the next revolution,")
    slow_print("  the next set of useful fools.")
    slow_print("  Men like Pyotr Verkhovensky are never caught.")
    slow_print("  They are too light. They float.")
    print()
    slow_print("  Liza is dead. Beaten by a crowd at the fire site.")
    slow_print("  Mavriky Nikolaevich carried her body home.")
    slow_print("  He did not speak for three days afterward.")
    print()
    slow_print("  The Governor resigns. Yulia Mihailovna has a nervous collapse.")
    slow_print("  The province has been shaken to its foundations,")
    slow_print("  and the foundations were never very deep.")
    print()
    slow_print("  And then your mother comes to see you.")
    press_enter()

    clear_screen()
    print(f"""{CYAN}
    ╔═══════════════════════════════════════════════════════╗
    ║                                                       ║
    ║     {WHITE}Varvara Petrovna Stavrogina{CYAN}                        ║
    ║     {DIM}stands in the doorway of your rooms.{CYAN}                ║
    ║                                                       ║
    ╚═══════════════════════════════════════════════════════╝{RESET}
""")

    slow_print("  Varvara Petrovna stands in the doorway of your rooms.")
    slow_print("  She is dressed in black. She is always dressed in black,")
    slow_print("  but now it looks different. Now it looks earned.")
    print()
    slow_print("  She has heard everything. The murders. The conspiracy.")
    slow_print("  Your involvement — or your proximity to involvement,")
    slow_print("  which in a provincial town amounts to the same thing.")
    slow_print("  Stepan Trofimovich has fled. Her oldest friend,")
    slow_print("  wandering the high road with an umbrella,")
    slow_print("  and she does not yet know where.")
    print()
    slow_print("  She looks at you. Her eyes are dry.")
    slow_print("  She has spent a lifetime defending you —")
    slow_print("  explaining, justifying, constructing elaborate fictions")
    slow_print("  around the void at the center of her son.")
    slow_print("  The nose-pulling. The ear-biting. The marriage.")
    slow_print("  She explained them all. She cannot explain this.")
    print()
    slow_print('  "They are saying things about you," she says.')
    slow_print("  Her voice is level. Too level.")
    slow_print('  "Terrible things. About the fire.')
    slow_print('   About the Lebyadkin woman. About Lizaveta Nikolaevna."')
    print()
    slow_print("  She waits. She is giving you one last chance")
    slow_print("  to explain, to deny, to perform the role of a son")
    slow_print("  who has done nothing wrong.")
    print()

    slow_print("  How do you face your mother?")

    choice = get_choice([
        '"I did not kill them, Mother. That much is true."',
        "Say nothing. Let her draw her own conclusions.",
        '"I am leaving. There is nothing more to discuss."',
        '"Everything they say is true. And worse besides."',
        '"I did it all. I planned everything. Send for the police."',
    ])

    if choice == 5:
        state["decisions"].append("false_confession")
        game_over([
            '  "I did it all," you say.',
            '  "The fire. The murders. The conspiracy.',
            '   I planned everything. Pyotr was my instrument.',
            '   Send for the police. Let them take me."',
            "",
            "  Your mother stares at you.",
            "  She knows you are lying. You can see it in her eyes.",
            "  She knows because she knows you — the real you,",
            "  the one who could never plan anything",
            "  because he has never wanted anything enough.",
            "",
            "  But she does not contradict you.",
            '  "If that is what you wish," she says.',
            "  Her voice is ice. Her back is straight.",
            "  She has always been the stronger one.",
            "",
            "  The police come. You confess to everything.",
            "  Not from repentance — from vanity.",
            "  The ultimate performance: becoming the demon",
            "  the town always feared you were.",
            "",
            f"  {BOLD}THE DEMON{RESET}",
            f"  {DIM}Even your confession was a lie. Especially your confession.{RESET}",
        ])

    if choice == 1:
        state["soul"] += 5
        state["ennui"] += 5
        state["decisions"].append("denied_to_mother")
        slow_print('\n  "I did not kill them," you say.')
        slow_print("  Varvara Petrovna searches your face.")
        slow_print("  She has always been able to read others —")
        slow_print("  but never you. You are the one text")
        slow_print("  that defeats her intelligence.")
        slow_print('  "But did you cause it?" she whispers.')
        slow_print("  You do not answer. The silence is enough.")
        slow_print("  She nods once, very slowly,")
        slow_print("  the way a person nods when the last door closes.")
        slow_print(f"  {DIM}She walks out without touching you.{RESET}")
        slow_print(f"  {DIM}She will never touch you again.{RESET}")
    elif choice == 2:
        state["ennui"] += 15
        state["decisions"].append("silent_before_mother")
        slow_print("\n  You say nothing. She stands in the doorway")
        slow_print("  for a very long time, waiting.")
        slow_print("  The clock on the mantel ticks.")
        slow_print("  Your silence fills the room like water filling a well.")
        slow_print("  Finally she turns to go.")
        slow_print("  At the door she pauses:")
        slow_print(f'  {DIM}"I have no son."{RESET}')
        slow_print("  The words fall into the room like stones.")
        slow_print("  She closes the door behind her very gently —")
        slow_print("  not a slam. Worse than a slam.")
        slow_print(f"  {DIM}The gentleness of it is unbearable.{RESET}")
    elif choice == 3:
        state["ennui"] += 10
        state["decisions"].append("told_mother_leaving")
        slow_print('\n  "I am leaving," you say. "I have a house in Switzerland.')
        slow_print('   In the canton of Uri. There is nothing left here."')
        slow_print("  Varvara Petrovna's composure cracks — just for a moment,")
        slow_print("  just a flash of something raw underneath")
        slow_print("  the armor of twenty years of propriety.")
        slow_print('  "Nicolas—"')
        slow_print('  "Do not," you say. Just that. Do not.')
        slow_print("  She swallows whatever she was going to say.")
        slow_print("  She straightens her back. She nods.")
        slow_print(f"  {DIM}The last conversation you will ever have with your mother{RESET}")
        slow_print(f"  {DIM}ends with a prohibition. Do not feel. Do not weep.{RESET}")
        slow_print(f"  {DIM}Do not be human in front of me.{RESET}")
    elif choice == 4:
        state["soul"] -= 10
        state["notoriety"] += 10
        state["decisions"].append("confessed_to_mother")
        slow_print('\n  "Everything they say is true," you say,')
        slow_print("  your voice perfectly level, perfectly empty.")
        slow_print('  "And worse besides."')
        slow_print("  Varvara Petrovna's face does not change.")
        slow_print("  Perhaps she always knew. Perhaps mothers always know.")
        slow_print("  Perhaps the elaborate fictions she built")
        slow_print("  around your behavior were never for others —")
        slow_print("  they were for herself. Walls against a truth")
        slow_print("  she could not afford to see.")
        slow_print("  She crosses herself. The gesture is automatic.")
        slow_print("  She walks out.")
        slow_print(f"  {DIM}You hear her footsteps on the stairs.{RESET}")
        slow_print(f"  {DIM}Slow. Measured. The footsteps of a woman{RESET}")
        slow_print(f"  {DIM}who has just buried her son while he is still alive.{RESET}")

    clamp_stats()
    show_status()
    press_enter()


# ═══════════════════════════════════════════════════════════════
#  STEPAN TROFIMOVICH'S LAST WANDERING
# ═══════════════════════════════════════════════════════════════

def chapter_10_stepan_wandering():
    """Part III, Ch.7: Stepan Trofimovich's Last Wandering."""
    clear_screen()
    print(f"""{GREEN}
                                    .       .       .
                *        .                      *
       .                       .        .                .

  /||\\    /||\\    /||\\    /||\\    /||\\    /||\\    /||\\    /||\\
  {DIM}willows{GREEN}   {DIM}willows{GREEN}   {DIM}willows{GREEN}   {DIM}willows{GREEN}   {DIM}willows{GREEN}   {DIM}willows{GREEN}

  ================================================================
  ================================================================
      {WHITE}THE HIGH ROAD{GREEN}
  ================================================================
  ================================================================

                     o
                    /|\\
                    / \\
                   {DIM}Stepan Trofimovich{GREEN}
                   {DIM}with an umbrella{GREEN}
                   {DIM}and no destination{GREEN}

  /||\\    /||\\    /||\\    /||\\    /||\\    /||\\    /||\\    /||\\

    {DIM}"All my life I have been lying. Even when I spoke the truth.{GREEN}
    {DIM} I never spoke for the sake of truth, only for my own sake."{RESET}
""")

    slow_print(f"  {BOLD}CHAPTER XIII: STEPAN TROFIMOVICH'S LAST WANDERING{RESET}")
    print()
    slow_print("  While the town tears itself apart, old Stepan Trofimovich")
    slow_print("  does the most extraordinary thing of his life:")
    slow_print("  he leaves.")
    print()
    slow_print("  Not in the way young men leave — with a plan,")
    slow_print("  a destination, a reason. He leaves the way a leaf")
    slow_print("  leaves a tree: because it is time, because the wind came,")
    slow_print("  because staying had become the only impossibility.")
    print()
    slow_print("  His travelling costume is magnificent and absurd.")
    slow_print("  He wears his best embroidered waistcoat,")
    slow_print("  the one Varvara Petrovna bought him in Paris.")
    slow_print("  Over this: a broad-brimmed hat. An umbrella.")
    slow_print("  A walking stick he has never used for walking.")
    slow_print("  His bag contains: two shirts, a French novel,")
    slow_print("  a lorgnette, and fifty roubles in small bills.")
    slow_print("  He does not know where he is going.")
    slow_print("  This is, perhaps, the point.")
    print()
    slow_print("  Twenty years of living on Varvara Petrovna's charity.")
    slow_print("  Twenty years of playing the exiled intellectual,")
    slow_print("  the persecuted liberal, the man of the forties")
    slow_print("  who once wrote a poem that may or may not")
    slow_print("  have been investigated by the authorities.")
    slow_print("  Twenty years of performing genius for a woman")
    slow_print("  who kept him like a hothouse flower.")
    slow_print("  And now — at last — he walks out onto the high road.")
    print()
    slow_print("  The road is black with wheel-ruts, planted with willows.")
    slow_print("  Rain drizzles. He opens his umbrella.")
    slow_print("  His shoes — city shoes, thin-soled, absurd —")
    slow_print("  are ruined within the first verst.")
    slow_print("  He does not notice. He is walking.")
    slow_print("  For the first time in twenty years,")
    slow_print("  he is moving under his own power,")
    slow_print("  toward no one's expectation.")
    print()
    slow_print("  A peasant with a cart passes him on the road.")
    slow_print('  "Where are you going, master?"')
    slow_print('  "I... I am going... somewhere," Stepan says.')
    slow_print('  "To Spasov? That is thirty versts."')
    slow_print('  "Thirty versts! Very well. I shall walk thirty versts."')
    slow_print("  The peasant stares at this old man in a waistcoat")
    slow_print("  and embroidered tie, with a walking stick and an umbrella,")
    slow_print("  mud to his ankles, heading nowhere at four miles an hour.")
    slow_print("  He crosses himself and drives on.")
    print()
    slow_print("  After five versts, Stepan Trofimovich collapses")
    slow_print("  under a tree. His feet are bleeding.")
    slow_print("  He has blisters on both heels.")
    slow_print("  He sits in the rain and weeps —")
    slow_print("  not from pain, but from a joy he cannot name.")
    slow_print(f'  {DIM}"I am free," he says to no one. "I am free at last."{RESET}')
    press_enter()

    clear_screen()
    print(f"""{GREEN}
    ╔═══════════════════════════════════════════════════════╗
    ║                                                       ║
    ║     {WHITE}A woman on the road. A Bible seller.{GREEN}              ║
    ║     {WHITE}Sofya Matveyevna.{GREEN}                                  ║
    ║                                                       ║
    ╚═══════════════════════════════════════════════════════╝{RESET}
""")

    slow_print("  On the road, by the town of Khatovo,")
    slow_print("  he meets a woman selling Bibles and Gospels.")
    slow_print("  Sofya Matveyevna — young, plain, gentle,")
    slow_print("  with the patient eyes of someone who has learned")
    slow_print("  to expect nothing from the world.")
    print()
    slow_print("  Stepan Trofimovich latches onto her immediately.")
    slow_print('  "My dear! My kind one! Will you read to me?')
    slow_print("   I have been wanting someone to read to me")
    slow_print('   for twenty years!"')
    slow_print("  She is bewildered but kind. She reads.")
    print()
    slow_print("  He talks to her as he has never talked to anyone.")
    slow_print("  Not performing. Not quoting Schiller.")
    slow_print("  Just talking — about his life, his son,")
    slow_print("  about Varvara Petrovna, about beauty.")
    slow_print('  "Je vous aimais," he says suddenly, in French.')
    slow_print('  "I loved her — Varvara Petrovna — all my life.')
    slow_print('   Twenty years! And I never told her."')
    slow_print("  His eyes are bright with tears.")
    slow_print('  "Twenty years of living beside her')
    slow_print("   and I was too proud, too absurd,")
    slow_print('   too much the great man to simply say: I love you."')
    print()
    slow_print("  Sofya Matveyevna does not understand French.")
    slow_print("  But she understands weeping. She holds his hand.")
    print()
    slow_print("  He asks her to read from Luke. Chapter eight.")
    slow_print("  The passage about the Gadarene swine:")
    slow_print("  the demons that entered the herd and drove them")
    slow_print("  headlong over the cliff into the sea.")
    print()
    slow_print("  She reads. His face changes.")
    slow_print("  Something vast is assembling itself behind his eyes.")
    print()
    slow_print('  "These demons," he whispers,')
    slow_print("  seizing Sofya Matveyevna's hand,")
    slow_print('  "that is us. All of us.')
    slow_print("   Pyotr, and I, and perhaps Stavrogin,")
    slow_print("   and all the others — Shatov, Kirillov,")
    slow_print("   poor Virginsky, all of them.")
    slow_print("   We are the sick man's demons,")
    slow_print("   entering the swine!")
    slow_print("   And the swine will rush down the cliff")
    slow_print('   and be drowned!"')
    print()
    slow_print("  He is weeping openly now. Sofya Matveyevna is frightened.")
    slow_print("  But he grips her hand tighter:")
    print()
    slow_print(f'  {BOLD}"But the sick man will be healed!{RESET}')
    slow_print(f'  {BOLD} And he will sit at the feet of Jesus,')
    slow_print(f'   and all will look upon him with astonishment!"{RESET}')
    print()
    slow_print("  It is the epigraph of the novel.")
    slow_print("  It is the meaning of the novel.")
    slow_print("  And it has taken Stepan Trofimovich his whole ridiculous life")
    slow_print("  to arrive at it — on a muddy road, in ruined shoes,")
    slow_print("  holding the hand of a stranger.")
    print()

    slow_print("  You encounter Stepan on the road. What do you do?")

    choice = get_choice([
        "Sit with him. Listen to his reading of Luke.",
        "Offer him your coat. He is shivering in the rain.",
        "Tell him Varvara Petrovna is looking for him.",
        "Pass by. This is his journey, not yours.",
    ])

    if choice == 1:
        state["soul"] += 15
        state["stepan_bond"] += 15
        state["ennui"] -= 10
        state["decisions"].append("sat_with_stepan")
        slow_print("\n  You sit beside him on the muddy road.")
        slow_print("  Sofya Matveyevna reads, and you listen.")
        slow_print("  The words wash over you — demons, swine, healing.")
        slow_print("  Stepan Trofimovich looks at you with shining eyes.")
        slow_print('  "Nicolas... you came. You are here."')
        slow_print('  "I am here, Stepan Trofimovich."')
        slow_print('  "Do you hear it? The sick man will be healed.')
        slow_print('   Russia will be healed. Even you, perhaps."')
        slow_print("  You do not believe him. But sitting beside him")
        slow_print("  in the mud and the rain, listening to Luke,")
        slow_print("  you feel something you had forgotten existed:")
        slow_print("  the warmth of another person's faith.")
        slow_print(f"  {DIM}It is not yours. But you can feel it from here.{RESET}")
    elif choice == 2:
        state["soul"] += 10
        state["stepan_bond"] += 10
        state["decisions"].append("gave_stepan_coat")
        slow_print("\n  You take off your coat and put it around his shoulders.")
        slow_print("  He looks up at you, startled.")
        slow_print('  "Nicolas! You will catch cold!"')
        slow_print('  "You are an old man on a road in the rain.')
        slow_print('   Take the coat."')
        slow_print("  He begins to weep again — but differently now.")
        slow_print("  Not the theatrical weeping of twenty years")
        slow_print("  of provincial salon life. Real tears.")
        slow_print("  The tears of a man being cared for")
        slow_print("  by someone he thought had forgotten how.")
        slow_print(f"  {DIM}It is the smallest gesture. A coat.{RESET}")
        slow_print(f"  {DIM}And yet it is the largest thing you have done all year.{RESET}")
    elif choice == 3:
        state["stepan_bond"] += 5
        state["ennui"] += 5
        state["decisions"].append("told_stepan_about_varvara")
        slow_print('\n  "She is looking for you," you say.')
        slow_print("  Stepan Trofimovich's face changes —")
        slow_print("  fear, hope, and love all fighting for dominance.")
        slow_print('  "Varvara Petrovna? She is... looking?"')
        slow_print('  "She has sent people out on every road."')
        slow_print("  He sits very still. Then a kind of peace settles over him.")
        slow_print('  "Then she will find me," he says softly.')
        slow_print('  "She always finds me."')
        slow_print(f"  {DIM}It is the most hopeful thing anyone has said in this story.{RESET}")
        slow_print(f"  {DIM}It is also the most accurate.{RESET}")
    elif choice == 4:
        state["ennui"] += 10
        state["decisions"].append("passed_stepan_by")
        slow_print("\n  You walk past. He does not call out.")
        slow_print("  Perhaps he does not see you.")
        slow_print("  Perhaps he has already left this world")
        slow_print("  for whatever world he is traveling toward.")
        slow_print("  His umbrella bobs in the rain.")
        slow_print("  His voice carries behind you,")
        slow_print("  reading Luke to a stranger.")
        slow_print(f"  {DIM}You do not look back.{RESET}")
        slow_print(f"  {DIM}You are very good at not looking back.{RESET}")
        slow_print(f"  {DIM}It is perhaps your only genuine skill.{RESET}")

    print()
    slow_print("  That evening, Stepan Trofimovich collapses.")
    slow_print("  Varvara Petrovna arrives the next morning.")
    slow_print("  She finds him in a peasant cottage,")
    slow_print("  burning with fever, holding Sofya Matveyevna's hand.")
    print()
    slow_print('  "Darling," he says. In twenty years')
    slow_print("  he has never called her that.")
    slow_print("  She sits by his bed. She takes his hand.")
    slow_print("  He confesses to a priest. He weeps.")
    slow_print("  He tells Varvara Petrovna he loved her.")
    slow_print("  She knows. She has always known.")
    print()
    slow_print("  He dies the next morning, having confessed,")
    slow_print("  having wept, having loved, having been ridiculous")
    slow_print("  and sincere and utterly, finally, himself.")
    print()
    slow_print(f"  {DIM}He is the only character in this story who dies well.{RESET}")
    slow_print(f"  {DIM}The only one who finds, at the end, something real.{RESET}")
    slow_print(f"  {DIM}Not because he was wise — he was absurd.{RESET}")
    slow_print(f"  {DIM}Not because he was brave — he was terrified.{RESET}")
    slow_print(f"  {DIM}Because he walked out the door.{RESET}")

    clamp_stats()
    show_status()
    press_enter()


# ═══════════════════════════════════════════════════════════════
#  THE LAST NIGHT — FINAL BOSS
# ═══════════════════════════════════════════════════════════════

def chapter_final_boss():
    """The psychological gauntlet. Stavrogin's last night alive."""
    clear_screen()
    print(f"""{CYAN}
  {WHITE}Night  |  Skvoreshniki  |  Your Rooms{CYAN}

     __________________________________________________________
    |                                                          |
    |     {YELLOW}*{CYAN}                                                    |
    |    {DIM}candle{CYAN}                                                  |
    |                                                          |
    |    .-----------.                                         |
    |    | {WHITE}a letter{CYAN}  |    {DIM}half-written{CYAN}                          |
    |    | {WHITE}to Dasha{CYAN}  |    {DIM}the pen still wet{CYAN}                     |
    |    '-----------'                                         |
    |                                                          |
    |        o          o       o        o         o           |
    |       /|\\        /|\\     /|\\      /|\\       /|\\         |
    |       / \\        / \\     / \\      / \\       / \\         |
    |     {DIM}Shatov{CYAN}    {DIM}Kirillov{CYAN}  {DIM}Marya{CYAN}  {DIM}Lebyadkin{CYAN}   {DIM}Liza{CYAN}        |
    |                                                          |
    |      {DIM}five ghosts     who will not leave{CYAN}                  |
    |__________________________________________________________|

    {DIM}Everyone you have touched. Everyone you have broken.{CYAN}
    {DIM}They are all here tonight.{RESET}
""")

    slow_print(f"  {BOLD}THE LAST NIGHT{RESET}")
    print()
    slow_print("  It is your last night alive. You know this.")
    slow_print("  Not as a premonition — as a decision already made,")
    slow_print("  calmly, the way one decides to take a train.")
    print()
    slow_print("  You sit at your desk at Skvoreshniki.")
    slow_print("  The letter to Dasha is half-written.")
    slow_print("  The candle burns. The house is silent.")
    print()
    slow_print("  And then they come.")
    slow_print("  Not ghosts. Not apparitions.")
    slow_print("  Memories so vivid they have voices.")
    slow_print("  The people whose lives you shaped — or shattered —")
    slow_print("  each making a claim on the emptiness at your center.")
    print()
    slow_print(f"  {DIM}Five confrontations stand between you and the loft.{RESET}")
    slow_print(f"  {DIM}What you built — or failed to build — determines{RESET}")
    slow_print(f"  {DIM}whether you can answer them.{RESET}")
    print()

    confrontations = 0

    press_enter()

    # ─── ROUND 1: SHATOV ─────────────────────────────────────

    clear_screen()
    print(f"""{CYAN}
    ╔═════════════════════════════════════╗
    ║  {WHITE}I — SHATOV — "The Question"{CYAN}        ║
    ╚═════════════════════════════════════╝{RESET}
""")

    slow_print("  He appears as he was in the garret.")
    slow_print("  Before the park. Before the pond.")
    slow_print("  Before the five of them held him down in the dark.")
    print()
    slow_print("  He is standing by your desk, shaking slightly,")
    slow_print("  the way he always shook — from feeling too much,")
    slow_print("  never too little.")
    print()
    slow_print(f'  {BOLD}"Do you believe in God, Stavrogin?"{RESET}')
    print()
    slow_print("  But this time it is not a philosophical question.")
    slow_print("  This time it is asked by a man who was murdered")
    slow_print("  on the night his wife gave birth to a child")
    slow_print("  he believed was yours.")
    print()

    shatov_locked = state["shatov_bond"] >= 15

    if shatov_locked:
        print(f'  {GREEN}[1] "I wanted to believe. I could not. But I heard you, Ivan."{RESET}')
    else:
        print(f'  {DIM}[1] [Requires stronger bond with Shatov]{RESET}')
    print(f'  [2] "I told you the truth. I do not believe."')
    print(f'  [3] Say nothing.')
    print()

    _reset_skip()
    while True:
        try:
            c = input(f"  {GREEN}Your answer (1-3): {RESET}").strip()
            if c == "1" and shatov_locked:
                state["soul"] += 15
                confrontations += 1
                state["decisions"].append("answered_shatov")
                print()
                slow_print("  Something shifts in his face.")
                slow_print("  The shaking stops.")
                slow_print('  "Then it was not all for nothing," he says.')
                slow_print("  His voice is steady. His eyes are clear.")
                slow_print("  He was always the bravest of them all —")
                slow_print("  the one who believed without proof.")
                slow_print("  For one moment, you were worthy of his question.")
                break
            elif c == "1" and not shatov_locked:
                print(f"  {DIM}You cannot choose this. The bond was never built.{RESET}")
                continue
            elif c == "2":
                state["ennui"] += 10
                state["soul"] -= 5
                state["decisions"].append("denied_shatov_again")
                print()
                slow_print("  Honest, at least. The truth you always told.")
                slow_print('  He nods slowly. "I know," he says.')
                slow_print("  But knowing does not help him.")
                slow_print("  He turns away. You hear his footsteps")
                slow_print("  on stairs that no longer exist.")
                break
            elif c == "3":
                state["ennui"] += 15
                state["decisions"].append("silent_before_shatov")
                print()
                slow_print("  You reach for something to say and find only emptiness.")
                slow_print("  The silence stretches. He waits.")
                slow_print("  He has always waited for you — for the answer,")
                slow_print("  for the sign, for the faith you could not give.")
                slow_print("  He waited until the night by the pond.")
                slow_print("  He is still waiting.")
                break
        except (ValueError, EOFError):
            continue

    clamp_stats()
    print()
    press_enter()

    # ─── ROUND 2: KIRILLOV ───────────────────────────────────

    clear_screen()
    print(f"""{CYAN}
    ╔═════════════════════════════════════╗
    ║  {WHITE}II — KIRILLOV — "The Proof"{CYAN}        ║
    ╚═════════════════════════════════════╝{RESET}
""")

    slow_print("  He appears bouncing his india-rubber ball.")
    slow_print("  Catch, bounce, catch. The rhythm of a man")
    slow_print("  who has resolved the problem of existence")
    slow_print("  and found the answer is a pistol.")
    print()
    slow_print("  He looks at you with that odd, gentle clarity —")
    slow_print("  the face of someone who has already stepped")
    slow_print("  beyond fear, beyond hope, into pure logic.")
    print()
    slow_print(f'  {BOLD}"I proved my freedom. I acted."{RESET}')
    slow_print(f'  {BOLD}"What have you done with yours, Stavrogin?"{RESET}')
    print()
    slow_print("  His logic is still perfect. Still insane.")
    slow_print("  But from the other side, it carries a different weight.")
    slow_print("  He did what he said he would do.")
    slow_print("  That is more than you have ever managed.")
    print()

    kirillov_locked = state["soul"] >= 60

    if kirillov_locked:
        print(f'  {GREEN}[1] "You were braver than I am, Kirillov. I see that now."{RESET}')
    else:
        print(f'  {DIM}[1] [Requires higher soul]{RESET}')
    print(f'  [2] "Your logic destroyed you."')
    print(f'  [3] "Freedom without purpose is just another prison."')
    print()

    _reset_skip()
    while True:
        try:
            c = input(f"  {GREEN}Your answer (1-3): {RESET}").strip()
            if c == "1" and kirillov_locked:
                state["soul"] += 10
                state["ennui"] -= 10
                confrontations += 1
                state["decisions"].append("honored_kirillov")
                print()
                slow_print("  His face changes.")
                slow_print("  The ball stops bouncing.")
                slow_print("  For a moment you see it — the five seconds")
                slow_print("  of eternal harmony he described that night,")
                slow_print("  the leaf, the spider's web, the sunlight.")
                slow_print("  He smiles. It is the rarest thing in the world:")
                slow_print("  Kirillov's smile, unguarded, fully human.")
                slow_print('  "Then you understand," he says.')
                break
            elif c == "1" and not kirillov_locked:
                print(f"  {DIM}You cannot choose this. The soul is too corroded.{RESET}")
                continue
            elif c == "2":
                state["ennui"] += 5
                state["decisions"].append("dismissed_kirillovs_proof")
                print()
                slow_print("  He bounces the ball twice.")
                slow_print("  The sound echoes in the empty room.")
                slow_print('  "You are afraid," he says simply.')
                slow_print("  He is right. You are afraid of everything.")
                slow_print("  Even of the logic that would set you free.")
                break
            elif c == "3":
                state["soul"] += 5
                state["ennui"] += 5
                state["decisions"].append("questioned_kirillovs_freedom")
                print()
                slow_print("  He considers this. The ball bounces.")
                slow_print('  "Perhaps," he says. "But I chose my prison.')
                slow_print('   You — you cannot even choose."')
                slow_print("  The distinction is devastating")
                slow_print("  precisely because it is accurate.")
                break
        except (ValueError, EOFError):
            continue

    clamp_stats()
    print()
    press_enter()

    # ─── ROUND 3: MARYA TIMOFEYEVNA ──────────────────────────

    clear_screen()
    print(f"""{CYAN}
    ╔═════════════════════════════════════╗
    ║  {WHITE}III — MARYA — "The Impostor"{CYAN}       ║
    ╚═════════════════════════════════════╝{RESET}
""")

    slow_print("  She appears in her clean white dress.")
    slow_print("  The holy fool. The lame one. Your wife.")
    slow_print("  She is dead now — burned in the fire")
    slow_print("  with her brother, the captain, who wept over her")
    slow_print("  even as he drank away the money you sent.")
    print()
    slow_print("  She looks through you the way she always did —")
    slow_print("  past the handsome face, past the officer's bearing,")
    slow_print("  past everything the world sees, to the thing")
    slow_print("  the world does not.")
    print()
    slow_print(f'  {BOLD}"You are not my prince."{RESET}')
    slow_print(f"  She knew that from the beginning.")
    slow_print(f'  {BOLD}"But I have a question for you, impostor:"{RESET}')
    slow_print(f'  {BOLD}"Did you ever love anyone? Even once? Even badly?"{RESET}')
    print()

    marya_locked = state.get("marya_bond_peak", 0) >= 10

    if marya_locked:
        print(f'  {GREEN}[1] "I loved you. Not well. Not enough. But it was not nothing."{RESET}')
    else:
        print(f'  {DIM}[1] [Requires deeper bond with Marya — now lost]{RESET}')
    print(f'  [2] "I married you on a dare. I am sorry."')
    print(f'  [3] "No. I have never loved anyone."')
    print()

    _reset_skip()
    while True:
        try:
            c = input(f"  {GREEN}Your answer (1-3): {RESET}").strip()
            if c == "1" and marya_locked:
                state["soul"] += 15
                confrontations += 1
                state["decisions"].append("loved_marya")
                print()
                slow_print("  Her face softens.")
                slow_print("  Not forgiveness — she is beyond that —")
                slow_print("  but the pity she showed in life.")
                slow_print("  The pity of the holy fool who sees everything")
                slow_print("  and judges nothing.")
                slow_print('  "Poor prince," she says. Not impostor. Prince.')
                slow_print("  It is the kindest thing anyone has ever called you.")
                slow_print("  And you married her on a dare. And she is dead.")
                break
            elif c == "1" and not marya_locked:
                print(f"  {DIM}You cannot choose this. The bond was never built — and now she is ash.{RESET}")
                continue
            elif c == "2":
                state["soul"] += 5
                state["ennui"] += 5
                state["decisions"].append("apologized_to_marya")
                print()
                slow_print("  She tilts her head, considering.")
                slow_print('  "Sorry," she repeats, tasting the word.')
                slow_print('  "Yes. You are that. Sorry."')
                slow_print("  She is not cruel. But the holy fool tells the truth.")
                slow_print("  Sorry is all you are, and all you have.")
                break
            elif c == "3":
                state["ennui"] += 15
                state["soul"] -= 10
                state["decisions"].append("admitted_lovelessness")
                print()
                slow_print('  "Poor impostor," she says, and turns away.')
                slow_print("  Her white dress vanishes into the dark")
                slow_print("  like smoke from the fire that killed her.")
                slow_print("  You married her on a bet. She died in a fire.")
                slow_print("  And you have never loved anyone.")
                slow_print("  The emptiness is so complete it is almost admirable.")
                break
        except (ValueError, EOFError):
            continue

    clamp_stats()
    print()
    press_enter()

    # ─── ROUND 4: PYOTR VERKHOVENSKY ─────────────────────────

    clear_screen()
    print(f"""{CYAN}
    ╔═════════════════════════════════════╗
    ║  {WHITE}IV — PYOTR — "The Worm"{CYAN}            ║
    ╚═════════════════════════════════════╝{RESET}
""")

    slow_print("  He appears clutching your sleeve, eyes bright.")
    slow_print("  He always did that — clutched, grasped, pulled —")
    slow_print("  the way a vine wraps around whatever is nearest.")
    print()
    slow_print("  This is the most dangerous round.")
    slow_print("  Pyotr does not accuse. He does not plead.")
    slow_print("  He tempts.")
    print()
    slow_print(f'  {BOLD}"It is not too late!"{RESET} His voice is urgent, ecstatic.')
    slow_print(f'  {BOLD}"You can still be Ivan the Tsarevitch!{RESET}')
    slow_print(f'  {BOLD} Columbus has found his America!{RESET}')
    slow_print(f'  {BOLD} You are the leader — you are the sun —{RESET}')
    slow_print(f'  {BOLD} and I am your worm!"{RESET}')
    print()
    slow_print("  His face is the face of a man in love.")
    slow_print("  Not with you — with the idea of you.")
    slow_print("  With the idol he has built from your indifference")
    slow_print("  and called it strength.")
    print()

    pyotr_locked = state["pyotr_entangled"] <= 10

    if pyotr_locked:
        print(f'  {GREEN}[1] "You are a fly, Pyotr. And I am not your America."{RESET}')
    else:
        print(f'  {DIM}[1] [Requires less entanglement with Pyotr]{RESET}')
    print(f'  [2] "Perhaps you are right. Perhaps it was always your game."')
    print(f'  [3] Pull your hand away. Say nothing.')
    print()

    _reset_skip()
    while True:
        try:
            c = input(f"  {GREEN}Your answer (1-3): {RESET}").strip()
            if c == "1" and pyotr_locked:
                state["pyotr_entangled"] -= 20
                state["soul"] += 10
                confrontations += 1
                state["decisions"].append("refused_pyotr_finally")
                print()
                slow_print("  He recoils.")
                slow_print("  Something raw crosses his face — almost human.")
                slow_print("  The grief of a man whose idol has spoken")
                slow_print("  and said: No. Definitively, finally: No.")
                slow_print("  His fingers release your sleeve.")
                slow_print("  For the first time since he arrived in this town,")
                slow_print("  Pyotr Stepanovich has nothing to say.")
                slow_print("  He shrinks. The worm becomes a worm.")
                break
            elif c == "1" and not pyotr_locked:
                print(f"  {DIM}You cannot choose this. You are too entangled in his web.{RESET}")
                continue
            elif c == "2":
                state["pyotr_entangled"] += 10
                state["revolutionary_fervor"] += 10
                state["decisions"].append("yielded_to_pyotr")
                print()
                slow_print("  His eyes light up. The fingers tighten.")
                slow_print('  "I knew it! I always knew!"')
                slow_print("  He is wrong, of course. It was never his game.")
                slow_print("  It was nobody's game. That is the horror.")
                slow_print("  But now, in your last hours, you have given him")
                slow_print("  exactly what he wanted: permission to believe")
                slow_print("  you were what he needed you to be.")
                break
            elif c == "3":
                state["ennui"] += 10
                state["decisions"].append("silent_before_pyotr")
                print()
                slow_print("  You pull your hand away.")
                slow_print("  But he keeps clutching. He always keeps clutching.")
                slow_print("  Even now, even here, even on your last night,")
                slow_print("  you cannot quite shake him off.")
                slow_print("  He will follow you everywhere.")
                slow_print("  Even into the loft.")
                break
        except (ValueError, EOFError):
            continue

    clamp_stats()
    print()
    press_enter()

    # ─── ROUND 5: STEPAN TROFIMOVICH ─────────────────────────

    clear_screen()
    print(f"""{CYAN}
    ╔═════════════════════════════════════╗
    ║  {WHITE}V — STEPAN — "The Healing"{CYAN}         ║
    ╚═════════════════════════════════════╝{RESET}
""")

    slow_print("  Your old tutor appears last.")
    slow_print("  He is wearing his best waistcoat —")
    slow_print("  the one he wore to the fête, the one")
    slow_print("  he wore on the road, the one he died in.")
    slow_print("  He is holding a book. The Gospel of Luke.")
    print()
    slow_print("  He does not accuse. He does not tempt.")
    slow_print("  He reads.")
    print()
    slow_print(f'  {DIM}"And there was there one herd of many swine')
    slow_print(f'   feeding on the mountain; and they besought him')
    slow_print(f'   that he would suffer them to enter into them.')
    slow_print(f'   And he suffered them."{RESET}')
    print()
    slow_print("  He looks up from the book.")
    slow_print("  His eyes are wet. They were always wet.")
    slow_print("  Twenty years he was your tutor. Twenty years")
    slow_print("  he taught you French and let you down")
    slow_print("  and loved you in the clumsy, insufficient way")
    slow_print("  that is the only way he knows.")
    print()
    slow_print(f'  {BOLD}"The sick man will be healed, Nicolas."{RESET}')
    slow_print(f'  {BOLD}"Will you be healed?"{RESET}')
    print()

    stepan_locked = state["stepan_bond"] >= 15

    if stepan_locked:
        print(f'  {GREEN}[1] "Read to me, Stepan Trofimovich. I am listening."{RESET}')
    else:
        print(f'  {DIM}[1] [Requires stronger bond with Stepan]{RESET}')
    print(f'  [2] "You were always ridiculous, old man. And always right."')
    print(f'  [3] "Beauty will not save the world. It did not save you."')
    print()

    _reset_skip()
    while True:
        try:
            c = input(f"  {GREEN}Your answer (1-3): {RESET}").strip()
            if c == "1" and stepan_locked:
                state["soul"] += 20
                state["ennui"] -= 15
                confrontations += 1
                state["decisions"].append("heard_the_gospel")
                print()
                slow_print("  He reads.")
                slow_print("  And you listen.")
                print()
                slow_print(f'  {DIM}"And the man out of whom the devils were departed{RESET}')
                slow_print(f'  {DIM} sat at the feet of Jesus, clothed{RESET}')
                slow_print(f'  {DIM} and in his right mind...{RESET}')
                slow_print(f'  {DIM} and they were afraid."{RESET}')
                print()
                slow_print("  For one moment — just one —")
                slow_print("  the emptiness recedes.")
                slow_print("  Not gone. Not healed. But held at bay")
                slow_print("  by the voice of a ridiculous old man")
                slow_print("  reading the words that matter.")
                slow_print("  It is the closest you have ever come to grace.")
                break
            elif c == "1" and not stepan_locked:
                print(f"  {DIM}You cannot choose this. You never built that bond.{RESET}")
                continue
            elif c == "2":
                state["soul"] += 10
                state["stepan_bond"] += 5
                state["decisions"].append("called_stepan_right")
                print()
                slow_print("  He smiles through his tears.")
                slow_print('  "Ridiculous! Yes! Always ridiculous!"')
                slow_print("  He laughs. It is genuine — the laugh")
                slow_print("  of a man who has been seen truly")
                slow_print("  and not found entirely wanting.")
                slow_print("  But he wanted more for you than accuracy.")
                slow_print("  He wanted you to listen.")
                break
            elif c == "3":
                state["ennui"] += 15
                state["soul"] -= 10
                state["decisions"].append("rejected_stepans_healing")
                print()
                slow_print("  He weeps.")
                slow_print("  He closes the book.")
                slow_print("  He walks away, slowly, leaning on his umbrella,")
                slow_print("  back into the darkness from which he came.")
                slow_print("  You are left alone in the silence.")
                slow_print("  The candle gutters. The letter waits.")
                slow_print("  There is no one left to read to you.")
                break
        except (ValueError, EOFError):
            continue

    clamp_stats()
    print()

    # ─── THE LETTER ───────────────────────────────────────────

    state["confrontations_survived"] = confrontations

    press_enter()
    clear_screen()
    print(f"""{CYAN}
    ╔═════════════════════════════════════╗
    ║  {WHITE}THE LETTER TO DASHA{CYAN}                ║
    ╚═════════════════════════════════════╝{RESET}
""")

    slow_print("  They are gone. All of them.")
    slow_print("  The room is empty again. The candle burns low.")
    slow_print("  You sit down and finish the letter.")
    print()

    if confrontations <= 1:
        # Cold, clinical — the novel's actual tone
        slow_print(f'  {DIM}"Dear Darya Pavlovna,"{RESET}')
        print()
        slow_print(f'  {DIM}"I have tried my strength everywhere.')
        slow_print(f'   You advised me to do this, that I might learn')
        slow_print(f'   to know myself. In testing myself for you')
        slow_print(f'   and for them, I found my desires are too weak;')
        slow_print(f'   they cannot guide me."{RESET}')
        print()
        slow_print(f'  {DIM}"On a log one may cross a river')
        slow_print(f'   but not on a chip."{RESET}')
        print()
        slow_print("  The letter is perfect. Cold. Clinical.")
        slow_print("  A spiritual autopsy performed by the patient himself.")
        slow_print("  There is no warmth in it. No crack in the armor.")
        slow_print("  Just the precision of a man who has measured his own void")
        slow_print("  and found the dimensions exact.")
    elif confrontations <= 3:
        # Flickers of self-awareness
        slow_print(f'  {DIM}"Dear Darya Pavlovna,"{RESET}')
        print()
        slow_print(f'  {DIM}"I have tried my strength everywhere.')
        slow_print(f'   My desires are too weak.')
        slow_print(f'   But tonight I was visited by the faces')
        slow_print(f'   of those I have touched, and some of them —')
        slow_print(f'   not all, but some — did not turn away."{RESET}')
        print()
        slow_print(f'  {DIM}"Perhaps that is something. I do not know.')
        slow_print(f'   I have never known what anything means."{RESET}')
        print()
        slow_print("  The letter shows cracks. Flickers of something")
        slow_print("  that might be honesty, or might be")
        slow_print("  the last performance of a consummate actor.")
        slow_print("  Even you are not sure which.")
    else:
        # Warmer, more honest
        slow_print(f'  {DIM}"Dear Dasha,"{RESET}')
        print()
        slow_print(f'  {DIM}"I have tried my strength everywhere,')
        slow_print(f'   and tonight I found it in the strangest place —')
        slow_print(f'   in the faces of those I failed.')
        slow_print(f'   They came to me and I answered them.')
        slow_print(f'   Not well. Not enough. But I answered."{RESET}')
        print()
        slow_print(f'  {DIM}"I still intend to go to Uri.')
        slow_print(f'   I still know what I am. But for one night,')
        slow_print(f'   in this room, with this candle,')
        slow_print(f'   something was not empty."{RESET}')
        print()
        slow_print("  The letter is different.")
        slow_print("  Still the letter of a man walking toward the loft.")
        slow_print("  But written by a hand that trembled.")
        slow_print("  And a trembling hand is a living hand.")

    print()
    slow_print(f"  {DIM}{'═' * 50}{RESET}")
    print()
    slow_print(f"  {BOLD}Confrontations survived: {confrontations} of 5{RESET}")
    print()
    if confrontations == 5:
        slow_print(f"  {GREEN}Every ghost answered. Every bond held.{RESET}")
    elif confrontations >= 3:
        slow_print(f"  {YELLOW}Some bonds held. Some doors opened.{RESET}")
    elif confrontations >= 1:
        slow_print(f"  {MAGENTA}Most ghosts turned away unanswered.{RESET}")
    else:
        slow_print(f"  {RED}Silence. From beginning to end, silence.{RESET}")

    show_status()
    press_enter()


# ═══════════════════════════════════════════════════════════════
#  THE RECKONING — STAVROGIN'S END
# ═══════════════════════════════════════════════════════════════

def generate_score_card(ending_title, human_count):
    """Generate a shareable ASCII score card for screenshots."""
    cs = state.get("confrontations_survived", 0)

    # Score calculation (0-999 scale)
    raw = (
        state["soul"] * 2
        + cs * 100
        + human_count * 25
        + state["tea_consumed"] * 5
        - state["ennui"]
        - state["revolutionary_fervor"]
        - state["pyotr_entangled"] * 2
    )
    score = max(0, min(999, raw))

    # Ghost bar
    ghost_filled = "█" * cs
    ghost_empty = "░" * (5 - cs)
    ghost_bar = f"{ghost_filled}{ghost_empty}"

    # Score bar (20 chars wide, proportional to 999)
    bar_len = 20
    filled = min(int(score / 999 * bar_len), bar_len)
    score_bar = "█" * filled + "░" * (bar_len - filled)

    # Superlative awards — pick top 3
    awards = []
    if state.get("confessed_to_tikhon") and "heard_the_gospel" in state["decisions"]:
        awards.append("The Confessor")
    if cs >= 4:
        awards.append("Ghost Whisperer")
    if state["soul"] >= 80:
        awards.append("Most Soulful")
    if state.get("marya_bond_peak", 0) >= 15:
        awards.append("Holy Fool's Prince")
    if state["stepan_bond"] >= 15 and state["shatov_bond"] >= 15:
        awards.append("Faithful Friend")
    if "fired_air_three_times" in state["decisions"]:
        awards.append("The Duellist")
    if state["liza_bond"] >= 10:
        awards.append("Breaker of Hearts")
    if state["tea_consumed"] >= 8:
        awards.append("Tea Connoisseur")
    if state["revolutionary_fervor"] >= 60:
        awards.append("Revolutionary")
    if state["ennui"] >= 80:
        awards.append("The Nihilist")
    if state["pyotr_entangled"] >= 40:
        awards.append("Pyotr's Puppet")
    if state["ennui"] >= 60 and state["soul"] <= 30:
        awards.append("The Empty Man")
    awards = awards[:3]

    # Performance description
    if ending_title == "THE PENITENT":
        perf = "Against all odds, you reached toward grace."
    elif ending_title == "THE WANDERER" and cs >= 4:
        perf = "You touched something real. Almost enough."
    elif ending_title == "THE WANDERER":
        perf = "A few genuine moments in a sea of emptiness."
    elif ending_title == "THE POSSESSED":
        perf = "The demons did their work from within."
    else:
        perf = "Nothing, from beginning to end."

    # Build award lines
    if len(awards) >= 2:
        award_line1 = f"  * {awards[0]:<20} * {awards[1]}"
        award_line2 = f"  * {awards[2]}" if len(awards) >= 3 else ""
    elif len(awards) == 1:
        award_line1 = f"  * {awards[0]}"
        award_line2 = ""
    else:
        award_line1 = f"  (No awards earned)"
        award_line2 = ""

    # Tea display
    tea_icons = "T" * min(state["tea_consumed"], 10)

    # Print the card
    print(f"""
  {BOLD}╔══════════════════════════════════════════════════╗
  ║                                                  ║
  ║       Д Е М О Н Ы  /  D E M O N S              ║
  ║           Б Е С Ы  /  THE POSSESSED             ║
  ║                                                  ║
  ║  ┌──────────────────────────────────────────┐    ║
  ║  │  SCORE:  {score_bar}  {score:>3}    │    ║
  ║  │  ENDING: {ending_title:<33}│    ║
  ║  │  GHOSTS: {ghost_bar}  {cs}/5                    │    ║
  ║  └──────────────────────────────────────────┘    ║
  ║                                                  ║
  ║  {award_line1:<48}║
  ║  {award_line2:<48}║
  ║                                                  ║
  ║  {DIM}"{perf}"{RESET}{BOLD}  ║
  ║                                                  ║
  ║  Soul: {state['soul']:<5} Ennui: {state['ennui']:<5} Tea: {state['tea_consumed']:<4}       ║
  ║  Decisions: {len(state['decisions']):<4} Human moments: {human_count:<4}        ║
  ║                                                  ║
  ║  {DIM}After Dostoevsky, 1872.  Garnett translation.{RESET}{BOLD}   ║
  ║  {DIM}github.com/timhwang/demons-interactive{RESET}{BOLD}           ║
  ║                                                  ║
  ╚══════════════════════════════════════════════════╝{RESET}
""")


def chapter_11_reckoning():
    """The final chapter. Stavrogin's end."""
    clear_screen()
    print(f"""{DIM}
  Dawn  |  Skvoreshniki  |  The Loft{RESET}

     __________________________________________________________
    |                                                          |
    |                                                          |
    |                                                          |
    |                                                          |
    |                    .-------.                              |
    |                    |       |                              |
    |                    |   {WHITE}+{DIM}   |                              |
    |                    |   {WHITE}|{DIM}   |                              |
    |                    |  {WHITE}=|={DIM}  |                              |
    |                    |   {WHITE}|{DIM}   |    {DIM}A table.{RESET}{DIM}                   |
    |                    |   {WHITE}|{DIM}   |    {DIM}A note.{RESET}{DIM}                    |
    |                    |   {WHITE}|{DIM}   |    {DIM}A nail.{RESET}{DIM}                    |
    |                    '---{WHITE}|{DIM}---'    {DIM}A piece of soap.{RESET}{DIM}           |
    |                        {WHITE}|{DIM}        {DIM}A strong silk cord.{RESET}{DIM}        |
    |                                                          |
    |__________________________________________________________|

    {DIM}Everything proved premeditation and consciousness
    up to the last moment.{RESET}
""")

    slow_print(f"  {BOLD}EPILOGUE: CONCLUSION{RESET}")
    print()
    slow_print("  The letter is sealed. The candle is out.")
    slow_print("  There is nothing left to write, nothing left to say.")
    print()
    slow_print("  Varvara Petrovna and Dasha came to Skvoreshniki the next morning.")
    slow_print("  They found all the doors open.")
    slow_print("  They went upstairs. Then to the loft.")
    print()
    slow_print("  On the table: a note in pencil.")
    slow_print(f'  {REVERSE}  "No one is to blame. I did it myself."  {RESET}')
    print()
    slow_print("  Beside it: a hammer. A piece of soap. A large nail.")
    slow_print("  The strong silk cord was thickly smeared with soap.")
    print()
    slow_print("  At the inquest, the doctors absolutely and emphatically")
    slow_print("  rejected all idea of insanity.")
    print()

    # Calculate ending based on confrontations survived
    cs = state.get("confrontations_survived", 0)

    print(f"  {DIM}{'═' * 55}{RESET}")
    show_status()
    print(f"  {BOLD}FINAL JUDGMENT{RESET}")
    print(f"  {DIM}{'═' * 55}{RESET}")
    print()

    if cs >= 4 and state.get("confessed_to_tikhon") and "heard_the_gospel" in state["decisions"]:
        ending_title = "THE PENITENT"
        print(f"  {GREEN}{BOLD}  ★ ★ ★ ★ ★  THE PENITENT  ★ ★ ★ ★ ★{RESET}")
        print()
        slow_print("  You went to Tikhon. You heard the Gospel.")
        slow_print("  And on your last night, when they came for you —")
        slow_print("  the ghosts of everyone you touched —")
        slow_print("  you answered them. Not perfectly. Not enough.")
        slow_print("  But you answered.")
        slow_print("  Perhaps it was pride, as the bishop said.")
        slow_print("  But you reached toward something.")
        slow_print("  The silk cord was still there. You know that.")
        slow_print("  But perhaps — only perhaps — for one night,")
        slow_print("  in one room, with one candle and five ghosts,")
        slow_print("  another ending was possible.")
        slow_print(f"  {DIM}Dostoevsky cut the confession chapter from the novel.{RESET}")
        slow_print(f"  {DIM}Even fiction cannot bear too much hope.{RESET}")
    elif cs >= 4:
        ending_title = "THE WANDERER"
        print(f"  {YELLOW}{BOLD}  ★ ★ ★ ★ ☆  THE WANDERER  ★ ★ ★ ★ ☆{RESET}")
        print()
        slow_print("  On your last night, you answered almost everyone.")
        slow_print("  Shatov, Kirillov, Marya, Pyotr, Stepan —")
        slow_print("  you built enough to face them.")
        slow_print("  The letter to Dasha was warmer than the novel's.")
        slow_print("  But without the confession, without the Gospel,")
        slow_print("  the warmth was not enough to reach the loft")
        slow_print("  and cut the cord.")
        slow_print("  In the end, the citizen of the canton of Uri")
        slow_print("  was found at Skvoreshniki.")
        slow_print(f"  {DIM}But the bonds you built were real.{RESET}")
        slow_print(f"  {DIM}That changes nothing. And everything.{RESET}")
    elif cs == 3:
        ending_title = "THE WANDERER"
        print(f"  {YELLOW}{BOLD}  ★ ★ ★ ☆ ☆  THE WANDERER  ★ ★ ★ ☆ ☆{RESET}")
        print()
        slow_print("  You survived longer than you expected.")
        slow_print("  You touched something real — in Shatov's garret,")
        slow_print("  or at Stepan Trofimovich's side, or on the bridge.")
        slow_print("  But it was not enough. The silk cord was patient.")
        slow_print("  The house in Uri was a fiction. The letter to Dasha")
        slow_print("  was a goodbye that could not say its own name.")
        slow_print("  In the end, the citizen of the canton of Uri")
        slow_print("  was found in the loft at Skvoreshniki.")
        slow_print(f"  {DIM}The swine went over the cliff.{RESET}")
        slow_print(f"  {DIM}But the sick man — Russia — will be healed.{RESET}")
        slow_print(f"  {DIM}Stepan Trofimovich said so.{RESET}")
    elif cs == 2:
        ending_title = "THE POSSESSED"
        print(f"  {MAGENTA}{BOLD}  ★ ★ ☆ ☆ ☆  THE POSSESSED  ★ ★ ☆ ☆ ☆{RESET}")
        print()
        slow_print("  The demons entered and did their work.")
        slow_print("  Not from outside — from within.")
        slow_print("  From the terrible leisure of an aristocrat")
        slow_print("  who tried everything and felt nothing.")
        slow_print("  From the vacuum at the center that drew in")
        slow_print("  everyone who loved you, believed in you,")
        slow_print("  projected their God and their Russia onto your face.")
        slow_print("  The silk cord. The soap. The nail.")
        slow_print("  Premeditation and consciousness to the last moment.")
        slow_print(f"  {DIM}Even negation did not come from you.{RESET}")
        slow_print(f"  {DIM}Everything was always petty and spiritless.{RESET}")
    else:
        ending_title = "THE ABYSS"
        print(f"  {RED}{BOLD}  ★ ☆ ☆ ☆ ☆  THE ABYSS  ★ ☆ ☆ ☆ ☆{RESET}")
        print()
        slow_print("  Nothing. From beginning to end, nothing.")
        slow_print("  The emptiness was so total that it pulled")
        slow_print("  the entire town into itself — Shatov, Kirillov,")
        slow_print("  Marya Timofeyevna, Liza, Lebyadkin, Stepan Trofimovich.")
        slow_print("  All of them swallowed by the void at your center.")
        slow_print("  On your last night, the ghosts came and you could not answer.")
        slow_print("  Pyotr Verkhovensky used you and discarded you.")
        slow_print("  Your mother found you in the loft.")
        slow_print("  The note said no one was to blame.")
        slow_print("  The doctors said you were sane.")
        slow_print(f"  {DIM}Both statements were lies dressed as truth.{RESET}")
        slow_print(f"  {DIM}Your specialty.{RESET}")

    print()
    print(f"  {DIM}{'═' * 55}{RESET}")
    print()

    # Stats
    print(f"  {BOLD}THE BODY COUNT:{RESET}")
    print(f"  Tea consumed:              {'🍵' * min(state['tea_consumed'],10)} ({state['tea_consumed']})")
    print(f"  Dead by story's end:       Shatov, Kirillov, Lebyadkin,")
    print(f"                             Marya Timofeyevna, Liza,")
    print(f"                             Fedka, Stepan Trofimovich,")
    print(f"                             Shatov's wife, Shatov's baby.")
    print(f"                             And you.")
    print(f"  Pyotr Verkhovensky:        Escaped abroad. Naturally.")
    print(f"  Confrontations survived:   {state.get('confrontations_survived', 0)} of 5")
    human_count = sum(1 for d in state["decisions"] if d in [
        "greeted_stepan", "protected_marya", "accepted_the_slap",
        "seized_shatovs_arms", "called_kirillov_mad", "acknowledged_kirillov",
        "believed_in_russia", "will_believe", "asked_about_marya",
        "admitted_impostor", "refused_shatovs_blood", "struck_fedka",
        "called_meeting_farce", "followed_shatov_out", "rescued_stepan",
        "went_to_tikhon", "wrote_a_letter",
        "accepted_tikhons_truth", "asked_tikhon_for_way", "admitted_vanity",
        "fired_air_three_times", "offered_hand_to_gaganov",
        "held_lizas_hand", "denied_to_mother",
        "sat_with_stepan", "gave_stepan_coat", "told_stepan_about_varvara",
        "answered_shatov", "honored_kirillov", "loved_marya",
        "refused_pyotr_finally", "heard_the_gospel",
    ])
    print(f"  Genuine human moments:     {human_count}")
    print()

    # Decision recap
    print(f"  {BOLD}KEY DECISIONS:{RESET}")
    decision_labels = {
        "dutiful_return": "  • Kissed your mother's hand (it was not enough)",
        "cold_return": "  • Walked past everyone into silence",
        "greeted_stepan": "  • Greeted Stepan Trofimovich first",
        "announced_marriage": "  • Announced your marriage publicly",
        "acknowledged_marya": '  • Told the truth: "She is my wife"',
        "silence_in_salon": "  • Let silence speak in the salon",
        "protected_marya": "  • Led Marya Timofeyevna gently out",
        "dismissed_lebyadkins": "  • Dismissed the Lebyadkins coldly",
        "accepted_the_slap": "  • Accepted Shatov's slap without retaliation",
        "seized_shatovs_arms": '  • Caught Shatov\'s wrists and said "I know"',
        "walked_away_from_slap": "  • Walked away from the slap",
        "smiled_at_slap": "  • Smiled (the room was horrified)",
        # Duel decisions
        "fired_air_three_times": "  • Fired into the air three times (the worst insult)",
        "fired_at_gaganovs_feet": "  • Fired at Gaganov's feet (theater of violence)",
        "fired_at_stump": '  • Fired at a tree stump ("What a splendid morning")',
        "offered_hand_to_gaganov": "  • Walked to Gaganov and asked forgiveness",
        # Kirillov decisions
        "called_kirillov_mad": '  • Told Kirillov "Living" was more rational',
        "listened_to_kirillov": "  • Listened to Kirillov for two hours",
        "challenged_kirillov": "  • Planted doubt in a certain man",
        "acknowledged_kirillov": '  • Acknowledged what Kirillov meant to you',
        # Shatov decisions
        "believed_in_russia": '  • "I believe in Russia... in her orthodoxy..."',
        "declared_atheism": '  • "I do not believe." (Honest to the end.)',
        "will_believe": '  • "I will believe in God." (The future tense.)',
        "asked_about_marya": "  • Asked Shatov to care for Marya Timofeyevna",
        # Marya decisions
        "admitted_impostor": '  • Told Marya: "You are right. I am not your prince."',
        "promised_provision": "  • Promised to provide for your wife",
        "stood_before_marya": "  • Stood and let the holy fool read you",
        "fled_from_marya": "  • Fled from the only person who sees through you",
        # Fedka decisions
        "struck_fedka": "  • Struck Fedka and refused his offer",
        "ambiguous_with_fedka": "  • Were ambiguous with Fedka (fatally so)",
        "paid_fedka": "  • Gave Fedka three roubles (a terrible currency)",
        # Pyotr decisions
        "called_pyotr_madman": '  • Called Pyotr "Madman" and pulled away',
        "refused_shatovs_blood": '  • "I won\'t give up Shatov to you."',
        "questioned_the_plan": "  • Asked about the Ivan Tsarevitch plan",
        "let_pyotr_rave": "  • Let Pyotr rave all the way home",
        # Meeting decisions
        "observed_meeting": "  • Observed the meeting at Virginsky's",
        "called_meeting_farce": '  • Called the meeting "a farce"',
        "silent_at_meeting": "  • Sat silent (emptiness as endorsement)",
        "followed_shatov_out": "  • Followed Shatov out of the meeting",
        # Liza decisions
        "told_liza_the_truth": '  • Told Liza: "I knew I did not love you"',
        "told_liza_incapable": '  • Told Liza: "I am not capable"',
        "held_lizas_hand": "  • Held Liza's hand in the grey dawn",
        "told_liza_perhaps": '  • Told Liza: "Perhaps"',
        # Fete decisions
        "rescued_stepan": "  • Led Stepan Trofimovich off the stage",
        "watched_fete_collapse": "  • Watched the fete collapse",
        "found_liza_at_fete": "  • Found Liza at the fete",
        "left_the_fete": "  • Left the fete entirely",
        # Shatov murder night decisions
        "wrote_a_letter": "  • Wrote the letter to Dasha",
        "stood_on_bridge": "  • Stood on the bridge over the river in the dark",
        "sat_in_darkness": "  • Sat in the dark and let it press down",
        "prepared_to_leave": "  • Packed for Uri (a house in a narrow valley)",
        # Tikhon decisions
        "went_to_tikhon": "  • ☦ Went to Bishop Tikhon — the suppressed chapter",
        "denied_tikhons_truth": '  • ☦ Denied Tikhon\'s truth ("You are wrong, old man")',
        "accepted_tikhons_truth": "  • ☦ Accepted Tikhon's truth in silence",
        "asked_tikhon_for_way": '  • ☦ Asked Tikhon: "What would you have me do?"',
        "admitted_vanity": "  • ☦ Admitted even the confession was vanity",
        # Aftermath decisions
        "denied_to_mother": '  • Told your mother: "I did not kill them"',
        "silent_before_mother": '  • Said nothing (she said: "I have no son")',
        "told_mother_leaving": "  • Told your mother you are leaving for Uri",
        "confessed_to_mother": '  • Told your mother: "Everything they say is true"',
        # Stepan's wandering decisions
        "sat_with_stepan": "  • Sat with Stepan on the road and heard Luke",
        "gave_stepan_coat": "  • Gave Stepan your coat in the rain",
        "told_stepan_about_varvara": "  • Told Stepan she was looking for him",
        "passed_stepan_by": "  • Passed Stepan by on the road",
        # The Last Night — Final Boss confrontations
        "answered_shatov": '  • ✦ Answered Shatov: "I heard you, Ivan"',
        "denied_shatov_again": '  • ✦ Told Shatov\'s ghost: "I do not believe"',
        "silent_before_shatov": "  • ✦ Could not answer Shatov's question",
        "honored_kirillov": '  • ✦ Told Kirillov: "You were braver than I am"',
        "dismissed_kirillovs_proof": '  • ✦ Dismissed Kirillov: "Your logic destroyed you"',
        "questioned_kirillovs_freedom": '  • ✦ Told Kirillov: "Freedom without purpose..."',
        "loved_marya": '  • ✦ Told Marya\'s ghost: "I loved you"',
        "apologized_to_marya": '  • ✦ Apologized to Marya: "I married you on a dare"',
        "admitted_lovelessness": '  • ✦ Admitted to Marya: "I have never loved anyone"',
        "refused_pyotr_finally": '  • ✦ Refused Pyotr: "You are a fly"',
        "yielded_to_pyotr": '  • ✦ Yielded to Pyotr on the last night',
        "silent_before_pyotr": "  • ✦ Pulled away from Pyotr (he kept clutching)",
        "heard_the_gospel": '  • ✦ Listened to Stepan read the Gospel of Luke',
        "called_stepan_right": '  • ✦ Called Stepan "always ridiculous, always right"',
        "rejected_stepans_healing": '  • ✦ Rejected Stepan: "Beauty will not save the world"',
        # Fatal decisions
        "walked_into_bullet": f"  • {RED}☠ Walked into Gaganov's bullet{RESET}",
        "turned_back_on_fedka": f"  • {RED}☠ Turned your back on Fedka (fatal){RESET}",
        "walked_into_fire": f"  • {RED}☠ Ran into the Lebyadkin fire{RESET}",
        # Soul deaths
        "destroyed_shatov": f"  • {RED}☠ Told Shatov: 'There is nothing' (THE VOID){RESET}",
        "became_ivan_tsarevitch": f"  • {RED}☠ Accepted Pyotr's crown (CONSUMED){RESET}",
        "endorsed_murder": f"  • {RED}☠ Endorsed Shatov's murder (THE ACCOMPLICE){RESET}",
        "watched_murder": f"  • {RED}☠ Watched Shatov die at the pond (THE WITNESS){RESET}",
        "false_confession": f"  • {RED}☠ False confession — became The Demon{RESET}",
    }
    for d in state["decisions"]:
        if d in decision_labels:
            print(decision_labels[d])

    print(f"""

  {DIM}╔══════════════════════════════════════════════════════╗
  ║                                                      ║
  ║  Д Е М О Н Ы  /  D E M O N S                       ║
  ║  Б Е С Ы    /  THE POSSESSED                        ║
  ║                                                      ║
  ║  Ending: {ending_title:<43}║
  ║                                                      ║
  ║  "The sick man will be healed and will sit           ║
  ║   at the feet of Jesus, and all will look            ║
  ║   upon him with astonishment."                       ║
  ║                            — Luke viii. 35           ║
  ║                                                      ║
  ║  After Fyodor Mikhailovich Dostoevsky, 1872.         ║
  ║  Translated by Constance Garnett.                    ║
  ║                                                      ║
  ║  No nihilists were harmed in the making of           ║
  ║  this game. Several were, however, profoundly        ║
  ║  and irrevocably possessed.                          ║
  ║                                                      ║
  ╚══════════════════════════════════════════════════════╝{RESET}
""")

    # Shareable score card
    generate_score_card(ending_title, human_count)
    press_enter()

    play_again = input(f"  {GREEN}Play again? (y/n): {RESET}").strip().lower()
    return play_again == "y"


# ═══════════════════════════════════════════════════════════════
#  CHAPTER REGISTRY & MAIN
# ═══════════════════════════════════════════════════════════════

# Ordered list of (name, function) — used for save/resume.
# The secret Tikhon chapter is handled conditionally at runtime,
# not included in this list.
CHAPTERS = [
    ("The Return",              chapter_1_return),         # 0
    ("The Drawing Room",        chapter_2_drawing_room),   # 1
    ("The Duel",                chapter_new_duel),         # 2
    ("Night — Kirillov",        chapter_3_night_kirillov), # 3
    ("Night — Shatov",          chapter_4_night_shatov),   # 4
    ("Night — Lebyadkins",      chapter_5_night_lebyadkins),# 5
    ("Ivan the Tsarevitch",     chapter_6_ivan_tsarevitch),# 6
    ("The Meeting",             chapter_7_meeting),        # 7
    ("The Fête",                chapter_8_fete),           # 8
    ("Liza",                    chapter_new_liza),         # 9
    ("A Busy Night",            chapter_9_shatov_murder),  # 10
    ("The Aftermath",           chapter_new_aftermath),    # 11
    ("Stepan's Wandering",      chapter_10_stepan_wandering),# 12
    ("The Last Night",          chapter_final_boss),       # 13 — Final Boss
    ("Conclusion",              chapter_11_reckoning),     # 14
]

# Indices for special chapters
_IDX_SHATOV_MURDER = 10   # "A Busy Night"
_IDX_AFTERMATH = 11        # "The Aftermath"
_IDX_CONCLUSION = 14       # "Conclusion"

DEFAULT_STATE = {
    "ennui": 40,
    "revolutionary_fervor": 0,
    "soul": 50,
    "notoriety": 30,
    "tea_consumed": 0,
    "decisions": [],
    "shatov_bond": 0,
    "pyotr_entangled": 0,
    "marya_bond": 0,
    "stepan_bond": 0,
    "liza_bond": 0,
    "warned_shatov": False,
    "took_fedkas_offer": False,
    "gave_money_to_lebyadkin": False,
    "confessed_to_tikhon": False,
    "marya_bond_peak": 0,
    "confrontations_survived": 0,
}


def main():
    global _current_chapter_index
    while True:
        # Reset state
        state.update(DEFAULT_STATE)
        state["decisions"] = []  # ensure a fresh list (not the default's)

        result = title_screen()
        start_index = 0

        if result and result.startswith("load:"):
            # Loading a save (auto or slot)
            saved = None
            if result == "load:auto":
                saved = load_game()
            else:
                slot_num = int(result.split(":")[1])
                saved = load_slot(slot_num)
            if saved:
                for k, v in saved["state"].items():
                    state[k] = v
                start_index = saved["chapter_index"]
                clear_screen()
                slow_print(f"\n  {YELLOW}Resuming your journey...{RESET}")
                slow_print(f"  {DIM}Chapter: {CHAPTERS[start_index][0]}{RESET}")
                dramatic_pause(1.5)

        try:
            for i in range(start_index, len(CHAPTERS)):
                _current_chapter_index = i
                name, func = CHAPTERS[i]

                # Secret Tikhon chapter — insert after Shatov murder, before Aftermath
                if i == _IDX_AFTERMATH and check_tikhon_unlock():
                    chapter_secret_tikhon()

                # Run the chapter
                if i == _IDX_CONCLUSION:
                    # Conclusion returns True/False for play-again
                    if not func():
                        clear_screen()
                        slow_print(f"\n  {DIM}The candle goes out. The samovar cools.")
                        slow_print(f"  The silk cord hangs in the loft at Skvoreshniki.{RESET}")
                        slow_print(f"  {DIM}Somewhere on the high road, an old man with an umbrella{RESET}")
                        slow_print(f"  {DIM}asks a stranger to read to him from the Gospels.{RESET}")
                        slow_print(f"  {DIM}The sick man will be healed.{RESET}")
                        slow_print(f"  {DIM}Russia endures. It always endures.{RESET}")
                        print()
                        delete_save()
                        print(f"  {GREEN}Farewell. May your soul be heavier than your ennui.{RESET}\n")
                        return
                    else:
                        delete_save()
                        break  # restart the while loop
                else:
                    func()
                    # Auto-save after each chapter
                    save_game(i + 1)
        except GameOverException:
            # Fatal decision — return to title screen, save is preserved
            continue


if __name__ == "__main__":
    main()
