"""World seed for Milestone 1: archetypes, the starting location and a default character.

Lore moves to RAG lorebooks in M2, and characters move to Lakebase in M3. This module stays
the source of archetype stats.
"""

from dataclasses import dataclass, field

from pydantic import BaseModel

from rpg.rules import Stat

STARTING_GOLD = 12


@dataclass(frozen=True)
class Archetype:
    name: str
    might: int
    wits: int
    charm: int
    max_hp: int
    kit: tuple[str, ...]


ARCHETYPES: dict[str, Archetype] = {
    "warrior": Archetype("Warrior", 3, 0, 1, 18, ("longsword (d6+2)", "shield", "rope")),
    "mage": Archetype("Mage", 0, 3, 1, 12, ("ember wand (d6+2 spell)", "lantern", "satchel of runes")),
    "bard": Archetype("Bard", 1, 0, 3, 14, ("rapier (d6+1)", "lute", "letter of introduction")),
}


class Character(BaseModel):
    name: str
    archetype: str
    might: int
    wits: int
    charm: int
    hp: int
    max_hp: int
    xp: int = 0
    gold: int
    inventory: list[str]

    def modifier(self, stat: Stat) -> int:
        return getattr(self, stat.value)

    @property
    def defence(self) -> int:
        return 10 + max(self.might, self.wits)


def new_character(name: str, archetype: str) -> Character:
    name = name.strip()
    if not name:
        raise ValueError("name must not be blank")
    key = archetype.strip().lower()
    if key not in ARCHETYPES:
        raise ValueError(f"unknown archetype {archetype!r}; choose from {sorted(ARCHETYPES)}")
    a = ARCHETYPES[key]
    return Character(
        name=name, archetype=key, might=a.might, wits=a.wits, charm=a.charm,
        hp=a.max_hp, max_hp=a.max_hp, gold=STARTING_GOLD, inventory=list(a.kit),
    )


@dataclass(frozen=True)
class Location:
    id: str
    name: str
    description: str
    exits: tuple[str, ...]
    gates: dict[str, str] = field(default_factory=dict)  # exit id -> flag that must be "yes"

    def barrier(self, exit_id: str, flags: dict) -> str | None:
        required = self.gates.get(exit_id)
        return required if required and flags.get(required) != "yes" else None


START_LOCATION_ID = "medallion-inn"

LOCATIONS: dict[str, Location] = {
    START_LOCATION_ID: Location(
        id=START_LOCATION_ID,
        name="The Medallion Inn, Lakehouse Village",
        description=(
            "A three-storey coaching inn at the heart of Lakehouse Village in the Kingdom of "
            "Sparkia. Its rooms are named Bronze, Silver and Gold, from the draughty attic to "
            "the gilded suite. Travellers swap rumours by the fire: the Delta river has begun "
            "running backwards some nights, and the Unity Archive has sealed its doors. The "
            "innkeeper, Marta Quill, knows everyone's business and sells it by the half-pint."
        ),
        exits=("delta-crossing", "unity-archive"),
        gates={"unity-archive": "knows_cellar_route"},
    ),
    "delta-crossing": Location(
        id="delta-crossing",
        name="The Delta Crossing",
        description=(
            "A wide, cold ford where the river Delta runs in visible layers, each current a "
            "different day. A rope ferry worked by a silent ferryman called the Sweeper crosses "
            "to the road for the Unity Archive. Upstream stand the broken piers of the old bridge."
        ),
        exits=("medallion-inn", "unity-archive", "data-swamp"),
        gates={"data-swamp": "has_catalog"},
    ),
    "unity-archive": Location(
        id="unity-archive",
        name="The Unity Archive",
        description=(
            "The great library of Sparkia, a hill of grey stone and bronze doors that answer only "
            "to proper writs. The doors are sealed. Behind them, Keeper Aldric guards the vault. "
            "Three roads leave its courtyard for the realm's great houses."
        ),
        exits=("delta-crossing", "spark-forge", "streaming-falls", "photon-mines", "medallion-inn"),
        gates={"spark-forge": "spoke_with_aldric", "streaming-falls": "spoke_with_aldric",
               "photon-mines": "spoke_with_aldric", "medallion-inn": "knows_cellar_route"},
    ),
    "spark-forge": Location(
        id="spark-forge",
        name="The Spark Forge",
        description=(
            "A tower of furnaces where Sparkia's mages learn to kindle. Apprentices work in rings "
            "around a single great flame. Forgemaster Ignatia Vale holds the Forge Seal."
        ),
        exits=("unity-archive",),
    ),
    "streaming-falls": Location(
        id="streaming-falls",
        name="The Streaming Falls",
        description=(
            "A curtain of water that never stops, where the river's memory spills into mist. In "
            "the spray, shapes replay what travellers once did. The Echo keeps the Falls Seal."
        ),
        exits=("unity-archive",),
    ),
    "photon-mines": Location(
        id="photon-mines",
        name="The Photon Mines",
        description=(
            "Deep galleries lit by ore that shines like trapped light. The tunnels shift after "
            "every collapse, and miners chalk each turn on the walls. Shiftmaster Odo Brack holds "
            "the Mines Seal."
        ),
        exits=("unity-archive",),
    ),
    "data-swamp": Location(
        id="data-swamp",
        name="The Data Swamp",
        description=(
            "A sprawling fen where walled-away records rot into mud and the water runs every way "
            "at once. Swamp rats, Orphans and worse lurk here, and Warden Grisle keeps the road to "
            "Silo's Keep."
        ),
        exits=("delta-crossing", "silos-keep"),
        gates={"silos-keep": "has_catalog"},
    ),
    "silos-keep": Location(
        id="silos-keep",
        name="Silo's Keep",
        description=(
            "A fortress of walled-up books rising from the swamp, its corridors bricked shut with "
            "volumes. At its heart, Lord Silo keeps the realm's knowledge from everyone."
        ),
        exits=("data-swamp",),
    ),
}

DEFAULT_CHARACTER = new_character("Brannoc", "warrior")
