# Rift

[Aside block] Rift
------------------

### Duration

24:00 - 30:00

### Delay Time

10:00 - 15:00

### ID

rift

The narrow, zigzagging Rift variant

The wide-open Rift variant

A medium-sized Rift during sunset

A wide Rift during the night

A wide Rift during midnight

The **Rift** is a cyclical event that occurs frequently in The Betweenlands. It primarily consists of visual changes that affect visibility based on the Daylight cycle of The Overworld.

By default, this event will always be active the first time a player enters the Betweenlands dimension, and will initially last for its maximum duration (30 minutes) before ending. Whether or not it is active upon first loading and how long it initially lasts can be controlled in the mod's config.cfg file.

Contents
--------

* 1 Effects
  + 1.1 Prediction
  + 1.2 Manual Control
* 2 Gallery
* 3 Sounds
* 4 Advancements
* 5 History

Effects
---------

Anywhere from a minute and a half to 4 seconds *before* the Rift event starts (*or* ends), occasional creaking sounds will reverberate throughout the dimension. When the event first starts, a loud tearing sound will play, and a Rift will abruptly appear in a random location in the sky. It can appear as one of three different visual variants: A medium-sized crescent-like split, a very narrow zigzagging crack, or a wide-open break.

The Overworld's Sky will be visible through the Rift, and its current place in the daylight cycle will be reflected accordingly in real time. This includes the Overworld's Sun and Moon, as well as Clouds and stars, which will be visible in their real-time locations (as long as the Rift itself is positioned within that relative location). Note that the ability to see details in the Rift is affected by render distance, and they may not appear if it is too low.

Normally, the Betweenlands has no daylight cycle and is very dark, making it very difficult to see, even with several light sources. The Rift event will increase the sky light on the surface of the dimension, depending on the time of day in the Overworld as shown through the opening:

* If it is night in the Overworld, the Rift provides a small amount of light, enough to see around slightly more and make out further details.
* If it is day in the Overworld, the Rift provides the most amount of light, making it much easier to see.

Note that the additional sky light can vary between the minimum and maximum levels as the sun rises or sets. Also, the visual size of the Rift has no effect on the amount of light it produces.

While the Rift event is primarily visual and the daylight cycle has little effect on mob spawns within the Betweenlands, there are a few minor gameplay changes:

* Fireflies can *only* spawn when the sky light of the dimension is dark enough - specifically, when this event is *not* active, *or* only during the night when it *is* active. However, they can spawn regardless of sky light during the Blood Sky event.
* Pyrads that spawn around Giant Weedwood Trees (*not* from Monster Spawners) will be in their "sleeping" state if they spawn when the sky light of the dimension is bright enough - specifically, during the day when this event is active. Awake Pyrads will also eventually enter their sleeping state if they are not targeting anything and it is bright enough. Otherwise, they will always be awake.
* The Auroras event can only *start* naturally during this event *or* the Winter seasonal event. Note that it can remain active after the Rift has ended.

The Rift will remain in the position that it first appeared for the duration of the event. Once the event ends, the Rift will fade out and disappear, and light levels in the dimension will return to their usual, deep darkness.

### Prediction
The Wind Chime forecast visual for the Rift event

The Rift event can be predicted up to 5 minutes before it starts by a Wind Chime, or up to 10 minutes before if it is attuned to the event.

When forecasting, a forecast visual will emanate from the Wind Chime, and a unique chime jingle sound will play:

| Sound | Subtitles | Source | Description | ID |
| --- | --- | --- | --- | --- |
| https://the-betweenlands.fandom.com/wiki/File:Chimes\_rift.ogg | N/A | Blocks | Plays when a Wind Chime forecasts the Rift event | chimes\_rift |

### Manual Control
The Rift event can be manually turned/toggled on and off using the following command:

```
/blevent <toggle|on|off> thebetweenlands:rift
```

Gallery
---------

A low, medium-sized Rift at night.

A high, medium-sized Rift at night.

A high, medium-sized Rift at day.

A low, wide Rift at sunrise.

A low, wide Rift at day.

A low, wide Rift during the Heavy Rain event.

Sounds
--------

| Sound | Subtitles | Source | Description | ID |
| --- | --- | --- | --- | --- |
| https://the-betweenlands.fandom.com/wiki/File:Rift\_creak\_1.ogg https://the-betweenlands.fandom.com/wiki/File:Rift\_creak\_2.ogg https://the-betweenlands.fandom.com/wiki/File:Rift\_creak\_3.ogg | Sky creaks | Ambient/Environment | Plays randomly in The Betweenlands a short time before the Rift event starts or ends | rift\_creak |
| https://the-betweenlands.fandom.com/wiki/File:Rift\_open.ogg | Rift opens | Ambient/Environment | Plays in The Betweenlands when the Rift event starts | rift\_open |

Advancements
--------------

| Advancement | In-game Description | Parent | Actual Requirements | ID |
| --- | --- | --- | --- | --- |
| In the Air Tonight | Predict a weather event with windchimes | All Over Again | Be near a Wind Chime when it detects an upcoming Event and chimes | craftsman /feel\_it\_coming |

History
---------

* Release 3.7.2:
  + Can now be predicted ahead of time by a Wind Chime.
  + Added Advancement.
* Release 3.3.9: Added new visual Rift variants.
* Release 3.3.1: Introduced.