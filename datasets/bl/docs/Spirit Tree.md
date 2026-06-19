# Spirit Tree

[Aside block] Spirit Tree
-------------------------

### Type

Natural

### Generation

Swamplands Clearing

 Map Icon

The Large Face of the tree

**Spirit Trees** are unique boss-like trees. They feature a dense, drooping canopy, a thick trunk etched with carvings, and huge roots that jut out into the surrounding area. The trunk is surrounded by small stone pedestals, occasionally topped with Wisps.

The Spirit Tree contains multiple sentient, hostile **Small Spirit Tree Face** mobs, and a single **Large Spirit Tree Face** that acts as the primary boss.

The Spirit Tree has a world location that identifies the area it takes up, as well as a title that appear briefly to players who approach it. While in the location, the surrounding area will be covered in a light fog, and ambient sounds will fade away.

Most of the blocks of the Spirit Tree and its surroundings are protected from destruction by a ward that persists until the Large Spirit Tree Face is defeated. The tree also has varying levels of difficulty and rewards depending on the number of Wisps on the pedestals surrounding it.

Contents
--------

* 1 Generation & Spawning
* 2 Composition
* 3 Behavior
  + 3.1 Small Spirit Tree Face
  + 3.2 Large Spirit Tree Face
* 4 Effects of Wisps
  + 4.1 Removing Wisps
  + 4.2 Adding Wisps
* 5 Strategy
* 6 Aftermath
* 7 Growing
* 8 Drops
  + 8.1 spirit\_tree\_face\_small
  + 8.2 spirit\_tree\_face\_large
* 9 Advancements
* 10 Sounds
* 11 History

Generation & Spawning
-----------------------

One Spirit Tree will always generate in the center of the Swamplands Clearing sub-biome. The Small Spirit Tree Faces continually spawn on the roots of the tree, while the Large Spirit Tree Face spawns on the main trunk.

Composition
-------------

Spirit Trees consist of:

* Spirit Tree Log, as the log block
* Spirit Tree Leaves, as the leaf block
* Root, jutting from around the base and roots
* Mossy Betweenstone Bricks, at the bases of the pedestals
* Mossy Betweenstone Brick Wall, as the main poles of the pedestals
* Wisp, on top of some of the pedestals (unprotected)

Behavior
----------

[Aside block] Spirit Tree Face
------------------------------

### Health

Small: 20 
Large: 600 ( x 300)

### Damage

Default wisp strength:  
Small Sap Spit: 3 
Large Sap Spit: 4 
Root Spit Easy: 7 
Root Spit Normal: 12 
Root Spit Hard: 18  

Root Wave: 10 
### Drops

Small:  
 Sap Spit  
 Small Spirit Tree Face Mask  
Large:  
 Bark Amulet  
 Large Spirit Tree Face Mask  
 Spirit Tree Sapling  
*(See Drops for more info)*

### Experience

Small: 4  
Large:  
Minimum wisp strength: 150  
Default wisp strength: 300  
Maximum wisp strength: 2100

### ID

spirit\_tree\_face\_small  
spirit\_tree\_face\_large

Spirit Trees can manifest two types of faces across its bark to attack intruders: Small and Large.

Both Small and Large Faces take additional damage when hit with an Axe, but are unsusceptible to Lava or drowning.

### Small Spirit Tree Face
**Small Spirit Tree Faces** act as supporting sentries, and spawn on both the main trunk and the surrounding roots of the tree. They have a couple variants with slightly different appearances. They can disappear and reappear on any side of a connected Spirit Tree Log, often doing so to reach a position where they can target the player. Their eyes and mouth glow before shooting Sap Spit projectiles at players nearby, even if they are too far away to hit. If killed, they will respawn after a while as long as the Large Spirit Tree Face remains alive.

If the block a Small Spirit Tree Face is on is somehow removed, or if it otherwise ends up in an invalid position, it will drop to the ground and attempt to teleport to a nearby Spirit Tree Log.

### Large Spirit Tree Face
The **Large Spirit Tree Face** is the main boss, and can be found on the tree's trunk, occasionally disappearing and reappearing on other sides of it. It has a high amount of health and uses the same Sap Spit attack as the smaller faces, on top of three additional attacks:

* **Root Spit**: If the player gets too close, it will eventually start to suck in air for a few seconds before spitting out several rounds of root spikes at a relatively short range but dealing extreme damage.
* **Root Wave**: Rolling waves of root spikes that travel quickly along the ground around the tree. About three waves of spikes will be summoned per attack, and the radius they follow attempts to track the player's position. The spikes can be jumped over with sufficient timing, or avoided completely.
* **Root Entanglement**: A small bundle of roots will appear directly below the player. If they do not move out of the way in time, the roots will shoot out and entangle the player, immobilizing them for a short period.

Effects of Wisps
------------------

A Spirit Tree with maximum Wisps

The number of Wisps on the pedestals surrounding the Spirit Tree affect the difficulty of its attacks, as well as the amount and types of loot that will be obtained upon its defeat.

