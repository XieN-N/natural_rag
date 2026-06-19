# Configuration

The Betweenlands has its own configuration file that can be used to toggle and alter certain parts of the mod.

To access the config folder, go into your computer's search tab or file navigator and type %AppData%. When the folder list comes up, navigate to Roaming/.minecraft/config/thebetweenlands.

Configurable Options
----------------------

You can edit specific options and IDs in the file called "config.cfg", found in the thebetweenlands config folder; open this file using Notepad or another text program. The base options you can edit are as follows:

* "Betweenlands Main Menu": Toggles whether or not the game will load the Betweenlands' custom main menu on the menu screen. Parameter options are ***true*** or ***false***, default is true.
* "Debug menu on start": Toggles access to the Betweenlands debug menu for testing purposes. Parameter options are ***true*** or ***false***, default is false.
* "Debug mode": Toggles the Betweenlands debug mode for testing purposes. Parameter options are ***true*** or ***false***, default is false.
* "Rowboat view": Toggles the automatic transfer to the F5 (third person) mode whenever the player enters a Weedwood Rowboat; when set to false, it will keep them in first person mode. Parameter options are ***true*** or ***false***, default is true.
* "potion effects": The complete list of effect IDs used by Infusions. The numbers can be changed to change the IDs and solve potion ID conflicts with other mods, but the maximum number you can set any ID to is 127. Make sure that no two effects use the same ID number.
* "Firefly block lighting": Toggles whether or not fireflies will emit orange shader light. Parameter options are ***true*** or ***false***, default is true. Note that this option is forced on IF shaders are set to true. For those with shader issues it is recommended to turn this and shaders to false.
* "Sky texture resolution": Sets the resolution of the custom Betweenlands sky. Parameter options are **appropriate resolution numbers**, default is 1024. Note that shaders MUST be enabled for this to take any effect.
* "Use shaders for rendering": Toggles the use of custom shaders in the Betweenlands dimension. This includes various aesthetic improvements such as colored and dynamic light, but will cost performance and as such for those with lag issues or problems with shaders in general it is recommended to turn this to false. Parameter options are ***true*** or ***false***, default is true. Note that if true, it will force firefly block lighting to be true as well.
* "Wisp rendering quality": Sets the quality that Will o' the Wisps are rendered at. Parameter options are numbers **0-100**, default is 100; quality increases as number increases.
* Biome and dimension IDs: The complete list of biome and dimension IDs used by the mod. The numbers can be changed to change the IDs and solve biome or dimension ID conflicts with other mods. Note that if biome ID limit is set to true, numbers cannot exceed 127, and make sure that no two effects use the same ID number.
* "Biome ID limit": Prevents any biome ID set in the config from exceeding 127, preventing possible issues with the biome generation. **IT SHOULD ONLY BE TURNED TO FALSE IF YOU KNOW WHAT YOU'RE DOING.** Parameter options are ***true*** or ***false***, default is true.
* "Dimension brightness": Sets how dark the average lighting in the Betweenlands is. Parameter options are numbers **0-100**, default is 75; brightness increases as number increases.
* "Frequency of druid circles": Sets the number of tries per chunk that the Overworld attempts to generate Druid Circles in swamp-type biomes. It can be set to any number; the number of tries decreases as number increases. Default (normal) generation is 100.

Custom Recipes
----------------

The Betweenlands adds a way for users to add recipes to the machines it adds. The compatible machines are: the Purifier, Mortar, Compost Bin, Animator, and Dark Druid Altar.

How each of these works can be found elsewhere. In your config folder there will be a folder called "thebetweenlands" and in this folder you have to create a file called recipes.json. To add recipes, you need to edit this file and put some basic stuff in there. Before we go into the specifics, there are a few things that are easier said beforehand.

There are a few basic structures that most recipes use:

Item template:

```
//The item ID
"id": "domain:name",
//The metadata/damage. Optional - if not specified is 0 for outputs and 'any' for inputs
"meta": 42,
//The NBT. Make sure quotation marks ("") are escaped. Optional.
"nbt": "{Tag: \"Value\"}",
//Item stack size. Optional - 1 if not specified
"size": 16
```

Entity template:

```
//The entity ID
"id": "EntityID",
//The NBT. Make sure quotation marks ("") are escaped. Optional.
"nbt": "{Tag: \"Value\"}"
```

Now that those are explained, let's get into the specifics.

**Compost Bin recipes:**

Adding compost recipes is quite easy. These recipes take an input (item and composting time), and an output (compost amount).

* Composting time defines the time it will take for an item to turn into compost. This number is in ticks (20 ticks = 1 second)
* Compost amount is the amount of compost it will create. The compost bin can hold a maximum of 100 compost and uses 20 to make a compost item.

Compost recipes can be added as follows:

```
"compost_bin": [
  {
    "input": {
      "item": {
        //Item template goes here
      },
      //Time it takes to turn into compost
      "composting_time": 40
    },
    //How much compost is created
    "output": 20
  }
]
```

