# Release 3.3.12

**Release 3.3.12** was an update to the Betweenlands for Minecraft 1.12.2 that was released on September 10, 2018. It converted most sounds in the mod from stereo to mono, among adding other changes and bug fixes.

Changelog
---------

### Additions and Changes

* Improved Chiromaw animations
* Added durability bar to Pestle
* Removed block protection from Druid Circle
* Reduced network traffic from events and locations
* Removed Primordial Malevolence force teleporting players back into arena and instead made it regenerate health when no player is nearby
* Converted most sound effects to mono so that they work properly in the game

### Bug Fixes

* Fixed not all variants of logs having oredict
* Fixed portal generation with Cubic Chunks mod (thanks Foghrye4)
* Fixed potential memory leak when unloading chunks (couldn't reproduce but should be fixed)
* Fixed Octine Sword not setting mobs on fire
* Fixed Life Crystal Ore not glowing
* Fixed shader lighting rendering through opaque block overlays
* Fixed custom portal allowing to teleport to itself
* Fixed custom portals leading to the End spawning at incorrect positions
* Fixed one Marsh Ruins variant not generating
* Fixed Repeller shield being culled while still visible
* Fixed Rift not open when generating world