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
import asyncio
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


async def ainput(prompt=""):
    """Async input(). CLI: defers to blocking input() in a thread.
    Web bootloader overrides this with a JS bridge."""
    return await asyncio.to_thread(input, prompt)


def _reset_skip():
    """Reset skip mode and flush any buffered keypresses."""
    global _skip_text
    _skip_text = False
    if _is_interactive():
        try:
            termios.tcflush(sys.stdin.fileno(), termios.TCIFLUSH)
        except (termios.error, ValueError, OSError):
            pass


async def slow_print(text, delay=0.018):
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
                await asyncio.sleep(delay)
    finally:
        if interactive and old_settings is not None:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    print()


async def dramatic_pause(seconds=1.5):
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
            await asyncio.sleep(seconds)
    finally:
        if interactive and old_settings is not None:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


async def press_enter():
    _reset_skip()
    await ainput(f"\n{DIM}  [ Press ENTER to continue ]{RESET}")


async def get_choice(options):
    _reset_skip()
    print()
    for i, option in enumerate(options, 1):
        print(f"  {YELLOW}{i}{RESET}) {option}")
    print()
    print(f"  {DIM}[S] Save game{RESET}")
    print()
    while True:
        try:
            raw = (await ainput(f"  {GREEN}>{RESET} ")).strip()
            if raw.lower() == "s":
                await save_to_slot()
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

async def game_over(death_lines):
    """Fatal decision — show death scene and end the run."""
    print()
    for line in death_lines:
        await slow_print(line)
    print()
    await slow_print(f"  {RED}{BOLD}  ★ ☆ ☆ ☆ ☆  GAME OVER  ★ ☆ ☆ ☆ ☆{RESET}")
    print()
    await slow_print(f"  {DIM}The silk cord was not needed after all.{RESET}")
    await slow_print(f"  {DIM}Load a save to try again.{RESET}")
    print()
    await press_enter()
    raise GameOverException()


# ─── SAVE SYSTEM ──────────────────────────────────────────────

SAVE_FILE = Path.home() / ".demons_save.json"

# Tracks current chapter index so await save_to_slot() knows where we are
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


async def save_to_slot():
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
            raw = (await ainput(f"  {GREEN}Save to slot: {RESET}")).strip()
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

async def title_screen():
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
            raw = (await ainput(f"  {GREEN}>{RESET} ")).strip().lower()
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
        await press_enter()

    return "new"


# ═══════════════════════════════════════════════════════════════
#  PART I: THE RETURN
# ═══════════════════════════════════════════════════════════════

