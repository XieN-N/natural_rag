# Dark Druid Altar

[Aside block] Dark Druid Altar
------------------------------

### Transparency

Yes

### Luminance

No

### Hardness

?

### Blast Resistance

300.0

### Tool

None

### Renewable

No

### Stackable

Yes (64)

### Flammable

No

### Compostable

No

### ID

druid\_altar

The Dark Druid Altar ingame

The Assembly interface. Each part is colour-coded based on the coloured text to the left.

The **Dark Druid Altar** is a utility block that generates at the center of Druid Circles. It assembles four items together, primarily to create the Swamp Talisman needed to access The Betweenlands.

Contents
--------

* 1 How to Use
* 2 Reactivating the Druid Spawner
* 3 Indestructibility
* 4 Sounds
* 5 History

How to Use
------------

The assembly interface can be accessed by right-clicking the Dark Druid Altar.

Assembling the Swamp Talisman requires four Swamp Talisman Pieces, which are placed in the four corner slots of the interface. Each piece must be a different type, or else the assembly process will not function.

Once these requirements are met, all nearby Dark Druids from the Druid Circle will die. The Dark Druid Altar will then perform an animation levitating the four pieces of the talisman together into the whole Swamp Talisman. During the animation, the surrounding Rune Stone of the Druid Circle will flash white, and runes will slowly float from them to the assembling pieces. A special altar sound will also play.

Once assembly is complete, the Dark Druid Monster Spawner underneath the Altar will be destroyed. The assembled Swamp Talisman can then be retrieved from the middle slot of the assembly interface.

| Result | Ingredients | Recipe |
| --- | --- | --- |
| Swamp Talisman | Each Swamp Talisman Piece |  |

You can add your own assembly recipes in the recipes.json in the config.

Reactivating the Druid Spawner
--------------------------------

The Dark Druid Altar can be used to recreate the Monster Spawner of the Druid Circle that was spawning Dark Druids before the Swamp Talisman was assembled, in case the player wants to fight the Druids again for more Talisman Pieces. To do so, simply place four Saplings of any variety in the four corner slots of the assembly interface. The saplings will float up in the usual assembly animation, and once they come together, the spawner will be recreated.

| Result | Ingredients | Recipe |
| --- | --- | --- |
| Reactivates Dark Druid Monster Spawner | Any Sapling (4) |  |

Indestructibility
-------------------

The Dark Druid Altar cannot be broken, moved, or collected in any way by players in Survival Mode, nor can it be destroyed by explosions.

Sounds
--------

| Sound | Subtitles | Source | Description | ID |
| --- | --- | --- | --- | --- |
| https://the-betweenlands.fandom.com/wiki/File:Druid\_chant.ogg | Mysterious chanting | Blocks | Plays when the Dark Druid Altar is assembling the completed Swamp Talisman | druid\_chant |

History
---------

* Release 3.3.9: Can now reactivate the Druid Spawner using Saplings.
* Release 3.3.0: Tweaked druid\_chant sound.
* Beta 2.0.2: Added recipes to API.
* **Beta 1.0.0**: Introduced.