# Release 3.3.1

**Release 3.3.1** was an update to the Betweenlands for Minecraft 1.12.2 that was released on March 4, 2018. It added the Rift event and its day/night cycle, the Smol Sludge mob, and many other changes and bug fixes.

Changelog
---------

### Additions and Changes

* Added sky Rift event and new day/night cycle
* Added minimum Forge version requirement (14.23.1.2602)
* Added config option to override any (including modded) conflicting oredict recipes
* Added decay food tooltip
* Added overworld tool damage reduction particles and sound effects
* Added random cave ambience sounds
* Added config option to log recipe overrides
* Added tooltips to all Infusions
* Added glint effect to Infusions
* Added visual Aspect liquid to Repeller
* Added Smoll Sludge mob
* Added Sludge Trail attribute to Sludge and Smoll Sludge
* Added textures for cut (ie placed by player in survival) Rubber Tree Log
* Added config updater, enabling the mod to automatically update outdated configs
* Changed config properties key names
* Improved visibility of liquid in Aspect Vials
* Poisonous Frogs can now poison players even when on easy difficulty
* Improved Cragrock Tower crumble trigger, now only triggers when the tower is conquered and no players are left at the top
* Players are now rewarded 350 XP upon conquering a Cragrock Tower
* Sneaking now cancels the effect of the Boots of the Marsh Runner
* Fire Flies now only spawn when it's night or the Rift is inactive
* Portals can now be linked together if they are within 500 blocks of each other by right-clicking on them with a Swamp Talisman
* Portals can now work in any dimension and a config whitelist determines which dimensions the portals work
* Pyrads are now always active during night or when the Rift is inactive
* Improved portal generator, should now be able to deal with almost any terrain (including the Nether e.g.)
* Adjusted various Infusion stats
* Reduced amount of Aspects the Aspect Vials can hold
* Decreased required amount of Aspects to create Infusions with high potency or duration
* Random position of Aspect Vials can now be toggled by shift-right-clicking on the block
* Ring of Ascent is now automatically disabled when riding an entity
* Reduced dig speed of overworld tools
* Shockwave of Shockwave Sword can now damage the Primordial Malevolence's Energy Fields once again

### Fixes

* Fixed some minor localization errors
* Fixed displayed attack damage on item not affected by corrosion
* Fixed Boots of the Marsh Runner losing gem on crafting
* Fixed Swamp Hags hesitating to attack the player after being hit
* Fixed items in Item Shelf rendering mirrored
* Fixed Swamp Tallgrass dropping Leaves
* Fixed decay breaking player's health when other mods also modify health (such as the Ring of Odin from Botania)
* Fixed Chiromaws targeting and attacking through solid walls
* Fixed Aspectrus Plant sometimes destroying fences
* Fixed Aspectrus Plant sometimes dropping too many items
* Fixed way too high capacity in Aspect Vials allowing to create broken Infusions
* Fixed thrown Infusions not rendering
* Fixed Repeller not saving accumulated aspect cost
* Fixed Betweenlands Monster Spawner showing incorrect entity when placed
* Fixed Animated Tar Beast Heart animator recipe rendering Tar Minion