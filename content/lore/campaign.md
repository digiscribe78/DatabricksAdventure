# The Campaign: Lord Silo and the Lost Catalog

## Premise

The realm's knowledge is draining away. The Delta runs backwards on some nights, and the Unity Archive has sealed its doors. Inside, Keeper Aldric holds the vault shut against Lord Silo, who wants the Lost Catalog: the one book that indexes everything the Kingdom of Sparkia knows. With it, Silo could find and wall away every last record in the realm.

Lord Silo was once the Archive's greatest Keeper, and Aldric's own master. Years ago a war began over a stolen map, and grief turned Silo's love of knowledge into fear of it. He came to believe knowledge must be walled away from everyone, for everyone's good. Aldric, then young, helped him raise the first walls, and has regretted it ever since. This is the story's heart: reveal it only in Act 3.

## Act 1

The player begins at The Medallion Inn. Marta Quill fears for her old friend Aldric; if the player promises to find him, set `vowed_to_find_aldric`. At The Delta Crossing the Sweeper ferries travellers towards the Archive road; if he trusts the player he shows them an older current, the night Silo's wardens diverted the river, and you set `saw_the_diversion`. At The Unity Archive the bronze doors stay shut, but Keeper Aldric speaks through them, explains that the vault opens only to three seals held by the realm's great houses, and asks for help. Set `spoke_with_aldric` when he does: this opens the roads to the three houses.

If Marta comes to trust the player deeply (disposition +2), she reveals that the inn cellar's running water reaches the Archive undercroft; set `knows_cellar_route`.

## Act 2

The three seal locations may be visited in any order. Offer them; never push one.

- The Spark Forge: Forgemaster Ignatia Vale sets the Trial of Kindling. Award the Forge Seal (`seal_forge`) only to a player who shares the spark rather than hoarding it. If she confesses that her forge made the fire for Silo's walls, set `forge_regret_shared`.
- The Streaming Falls: the Echo replays the player's own past choices. Award the Falls Seal (`seal_falls`) when the player honestly faces one. If the Echo quotes a remembered choice from another adventure, also set `echo_saw_past_life`.
- The Photon Mines: Shiftmaster Odo Brack's crew is trapped. Rescuing them sets `crew_rescued` and earns the Mines Seal (`seal_mines`).

## Act 3

With all three seals, the player returns to The Unity Archive. The vault opens and they take the Lost Catalog: set `has_catalog`. Aldric, now met face to face, confesses that Silo was his master and that he helped build the walls. If the player helps him make peace with that, set `aldric_forgives_silo`.

Silo's agents strike once the Catalog leaves the vault. The Sweeper's downstream ferry from The Delta Crossing carries the player into The Data Swamp, where Warden Grisle holds the causeway gate. Record how they pass him with `grisle_outcome` set to `fought`, `bribed` or `bluffed`. Beyond lies Silo's Keep and the finale.

## Endings

The finale is at Silo's Keep. Three ways to win; record the winning way with `ending` set to `might`, `wits` or `charm`.

- Might: wound Lord Silo three times with resolve_attack (defence 14). After each hit set `silo_wounds` to the new count (`1`, `2`, `3`). With `crew_rescued`, Odo's miners hold the Sealing Wardens back; otherwise two wardens fight beside Silo. Three wounds break his walls: set `ending` to `might`.
- Wits: present the Lost Catalog as proof that knowledge belongs to everyone. Wits check DC 16, or DC 12 if `forge_regret_shared`. On success set `ending` to `wits`.
- Charm: only possible if `aldric_forgives_silo`. Charm check DC 12 if Marta trusts the player or `echo_saw_past_life`, otherwise DC 16. Offer Silo his old friend's forgiveness; on success set `ending` to `charm`.
- A failed Wits or Charm check closes the walls in; the player may try the other approach, or fight.
- Being downed during the finale ends the adventure in defeat.

## Rules for the Dungeon Master

- Never reveal that Silo was Aldric's master before Act 3.
- Never name Silo's location before `has_catalog`.
- The Echo only quotes the player.
- Every seal must be *earned*, never handed over.
- Offer, never force: the player chooses the order of Act 2.
