# Loot Tables

The following is a list of most of the different **Loot Tables** used in the Betweenlands mod, including the items they can contain as well as their number of rolls, quantities, and weights.

Contents
--------

* 1 Explanation of Loot Tables
  + 1.1 Shared Loot
* 2 Animator
  + 2.1 fabricated\_scroll
  + 2.2 scroll
* 3 Entities
  + 3.1 anadia
  + 3.2 anadia\_head, anadia\_body, anadia\_tail, anadia\_treasure
  + 3.3 angler
  + 3.4 ash\_sprite
  + 3.5 barrishee
  + 3.6 blind\_cave\_fish
  + 3.7 blood\_snail
  + 3.8 boulder\_sprite
  + 3.9 bubbler\_crab\_trimming\_1, bubbler\_crab\_trimming\_2, bubbler\_crab\_trimming\_3
  + 3.10 chiromaw
  + 3.11 chiromaw\_hatchling
  + 3.12 chiromaw\_matriarch
  + 3.13 crypt\_crawler
  + 3.14 dark\_druid
  + 3.15 dragonfly
  + 3.16 dreadful\_peat\_mummy
  + 3.17 emberling
  + 3.18 emberling\_shaman
  + 3.19 firefly
  + 3.20 fortress\_boss
  + 3.21 frog
  + 3.22 gas\_cloud
  + 3.23 gecko
  + 3.24 greebling\_coracle
  + 3.25 greebling\_corpse
  + 3.26 jellyfish
  + 3.27 large\_sludge\_worm
  + 3.28 leech
  + 3.29 lurker
  + 3.30 mire\_snail
  + 3.31 mire\_snail\_egg
  + 3.32 moving\_spawner\_hole
  + 3.33 olm
  + 3.34 peat\_mummy
  + 3.35 pyrad
  + 3.36 rock\_snot
  + 3.37 root\_sprite
  + 3.38 shambler
  + 3.39 silt\_crab
  + 3.40 silt\_crab\_trimming\_1, silt\_crab\_trimming\_2, silt\_crab\_trimming\_3
  + 3.41 sludge
  + 3.42 sludge\_menace
  + 3.43 small\_sludge\_worm
  + 3.44 spirit\_tree\_face\_large
  + 3.45 spirit\_tree\_face\_small
  + 3.46 sporeling
  + 3.47 swamp\_hag
  + 3.48 tar\_beast
  + 3.49 tarminion
  + 3.50 termite
  + 3.51 tiny\_sludge\_worm
  + 3.52 tiny\_sludge\_worm\_helper
  + 3.53 toad
  + 3.54 wall\_lamprey
  + 3.55 wall\_living\_root
  + 3.56 wight
* 4 Loot
  + 4.1 cave\_pot
  + 4.2 chiromaw\_nest\_scattered\_loot
  + 4.3 cragrock\_tower\_chest
  + 4.4 cragrock\_tower\_pot
  + 4.5 deepman\_simulacrum\_offerings
  + 4.6 idol\_heads\_chest
  + 4.7 lake\_cavern\_simulacrum\_offerings
  + 4.8 marsh\_ruins\_pot
  + 4.9 music\_disc
  + 4.10 present\_loot
  + 4.11 puffshroom
  + 4.12 rootman\_simulacrum\_offerings
  + 4.13 sludge\_plains\_ruins\_urn
  + 4.14 sludge\_worm\_dungeon\_barrishee\_chest
  + 4.15 sludge\_worm\_dungeon\_chest
  + 4.16 sludge\_worm\_dungeon\_crypt\_urn
  + 4.17 sludge\_worm\_dungeon\_item\_shelf
  + 4.18 sludge\_worm\_dungeon\_urn
  + 4.19 spawner\_chest
  + 4.20 tar\_pool\_pot
  + 4.21 underground\_ruins\_pot
  + 4.22 wight\_fortress\_chest
  + 4.23 wight\_fortress\_pot
* 5 Unused
  + 5.1 common\_pot\_loot
  + 5.2 common\_chest\_loot
  + 5.3 dungeon\_pot\_loot
  + 5.4 dungeon\_chest\_loot
  + 5.5 shared\_loot\_pool\_test
* 6 History

Explanation of Loot Tables
----------------------------

There are several key terms used to determine items within a loot table.

* "**Rolls**" refers to the number of times an item type (usually from a selection of items) is called per inventory using the loot table.
* "**Quantity**" refers to the amount of the called item that can be found per roll, including minimum/maximum.
* "**Weight**" refers to how likely the item is to be called per roll when compared to the total weight of items in the selection (in general, the smaller the weight number, the rarer the item is).

### Shared Loot
Some loot pools also use a custom *Shared Loot* system that can determine guaranteed or minimum/maximum loot for an entire location.

* "**Shared Pools**" are where the items that can be shared per location are designated and pulled from. Rolls in Shared Pools apply to the collective inventories for an entire location that are using the same loot table, not for each individual inventory.
* From here, the shared items are called from somewhere else in the loot table. The rolls and weights listed in these selections are applied per inventory using the loot table, as with unshared items, but will consume a roll from the Shared Pool when the item is called. This means that while each inventory has its own chance to contain the item, there can only be as many appearances of the item per location as is designated by the Shared Pool.
  + Additionally, items can have a "**Guaranteed After**" condition, which means that if the item has not yet appeared in any other inventory upon checking a certain amount of inventories within each location (either a specific number or a percentage, inclusive), the current inventory will always contain the item (and pull a roll from the Shared Pool). This allows an entire location to be guaranteed to contain a specific item within one of its loot inventories.

See shared\_loot\_pool\_test for an example of a loot table with shared loot, or this GitHub issue for more detailed information regarding shared loot.

Animator
----------

These loot tables are used by Item Scrolls in the Animator to determine what random item they turn into.

### fabricated\_scroll
Used by Fabricated Scrolls in the Animator

| Fabricated Scroll Random Items | | |
| --- | --- | --- |
| **Random Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Item Scroll Loot** (see scroll) | 1 | 3/5 (60%) |
| **Loot Scraps** | 1-3 | 2/5 (40%) |

### scroll
Used by Item Scrolls in the Animator

| Item Scroll Random Items | | |
| --- | --- | --- |
| **Random Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Octine Ingot** | 5-12 | 20/193 (10.36%) |
| **Syrmorite Ingot** | 5-12 | 20/193 (10.36%) |
| **Skull Mask** | 1 | 16/193 (8.29%) |
| **Swift Pick** | 1 | 12/193 (6.22%) |
| **Wight's Bane** | 1 | 12/193 (6.22%) |
| **Hag Hacker** | 1 | 12/193 (6.22%) |
| **Critter Cruncher** | 1 | 12/193 (6.22%) |
| **Sludge Slicer** | 1 | 12/193 (6.22%) |
| **Valonite Shard** | 1-3 | 12/193 (6.22%) |
| **Voodoo Doll** | 1 | 10/193 (5.18%) |
| **Magic Item Magnet** | 1 | 10/193 (5.18%) |
| **Amulet Socket** | 1 | 10/193 (5.18%) |
| **Ring of Power** | 1 | 10/193 (5.18%) |
| **Staff of the Shadow Walker** | 1 | 10/193 (5.18%) |
| **Staff of the Mist Walker** | 1 | 10/193 (5.18%) |
| **Music Disc Loot** (see music\_disc) | 1 | 5/193 (2.59%) |

Entities
----------

These loot tables are used by entities, primarily Mobs, to determine their potential drops or other item-based factors.

### anadia
Used by Anadia

| Anadia Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll, if killed by player: | | |
| **Raw Anadia Meat** **( Cooked Anadia Meat if killed while on fire)** | 1 | 1/1 (100%) |

### anadia\_head, anadia\_body, anadia\_tail, anadia\_treasure
Used by Anadia items in the Trimming Table

| Anadia Trimming | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| *Based on Anadia body type*   1 Roll | | |
| If Skittish body type | | |
| **Raw Anadia Meat** **(Smoked Anadia Meat if Smoked)** | 1-5 (Based on Anadia size) | 1/3 (33%) |
| If Slender body type | | |
| **Raw Anadia Meat** | 1-5 (Based on Anadia Size) | 1/3 (33%) |
| If Stubby body type | | |
| **Raw Anadia Meat** **(Smoked Anadia Meat if Smoked)** | 1-5 (Based on Anadia size) | 1/3 (33%) |
| *Based on Anadia head type*   1 Roll | | |
| If Grazer head type | | |
| **Anadia Bones** | 1 | 1/3 (33%) |
| If Thumphead head type | | |
| **Anadia Eye** | 1 | 1/3 (33%) |
| If Prowler head type | | |
| **Anadia Gills** | 1 | 1/3 (33%) |
| *Based on Anadia tail type*   Roll 1 | | |
| If Cliptail type | | |
| **Anadia Scales** | 1 | 1/3 (33%) |
| If Fantail type | | |
| **Anadia Fins** | 1 | 1/3 (33%) |
| If Longtail type | | |
| **Anadia Swim Bladder** | 1 | 1/3 (33%) |
| Treasure Fish Loot   1 Roll | | |
| If Skittish body type | | |
| **Shimmerstone** | 1 | 1/40 (2.5%) |
| **Rubber Boots** | 1 | 2/40 (5%) |
| **Rocksnot Pearl** | 1-2 (Based on Anadia Size) | 3/40 (7.5%) |
| **Loot Scraps** | 1-2 (Based on Anadia Size) | 3/40 (7.5%) |
| **Syrmorite Nugget** | 2-4 (Based on Anadia Size) | 3/40 (7.5%) |
| **Fish Vortex Upgrade** | 1 | 2/40 (5%) |
| **Urchin Spike Upgrade** | 1 | 2/40 (5%) |
| If Slender body type | | |
| **Aqua Middle Gem** | 1 | 1/40 (2.5%) |
| **Crimson Middle Gem** | 1 | 1/40 (2.5%) |
| **Green Middle Gem** | 1 | 1/40 (2.5%) |
| **Rocksnot Pearl** | 2-3 (Based on Anadia size) | 1/40 (2.5%) |
| **Loot Scraps** | 1-2 (Based on Anadia size) | 1/40 (2.5%) |
| **Syrmorite Nugget** | 1-2 (Based on Anadia size) | 3/40 (7.5%) |
| **Glide Upgrade** | 1 | 2/40 (5%) |
| **Electric Upgrade** | 1 | 2/40 (5%) |
| If Stubby body type | | |
| **Valonite Splinter** | 2-4 (Based on Anadia size) | 1/40 (2.5%) |
| **Aqua Middle Gem** | 1-2 (Based on Anadia size) | 1/40 (2.5%) |
| **Green Middle Gem** | 1-2 (Based on Anadia size) | 1/40 (2.5%) |
| **Crimson Middle Gem** | 1-2 (Based on Anadia size) | 1/40 (2.5%) |
| **Rocksnot Pearl** | 2-4 (Based on Anadia size) | 1/40 (2.5%) |
| **Loot Scraps** | 1-3 | 2/40 (5%) |
| **Syrmorite Nugget** | 2-3 | 2/40 (5%) |
| **Ascent Upgrade** | 1 | 3/40 (7.5%) |

### angler
Used by Anglers