**Mortar recipes:**

Adding pestle and mortar recipes is easy. These recipes require only the basic tags: input (item) and output (item).

Mortar recipes can be added like this:

```
"pestle_and_mortar": [
  {
    "input": {
      //Item template goes here
    },
    "output": {
      //Item template goes here
    }
  }
]
```

**Purifier recipes:**

Adding purifier recipes is almost exactly the same as Mortar recipes:

```
"purifier": [
  {
    "input": {
      //Item template goes here
    },
    "output": {
      //Item template goes here
    }
  }
]
```

**Animator recipes:**

Adding animator recipes are a bit more complicated. These recipes require an input (item, fuel amount and life amount) and either one item output, an entity output or both.

Life amount and fuel amount are, respectively, the amount of Sulfur and amount of Life Crystal that will be consumed.

Adding a recipe with an entity as output works like this:

```
"animator": [
  {
    "input": {
      "item": {
        //Item template goes here
      },
      //Amount of fuel
      "fuel": 8,
      //Amount of life crystal
      "life": 4
    },
    "output_entity": {
      //Entity template goes here
    },
    //Specify which entity should be rendered. Optional.
    "rendered_entity": "thebetweenlands:swamp_hag"
  }
]
```

Adding a recipe with an item as output is almost the same:

```
"animator": [
  {
    "input": {
      "item": {
        //Item template goes here
      },
      //Amount of fuel
      "fuel": 8,
      //Amount of life crystal
      "life": 4
    },
    "output": {
      //Item template goes here
    }
  }
]
```

You can also specify both "output" and "output\_entity" at once.

**Animator reparing recipes (coming in version 3.3.0+):**

Once version 3.3.0+ is released you will be able to add custom recipes for item repairing in the animator.

Life amount and fuel amount are, respectively, the amount of Sulfur and amount of Life Crystal that will be consumed.

The required amounts are linearly interpolated between the minimum and maximum amounts depending on how damaged the item is.

```
"animator_repairable": [
  {
    "input": {
      "item": {
        //Item template goes here
      },
      //Minumum amount of fuel required to repair the item
      "min_fuel": 2,
      //Mimumum amount of life crystal required to repair the item
      "min_life": 4,
      //Amount of fuel required to repair the item if it is fully broken
        "max_fuel": 32,
      //Amount of life crystal required to repair the item if it is fully broken
      "max_life": 60
    }
  }
]
```

**Dark Druid Altar recipes:**

Adding druid altar recipes requires 4 inputs (item) and one output:

```
"druid_altar": [
  {
    "input": {
      "item_1": {
        //Item template goes here
      },
      "item_2": {
        //Item template goes here
      },
      "item_3": {
        //Item template goes here
      },
      "item_4": {
        //Item template goes here
      }
    },
    "output": {
      //Item template goes here
    }
  }
]
```

**Example file:**

Here's an example file that you can try out yourself:

```
{
  "purifier": [{
    "input": {
      "id": "minecraft:stone"
    },
    "output": {
      "id": "minecraft:dirt",
      "meta": 2,
      "size": 4,
      "nbt": "{display: {Name:\"Magical Podzol\", Lore:[\"Such cool\", \"much wow\"]}}"
    }
  }],
  "animator": [{
    "input": {
      "item": {
        "id": "minecraft:stone"
      },
      "fuel": 8,
      "life": 4
    },
    "output_entity": {
      "id": "thebetweenlands:swamp_hag",
      "nbt": "{Attributes: [{Name:generic.maxHealth, Base:2}], CustomName:\"Weak Swamp Hag\", CustomNameVisible:1}"
    },
    "rendered_entity": "thebetweenlands:swamp_hag"
  }],
  "animator_repairable": [{
    "input": {
      "item": {
        "id": "minecraft:diamond_sword"
      },
      "min_fuel": 2,
      "min_life": 4,
      "max_fuel": 32,
      "max_life": 60
    }
  }],
  "compost_bin": [{
    "input": {
      "item": {
        "id": "minecraft:dirt",
        "meta": 2
      },
      "composting_time": 40
    },
    "output": 20
  }],
  "druid_altar": [{
    "input": {
      "item_1": {
        "id": "minecraft:stone"
      },
      "item_2": {
        "id": "minecraft:dirt"
      },
      "item_3": {
        "id": "minecraft:grass"
      },
      "item_4": {
        "id": "minecraft:cobblestone"
      }
    },
    "output": {
      "id": "minecraft:diamond"
    }
  }],
  "pestle_and_mortar": [{
    "input": {
      "id": "minecraft:stone"
    },
    "output": {
      "id": "minecraft:cobblestone"
    }
  }, {
    "input": {
      "id": "minecraft:cobblestone"
    },
    "output": {
      "id": "minecraft:dirt"
    }
  }, {
    "input": {
      "id": "minecraft:dirt"
    },
    "output": {
      "id": "minecraft:sand"
    }
  }]
}
```