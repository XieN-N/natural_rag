# Animator

[Aside block] Animator
----------------------

### Transparency

Yes

### Luminance

No

### Hardness

?

### Blast Resistance

10.0

### Tool

Any Pickaxe

### Renewable

Yes

### Stackable

Yes (64)

### Flammable

No

### Compostable

No

### ID

animator

The Animator ingame

The Animator's interface. Each part is colour-coded based on the coloured text to the left.

The **Animator** is a craftable utility block that "animates" items into new or restored forms.

It is primarily used to repair damaged equipment and animate Item Scrolls, among other recipes.

Contents
--------

* 1 Crafting Recipe
* 2 How to Use
* 3 Animating Recipes
* 4 Advancements
* 5 Sounds
* 6 History

Crafting Recipe
-----------------

| Result | Ingredients | Recipe |
| --- | --- | --- |
| **Animator** | Weedwood Planks (3) + Weedwood Stick (2) + Betweenstone (3) + Wight's Heart |  |

How to Use
------------

The Animator's interface can be accessed with right-click. Animating requires the following items:

* An adequately charged Life Crystal or Life Crystal Fragment, placed in the left slot of the interface. The amount of charge required depends on the recipe. Life Crystal Fragments can only contain up to half the charge of a full Life Crystal, and cannot be recharged.
* A varying amount of Sulfur, placed in the right slot. The amount required depends on the recipe.
* The item to be animated, placed in the middle slot.

Once these requirements are met, the Animator will begin consuming the necessary Sulfur. Each Sulfur item takes about 2 seconds to be consumed, so the time taken to finish Animating depends on the amount of Sulfur required by the recipe.

Above the Life Crystal and Sulfur slots are corresponding bars which show how much Life Crystal fuel charge is left and how much time before the next Sulfur item will be consumed. The portion of Life Crystal charge that will be consumed will also preview in the crystal charge bar. The smaller bars connecting the left and right slots to the middle one fill based on how much time is left before the process is complete.

The Animating item/entity will render above the Animator, and Sulfur and Life Crystal fuel will also render in its bottom portion. While animating, white runes will float from the scroll on the Animator to the hovering object, and some steam particles will emanate from the Sulfur. An continuous animation sound will also play.

If the animation process is canceled midway or the Animator runs out of Sulfur, the Life Crystal fuel's charge will not be drained, but any Sulfur already consumed will be lost.

Once the animation process is complete, the Life Crystal fuel's charge will drain. If the result is an item, it can be retrieved from the same middle slot in the interface. If it is an entity, it will be spawned directly on top of the Animator.

Animating Recipes
-------------------

To view all default Animating recipes, visit the Animating page.

Players can add their own Animating recipes in the recipes.json in the config.

Advancements
--------------

| Advancement | In-game Description | Parent | Actual Requirements | ID |
| --- | --- | --- | --- | --- |
| Gambling Addict | Animate way too many Item Scrolls | Ruined It | Animate 15 Item Scrolls in the **Animator** (does *not* include Fabricated Scrolls) | adventurer /gambling\_addict |

Sounds
--------

| Sound | Subtitles | Source | Description | ID |
| --- | --- | --- | --- | --- |
| https://the-betweenlands.fandom.com/wiki/File:Animator.ogg | Animator hums | Blocks | Plays constantly when the Animator is animating | animator |

History
---------

* Release 3.7.2:
  + Life Crystal Fragments can now be used in place of Life Crystals.
  + Added Advancement.
* Release 3.3.2: Reduced number of rendered items.
* Release 3.3.0: Can now repair most equipment items.
* Alpha 3.0.0: Re-enabled custom recipes.
* Beta 2.0.4: Disabled custom recipes.
* **Beta 1.0.0**: Introduced.