# Release 3.4.7

**Release 3.4.7** was a small update to the Betweenlands for Minecraft 1.12.2 that was released on June 6, 2019. It implemented a new block model texture packing system, as well as some more configuration options and bug fixes.

Changelog
---------

### Changes

* Block model textures are now packed, significantly reducing the space used on the texture atlas. May slightly improve performance on graphics cards that are slow at updating textures for texture animations
* Tamed Small Spirit Tree Faces now no longer instantly despawn when collided with another entity or being in an invalid position, instead they drop to the ground and teleport to nearby Spirit Tree Logs if available
* Decay now uses an Attribute Modifier for the health reduction, improving compatibility with other mods that change the max health
* Several small optimizations, especially regarding capability tick time
* Added option to enable Food Sickness in The Overworld
* Added options to change Decay bar position on HUD
* Added option for percentual Decay health decrease

### Bug Fixes

* Fixed Syrmorite Buckets no longer stackable after having removed Solid Rubber from them
* Fixed Rotten Food and Tainted Potions sometimes displaying item names incorrectly
* Fixed a bug with XP consumption from Rings and Bone Wayfinder