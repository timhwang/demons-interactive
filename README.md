# Demons / Бесы — An Interactive Text Adventure

A terminal-based interactive fiction game based on Fyodor Dostoevsky's novel *The Possessed* (*Demons*, 1872), translated by Constance Garnett.

You play as **Nikolai Vsevolodovich Stavrogin** — aristocrat, officer, husband, destroyer — navigating the collapse of a provincial Russian town consumed by nihilism, conspiracy, and spiritual crisis.

## How to Play

```bash
python3 demons.py
```

**Requirements:** Python 3.6+ (no external dependencies). Runs in any terminal that supports ANSI escape codes.

### Controls
- **Number keys** — select choices at decision points
- **Enter** — press during scrolling text to skip ahead instantly
- **S** — save your game to a slot at any decision point

## Overview

- **15 chapters** spanning the full arc of the novel, plus a **secret unlockable chapter**
- **~30 decision points** that shape your stats and determine your ending
- **8 game-ending decisions** — 3 physical deaths and 5 soul deaths where a wrong choice ends your run instantly
- **4 possible endings** based on cumulative choices
- **~60–75 minutes** per playthrough
- **1 secret chapter** — "At Tikhon's," the suppressed confession chapter Dostoevsky's editor cut from the 1872 publication. Unlocked by making enough humane choices across the game.

### Stats

| Stat | Description |
|------|-------------|
| **Ennui** | Existential paralysis. High ennui darkens endings. |
| **Revolutionary Fervor** | Entanglement with Pyotr Verkhovensky's conspiracy. |
| **Soul** | Capacity for genuine human feeling. |
| **Notoriety** | How the town perceives you. |
| **Tea** | Cups of tea consumed (tracked for historical accuracy). |

Relationship trackers for key characters (Shatov, Pyotr, Marya, Stepan, Liza) also influence the story and ending.

### Endings

1. **The Penitent** — Requires the secret chapter + hearing the gospel + surviving 4+ confrontations
2. **The Wanderer** — Touched something real, but not enough
3. **The Possessed** — The demons did their work
4. **The Abyss** — Nothing, from beginning to end

### Game-Ending Decisions

Not every choice is safe. Throughout the game, certain decisions will end your run immediately — some through physical death, others through spiritual surrender. These options are not marked or color-coded; you must use your own judgment.

**Soul deaths** give you a named ending (THE VOID, CONSUMED, THE ACCOMPLICE, THE WITNESS, THE DEMON) before returning you to the title screen.

## Chapter List

1. The Return
2. The Drawing Room
3. The Duel
4. Night — Kirillov
5. Night — Shatov
6. Night — Lebyadkins
7. Ivan the Tsarevitch
8. The Meeting
9. The Fête
10. Liza
11. A Busy Night
12. The Aftermath
13. Stepan's Wandering
14. The Last Night
15. Conclusion

*Plus: At Tikhon's (secret, conditional)*

## Save System

The game supports **3 manual save slots** plus an **auto-save** after each chapter.

- **Manual saves:** Press **S** at any decision prompt to save to one of 3 slots. Each slot records your chapter, stats, and all decisions.
- **Auto-save:** The game auto-saves to a separate slot after each chapter.
- **Loading:** Select a save slot from the title screen to resume. Auto-save and manual slots are listed separately.
- **Game over:** If a fatal decision kills you, your saves are preserved — load a slot and try again.

Save data is stored in `~/.demons_save.json`. To start completely fresh, choose "Begin anew" at the title screen or delete the file manually.

## The Last Night (Final Boss)

Chapter 14 is a psychological gauntlet: five confrontations with characters whose fates you shaped throughout the game. Each confrontation tests a different relationship or stat — choices that were locked behind stat gates earlier in the game determine whether the strongest option is available to you.

Your **confrontations survived** count (0–5) replaces the old weighted score and directly determines your ending.

## Score Card

At the end of a complete playthrough, the game displays a shareable ASCII art score card with:
- Your ending title and score (0–999)
- Top 3 superlative awards (e.g., "Most Soulful," "The Nihilist," "Tea Connoisseur")
- A short performance description
- Designed to be screenshot-friendly for sharing

## Contributing

Contributions are welcome. The game is a single Python file (`demons.py`) with no external dependencies. The architecture is straightforward:

- Each chapter is a standalone function
- The `CHAPTERS` list defines the play order
- `state` dict tracks all stats, decisions, and flags
- `check_tikhon_unlock()` gates the secret chapter
- `slow_print()` handles the character-by-character text display with skip support
- `game_over()` raises `GameOverException` for fatal decisions — caught in `main()` to return to the title screen
- `save_to_slot()` / `load_slot()` handle the 3-slot manual save system
- `generate_score_card()` builds the end-of-game shareable card
- Decision tags (stored in `state["decisions"]`) are used for the ending calculation and recap

If adding a new scene, add the function, register it in `CHAPTERS`, and update the decision labels and humane choice lists at the bottom of the file.

## License

This is a fan work based on a public domain novel. The game code is provided as-is for educational and entertainment purposes.

---

*"The sick man will be healed and will sit at the feet of Jesus, and all will look upon him with astonishment." — Luke viii. 35*
