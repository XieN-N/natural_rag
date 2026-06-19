# Middle Gem Circle

Gems circling the player when an Amulet is equipped

The **Middle Gem Circle** is a rock-paper-scissors type combat/PvP mechanic used to upgrade equipment.

Contents
--------

* 1 Description
  + 1.1 Upgrading Amphibious Armor
  + 1.2 Other Mobs
* 2 Application Recipes
* 3 History

Description
-------------

Middle Gems can be applied via crafting to most Tools and Weapons (encompassing Shovels, Pickaxes, Axes, Swords and other melee weapons, and Bows), Shields, Armor, and empty Amulets. These apply combat bonuses to the equipment, which have a chance to take effect when either the corresponding tool deals damage, the corresponding armor piece is damaged, or the corresponding shield blocks an attack. Each gem has an offensive and defensive bonus, and which one is used depends on if the gem is applied to a tool/weapon (offensive) or armor piece/shield (defensive). However, Amulets give both offensive *and* defensive bonuses, although they trigger independently. Stacking multiple pieces of equipped gear with the same gem applied increases the chances of the appropriate bonus triggering, as well as the power of its effects (to a limit).

The following are each of the Middle Gems and their offensive and defensive bonuses:

| Middle Gem Bonuses | | | |
| --- | --- | --- | --- |
| **Middle Gem** | **Offensive Bonus** | **Defensive Bonus** |
| Aqua Middle Gem | Has a chance to apply the  Weakness effect to the target when attacking, decreasing the damage they deal.  The potency of the Weakness effect increases the more damage was dealt, as well as with more stacks of the same gem. It caps at a maximum potency of III and lasts for 4 seconds at potency I, but only 2 seconds at potency II or higher. | Has a chance to provide the  Resistance effect when attacked/blocking, boosting defense.  The potency of the Resistance effect increases the more damage was taken/blocked, as well as with more stacks of the same gem. It caps at a maximum potency of III and always lasts for 6.5 seconds. |
| Crimson Middle Gem | Has a chance to inflict extra knockback to the target and provide the  Strength effect to the attacker when attacking, increasing the damage they deal.  Both the amount of knockback dealt and the potency of the Strength effect increase the more damage was dealt, as well as with more stacks of the same gem. The Strength effect caps at a maximum potency of III and always lasts for 5.5 seconds. | Has a chance to inflict knockback and reflect damage back upon the attacker when attacked/blocking (similar to the vanilla Thorns enchantment).  Both the amount of knockback dealt and the percentage of initial damage reflected back increase the more initial damage was taken/blocked, as well as with more stacks of the same gem. The reflected damage caps at a maximum amount of 66% (or 2/3) of the initial damage. |
| Green Middle Gem | Has a chance to heal the attacker when attacking.  The amount of health restored is at least 1 health (), but is generally 45% of the damage that was dealt. It increases with more stacks of the same gem, and caps at a maximum amount of 10 health (). | Has a chance to provide the  Absorption effect when attacked/blocking, providing temporary additional hearts.  The potency of the Absorption effect increases the more damage was taken/blocked, as well as with more stacks of the same gem. It caps at a maximum potency of III and always lasts for 13 seconds. |

Middle Gems are also stronger against some gems and weaker against others, in a rock-paper-scissors-like circle - using a gem-affected weapon (offensive) against a gem-protected player or mob (defensive) will modify the total damage dealt based on the circle. For example, using a sword with a Crimson Gem against a player equipped with an Aqua Gem Amulet will deal less damage than usual, whereas using a sword with a Green Gem will deal more damage than usual. Like the other bonuses, the damage modification increases with more stacks of the same gem. Damage is unchanged when either the attacker or the receiver is not using any gems, or if they are both using the exact same type/s of gem.

A demonstration of the Middle Gem Circle. Each gem is stronger against the gem it is pointing to, but weaker against the one pointing to *it*.

The strengths and weaknesses of each gem are as follows:

* Aqua Gems are stronger against Crimson Gems, but weaker against Green Gems.
* Crimson Gems are stronger against Green Gems, but weaker against Aqua Gems.
* Green Gems are stronger against Aqua Gems, but weaker against Crimson Gems.

The Middle Gem applied to the equipment can be seen in the equipment's tooltip, whereas the bonuses provided can be seen on the gem's own tooltip.

Equipped Middle Gems appear visually on the texture of many weapons and most armor pieces, and worn Amulets show the respective gem floating around the player in a circle for each Amulet worn. Equipped Amulets are also displayed to the right of the player's hotbar.

The number of Amulets a player can wear at a time can be increased with an Amulet Slot, up to a maximum of 3 Amulets, although these extra slots disappear if the player dies.

Middle Gems *can* be applied to non-Betweenlands equipment, although they will never appear on the item's texture.

### Upgrading Amphibious Armor
Middle Gems can be applied onto Amphibious Armor, but instead of being crafted with the armor piece, they must be placed in one or more of its upgrade slots (up to 3 can be placed in each slot). Each slot with a Middle Gem upgrade gives the armor piece the same bonuses as the gem would normally provide when equipped. Only one type of Middle Gem can be used to upgrade per armor piece, but multiple of the same type can be used, although the effects do not stack.

Amphibious Armor will utilize the Middle Gems like any other upgrade, meaning each gem item at the top of an upgrade stack will receive durability damage when the armor itself is damaged, and will retain this durability loss even if taken out of the armor, becoming unstackable with other Middle Gem items even of the same type. Each item has a maximum durability of 64 before breaking, and the armor will then start using the next item down if it was stacked.

### Other Mobs
Swamp Hags, Wights, Tar Beasts, Peat Mummies, and the Dreadful Peat Mummy can rarely spawn with one or more Middle Gem Amulet affects, which work the same as they do on a player. Like an Amulet-wearing player, the applied Middle Gems can be seen circling the mob.

Middle Gem Amulets can also be equipped onto player-serving mobs (Tar Minions and tamed Harlequin Toads). Amulet Slots can also be used to increase the number of amulets that can be applied to any given mob, although this currently only works for Tar Minions(verify?).

Application Recipes
---------------------

| Result | Ingredients | Recipe |
| --- | --- | --- |
| Applies corresponding Middle Gem to corresponding Tool or Weapon | Shapeless: Any Tool or Weapon + Any Middle Gem |  |
| Applies corresponding Middle Gem to corresponding Shield | Shapeless: Any Shield + Any Middle Gem |  |
| Applies corresponding Middle Gem to corresponding Armor piece | Shapeless: Any applicable Armor piece + Any Middle Gem |  |
| Applies corresponding Middle Gem to Amulet | Shapeless: Amulet (empty) + Any Middle Gem |  |

History
---------

* Release 3.4.0: Now applies to shields.
* Alpha 3.0.0: Now provides both offensive and defensive bonuses.
* Beta 2.0.0: Now applies to bows.
* **Beta 1.0.0**: Introduced.