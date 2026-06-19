# Release 3.4.0

**Release 3.4.0** was a major update to the Betweenlands for Minecraft 1.12.2 that was released on October 25, 2018. It was known as the **Spirits 'n Sprites** update as it added the Spirit Tree, Root Sprites and Boulder Sprites, as well as a variety of new decorative blocks, Menhirs, some special new equipment, and a massive array of changes and bug fixes.

Changelog
---------

*Important: We've removed several unobtainable items and Forge will warn you about that when loading a world from a previous Betweenlands version ("Forge Mod Loader detected missing registry entries..."). That's fine and you can click "Yes".*
*We still recommend you make a backup before updating though (As you always should, anyways! Make yo backups!).*

*Also, this update requires at least Forge 14.23.4.2767.*

### Additions

* Added Nibbletwig Planks and associated; slab, stairs, fence, fence gate, door and trapdoor
* Added Hearthgrove Planks and associated; slab, stairs, fence, fence gate, door and trapdoor
* Added Scabyst building blocks; storage, bricks, slab, stairs, wall, 3 chiseled variations, 2 pitstone variations, door, trapdoor
* Added Amate Paper Panes; 3 variations
* Added Mud Brick Flower Pot with Candle
* Added Mud Brick Shingles block and slab
* Added Root Sprite mob
* Added Boulder Sprite mob
* Added Spirit Tree + associated terrain generation and blocks; Spirit Tree Logs + 3 carved variations, Spirit Tree Leaves, Spreading Sludgy Dirt, Spreading Rotten Bark
* Added Root Pods, which grow Roots and Giant Root (block)s when planted
* Added Spirit Tree Sapling, which grows friendly sentry trees which shoot at hostiles
* Added Small and Large Spirit Tree Face Mask, which can be worn or placed as decorational blocks. Small Masks can be animated and crafted with a Weedwood Shield
* Added Living Weedwood Shield, which shoots at hostiles
* Added Sap Spit, used to breed Mire Snails, heal Geckos, and remove Corrosion on equipment
* Added Bark Amulet, which when worn indicates a mob's health
* Added Spirit Fruit
* Added Menhirs, which generate throughout the world and can be activated for fast travel
* Added Bone Wayfinder, which is used to activate Menhirs
* Added Magic Item Magnet, which can be equipped and will automatically pull items towards the player
* Added Gem Singer, which can locate nearby Middle Gems or Life Crystals
* Added Amate Maps
* Added Dentrothyst Shards
* Added several new config options regarding item black-/whitelists and gamerules (blFoodSickness, blRottenFood, blDecay, blCorrosion, blToolWeakness, blTorchBlacklist, blFireToolBlacklist, blPotionBlacklist, blFertilizerBlacklist) to customize mechanics.
* Added config option to move equipment on HUD to the other side of the hotbar or to disable it completely
* What's a Greebling?

### Changes

* Added rarities to some items
* Added Scabyst to oredict
* Added item sprites to Roots, Stalactites and Life Crystal Stalactites/Ore blocks
* Amate Paper recipe now makes 9, up from 3
* Lurker Skin Pouch can now deposit all items in an inventory by shift-right-clicking on an inventory block and renders on the player
* Lurker Skin Shield can now be used as a raft
* Weedwood Rowboats now protect the rowing player from attacks from below
* Decreased Slimy Bone Ore and Middle Gem Ore generation
* Dug Purified Swamp Dirt now reverts to Swamp Dirt after 3 harvests, and Dug Purified Swamp Grass after 6
* Shields can now be upgraded with Middle Gems
* Tar Beast Hearts can now be crafted
* Caving Rope now has block lighting
* Decreased large Marsh Ruins generation
* Renamed Fire Fly to Firefly for cOnSiStEnCy
* Renamed Ground Tangled Roots to Ground Roots, and made them obtainable from grinding Giant Root
* Updated Chinese translations (thanks RisingInIris2017)
* Lurkers can now exist on peaceful with slightly different AI
* Reduced network traffic from events and locations
* Reorganized some blocks and items in the Creative inventory
* Removed several unobtainable items
* Additional item information regarding Corrosion/Food Sickness and Decay bar are now only shown if those mechanics are enabled
* Dentrothysts now always drop 4 Dentrothyst Shards; 2x2 Dentrothyst Shards can be crafted back into Dentrothyst
* Changed Dentrothyst Vial recipes to use Dentrothyst Shards
* Thrown Infusions now have a chance to drop some Dentrothyst Shards
* Smelting Buckets filled with Rubber now gives 3 Rubber Balls

### Bug Fixes

* Fixed incorrect Life Crystal Ore oredict
* Fixed Polished Dentrothysts dropping wrong item meta
* Fixed Trapdoor rotations and side textures
* Fixed some Buckets not being stackable
* Fixed Weedwood Lever using Betweenstone base
* Fixed Lurker movement in water
* Fixed missing localization entry for mummy arms spawned by the Ring of Summoning
* Fixed rare occurence where single chunks with overworld biomes would generate
* Fixed mobs being able to break blocks in protected locations
* Fixed the Dreadful Peat Mummy not being killable via command
* Fixed TileEntities having incorrect registry name