This system is determined by a "wisp strength" value that starts at 1.0 with the default wisp number generated with every Spirit Tree, and fluctuates based on wisps added or removed. The change is not immediate, but rather a gradual shift over the course of the fight, so it is not possible to fight the tree at a lower wisp value and then change it to a higher value at the last moment to exploit the rewards.

The current wisp strength value is denoted visually by the glow colour of the Spirit Tree Faces.

### Removing Wisps
Removing naturally generated Wisps will gradually decrease the wisp strength value, down to a minimum of 0.5. A wisp strength value below 1.0 results in attacks being slower and dealing less damage, but also reduces the experience the Large Face drops by `(300 * strength value)`. Note that naturally generated Wisps can only be removed if the Large Spirit Tree Face is above 50% health, and Wisps placed by the player cannot be removed at all.

### Adding Wisps
Adding additional Wisps onto empty pedestals will gradually increase the wisp strength value, up to a maximum of 2.0. A wisp strength value above 1.0 results in attacks being faster and dealing more damage, but also increases the experience the Large Face drops by `(300 * (1 + (strength value - 1) * 6))`. Higher wisp strengths also means that there is a chance for more Spirit Tree Saplings to drop from the Large Face - each 0.2 strength above 1.0 results in an additional chance for a sapling to drop, more likely the higher the strength is, up to maximum possible saplings at a strength of 1.95. A wisp strength of 1.4 or higher results in the Large Spirit Tree Face Mask dropping as well.

Strategy
----------

The Spirit Tree uses a large number of attacks that can be overwhelming at first. Ranged combat is the safest for dodging projectiles and roots, but Axes also deal considerable melee damage if the player can get close, especially an Octine Axe due to its additional fire damage. Having a Shield is also useful to block the tree's constant projectiles.

Covering the roots surrounding the tree with blocks can also be a viable way to avoid the Small Faces' attacks while attacking the Large Face. As the Large Face will not despawn nor regenerate health, players who find themselves unequipped for the fight can always flee and return later.

Aftermath
-----------

Upon defeating the Large Spirit Tree Face, the Tree's block protection ward will disappear, new Small Faces will stop spawning, and the tree and the area around it will start to decay.

Several blocks of Spreading Sludgy Dirt will spawn around the Tree's base, and several Spreading Rotten Bark blocks will replace some of the Spirit Tree Logs, appearing both in the base of the tree and on its surrounding roots. These blocks will slowly convert neighbouring Swamp Grass and Spirit Tree Logs into themselves, spreading across the Tree and the surrounding area.

As Rotten Bark spreads to the branches, the Spirit Tree Leaves will begin to break, occasionally dropping Spirit Fruit. Any of the Clearing's ground cover plants will also turn into Dead Weedwood Bushes as their supporting grass block decays.

If left unchecked, the decay will spread until it has consumed the entire Swamplands Clearing sub-biome, essentially turning it into a miniature Sludge Plains biome that is capable of spawning Sludges and Smol Sludges. However, this can be prevented if the spreading blocks are removed or isolated quickly enough before they can expand out of control.

Once the Large Face has been defeated, the Spirit Tree's icon on an Amate Map will be accompanied by a check mark.

Growing
---------

The small friendly tree grown from saplings

While natural Spirit Trees cannot be grown, smaller, friendlier versions can be grown from Spirit Tree Saplings. These smaller trees consist purely of the log and leaf blocks and are inhabited by a single, friendly Small Spirit Tree Face. This Face has almost the same stats and behavior as the hostile ones, but will attack nearby hostile mobs instead of the player, albeit at a lesser range. The face can connect to Spirit Tree Logs added to its tree to extend its range, making an effective sentry. Friendly Small Spirit Tree Faces can also be fed by right-clicking them with Compost, healing them by 4 health () and occasionally causing them to drop 1-3 Sap Spit.

Friendly Small Spirit Tree Faces can be given Amulets, giving them a Middle Gem Circle modifier that directly affects the face's own attacks and the player they are assigned to while they are alive. The number of amulets that they can equip at once can be extended with an Amulet Slot, and amulets can be taken off of them by shift right-clicking them. *(NOTE: Amulet Slot extension for this mob is intended but not yet implemented.)*

Spirit Trees grown from saplings do not appear with a map icon on an Amate Map.

Drops
-------

The drops from Small and Large Spirit Tree Faces are derived from two loot tables: spirit\_tree\_face\_small and spirit\_tree\_face\_large, respectively. On top of that, Spirit Fruit can also be dropped from the tree's leaves when broken.

The following is a list of all of the items that can be dropped by Small and Large Spirit Tree Faces, including their rolls, quantities, and weights.

### spirit\_tree\_face\_small
| Small Spirit Tree Face Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Nothing** | N/A | 2/3 (66.67%) |
| **Sap Spit** | 1 (+0-1 per Looting level) | 1/3 (33.33%) |
| 1 Roll: | | |
| **Nothing** | N/A | 8/9 (88.89%) |
| **Small Spirit Tree Face Mask** | 1 | 1/9 (11.11%) |

