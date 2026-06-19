# Release 3.3.11

**Release 3.3.11** was a small update to the Betweenlands for Minecraft 1.12.2 that was released on July 29, 2018. It removed the need to manually delete the core jar file after removing the mod from the mods directory, among adding other small tweaks and bug fixes.

Changelog
---------

### Additions and Changes

* Core jar will no longer have to be deleted when updating as of this version (however previous left over core jar files still need to be deleted manually, sorry!)
* Adjusted Dreadful Peat Mummy walking animation

### Bug Fixes

* Fixed server only version trying to load when installed on client
* Fixed Mortar causing crash when looking at certain items in JEI
* Fixed some shader textures uninitialized in first frame when loading world causing a crash with Optifine
* Fixed Portal Tree replacing unbreakable blocks such as Bedrock
* Fixed player mounting Harlequin Toad when healing with Dragonfly Wings
* Fixed Harlequin Toad healing causing a null stack crash in a specific situation