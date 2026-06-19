# Rotten Food

[Aside block] Rotten Food
-------------------------

### Type

Consumable

### Restores

–1 hunger (-)

### Saturation

1

### Effects

Poison II (0:10)  
 Hunger II (0:10)

### Renewable

Yes

### Stackable

Yes (64)

### Compostable

No

### ID

rotten\_food

**Rotten Food** is a food item that results from bringing non-Betweenlands food to the Betweenlands. It is meant to encourage finding other sources of food *from* the Betweenlands.

Contents
--------

* 1 Obtaining
  + 1.1 The Betweenlands
* 2 Properties
  + 2.1 Consuming
  + 2.2 Reverting
* 3 Advancements
* 4 Notes
* 5 History

Obtaining
-----------

### The Betweenlands
While in The Betweenlands, most food from other dimensions in the player's inventory will instantly turn into Rotten Food. The original food's identity will be retained and displayed in parentheses as part of the item name, and the size of the food stack will remain intact.

While the food rotting mechanic is on by default, the mod's config.cfg file can be used to disable or reenable it. The config can also be used to blacklist additional items to turn into Rotten Food, or whitelist specific items to *not* turn into Rotten Food.

Items do not become Rotten Food while in Creative Mode.

Properties
------------

### Consuming
When eaten, Rotten Food *depletes* 1 hunger and restores 1 saturation. It also inflicts the  Poison II and  Hunger II effects for 10 seconds each. It can be eaten even if the player's hunger bar is full.

Unlike most other foods, Rotten Food is not affected by Food Sickness.

### Reverting
If Rotten Food is returned to a dimension other than The Betweenlands, it will revert back to its original food item, retaining its stack size.

This functionality is on by default, and can be disabled or reenabled in the mod's config.cfg file.

Advancements
--------------

| Advancement | In-game Description | Parent | Actual Requirements | ID |
| --- | --- | --- | --- | --- |
| You Are What You Eat | Consume **Rotten Food** | Survivalist | Same as description | survivalist /you\_are\_what\_you\_eat |

Notes
-------

* By default, Rotten Flesh is the only non-Betweenlands food item that does not turn into Rotten Food.
* Similarly to Rotten Food, Potions from outside of The Betweenlands turn into Tainted Potions while in the dimension.

History
---------

* Release 3.3.7:
  + Added more config entries for Rotten Food.
  + Added localization for Rotten Food with no original item assigned to it.
* Release 3.3.5: Added more config options regarding Rotten Food.
* Alpha 3.2.0:
  + Added config for Rotten Food whitelist.
  + Cake now turns into Rotten Food in the Betweenlands.
* Beta 1.0.1: Removed food sickness tooltip.
* **Beta 1.0.0**: Introduced.