### spirit\_tree\_face\_large
| Large Spirit Tree Face Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Bark Amulet** | 1 | 1/1 (100%) |
| 1 Roll, if at 1.4 Wisp strength or higher: | | |
| **Large Spirit Tree Face Mask** | 1 | 1/1 (100%) |
| 1 Roll: | | |
| **Spirit Tree Sapling** | 1 | 1/1 (100%) |
| 1 Roll, if at 1.2 Wisp strength or higher: | | |
| **Nothing** | N/A | 5/6 (83.33%) |
| **Spirit Tree Sapling** | 1 | 1/6 (16.67%) |
| 1 Roll, if at 1.4 Wisp strength or higher: | | |
| **Nothing** | N/A | 4/5 (80%) |
| **Spirit Tree Sapling** | 1 | 1/5 (20%) |
| 1 Roll, if at 1.6 Wisp strength or higher: | | |
| **Nothing** | N/A | 3/4 (75%) |
| **Spirit Tree Sapling** | 1 | 1/4 (25%) |
| 1 Roll, if at 1.8 Wisp strength or higher: | | |
| **Nothing** | N/A | 2/3 (66.67%) |
| **Spirit Tree Sapling** | 1 | 1/3 (33.33%) |
| 1 Roll, if at 1.95 Wisp strength or higher: | | |
| **Nothing** | N/A | 1/2 (50%) |
| **Spirit Tree Sapling** | 1 | 1/2 (50%) |

Visit the Loot Tables page for more information on loot.

Advancements
--------------

| Advancement | In-game Description | Parent | Actual Requirements | ID |
| --- | --- | --- | --- | --- |
| Illegal Logging | Defeat a **Spirit Tree** | Chopping Boy | Kill the Large Spirit Tree Face of a **Spirit Tree** | fighter /illegal\_logging |

Sounds
--------

| Sound | Subtitles | Source | Description | ID |
| --- | --- | --- | --- | --- |
| https://the-betweenlands.fandom.com/wiki/File:Spirit\_tree\_face\_large\_death.ogg | Spirit Tree dies | Hostile | Plays when the large spirit tree dies. | spirit\_tree\_face\_large\_death |
| https://the-betweenlands.fandom.com/wiki/File:Spirit\_tree\_face\_large\_emerge.ogg | N/A | Hostile | Plays when the Large Spirit Tree face moves from one side to another. | spirit\_tree\_face\_large\_emerge |
| https://the-betweenlands.fandom.com/wiki/File:Spirit\_tree\_face\_large\_living\_1.ogg https://the-betweenlands.fandom.com/wiki/File:Spirit\_tree\_face\_large\_living\_2.ogg https://the-betweenlands.fandom.com/wiki/File:Spirit\_tree\_face\_large\_living\_3.ogg https://the-betweenlands.fandom.com/wiki/File:Spirit\_tree\_face\_large\_living\_4.ogg | Spirit Tree creaks | Hostile | Plays when the Spirit Tree is idle. | spirit\_tree\_face\_large\_living |
| https://the-betweenlands.fandom.com/wiki/File:Spirit\_tree\_face\_small\_emerge.ogg | N/A | Hostile | Plays when a Small Spirit Tree face moves from one log to another. | spirit\_tree\_face\_small\_emerge |
| https://the-betweenlands.fandom.com/wiki/File:Spirit\_tree\_face\_spit.ogg | Spirit Tree spits | Hostile | Plays when a Spirit Tree face uses a spit attack. | spirit\_tree\_face\_spit |
| https://the-betweenlands.fandom.com/wiki/File:Spirit\_tree\_face\_spit\_root\_spikes.ogg | Spirt Tree spits spikes | Hostile | Plays when the Spirt Tree spits root spikes. | spirit\_tree\_face\_spit\_root\_spikes |
| https://the-betweenlands.fandom.com/wiki/File:Spirit\_tree\_face\_suck.ogg | Spirt Tree inhales | Hostile | Plays before the Spirit Tree begins the root spike attack. | spirit\_tree\_face\_large\_suck |
| https://the-betweenlands.fandom.com/wiki/File:Spirit\_tree\_spike\_trap\_emerge.ogg | Spike trap emerges | Hostile | Plays when trapping the player in roots. | spirit\_tree\_spike\_trap\_emerge |
| https://the-betweenlands.fandom.com/wiki/File:Spirit\_tree\_spikes.ogg | Spikes shoot out | Hostile | Plays during the spike wave. | spirit\_tree\_spikes |

History
---------

* Release 3.5.5: Friendly Small Spirit Tree Faces can now be fed Compost to heal them and produce Sap Spit.
* Release 3.4.7: Small Spirit Tree Faces now no longer instantly despawn when collided with another entity or being in an invalid position; instead they drop to the ground and teleport to nearby Spirit Tree Logs if available.
* Release 3.4.0: Introduced.