| Angler Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 0-1 Rolls, if killed by player: | | |
| **Angler Tooth** | 0-2 (+0-1 per Looting level) | 1/1 (100%) |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 8/11 (72.73%) |
| **Blue Candy** | 1 | 1/11 (9.09%) |
| **Red Candy** | 1 | 1/11 (9.09%) |
| **Yellow Candy** | 1 | 1/11 (9.09%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 4/5 (80%) |
| **Mince Pie** | 1 | 1/5 (20%) |

### ash\_sprite
Used by Ash Sprites

| Ash Sprite Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1-2 Rolls: | | |
| **Cremains** | 1-2 (+0-1 per Looting level) | 1/1 (100%) |

### barrishee
Used by the Barrishee

| Barrishee Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Rune Door Key** | 1 | 1/1 (100%) |
| 1 Roll: | | |
| **Life Crystal (64 charge)** | 1 | 3/7 (42.86%) |
| **Life Crystal (32 charge)** | 1 | 2/7 (28.57%) |
| **Life Crystal (88 charge)** | 1 | 1/7 (14.29%) |
| **Life Crystal (26 charge)** | 1 | 1/7 (14.29%) |

### blind\_cave\_fish
Used by Blind Cave Fish

*This loot table contains no content.*

### blood\_snail
Used by Blood Snails

| Blood Snail Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Raw Snail Flesh** **( Seared Snail Flesh if killed by fire)** | 0-1 (+0-1 per Looting level) | 1/1 (100%) |
| 1 Roll: | | |
| **Nothing** | N/A | 1/4 (25%) |
| **Crimson Snail Shell** | 1 | 2/4 (50%) |
| **Poison Gland** | 1 (+0-2 per Looting level) | 1/4 (25%) |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 8/11 (72.73%) |
| **Blue Candy** | 1 | 1/11 (9.09%) |
| **Red Candy** | 1 | 1/11 (9.09%) |
| **Yellow Candy** | 1 | 1/11 (9.09%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 4/5 (80%) |
| **Mince Pie** | 1 | 1/5 (20%) |

### boulder\_sprite
Used by Boulder Sprites

| Boulder Sprite Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll, if head has at least 2 stalactites: | | |
| **Stalactite** | 1 | 1/1 (100%) |
| 1 Roll, if head has at least 4 stalactites: | | |
| **Stalactite** | 1 | 1/1 (100%) |
| 1 Roll, if head has at least 6 stalactites: | | |
| **Stalactite** | 1 | 1/1 (100%) |
| 1 Roll, if head has at least 8 stalactites: | | |
| **Stalactite** | 1 | 1/1 (100%) |
| 1 Roll, if head has at least 10 stalactites: | | |
| **Stalactite** | 1 | 1/1 (100%) |
| 1 Roll, if head has at least 12 stalactites: | | |
| **Stalactite** | 1 | 1/1 (100%) |
| 1 Roll, if head has at least 14 stalactites: | | |
| **Stalactite** | 1 | 1/1 (100%) |
| 1 Roll, if head has at least 16 stalactites: | | |
| **Stalactite** | 1 | 1/1 (100%) |
| 1 Roll: | | |
| **Nothing** | N/A | 1/2 (50%) |
| **Angry Pebble** | 1 | 1/2 (50%) |
| 1-2 Rolls: | | |
| **Betweenstone** | 1 | 14/61 (22.95%) |
| **Sulfur Ore** | 1 | 12/61 (19.67%) |
| **Slimy Bone Ore** | 1 | 12/61 (19.67%) |
| **Syrmorite Ore** | 1 | 10/61 (16.39%) |
| **Octine Ore** | 1 | 7/61 (11.48%) |
| **Scabyst Ore** | 1 | 4/61 (6.56%) |
| **Valonite Ore** | 1 | 2/61 (3.28%) |

### bubbler\_crab\_trimming\_1, bubbler\_crab\_trimming\_2, bubbler\_crab\_trimming\_3
Used by Bubbler Crabs in the Trimming Table

| Crab Trimming Loot | | |
| --- | --- | --- |
| **Item** | **Quantity** | **Weight** |
| Slot 1, 1 Roll | | |
| **Crab Claw** | 1 | 1/1 (100%) |
| Slot 2, 1 Roll | | |
| **Crabstick** | 2 | 1/1 (100%) |
| Slot 3, 1 Roll | | |
| **Crab Claw** | 1 | 1/1 (100%) |

### chiromaw
Used by Chiromaws (untamed)

| Chiromaw Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Chiromaw Wing** | 0-1 (+0-1 per Looting level) | 1/1 (100%) |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 8/11 (72.73%) |
| **Blue Candy** | 1 | 1/11 (9.09%) |
| **Red Candy** | 1 | 1/11 (9.09%) |
| **Yellow Candy** | 1 | 1/11 (9.09%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 6/7 (85.71%) |
| **Mince Pie** | 1 | 1/7 (14.29%) |

### chiromaw\_hatchling
Used for feeding items to growing Chiromaw Hatchlings

| Chiromaw Hatchling Feeding Items | | |
| --- | --- | --- |
| **Feeding Item** | **Quantity** | **Weight** |
| 2 Rolls: | | |
| **Raw Anadia Meat** | 1 | 1/10 (10%) |
| **Silt Crab Claw** | 1 | 1/10 (10%) |
| **Dragonfly (item)** | 1 | 1/10 (10%) |
| **Dragonfly Wing** | 1 | 1/10 (10%) |
| **Firefly (item)** | 1 | 1/10 (10%) |
| **Raw Frog's Leg** | 1 | 1/10 (10%) |
| **Gecko (item)** | 1 | 1/10 (10%) |
| **Lurker Skin** | 1 | 1/10 (10%) |
| **Mire Snail Egg (item)** | 1 | 1/10 (10%) |
| **Raw Snail Flesh** | 1 | 1/10 (10%) |

### chiromaw\_matriarch
Used by the Chiromaw Matriarch

| Chiromaw Matriarch Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Chirobarb Erupter** | 1 | 1/1 (100%) |
| 1 Roll: | | |
| **Chiromaw Barb** | 5-10 | 1/1 (100%) |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 6/9 (66.67%) |
| **Blue Candy** | 1 | 1/9 (11.11%) |
| **Red Candy** | 1 | 1/9 (11.11%) |
| **Yellow Candy** | 1 | 1/9 (11.11%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 1/2 (50%) |
| **Mince Pie** | 1 | 1/2 (50%) |

### crypt\_crawler
Used by Crypt Crawlers

| Crypt Crawler Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Reed Rope** | 1 | 35/102 (34.31%) |
| **Syrmorite Nugget** | 1 | 15/102 (14.71%) |
| **Octine Nugget** | 1 | 13/102 (12.75%) |
| **Dragonfly Wing** | 1 | 10/102 (9.8%) |
| **Amate Paper** | 1 | 10/102 (9.8%) |
| **Lurker Skin** | 1 | 10/102 (9.8%) |
| **Reed Donut** | 1 | 5/102 (4.9%) |
| **Tar Drip** | 1 | 3/102 (2.94%) |
| **Valonite Splinter** | 1 | 1/102 (0.98%) |
| 1 Roll: | | |
| **Ancient Remnant** | 1-3 | 1/2 (50%) |
| **Nothing** | N/A | 1/2 (50%) |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 6/9 (66.67%) |
| **Blue Candy** | 1 | 1/9 (11.11%) |
| **Red Candy** | 1 | 1/9 (11.11%) |
| **Yellow Candy** | 1 | 1/9 (11.11%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 1/2 (50%) |
| **Mince Pie** | 1 | 1/2 (50%) |

### dark\_druid
Used by Dark Druids

| Dark Druid Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 0-1 Rolls: | | |
| **Swamp Talisman Piece** | 1 | 1/5 (20%) (if no duplicates in inventory *or* not killed by player) |
| **Swamp Talisman Piece** | 1 | 1/5 (20%) (if no duplicates in inventory *or* not killed by player) |
| **Swamp Talisman Piece** | 1 | 1/5 (20%) (if no duplicates in inventory *or* not killed by player) |
| **Swamp Talisman Piece** | 1 | 1/5 (20%) (if no duplicates in inventory *or* not killed by player) |
| **Any Swamp Talisman Piece** | 1 | 1/5 (20%) (if all pieces *are* in inventory) |

### dragonfly
Used by Dragonflies

| Dragonfly Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1-2 Rolls: | | |
| **Dragonfly Wing** | 1-2 (+0-1 per Looting level) | 1/1 (100%) |

### dreadful\_peat\_mummy
Used by the Dreadful Peat Mummy

| Dreadful Peat Mummy Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Ring of Summoning** | 1 | 1/1 (100%) |
| 1 Roll: | | |
| **Amulet Slot** | 1 | 1/1 (100%) |
| 3-6 Rolls: | | |
| **Shimmerstone** | 1 | 1/1 (100%) |
| 8 Rolls, if killed by player, Spook event only: | | |
| **Blue Candy** | 1 | 1/3 (33.33%) |
| **Red Candy** | 1 | 1/3 (33.33%) |
| **Yellow Candy** | 1 | 1/3 (33.33%) |
| 6 Rolls, if killed by player, Winter event only: | | |
| **Mince Pie** | 1 | 1/1 (100%) |

### emberling
Used by Emberlings

| Emberling Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Octine Nugget** | 1 (+1-3 per Looting level) | 1/1 (100%) |
| 1-2 Rolls, if killed by player: | | |
| **Undying Embers** | 0-1 (+0-1 per Looting level) | 1/1 (100%) |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 8/11 (72.73%) |
| **Blue Candy** | 1 | 1/11 (9.09%) |
| **Red Candy** | 1 | 1/11 (9.09%) |
| **Yellow Candy** | 1 | 1/11 (9.09%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 3/4 (75%) |
| **Mince Pie** | 1 | 1/4 (25%) |

### emberling\_shaman
Used by Emberling Shamans

| Emberling Shaman Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1-2 Rolls: | | |
| **Undying Embers** | 1-2 (+0-1 per Looting level) | 1/1 (100%) |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 8/11 (72.73%) |
| **Blue Candy** | 1 | 1/11 (9.09%) |
| **Red Candy** | 1 | 1/11 (9.09%) |
| **Yellow Candy** | 1 | 1/11 (9.09%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 3/4 (75%) |
| **Mince Pie** | 1 | 1/4 (25%) |

### firefly
Used by Fireflies

*This loot table contains no content.*

### fortress\_boss
Used by the Primordial Malevolence

| Primordial Malevolence Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Ring of Recruitment** | 1 | 1/1 (100%) |
| 1 Roll: | | |
| **Amulet Slot** | 1 | 1/1 (100%) |
| 8 Rolls, if killed by player, Spook event only: | | |
| **Blue Candy** | 1 | 1/3 (33.33%) |
| **Red Candy** | 1 | 1/3 (33.33%) |
| **Yellow Candy** | 1 | 1/3 (33.33%) |
| 6 Rolls, if killed by player, Winter event only: | | |
| **Mince Pie** | 1 | 1/1 (100%) |

### frog
Used by Frogs

| Frog Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Raw Frog's Leg** **( Fried Frog's Leg if killed by fire)** | 1-2 (+0-1 per Looting level) | 1/1 (100%) |
| 1 Roll: | | |
| **Poison Gland** | 1 (+0-2 per Looting level) | 1/1 (100%) (poison variant only) |

### gas\_cloud
Used by Shallowbreaths

| Shallowbreath Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 6/9 (66.67%) |
| **Blue Candy** | 1 | 1/9 (11.11%) |
| **Red Candy** | 1 | 1/9 (11.11%) |
| **Yellow Candy** | 1 | 1/9 (11.11%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 4/5 (80%) |
| **Mince Pie** | 1 | 1/5 (20%) |

### gecko
Used by Geckos

*This loot table contains no content.*

### greebling\_coracle
Used for looting Greebling Coracles

| Greebling Coracle Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Raw Anadia Meat** | 1 | 2/12 (0.17%) |
| **Tiny Sludge Worm** | 1 | 2/12 (0.17%) |
| **Anadia Bones** | 1 | 2/12 (0.17%) |
| **Anadia Remains** | 1 | 2/12 (0.17%) |
| **Anadia** | 1 | 2/12 (0.17%) |
| **Rotten Anadia** | 1 | 1/12 (0.08%) |
| **Treasure Anadia** | 1 | 1/12 (0.08%) |
| 1 Roll: | | |
| **Angler Tooth** | 1 | 1/6 (0.17%) |
| **Lurker Skin** | 1 | 1/6 (0.17%) |
| **Swamp Kelp** | 1-3 | 1/6 (0.17%) |
| **Reed Rope** | 1-3 | 1/6 (0.17%) |
| **Algae Clump** | 1-3 | 1/6 (0.17%) |
| **Water Weeds** | 1-3 | 1/6 (0.17%) |
| 0-1 Rolls: | | |
| **Net** | 1 | 4/17 (0.24%) |
| **Fishing Float** | 1 | 4/17 (0.24%) |
| **Weedwood Bowl** | 1 | 4/ 17(0.24%) |
| **Amate Map** | 1 | 2/17 (0.12%) |
| **Fishing Spear** | 1 | 1/17 (0.06%) |
| **Amphibious Fishing Spear** | 1 | 1/17 (0.06%) |
| **Fabricated Scroll** | 1 | 1/17 (0.06%) |

### greebling\_corpse
Used for looting Greebling Corpses

| Greebling Corpse Loot Items | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 2 Rolls: | | |
| **Betweenstone Pebble** | 1-5 | 10/104 (9.62%) |
| **Reed Rope** | 1-2 | 10/104 (9.62%) |
| **Weedwood Stick** | 1-3 | 10/104 (9.62%) |
| **Raw Anadia Meat** | 1 | 8/104 (7.69%) |
| **Silt Crab Claw** | 1 | 8/104 (7.69%) |
| **Dragonfly Wing** | 1 | 8/104 (7.69%) |
| **Raw Frog's Leg** | 1 | 8/104 (7.69%) |
| **Lurker Skin** | 1 | 8/104 (7.69%) |
| **Raw Snail Flesh** | 1 | 8/104 (7.69%) |
| **Amate Paper** | 1-3 | 5/104 (4.81%) |
| **Dragonfly (item)** | 1 | 4/104 (3.85%) |
| **Firefly (item)** | 1 | 4/104 (3.85%) |
| **Gecko (item)** | 1 | 4/104 (3.85%) |
| **Mire Snail Egg (item)** | 1 | 4/104 (3.85%) |
| **Net** | 1 | 2/104 (1.92%) |
| **Amate Map** | 1 | 1/104 (0.96%) |
| **Simple Slingshot** | 1 | 1/104 (0.96%) |
| **Fabricated Scroll** | 1 | 1/104 (0.96%) |

### jellyfish
Used by Jellyfish and Cave Jellyfish
Template:Loot/jellyfish

### large\_sludge\_worm
Used by Large Sludge Worms

| Large Sludge Worm Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1-3 Rolls: | | |
| **Sludge Ball** | 1-3 | 8/16 (50%) |
| **Slimy Bone** | 1-2 | 6/16 (37.5%) |
| **Sludge Jello** | 1 | 2/16 (12.5%) |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 6/9 (66.67%) |
| **Blue Candy** | 1 | 1/9 (11.11%) |
| **Red Candy** | 1 | 1/9 (11.11%) |
| **Yellow Candy** | 1 | 1/9 (11.11%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 1/2 (50%) |
| **Mince Pie** | 1 | 1/2 (50%) |

### leech
Used by Leeches

| Leech Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 0-1 Rolls: | | |
| **Ball of Sap** | 1 (+0-1 per Looting level) | 1/1 (100%) |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 8/11 (72.73%) |
| **Blue Candy** | 1 | 1/11 (9.09%) |
| **Red Candy** | 1 | 1/11 (9.09%) |
| **Yellow Candy** | 1 | 1/11 (9.09%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 3/4 (75%) |
| **Mince Pie** | 1 | 1/4 (25%) |

### lurker
Used by Lurkers

| Lurker Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll, if killed by player: | | |
| **Lurker Skin** | 1-3 (+0-1 per Looting level) | 1/1 (100%) |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 6/9 (66.67%) |
| **Blue Candy** | 1 | 1/9 (11.11%) |
| **Red Candy** | 1 | 1/9 (11.11%) |
| **Yellow Candy** | 1 | 1/9 (11.11%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 1/2 (50%) |
| **Mince Pie** | 1 | 1/2 (50%) |

### mire\_snail
Used by Mire Snails

| Mire Snail Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Raw Snail Flesh** **( Seared Snail Flesh if killed by fire)** | 1-2 (+0-1 per Looting level) | 1/1 (100%) |
| 0-1 Rolls: | | |
| **Ochre Snail Shell** | 1 | 1/1 (100%) |

### mire\_snail\_egg
Used by Mire Snail Eggs

*This loot table contains no content.*

### moving\_spawner\_hole
Used by Worm Holes

| Worm Hole Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Nothing** | N/A | 2/3 (66.67%) |
| **Sludge Worm Egg Sac (item)** | 1 | 1/3 (33.33%) |

### olm
Used by Olms

*This loot table contains no content.*

### peat\_mummy
Used by Peat Mummies

| Peat Mummy Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll, if killed by player and *not* summoned by boss: | | |
| **Nothing** | N/A | 8/15 (53.33%) |
| **Shimmerstone** | 1 | 6/15 (40%) |
| **Shimmerstone** | 2-5 | 1/15 (6.67%) |
| 1 Roll, if collected Shimmerstone and *not* summoned by boss: | | |
| **Nothing** | N/A | 1/10 (10%) |
| **Shimmerstone** | 1 | 9/10 (90%) |
| 3 Rolls, if killed by player, Spook event only: | | |
| **Blue Candy** | 1 | 1/3 (33.33%) |
| **Red Candy** | 1 | 1/3 (33.33%) |
| **Yellow Candy** | 1 | 1/3 (33.33%) |
| 3 Rolls, if killed by player, Winter event only: | | |
| **Mince Pie** | 1 | 1/1 (100%) |

### pyrad
Used by Pyrads

| Pyrad Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Sulfur** | 1 (+1-3 per Looting level) | 1/1 (100%) |
| 1-3 Rolls: | | |
| **Tangled Root** | 1 (+0-2 per Looting level) | 1/1 (100%) |
| 1 Roll, if killed by player while charging attack: | | |
| **Nothing** | N/A | 3/4 (75%) |
| **Pyrad Flame** | 1-6 | 1/4 (25%) |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 3/6 (50%) |
| **Blue Candy** | 1 | 1/6 (16.67%) |
| **Red Candy** | 1 | 1/6 (16.67%) |
| **Yellow Candy** | 1 | 1/6 (16.67%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 1/2 (50%) |
| **Mince Pie** | 1 | 1/2 (50%) |

### rock\_snot
Used by Rock Snots

| Rock Snot Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Snot** | 1 (+0-1 per looting level) | 1/1 (100%) |
| 1 Roll: | | |
| **Rocksnot Pearl** | 1 (+0-2 per looting level) | 1/21 (4.76%) |
| **Nothing** | N/A | 20/21 (95.23%) |
| 1 Roll, if placed by player: | | |
| **Rocksnot Pod** | 1 | 1/1 (100%) |

### root\_sprite
Used by Root Sprites

| Root Sprite Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Root Pod** | 1 | 1/1 (100%) |
| 1 Roll: | | |
| **Nothing** | N/A | 2/3 (66.67%) |
| **Root Pod** | 1 | 1/3 (33.33%) |
| 1 Roll: | | |
| **Nothing** | N/A | 14/33 (42.42%) |
| **Most Plant Items** | 1 | 14/33 (42.42%) |
| **White Pear Seeds** | 1 | 4/33 (12.12%) |
| **Aspectrus Seeds** | 1 | 1/33 (3.03%) |

### shambler
Used by Shamblers

| Shambler Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Shambler Tongue** | 0-1 (+0-1 per Looting level) | 1/1 (100%) |

### silt\_crab
Used by Silt Crabs

| Silt Crab Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Crab Claw** | 1-2 (+0-1 per Looting level) | 1/1 (100%) |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 10/13 (76.92%) |
| **Blue Candy** | 1 | 1/13 (7.69%) |
| **Red Candy** | 1 | 1/13 (7.69%) |
| **Yellow Candy** | 1 | 1/13 (7.69%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 5/6 (83.33%) |
| **Mince Pie** | 1 | 1/6 (16.67%) |

### silt\_crab\_trimming\_1, silt\_crab\_trimming\_2, silt\_crab\_trimming\_3
Used by Silt Crabs in the Trimming Table

| Crab Trimming Loot | | |
| --- | --- | --- |
| **Item** | **Quantity** | **Weight** |
| Slot 1, 1 Roll | | |
| **Crab Claw** | 1 | 1/1 (100%) |
| Slot 2, 1 Roll | | |
| **Crabstick** | 2 | 1/1 (100%) |
| Slot 3, 1 Roll | | |
| **Crab Claw** | 1 | 1/1 (100%) |

### sludge
Used by Sludges and Smol Sludges

| Sludge and Smol Sludge Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 0-2 Rolls: | | |
| **Sludge Ball** | 1 (+0-1 per Looting level) | 1/1 (100%) |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 8/11 (72.73%) |
| **Blue Candy** | 1 | 1/11 (9.09%) |
| **Red Candy** | 1 | 1/11 (9.09%) |
| **Yellow Candy** | 1 | 1/11 (9.09%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 5/6 (83.33%) |
| **Mince Pie** | 1 | 1/6 (16.67%) |

### sludge\_menace
Used by the Sludge Menace

| Sludge Menace Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Ring of Dispersion** | 1 | 1/1 (100%) |
| 1 Roll: | | |
| **Amulet Slot** | 1 | 1/1 (100%) |
| 8 Rolls, if killed by player, Spook event only: | | |
| **Blue Candy** | 1 | 1/3 (33.33%) |
| **Red Candy** | 1 | 1/3 (33.33%) |
| **Yellow Candy** | 1 | 1/3 (33.33%) |
| 6 Rolls, if killed by player, Winter event only: | | |
| **Mince Pie** | 1 | 1/1 (100%) |

### small\_sludge\_worm
Used by Small Sludge Worms

| Small Sludge Worm Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 0-1 Rolls: | | |
| **Sludge Ball** | 1 (+0-1 per Looting level) | 1/1 (100%) |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 8/11 (72.73%) |
| **Blue Candy** | 1 | 1/11 (9.09%) |
| **Red Candy** | 1 | 1/11 (9.09%) |
| **Yellow Candy** | 1 | 1/11 (9.09%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 3/4 (75%) |
| **Mince Pie** | 1 | 1/4 (25%) |

### spirit\_tree\_face\_large
Used by the Large Spirit Tree Face of a Spirit Tree

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

### spirit\_tree\_face\_small
Used by the Small Spirit Tree Faces of a Spirit Tree

| Small Spirit Tree Face Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Nothing** | N/A | 2/3 (66.67%) |
| **Sap Spit** | 1 (+0-1 per Looting level) | 1/3 (33.33%) |
| 1 Roll: | | |
| **Nothing** | N/A | 8/9 (88.89%) |
| **Small Spirit Tree Face Mask** | 1 | 1/9 (11.11%) |

### sporeling
Used by Sporelings

| Sporeling Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 0-2 Rolls: | | |
| **Spores** | 1 (+0-1 per Looting level) | 1/1 (100%) |

### swamp\_hag
Used by Swamp Hags

| Swamp Hag Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Slimy Bone** | 1-2 (+0-1 per Looting level) | 1/1 (100%) |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 3/6 (50%) |
| **Blue Candy** | 1 | 1/6 (16.67%) |
| **Red Candy** | 1 | 1/6 (16.67%) |
| **Yellow Candy** | 1 | 1/6 (16.67%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 2/3 (66.67%) |
| **Mince Pie** | 1 | 1/3 (33.33%) |

### tar\_beast
Used by Tar Beasts

| Tar Beast Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Tar Beast Heart** | 1 | 1/9 (11.11%) (if killed by player) |
| **Tar Drip** | 1-2 (+1-2 per Looting level) | 8/9 (88.89%) |
| 3 Rolls, if killed by player, Spook event only: | | |
| **Blue Candy** | 1 | 1/3 (33.33%) |
| **Red Candy** | 1 | 1/3 (33.33%) |
| **Yellow Candy** | 1 | 1/3 (33.33%) |
| 3 Rolls, if killed by player, Winter event only: | | |
| **Mince Pie** | 1 | 1/1 (100%) |

### tarminion
Used by Tarminions

| Tarminion Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Inanimate Tarminion** | 1 | 1/1 (100%) |

### termite
Used by Termites

| Termite Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 10/13 (76.92%) |
| **Blue Candy** | 1 | 1/13 (7.69%) |
| **Red Candy** | 1 | 1/13 (7.69%) |
| **Yellow Candy** | 1 | 1/13 (7.69%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 6/7 (85.71%) |
| **Mince Pie** | 1 | 1/7 (14.29%) |

### tiny\_sludge\_worm
Used by Tiny Sludge Worms

| Tiny Sludge Worm Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll, if squashed: | | |
| **Nothing** | N/A | 50/51 (98.04%) |
| **Valonite Splinter** | 1 | 1/51 (1.96%) |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 8/11 (72.73%) |
| **Blue Candy** | 1 | 1/11 (9.09%) |
| **Red Candy** | 1 | 1/11 (9.09%) |
| **Yellow Candy** | 1 | 1/11 (9.09%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 3/4 (75%) |
| **Mince Pie** | 1 | 1/4 (25%) |

### tiny\_sludge\_worm\_helper
Used by Tiny Sludge Worm Helpers

*This loot table contains no content.*

### toad
Used by Harlequin Toads

*This loot table contains no content.*

### wall\_lamprey
Used by Lampreys

*This loot table contains no content.*

### wall\_living\_root
Used by Living Roots

*This loot table contains no content.*

### wight
Used by Wights

| Wight Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll, if killed by player: | | |
| **Nothing** | N/A | 2/3 (66.67%) |
| **Wight's Heart** | 1 (+0-1 per Looting level) | 1/3 (33.33%) |
| 2 Rolls, if killed by player, Spook event only: | | |
| **Nothing** | N/A | 1/4 (25%) |
| **Blue Candy** | 1 | 1/4 (25%) |
| **Red Candy** | 1 | 1/4 (25%) |
| **Yellow Candy** | 1 | 1/4 (25%) |
| 1 Roll, if killed by player, Winter event only: | | |
| **Nothing** | N/A | 1/2 (50%) |
| **Mince Pie** | 1 | 1/2 (50%) |

Loot
------

These loot tables are used by blocks, primarily Pots, Urns, and Chests, to determine their random loot.

### cave\_pot
Used by Pots in the Cavern and Lake Cavern layers

| Cave Pot drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1-2 Rolls: | | |
| **Reed Rope** | 1-3 | 45/233 (19.31%) |
| **Sulfur** | 2-4 | 40/233 (17.17%) |
| **Ball of Sap** | 1-4 | 26/233 (11.16%) |
| **Green Dentrothyst Shard** | 1-3 | 10/233 (4.29%) |
| **Orange Dentrothyst Shard** | 1-3 | 4/233 (1.72%) |
| **Lurker Skin** | 1-2 | 12/233 (5.15%) |
| **Angler Tooth Arrow** | 1-4 | 12/233 (5.15%) |
| **Syrmorite Nugget** | 1-4 | 11/233 (4.72%) |
| **Octine Nugget** | 1-4 | 11/233 (4.72%) |
| **Item Scroll** | 1 | 8/233 (3.43%) |
| **Poisoned Angler Tooth Arrow** | 1-4 | 7/233 (3.004%) |
| **Octine Arrow** | 1-4 | 7/233 (3.004%) |
| **Wight's Heart** | 1 | 6/233 (2.58%) |
| **Basilisk Arrow** | 1-4 | 4/233 (1.72%) |
| **Shock Arrow** | 1-4 | 4/233 (1.72%) |
| **Weeping Blue Petal** | 1 | 6/233 (2.58%) |
| **Valonite Splinter** | 1-2 | 3/233 (1.29%) |
| **Amulet Socket** | 1 | 2/233 (0.86%) |
| **Lore Scrap** | 0-2 | 5/233 (2.15%) |
| **Aspectrus Seeds** | 1-2 | 4/233 (1.72%) |
| **Bone Wayfinder** | 1 | 6/233 (2.58%) |

### chiromaw\_nest\_scattered\_loot
Used for scattered items found in Chiromaw Matriarch Nests

| Scattered Chiromaw Nest Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 2 Rolls: | | |
| **Crimson Middle Gem** | 1 | 1/40 (2.5%) |
| **Aqua Middle Gem** | 1 | 1/40 (2.5%) |
| **Green Middle Gem** | 1 | 1/40 (2.5%) |
| **Chiromaw Barb** | 1 | 8/40 (20%) |
| **Valonite Shard** | 1 | 2/40 (5%) |
| **Syrmorite Nugget** | 1 | 5/40 (12.5%) |
| **Octine Nugget** | 1 | 5/40 (12.5%) |
| **Valonite Splinter** | 1 | 5/40 (12.5%) |
| **Green Dentrothyst Vial** | 0-1 | 1/40 (2.5%) |
| **Orange Dentrothyst Vial** | 1 | 1/40 (2.5%) |
| **Green Dentrothyst Shard** | 1 | 5/40 (12.5%) |
| **Orange Dentrothyst Shard** | 1 | 5/40 (12.5%) |

### cragrock\_tower\_chest
Used by Chests in Cragrock Towers

| Cragrock Tower Chest | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| *Shared Pool*  0-1 Rolls per location: | | |
| **Explorer's Entries: The Tower** | 1 | 1/1 (100%) |
| 1 Roll per inventory: | | |
| **Nothing** | N/A | 4/5 (80%) |
| **Exporer's Entries: The Tower** | 1 | 1/5 (20%) |
| *Shared Pool*  1 Roll (+0-1 Bonus Rolls) per location | | |
| **Gem Singer** | 1 | 1/1 (100%) |
| *Shared Pool*  1 Roll per location: | | |
| **Ring of Ascent** | 1 | 1/1 (100%) |
| *Shared Pool*  1 Roll per location: | | |
| **Ring of Power** | 1 | 1/1 (100%) |
| *Shared Pool*  1 Roll per location: | | |
| **Wight's Bane** | 1 | 1/1 (100%) |
| *Shared Pool*  1 Roll per location: | | |
| **Critter Cruncher** | 1 | 1/1 (100%) |
| *Shared Pool*  1 Roll per location: | | |
| **Sludge Slicer** | 1 | 1/1 (100%) |
| *Shared Pool*  1 Roll per location: | | |
| **Hag Hacker** | 1 | 1/1 (100%) |
| *Shared Pool*  1 Roll per location: | | |
| **Forbidden Fig** | 1 | 1/1 (100%) |
| *Shared Pool*  1 Roll per location: | | |
| **Explorer's Hat** | 1 | 1/1 (100%) |
| *Shared Pool*  1 Roll per location: | | |
| **Swift Pick** | 1 | 1/1 (100%) |
| 0-1 Rolls per inventory: | | |
| **Nothing** | N/A | 1/2 (50%) |
| **Gem Singer** (from shared pool) | 1 | 1/2 (50%) |
| 2-3 Rolls (+1-2 Bonus Rolls): | | |
| **Nothing** | N/A | 100/182 (54.95%) |
| **Ring of Ascent** (from shared pool) | 1 | 4/182 (2.2%) |
| **Ring of Power** (from shared pool) | 1 | 4/182 (2.2%) |
| **Forbidden Fig** (from shared pool) | 1 | 5/182 (2.75%) |
| **Explorer's Hat** (from shared pool) | 1 | 4/182 (2.2%) |
| **Swift Pick** (from shared pool) | 1 | 6/182 (3.3%) |
| **Wight's Bane** (from shared pool) | 1 | 8/182 (4.4%) |
| **Critter Cruncher** (from shared pool) | 1 | 10/182 (5.49%) |
| **Hag Hacker** (from shared pool) | 1 | 10/182 (5.49%) |
| **Sludge Slicer** (from shared pool) | 1 | 8/182 (4.4%) |
| **Aspectrus Seeds** | 1 | 10/182 (5.49%) |
| **Life Crystal Fragment** | 1 | 8/182 (4.4%) |
| **Music Discs** (see music\_disc) | 1 | 5/182 (2.75%) |
| 4-6 Rolls (+1-2 Bonus Rolls): | | |
| **Nothing** | N/A | 20/176 (11.36%) |
| **Amulet Socket** | 1 | 22/176 (12.5%) |
| **Item Scroll** | 1 | 24/176 (13.64%) |
| **Wight's Heart** | 1-2 | 20/176 (11.36%) |
| **Angry Pebble** | 1-3 | 20/176 (11.36%) |
| **Bone Wayfinder** | 1 | 15/176 (8.52%) |
| **Valonite Splinter** | 2-4 | 15/176 (8.52%) |
| **Octine Ingot** | 1-2 | 10/176 (5.68%) |
| **Syrmorite Ingot** | 1-2 | 10/176 (5.68%) |
| **Valonite Shard** | 1-2 | 10/176 (5.68%) |
| **Orange Dentrothyst Shard** | 1-4 | 10/176 (5.68%) |
| 6-10 Rolls (+1-2 Bonus Rolls): | | |
| **Green Marshmallow** | 1 | 26/230 (11.3%) |
| **Pink Marshmallow** | 1 | 26/230 (11.3%) |
| **Lurker Skin** | 1-2 | 20/230 (8.7%) |
| **Angler Tooth Arrow** | 12-16 | 20/230 (8.7%) |
| **Syrmorite Nugget** | 4-10 | 15/230 (6.52%) |
| **Octine Nugget** | 4-10 | 15/230 (6.52%) |
| **Reed Donut** | 1-3 | 24/230 (10.43%) |
| **Jam Donut** | 1-2 | 26/230 (11.3%) |
| **Ball of Sap** | 4-12 | 28/230 (12.17%) |
| **Weeping Blue Petal** | 1-2 | 15/230 (6.52%) |
| **Green Dentrothyst Shard** | 1-4 | 15/230 (6.52%) |
| 5-6 Rolls (+1-2 Bonus Rolls): | | |
| **Sulfur** | 6-12 | 10/20 (50%) |
| **Reed Rope** | 4-8 | 10/20 (50%) |

### cragrock\_tower\_pot
Used by Pots in Cragrock Towers

| Cragrock Tower Pot | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| *Shared Pool* 1 Roll per location: | | |
| **Explorer's Entries: The Tower** | 1 | 1/1 (100%) |
| 1 Roll per inventory: | | |
| **Nothing** | N/A | 9/10 (90%) |
| **Explorer's Entries: The Tower** (from shared pool) | 1 | 1/10 (10%) (guaranteed after looting 50% of inventories per location) |
| 1-2 Rolls: | | |
| **Amulet Socket** | 1 | 15/530 (2.83%) |
| **Item Scroll** | 1-3 | 29/530 (5.47%) |
| **Wight's Heart** | 1-3 | 20/530 (3.77%) |
| **Angry Pebble** | 1-3 | 17/530 (3.21%) |
| **Valonite Splinter** | 2-5 | 20/530 (3.77%) |
| **Valonite Shard** | 1-3 | 15/530 (2.83%) |
| **Orange Dentrothyst Shard** | 1-3 | 15/530 (2.83%) |
| **Green Marshmallow** | 1-3 | 31/530 (5.85%) |
| **Pink Marshmallow** | 1-3 | 31/530 (5.85%) |
| **Lurker Skin** | 1-3 | 25/530 (4.72%) |
| **Angler Tooth Arrow** | 13-20 | 25/530 (4.72%) |
| **Basilisk Arrow** | 1-2 | 12/530 (2.26%) |
| **Shock Arrow** | 1-2 | 12/530 (2.26%) |
| **Octine Arrow** | 7-14 | 20/530 (3.77%) |
| **Syrmorite Nugget** | 7-16 | 20/530 (3.77%) |
| **Octine Nugget** | 7-16 | 20/530 (3.77%) |
| **Reed Donut** | 4-9 | 20/530 (3.77%) |
| **Jam Donut** | 4-8 | 31/530 (5.85%) |
| **Ball of Sap** | 7-18 | 33/530 (6.23%) |
| **Weeping Blue Petal** | 4-8 | 20/530 (3.77%) |
| **Green Dentrothyst Shard** | 4-10 | 20/530 (3.77%) |
| **Sulfur** | 13-22 | 25/530 (4.72%) |
| **Reed Rope** | 11-18 | 35/530 (6.6%) |

### deepman\_simulacrum\_offerings
Used by Offering Tables found next to Deepman Simulacra

| Simulacrum Offerings | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Ball of Sap** | 1 | 1/7 (14.29%) |
| **Reed Donut** | 1 | 1/7 (14.29%) |
| **Jam Donut** | 1 | 1/7 (14.29%) |
| **White Pear** | 1 | 1/7 (14.29%) |
| **Weeping Blue Petal** | 1 | 1/7 (14.29%) |
| **Forbidden Fig** | 1 | 1/7 (14.29%) |
| **Spirit Fruit** | 1 | 1/7 (14.29%) |

### idol\_heads\_chest
Used by Chests in Idol Head Statues

| Idol Head Chest | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 6-8 Rolls (+1-2 Bonus Rolls): | | |
| **Pink Marshmallow** | 1 | 24/383 (6.27%) |
| **Lurker Skin** | 1-2 | 20/383 (5.22%) |
| **Sulfur** | 8-16 | 20/383 (5.22%) |
| **Reed Rope** | 1-3 | 20/383 (5.22%) |
| **Angler Tooth Arrow** | 4-8 | 20/383 (5.22%) |
| **Syrmorite Nugget** | 4-16 | 25/383 (6.53%) |
| **Octine Nugget** | 4-16 | 25/383 (6.53%) |
| **Green Marshmallow** | 1 | 24/383 (6.27%) |
| **Reed Donut** | 1-2 | 18/383 (4.7%) |
| **Jam Donut** | 1 | 18/383 (4.7%) |
| **Amulet Socket** | 1 | 15/383 (3.92%) |
| **Item Scroll** | 1 | 16/383 (4.18%) |
| **Ball of Sap** | 2-8 | 18/383 (4.7%) |
| **Poisoned Angler Tooth Arrow** | 4-8 | 13/383 (3.39%) |
| **Wight's Heart** | 1-2 | 12/383 (3.13%) |
| **Weeping Blue Petal** | 1-3 | 11/383 (2.87%) |
| **Octine Arrow** | 4-8 | 11/383 (2.87%) |
| **Basilisk Arrow** | 1-3 | 6/383 (1.57%) |
| **Shock Arrow** | 1-3 | 6/383 (1.57%) |
| **Syrmorite Ingot** | 1-2 | 15/383 (3.92%) |
| **Octine Ingot** | 1-2 | 15/383 (3.92%) |
| **Angry Pebble** | 1-3 | 10/383 (2.61%) |
| **Bone Wayfinder** | 1 | 10/383 (2.61%) |
| **Valonite Splinter** | 1-4 | 8/383 (2.09%) |
| **Lore Scrap** | 1 | 8/383 (2.09%) |
| **Explorer's Entries: Idol Heads** | 1 | 10/383 (2.61%) |
| **Valonite Shard** | 1 | 6/383 (1.57%) |
| **Explorer's Hat** | 1 | 4/383 (1.04%) |

### lake\_cavern\_simulacrum\_offerings
Used by Offering Tables found next to Lake Cavern Simulacra

| Simulacrum Offerings | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Ball of Sap** | 1 | 1/7 (14.29%) |
| **Reed Donut** | 1 | 1/7 (14.29%) |
| **Jam Donut** | 1 | 1/7 (14.29%) |
| **White Pear** | 1 | 1/7 (14.29%) |
| **Weeping Blue Petal** | 1 | 1/7 (14.29%) |
| **Forbidden Fig** | 1 | 1/7 (14.29%) |
| **Spirit Fruit** | 1 | 1/7 (14.29%) |

### marsh\_ruins\_pot
Used by Pots in Marsh Ruins

| Marsh Ruins Pot | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1-2 Rolls: | | |
| **Reed Rope** | 1-3 | 40/277 (14.44%) |
| **Sulfur** | 2-4 | 35/277 (12.64%) |
| **Ball of Sap** | 2-6 | 26/277 (9.39%) |
| **Green Dentrothyst Shard** | 1-3 | 16/277 (5.78%) |
| **Orange Dentrothyst Shard** | 1-3 | 10/277 (3.61%) |
| **Lurker Skin** | 1-3 | 12/277 (4.33%) |
| **Angler Tooth Arrow** | 2-8 | 16/277 (5.78%) |
| **Syrmorite Nugget** | 2-8 | 12/277 (4.33%) |
| **Octine Nugget** | 2-8 | 12/277 (4.33%) |
| **Item Scroll** | 1 | 10/277 (3.61%) |
| **Poisoned Angler Tooth Arrow** | 2-8 | 11/277 (3.97%) |
| **Octine Arrow** | 2-8 | 11/277 (3.97%) |
| **Wight's Heart** | 1 | 6/277 (2.17%) |
| **Basilisk Arrow** | 1-2 | 6/277 (2.17%) |
| **Shock Arrow** | 1-2 | 6/277 (2.17%) |
| **Weeping Blue Petal** | 1 | 15/277 (5.42%) |
| **Valonite Splinter** | 1-2 | 5/277 (1.81%) |
| **Amulet Socket** | 1 | 3/277 (1.08%) |
| **Lore Scrap** | 1 | 7/277 (2.53%) |
| **Explorer's Entries: Marsh Ruins** | 1 | 8/277 (2.89%) |
| **Aspectrus Seeds** | 1-2 | 4/277 (1.44%) |
| **Bone Wayfinder** | 1 | 6/277 (2.17%) |

### music\_disc
Used by other loot tables for Music Disc loot

| Music Disc Loot | | |
| --- | --- | --- |
| **Loot Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Legendary Disc** | 1 | 1/14 (7.14%) |
| **Tribeman's Disc** | 1 | 1/14 (7.14%) |
| **Frosty Disc** | 1 | 1/14 (7.14%) |
| **Explorer's Disc** | 1 | 1/14 (7.14%) |
| **Music Disc** | 1 | 1/14 (7.14%) |
| **Music Disc** | 1 | 1/14 (7.14%) |
| **Mysterious Disc** | 1 | 1/14 (7.14%) |
| **Temple Disc** | 1 | 1/14 (7.14%) |
| **Music Disc** | 1 | 1/14 (7.14%) |
| **DJ Wight's Hot New Mixtape** | 1 | 1/14 (7.14%) |
| **Music Disc** | 1 | 1/14 (7.14%) |
| **Music Disc** | 1 | 1/14 (7.14%) |
| **Music Disc** | 1 | 1/14 (7.14%) |
| **Music Disc** | 1 | 1/14 (7.14%) |

### present\_loot
Used by Presents from the Winter event

| Present Loot | | |
| --- | --- | --- |
| **Loot Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Mince Pie** | 3-8 | 66/214 (30.84%) |
| **Christmas Pudding** | 3-8 | 66/214 (30.84%) |
| **Candy Cane** | 3-8 | 66/214 (30.84%) |
| **Frosty Disc** | 1 | 15/214 (7.01%) |
| **Coal** | 1 | 1/214 (0.56%) |

### puffshroom
Used for shearing Puffshrooms

| Puffshroom Loot | | |
| --- | --- | --- |
| **Loot Item** | **Quantity** | **Weight** |
| 1-2 Rolls, if sheared: | | |
| **Puffshroom Tendril** | 1 | 1/1 (100%) |

### rootman\_simulacrum\_offerings
Used by Offering Tables found next to Rootman Simulacra

| Simulacrum Offerings | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1 Roll: | | |
| **Ball of Sap** | 1 | 1/7 (14.29%) |
| **Reed Donut** | 1 | 1/7 (14.29%) |
| **Jam Donut** | 1 | 1/7 (14.29%) |
| **White Pear** | 1 | 1/7 (14.29%) |
| **Weeping Blue Petal** | 1 | 1/7 (14.29%) |
| **Forbidden Fig** | 1 | 1/7 (14.29%) |
| **Spirit Fruit** | 1 | 1/7 (14.29%) |

### sludge\_plains\_ruins\_urn
Used by Urns in Sludge Plains Ruins

| Sludge Ruins Urn | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1-2 Rolls: | | |
| **Mud Brick** | 1-3 | 40/267 (14.98%) |
| **Sulfur** | 2-4 | 35/267 (13.11%) |
| **Ball of Sap** | 2-6 | 26/267 (9.74%) |
| **Green Dentrothyst Shard** | 1-3 | 16/267 (5.99%) |
| **Orange Dentrothyst Shard** | 1-3 | 10/267 (3.75%) |
| **Amate Paper** | 2-3 | 12/267 (4.49%) |
| **Angler Tooth Arrow** | 2-8 | 16/267 (5.99%) |
| **Syrmorite Nugget** | 2-8 | 12/267 (4.49%) |
| **Octine Nugget** | 2-8 | 12/267 (4.49%) |
| **Item Scroll** | 1 | 10/267 (3.75%) |
| **Poisoned Angler Tooth Arrow** | 2-8 | 11/267 (4.12%) |
| **Octine Arrow** | 2-8 | 11/267 (4.12%) |
| **Wight's Heart** | 1 | 6/267 (2.25%) |
| **Basilisk Arrow** | 1-2 | 6/267 (2.25%) |
| **Shock Arrow** | 1-2 | 6/267 (2.25%) |
| **File:LargeSludgeJello.png Sludge Jello** | 1 | 15/267 (5.62%) |
| **Valonite Splinter** | 1-2 | 5/267 (1.87%) |
| **Amulet Socket** | 1 | 3/267 (1.12%) |
| **Lore Scrap** | 1 | 7/267 (2.62%) |
| **Explorer's Entries: Marsh Ruins** | 1 | 8/267 (3%) |
| **Aspectrus Seeds** | 1-2 | 4/267 (1.5%) |
| **Bone Wayfinder** | 1 | 6/267 (2.25%) |

### sludge\_worm\_dungeon\_barrishee\_chest
Used by Chests in the Barrishee Lair of the Sludgeon

| Sludgeon Barrishee Chest | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| *Shared Pool*  1 Roll per location: | | |
| **Critter Cruncher** | 1 | 1/1 (100%) |
| *Shared Pool*  1-2 Rolls per location: | | |
| **Sludge Slicer** | 1 | 1/1 (100%) |
| *Shared Pool*  1 Roll per location: | | |
| **Forbidden Fig** | 1 | 1/1 (100%) |
| *Shared Pool*  1 Roll per location: | | |
| **Explorer's Hat** | 1 | 1/1 (100%) |
| *Shared Pool*  1 Roll per location: | | |
| **Swift Pick** | 1 | 1/1 (100%) |
| *Shared Pool*  1 Roll per location: | | |
| **Ring of Gathering** | 1 | 1/1 (100%) |
| 1 Roll per inventory: | | |
| **Ring of Gathering** (from shared pool) | 1 | 1/1 (100%) |
| 3-4 Rolls (+1-2 Bonus Rolls): | | |
| **Nothing** | N/A | 90/149 (60.4%) |
| **Forbidden Fig** (from shared pool) | 1 | 5/149 (3.36%) |
| **Explorer's Hat** (from shared pool) | 1 | 5/149 (3.36%) |
| **Swift Pick** (from shared pool) | 1 | 6/149 (4.02%) |
| **Critter Cruncher** (from shared pool) | 1 | 10/149 (6.71%) |
| **Sludge Slicer** (from shared pool) | 1 | 8/149 (5.37%) |
| **Aspectrus Seeds** | 1 | 10/149 (6.71%) |
| **Life Crystal Fragment** | 1 | 8/149 (5.37%) |
| **Music Discs** (see music\_disc) | 1 | 7/149 (4.7%) |
| 5-7 Rolls (+1-2 Bonus Rolls): | | |
| **Nothing** | N/A | 20/179 (11.17%) |
| **Amulet Socket** | 1 | 22/179 (12.29%) |
| **Item Scroll** | 1 | 24/179 (13.41%) |
| **Wight's Heart** | 1-2 | 20/179 (11.17%) |
| **Angry Pebble** | 1-3 | 20/179 (11.17%) |
| **Bone Wayfinder** | 1 | 2/179 (1.11%) |
| **Valonite Splinter** | 2-4 | 15/179 (8.38%) |
| **Octine Ingot** | 1-2 | 10/179 (5.59%) |
| **Syrmorite Ingot** | 1-2 | 10/179 (5.59%) |
| **Valonite Shard** | 1-2 | 10/179 (5.59%) |
| **Basilisk Arrow** | 1-3 | 8/179 (4.47%) |
| **Shock Arrow** | 1-3 | 8/179 (4.47%) |
| **Orange Dentrothyst Shard** | 1-4 | 10/179 (5.59%) |
| 6-10 Rolls (+1-2 Bonus Rolls): | | |
| **Green Marshmallow** | 1 | 26/230 (11.3%) |
| **Pink Marshmallow** | 1 | 26/230 (11.3%) |
| **Amate Paper** | 2-3 | 20/230 (8.7%) |
| **Angler Tooth Arrow** | 8-16 | 20/230 (8.7%) |
| **Syrmorite Nugget** | 4-8 | 15/230 (6.52%) |
| **Octine Nugget** | 4-8 | 15/230 (6.52%) |
| **Reed Donut** | 1-3 | 24/230 (10.43%) |
| **Jam Donut** | 1-2 | 26/230 (11.3%) |
| **Ball of Sap** | 4-12 | 28/230 (12.17%) |
| **Weeping Blue Petal** | 1-2 | 15/230 (6.52%) |
| **Green Dentrothyst Shard** | 1-4 | 15/230 (6.52%) |
| 5-6 Rolls (+1-2 Bonus Rolls): | | |
| **Sulfur** | 4-8 | 10/30 (33.33%) |
| **Reed Rope** | 4-8 | 10/30 (33.33%) |
| **Mud Brick** | 2-4 | 10/30 (33.33%) |

### sludge\_worm\_dungeon\_chest
Used by Chests in the Labyrinthine Vaults of the Sludgeon

| Sludgeon Chest | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| *Shared Pool*  1 Roll per location: | | |
| **Critter Cruncher** | 1 | 1/1 (100%) |
| *Shared Pool*  1-2 Rolls per location: | | |
| **Sludge Slicer** | 1 | 1/1 (100%) |
| *Shared Pool*  1-2 Rolls per location: | | |
| **Predator Bow** | 1 | 1/1 (100%) |
| 1 Roll per inventory: | | |
| **Nothing** | N/A | 2/3 (66.67%) |
| **Predator Bow** (from shared pool) | 1 | 1/3 (33.33%) (guaranteed upon looting 3rd inventory) |
| *Shared Pool*  2-3 Rolls per location: | | |
| **Weedwood Bow** | 1 | 1/1 (100%) |
| 1 Roll per inventory: | | |
| **Nothing** | N/A | 1/2 (50%) |
| **Weedwood Bow** (from shared pool) | 1 | 1/2 (50%) |
| *Shared Pool*  1 Roll per location: | | |
| **Forbidden Fig** | 1 | 1/1 (100%) |
| *Shared Pool*  1 Roll per location: | | |
| **Explorer's Hat** | 1 | 1/1 (100%) |
| *Shared Pool*  1 Roll per location: | | |
| **Swift Pick** | 1 | 1/1 (100%) |
| 2-3 Rolls (+1-2 Bonus Rolls) per inventory: | | |
| **Nothing** | N/A | 90/149 (60.4%) |
| **Forbidden Fig** (from shared pool) | 1 | 5/149 (3.36%) |
| **Explorer's Hat** (from shared pool) | 1 | 5/149 (3.36%) |
| **Swift Pick** (from shared pool) | 1 | 6/149 (4.02%) |
| **Critter Cruncher** (from shared pool) | 1 | 10/149 (6.71%) |
| **Sludge Slicer** (from shared pool) | 1 | 8/149 (5.37%) |
| **Aspectrus Seeds** | 1 | 10/149 (6.71%) |
| **Life Crystal Fragment** | 1 | 8/149 (5.37%) |
| **Music Discs** (see music\_disc) | 1 | 7/149 (4.7%) |
| 4-6 Rolls (+1-2 Bonus Rolls): | | |
| **Nothing** | N/A | 20/179 (11.17%) |
| **Amulet Socket** | 1 | 22/179 (12.29%) |
| **Item Scroll** | 1 | 24/179 (13.41%) |
| **Wight's Heart** | 1-2 | 20/179 (11.17%) |
| **Angry Pebble** | 1-3 | 20/179 (11.17%) |
| **Bone Wayfinder** | 1 | 2/179 (1.12%) |
| **Valonite Splinter** | 2-4 | 15/179 (8.38%) |
| **Octine Ingot** | 1-2 | 10/179 (5.59%) |
| **Syrmorite Ingot** | 1-2 | 10/179 (5.59%) |
| **Valonite Shard** | 1-2 | 10/179 (5.59%) |
| **Basilisk Arrow** | 1-3 | 8/179 (4.47%) |
| **Shock Arrow** | 1-3 | 8/179 (4.47%) |
| **Orange Dentrothyst Shard** | 1-4 | 10/179 (5.59%) |
| 6-10 Rolls (+1-2 Bonus Rolls): | | |
| **Green Marshmallow** | 1 | 26/230 (11.3%) |
| **Pink Marshmallow** | 1 | 26/230 (11.3%) |
| **Amate Paper** | 2-3 | 20/230 (8.7%) |
| **Angler Tooth Arrow** | 8-16 | 20/230 (8.7%) |
| **Syrmorite Nugget** | 4-8 | 15/230 (6.52%) |
| **Octine Nugget** | 4-8 | 15/230 (6.52%) |
| **Reed Donut** | 1-3 | 24/230 (%) |
| **Jam Donut** | 1-2 | 26/230 (11.3%) |
| **Ball of Sap** | 4-12 | 28/230 (12.17%) |
| **Weeping Blue Petal** | 1-2 | 15/230 (6.52%) |
| **Green Dentrothyst Shard** | 1-4 | 15/230 (6.52%) |
| 5-6 Rolls (+1-2 Bonus Rolls): | | |
| **Sulfur** | 4-8 | 10/30 (33.33%) |
| **Reed Rope** | 4-8 | 10/30 (33.33%) |
| **Mud Brick** | 2-4 | 10/30 (33.33%) |

### sludge\_worm\_dungeon\_crypt\_urn
Used by Urns and Dungeon Alcoves in the Crypt of the Sludgeon

| Sludgeon Crypt Urn | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1-2 Rolls: | | |
| **Amulet Socket** | 1 | 80/1016 (7.87%) |
| **Item Scroll** | 1 | 94/1016 (9.25%) |
| **Wight's Heart** | 1-3 | 80/1016 (7.87%) |
| **Angry Pebble** | 1-3 | 82/1016 (8.07%) |
| **Valonite Splinter** | 2-5 | 85/1016 (8.37%) |
| **Valonite Shard** | 1-3 | 80/1016 (7.87%) |
| **Orange Dentrothyst Shard** | 1-3 | 80/1016 (7.87%) |
| **Green Marshmallow** | 1-3 | 31/1016 (3.05%) |
| **Pink Marshmallow** | 1-3 | 31/1016 (3.05%) |
| **Amate Paper** | 2-3 | 25/1016 (2.46%) |
| **Angler Tooth Arrow** | 10-14 | 25/1016 (2.46%) |
| **Basilisk Arrow** | 2-3 | 12/1016 (1.18%) |
| **Shock Arrow** | 2-3 | 12/1016 (1.18%) |
| **Octine Arrow** | 4-8 | 20/1016 (1.97%) |
| **Syrmorite Nugget** | 4-10 | 20/1016 (1.97%) |
| **Octine Nugget** | 4-10 | 20/1016 (1.97%) |
| **Reed Donut** | 1-3 | 31/1016 (3.05%) |
| **Jam Donut** | 1-2 | 30/1016 (2.95%) |
| **Ball of Sap** | 6-12 | 33/1016 (3.25%) |
| **File:LargeSludgeJello.png Sludge Jello** | 1-2 | 20/1016 (1.97%) |
| **Green Dentrothyst Shard** | 1-4 | 20/1016 (1.97%) |
| **Sulfur** | 4-8 | 35/1016 (3.44%) |
| **Sludge Ball** | 4-8 | 35/1016 (3.44%) |
| **Mud Brick** | 2-4 | 35/1016 (3.44%) |

### sludge\_worm\_dungeon\_item\_shelf
Used by Item Shelves in the Labyrinthine Vaults of the Sludgeon

| Sludgeon Item Shelf | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1-3 Rolls: | | |
| **Nothing** | N/A | 120/253 (47.43%) |
| **Green Dentrothyst Vial** (clean or dirty) | 1 | 25/253 (9.88%) |
| **Orange Dentrothyst Vial** | 1 | 20/253 (7.91%) |
| **Aqua Middle Gem** | 1 | 10/253 (3.95%) |
| **Crimson Middle Gem** | 1 | 10/253 (3.95%) |
| **Green Middle Gem** | 1 | 10/253 (3.95%) |
| **Reed Donut** | 1 | 20/253 (7.91%) |
| **Sludgeon Plant Items** | 1 | 30/253 (11.86%) |
| **Herblore Book** | 1 | 8/253 (3.16%) |

### sludge\_worm\_dungeon\_urn
Used by Urns and Dungeon Alcoves in the Sludgeon Tower, Labyrinthine Vaults, and Barrishee Lair of the Sludgeon

| Sludgeon Urn Drops | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1-2 Roll: | | |
| **Amulet Socket** | 1 | 15/530 (2.83%) |
| **Item Scroll** | 1 | 29/530 (5.47%) |
| **Wight's Heart** | 1-3 | 15/530 (2.83%) |
| **Angry Pebble** | 1-3 | 17/530 (3.21%) |
| **Valonite Splinter** | 2-5 | 20/530 (3.77%) |
| **Valonite Shard** | 1-3 | 15/530 (2.83%) |
| **Orange Dentrothyst Shard** | 1-3 | 15/530 (2.83%) |
| **Green Marshmallow** | 1-3 | 31/530 (5.85%) |
| **Pink Marshmallow** | 1-3 | 31/530 (5.85%) |
| **Amate Paper** | 2-3 | 25/530 (4.72%) |
| **Angler Tooth Arrow** | 10-14 | 25/530 (4.72%) |
| **Basilisk Arrow** | 1-2 | 12/530 (2.26%) |
| **Shock Arrow** | 1-2 | 12/530 (2.26%) |
| **Octine Arrow** | 4-8 | 20/530 (3.77%) |
| **Syrmorite Nugget** | 4-10 | 20/530 (3.77%) |
| **Octine Nugget** | 4-10 | 20/530 (3.77%) |
| **Reed Donut** | 1-3 | 31/530 (5.85%) |
| **Jam Donut** | 1-2 | 30/530 (5.66%) |
| **Ball of Sap** | 6-12 | 33/530 (6.23%) |
| **File:LargeSludgeJello.png Sludge Jello** | 1-2 | 20/530 (3.77%) |
| **Green Dentrothyst Shard** | 1-4 | 20/530 (3.77%) |
| **Sulfur** | 4-8 | 35/530 (6.6%) |
| **Sludge Ball** | 4-8 | 35/530 (6.6%) |
| **Mud Brick** | 2-4 | 35/530 (6.6%) |

### spawner\_chest
Used by Chests in Shrines

| Spawner Chest | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 7-10 Rolls (+1-2 Bonus Rolls): | | |
| **Pink Marshmallow** | 1 | 24/414 (5.8%) |
| **Lurker Skin** | 1-2 | 20/414 (4.83%) |
| **Sulfur** | 8-16 | 20/414 (4.83%) |
| **Reed Rope** | 1-3 | 20/414 (4.83%) |
| **Angler Tooth Arrow** | 4-8 | 20/414 (4.83%) |
| **Syrmorite Nugget** | 4-16 | 25/414 (6.04%) |
| **Octine Nugget** | 4-16 | 25/414 (6.04%) |
| **Green Marshmallow** | 1 | 24/414 (5.8%) |
| **Reed Donut** | 1-2 | 18/414 (4.35%) |
| **Jam Donut** | 1 | 18/414 (4.35%) |
| **Amulet Socket** | 1 | 15/414 (3.62%) |
| **Item Scroll** | 1 | 14/414 (3.38%) |
| **Ball of Sap** | 2-8 | 18/414 (4.35%) |
| **Poisoned Angler Tooth Arrow** | 4-8 | 13/414 (3.14%) |
| **Wight's Heart** | 1-2 | 12/414 (2.9%) |
| **Weeping Blue Petal** | 1-3 | 11/414 (2.66%) |
| **Octine Arrow** | 4-8 | 11/414 (2.66%) |
| **Basilisk Arrow** | 1-3 | 6/414 (1.45%) |
| **Shock Arrow** | 1-3 | 6/414 (1.45%) |
| **Syrmorite Nugget** | 1-2 | 15/414 (3.62%) |
| **Octine Nugget** | 1-2 | 15/414 (3.62%) |
| **Critter Cruncher** | 1 | 8/414 (1.93%) |
| **Hag Hacker** | 1 | 8/414 (1.93%) |
| **Bone Wayfinder** | 1 | 10/414 (2.42%) |
| **Valonite Splinter** | 1-4 | 8/414 (1.93%) |
| **Lore Scrap** | 1 | 8/414 (1.93%) |
| **Explorer's Entries: Dungeon Shrine** | 1 | 6/414 (1.45%) |
| **Valonite Shard** | 1 | 6/414 (1.45%) |
| **Explorer's Hat** | 1 | 4/414 (0.97%) |

### tar\_pool\_pot
Used by Pots in Tar Pool Dungeons

| Tar Pool Pot | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 2-3 Rolls: | | |
| **Tar Drip** | 1-3 | 28/307 (9.12%) |
| **Green Dentrothyst Shard** | 3-6 | 15/307 (4.89%) |
| **Orange Dentrothyst Shard** | 3-6 | 10/307 (3.26%) |
| **Syrmorite Nugget** | 4-16 | 28/307 (9.12%) |
| **Octine Nugget** | 4-16 | 28/307 (9.12%) |
| **Item Scroll** | 1 | 20/307 (6.51%) |
| **Valonite Splinter** | 1-4 | 12/307 (3.91%) |
| **Amulet Socket** | 1 | 12/307 (3.91%) |
| **Lore Scrap** | 1 | 10/307 (3.26%) |
| **Explorer's Entries: Pools of Tar** | 1 | 12/307 (3.91%) |
| **Jam Donut** | 1 | 28/307 (9.12%) |
| **Reed Donut** | 1-2 | 28/307 (9.12%) |
| **Pink Marshmallow** | 1 | 28/307 (9.12%) |
| **Green Marshmallow** | 1 | 28/307 (9.12%) |
| **Aspectrus Seeds** | 2-6 | 12/307 (3.91%) |
| **Ring of Gathering** | 1 | 8/307 (2.61%) |

### underground\_ruins\_pot
Used by Pots in Underground Ruins

| Underground Ruins Pot | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| 1-3 Rolls: | | |
| **Reed Rope** | 2-4 | 40/309 (12.94%) |
| **Sulfur** | 3-6 | 35/309 (11.33%) |
| **Ball of Sap** | 2-6 | 26/309 (8.41%) |
| **Green Dentrothyst Shard** | 1-3 | 16/309 (5.18%) |
| **Orange Dentrothyst Shard** | 1-3 | 10/309 (3.23%) |
| **Lurker Skin** | 2-3 | 12/309 (3.88%) |
| **Angler Tooth Arrow** | 2-8 | 18/309 (5.83%) |
| **Syrmorite Nugget** | 2-8 | 12/309 (3.88%) |
| **Octine Nugget** | 2-8 | 12/309 (3.88%) |
| **Item Scroll** | 1 | 10/309 (3.23%) |
| **Poisoned Angler Tooth Arrow** | 2-8 | 11/309 (3.56%) |
| **Octine Arrow** | 2-8 | 11/309 (3.56%) |
| **Limestone Flux** | 1-3 | 11/309 (3.56%) |
| **Wight's Heart** | 1 | 8/309 (2.59%) |
| **Basilisk Arrow** | 1-2 | 6/309 (1.94%) |
| **Shock Arrow** | 1-2 | 6/309 (1.94%) |
| **Weeping Blue Petal** | 1 | 15/309 (4.85%) |
| **Reed Donut** | 1 | 15/309 (4.85%) |
| **Valonite Splinter** | 1-2 | 5/309 (1.62%) |
| **Amulet Socket** | 1 | 3/309 (0.97%) |
| **Lore Scrap** | 1 | 7/309 (2.27%) |
| **Explorer's Entries: Underground Ruins** | 1 | 8/309 (2.59%) |
| **Aspectrus Seeds** | 1-2 | 4/309 (1.29%) |
| **Bone Wayfinder** | 1 | 8/309 (2.59%) |

### wight\_fortress\_chest
Used by Chests in the Wight Fortress

| Wight Fortress Chest | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| *Shared Pool*  0-1 Rolls per location: | | |
| **Explorer's Entries: The Fortress** | 1 | 1/1 (100%) |
| 1 Roll per inventory: | | |
| **Nothing** | N/A | 4/5 (80%) |
| **Explorer's Entries: The Fortress** (from shared pool) | 1 | 1/5 (20%) |
| *Shared Pool*  1 Roll (+1 Bonus Roll) per location | | |
| **Gem Singer** | 1 | 1/1 (100%) |
| *Shared Pool*  1 Roll per location: | | |
| **Ring of Ascent** | 1 | 1/1 (100%) |
| *Shared Pool*  1-3 Rolls per location: | | |
| **Wight's Bane** | 1 | 1/1 (100%) |
| *Shared Pool*  1-2 Rolls per location: | | |
| **Critter Cruncher** | 1 | 1/1 (100%) |
| *Shared Pool*  1-2 Rolls per location: | | |
| **Sludge Slicer** | 1 | 1/1 (100%) |
| *Shared Pool*  1-2 Rolls per location: | | |
| **Hag Hacker** | 1 | 1/1 (100%) |
| *Shared Pool*  1-2 Rolls per location: | | |
| **Forbidden Fig** | 1 | 1/1 (100%) |
| *Shared Pool*  1 Roll per location: | | |
| **Explorer's Hat** | 1 | 1/1 (100%) |
| *Shared Pool*  1-2 Rolls per location: | | |
| **Swift Pick** | 1 | 1/1 (100%) |
| 2-3 Rolls (+1-2 Bonus Rolls) per inventory: | | |
| **Nothing** | N/A | 90/176 (51.14%) |
| **Ring of Ascent** | 1 | 4/176 (2.27%) (guaranteed after looting 60% of inventories per location) |
| **Forbidden Fig** (from shared pool) | 1 | 5/176 (2.84%) |
| **Explorer's Hat** (from shared pool) | 1 | 5/176 (2.84%) |
| **Swift Pick** (from shared pool) | 1 | 6/176 (3.41%) |
| **Wight's Bane** (from shared pool) | 1 | 8/176 (4.55%) |
| **Critter Cruncher** (from shared pool) | 1 | 10/176 (5.68%) |
| **Hag Hacker** (from shared pool) | 1 | 10/176 (5.68%) |
| **Sludge Slicer** (from shared pool) | 1 | 8/176 (4.55%) |
| **Gem Singer** (from shared pool) | 1 | 5/176 (2.84%) |
| **Aspectrus Seeds** | 1 | 10/176 (5.68%) |
| **Life Crystal Fragment** | 1 | 8/176 (4.55%) |
| **Music Discs** (see music\_disc) | 1 | 7/176 (3.98%) |
| 3-5 Rolls (+1-2 Bonus Rolls): | | |
| **Nothing** | N/A | 20/179 (11.17%) |
| **Amulet Socket** | 1 | 22/179 (12.29%) |
| **Item Scroll** | 1 | 24/179 (13.41%) |
| **Wight's Heart** | 1-2 | 20/179 (11.17%) |
| **Angry Pebble** | 1-3 | 20/179 (11.17%) |
| **Bone Wayfinder** | 1 | 2/179 (1.18%) |
| **Valonite Splinter** | 2-4 | 15/179 (8.38%) |
| **Octine Ingot** | 1-2 | 10/179 (5.59%) |
| **Syrmorite Ingot** | 1-2 | 10/179 (5.59%) |
| **Valonite Shard** | 1-2 | 10/179 (5.59%) |
| **Basilisk Arrow** | 1-3 | 8/179 (4.47%) |
| **Shock Arrow** | 1-3 | 8/179 (4.47%) |
| **Orange Dentrothyst Shard** | 1-4 | 10/179 (5.59%) |
| 5-9 Rolls (+1-2 Bonus Rolls): | | |
| **Green Marshmallow** | 1 | 26/230 (11.3%) |
| **Pink Marshmallow** | 1 | 26/230 (11.3%) |
| **Lurker Skin** | 1-2 | 20/230 (8.7%) |
| **Angler Tooth Arrow** | 8-16 | 20/230 (8.7%) |
| **Syrmorite Nugget** | 4-8 | 15/230 (6.52%) |
| **Octine Nugget** | 4-8 | 15/230 (6.52%) |
| **Reed Donut** | 1-3 | 24/230 (10.43%) |
| **Jam Donut** | 1-2 | 26/230 (11.3%) |
| **Ball of Sap** | 4-12 | 28/230 (12.17%) |
| **Weeping Blue Petal** | 1-2 | 15/230 (6.52%) |
| **Green Dentrothyst Shard** | 1-4 | 15/230 (6.52%) |
| 5-6 Rolls (+1-2 Bonus Rolls): | | |
| **Sulfur** | 4-8 | 10/20 (50%) |
| **Reed Rope** | 4-8 | 10/20 (50%) |

### wight\_fortress\_pot
Used by Pots in the Wight Fortress

| Wight Fortress Pot | | |
| --- | --- | --- |
| **Dropped Item** | **Quantity** | **Weight** |
| *Shared Pool* 1 Roll per location: | | |
| **Explorer's Entries: The Fortress** | 1 | 1/1 (100%) |
| 1 Roll per inventory: | | |
| **Nothing** | N/A | 9/10 (90%) |
| **Explorer's Entries: The Fortress** (from shared pool) | 1 | 1/10 (10%) (guaranteed after looting 50% of inventories per location) |
| 1-2 Rolls: | | |
| **Amulet Socket** | 1 | 15/530 (2.83%) |
| **Item Scroll** | 1-3 | 29/530 (5.47%) |
| **Wight's Heart** | 1-3 | 20/530 (3.77%) |
| **Angry Pebble** | 1-3 | 17/530 (3.21%) |
| **Valonite Splinter** | 2-5 | 20/530 (3.77%) |
| **Valonite Shard** | 1-3 | 15/530 (2.83%) |
| **Orange Dentrothyst Shard** | 1-3 | 15/530 (2.83%) |
| **Green Marshmallow** | 1-3 | 31/530 (5.85%) |
| **Pink Marshmallow** | 1-3 | 31/530 (5.85%) |
| **Lurker Skin** | 1-3 | 25/530 (4.72%) |
| **Angler Tooth Arrow** | 13-20 | 25/530 (4.72%) |
| **Basilisk Arrow** | 1-2 | 12/530 (2.26%) |
| **Shock Arrow** | 1-2 | 12/530 (2.26%) |
| **Octine Arrow** | 7-14 | 20/530 (3.77%) |
| **Syrmorite Nugget** | 7-16 | 20/530 (3.77%) |
| **Octine Nugget** | 7-16 | 20/530 (3.77%) |
| **Reed Donut** | 4-9 | 29/530 (5.47%) |
| **Jam Donut** | 4-8 | 31/530 (5.85%) |
| **Ball of Sap** | 7-18 | 33/530 (6.23%) |
| **Weeping Blue Petal** | 4-8 | 20/530 (3.77%) |
| **Green Dentrothyst Shard** | 4-10 | 20/530 (3.77%) |
| **Sulfur** | 13-22 | 35/530 (6.6%) |
| **Reed Rope** | 11-18 | 35/530 (6.6%) |

Unused
--------

These loot tables are not used anywhere in the mod, but exist in the files.

### common\_pot\_loot
*Unused* (used by Pots in Caverns/Lake Caverns, Ruins, and Underground Ruins in worlds from before Beta 3.5.0)

| Common Pot Loot | | |
| --- | --- | --- |
| **Loot Item** | **Quantity** | **Weight** |
| 1-2 Rolls: | | |
| **Reed Rope** | 1-3 | 45/233 (19.31%) |
| **Sulfur** | 2-4 | 40/233 (17.17%) |
| **Ball of Sap** | 1-4 | 26/233 (11.16%) |
| **Lurker Skin** | 1-2 | 12/233 (5.15%) |
| **Angler Tooth Arrow** | 4-12 | 12/233 (5.15%) |
| **Syrmorite Nugget** | 2-8 | 11/233 (4.72%) |
| **Octine Nugget** | 2-8 | 11/233 (4.72%) |
| **Green Dentrothyst Shard** | 1-3 | 10/233 (4.29%) |
| **Item Scroll** | 1 | 8/233 (3.43%) |
| **Poisoned Angler Tooth Arrow** | 4-10 | 7/233 (3%) |
| **Octine Arrow** | 4-10 | 7/233 (3%) |
| **Wight's Heart** | 1 | 6/233 (2.58%) |
| **Weeping Blue Petal** | 1 | 6/233 (2.58%) |
| **Bone Wayfinder** | 1 | 6/233 (2.58%) |
| **Any Lore Scrap** | 1 | 5/233 (2.15%) |
| **Orange Dentrothyst Shard** | 1-3 | 4/233 (1.72%) |
| **Basilisk Arrow** | 2-8 | 4/233 (1.72%) |
| **Shock Arrow** | 2-8 | 4/233 (1.72%) |
| **Aspectrus Seeds** | 1-2 | 4/233 (1.72%) |
| **Valonite Splinter** | 1-2 | 3/233 (1.29%) |
| **Amulet Socket** | 1 | 2/233 (0.86%) |

### common\_chest\_loot
*Unused* (used by Chests in Idol Head Statues in worlds from before Beta 3.5.0)

| Common Chest Loot | | |
| --- | --- | --- |
| **Loot Item** | **Quantity** | **Weight** |
| 4-6 Rolls (+1-2 Bonus Rolls): | | |
| **Syrmorite Nugget** | 4-16 | 25/396 (6.31%) |
| **Octine Nugget** | 4-16 | 25/396 (6.31%) |
| **Pink Marshmallow** | 1 | 24/396 (6.06%) |
| **Green Marshmallow** | 1 | 24/396 (6.06%) |
| **Lurker Skin** | 1-2 | 20/396 (5.05%) |
| **Sulfur** | 8-16 | 20/396 (5.05%) |
| **Reed Rope** | 1-3 | 20/396 (5.05%) |
| **Angler Tooth Arrow** | 8-12 | 20/396 (5.05%) |
| **Reed Donut** | 1-2 | 18/396 (4.55%) |
| **Jam Donut** | 1 | 18/396 (4.55%) |
| **Ball of Sap** | 2-8 | 18/396 (4.55%) |
| **Item Scroll** | 1 | 16/396 (4.04%) |
| **Amulet Socket** | 1 | 15/396 (3.79%) |
| **Syrmorite Ingot** | 1-2 | 15/396 (3.79%) |
| **Octine Ingot** | 1-2 | 15/396 (3.79%) |
| **Poisoned Angler Tooth Arrow** | 4-8 | 13/396 (3.28%) |
| **Wight's Heart** | 1-2 | 12/396 (3.03%) |
| **Angry Pebble** | 1-4 | 12/396 (3.03%) |
| **Weeping Blue Petal** | 1-3 | 11/396 (2.78%) |
| **Octine Arrow** | 4-8 | 11/396 (2.78%) |
| **Bone Wayfinder** | 1 | 10/396 (2.53%) |
| **Valonite Splinter** | 1-4 | 8/396 (2.02%) |
| **Any Lore Scrap** | 1 | 8/396 (2.02%) |
| **Basilisk Arrow** | 4-8 | 6/396 (1.52%) |
| **Shock Arrow** | 4-8 | 6/396 (1.52%) |
| **Valonite Shard** | 1 | 6/396 (1.52%) |

### dungeon\_pot\_loot
*Unused* (used by Pots in Tar Pool Dungeons, Cragrock Towers, and the Wight Fortress in worlds from before Beta 3.5.0)

| Dungeon Pot Loot | | |
| --- | --- | --- |
| **Loot Item** | **Quantity** | **Weight** |
| 1-3 Rolls: | | |
| **Syrmorite Nugget** | 4-16 | 28/282 (9.93%) |
| **Octine Nugget** | 4-16 | 28/282 (9.93%) |
| **Jam Donut** | 1 | 28/282 (9.93%) |
| **Reed Donut** | 1-2 | 28/282 (9.93%) |
| **Pink Marshmallow** | 1 | 28/282 (9.93%) |
| **Green Marshmallow** | 1 | 28/282 (9.93%) |
| **Item Scroll** | 1 | 20/282 (7.09%) |
| **Reed Rope** | 1-5 | 15/282 (5.32%) |
| **Sulfur** | 2-6 | 15/282 (5.32%) |
| **Ball of Sap** | 3-9 | 15/282 (5.32%) |
| **Valonite Splinter** | 1-4 | 12/282 (4.26%) |
| **Aspectrus Seeds** | 1-4 | 12/282 (4.26%) |
| **Any Lore Scrap** | 1 | 8/282 (2.84%) |
| **Amulet Socket** | 1 | 6/282 (2.13%) |
| **Green Dentrothyst Shard** | 1-3 | 6/282 (2.13%) |
| **Orange Dentrothyst Shard** | 1-3 | 5/282 (1.77%) |

### dungeon\_chest\_loot
*Unused* (used by Chests in Shrines, Cragrock Towers, and the Wight Fortress in worlds from before Beta 3.5.0)

| Dungeon Chest Loot | | |
| --- | --- | --- |
| **Loot Item** | **Quantity** | **Weight** |
| 4-8 Rolls (+1-2 Bonus Rolls): | | |
| **Ball of Sap** | 4-12 | 28/271 (10.33%) |
| **Pink Marshmallow** | 1 | 26/271 (9.59%) |
| **Green Marshmallow** | 1 | 26/271 (9.59%) |
| **Syrmorite Nugget** | 4-16 | 20/271 (7.38%) |
| **Octine Nugget** | 4-16 | 20/271 (7.38%) |
| **Reed Donut** | 1-3 | 20/271 (7.38%) |
| **Jam Donut** | 1-2 | 20/271 (7.38%) |
| **Item Scroll** | 1 | 18/271 (6.64%) |
| **Octine Ingot** | 1-2 | 15/271 (5.54%) |
| **Syrmorite Ingot** | 1-2 | 15/271 (5.54%) |
| **Lurker Skin** | 2-3 | 12/271 (4.43%) |
| **Sulfur** | 3-7 | 12/271 (4.43%) |
| **Reed Rope** | 2-6 | 12/271 (4.43%) |
| **Any Lore Scrap** | 1 | 8/271 (2.95%) |
| **Amulet Socket** | 1 | 6/271 (2.21%) |
| **Music Disc Loot** (see music\_disc) | 1 | 5/271 (1.85%) |
| **Bone Wayfinder** | 1 | 5/271 (1.85%) |
| **Gem Singer** | 1 | 3/271 (1.11%) |
| 1-2 Rolls (+1-2 Bonus Rolls): | | |
| **Nothing** | N/A | 200/265 (75.47%) |
| **Critter Cruncher** | 1 | 10/265 (3.77%) |
| **Hag Hacker** | 1 | 10/265 (3.77%) |
| **Gem Singer** | 1 | 10/265 (3.77%) |
| **Wight's Bane** | 1 | 8/265 (3.02%) |
| **Sludge Slicer** | 1 | 8/265 (3.02%) |
| **Swift Pick** | 1 | 6/265 (2.26%) |
| **Forbidden Fig** | 1 | 5/265 (1.89%) |
| **Ring of Ascent** | 1 | 4/265 (1.51%) |
| **Explorer's Hat** | 1 | 4/265 (1.51%) |

### shared\_loot\_pool\_test
*Unused* (was used to test the shared loot pool system)

| Shared Loot Pool Test Loot | | |
| --- | --- | --- |
| **Loot Item** | **Quantity** | **Weight** |
| *Shared Pool* 0-1 Rolls per location: | | |
| **Gem Singer** | 1 | 1/1 (100%) |
| *Shared Pool* 1-3 Rolls per location: | | |
| **Block of Valonite** | 1 | 1/1 (100%) |
| 1 Roll per inventory: | | |
| **Nothing** | N/A | 3/4 (75%) |
| **Gem Singer** (from shared pool) | 1 | 1/4 (25%) (guaranteed after looting 4 inventories per location) |
| 0-1 Rolls per inventory: | | |
| **Block of Valonite** (from shared pool) | 1 | 1/1 (100%) |
| 1 Roll: | | |
| **Betweenstone** | 1-8 | 1/1 (100%) |

History
---------

* Release 3.8.0:
  + Added underwater\_ruins\_pot Loot table.
  + Added anadia\_head, anadia\_body, anadia\_tail, anadia\_treasure, and silt\_crab\_trimming\_1, silt\_crab\_trimming\_2, silt\_crab\_trimming\_3 Loot tables.
  + Added anadia, greebling\_coracle, jellyfish, olm, and rock\_snot Entity tables.
  + Added Staff of the Mist Walker and Staff of the Shadow Walker to the Animator table.
* Release 3.7.0: Added deepman\_simulacrum\_offerings, lake\_cavern\_simulacrum\_offerings, and rootman\_simulacrum\_offerings Loot tables.
* Release 3.6.0:
  + Added chiromaw\_nest\_scattered\_loot Loot table.
  + Added chiromaw\_hatchling, chiromaw\_matriarch, and greebling\_corpse Entity tables.
* Beta 3.5.0:
  + Implented a new shared loot pool system, allowing entire structures to have a set amount of loot, allowing for better consistency of loot.
  + Rebalanced Loot tables massively. This includes overall amounts and weights of items being reduced, and most Ingots being replaced by Nuggets.
  + Added cave\_pot, cragrock\_tower\_chest, cragrock\_tower\_pot, idol\_heads\_chest, marsh\_ruins\_pot, puffshroom, sludge\_plains\_ruins\_urn, sludge\_worm\_dungeon\_barrishee\_chest, sludge\_worm\_dungeon\_chest, sludge\_worm\_dungeon\_crypt\_urn, sludge\_worm\_dungeon\_item\_shelf, sludge\_worm\_dungeon\_urn, spawner\_chest, tar\_pool\_pot, underground\_ruins\_pot, wight\_fortress\_chest, and wight\_fortress\_pot Loot tables.
  + The original common\_pot\_loot, common\_chest\_loot, dungeon\_pot\_loot, and dungeon\_chest\_loot Loot tables are no longer used in new worlds. Structures now use the above individual loot tables instead.
  + Added ash\_sprite, barrishee, crypt\_crawler, emberling, emberling\_shaman, large\_sludge\_worm, moving\_spawner\_hole, shambler, sludge\_menace, small\_sludge\_worm, tiny\_sludge\_worm, tiny\_sludge\_worm\_helper, wall\_lamprey, and wall\_living\_root Entity tables.
  + Added fabricated\_scroll Animator table.
* Release 3.4.0:
  + Added boulder\_sprite, root\_sprite, spirit\_tree\_face\_large, and spirit\_tree\_face\_small Entity tables.
  + Added Dentrothyst Shards, Bone Wayfinder, and Gem Singer to existing Loot tables.
  + Increased weight of Music Discs.
* Alpha 3.2.0:
  + Increased weight of Lore Scraps and Aspectrus Seeds.
  + Added Frosty Disc to present Loot table.
* Alpha 3.1.0: Added present\_loot Loot table.
* Alpha 3.0.0: Added dreadful\_peat\_mummy Entity table.
* Beta 2.0.0: Refactored entity drops into Entity tables.
* Beta 1.0.2: Loot tables adjusted.
* **Beta 1.0.0**: Introduced.