async def chapter_1_return():
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

    await slow_print(f"  {BOLD}PART I")
    await slow_print(f"  CHAPTER I: INTRODUCTORY — THE RETURN{RESET}")
    print()
    await slow_print("  Four years abroad. Perhaps five. It ceased to matter somewhere")
    await slow_print("  around Naples, or was it Geneva? You have been everywhere and")
    await slow_print("  nowhere. You have studied philosophy in German universities,")
    await slow_print("  fought two duels, been degraded from officer's rank, married")
    await slow_print("  a lame beggar-woman on a bet — or perhaps out of some")
    await slow_print("  monstrous curiosity about your own capacity for abasement.")
    print()
    await slow_print("  Now: the provincial town. The old estate at Skvoreshniki.")
    await slow_print("  Your mother Varvara Petrovna waits in the drawing room.")
    await slow_print("  She has been keeping your old tutor, Stepan Trofimovich")
    await slow_print("  Verkhovensky, like a lapdog in a waistcoat for twenty years.")
    await slow_print("  He is a liberal, a man of the forties, who has not published")
    await slow_print("  anything in two decades but still gestures as though ideas")
    await slow_print("  are leaving his fingertips.")
    print()
    await slow_print("  The town remembers you. Before you left, you pulled a")
    await slow_print("  respected old man named Gaganov across the room by his nose")
    await slow_print("  — in front of the entire club. You bit the Governor's ear")
    await slow_print("  at a birthday party. You kissed another man's wife in public.")
    await slow_print("  No one could explain these acts. Neither could you.")
    print()
    await slow_print(f"  {DIM}The carriage halts. The door opens. Russia receives you back.{RESET}")
    print()
    await slow_print("  The house smells of beeswax and camphor.")
    await slow_print("  A servant you do not recognize takes your coat.")
    await slow_print("  Another — old Alexei, who carried you as a child —")
    await slow_print("  stares at you from the passage with an expression")
    await slow_print("  that contains twenty years of gossip, fear, and hope.")
    await slow_print("  He crosses himself. You pretend not to see.")
    print()
    await slow_print("  Through the open door of the drawing room, you see them:")
    await slow_print("  your mother, upright as a bayonet in her black silk,")
    await slow_print("  and Stepan Trofimovich beside her, already preparing")
    await slow_print("  to produce the emotion the moment requires.")
    await slow_print("  He has been rehearsing this scene for months.")
    await slow_print("  Your mother has been rehearsing it for years.")
    print()

    await slow_print("  How do you present yourself?")

    choice = await get_choice([
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
        await slow_print('\n  "Maman." You kiss her hand. She trembles.')
        await slow_print("  Varvara Petrovna's eyes fill with tears she will")
        await slow_print("  never acknowledge. Twenty servants watch in silence.")
        await slow_print("  You note that the wallpaper has been changed.")
        await slow_print("  You note that Stepan Trofimovich has grown fatter.")
        await slow_print("  You note that you feel precisely nothing.")
        await slow_print(f"  {DIM}The performance is flawless. That is the horror of it.{RESET}")
    elif choice == 2:
        state["ennui"] += 15
        state["notoriety"] += 10
        state["decisions"].append("cold_return")
        await slow_print("\n  You walk through the vestibule, past the servants,")
        await slow_print("  past your mother, past Stepan Trofimovich who has")
        await slow_print("  prepared a three-page welcome speech in French.")
        await slow_print("  You close the door to your old rooms.")
        await slow_print("  You sit on the bed and look at the ceiling.")
        await slow_print("  The ceiling looks back. It has been doing this for years.")
        await slow_print(f"  {DIM}Outside, you hear your mother say to no one in particular:")
        await slow_print(f'  "He is tired from the journey."{RESET}')
        await slow_print(f"  {DIM}She will defend you until it destroys her.{RESET}")
    elif choice == 3:
        state["stepan_bond"] += 10
        state["ennui"] += 5
        state["soul"] += 5
        state["decisions"].append("greeted_stepan")
        await slow_print('\n  "Stepan Trofimovich." You take his hand.')
        await slow_print("  The old man's eyes fill immediately. His lip trembles.")
        await slow_print('  "Nicolas! Mon cher enfant! You remember your old teacher!"')
        await slow_print("  He weeps openly, without shame. He is absurd.")
        await slow_print("  He is also the only person in this house who ever")
        await slow_print("  read you bedtime stories. In Latin, naturally.")
        await slow_print("  Your mother watches from across the room, jealous")
        await slow_print("  of an emotion she cannot permit herself.")
        await slow_print(f"  {DIM}For a moment, you almost feel something.{RESET}")
        await slow_print(f"  {DIM}It passes. These things always pass.{RESET}")
    elif choice == 4:
        state["notoriety"] += 20
        state["soul"] -= 5
        state["ennui"] -= 5
        state["marya_bond"] += 5
        state["decisions"].append("announced_marriage")
        await slow_print("\n  The drawing room goes silent.")
        await slow_print('  "I intend to make a public announcement," you say.')
        await slow_print('  "Marya Timofeyevna Lebyadkina is my lawful wife.')
        await slow_print('   We were married in Petersburg four and a half years ago."')
        await slow_print("  Your mother grips the arm of her chair.")
        await slow_print("  Stepan Trofimovich drops his lorgnette.")
        await slow_print("  Somewhere, distantly, a dog barks.")
        await slow_print('  "The cripple?" your mother whispers.')
        await slow_print("  You do not correct her. The word is accurate enough.")
        await slow_print(f"  {DIM}You married her because the shame and senselessness{RESET}")
        await slow_print(f"  {DIM}of it reached the pitch of genius. Shatov said that.{RESET}")
        await slow_print(f"  {DIM}Shatov was right.{RESET}")

    # Interior monologue
    print()
    await slow_print(f"  {DIM}Later, in your old rooms, you sit in a chair{RESET}")
    await slow_print(f"  {DIM}that still remembers the shape of you at sixteen.{RESET}")
    await slow_print(f"  {DIM}Outside the window: the lime trees, the path to the pond,{RESET}")
    await slow_print(f"  {DIM}the distant roof of the church where you were baptized.{RESET}")
    await slow_print(f"  {DIM}You have been to Naples, to Iceland, to Egypt.{RESET}")
    await slow_print(f"  {DIM}You have read everything, tried everything, felt nothing.{RESET}")
    await slow_print(f"  {DIM}And now you are here, and here is exactly like everywhere else:{RESET}")
    await slow_print(f"  {DIM}a room containing you, which is to say, containing nothing.{RESET}")

    clamp_stats()
    show_status()
    await press_enter()


# ═══════════════════════════════════════════════════════════════
#  THE DRAWING ROOM / SCANDAL SUNDAY
# ═══════════════════════════════════════════════════════════════

async def chapter_2_drawing_room():
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

    await slow_print(f"  {BOLD}CHAPTER II: THE SUBTLE SERPENT{RESET}")
    print()
    await slow_print("  Your mother has arranged one of her Sundays.")
    await slow_print("  The drawing room is full. Everyone who matters in the province")
    await slow_print("  is here, and everyone who does not matter is here also,")
    await slow_print("  because in a provincial town these categories overlap entirely.")
    print()
    await slow_print("  Present: Varvara Petrovna, rigid with propriety.")
    await slow_print("  Stepan Trofimovich on the divan, gesturing at Schiller.")
    await slow_print("  Lizaveta Nikolaevna Tushina — Liza — beautiful, nervous,")
    await slow_print("  watching you with an intensity that borders on illness.")
    await slow_print("  Her fiancé Mavriky Nikolaevich, loyal as a large dog.")
    print()
    await slow_print("  And then — the door opens.")
    await slow_print("  Captain Lebyadkin enters, drunk, reciting his own poetry.")
    await slow_print("  Behind him, led by the hand: Marya Timofeyevna.")
    await slow_print("  Your wife. The lame woman. The holy fool.")
    await slow_print("  She looks around the room with the serenity of a child.")
    print()
    await slow_print("  Varvara Petrovna's face turns to stone.")
    await slow_print('  "Who is this woman?" she demands.')
    print()
    await slow_print("  Every eye turns to you.")
    print()

    await slow_print("  How do you handle the catastrophe?")

    choice = await get_choice([
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
        await slow_print('\n  "This is Marya Timofeyevna," you say quietly.')
        await slow_print('  "She is my wife."')
        await slow_print("  The room does not gasp. It does something worse:")
        await slow_print("  it goes utterly, completely silent.")
        await slow_print("  Liza's face drains of color. Stepan Trofimovich")
        await slow_print("  makes a small sound like a man stepping on a cat.")
        await slow_print("  Your mother grips the arm of her chair so hard")
        await slow_print("  that her knuckles turn the color of bone.")
        await slow_print("  Marya Timofeyevna smiles at everyone and says:")
        await slow_print(f'  {DIM}"What nice people. Is there tea?"{RESET}')
    elif choice == 2:
        state["ennui"] += 15
        state["notoriety"] += 10
        state["decisions"].append("silence_in_salon")
        await slow_print("\n  You say nothing. The room holds its breath.")
        await slow_print("  Varvara Petrovna looks from you to the cripple")
        await slow_print("  and back again, searching for some explanation")
        await slow_print("  that does not exist.")
        await slow_print("  Lebyadkin, encouraged by the silence, begins to recite:")
        await slow_print(f'  {DIM}"Oh, she\'s a sweet queen, Lizaveta Tushin!"{RESET}')
        await slow_print("  — terrible poetry, directed at Liza, of all people.")
        await slow_print("  Your silence fills the room like smoke.")
        await slow_print("  Everyone assigns it the meaning they most fear.")
    elif choice == 3:
        state["soul"] += 15
        state["marya_bond"] += 15
        state["ennui"] -= 5
        state["decisions"].append("protected_marya")
        await slow_print("\n  You cross the room. Thirty people watch.")
        await slow_print("  You take Marya Timofeyevna's hand — gently,")
        await slow_print("  the way one handles something precious and breakable.")
        await slow_print('  "Come," you say softly. "This is no place for you."')
        await slow_print("  She looks up at you with her lame, luminous smile.")
        await slow_print('  "My prince," she whispers. "You came back."')
        await slow_print("  Something moves in your chest. You are not sure what.")
        await slow_print("  You lead her out. Behind you, the room erupts.")
        await slow_print(f"  {DIM}For a moment, your hand in hers, you were almost human.{RESET}")
    elif choice == 4:
        state["soul"] -= 10
        state["notoriety"] += 10
        state["marya_bond"] -= 10
        state["decisions"].append("dismissed_lebyadkins")
        await slow_print('\n  "Remove yourself," you say to Lebyadkin,')
        await slow_print("  in a voice so cold it could frost glass.")
        await slow_print("  Lebyadkin stammers. He is used to being dismissed")
        await slow_print("  but not like this, not in front of society.")
        await slow_print("  Marya Timofeyevna looks at you. Her face changes.")
        await slow_print('  "You are not my prince," she says suddenly.')
        await slow_print('  "My prince would not speak so. You are someone else.')
        await slow_print('   You are an impostor."')
        await slow_print("  The holy fool sees what no one else can see:")
        await slow_print("  the emptiness behind the beautiful face.")
        await slow_print(f"  {DIM}She is the only one who has ever looked through you.{RESET}")
        await slow_print(f"  {DIM}It is the most terrifying thing that has ever happened to you.{RESET}")

    # Shatov's slap — happens regardless
    print()
    await slow_print(f"  {RED}  Then Shatov enters.{RESET}")
    await slow_print(f"  {RED}  Ivan Pavlovich Shatov — your former disciple,{RESET}")
    await slow_print(f"  {RED}  the man you taught about God and Russia,{RESET}")
    await slow_print(f"  {RED}  whose wife you seduced because you could.{RESET}")
    print()
    await slow_print("  He walks up to you in front of thirty people.")
    await slow_print("  He slaps you across the face.")
    await slow_print("  Hard. The sound is like a gunshot in the drawing room.")
    print()
    await slow_print("  The room is frozen. Your cheek burns.")
    await slow_print("  Your hands do not move.")
    print()

    await slow_print("  What do you do?")

    choice2 = await get_choice([
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
        await slow_print('\n  "Enough," you say, quietly, and put your hands')
        await slow_print("  behind your back. Shatov's fist trembles.")
        await slow_print("  He wants to hit you again. He cannot.")
        await slow_print("  The whole room watches a man accept punishment")
        await slow_print("  from someone weaker. It is the most shocking thing")
        await slow_print("  any of them have ever witnessed.")
        await slow_print("  Liza faints. Mavriky Nikolaevich catches her.")
        await slow_print(f"  {DIM}Your restraint will be interpreted as superhuman.{RESET}")
        await slow_print(f"  {DIM}It is not. You simply deserved it.{RESET}")
    elif choice2 == 2:
        state["soul"] += 10
        state["shatov_bond"] += 15
        state["decisions"].append("seized_shatovs_arms")
        await slow_print("\n  You catch both his wrists. Your grip is iron.")
        await slow_print("  Shatov struggles. He is shaking.")
        await slow_print('  "Ivan," you say. Just his name.')
        await slow_print("  His eyes are wild — not with hatred but with")
        await slow_print("  a grief so enormous it has curdled into violence.")
        await slow_print('  "Because of your fall," he whispers. "Your lie.')
        await slow_print('   I didn\'t know I would strike you until I did."')
        await slow_print('  "I know," you say. "I understand."')
        await slow_print(f"  {DIM}You hold him until the shaking stops.{RESET}")
        await slow_print(f"  {DIM}In Russia, this counts as an embrace.{RESET}")
    elif choice2 == 3:
        state["ennui"] += 15
        state["notoriety"] += 10
        state["decisions"].append("walked_away_from_slap")
        await slow_print("\n  You turn and walk out of the drawing room.")
        await slow_print("  Through the vestibule. Past the servants.")
        await slow_print("  Into the garden, where the birches are turning.")
        await slow_print("  Behind you, chaos. Shouts. A woman screaming.")
        await slow_print("  You keep walking until you reach the gate.")
        await slow_print("  The evening air smells of woodsmoke and damp earth.")
        await slow_print("  Your cheek throbs. It is the most alive")
        await slow_print("  you have felt in four years.")
        await slow_print(f"  {DIM}You do not go back inside for eight days.{RESET}")
    elif choice2 == 4:
        state["ennui"] += 10
        state["notoriety"] += 20
        state["soul"] -= 15
        state["decisions"].append("smiled_at_slap")
        await slow_print("\n  You smile. Not a mocking smile. Not a kind one.")
        await slow_print("  Just — a smile. The expression of a man who has")
        await slow_print("  been given something he has been waiting for.")
        await slow_print("  Shatov recoils as though burned.")
        await slow_print("  The room is horrified. Three women faint.")
        await slow_print("  Stepan Trofimovich later tells the narrator")
        await slow_print('  that he saw "something diabolical" in it.')
        await slow_print("  You disagree. Diabolical implies purpose.")
        await slow_print(f"  {DIM}There was no purpose. Only the reflex{RESET}")
        await slow_print(f"  {DIM}of a man who has forgotten what faces are for.{RESET}")

    clamp_stats()
    show_status()
    await press_enter()


# ═══════════════════════════════════════════════════════════════
#  THE DUEL
# ═══════════════════════════════════════════════════════════════

async def chapter_new_duel():
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

    await slow_print(f"  {BOLD}CHAPTER III: THE DUEL{RESET}")
    print()
    await slow_print("  Three days after the scandal in the drawing room.")
    await slow_print("  A letter arrives at Skvoreshniki, carried by a second:")
    await slow_print("  Artemy Pavlovich Gaganov — the son — demands satisfaction.")
    await slow_print("  You pulled his father across a room by the nose,")
    await slow_print("  years ago, in the club, in front of everyone.")
    await slow_print("  The old man never recovered. He weeps at dinner parties.")
    await slow_print("  The son has sworn to avenge the family honor.")
    print()
    await slow_print("  You had apologized already — a written apology,")
    await slow_print("  polite, correct, admitting that you had acted")
    await slow_print('  "under the influence of illness." Gaganov Jr.')
    await slow_print("  threw the letter in the fire. He will have blood.")
    print()
    await slow_print("  Kirillov agrees to act as your second.")
    await slow_print("  He has never mounted a horse before.")
    await slow_print("  The ride to the forest takes an hour;")
    await slow_print("  he clings to the saddle with grim determination,")
    await slow_print("  bouncing like a sack of philosophy.")
    await slow_print('  "I agreed because I do not accept conventions,"')
    await slow_print("  he says, teeth rattling. You almost smile.")
    print()
    await slow_print("  Brykov forest. A clearing among the birches.")
    await slow_print("  The seconds pace out twenty steps.")
    await slow_print("  Gaganov stands at his mark: young, trembling,")
    await slow_print("  his face white with an emotion that is half courage")
    await slow_print("  and half the nausea of a man about to do violence.")
    await slow_print("  Mavriky Nikolaevich — Liza's fiancé — serves as his second.")
    print()
    await slow_print(f"  {BOLD}First exchange.{RESET}")
    await slow_print("  The signal is given. Gaganov fires first.")
    await slow_print("  The bullet whirs past your head.")
    await slow_print("  You raise your pistol. The clearing is silent.")
    await slow_print("  Every bird has stopped singing.")
    print()
    await slow_print("  You fire into the air.")
    print()
    await slow_print("  Gaganov stares. The seconds exchange glances.")
    await slow_print('  "You fired in the air!" Gaganov shouts.')
    await slow_print('  "That is an insult! You treat me like a child!"')
    await slow_print('  "I have no wish to kill you," you say.')
    await slow_print('  "Then why did you accept the duel?"')
    await slow_print("  You do not answer. There is no answer.")
    print()
    await slow_print(f"  {BOLD}Second exchange.{RESET}")
    await slow_print("  Gaganov's hands are shaking now. He fires again —")
    await slow_print("  the bullet clips a branch above your shoulder.")
    await slow_print("  Splinters of bark rain down on your coat.")
    await slow_print("  You raise your pistol. Again, deliberately,")
    await slow_print("  you aim above his head and fire into the trees.")
    print()
    await slow_print('  "He is playing with me!" Gaganov screams.')
    await slow_print("  He is weeping now — not from fear but from rage.")
    await slow_print("  The shame of it: a man who will not fight back.")
    await slow_print("  Worse than being shot. Worse than being hated.")
    await slow_print("  To be treated as though you do not matter enough to kill.")
    print()
    await slow_print(f"  {BOLD}Third exchange.{RESET}")
    await slow_print("  This time Gaganov takes careful aim.")
    await slow_print("  The pistol steadies. He fires.")
    await slow_print("  The bullet punches through the crown of your hat.")
    await slow_print("  An inch lower and you would be dead.")
    await slow_print("  You remove the hat. Examine the hole.")
    await slow_print("  Put it back on.")
    print()

    await slow_print("  How do you take your final shot?")

    choice = await get_choice([
        "Fire into the air a third time. Let him have his rage.",
        "Fire into the ground at Gaganov's feet. Make a point.",
        "Fire into a tree stump and remark on the splendid morning.",
        "Walk toward him, pistol lowered, and offer your hand.",
        "Step forward into his line of fire.",
    ])

    if choice == 5:
        state["decisions"].append("walked_into_bullet")
        await game_over([
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
        await slow_print("\n  You fire into the air. A third time.")
        await slow_print('  "I declare that I fire in the air on purpose!"')
        await slow_print("  you say, loud enough for all to hear.")
        await slow_print("  Gaganov collapses to his knees in the wet grass.")
        await slow_print("  He is sobbing. Not with relief. With humiliation.")
        await slow_print("  You have given him something worse than a wound:")
        await slow_print("  the knowledge that he was not worth wounding.")
        await slow_print(f"  {DIM}The seconds lead him away.{RESET}")
        await slow_print(f"  {DIM}Kirillov studies your face on the ride home.{RESET}")
        await slow_print(f'  {DIM}"You did not fire because you did not care," he says.{RESET}')
        await slow_print(f'  {DIM}"Not because you were merciful."{RESET}')
        await slow_print(f"  {DIM}You do not contradict him.{RESET}")
    elif choice == 2:
        state["ennui"] += 5
        state["notoriety"] += 15
        state["decisions"].append("fired_at_gaganovs_feet")
        await slow_print("\n  You lower the pistol and fire into the ground")
        await slow_print("  six inches from Gaganov's boots.")
        await slow_print("  Dirt sprays across his trousers.")
        await slow_print("  He staggers backward, white as paper.")
        await slow_print('  "Next time," you say quietly, "I will aim lower still."')
        await slow_print("  It is a lie. You would never aim at him.")
        await slow_print("  But the cruelty of the gesture is exquisite —")
        await slow_print("  not violence, but the theater of violence.")
        await slow_print(f"  {DIM}Gaganov will never challenge you again.{RESET}")
        await slow_print(f"  {DIM}He will also never forgive you.{RESET}")
        await slow_print(f"  {DIM}These are the same thing.{RESET}")
    elif choice == 3:
        state["ennui"] += 10
        state["notoriety"] += 15
        state["soul"] -= 5
        state["decisions"].append("fired_at_stump")
        await slow_print("\n  You turn ninety degrees and fire into a tree stump")
        await slow_print("  at the edge of the clearing. The bark explodes.")
        await slow_print('  "What a splendid morning," you say.')
        await slow_print('  "The birches are particularly fine at this hour."')
        await slow_print("  The seconds stare at you as though you have gone mad.")
        await slow_print("  Perhaps you have. The distinction between madness")
        await slow_print("  and perfect indifference is academic.")
        await slow_print("  Gaganov throws his pistol on the ground and weeps.")
        await slow_print(f"  {DIM}The ride home is silent.{RESET}")
        await slow_print(f"  {DIM}Even Kirillov has nothing to say.{RESET}")
        await slow_print(f"  {DIM}The birches really are very fine.{RESET}")
    elif choice == 4:
        state["soul"] += 15
        state["ennui"] -= 10
        state["shatov_bond"] += 5
        state["decisions"].append("offered_hand_to_gaganov")
        await slow_print("\n  You lower the pistol. You walk forward.")
        await slow_print("  Twenty paces. Past the mark. Past the rules.")
        await slow_print("  Gaganov watches you come, pistol forgotten in his hand.")
        await slow_print("  You stop in front of him and extend your hand.")
        await slow_print('  "Forgive me," you say.')
        await slow_print("  Not for the duel. For the nose. For his father.")
        await slow_print("  For the casual cruelty of a bored aristocrat.")
        await slow_print("  Gaganov stares at your hand. His lip trembles.")
        await slow_print("  He does not take it. He turns and walks away.")
        await slow_print(f"  {DIM}But something moved in his face before he turned.{RESET}")
        await slow_print(f"  {DIM}Something that might have been — in another life —{RESET}")
        await slow_print(f"  {DIM}the beginning of forgiveness.{RESET}")

    print()
    await slow_print("  On the ride back, Kirillov is quiet for a long time.")
    await slow_print("  Then he says, very softly, without looking at you:")
    await slow_print(f'  {DIM}"You had better not come to me tonight.{RESET}')
    await slow_print(f'  {DIM} You are not a strong person, Stavrogin.{RESET}')
    await slow_print(f'  {DIM} I can see that now."{RESET}')
    await slow_print(f"  {DIM}He is wrong. Or he is right.{RESET}")
    await slow_print(f"  {DIM}Strength and emptiness look the same from outside.{RESET}")

    clamp_stats()
    show_status()
    await press_enter()


# ═══════════════════════════════════════════════════════════════
#  PART II: NIGHT — THE VISITS
# ═══════════════════════════════════════════════════════════════

async def chapter_3_night_kirillov():
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

    await slow_print(f"  {BOLD}CHAPTER III: NIGHT — KIRILLOV{RESET}")
    print()
    await slow_print("  Eight days after the scandal. Monday night, seven o'clock.")
    await slow_print("  You have been in your rooms at Skvoreshniki, seeing no one,")
    await slow_print("  not even your mother. The swelling on your face has gone down.")
    await slow_print("  Tonight, finally, you go out.")
    print()
    await slow_print("  Filipov's house. A ramshackle building on Bogoyavlensky Street.")
    await slow_print("  Kirillov lodges on the ground floor. Shatov lives upstairs.")
    await slow_print("  The staircase smells of cabbage and philosophical despair.")
    print()
    await slow_print("  Alexei Nilych Kirillov opens his door. He has been doing")
    await slow_print("  his exercises — he is always doing exercises, or drinking tea,")
    await slow_print("  or bouncing an india-rubber ball against the wall.")
    await slow_print("  His room is bare. A table. A candle. The samovar.")
    await slow_print("  He pours you tea without being asked.")
    print()
    await slow_print('  "I walk about the room," Kirillov says matter-of-factly.')
    await slow_print('  "I walk and I think. I have thought of something extraordinary."')
    print()
    await slow_print('  He pauses. His eyes are calm and bright.')
    await slow_print('  "If there is no God, then I am God. If I am God,')
    await slow_print('   then I must express my self-will to the highest degree.')
    await slow_print('   The highest degree of self-will is to kill oneself.')
    await slow_print('   Not from despair. From freedom."')
    print()
    await slow_print("  He pours more tea. His hands are steady.")
    await slow_print("  This is a man who has resolved to die and has found")
    await slow_print("  perfect peace in the resolution.")
    print()

    await slow_print("  How do you respond to the logical suicide?")

    choice = await get_choice([
        '"Your logic is madness, Kirillov."',
        "Listen in silence. Drink the tea. Let him speak.",
        '"If you are so free, why haven\'t you done it yet?"',
        '"Remember what you have meant in my life, Kirillov."',
    ])

    if choice == 1:
        state["soul"] += 10
        state["ennui"] -= 5
        state["decisions"].append("called_kirillov_mad")
        await slow_print('\n  "That is what they all say," Kirillov answers calmly.')
        await slow_print('  "But name one act more rational than choosing')
        await slow_print('   the moment and manner of your own end."')
        await slow_print('  "Living," you say, surprising yourself.')
        await slow_print("  Kirillov considers this with genuine interest,")
        await slow_print("  like a mathematician presented with a new proof.")
        await slow_print('  "But you do not live, Stavrogin. You endure.')
        await slow_print('   That is not the same."')
        await slow_print(f"  {DIM}The candle gutters. Neither of you has a rebuttal.{RESET}")
        state["tea_consumed"] += 1
    elif choice == 2:
        state["ennui"] += 10
        state["tea_consumed"] += 3
        state["decisions"].append("listened_to_kirillov")
        await slow_print("\n  You listen. Kirillov talks for two hours.")
        await slow_print("  About God. About freedom. About a spider he watched")
        await slow_print("  for three days, trying to determine if it chose")
        await slow_print("  to build its web or was merely compelled.")
        await slow_print("  About the moment between sleep and waking")
        await slow_print("  when all things are possible and nothing is true.")
        await slow_print("  His logic is airtight and insane —")
        await slow_print("  a perfect closed system, like a clock that only")
        await slow_print("  tells the time of its own unwinding.")
        await slow_print(f"  {DIM}The tea grows cold. Dawn approaches.{RESET}")
        await slow_print(f"  {DIM}He has promised to kill himself and leave a note{RESET}")
        await slow_print(f"  {DIM}taking responsibility for the group's crimes.{RESET}")
        await slow_print(f"  {DIM}Pyotr Verkhovensky arranged this. Of course he did.{RESET}")
    elif choice == 3:
        state["ennui"] += 5
        state["soul"] -= 5
        state["decisions"].append("challenged_kirillov")
        await slow_print("\n  Kirillov's smile fades. Then returns, wider.")
        await slow_print('  "The moment must be right. It must be an act')
        await slow_print("   of pure will, not despair. I am waiting for the")
        await slow_print('   right moment — when it will mean the most."')
        await slow_print('  "Mean the most to whom? You will be dead."')
        await slow_print("  A very long pause. The india-rubber ball")
        await slow_print("  sits motionless on the floor between you.")
        await slow_print('  "To humanity," he says at last.')
        await slow_print(f"  {DIM}You have planted a seed of doubt in a man{RESET}")
        await slow_print(f"  {DIM}who was perfectly certain. Whether this is mercy{RESET}")
        await slow_print(f"  {DIM}or cruelty, you genuinely cannot say.{RESET}")
        state["tea_consumed"] += 1
    elif choice == 4:
        state["soul"] += 5
        state["ennui"] += 5
        state["decisions"].append("acknowledged_kirillov")
        await slow_print("\n  Kirillov's face softens — the only time you have")
        await slow_print("  seen it do so.")
        await slow_print('  "I know what I meant," he says quietly.')
        await slow_print('  "You told me about the God-bearing people. And then')
        await slow_print("   you told me there was no God. Both at the same time.")
        await slow_print('   Both with perfect sincerity."')
        await slow_print('  "I was not lying either time."')
        await slow_print('  "I know. That is why you are the most dangerous')
        await slow_print('   man alive, Stavrogin."')
        await slow_print(f"  {DIM}He says it without malice. As a fact.{RESET}")
        await slow_print(f"  {DIM}Like reporting the weather, or the time.{RESET}")
        state["tea_consumed"] += 2

    # Second beat: Kirillov shows the view from his window
    print()
    await slow_print("  Before you leave, Kirillov does something unexpected.")
    await slow_print("  He takes the candle and walks to the window.")
    await slow_print('  "Come here," he says. "I want to show you something."')
    await slow_print("  You stand beside him. The window faces east.")
    await slow_print("  Beyond the rooftops: the river, the bridge, the fields.")
    await slow_print("  The moon is full. Everything is silver and black.")
    print()
    await slow_print('  "There are seconds," Kirillov says,')
    await slow_print('  "they come five or six at a time —')
    await slow_print("   and you suddenly feel the presence of eternal harmony.")
    await slow_print("   It's something not earthly. Not that it's heavenly,")
    await slow_print("   but a man in his earthly form can't endure it.")
    await slow_print('   He must be physically changed or die."')
    print()
    await slow_print('  "Five seconds of it — and you would give')
    await slow_print('   your whole life for it."')
    print()
    await slow_print("  He is looking at the moonlit river.")
    await slow_print("  His face, in the candlelight, is transformed —")
    await slow_print("  not ecstatic but perfectly still, perfectly present,")
    await slow_print("  as though for this one moment the gap between")
    await slow_print("  logic and feeling has closed.")
    print()
    await slow_print("  You look at the river. You feel nothing.")
    await slow_print("  But you remember what feeling felt like,")
    await slow_print("  and for a man in your condition,")
    await slow_print("  that is something.")
    print()
    await slow_print(f'  "Good-bye, Kirillov."')
    await slow_print(f'  "Come again at night. I know how to wake up.')
    await slow_print(f"   I say 'seven o'clock' and I wake at seven.")
    await slow_print(f'   I say \'ten o\'clock\' and I wake at ten."')
    await slow_print(f'  "You have remarkable powers," you say,')
    await slow_print(f"   looking at his pale face in the candlelight.")

    clamp_stats()
    show_status()
    await press_enter()


async def chapter_4_night_shatov():
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

    await slow_print(f"  {BOLD}CHAPTER IV: NIGHT — SHATOV{RESET}")
    print()
    await slow_print("  Up the stairs. Utter darkness in the passage.")
    await slow_print("  A door opens above. Light appears.")
    await slow_print("  Shatov does not come out, but stands at his table, waiting.")
    await slow_print("  He has been waiting for eight days. Perhaps longer.")
    await slow_print("  Perhaps he has been waiting for you his entire life.")
    print()
    await slow_print("  His garret is small. Three bookshelves. A revolver")
    await slow_print("  on the uppermost shelf — bought from Lyamshin")
    await slow_print("  in a delirium that you were coming to kill him.")
    print()
    await slow_print("  He has grown thinner. He seems feverish.")
    await slow_print('  "You\'ve been worrying me to death," he says softly.')
    await slow_print('  "Why didn\'t you come?"')
    print()
    await slow_print("  You sit. He sits. The candle between you.")
    await slow_print("  You tell him what you have come to tell him:")
    await slow_print("  that you are a member of the same secret society,")
    await slow_print("  and that they may murder him.")
    print()
    await slow_print("  Shatov stares at you, wild-eyed.")
    await slow_print('  "You... you are a member of the society?"')
    print()
    await slow_print("  Then the real conversation begins.")
    await slow_print("  Not about danger. About everything else.")
    await slow_print("  About God, and Russia, and the god-bearing people.")
    await slow_print("  About words you spoke to him years ago")
    await slow_print("  that rearranged his entire soul.")
    print()
    await slow_print('  "You told me," Shatov says, pacing, trembling,')
    await slow_print('  "that the Russian people are the only')
    await slow_print("   god-bearing people on earth, destined to regenerate")
    await slow_print('   and save the world in the name of a new God."')
    await slow_print('  "I remember."')
    await slow_print('  "You said it with such conviction — such fire —')
    await slow_print("   that I left everything. My wife, my work,")
    await slow_print("   my whole life in Geneva. I came back to Russia")
    await slow_print('   because of what you said to me."')
    print()
    await slow_print("  He stops pacing. His hands grip the back of a chair.")
    await slow_print("  The knuckles are white. A candle on the shelf")
    await slow_print("  throws his shadow enormous against the wall.")
    print()
    await slow_print('  "And then — in the same breath, the same evening —')
    await slow_print("   you told Kirillov there was no God at all.")
    await slow_print("   That man must become God through self-will.")
    await slow_print('   Both! At the same time! With the same sincerity!"')
    print()
    await slow_print("  His voice rises. He is shaking.")
    await slow_print('  "Do you believe in God, Stavrogin?')
    await slow_print('   You — who told me everything I now believe —')
    await slow_print('   do you yourself believe in God?"')
    print()

    await slow_print("  What do you answer?")

    choice = await get_choice([
        '"I believe in Russia... I believe in her orthodoxy..."',
        '"I shall not lie to you. I do not believe."',
        '"I... I will believe in God." (Shatov\'s own answer.)',
        "Change the subject. Ask about Marya Timofeyevna instead.",
        '"There is nothing. No God. No Russia. No you. Nothing."',
    ])

    if choice == 5:
        state["decisions"].append("destroyed_shatov")
        await game_over([
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
        await slow_print("\n  The words come out before you can stop them.")
        await slow_print("  Shatov stares. His whole body trembles.")
        await slow_print('  "Those are my words. You gave them to me')
        await slow_print('   and now you speak them back to me as your own?"')
        await slow_print('  "Perhaps they were always yours."')
        await slow_print("  Shatov's eyes fill with tears.")
        await slow_print('  "And in God? In God?"')
        await slow_print("  You do not answer. But you do not deny.")
        await slow_print(f"  {DIM}The silence between you is more honest{RESET}")
        await slow_print(f"  {DIM}than any words in any language.{RESET}")
    elif choice == 2:
        state["ennui"] += 10
        state["soul"] -= 5
        state["shatov_bond"] -= 5
        state["decisions"].append("declared_atheism")
        await slow_print('\n  "Are you an atheist now?" Shatov whispers.')
        await slow_print('  "Yes."')
        await slow_print('  "And then? When you told me those things?"')
        await slow_print('  "Just as I was then."')
        await slow_print("  Shatov flinches as though struck a second time.")
        await slow_print('  "You were an atheist even when you told me about')
        await slow_print('   the god-bearing people? About the body of Christ?"')
        await slow_print('  "I was not lying. In persuading you I was perhaps')
        await slow_print('   more concerned with myself than with you."')
        await slow_print(f"  {DIM}This is the most honest thing you have ever said.{RESET}")
        await slow_print(f"  {DIM}It is also the most terrible.{RESET}")
    elif choice == 3:
        state["soul"] += 15
        state["ennui"] -= 10
        state["shatov_bond"] += 10
        state["decisions"].append("will_believe")
        await slow_print('\n  "I... I will believe in God."')
        await slow_print("  The words fall into the room like stones into water.")
        await slow_print("  Shatov stares at you. His mouth opens. Closes.")
        await slow_print("  Not one muscle moves in your face.")
        await slow_print("  He cannot tell if this is mockery or revelation.")
        await slow_print("  Neither can you.")
        await slow_print(f"  {DIM}The future tense is the most dangerous verb form{RESET}")
        await slow_print(f"  {DIM}in the Russian language. It promises everything.{RESET}")
        await slow_print(f"  {DIM}It delivers nothing. But it keeps the door open.{RESET}")
    elif choice == 4:
        state["marya_bond"] += 5
        state["shatov_bond"] += 5
        state["decisions"].append("asked_about_marya")
        await slow_print("\n  You cannot answer the question. You change course.")
        await slow_print('  "I have a favor to ask about Marya Timofeyevna.')
        await slow_print("   You are the only person who has influence over her")
        await slow_print('   poor brain. I want you to look after her."')
        await slow_print("  Shatov is thrown off balance.")
        await slow_print('  "You speak so calmly... Your wife... and you ask me—"')
        await slow_print('  "Yes. I ask you."')
        await slow_print("  Something passes between you — not understanding,")
        await slow_print("  exactly, but the acknowledgment of a shared wound.")
        await slow_print(f"  {DIM}He nods. Once. That is enough.{RESET}")

    # Shatov's emotional breakdown — the weight of it
    print()
    await slow_print("  The room is very quiet. The candle has burned low.")
    await slow_print("  Shatov sinks into a chair. He puts his face in his hands.")
    await slow_print('  "I was nothing before you spoke to me," he says,')
    await slow_print("  his voice muffled through his fingers.")
    await slow_print('  "And now I am nothing again. But at least')
    await slow_print('   I know what everything looks like."')
    await slow_print("  He looks up. His eyes are red.")
    await slow_print('  "You created a soul in me, Stavrogin.')
    await slow_print('   And you don\'t even have one of your own."')
    await slow_print("  The words hang in the air between you.")
    await slow_print("  You should be angry. You are not.")
    await slow_print("  You should deny it. You cannot.")
    await slow_print(f"  {DIM}The man who slapped you eight days ago{RESET}")
    await slow_print(f"  {DIM}is the man who understands you best.{RESET}")
    await slow_print(f"  {DIM}This is how it works in Dostoevsky.{RESET}")

    # The warning about murder
    print()
    await slow_print("  Before you leave, you lean close:")
    await slow_print('  "I told you that they may murder you.')
    await slow_print("   Pyotr Verkhovensky is authorized to do it.")
    await slow_print('   You know too much, and they think you are a spy."')
    await slow_print('  "I\'ve broken with them!" Shatov cries.')
    await slow_print('  "He\'s a bug, an ignoramus!"')
    await slow_print('  "Verkhovensky is an enthusiast," you reply.')
    await slow_print('  "There is a point when he ceases to be a buffoon')
    await slow_print('   and becomes a madman."')
    state["warned_shatov"] = True

    clamp_stats()
    show_status()
    await press_enter()


async def chapter_5_night_lebyadkins():
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

    await slow_print(f"  {BOLD}CHAPTER V: NIGHT — THE LEBYADKINS AND FEDKA{RESET}")
    print()
    await slow_print("  You cross the river to the new lodgings.")
    await slow_print("  Captain Lebyadkin — your brother-in-law, God help you —")
    await slow_print("  opens the door drunk, in his undershirt.")
    await slow_print('  "Prince! Your Excellency!" He is instantly fawning.')
    await slow_print("  Behind him: empty bottles, the smell of herring,")
    await slow_print("  and terrible poetry scattered across the table.")
    print()
    await slow_print("  But you are here for Marya Timofeyevna.")
    await slow_print("  She sits in the far room, wearing a clean white dress,")
    await slow_print("  her hair neatly combed, as though expecting you.")
    await slow_print("  She always seems to be expecting someone.")
    print()
    await slow_print("  She looks at you with her strange, penetrating eyes.")
    await slow_print("  There is a long silence.")
    print()
    await slow_print('  "You are not he," she says suddenly.')
    await slow_print('  "Not who?"')
    await slow_print('  "Not my prince. My prince was bright as the sun.')
    await slow_print('   You look like him, but you are not him.')
    await slow_print('   You are an impostor."')
    print()
    await slow_print("  She has seen through you. The holy fool,")
    await slow_print("  the lame woman, the beggar you married on a dare —")
    await slow_print("  she is the only person alive who can see")
    await slow_print("  that behind your face there is no one.")
    print()

    await slow_print("  How do you respond?")

    choice = await get_choice([
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
        await slow_print('\n  Her face softens. Almost with pity.')
        await slow_print('  "I knew. I always knew. But sometimes')
        await slow_print('   you looked so much like him that I forgot."')
        await slow_print("  She reaches out and touches your cheek —")
        await slow_print("  the cheek Shatov slapped.")
        await slow_print('  "Poor impostor," she whispers.')
        await slow_print(f"  {DIM}No one has ever pitied you before.{RESET}")
        await slow_print(f"  {DIM}You are not sure you can survive it.{RESET}")
    elif choice == 2:
        state["ennui"] += 5
        state["soul"] += 5
        state["decisions"].append("promised_provision")
        await slow_print("\n  She waves this away like a child waving away a fly.")
        await slow_print('  "Money, money. The Captain always talks about money.')
        await slow_print('   I do not want money. I want the prince."')
        await slow_print('  "Marya Timofeyevna—"')
        await slow_print('  "Do you know, I had a baby once," she says dreamily.')
        await slow_print('  "It was very small. I brought it to a pond in the night')
        await slow_print('   and drowned it, and I have been crying ever since."')
        await slow_print("  She never had a baby. Marya Timofeyevna is a virgin.")
        await slow_print("  But she speaks of it as though reporting the weather.")
        await slow_print(f"  {DIM}You sit with her until dawn. The Captain snores.{RESET}")
        await slow_print(f"  {DIM}Neither of you speaks again. It is enough.{RESET}")
    elif choice == 3:
        state["ennui"] += 10
        state["marya_bond"] += 5
        state["decisions"].append("stood_before_marya")
        await slow_print("\n  You stand. She looks at you.")
        await slow_print("  Minutes pass. The candle burns lower.")
        await slow_print("  She is reading you like a book in a language")
        await slow_print("  only she understands.")
        await slow_print('  "There is a knife in your heart," she says finally.')
        await slow_print('  "Someone put it there. Maybe you."')
        await slow_print("  She crosses herself and turns away.")
        await slow_print(f"  {DIM}You leave. On the stairs, your hands are trembling.{RESET}")
        await slow_print(f"  {DIM}You do not know why. You never know why.{RESET}")
    elif choice == 4:
        state["ennui"] += 15
        state["soul"] -= 10
        state["decisions"].append("fled_from_marya")
        await slow_print("\n  You turn on your heel and walk out.")
        await slow_print("  Lebyadkin calls after you, something about money.")
        await slow_print("  You do not answer. The night air hits your face.")
        await slow_print("  You are walking fast, almost running.")
        await slow_print("  From a lame woman in a clean white dress.")
        await slow_print(f"  {DIM}She is the only person who terrifies you.{RESET}")
        await slow_print(f"  {DIM}Not because of what she says,{RESET}")
        await slow_print(f"  {DIM}but because she sees.{RESET}")

    # Fedka on the bridge
    print()
    await slow_print(f"  {RED}  On the bridge: a figure in the dark.{RESET}")
    await slow_print(f"  {RED}  Fedka the Convict — an escaped prisoner,{RESET}")
    await slow_print(f"  {RED}  a man Pyotr Verkhovensky has been using{RESET}")
    await slow_print(f"  {RED}  as a weapon with legs.{RESET}")
    print()
    await slow_print('  "Your Honor," Fedka says, showing his teeth,')
    await slow_print('  "I could relieve you of certain... difficulties.')
    await slow_print('   The Captain and his sister. An accident, perhaps.')
    await slow_print('   Fire is so common in the riverside quarter."')
    print()

    await slow_print("  What do you do?")

    choice2 = await get_choice([
        '"Get away from me." Strike him and walk on.',
        "Give him nothing. But do not refuse clearly either.",
        '"Here are three roubles. Now leave me alone."',
        "Turn your back on him. Walk slowly.",
    ])

    if choice2 == 4:
        state["decisions"].append("turned_back_on_fedka")
        await game_over([
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
        await slow_print("\n  You hit Fedka hard enough that he staggers.")
        await slow_print('  "I told you before. I won\'t give you money."')
        await slow_print("  Fedka spits blood and grins. He has been hit")
        await slow_print("  by better men. He will wait.")
        await slow_print(f"  {DIM}Later, Pyotr Verkhovensky will use this refusal{RESET}")
        await slow_print(f"  {DIM}against you. Everything becomes leverage.{RESET}")
    elif choice2 == 2:
        state["pyotr_entangled"] += 10
        state["ennui"] += 5
        state["decisions"].append("ambiguous_with_fedka")
        await slow_print("\n  You walk past him without a word.")
        await slow_print("  Fedka falls into step beside you.")
        await slow_print('  "Your Honor will think about it?"')
        await slow_print("  You say nothing. Silence, again.")
        await slow_print("  Fedka takes the silence as he pleases.")
        await slow_print(f"  {DIM}Ambiguity, again. Your specialty.{RESET}")
        await slow_print(f"  {DIM}The gap between a yes and a no is where{RESET}")
        await slow_print(f"  {DIM}murders get committed.{RESET}")
        state["took_fedkas_offer"] = True
    elif choice2 == 3:
        state["soul"] -= 5
        state["pyotr_entangled"] += 15
        state["decisions"].append("paid_fedka")
        await slow_print("\n  You give him three roubles. He takes them")
        await slow_print("  with the dignity of a man accepting his due.")
        await slow_print('  "God bless you, Your Honor."')
        await slow_print("  He disappears into the darkness under the bridge.")
        await slow_print(f"  {DIM}Three roubles. The price of nothing.{RESET}")
        await slow_print(f"  {DIM}Or the price of everything.{RESET}")
        await slow_print(f"  {DIM}Pyotr Verkhovensky will later say you gave Fedka{RESET}")
        await slow_print(f"  {DIM}the money as payment for the Lebyadkins.{RESET}")
        await slow_print(f"  {DIM}This is a lie. But lies are load-bearing walls{RESET}")
        await slow_print(f"  {DIM}in Pyotr Verkhovensky's architecture.{RESET}")
        state["took_fedkas_offer"] = True

    clamp_stats()
    show_status()
    await press_enter()


# ═══════════════════════════════════════════════════════════════
#  IVAN THE TSAREVITCH
# ═══════════════════════════════════════════════════════════════

async def chapter_6_ivan_tsarevitch():
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

    await slow_print(f"  {BOLD}CHAPTER VI: IVAN THE TSAREVITCH{RESET}")
    print()
    await slow_print("  The meeting at Virginsky's is over. Pyotr Verkhovensky's")
    await slow_print("  revolutionary cell — the five — have been harangued,")
    await slow_print("  manipulated, bound together with mutual suspicion.")
    await slow_print("  Shigalyov presented his system: starting from unlimited")
    await slow_print("  freedom, he arrives at unlimited despotism.")
    await slow_print("  No one found this alarming.")
    print()
    await slow_print("  Now Pyotr Stepanovich catches up to you on the road.")
    await slow_print("  Mud to his knees. Eyes bright with ideology.")
    await slow_print("  He clutches your sleeve and will not let go.")
    print()
    await slow_print('  "Listen, Stavrogin!" he says, gasping, rapid.')
    await slow_print('  "We are going to make a revolution! Such an upheaval')
    await slow_print('   that everything will be uprooted from its foundation!"')
    print()
    await slow_print("  He tells you about Shigalovism: every member spies on")
    await slow_print("  every other. Total equality through total slavery.")
    await slow_print("  Great intellects banished. Shakespeare stoned.")
    await slow_print("  Cicero's tongue cut out. Copernicus blinded.")
    print()
    await slow_print('  "But I\'ve given up Shigalov!" he cries.')
    await slow_print('  "I need something more everyday.')
    await slow_print('   The Pope shall be for the west.')
    await slow_print('   And you — you shall be for us!"')
    print()
    await slow_print("  He is trembling. He clutches your arm.")
    await slow_print('  "Stavrogin, you are beautiful!" he says,')
    await slow_print("  almost ecstatically. He kisses your hand.")
    await slow_print("  A shiver runs down your spine.")
    print()
    await slow_print('  "You are the leader, you are the sun,')
    await slow_print('   and I am your worm!"')
    print()
    await slow_print('  He reveals his plan: you will be Ivan the Tsarevitch.')
    await slow_print("  The hidden prince. The legend. The face of revolution.")
    await slow_print('  "He exists, but no one has seen him.')
    await slow_print("   Oh, what a legend one can set going!\"")
    print()

    await slow_print("  What do you make of this madman?")

    choice = await get_choice([
        '"Madman!" Pull your hand away and leave.',
        '"I won\'t give up Shatov to you." Refuse the blood price.',
        '"Then have you been seriously reckoning on me?"',
        "Listen to all of it. Let him empty himself.",
        '"Yes. I will be your Ivan Tsarevitch."',
    ])

    if choice == 5:
        state["decisions"].append("became_ivan_tsarevitch")
        await game_over([
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
        await slow_print('\n  "Madman!" You pull your hand away.')
        await slow_print("  But Pyotr runs after you. He always runs after you.")
        await slow_print('  "Let us make it up!" he whispers, spasmodic.')
        await slow_print('  "Let us make it up! I\'ll bring you Lizaveta')
        await slow_print('   Nikolaevna tomorrow — shall I?"')
        await slow_print("  You shrug. You walk on. He trails behind.")
        await slow_print("  He is a man from whom the most precious thing")
        await slow_print("  is being taken — your attention.")
        await slow_print(f"  {DIM}Pyotr Verkhovensky without Stavrogin{RESET}")
        await slow_print(f"  {DIM}is Columbus without America.{RESET}")
        await slow_print(f"  {DIM}He said that himself. He believes it.{RESET}")
    elif choice == 2:
        state["soul"] += 15
        state["shatov_bond"] += 10
        state["pyotr_entangled"] -= 5
        state["decisions"].append("refused_shatovs_blood")
        await slow_print('\n  "I won\'t give up Shatov to you."')
        await slow_print("  Pyotr starts. You look at each other.")
        await slow_print('  "I told you this evening why you needed Shatov\'s blood.')
        await slow_print("   It's the cement to bind your groups together.")
        await slow_print('   I will not be party to it."')
        await slow_print("  Pyotr's face changes — something raw underneath")
        await slow_print("  the performance. Fear, perhaps. Or love.")
        await slow_print("  It is hard to tell with men like this.")
        await slow_print('  "Let us make it up!" he begs.')
        await slow_print('  "I have a knife in my boot, but I\'ll make it up!"')
        await slow_print(f"  {DIM}The most dangerous man in the province{RESET}")
        await slow_print(f"  {DIM}is begging you not to leave him.{RESET}")
        await slow_print(f"  {DIM}You leave him anyway.{RESET}")
    elif choice == 3:
        state["pyotr_entangled"] += 10
        state["revolutionary_fervor"] += 10
        state["ennui"] -= 5
        state["decisions"].append("questioned_the_plan")
        await slow_print('\n  "A pretender?" You look at him with surprise.')
        await slow_print('  "So that is your plan at last."')
        await slow_print("  Pyotr's face shines.")
        await slow_print('  "We shall say he is \'in hiding.\' Do you know')
        await slow_print("   the magic of that phrase? He exists, but no one")
        await slow_print("   has seen him. We'll set a legend going!")
        await slow_print('   We only need one lever to lift the earth!"')
        await slow_print("  You listen. Against your will, you are interested.")
        await slow_print("  Not in the revolution — in the mechanism.")
        await slow_print("  The clockwork of belief. The engineering of hope.")
        await slow_print(f"  {DIM}You are the most dangerous possible audience{RESET}")
        await slow_print(f"  {DIM}for a man like Pyotr Verkhovensky:{RESET}")
        await slow_print(f"  {DIM}intelligent enough to see the game,{RESET}")
        await slow_print(f"  {DIM}empty enough to play it.{RESET}")
    elif choice == 4:
        state["ennui"] += 10
        state["pyotr_entangled"] += 15
        state["revolutionary_fervor"] += 5
        state["decisions"].append("let_pyotr_rave")
        await slow_print("\n  You let him talk. He talks for the entire walk home.")
        await slow_print("  Revolution. Destruction. Teachers who laugh at God.")
        await slow_print("  Lawyers who defend murderers. Peasants drunk on vodka.")
        await slow_print("  One or two generations of vice, he says, are necessary.")
        await slow_print("  Monstrous, abject vice. Fresh blood.")
        await slow_print("  He says all of this while clutching your sleeve")
        await slow_print("  in the mud, in the dark, on a provincial road.")
        await slow_print(f"  {DIM}He is in a fever. He is raving.{RESET}")
        await slow_print(f"  {DIM}He is also, perhaps, the future.{RESET}")
        await slow_print(f"  {DIM}That is the terrible thing.{RESET}")

    clamp_stats()
    show_status()
    await press_enter()


# ═══════════════════════════════════════════════════════════════
#  THE CONSPIRATORS' MEETING
# ═══════════════════════════════════════════════════════════════

async def chapter_7_meeting():
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

    await slow_print(f"  {BOLD}CHAPTER VII: A MEETING{RESET}")
    print()
    await slow_print("  The meeting at Virginsky's. The famous gathering of the five.")
    await slow_print("  Or seven. Or however many Pyotr Verkhovensky needs tonight.")
    print()
    await slow_print("  They are here: Virginsky, the pure-hearted liberal.")
    await slow_print("  Liputin, the rogue with one good point.")
    await slow_print("  Shigalyov, with his ears like donkey-ears")
    await slow_print("  and his manuscript on the reorganization of society.")
    await slow_print("  Lyamshin, who will break first.")
    await slow_print("  And Pyotr Stepanovich, the spider at the center.")
    print()
    await slow_print("  Shigalyov presents his system. He speaks for ten minutes.")
    await slow_print("  The room is baffled. He concludes:")
    await slow_print(f'  {REVERSE}  "Starting from unlimited freedom,   {RESET}')
    await slow_print(f'  {REVERSE}   I arrive at unlimited despotism."  {RESET}')
    print()
    await slow_print("  He acknowledges this is a contradiction.")
    await slow_print("  He believes there is no other solution.")
    print()
    await slow_print("  Pyotr steers the meeting toward the real purpose:")
    await slow_print("  binding the group. Creating mutual complicity.")
    await slow_print('  He asks: "Would each of you inform the authorities')
    await slow_print('   if you discovered a planned political murder?"')
    print()
    await slow_print("  Shatov stands up and shouts: 'I refuse to answer")
    await slow_print("  such a question!' He leaves, slamming the door.")
    print()
    await slow_print("  The room looks at Pyotr. Pyotr looks at you.")
    await slow_print("  The candle flickers.")
    print()

    await slow_print("  What is your role here?")

    choice = await get_choice([
        "Observe. You are collecting data, not taking sides.",
        '"Shatov is right. This meeting is a farce."',
        "Stay silent. Your silence binds them as much as any words.",
        "Leave. Follow Shatov out.",
        '"Shatov is a traitor. Do what must be done."',
    ])

    if choice == 5:
        state["decisions"].append("endorsed_murder")
        await game_over([
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
        await slow_print("\n  You watch. Pyotr talks. The conspirators shuffle,")
        await slow_print("  argue, posture. Virginsky pleads for principles.")
        await slow_print("  Liputin calculates odds. Shigalyov reads his manuscript")
        await slow_print("  to no one in particular.")
        await slow_print("  You see it all clearly: a handful of fools")
        await slow_print("  magnifying their own significance.")
        await slow_print("  And Pyotr, the only one among them who is dangerous,")
        await slow_print("  because he alone has no ideology — only will.")
        await slow_print(f"  {DIM}You are the sanest person in the room.{RESET}")
        await slow_print(f"  {DIM}This does not comfort you.{RESET}")
    elif choice == 2:
        state["soul"] += 10
        state["revolutionary_fervor"] -= 10
        state["pyotr_entangled"] -= 5
        state["decisions"].append("called_meeting_farce")
        await slow_print('\n  "This is a farce," you say, evenly.')
        await slow_print("  The room falls silent.")
        await slow_print("  Pyotr laughs — too quickly, too loudly.")
        await slow_print('  "Stavrogin jokes! He is above our petty planning."')
        await slow_print("  But his eyes are not laughing.")
        await slow_print("  You have said the quiet part aloud.")
        await slow_print("  That none of this has any plan beyond destruction.")
        await slow_print("  That the new world they imagine is a blank page")
        await slow_print("  they are terrified to fill.")
        await slow_print(f"  {DIM}The truth, in a room full of revolutionaries,{RESET}")
        await slow_print(f"  {DIM}is the most revolutionary act of all.{RESET}")
    elif choice == 3:
        state["ennui"] += 15
        state["pyotr_entangled"] += 10
        state["notoriety"] += 10
        state["decisions"].append("silent_at_meeting")
        await slow_print("\n  You sit in the corner. Silent. Everyone steals")
        await slow_print("  glances at you. Pyotr references you constantly:")
        await slow_print('  "Stavrogin knows... Stavrogin understands..."')
        await slow_print("  You have said nothing. You have endorsed nothing.")
        await slow_print("  But your presence is a signature on a blank check.")
        await slow_print("  They will fill in the amount later.")
        await slow_print(f"  {DIM}In the darkness of the room, emptiness{RESET}")
        await slow_print(f"  {DIM}and depth are indistinguishable.{RESET}")
    elif choice == 4:
        state["shatov_bond"] += 10
        state["soul"] += 5
        state["pyotr_entangled"] -= 10
        state["decisions"].append("followed_shatov_out")
        await slow_print("\n  You stand and walk out after Shatov.")
        await slow_print("  The room erupts behind you. Pyotr calls your name.")
        await slow_print("  You do not turn around.")
        await slow_print("  In the street, Shatov is walking fast.")
        await slow_print('  "You followed me out," he says, not looking at you.')
        await slow_print('  "Yes."')
        await slow_print('  "Does that mean something?"')
        await slow_print('  "I don\'t know."')
        await slow_print("  You walk together in silence for a long time.")
        await slow_print(f"  {DIM}Two men who cannot believe in anything{RESET}")
        await slow_print(f"  {DIM}walking side by side in the dark.{RESET}")

    clamp_stats()
    show_status()
    await press_enter()


# ═══════════════════════════════════════════════════════════════
#  THE FETE
# ═══════════════════════════════════════════════════════════════

async def chapter_8_fete():
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

    await slow_print(f"  {BOLD}CHAPTER VIII: THE FETE{RESET}")
    print()
    await slow_print("  Yulia Mihailovna — the Governor's wife — has been planning")
    await slow_print("  this fete for months. It will raise money for governesses.")
    await slow_print("  It will feature a literary matinée. Karmazinov,")
    await slow_print("  the famous author, will read his farewell piece.")
    await slow_print("  Stepan Trofimovich will give an address on beauty.")
    await slow_print("  There will be a ball. There will not be champagne.")
    await slow_print("  This last fact will become important.")
    print()
    await slow_print("  The entire town has subscribed. Everyone is here.")
    await slow_print("  But underneath the gaiety there is a feeling")
    await slow_print("  of implacable resentment — a forced, strained cynicism.")
    await slow_print("  The ladies all despise Yulia Mihailovna.")
    await slow_print("  The men are drunk by noon.")
    await slow_print("  Pyotr Verkhovensky's people are in the crowd,")
    await slow_print("  waiting for their signal.")
    print()
    await slow_print("  First: Karmazinov, the famous writer, reads his farewell.")
    await slow_print("  He calls it 'Merci' — a saccharine reminiscence")
    await slow_print("  of his childhood nurse, his first love, the Rhine,")
    await slow_print("  and a blade of grass that taught him the meaning of life.")
    await slow_print("  It goes on for an hour. The audience grows restless.")
    await slow_print("  Someone in the back row falls asleep.")
    await slow_print("  Karmazinov bows to scattered, confused applause")
    await slow_print("  and exits with the air of a man who has given")
    await slow_print("  humanity its final gift.")
    print()
    await slow_print("  Then: Stepan Trofimovich takes the stage.")
    await slow_print("  He is trembling. His waistcoat is buttoned wrong.")
    await slow_print("  His speech is crumpled in his hand.")
    await slow_print("  He looks out at the crowd — three hundred faces,")
    await slow_print("  most of them already hostile from Karmazinov's ordeal.")
    print()
    await slow_print("  He begins to speak — not the speech he prepared,")
    await slow_print("  but something else. Something honest. Something mad.")
    await slow_print("  His voice cracks. He waves his arms.")
    print()
    await slow_print('  "I declare," he cries, his lorgnette trembling,')
    await slow_print('  "that Shakespeare and Raphael are higher than')
    await slow_print('   the emancipation of the serfs! Higher than Socialism!')
    await slow_print('   Higher than the coming generation!')
    await slow_print('   Higher than chemistry!')
    await slow_print('   Higher, perhaps, than almost everything!"')
    print()
    await slow_print('  "Beauty will save the world!"')
    print()
    await slow_print("  The crowd erupts. Not with agreement — with fury.")
    await slow_print('  "That is reactionary!" someone shouts.')
    await slow_print('  "Aesthetics are the privilege of parasites!"')
    await slow_print("  A shoe flies through the air.")
    await slow_print("  Stepan Trofimovich catches it — or rather,")
    await slow_print("  it hits him in the chest, and he stares at it")
    await slow_print("  as though a shoe from the audience is a new phenomenon")
    await slow_print("  that requires careful philosophical analysis.")
    await slow_print("  He begins to weep, still holding the shoe.")
    await slow_print("  Yulia Mihailovna's face is a mask of horror.")
    print()
    await slow_print("  Then the literary quadrille begins. Pyotr arranged it.")
    await slow_print("  Dancers in costumes symbolizing 'Great Thoughts':")
    await slow_print("  someone is dressed as 'The Spirit of Local Government.'")
    await slow_print("  Someone else represents 'The Honest Russian Journalist'")
    await slow_print("  and carries a sign no one can read.")
    await slow_print("  It is chaos dressed as allegory.")
    print()

    await slow_print("  What do you do during the catastrophe?")

    choice = await get_choice([
        "Go to Stepan Trofimovich. Lead him off the stage.",
        "Watch from the back. This is not your disaster.",
        "Find Liza. Something is happening between you tonight.",
        "Leave the fete entirely. Walk into the night.",
        "Walk to the river. The fire across the water is calling.",
    ])

    if choice == 5:
        state["decisions"].append("walked_into_fire")
        await game_over([
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
        await slow_print("\n  You walk to the stage. Through the crowd.")
        await slow_print("  Three hundred people watch you do it.")
        await slow_print("  Stepan Trofimovich is weeping, still quoting Shakespeare,")
        await slow_print("  still insisting that beauty matters more than bread.")
        await slow_print("  You take his arm.")
        await slow_print('  "Come, Stepan Trofimovich. That is enough."')
        await slow_print("  He looks at you with the eyes of a drowning man.")
        await slow_print('  "Nicolas... did I speak well?"')
        await slow_print('  "You spoke the truth. That is always badly received."')
        await slow_print("  You lead him out. Behind you, the fete collapses.")
        await slow_print(f"  {DIM}He will remember this kindness until the day he dies.{RESET}")
        await slow_print(f"  {DIM}That day is not far off.{RESET}")
    elif choice == 2:
        state["ennui"] += 15
        state["notoriety"] += 5
        state["decisions"].append("watched_fete_collapse")
        await slow_print("\n  You stand at the back. Arms crossed.")
        await slow_print("  Watching the provincial world tear itself apart.")
        await slow_print("  Stepan Trofimovich is booed off stage.")
        await slow_print("  Karmazinov reads his interminable farewell.")
        await slow_print("  Someone sets off firecrackers — Pyotr's signal.")
        await slow_print("  The literary quadrille begins, absurd,")
        await slow_print("  with costumes symbolizing thoughts no one understands.")
        await slow_print("  A fight breaks out near the buffet.")
        await slow_print("  Yulia Mihailovna leaves in tears.")
        await slow_print(f"  {DIM}From the back of the room, civilization looks exactly{RESET}")
        await slow_print(f"  {DIM}like a building that has been burning for some time{RESET}")
        await slow_print(f"  {DIM}without anyone noticing.{RESET}")
    elif choice == 3:
        state["liza_bond"] += 15
        state["ennui"] -= 10
        state["soul"] -= 5
        state["decisions"].append("found_liza_at_fete")
        await slow_print("\n  You find Liza near the exit. She is pale, shaking.")
        await slow_print("  Mavriky Nikolaevich hovers nearby, loyal and miserable.")
        await slow_print("  She looks at you and everything in the room stops.")
        await slow_print('  "Take me away from here," she says.')
        await slow_print("  It is not a request. It is a confession.")
        await slow_print("  You take her hand. Mavriky Nikolaevich watches you")
        await slow_print("  lead her away and does not follow.")
        await slow_print("  The fete burns behind you.")
        await slow_print(f"  {DIM}Tonight she will come to your rooms.{RESET}")
        await slow_print(f"  {DIM}Tomorrow she will know the truth about you.{RESET}")
        await slow_print(f"  {DIM}She will not survive the knowing.{RESET}")
    elif choice == 4:
        state["ennui"] += 10
        state["decisions"].append("left_the_fete")
        await slow_print("\n  You walk out into the night.")
        await slow_print("  Behind you, the sounds of the fete —")
        await slow_print("  shouts, music, a crash of crockery.")
        await slow_print("  The air outside is cold and clean.")
        await slow_print("  You walk for a long time.")
        await slow_print("  Past the church. Past the river. Past the bridge")
        await slow_print("  where Fedka waited for you.")
        await slow_print(f"  {DIM}The provincial town is destroying itself.{RESET}")
        await slow_print(f"  {DIM}You are not responsible. Or you are.{RESET}")
        await slow_print(f"  {DIM}The distinction no longer seems important.{RESET}")

    clamp_stats()
    show_status()
    await press_enter()


# ═══════════════════════════════════════════════════════════════
#  LIZA
# ═══════════════════════════════════════════════════════════════

async def chapter_new_liza():
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

    await slow_print(f"  {BOLD}CHAPTER X: LIZA{RESET}")
    print()
    await slow_print("  She came to you.")
    await slow_print("  Lizaveta Nikolaevna Tushina — Liza — came to Skvoreshniki")
    await slow_print("  in the night, alone, without her fiancé,")
    await slow_print("  without her reputation, without anything")
    await slow_print("  except the green dress she was wearing")
    await slow_print("  and the terrible clarity of a woman")
    await slow_print("  who knows exactly what she is destroying.")
    print()
    await slow_print("  Now: dawn. Grey light through the curtains.")
    await slow_print("  She stands at the window, not looking at you.")
    await slow_print("  The green dress is crumpled on the chair.")
    await slow_print("  She is wearing your dressing gown.")
    await slow_print("  Her hair is loose. Her back is very straight.")
    print()
    await slow_print('  "I was a dead woman when I came in yesterday,"')
    await slow_print("  she says, to the window, not to you.")
    await slow_print('  "I knew it was the end. But I wanted')
    await slow_print('   to have this one thing. Even knowing."')
    print()
    await slow_print("  You sit on the edge of the bed.")
    await slow_print("  You look at her and feel — what?")
    await slow_print("  Not love. You have tried love; it did not take.")
    await slow_print("  Not desire. That passed in the night.")
    await slow_print("  Something more like recognition.")
    await slow_print("  She is as doomed as you are, and she knows it,")
    await slow_print("  and she came anyway. That takes a kind of courage")
    await slow_print("  you have never possessed.")
    print()
    await slow_print("  She turns from the window. Her face is pale.")
    await slow_print("  Her eyes are dry — she is past tears.")
    await slow_print('  "Tell me the truth, Stavrogin.')
    await slow_print("   You have lied to everyone. Lie to me too,")
    await slow_print('   if you must. But at least tell me the truth first."')
    print()
    await slow_print('  "What truth?"')
    print()
    await slow_print('  "Do you love me?"')
    print()
    await slow_print("  The question hangs in the grey dawn light.")
    await slow_print("  Outside, a bird begins to sing.")
    await slow_print("  The most ordinary sound in the world.")
    print()

    await slow_print("  What do you tell her?")

    choice = await get_choice([
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
        await slow_print('\n  "I knew I did not love you," you say,')
        await slow_print('  "and yet I ruined you."')
        await slow_print("  Liza's face does not change. She expected this.")
        await slow_print("  That is the worst part — she came knowing.")
        await slow_print('  "You are a monster," she says, without heat.')
        await slow_print('  "A beautiful, empty monster."')
        await slow_print("  She begins to dress. Her movements are precise,")
        await slow_print("  mechanical, the gestures of a woman")
        await slow_print("  who has already left the room in her mind.")
        await slow_print(f"  {DIM}The honesty costs you nothing.{RESET}")
        await slow_print(f"  {DIM}It costs her everything.{RESET}")
    elif choice == 2:
        state["ennui"] += 10
        state["liza_bond"] -= 5
        state["decisions"].append("told_liza_incapable")
        await slow_print("\n  She stares at you for a long time.")
        await slow_print('  "I know," she says. "I have always known.')
        await slow_print("   Everyone sees it — the emptiness behind your eyes.")
        await slow_print("   But I thought — I hoped — that with me,")
        await slow_print('   something might —"')
        await slow_print("  She stops. She will not finish the sentence.")
        await slow_print("  To finish it would be to hear herself beg,")
        await slow_print("  and Liza does not beg.")
        await slow_print("  She sits very still, her hands in her lap.")
        await slow_print(f"  {DIM}You watch a woman's last illusion die.{RESET}")
        await slow_print(f"  {DIM}It makes the same sound as everything else:{RESET}")
        await slow_print(f"  {DIM}silence.{RESET}")
    elif choice == 3:
        state["soul"] += 10
        state["liza_bond"] += 10
        state["ennui"] -= 5
        state["decisions"].append("held_lizas_hand")
        await slow_print("\n  You take her hand. You say nothing.")
        await slow_print("  She looks at your hand holding hers.")
        await slow_print("  Something moves across her face —")
        await slow_print("  not hope, exactly, but the memory of hope.")
        await slow_print("  You sit together in the grey light.")
        await slow_print("  For five minutes, perhaps ten, there is peace.")
        await slow_print("  Not happiness. Not love. Just two people")
        await slow_print("  sitting together in the ruins of everything.")
        await slow_print(f"  {DIM}It is the most tender thing you have done in years.{RESET}")
        await slow_print(f"  {DIM}It is also insufficient. It is always insufficient.{RESET}")
    elif choice == 4:
        state["ennui"] += 5
        state["soul"] += 5
        state["liza_bond"] += 5
        state["decisions"].append("told_liza_perhaps")
        await slow_print('\n  "Perhaps," you say. And then: "I cannot tell')
        await slow_print('   the difference anymore. Between love and its absence.')
        await slow_print("   Between what I feel and what I perform.")
        await slow_print('   I have been acting for so long that the actor"')
        await slow_print('  "— has eaten the man," she finishes. "I know."')
        await slow_print("  She looks at you with something that is not quite pity")
        await slow_print("  and not quite contempt and not quite love.")
        await slow_print("  It is, perhaps, the only honest emotion left in the room.")
        await slow_print(f"  {DIM}Two people who cannot love, failing to love each other.{RESET}")
        await slow_print(f"  {DIM}Dostoevsky would call this the human condition.{RESET}")

    # Pyotr arrives with news of the fire
    print()
    await slow_print(f"  {RED}  Then: a knock at the door.{RESET}")
    await slow_print(f"  {RED}  Pyotr Stepanovich. Of course.{RESET}")
    await slow_print(f"  {RED}  He enters without waiting, sees Liza,{RESET}")
    await slow_print(f"  {RED}  and his face arranges itself into something{RESET}")
    await slow_print(f"  {RED}  between triumph and calculation.{RESET}")
    print()
    await slow_print('  "There has been a fire," he says, almost cheerfully.')
    await slow_print('  "The Zarechye district. And — well —')
    await slow_print('   Captain Lebyadkin and his sister..."')
    await slow_print("  He trails off. He is watching your face.")
    await slow_print("  Liza understands before you do.")
    print()
    await slow_print('  "The cripple?" she whispers. "Your wife?')
    await slow_print('   She is dead?"')
    print()
    await slow_print("  Pyotr says nothing. His silence is an answer.")
    await slow_print("  Liza looks at you. Then at Pyotr. Then at you.")
    await slow_print("  Something terrible assembles itself in her mind —")
    await slow_print("  the connection between this death and this night,")
    await slow_print("  between the convenient fire and the convenient lover.")
    print()
    await slow_print('  "Did you — " she begins.')
    await slow_print('  "No." But your voice comes too late, too flat.')
    print()
    await slow_print("  She runs. Out of the room, out of the house,")
    await slow_print("  into the grey morning, toward the smoke")
    await slow_print("  still rising from the riverside quarter.")
    await slow_print("  You do not follow. Pyotr watches you not follow.")
    print()
    await slow_print(f"  {RED}  The fire. The Lebyadkin house.{RESET}")
    await slow_print(f"  {RED}  Captain Lebyadkin and Marya Timofeyevna.{RESET}")
    await slow_print(f"  {RED}  Their throats cut. Fedka's work.{RESET}")
    print()
    await slow_print(f"  {DIM}  Your wife is dead.{RESET}")
    await slow_print(f"  {DIM}  Murdered by a man you gave three roubles to.{RESET}" if state["took_fedkas_offer"] else f"  {DIM}  Murdered by a man Pyotr Verkhovensky unleashed.{RESET}")
    await slow_print(f"  {DIM}  Or refused. It doesn't matter. She is dead.{RESET}")
    print()
    await slow_print(f"  {DIM}Mavriky Nikolaevich will find Liza at the fire.{RESET}")
    await slow_print(f"  {DIM}He will be waiting, loyal as always.{RESET}")
    await slow_print(f"  {DIM}The crowd will recognize her — Stavrogin's woman —{RESET}")
    await slow_print(f"  {DIM}and they will not be kind.{RESET}")

    state["marya_bond"] = 0

    clamp_stats()
    show_status()
    await press_enter()


# ═══════════════════════════════════════════════════════════════
#  THE MURDER OF SHATOV
# ═══════════════════════════════════════════════════════════════

async def chapter_9_shatov_murder():
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

    await slow_print(f"  {BOLD}CHAPTER IX: A BUSY NIGHT{RESET}")
    print()
    await slow_print("  You are not present for the murder.")
    await slow_print("  But you know it is happening. You warned him.")
    if state["warned_shatov"]:
        await slow_print(f"  {DIM}You warned him and it was not enough.{RESET}")
    print()
    await slow_print("  At this moment, in Skvoreshniki park, by the grotto:")
    await slow_print("  Pyotr Verkhovensky leads Shatov to a spot")
    await slow_print("  where a printing press is supposedly buried.")
    await slow_print("  Shatov bends down to dig.")
    await slow_print("  Pyotr shoots him in the head.")
    print()
    await slow_print("  Virginsky cries: 'It's not right! It's not right at all!'")
    await slow_print("  They weigh the body with stones and sink it in the pond.")
    await slow_print("  Shatov's cap is left behind — an extraordinary carelessness.")
    print()
    await slow_print("  Shatov had just hours earlier held his newborn baby.")
    await slow_print("  His estranged wife had returned to him.")
    await slow_print("  For one night, he had been happy —")
    await slow_print("  the only genuine happiness in this entire story.")
    await slow_print("  And then: the knock on the door.")
    print()
    await slow_print("  Meanwhile, Kirillov fulfills his promise.")
    await slow_print("  He writes the note taking responsibility.")
    await slow_print("  Pyotr dictates: 'I killed Shatov.'")
    await slow_print("  Then Kirillov goes into the next room")
    await slow_print("  and shoots himself.")
    print()
    await slow_print("  His hand trembled. He bit Pyotr's finger first.")
    await slow_print("  In the end, the logical suicide was not so logical.")
    await slow_print("  In the end, the body made its own argument.")
    print()

    await slow_print("  You are alone in your rooms at Skvoreshniki.")
    await slow_print("  What do you do with this night?")

    choice = await get_choice([
        "Write a letter. To Dasha. To anyone. Put words on paper.",
        "Walk to the bridge over the river. Stand in the dark.",
        "Sit in the dark. Let it press down on you.",
        "Prepare to leave. There is nothing left here.",
        "Go to the pond. Watch them do it.",
    ])

    if choice == 5:
        state["decisions"].append("watched_murder")
        await game_over([
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
        await slow_print("\n  You write. The pen scratches in the silence.")
        await slow_print("  To Darya Pavlovna — Dasha — Shatov's sister.")
        await slow_print("  The one person who offered to be your nurse,")
        await slow_print("  your keeper, your last connection to anything human.")
        await slow_print('  "Dear Darya Pavlovna — at one time you expressed')
        await slow_print('   a wish to be my nurse. I am going away.')
        await slow_print('   Will you go with me?"')
        await slow_print("  You write about Uri, in Switzerland. A small house.")
        await slow_print("  A dull place. Mountains that restrict vision and thought.")
        await slow_print('  "I expect nothing of Uri. I am simply going."')
        await slow_print(f"  {DIM}The letter runs to several pages.{RESET}")
        await slow_print(f"  {DIM}You will not send it. Or you will. It does not matter.{RESET}")
    elif choice == 2:
        state["ennui"] += 15
        state["soul"] -= 5
        state["decisions"].append("stood_on_bridge")
        await slow_print("\n  The bridge over the river. Three in the morning.")
        await slow_print("  The water is black and fast and utterly indifferent.")
        await slow_print("  You stand where Fedka stood, weeks ago,")
        await slow_print("  offering to solve your problems with fire.")
        await slow_print("  The railing is cold under your hands.")
        await slow_print("  You think about Kirillov's logic —")
        await slow_print("  the ultimate act of freedom, the proof of self-will.")
        await slow_print("  But you are not Kirillov. You have no logic.")
        await slow_print("  You have only this: the water, the cold, the dark.")
        await slow_print(f"  {DIM}You stand there for an hour. Then two.{RESET}")
        await slow_print(f"  {DIM}Then you walk home. Not out of hope.{RESET}")
        await slow_print(f"  {DIM}Out of the same inertia that keeps the earth spinning.{RESET}")
    elif choice == 3:
        state["ennui"] += 20
        state["soul"] -= 10
        state["decisions"].append("sat_in_darkness")
        await slow_print("\n  You sit in the dark of your rooms.")
        await slow_print("  The house creaks around you. Skvoreshniki is old.")
        await slow_print("  Somewhere your mother is awake, worrying.")
        await slow_print("  Somewhere Shatov is at the bottom of a pond.")
        await slow_print("  Somewhere Kirillov is cooling on the floor.")
        await slow_print("  Somewhere Marya Timofeyevna's clean white dress")
        await slow_print("  is stained with blood that is not her own.")
        await slow_print("  The darkness presses down.")
        await slow_print("  You let it.")
        await slow_print(f"  {DIM}You have tried your strength everywhere.{RESET}")
        await slow_print(f"  {DIM}As long as you were experimenting, it seemed infinite.{RESET}")
        await slow_print(f"  {DIM}But to what to apply your strength —{RESET}")
        await slow_print(f"  {DIM}that you have never seen, and do not see now.{RESET}")
    elif choice == 4:
        state["ennui"] += 10
        state["decisions"].append("prepared_to_leave")
        await slow_print("\n  You pack a small bag. Almost nothing.")
        await slow_print("  You have bought a house in the canton of Uri.")
        await slow_print("  A narrow valley. Mountains that restrict thought.")
        await slow_print("  You chose it because there was nothing there.")
        await slow_print("  Not beauty. Not ugliness. Not ideas. Not people.")
        await slow_print("  Just mountains and silence and a door you can close.")
        await slow_print(f"  {DIM}I don't like vice and I didn't want it, you think.{RESET}")
        await slow_print(f"  {DIM}My desires are too weak to guide me.{RESET}")
        await slow_print(f"  {DIM}On a log one may cross a river but not on a chip.{RESET}")

    clamp_stats()
    show_status()
    await press_enter()


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


async def chapter_secret_tikhon():
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
    await slow_print(f"  {DIM}This chapter was suppressed by the editor Katkov in 1872.{RESET}")
    await slow_print(f"  {DIM}Dostoevsky never restored it in his lifetime.{RESET}")
    await slow_print(f"  {DIM}It is the missing center of the novel —{RESET}")
    await slow_print(f"  {DIM}the confession that explains everything.{RESET}")
    print()
    await slow_print(f"  {DIM}Your choices have unlocked it.{RESET}")
    await press_enter()

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

    await slow_print(f"  {BOLD}AT TIKHON'S — У ТИХОНА{RESET}")
    await slow_print(f"  {DIM}(The Suppressed Chapter){RESET}")
    print()
    await slow_print("  Before dawn. You leave Skvoreshniki on foot.")
    await slow_print("  Not toward the town. The other direction —")
    await slow_print("  toward the Bogorodsky monastery, three versts east,")
    await slow_print("  where the retired Bishop Tikhon lives in a cell.")
    print()
    await slow_print("  You have been told about Tikhon. A holy man,")
    await slow_print("  some say; a lunatic, others say. He was retired")
    await slow_print("  from his episcopal see due to illness and a certain")
    await slow_print("  eccentricity of behavior. He receives visitors.")
    await slow_print("  He listens. He has a stammer that appears and")
    await slow_print("  disappears depending on what is said to him.")
    print()
    await slow_print("  You carry in your breast pocket several sheets of paper,")
    await slow_print("  closely written, folded and refolded many times.")
    await slow_print("  Your written confession. You have been carrying it")
    await slow_print("  for months. Perhaps years.")
    print()
    await slow_print("  The monastery is quiet. An old monk leads you")
    await slow_print("  through a corridor that smells of incense and cold stone.")
    await slow_print("  Tikhon's door is open.")
    await press_enter()

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

    await slow_print("  He is not what you expected.")
    await slow_print("  Tall, lean, about fifty-five. An illness in his legs")
    await slow_print("  gives him an uncertain gait. Long, narrow face.")
    await slow_print("  His eyes are what strike you — clear, almost merry,")
    await slow_print("  the eyes of a man who has looked at the worst of himself")
    await slow_print("  and has not been destroyed by it.")
    print()
    await slow_print('  "Sit down," Tikhon says. His voice is gentle.')
    await slow_print("  On his table: a novel, a volume of Hegel,")
    await slow_print("  and a breviary. An unusual combination.")
    await slow_print('  "I have heard you are ill," you say.')
    await slow_print('  "Ill enough," he replies, smiling.')
    print()
    await slow_print("  You do not sit. You pace.")
    await slow_print("  Tikhon watches with the patience of a man who has")
    await slow_print("  seen a thousand confessions begin exactly like this —")
    await slow_print("  with pacing, with anger, with the inability to begin.")
    print()
    await slow_print("  Finally, you take out the pages.")
    await slow_print("  You put them on the table without a word.")
    await slow_print("  Tikhon looks at you, then at the pages.")
    await slow_print("  He picks them up and begins to read.")
    print()

    await slow_print(f"  {BOLD}The confession contains:{RESET}")
    await slow_print(f"  {DIM}  In Petersburg, in a furnished room on Gorokhovaya Street,{RESET}")
    await slow_print(f"  {DIM}  you lived next to a girl named Matryosha.{RESET}")
    await slow_print(f"  {DIM}  She was eleven or twelve years old.{RESET}")
    await slow_print(f"  {DIM}  Her mother beat her. She was thin and afraid.{RESET}")
    print()
    await slow_print(f"  {DIM}  You committed an act of unspeakable evil against her.{RESET}")
    await slow_print(f"  {DIM}  Not from desire. Not from compulsion.{RESET}")
    await slow_print(f"  {DIM}  From the wish to test whether you could feel anything at all.{RESET}")
    print()
    await slow_print(f"  {DIM}  Afterwards, she told you that she had killed God.{RESET}")
    await slow_print(f"  {DIM}  You sat and waited. You heard a buzzing sound.{RESET}")
    await slow_print(f"  {DIM}  A fly in the window. You examined the red spider{RESET}")
    await slow_print(f"  {DIM}  on a geranium leaf and fell into a sort of reverie.{RESET}")
    print()
    await slow_print(f"  {DIM}  When you went back, you knew what you would find.{RESET}")
    await slow_print(f"  {DIM}  You saw her tiny fist shaking at you from behind the door.{RESET}")
    await slow_print(f"  {DIM}  You walked away. You did not stop it.{RESET}")
    print()
    await slow_print(f"  {DIM}  She hanged herself.{RESET}")
    print()
    await slow_print(f"  {DIM}  You have never forgotten the red spider on the geranium.{RESET}")
    await slow_print(f"  {DIM}  Or the fly. Or the tiny fist.{RESET}")
    await slow_print(f"  {DIM}  You dream of them every night.{RESET}")
    await slow_print(f"  {DIM}  This is why you feel nothing:{RESET}")
    await slow_print(f"  {DIM}  you are already in hell.{RESET}")
    await press_enter()

    clear_screen()
    print(f"""{YELLOW}
    ╔═══════════════════════════════════════════════════════╗
    ║                                                       ║
    ║     {WHITE}Tikhon reads. His face changes.{YELLOW}                   ║
    ║                                                       ║
    ╚═══════════════════════════════════════════════════════╝{RESET}
""")

    await slow_print("  Tikhon reads slowly. His hands do not tremble.")
    await slow_print("  But his face — you watch his face —")
    await slow_print("  it passes through something.")
    await slow_print("  Not disgust. Not horror.")
    await slow_print("  Something worse: understanding.")
    print()
    await slow_print("  When he finishes, he puts the pages down carefully.")
    await slow_print("  A long silence. The candle flickers.")
    await slow_print("  Somewhere in the monastery, a bell rings for matins.")
    print()
    await slow_print('  "Can you forgive me?" you ask.')
    await slow_print("  You are surprised to hear your own voice.")
    await slow_print("  It sounds like someone else's.")
    print()
    await slow_print("  Tikhon looks at you with those terrible, clear eyes.")
    await slow_print('  "God can forgive all things," he says.')
    await slow_print("  Then his stammer appears:")
    await slow_print('  "B-but... the question is whether you can b-bear')
    await slow_print('   your own forgiveness."')
    print()
    await slow_print("  He pauses. When he speaks again, the stammer is gone.")
    await slow_print("  His voice is quiet and precise:")
    print()
    await slow_print(f'  {BOLD}"I see pride in this document."{RESET}')
    print()
    await slow_print("  You stiffen.")
    print()
    await slow_print('  "You confess not from repentance," Tikhon continues,')
    await slow_print('  "but from the need for a new sensation.')
    await slow_print('   You wish to publish this confession. You told me so.')
    await slow_print('   You want to provoke them — society — into hating you.')
    await slow_print('   You want their blows. Their disgust.')
    await slow_print('   Because even their hatred would be something to feel."')
    print()

    choice = await get_choice([
        '"You are wrong, old man."',
        "Say nothing. Let the words land.",
        '"Then what would you have me do?"',
        '"Perhaps you are right. Perhaps even this is vanity."',
    ])

    if choice == 1:
        state["ennui"] += 5
        state["soul"] += 5
        state["decisions"].append("denied_tikhons_truth")
        await slow_print('\n  "Am I?" Tikhon says gently.')
        await slow_print('  "Then tell me: in this confession,')
        await slow_print('   you describe the child\'s suffering in great detail.')
        await slow_print("   But your own? Almost nothing.")
        await slow_print('   The style is cold. Almost literary.')
        await slow_print('   You have made your sin into a document."')
        await slow_print("  He pauses.")
        await slow_print('  "There are even grammatical corrections in the margins."')
        await slow_print(f"  {DIM}You look down. He is right. You corrected the prose.{RESET}")
        await slow_print(f"  {DIM}Even your worst moment has been edited for style.{RESET}")
    elif choice == 2:
        state["soul"] += 15
        state["ennui"] -= 10
        state["decisions"].append("accepted_tikhons_truth")
        await slow_print("\n  You say nothing. The silence fills the cell.")
        await slow_print("  Tikhon watches you.")
        await slow_print("  Something is happening in your chest —")
        await slow_print("  not an emotion, exactly, but the space")
        await slow_print("  where an emotion might be, if the walls came down.")
        await slow_print("  It is the closest thing to feeling you have experienced")
        await slow_print("  since Matryosha. Since the red spider.")
        await slow_print(f"  {DIM}Tikhon sees it. His eyes are bright with tears.{RESET}")
        await slow_print(f"  {DIM}Not pity. Recognition.{RESET}")
    elif choice == 3:
        state["soul"] += 20
        state["ennui"] -= 15
        state["decisions"].append("asked_tikhon_for_way")
        await slow_print("\n  Tikhon leans forward. His whole face changes.")
        await slow_print('  "There is a way. Not publication.')
        await slow_print("   Not public degradation.")
        await slow_print('   That is only pride wearing the mask of humility."')
        await slow_print("  He speaks of an elder — a staretz —")
        await slow_print("  living in a remote monastery.")
        await slow_print('  "Submit yourself to his guidance.')
        await slow_print("   Five years. Perhaps seven.")
        await slow_print("   Not punishment — discipline.")
        await slow_print('   The slow, patient work of rebuilding a soul."')
        await slow_print("  He pauses.")
        await slow_print('  "It will be the hardest thing you have ever done.')
        await slow_print('   Harder than any duel. Harder than any confession.')
        await slow_print('   Because it will be boring, and quiet,')
        await slow_print('   and you will receive no admiration for it."')
        await slow_print(f"  {DIM}Boring. Quiet. No admiration.{RESET}")
        await slow_print(f"  {DIM}The perfect antidote to everything you are.{RESET}")
    elif choice == 4:
        state["soul"] += 10
        state["ennui"] -= 5
        state["decisions"].append("admitted_vanity")
        await slow_print("\n  Tikhon's face softens with something close to wonder.")
        await slow_print('  "You see it yourself. That is... that is more')
        await slow_print('   than I expected. More than most can manage."')
        await slow_print("  His stammer returns:")
        await slow_print('  "The f-fact that you can see the pride in your')
        await slow_print("   own confession means there is something")
        await slow_print('   b-beneath the pride. Something alive."')
        await slow_print(f"  {DIM}Something alive. Underneath all of it.{RESET}")
        await slow_print(f"  {DIM}You are not sure you believe him.{RESET}")
        await slow_print(f"  {DIM}But for the first time in years,{RESET}")
        await slow_print(f"  {DIM}you want to.{RESET}")

    print()
    await slow_print("  Then Tikhon says one more thing.")
    await slow_print("  The thing that breaks you:")
    print()
    await slow_print(f'  {BOLD}"I am most afraid for you," he says,')
    await slow_print(f'  "because I am not sure you can bear their laughter.')
    await slow_print(f'   You can bear their hatred. Their horror. Their pity.')
    await slow_print(f'   But if they laugh — if even one person laughs —')
    await slow_print(f'   you will commit a new crime to escape the shame.')
    await slow_print(f'   A crime worse than what is written here."{RESET}')
    print()
    await slow_print("  The words hit you like a blow.")
    await slow_print("  Not because they are cruel.")
    await slow_print("  Because they are true.")
    await slow_print("  Because this old man in a bare cell has seen through")
    await slow_print("  every mask, every performance, every layer of your")
    await slow_print("  carefully constructed emptiness, and has found —")
    await slow_print("  not nothing — but a terrified child hiding from laughter.")
    print()
    await slow_print("  You stand. Your chair scrapes the stone floor.")
    await slow_print("  Your hands are shaking.")
    print()
    await slow_print('  "I will come back," you say.')
    await slow_print("  Tikhon nods. He does not believe you.")
    await slow_print("  Neither do you.")
    print()
    await slow_print(f"  {DIM}You walk out into the dawn. The monastery bell{RESET}")
    await slow_print(f"  {DIM}is still ringing. Smoke rises from the kitchen.{RESET}")
    await slow_print(f"  {DIM}A monk is feeding chickens in the yard.{RESET}")
    await slow_print(f"  {DIM}The world is ordinary. It is unbearable.{RESET}")
    print()
    await slow_print(f"  {DIM}Dostoevsky's editor cut this chapter from the novel.{RESET}")
    await slow_print(f"  {DIM}Perhaps because it revealed too much.{RESET}")
    await slow_print(f"  {DIM}Perhaps because even fiction has limits{RESET}")
    await slow_print(f"  {DIM}on how much truth it can bear.{RESET}")

    state["confessed_to_tikhon"] = True
    state["decisions"].append("went_to_tikhon")
    state["soul"] += 10
    state["ennui"] -= 10

    clamp_stats()
    show_status()
    await press_enter()


# ═══════════════════════════════════════════════════════════════
#  THE AFTERMATH
# ═══════════════════════════════════════════════════════════════

async def chapter_new_aftermath():
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

    await slow_print(f"  {BOLD}CHAPTER XII: THE AFTERMATH{RESET}")
    print()
    await slow_print("  The town wakes up.")
    await slow_print("  Not all at once — slowly, painfully,")
    await slow_print("  the way a man wakes from a dream of falling")
    await slow_print("  and discovers that the floor is real.")
    print()
    await slow_print("  Lyamshin breaks first. He crawls to the police station")
    await slow_print("  on his hands and knees at two in the morning,")
    await slow_print("  sobbing so hard they cannot understand him.")
    await slow_print("  When they finally piece together his confession,")
    await slow_print("  the officer on duty crosses himself.")
    await slow_print("  He has been in the service for twenty-three years.")
    await slow_print("  He has never heard anything like this.")
    print()
    await slow_print("  Then: the pond at Skvoreshniki park.")
    await slow_print("  Divers go in at dawn. They find Shatov's body")
    await slow_print("  weighted with stones, the cap left behind on the shore.")
    await slow_print("  The pistol is still in his coat — Pyotr's mistake,")
    await slow_print("  one of many, committed in haste and darkness.")
    print()
    await slow_print("  The arrests come quickly after that.")
    await slow_print("  Virginsky weeps when they take him. He says:")
    await slow_print('  "It was not right! I said so at the time!')
    await slow_print('   It was not right at all!"')
    await slow_print("  Liputin is found packing his bags.")
    await slow_print("  Tolkatchenko makes it as far as the train station.")
    await slow_print("  Erkel says nothing. His face is blank —")
    await slow_print("  the face of a young man who followed orders")
    await slow_print("  because the orders were all he had.")
    print()
    await slow_print("  And Pyotr Stepanovich?")
    await slow_print("  Gone. Escaped by the evening train,")
    await slow_print("  with forged papers and a third-class ticket.")
    await slow_print("  He will resurface in Switzerland,")
    await slow_print("  organizing the next revolution,")
    await slow_print("  the next set of useful fools.")
    await slow_print("  Men like Pyotr Verkhovensky are never caught.")
    await slow_print("  They are too light. They float.")
    print()
    await slow_print("  Liza is dead. Beaten by a crowd at the fire site.")
    await slow_print("  Mavriky Nikolaevich carried her body home.")
    await slow_print("  He did not speak for three days afterward.")
    print()
    await slow_print("  The Governor resigns. Yulia Mihailovna has a nervous collapse.")
    await slow_print("  The province has been shaken to its foundations,")
    await slow_print("  and the foundations were never very deep.")
    print()
    await slow_print("  And then your mother comes to see you.")
    await press_enter()

    clear_screen()
    print(f"""{CYAN}
    ╔═══════════════════════════════════════════════════════╗
    ║                                                       ║
    ║     {WHITE}Varvara Petrovna Stavrogina{CYAN}                        ║
    ║     {DIM}stands in the doorway of your rooms.{CYAN}                ║
    ║                                                       ║
    ╚═══════════════════════════════════════════════════════╝{RESET}
""")

    await slow_print("  Varvara Petrovna stands in the doorway of your rooms.")
    await slow_print("  She is dressed in black. She is always dressed in black,")
    await slow_print("  but now it looks different. Now it looks earned.")
    print()
    await slow_print("  She has heard everything. The murders. The conspiracy.")
    await slow_print("  Your involvement — or your proximity to involvement,")
    await slow_print("  which in a provincial town amounts to the same thing.")
    await slow_print("  Stepan Trofimovich has fled. Her oldest friend,")
    await slow_print("  wandering the high road with an umbrella,")
    await slow_print("  and she does not yet know where.")
    print()
    await slow_print("  She looks at you. Her eyes are dry.")
    await slow_print("  She has spent a lifetime defending you —")
    await slow_print("  explaining, justifying, constructing elaborate fictions")
    await slow_print("  around the void at the center of her son.")
    await slow_print("  The nose-pulling. The ear-biting. The marriage.")
    await slow_print("  She explained them all. She cannot explain this.")
    print()
    await slow_print('  "They are saying things about you," she says.')
    await slow_print("  Her voice is level. Too level.")
    await slow_print('  "Terrible things. About the fire.')
    await slow_print('   About the Lebyadkin woman. About Lizaveta Nikolaevna."')
    print()
    await slow_print("  She waits. She is giving you one last chance")
    await slow_print("  to explain, to deny, to perform the role of a son")
    await slow_print("  who has done nothing wrong.")
    print()

    await slow_print("  How do you face your mother?")

    choice = await get_choice([
        '"I did not kill them, Mother. That much is true."',
        "Say nothing. Let her draw her own conclusions.",
        '"I am leaving. There is nothing more to discuss."',
        '"Everything they say is true. And worse besides."',
        '"I did it all. I planned everything. Send for the police."',
    ])

    if choice == 5:
        state["decisions"].append("false_confession")
        await game_over([
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
        await slow_print('\n  "I did not kill them," you say.')
        await slow_print("  Varvara Petrovna searches your face.")
        await slow_print("  She has always been able to read others —")
        await slow_print("  but never you. You are the one text")
        await slow_print("  that defeats her intelligence.")
        await slow_print('  "But did you cause it?" she whispers.')
        await slow_print("  You do not answer. The silence is enough.")
        await slow_print("  She nods once, very slowly,")
        await slow_print("  the way a person nods when the last door closes.")
        await slow_print(f"  {DIM}She walks out without touching you.{RESET}")
        await slow_print(f"  {DIM}She will never touch you again.{RESET}")
    elif choice == 2:
        state["ennui"] += 15
        state["decisions"].append("silent_before_mother")
        await slow_print("\n  You say nothing. She stands in the doorway")
        await slow_print("  for a very long time, waiting.")
        await slow_print("  The clock on the mantel ticks.")
        await slow_print("  Your silence fills the room like water filling a well.")
        await slow_print("  Finally she turns to go.")
        await slow_print("  At the door she pauses:")
        await slow_print(f'  {DIM}"I have no son."{RESET}')
        await slow_print("  The words fall into the room like stones.")
        await slow_print("  She closes the door behind her very gently —")
        await slow_print("  not a slam. Worse than a slam.")
        await slow_print(f"  {DIM}The gentleness of it is unbearable.{RESET}")
    elif choice == 3:
        state["ennui"] += 10
        state["decisions"].append("told_mother_leaving")
        await slow_print('\n  "I am leaving," you say. "I have a house in Switzerland.')
        await slow_print('   In the canton of Uri. There is nothing left here."')
        await slow_print("  Varvara Petrovna's composure cracks — just for a moment,")
        await slow_print("  just a flash of something raw underneath")
        await slow_print("  the armor of twenty years of propriety.")
        await slow_print('  "Nicolas—"')
        await slow_print('  "Do not," you say. Just that. Do not.')
        await slow_print("  She swallows whatever she was going to say.")
        await slow_print("  She straightens her back. She nods.")
        await slow_print(f"  {DIM}The last conversation you will ever have with your mother{RESET}")
        await slow_print(f"  {DIM}ends with a prohibition. Do not feel. Do not weep.{RESET}")
        await slow_print(f"  {DIM}Do not be human in front of me.{RESET}")
    elif choice == 4:
        state["soul"] -= 10
        state["notoriety"] += 10
        state["decisions"].append("confessed_to_mother")
        await slow_print('\n  "Everything they say is true," you say,')
        await slow_print("  your voice perfectly level, perfectly empty.")
        await slow_print('  "And worse besides."')
        await slow_print("  Varvara Petrovna's face does not change.")
        await slow_print("  Perhaps she always knew. Perhaps mothers always know.")
        await slow_print("  Perhaps the elaborate fictions she built")
        await slow_print("  around your behavior were never for others —")
        await slow_print("  they were for herself. Walls against a truth")
        await slow_print("  she could not afford to see.")
        await slow_print("  She crosses herself. The gesture is automatic.")
        await slow_print("  She walks out.")
        await slow_print(f"  {DIM}You hear her footsteps on the stairs.{RESET}")
        await slow_print(f"  {DIM}Slow. Measured. The footsteps of a woman{RESET}")
        await slow_print(f"  {DIM}who has just buried her son while he is still alive.{RESET}")

    clamp_stats()
    show_status()
    await press_enter()


# ═══════════════════════════════════════════════════════════════
#  STEPAN TROFIMOVICH'S LAST WANDERING
# ═══════════════════════════════════════════════════════════════

async def chapter_10_stepan_wandering():
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

    await slow_print(f"  {BOLD}CHAPTER XIII: STEPAN TROFIMOVICH'S LAST WANDERING{RESET}")
    print()
    await slow_print("  While the town tears itself apart, old Stepan Trofimovich")
    await slow_print("  does the most extraordinary thing of his life:")
    await slow_print("  he leaves.")
    print()
    await slow_print("  Not in the way young men leave — with a plan,")
    await slow_print("  a destination, a reason. He leaves the way a leaf")
    await slow_print("  leaves a tree: because it is time, because the wind came,")
    await slow_print("  because staying had become the only impossibility.")
    print()
    await slow_print("  His travelling costume is magnificent and absurd.")
    await slow_print("  He wears his best embroidered waistcoat,")
    await slow_print("  the one Varvara Petrovna bought him in Paris.")
    await slow_print("  Over this: a broad-brimmed hat. An umbrella.")
    await slow_print("  A walking stick he has never used for walking.")
    await slow_print("  His bag contains: two shirts, a French novel,")
    await slow_print("  a lorgnette, and fifty roubles in small bills.")
    await slow_print("  He does not know where he is going.")
    await slow_print("  This is, perhaps, the point.")
    print()
    await slow_print("  Twenty years of living on Varvara Petrovna's charity.")
    await slow_print("  Twenty years of playing the exiled intellectual,")
    await slow_print("  the persecuted liberal, the man of the forties")
    await slow_print("  who once wrote a poem that may or may not")
    await slow_print("  have been investigated by the authorities.")
    await slow_print("  Twenty years of performing genius for a woman")
    await slow_print("  who kept him like a hothouse flower.")
    await slow_print("  And now — at last — he walks out onto the high road.")
    print()
    await slow_print("  The road is black with wheel-ruts, planted with willows.")
    await slow_print("  Rain drizzles. He opens his umbrella.")
    await slow_print("  His shoes — city shoes, thin-soled, absurd —")
    await slow_print("  are ruined within the first verst.")
    await slow_print("  He does not notice. He is walking.")
    await slow_print("  For the first time in twenty years,")
    await slow_print("  he is moving under his own power,")
    await slow_print("  toward no one's expectation.")
    print()
    await slow_print("  A peasant with a cart passes him on the road.")
    await slow_print('  "Where are you going, master?"')
    await slow_print('  "I... I am going... somewhere," Stepan says.')
    await slow_print('  "To Spasov? That is thirty versts."')
    await slow_print('  "Thirty versts! Very well. I shall walk thirty versts."')
    await slow_print("  The peasant stares at this old man in a waistcoat")
    await slow_print("  and embroidered tie, with a walking stick and an umbrella,")
    await slow_print("  mud to his ankles, heading nowhere at four miles an hour.")
    await slow_print("  He crosses himself and drives on.")
    print()
    await slow_print("  After five versts, Stepan Trofimovich collapses")
    await slow_print("  under a tree. His feet are bleeding.")
    await slow_print("  He has blisters on both heels.")
    await slow_print("  He sits in the rain and weeps —")
    await slow_print("  not from pain, but from a joy he cannot name.")
    await slow_print(f'  {DIM}"I am free," he says to no one. "I am free at last."{RESET}')
    await press_enter()

    clear_screen()
    print(f"""{GREEN}
    ╔═══════════════════════════════════════════════════════╗
    ║                                                       ║
    ║     {WHITE}A woman on the road. A Bible seller.{GREEN}              ║
    ║     {WHITE}Sofya Matveyevna.{GREEN}                                  ║
    ║                                                       ║
    ╚═══════════════════════════════════════════════════════╝{RESET}
""")

    await slow_print("  On the road, by the town of Khatovo,")
    await slow_print("  he meets a woman selling Bibles and Gospels.")
    await slow_print("  Sofya Matveyevna — young, plain, gentle,")
    await slow_print("  with the patient eyes of someone who has learned")
    await slow_print("  to expect nothing from the world.")
    print()
    await slow_print("  Stepan Trofimovich latches onto her immediately.")
    await slow_print('  "My dear! My kind one! Will you read to me?')
    await slow_print("   I have been wanting someone to read to me")
    await slow_print('   for twenty years!"')
    await slow_print("  She is bewildered but kind. She reads.")
    print()
    await slow_print("  He talks to her as he has never talked to anyone.")
    await slow_print("  Not performing. Not quoting Schiller.")
    await slow_print("  Just talking — about his life, his son,")
    await slow_print("  about Varvara Petrovna, about beauty.")
    await slow_print('  "Je vous aimais," he says suddenly, in French.')
    await slow_print('  "I loved her — Varvara Petrovna — all my life.')
    await slow_print('   Twenty years! And I never told her."')
    await slow_print("  His eyes are bright with tears.")
    await slow_print('  "Twenty years of living beside her')
    await slow_print("   and I was too proud, too absurd,")
    await slow_print('   too much the great man to simply say: I love you."')
    print()
    await slow_print("  Sofya Matveyevna does not understand French.")
    await slow_print("  But she understands weeping. She holds his hand.")
    print()
    await slow_print("  He asks her to read from Luke. Chapter eight.")
    await slow_print("  The passage about the Gadarene swine:")
    await slow_print("  the demons that entered the herd and drove them")
    await slow_print("  headlong over the cliff into the sea.")
    print()
    await slow_print("  She reads. His face changes.")
    await slow_print("  Something vast is assembling itself behind his eyes.")
    print()
    await slow_print('  "These demons," he whispers,')
    await slow_print("  seizing Sofya Matveyevna's hand,")
    await slow_print('  "that is us. All of us.')
    await slow_print("   Pyotr, and I, and perhaps Stavrogin,")
    await slow_print("   and all the others — Shatov, Kirillov,")
    await slow_print("   poor Virginsky, all of them.")
    await slow_print("   We are the sick man's demons,")
    await slow_print("   entering the swine!")
    await slow_print("   And the swine will rush down the cliff")
    await slow_print('   and be drowned!"')
    print()
    await slow_print("  He is weeping openly now. Sofya Matveyevna is frightened.")
    await slow_print("  But he grips her hand tighter:")
    print()
    await slow_print(f'  {BOLD}"But the sick man will be healed!{RESET}')
    await slow_print(f'  {BOLD} And he will sit at the feet of Jesus,')
    await slow_print(f'   and all will look upon him with astonishment!"{RESET}')
    print()
    await slow_print("  It is the epigraph of the novel.")
    await slow_print("  It is the meaning of the novel.")
    await slow_print("  And it has taken Stepan Trofimovich his whole ridiculous life")
    await slow_print("  to arrive at it — on a muddy road, in ruined shoes,")
    await slow_print("  holding the hand of a stranger.")
    print()

    await slow_print("  You encounter Stepan on the road. What do you do?")

    choice = await get_choice([
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
        await slow_print("\n  You sit beside him on the muddy road.")
        await slow_print("  Sofya Matveyevna reads, and you listen.")
        await slow_print("  The words wash over you — demons, swine, healing.")
        await slow_print("  Stepan Trofimovich looks at you with shining eyes.")
        await slow_print('  "Nicolas... you came. You are here."')
        await slow_print('  "I am here, Stepan Trofimovich."')
        await slow_print('  "Do you hear it? The sick man will be healed.')
        await slow_print('   Russia will be healed. Even you, perhaps."')
        await slow_print("  You do not believe him. But sitting beside him")
        await slow_print("  in the mud and the rain, listening to Luke,")
        await slow_print("  you feel something you had forgotten existed:")
        await slow_print("  the warmth of another person's faith.")
        await slow_print(f"  {DIM}It is not yours. But you can feel it from here.{RESET}")
    elif choice == 2:
        state["soul"] += 10
        state["stepan_bond"] += 10
        state["decisions"].append("gave_stepan_coat")
        await slow_print("\n  You take off your coat and put it around his shoulders.")
        await slow_print("  He looks up at you, startled.")
        await slow_print('  "Nicolas! You will catch cold!"')
        await slow_print('  "You are an old man on a road in the rain.')
        await slow_print('   Take the coat."')
        await slow_print("  He begins to weep again — but differently now.")
        await slow_print("  Not the theatrical weeping of twenty years")
        await slow_print("  of provincial salon life. Real tears.")
        await slow_print("  The tears of a man being cared for")
        await slow_print("  by someone he thought had forgotten how.")
        await slow_print(f"  {DIM}It is the smallest gesture. A coat.{RESET}")
        await slow_print(f"  {DIM}And yet it is the largest thing you have done all year.{RESET}")
    elif choice == 3:
        state["stepan_bond"] += 5
        state["ennui"] += 5
        state["decisions"].append("told_stepan_about_varvara")
        await slow_print('\n  "She is looking for you," you say.')
        await slow_print("  Stepan Trofimovich's face changes —")
        await slow_print("  fear, hope, and love all fighting for dominance.")
        await slow_print('  "Varvara Petrovna? She is... looking?"')
        await slow_print('  "She has sent people out on every road."')
        await slow_print("  He sits very still. Then a kind of peace settles over him.")
        await slow_print('  "Then she will find me," he says softly.')
        await slow_print('  "She always finds me."')
        await slow_print(f"  {DIM}It is the most hopeful thing anyone has said in this story.{RESET}")
        await slow_print(f"  {DIM}It is also the most accurate.{RESET}")
    elif choice == 4:
        state["ennui"] += 10
        state["decisions"].append("passed_stepan_by")
        await slow_print("\n  You walk past. He does not call out.")
        await slow_print("  Perhaps he does not see you.")
        await slow_print("  Perhaps he has already left this world")
        await slow_print("  for whatever world he is traveling toward.")
        await slow_print("  His umbrella bobs in the rain.")
        await slow_print("  His voice carries behind you,")
        await slow_print("  reading Luke to a stranger.")
        await slow_print(f"  {DIM}You do not look back.{RESET}")
        await slow_print(f"  {DIM}You are very good at not looking back.{RESET}")
        await slow_print(f"  {DIM}It is perhaps your only genuine skill.{RESET}")

    print()
    await slow_print("  That evening, Stepan Trofimovich collapses.")
    await slow_print("  Varvara Petrovna arrives the next morning.")
    await slow_print("  She finds him in a peasant cottage,")
    await slow_print("  burning with fever, holding Sofya Matveyevna's hand.")
    print()
    await slow_print('  "Darling," he says. In twenty years')
    await slow_print("  he has never called her that.")
    await slow_print("  She sits by his bed. She takes his hand.")
    await slow_print("  He confesses to a priest. He weeps.")
    await slow_print("  He tells Varvara Petrovna he loved her.")
    await slow_print("  She knows. She has always known.")
    print()
    await slow_print("  He dies the next morning, having confessed,")
    await slow_print("  having wept, having loved, having been ridiculous")
    await slow_print("  and sincere and utterly, finally, himself.")
    print()
    await slow_print(f"  {DIM}He is the only character in this story who dies well.{RESET}")
    await slow_print(f"  {DIM}The only one who finds, at the end, something real.{RESET}")
    await slow_print(f"  {DIM}Not because he was wise — he was absurd.{RESET}")
    await slow_print(f"  {DIM}Not because he was brave — he was terrified.{RESET}")
    await slow_print(f"  {DIM}Because he walked out the door.{RESET}")

    clamp_stats()
    show_status()
    await press_enter()


# ═══════════════════════════════════════════════════════════════
#  THE LAST NIGHT — FINAL BOSS
# ═══════════════════════════════════════════════════════════════

async def chapter_final_boss():
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

    await slow_print(f"  {BOLD}THE LAST NIGHT{RESET}")
    print()
    await slow_print("  It is your last night alive. You know this.")
    await slow_print("  Not as a premonition — as a decision already made,")
    await slow_print("  calmly, the way one decides to take a train.")
    print()
    await slow_print("  You sit at your desk at Skvoreshniki.")
    await slow_print("  The letter to Dasha is half-written.")
    await slow_print("  The candle burns. The house is silent.")
    print()
    await slow_print("  And then they come.")
    await slow_print("  Not ghosts. Not apparitions.")
    await slow_print("  Memories so vivid they have voices.")
    await slow_print("  The people whose lives you shaped — or shattered —")
    await slow_print("  each making a claim on the emptiness at your center.")
    print()
    await slow_print(f"  {DIM}Five confrontations stand between you and the loft.{RESET}")
    await slow_print(f"  {DIM}What you built — or failed to build — determines{RESET}")
    await slow_print(f"  {DIM}whether you can answer them.{RESET}")
    print()

    confrontations = 0

    await press_enter()

    # ─── ROUND 1: SHATOV ─────────────────────────────────────

    clear_screen()
    print(f"""{CYAN}
    ╔═════════════════════════════════════╗
    ║  {WHITE}I — SHATOV — "The Question"{CYAN}        ║
    ╚═════════════════════════════════════╝{RESET}
""")

    await slow_print("  He appears as he was in the garret.")
    await slow_print("  Before the park. Before the pond.")
    await slow_print("  Before the five of them held him down in the dark.")
    print()
    await slow_print("  He is standing by your desk, shaking slightly,")
    await slow_print("  the way he always shook — from feeling too much,")
    await slow_print("  never too little.")
    print()
    await slow_print(f'  {BOLD}"Do you believe in God, Stavrogin?"{RESET}')
    print()
    await slow_print("  But this time it is not a philosophical question.")
    await slow_print("  This time it is asked by a man who was murdered")
    await slow_print("  on the night his wife gave birth to a child")
    await slow_print("  he believed was yours.")
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
            c = (await ainput(f"  {GREEN}Your answer (1-3): {RESET}")).strip()
            if c == "1" and shatov_locked:
                state["soul"] += 15
                confrontations += 1
                state["decisions"].append("answered_shatov")
                print()
                await slow_print("  Something shifts in his face.")
                await slow_print("  The shaking stops.")
                await slow_print('  "Then it was not all for nothing," he says.')
                await slow_print("  His voice is steady. His eyes are clear.")
                await slow_print("  He was always the bravest of them all —")
                await slow_print("  the one who believed without proof.")
                await slow_print("  For one moment, you were worthy of his question.")
                break
            elif c == "1" and not shatov_locked:
                print(f"  {DIM}You cannot choose this. The bond was never built.{RESET}")
                continue
            elif c == "2":
                state["ennui"] += 10
                state["soul"] -= 5
                state["decisions"].append("denied_shatov_again")
                print()
                await slow_print("  Honest, at least. The truth you always told.")
                await slow_print('  He nods slowly. "I know," he says.')
                await slow_print("  But knowing does not help him.")
                await slow_print("  He turns away. You hear his footsteps")
                await slow_print("  on stairs that no longer exist.")
                break
            elif c == "3":
                state["ennui"] += 15
                state["decisions"].append("silent_before_shatov")
                print()
                await slow_print("  You reach for something to say and find only emptiness.")
                await slow_print("  The silence stretches. He waits.")
                await slow_print("  He has always waited for you — for the answer,")
                await slow_print("  for the sign, for the faith you could not give.")
                await slow_print("  He waited until the night by the pond.")
                await slow_print("  He is still waiting.")
                break
        except (ValueError, EOFError):
            continue

    clamp_stats()
    print()
    await press_enter()

    # ─── ROUND 2: KIRILLOV ───────────────────────────────────

    clear_screen()
    print(f"""{CYAN}
    ╔═════════════════════════════════════╗
    ║  {WHITE}II — KIRILLOV — "The Proof"{CYAN}        ║
    ╚═════════════════════════════════════╝{RESET}
""")

    await slow_print("  He appears bouncing his india-rubber ball.")
    await slow_print("  Catch, bounce, catch. The rhythm of a man")
    await slow_print("  who has resolved the problem of existence")
    await slow_print("  and found the answer is a pistol.")
    print()
    await slow_print("  He looks at you with that odd, gentle clarity —")
    await slow_print("  the face of someone who has already stepped")
    await slow_print("  beyond fear, beyond hope, into pure logic.")
    print()
    await slow_print(f'  {BOLD}"I proved my freedom. I acted."{RESET}')
    await slow_print(f'  {BOLD}"What have you done with yours, Stavrogin?"{RESET}')
    print()
    await slow_print("  His logic is still perfect. Still insane.")
    await slow_print("  But from the other side, it carries a different weight.")
    await slow_print("  He did what he said he would do.")
    await slow_print("  That is more than you have ever managed.")
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
            c = (await ainput(f"  {GREEN}Your answer (1-3): {RESET}")).strip()
            if c == "1" and kirillov_locked:
                state["soul"] += 10
                state["ennui"] -= 10
                confrontations += 1
                state["decisions"].append("honored_kirillov")
                print()
                await slow_print("  His face changes.")
                await slow_print("  The ball stops bouncing.")
                await slow_print("  For a moment you see it — the five seconds")
                await slow_print("  of eternal harmony he described that night,")
                await slow_print("  the leaf, the spider's web, the sunlight.")
                await slow_print("  He smiles. It is the rarest thing in the world:")
                await slow_print("  Kirillov's smile, unguarded, fully human.")
                await slow_print('  "Then you understand," he says.')
                break
            elif c == "1" and not kirillov_locked:
                print(f"  {DIM}You cannot choose this. The soul is too corroded.{RESET}")
                continue
            elif c == "2":
                state["ennui"] += 5
                state["decisions"].append("dismissed_kirillovs_proof")
                print()
                await slow_print("  He bounces the ball twice.")
                await slow_print("  The sound echoes in the empty room.")
                await slow_print('  "You are afraid," he says simply.')
                await slow_print("  He is right. You are afraid of everything.")
                await slow_print("  Even of the logic that would set you free.")
                break
            elif c == "3":
                state["soul"] += 5
                state["ennui"] += 5
                state["decisions"].append("questioned_kirillovs_freedom")
                print()
                await slow_print("  He considers this. The ball bounces.")
                await slow_print('  "Perhaps," he says. "But I chose my prison.')
                await slow_print('   You — you cannot even choose."')
                await slow_print("  The distinction is devastating")
                await slow_print("  precisely because it is accurate.")
                break
        except (ValueError, EOFError):
            continue

    clamp_stats()
    print()
    await press_enter()

    # ─── ROUND 3: MARYA TIMOFEYEVNA ──────────────────────────

    clear_screen()
    print(f"""{CYAN}
    ╔═════════════════════════════════════╗
    ║  {WHITE}III — MARYA — "The Impostor"{CYAN}       ║
    ╚═════════════════════════════════════╝{RESET}
""")

    await slow_print("  She appears in her clean white dress.")
    await slow_print("  The holy fool. The lame one. Your wife.")
    await slow_print("  She is dead now — burned in the fire")
    await slow_print("  with her brother, the captain, who wept over her")
    await slow_print("  even as he drank away the money you sent.")
    print()
    await slow_print("  She looks through you the way she always did —")
    await slow_print("  past the handsome face, past the officer's bearing,")
    await slow_print("  past everything the world sees, to the thing")
    await slow_print("  the world does not.")
    print()
    await slow_print(f'  {BOLD}"You are not my prince."{RESET}')
    await slow_print(f"  She knew that from the beginning.")
    await slow_print(f'  {BOLD}"But I have a question for you, impostor:"{RESET}')
    await slow_print(f'  {BOLD}"Did you ever love anyone? Even once? Even badly?"{RESET}')
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
            c = (await ainput(f"  {GREEN}Your answer (1-3): {RESET}")).strip()
            if c == "1" and marya_locked:
                state["soul"] += 15
                confrontations += 1
                state["decisions"].append("loved_marya")
                print()
                await slow_print("  Her face softens.")
                await slow_print("  Not forgiveness — she is beyond that —")
                await slow_print("  but the pity she showed in life.")
                await slow_print("  The pity of the holy fool who sees everything")
                await slow_print("  and judges nothing.")
                await slow_print('  "Poor prince," she says. Not impostor. Prince.')
                await slow_print("  It is the kindest thing anyone has ever called you.")
                await slow_print("  And you married her on a dare. And she is dead.")
                break
            elif c == "1" and not marya_locked:
                print(f"  {DIM}You cannot choose this. The bond was never built — and now she is ash.{RESET}")
                continue
            elif c == "2":
                state["soul"] += 5
                state["ennui"] += 5
                state["decisions"].append("apologized_to_marya")
                print()
                await slow_print("  She tilts her head, considering.")
                await slow_print('  "Sorry," she repeats, tasting the word.')
                await slow_print('  "Yes. You are that. Sorry."')
                await slow_print("  She is not cruel. But the holy fool tells the truth.")
                await slow_print("  Sorry is all you are, and all you have.")
                break
            elif c == "3":
                state["ennui"] += 15
                state["soul"] -= 10
                state["decisions"].append("admitted_lovelessness")
                print()
                await slow_print('  "Poor impostor," she says, and turns away.')
                await slow_print("  Her white dress vanishes into the dark")
                await slow_print("  like smoke from the fire that killed her.")
                await slow_print("  You married her on a bet. She died in a fire.")
                await slow_print("  And you have never loved anyone.")
                await slow_print("  The emptiness is so complete it is almost admirable.")
                break
        except (ValueError, EOFError):
            continue

    clamp_stats()
    print()
    await press_enter()

    # ─── ROUND 4: PYOTR VERKHOVENSKY ─────────────────────────

    clear_screen()
    print(f"""{CYAN}
    ╔═════════════════════════════════════╗
    ║  {WHITE}IV — PYOTR — "The Worm"{CYAN}            ║
    ╚═════════════════════════════════════╝{RESET}
""")

    await slow_print("  He appears clutching your sleeve, eyes bright.")
    await slow_print("  He always did that — clutched, grasped, pulled —")
    await slow_print("  the way a vine wraps around whatever is nearest.")
    print()
    await slow_print("  This is the most dangerous round.")
    await slow_print("  Pyotr does not accuse. He does not plead.")
    await slow_print("  He tempts.")
    print()
    await slow_print(f'  {BOLD}"It is not too late!"{RESET} His voice is urgent, ecstatic.')
    await slow_print(f'  {BOLD}"You can still be Ivan the Tsarevitch!{RESET}')
    await slow_print(f'  {BOLD} Columbus has found his America!{RESET}')
    await slow_print(f'  {BOLD} You are the leader — you are the sun —{RESET}')
    await slow_print(f'  {BOLD} and I am your worm!"{RESET}')
    print()
    await slow_print("  His face is the face of a man in love.")
    await slow_print("  Not with you — with the idea of you.")
    await slow_print("  With the idol he has built from your indifference")
    await slow_print("  and called it strength.")
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
            c = (await ainput(f"  {GREEN}Your answer (1-3): {RESET}")).strip()
            if c == "1" and pyotr_locked:
                state["pyotr_entangled"] -= 20
                state["soul"] += 10
                confrontations += 1
                state["decisions"].append("refused_pyotr_finally")
                print()
                await slow_print("  He recoils.")
                await slow_print("  Something raw crosses his face — almost human.")
                await slow_print("  The grief of a man whose idol has spoken")
                await slow_print("  and said: No. Definitively, finally: No.")
                await slow_print("  His fingers release your sleeve.")
                await slow_print("  For the first time since he arrived in this town,")
                await slow_print("  Pyotr Stepanovich has nothing to say.")
                await slow_print("  He shrinks. The worm becomes a worm.")
                break
            elif c == "1" and not pyotr_locked:
                print(f"  {DIM}You cannot choose this. You are too entangled in his web.{RESET}")
                continue
            elif c == "2":
                state["pyotr_entangled"] += 10
                state["revolutionary_fervor"] += 10
                state["decisions"].append("yielded_to_pyotr")
                print()
                await slow_print("  His eyes light up. The fingers tighten.")
                await slow_print('  "I knew it! I always knew!"')
                await slow_print("  He is wrong, of course. It was never his game.")
                await slow_print("  It was nobody's game. That is the horror.")
                await slow_print("  But now, in your last hours, you have given him")
                await slow_print("  exactly what he wanted: permission to believe")
                await slow_print("  you were what he needed you to be.")
                break
            elif c == "3":
                state["ennui"] += 10
                state["decisions"].append("silent_before_pyotr")
                print()
                await slow_print("  You pull your hand away.")
                await slow_print("  But he keeps clutching. He always keeps clutching.")
                await slow_print("  Even now, even here, even on your last night,")
                await slow_print("  you cannot quite shake him off.")
                await slow_print("  He will follow you everywhere.")
                await slow_print("  Even into the loft.")
                break
        except (ValueError, EOFError):
            continue

    clamp_stats()
    print()
    await press_enter()

    # ─── ROUND 5: STEPAN TROFIMOVICH ─────────────────────────

    clear_screen()
    print(f"""{CYAN}
    ╔═════════════════════════════════════╗
    ║  {WHITE}V — STEPAN — "The Healing"{CYAN}         ║
    ╚═════════════════════════════════════╝{RESET}
""")

    await slow_print("  Your old tutor appears last.")
    await slow_print("  He is wearing his best waistcoat —")
    await slow_print("  the one he wore to the fête, the one")
    await slow_print("  he wore on the road, the one he died in.")
    await slow_print("  He is holding a book. The Gospel of Luke.")
    print()
    await slow_print("  He does not accuse. He does not tempt.")
    await slow_print("  He reads.")
    print()
    await slow_print(f'  {DIM}"And there was there one herd of many swine')
    await slow_print(f'   feeding on the mountain; and they besought him')
    await slow_print(f'   that he would suffer them to enter into them.')
    await slow_print(f'   And he suffered them."{RESET}')
    print()
    await slow_print("  He looks up from the book.")
    await slow_print("  His eyes are wet. They were always wet.")
    await slow_print("  Twenty years he was your tutor. Twenty years")
    await slow_print("  he taught you French and let you down")
    await slow_print("  and loved you in the clumsy, insufficient way")
    await slow_print("  that is the only way he knows.")
    print()
    await slow_print(f'  {BOLD}"The sick man will be healed, Nicolas."{RESET}')
    await slow_print(f'  {BOLD}"Will you be healed?"{RESET}')
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
            c = (await ainput(f"  {GREEN}Your answer (1-3): {RESET}")).strip()
            if c == "1" and stepan_locked:
                state["soul"] += 20
                state["ennui"] -= 15
                confrontations += 1
                state["decisions"].append("heard_the_gospel")
                print()
                await slow_print("  He reads.")
                await slow_print("  And you listen.")
                print()
                await slow_print(f'  {DIM}"And the man out of whom the devils were departed{RESET}')
                await slow_print(f'  {DIM} sat at the feet of Jesus, clothed{RESET}')
                await slow_print(f'  {DIM} and in his right mind...{RESET}')
                await slow_print(f'  {DIM} and they were afraid."{RESET}')
                print()
                await slow_print("  For one moment — just one —")
                await slow_print("  the emptiness recedes.")
                await slow_print("  Not gone. Not healed. But held at bay")
                await slow_print("  by the voice of a ridiculous old man")
                await slow_print("  reading the words that matter.")
                await slow_print("  It is the closest you have ever come to grace.")
                break
            elif c == "1" and not stepan_locked:
                print(f"  {DIM}You cannot choose this. You never built that bond.{RESET}")
                continue
            elif c == "2":
                state["soul"] += 10
                state["stepan_bond"] += 5
                state["decisions"].append("called_stepan_right")
                print()
                await slow_print("  He smiles through his tears.")
                await slow_print('  "Ridiculous! Yes! Always ridiculous!"')
                await slow_print("  He laughs. It is genuine — the laugh")
                await slow_print("  of a man who has been seen truly")
                await slow_print("  and not found entirely wanting.")
                await slow_print("  But he wanted more for you than accuracy.")
                await slow_print("  He wanted you to listen.")
                break
            elif c == "3":
                state["ennui"] += 15
                state["soul"] -= 10
                state["decisions"].append("rejected_stepans_healing")
                print()
                await slow_print("  He weeps.")
                await slow_print("  He closes the book.")
                await slow_print("  He walks away, slowly, leaning on his umbrella,")
                await slow_print("  back into the darkness from which he came.")
                await slow_print("  You are left alone in the silence.")
                await slow_print("  The candle gutters. The letter waits.")
                await slow_print("  There is no one left to read to you.")
                break
        except (ValueError, EOFError):
            continue

    clamp_stats()
    print()

    # ─── THE LETTER ───────────────────────────────────────────

    state["confrontations_survived"] = confrontations

    await press_enter()
    clear_screen()
    print(f"""{CYAN}
    ╔═════════════════════════════════════╗
    ║  {WHITE}THE LETTER TO DASHA{CYAN}                ║
    ╚═════════════════════════════════════╝{RESET}
""")

    await slow_print("  They are gone. All of them.")
    await slow_print("  The room is empty again. The candle burns low.")
    await slow_print("  You sit down and finish the letter.")
    print()

    if confrontations <= 1:
        # Cold, clinical — the novel's actual tone
        await slow_print(f'  {DIM}"Dear Darya Pavlovna,"{RESET}')
        print()
        await slow_print(f'  {DIM}"I have tried my strength everywhere.')
        await slow_print(f'   You advised me to do this, that I might learn')
        await slow_print(f'   to know myself. In testing myself for you')
        await slow_print(f'   and for them, I found my desires are too weak;')
        await slow_print(f'   they cannot guide me."{RESET}')
        print()
        await slow_print(f'  {DIM}"On a log one may cross a river')
        await slow_print(f'   but not on a chip."{RESET}')
        print()
        await slow_print("  The letter is perfect. Cold. Clinical.")
        await slow_print("  A spiritual autopsy performed by the patient himself.")
        await slow_print("  There is no warmth in it. No crack in the armor.")
        await slow_print("  Just the precision of a man who has measured his own void")
        await slow_print("  and found the dimensions exact.")
    elif confrontations <= 3:
        # Flickers of self-awareness
        await slow_print(f'  {DIM}"Dear Darya Pavlovna,"{RESET}')
        print()
        await slow_print(f'  {DIM}"I have tried my strength everywhere.')
        await slow_print(f'   My desires are too weak.')
        await slow_print(f'   But tonight I was visited by the faces')
        await slow_print(f'   of those I have touched, and some of them —')
        await slow_print(f'   not all, but some — did not turn away."{RESET}')
        print()
        await slow_print(f'  {DIM}"Perhaps that is something. I do not know.')
        await slow_print(f'   I have never known what anything means."{RESET}')
        print()
        await slow_print("  The letter shows cracks. Flickers of something")
        await slow_print("  that might be honesty, or might be")
        await slow_print("  the last performance of a consummate actor.")
        await slow_print("  Even you are not sure which.")
    else:
        # Warmer, more honest
        await slow_print(f'  {DIM}"Dear Dasha,"{RESET}')
        print()
        await slow_print(f'  {DIM}"I have tried my strength everywhere,')
        await slow_print(f'   and tonight I found it in the strangest place —')
        await slow_print(f'   in the faces of those I failed.')
        await slow_print(f'   They came to me and I answered them.')
        await slow_print(f'   Not well. Not enough. But I answered."{RESET}')
        print()
        await slow_print(f'  {DIM}"I still intend to go to Uri.')
        await slow_print(f'   I still know what I am. But for one night,')
        await slow_print(f'   in this room, with this candle,')
        await slow_print(f'   something was not empty."{RESET}')
        print()
        await slow_print("  The letter is different.")
        await slow_print("  Still the letter of a man walking toward the loft.")
        await slow_print("  But written by a hand that trembled.")
        await slow_print("  And a trembling hand is a living hand.")

    print()
    await slow_print(f"  {DIM}{'═' * 50}{RESET}")
    print()
    await slow_print(f"  {BOLD}Confrontations survived: {confrontations} of 5{RESET}")
    print()
    if confrontations == 5:
        await slow_print(f"  {GREEN}Every ghost answered. Every bond held.{RESET}")
    elif confrontations >= 3:
        await slow_print(f"  {YELLOW}Some bonds held. Some doors opened.{RESET}")
    elif confrontations >= 1:
        await slow_print(f"  {MAGENTA}Most ghosts turned away unanswered.{RESET}")
    else:
        await slow_print(f"  {RED}Silence. From beginning to end, silence.{RESET}")

    show_status()
    await press_enter()


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


async def chapter_11_reckoning():
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

    await slow_print(f"  {BOLD}EPILOGUE: CONCLUSION{RESET}")
    print()
    await slow_print("  The letter is sealed. The candle is out.")
    await slow_print("  There is nothing left to write, nothing left to say.")
    print()
    await slow_print("  Varvara Petrovna and Dasha came to Skvoreshniki the next morning.")
    await slow_print("  They found all the doors open.")
    await slow_print("  They went upstairs. Then to the loft.")
    print()
    await slow_print("  On the table: a note in pencil.")
    await slow_print(f'  {REVERSE}  "No one is to blame. I did it myself."  {RESET}')
    print()
    await slow_print("  Beside it: a hammer. A piece of soap. A large nail.")
    await slow_print("  The strong silk cord was thickly smeared with soap.")
    print()
    await slow_print("  At the inquest, the doctors absolutely and emphatically")
    await slow_print("  rejected all idea of insanity.")
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
        await slow_print("  You went to Tikhon. You heard the Gospel.")
        await slow_print("  And on your last night, when they came for you —")
        await slow_print("  the ghosts of everyone you touched —")
        await slow_print("  you answered them. Not perfectly. Not enough.")
        await slow_print("  But you answered.")
        await slow_print("  Perhaps it was pride, as the bishop said.")
        await slow_print("  But you reached toward something.")
        await slow_print("  The silk cord was still there. You know that.")
        await slow_print("  But perhaps — only perhaps — for one night,")
        await slow_print("  in one room, with one candle and five ghosts,")
        await slow_print("  another ending was possible.")
        await slow_print(f"  {DIM}Dostoevsky cut the confession chapter from the novel.{RESET}")
        await slow_print(f"  {DIM}Even fiction cannot bear too much hope.{RESET}")
    elif cs >= 4:
        ending_title = "THE WANDERER"
        print(f"  {YELLOW}{BOLD}  ★ ★ ★ ★ ☆  THE WANDERER  ★ ★ ★ ★ ☆{RESET}")
        print()
        await slow_print("  On your last night, you answered almost everyone.")
        await slow_print("  Shatov, Kirillov, Marya, Pyotr, Stepan —")
        await slow_print("  you built enough to face them.")
        await slow_print("  The letter to Dasha was warmer than the novel's.")
        await slow_print("  But without the confession, without the Gospel,")
        await slow_print("  the warmth was not enough to reach the loft")
        await slow_print("  and cut the cord.")
        await slow_print("  In the end, the citizen of the canton of Uri")
        await slow_print("  was found at Skvoreshniki.")
        await slow_print(f"  {DIM}But the bonds you built were real.{RESET}")
        await slow_print(f"  {DIM}That changes nothing. And everything.{RESET}")
    elif cs == 3:
        ending_title = "THE WANDERER"
        print(f"  {YELLOW}{BOLD}  ★ ★ ★ ☆ ☆  THE WANDERER  ★ ★ ★ ☆ ☆{RESET}")
        print()
        await slow_print("  You survived longer than you expected.")
        await slow_print("  You touched something real — in Shatov's garret,")
        await slow_print("  or at Stepan Trofimovich's side, or on the bridge.")
        await slow_print("  But it was not enough. The silk cord was patient.")
        await slow_print("  The house in Uri was a fiction. The letter to Dasha")
        await slow_print("  was a goodbye that could not say its own name.")
        await slow_print("  In the end, the citizen of the canton of Uri")
        await slow_print("  was found in the loft at Skvoreshniki.")
        await slow_print(f"  {DIM}The swine went over the cliff.{RESET}")
        await slow_print(f"  {DIM}But the sick man — Russia — will be healed.{RESET}")
        await slow_print(f"  {DIM}Stepan Trofimovich said so.{RESET}")
    elif cs == 2:
        ending_title = "THE POSSESSED"
        print(f"  {MAGENTA}{BOLD}  ★ ★ ☆ ☆ ☆  THE POSSESSED  ★ ★ ☆ ☆ ☆{RESET}")
        print()
        await slow_print("  The demons entered and did their work.")
        await slow_print("  Not from outside — from within.")
        await slow_print("  From the terrible leisure of an aristocrat")
        await slow_print("  who tried everything and felt nothing.")
        await slow_print("  From the vacuum at the center that drew in")
        await slow_print("  everyone who loved you, believed in you,")
        await slow_print("  projected their God and their Russia onto your face.")
        await slow_print("  The silk cord. The soap. The nail.")
        await slow_print("  Premeditation and consciousness to the last moment.")
        await slow_print(f"  {DIM}Even negation did not come from you.{RESET}")
        await slow_print(f"  {DIM}Everything was always petty and spiritless.{RESET}")
    else:
        ending_title = "THE ABYSS"
        print(f"  {RED}{BOLD}  ★ ☆ ☆ ☆ ☆  THE ABYSS  ★ ☆ ☆ ☆ ☆{RESET}")
        print()
        await slow_print("  Nothing. From beginning to end, nothing.")
        await slow_print("  The emptiness was so total that it pulled")
        await slow_print("  the entire town into itself — Shatov, Kirillov,")
        await slow_print("  Marya Timofeyevna, Liza, Lebyadkin, Stepan Trofimovich.")
        await slow_print("  All of them swallowed by the void at your center.")
        await slow_print("  On your last night, the ghosts came and you could not answer.")
        await slow_print("  Pyotr Verkhovensky used you and discarded you.")
        await slow_print("  Your mother found you in the loft.")
        await slow_print("  The note said no one was to blame.")
        await slow_print("  The doctors said you were sane.")
        await slow_print(f"  {DIM}Both statements were lies dressed as truth.{RESET}")
        await slow_print(f"  {DIM}Your specialty.{RESET}")

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
    await press_enter()

    play_again = (await ainput(f"  {GREEN}Play again? (y/n): {RESET}")).strip().lower()
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


async def main():
    global _current_chapter_index
    while True:
        # Reset state
        state.update(DEFAULT_STATE)
        state["decisions"] = []  # ensure a fresh list (not the default's)

        result = await title_screen()
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
                await slow_print(f"\n  {YELLOW}Resuming your journey...{RESET}")
                await slow_print(f"  {DIM}Chapter: {CHAPTERS[start_index][0]}{RESET}")
                await dramatic_pause(1.5)

        try:
            for i in range(start_index, len(CHAPTERS)):
                _current_chapter_index = i
                name, func = CHAPTERS[i]

                # Secret Tikhon chapter — insert after Shatov murder, before Aftermath
                if i == _IDX_AFTERMATH and check_tikhon_unlock():
                    await chapter_secret_tikhon()

                # Run the chapter
                if i == _IDX_CONCLUSION:
                    # Conclusion returns True/False for play-again
                    if not await func():
                        clear_screen()
                        await slow_print(f"\n  {DIM}The candle goes out. The samovar cools.")
                        await slow_print(f"  The silk cord hangs in the loft at Skvoreshniki.{RESET}")
                        await slow_print(f"  {DIM}Somewhere on the high road, an old man with an umbrella{RESET}")
                        await slow_print(f"  {DIM}asks a stranger to read to him from the Gospels.{RESET}")
                        await slow_print(f"  {DIM}The sick man will be healed.{RESET}")
                        await slow_print(f"  {DIM}Russia endures. It always endures.{RESET}")
                        print()
                        delete_save()
                        print(f"  {GREEN}Farewell. May your soul be heavier than your ennui.{RESET}\n")
                        return
                    else:
                        delete_save()
                        break  # restart the while loop
                else:
                    await func()
                    # Auto-save after each chapter
                    save_game(i + 1)
        except GameOverException:
            # Fatal decision — return to title screen, save is preserved
            continue


if __name__ == "__main__":
    asyncio.run(main())
