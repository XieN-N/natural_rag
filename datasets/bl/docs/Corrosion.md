# Corrosion

**Corrosion** is a mechanic that affects some Betweenlands equipment while in The Betweenlands, reducing its effectiveness over time.

Contents
--------

* 1 Description
* 2 Preventing Corrosion
  + 2.1 Purification
  + 2.2 Coating
  + 2.3 Direct Removal
  + 2.4 Other Methods
* 3 Advancements
* 4 History

Description
-------------

While in the dimension, Tools and Weapons (encompassing Shovels, Pickaxes, Axes, Swords and other melee weapons, Bows, the Simple Slingshot, and the Sickle) from the Betweenlands will slowly corrode over time. Note that non-Betweenlands equipment does not corrode.

Corrosion is a value between 0 and 255 (stored as "Decay" as item NBT data). The exact value out of 255 can be viewed as a tooltip on the affected item when Advanced Tooltips are toggled on (F3+H). Otherwise, corrosion is represented by six different texture overlays, becoming more grimy as it progresses, along with six tooltips for each stage:

* ***Good as new!***: 0-42 Corrosion points
* ***Slightly corroded***: 43-84 Corrosion points
* ***Moderately corroded***: 85-127 Corrosion points
* ***Very corroded***: 128-169 Corrosion points
* ***Extremely corroded***: 170-212 Corrosion points
* ***Completely corroded***: 213-255 Corrosion points

As items corrode, equipment attack damage and block breaking effectiveness are gradually reduced, down to 50% when completely corroded. The maximum power of Bows and the Simple Slingshot is reduced by 15%. The Sickle has a chance to not drop anything when harvesting plants, with the chance of failure increasing as the tool corrodes.
The probability of a corrodable item corroding in any given second is 4.88%. If the player is in water it is 13.98%, and if the player is currently using or swinging the item the previously stated probabilities are multiplied by 1.025, becoming 5% and 14.33% respectively. The higher a tool's corrosion level, the closer the probability is to being halved.

Preventing Corrosion
----------------------

There are three primary ways of preventing or removing Corrosion.

### Purification
Purifier

Corroded items can be "purified" within a Purifier, at the cost of Sulfur and some Swamp Water. Purifying an item resets its corrosion value back to 0. Any Scabyst coating on the item will not be removed in the process.

| Result | Ingredients | Recipe |
| --- | --- | --- |
| Removes **Corrosion** from corresponding Tool or Weapon | Any corroded Tool or Weapon + Sulfur + Swamp Water (250 mB) |  |

### Coating
Scabyst

Corrodable items can also be coated with Scabyst to keep the item's Corrosion from increasing any further until the Scabyst coating eventually wears off. Coated items can still have their corrosion level *decreased* by other methods, without removing any Scabyst coating on the item in the process.

Coating, similar to corrosion, is a value between 0 and 600 on equipment, initially at 0. The exact value out of 600 can be viewed as a tooltip on the affected item when Advanced Tooltips are toggled on (F3+H). Otherwise, coating is represented by four tooltips for each stage:

* ***Barely any coating left***: 0-99 coating points
* ***Slightly coated***: 100-199 coating points
* ***Moderately coated***: 200-399 coating points
* ***Well coated***: 400-600 coating points

Each piece of Scabyst applied to the equipment gives it 75 coating points, and any number between 1 and 8 can be crafted with the equipment at once. The points will deplete over time, and as long as the coating value is above 0, the equipment's corrosion level will not increase any further. The equipment will stay coated until the coating points are fully depleted.

| Result | Ingredients | Recipe |
| --- | --- | --- |
| Coats corresponding Tool or Weapon (75 points per piece) | Any corrodable Tool or Weapon + Scabyst (1-8) |  |

### Direct Removal
 File:LargeSapSpit.png 

Sap Spit

Similarly to Scabyst coating, corrodable items can be applied with Sap Spit to directly remove a specific amount of Corrosion from the item.

Each item of Sap Spit applied to the equipment removes 85 Corrosion points, and any number between 1 and 8 can be crafted with the equipment at once. Any Scabyst coating on the item will not be removed in the process.

| Result | Ingredients | Recipe |
| --- | --- | --- |
| Removes **Corrosion** from corresponding Tool or Weapon (85 points per item) | Any corroded Tool or Weapon + Sap Spit (1-8) |  |

### Other Methods
Only items in a *player's inventory* have the chance to corrode. Items do not corrode if they are inside a container, such as a Weedwood Chest, but will resume corroding upon being taken out.

Betweenlands equipment will also stop corroding if the player leaves The Betweenlands dimension or enters Creative Mode.

Combining equipment in the Crafting grid also resets the resulting tool's Corrosion value to 0.

Advancements
--------------

| Advancement | In-game Description | Parent | Actual Requirements | ID |
| --- | --- | --- | --- | --- |
| Hardware Laundry | Purify your tools | Survivalist | Purify any **corroded** and uncoated Betweenlands Equipment in the Purifier, and take it out of the output slot | survivalist /hardware\_laundry |
| Onions Have Layers, Tools Alike | Coat your tools against **Corrosion** | Hardware Laundry | Craft any **corrodable** Betweenlands Equipment with Scabyst | survivalist /onions\_have\_layers |

History
---------

* Release 3.4.0: Corrosion can now be removed using Sap Spit.
* Release 3.3.0: Added Advancements.
* **Beta 1.0.0**: Introduced.