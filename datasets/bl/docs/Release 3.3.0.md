# Release 3.3.0

**Release 3.3.0** was the first official update to the Betweenlands for Minecraft 1.12.2, and was released on February 7, 2018. In particular, it added Advancements, Giant Roots, Hearthgrove and Nibbletwig Trees, new foods, and a massive array of changes and bug fixes.

Changelog
---------

*Note: The following is a comprehensive list of all additions, changes and bug fixes **since version Beta 2.0.4**, including the snapshot updates.*

### Additions

* Added a plethora of Advancements under 7 different categories
* Added Giant Roots, massive root formations that spawn in Coarse Islands biomes
* Added Giant Root (block)s and associated planks, slab, stairs, fence, fence gate, door and trapdoor
* Added Hearthgrove Trees, whose logs can be tarred to make an effective fuel
* Added Nibbletwig Trees, whose logs can be crafted into experience-granting sticks
* Added Seeded Hangers, which grow on Giant Weedwood Trees and drop White Pear Seeds
* Added Mud Brick Roof sloped blocks
* Mire Snail Eggs can now be picked up/placed down as edible items, and be cooked into Cooked Mire Snail Eggs
* Added Weeping Blue Petal Salad and Mire Scramble
* Added Thunderstorm event featuring lightning
* Added Winter seasonal event with new textures, Black Ice, and randomly appearing Presents containing unique goodies
* Added Snowfall event that occurs during Winter
* Re-implemented Herblore and all parts related/linked to it (Dreadful Peat Mummy, Aspectrus Plant, Repeller, decay regeneration, etc.)
* Re-implemented Puddles during Heavy Rain
* Re-implemented Mossy and Cracked Limestone Bricks with recipes

Changes

* Obviously updated to Minecraft 1.12.2
* Completely retextured Algae in all ways possible
* Retextured the Rubber Tree Plank Door
* Renamed Gas Cloud to Shallowbreath
* The Betweenlands now has proper lighting
* Geckos and Fire Flies will now seek shelter from rain
* Lowered Pyrad spawn rate near Giant Weedwood Trees
* Improved Dragonfly idle animations
* Sporelings now have a chance to spawn riding a Gecko
* Wights can now buff Swamp Hags by possessing them
* Decreased Peat Mummy damage
* Tweaked flying mob AI
* Hostile mobs now drop Candies during the Spook event
* Most Logs can now be crafted into a variant with bark on all sides
* Coarse Swamp Dirt can now be crafted and has a slightly altered texture
* Players can now slowly walk through Weedwood Bushes
* Implemented biome foliage colours to many plants and leaves
* Most equipment can now be repaired in the Animator
* Middle Gems now have both offensive and defensive bonuses
* Increased Lore Scrap and Aspectrus Seeds drop rate
* Reduced Pot of Chance hardness
* The Hag Hacker now acts like an axe in that it can disable shields
* The Shockwave Sword no longer breaks, but becomes unusable at 0 durability and must be repaired
* Angry Pebbles now have a warning period before being thrown
* Slightly reduced Ring of Ascent flight speed
* Two rings can now be equipped at once
* Gecko Cage now spawns the Gecko when broken
* Blocks of Octine now give off light and burn Moss
* Rubber Taps now visibly pour so that when the tap is full can be gauged
* Many shields now have special abilities
* Mud Bricks and Mossy Cragrock now support plant growth
* Reduced placed Dentrothyst Vial/Aspect Vial size and gave them a random offset
* Grinding items can now be input on the side of the Mortar
* Infusion Buckets can now be emptied by shift-right clicking on a block
* Put tooltips on many more items
* Implemented a Caving Rope indicator and a keybind to connect/disconnect it
* Rewrote Herblore Book Infusion descriptions and some ingredient descriptions
* Implemented Herblore Book merging recipe
* Reduced Poison Ivy and Nettles gen rate
* Increased Mushrooms, Volarpad, Pitcher Plant, Venus Fly Trap, and Weedwood Bush gen rate
* Added underground Hangers gen
* Increased Underground Ruins gen rate
* Decreased Syrmorite Ore and Octine Ore gen rate
* Octine Ore now only generates further down
* Renamed Abandoned Shack to Ruins
* Implemented world locations for Idol Head Statues and Underground Ruins
* Increased Cragrock Tower generation rate
* Made Heavy Rain more common
* Adjusted some food saturation values
* Adjusted some recipe outputs
* Increased Food Sickness limits
* Implemented menu music and three new ambient tracks
* Tweaked some sounds
* Removed Stagnant Water glow
* Implemented more JEI recipe integration
* Re-enabled Animator custom recipes
* Implemented various new config options

Bug Fixes

* Fixed foot Leeches
* Fixed rendering of underwater plants
* Fixed visual issues in Herblore Book
* Fixed Shallowbreath crash
* Fixed picking up liquid with more than one bucket in a stack
* Fixed putting items in output slot of the Mortar
* Fixed blocks haven't incorrect BlockFaceShape's, causing snow and torches to be placable on all sides
* Fixed Moss Bed dropping vanilla Bed
* Fixed Betweenlands Snow having incorrect hardness
* Fixed Rubber Tap still using up Reed Rope
* Fixed Animator taking more than one item when fed by a Hopper
* Fixed Giant Hollow Logs generating incorrectly
* Fixed Sporelings not rotating when falling down
* Fixed Primordial Malevolence blockade not causing damage and suffocating
* Fixed sound not playing when Infusions finish
* Fixed Swamp Hags not knowing how to walk
* Fixed broken Scabyst coating recipe
* Fixed indirect damage sources not working properly with Middle Gems
* Fixed incorrect Weedwood Bush pick item
* Fixed Aspectrus Plant having a way too low growth rate
* Fixed Aspectrus Plant missing collision box
* Fixed some projectiles not blockable by shields
* Fixed BL Fences trying to connect to BL Walls
* Fixed Dark Druid Altar sound only playing once and not stopping properly
* Fixed Aspect Vial amount rounding issue
* Fixed brick and chiseled variant recipes giving too many items
* Fixed crops being harvestable with Sickle or Syrmorite Shears
* Fixed Torches always turning into Damp Torches regardless of dimension
* Fixed modded Torches that extend BlockTorch not turning into Damp Torches
* Fixed Fire Fly, Lurker and Blind Cave Fish AI
* Fixed Weedwood Bow not dealing enough damage
* Fixed Sulfur Furnace slots breaking when putting non fuel items in fuel slot
* Fixed some Stairs in specific rotations having the wrong texture
* Fixed crops getting destroyed when grass spreads to their block
* Fixed Mud Brick Flower Pot plant lighting
* Fixed Weedwood Trees not generating in water
* Fixed placed Dentrothyst Vials/Aspect Vials blocking light
* Fixed Syrmorite Buckets incorrectly collecting from the Infuser
* Fixed Infuser accepting any fluids after being emptied
* Fixed Infuser bubbles and Alembic steam particles
* Fixed a rendering bug caused by calling setBlurMipmap
* Fixed a crash with setting a Dark Druid on fire
* Fixed some lang errors
* Fixed leaves decaying even when placed by the player
* Fixed certain mobs not dropping experience
* Fixed water plants being placeable in liquids other than Swamp Water
* Fixed the Skull Mask not preventing Wights from possessing
* Fixed slab placement and the inability to place redstone/doors on them
* Fixed Lurker Skin Pouches not displaying custom name in GUI
* Fixed Syrmorite Hoppers being able to input invalid items, stack items, and not render with Infuser
* Fixed Fallen Leaves being unharvestable