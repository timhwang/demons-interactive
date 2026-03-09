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
- The game **auto-saves** after each chapter. If you quit mid-game, select **Continue** at the title screen to resume.

## Overview

- **14 chapters** spanning the full arc of the novel, plus a **secret unlockable chapter**
- **~20 decision points** that shape your stats and determine your ending
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

1. **The Penitent** — Requires the secret chapter + high soul score
2. **The Wanderer** — Touched something real, but not enough
3. **The Possessed** — The demons did their work
4. **The Abyss** — Nothing, from beginning to end

## Chapter List

1. The Return
2. The Drawing Room
3. The Duel
4. Night — Kirillov
5. Night — Shatov
6. Night — Lebyadkins
7. Ivan the Tsarevitch
8. The Meeting
9. The Fete
10. Liza
11. A Busy Night
12. The Aftermath
13. Stepan's Wandering
14. Conclusion

*Plus: At Tikhon's (secret, conditional)*

## Save System

The game saves automatically to `~/.demons_save.json` after each chapter. The save file is deleted upon completing the game. To start fresh, simply choose "Begin anew" at the title screen or delete the save file manually.

## Contributing

Contributions are welcome. The game is a single Python file (`demons.py`) with no external dependencies. The architecture is straightforward:

- Each chapter is a standalone function
- The `CHAPTERS` list in `main()` defines the play order
- `state` dict tracks all stats, decisions, and flags
- `check_tikhon_unlock()` gates the secret chapter
- `slow_print()` handles the character-by-character text display with skip support
- Decision tags (stored in `state["decisions"]`) are used for the ending calculation and recap

If adding a new scene, add the function, register it in `CHAPTERS`, and update the decision labels and humane choice lists at the bottom of the file.

## License

This is a fan work based on a public domain novel. The game code is provided as-is for educational and entertainment purposes.

---

*"The sick man will be healed and will sit at the feet of Jesus, and all will look upon him with astonishment." — Luke viii. 35*
