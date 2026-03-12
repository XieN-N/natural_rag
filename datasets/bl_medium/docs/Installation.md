# Installation

The Betweenlands mod is currently in active development. While the experience is mostly fleshed out and playable with minimal stability issues, keep in mind that it is still not finished.

Contents
--------

* 1 Installation
  + 1.1 Forge
  + 1.2 Github
* 2 Compatibility
* 3 Modpack Policy

Installation
--------------

Installation is relatively simple, generally the same as any other minecraft mod.

There are two ways to download The Betweenlands, through the Curse Forge site, or Github. Note that Betweenlands requires Minecraft Forge for 1.12.2 first, generally the most up to date 1.12.2 version.

The Official Betweenlands Discord Server also has a support section for questions, along with a list of Frequently Asked Questions pinned in said channel. Please check the FAQ first before asking a question to see if it's already been answered.

### Forge
You can download the mod from the Curse Forge site, found here, where official releases and updates are uploaded. Simply click Download for the latest build, and then drop the downloaded file into the .minecraft/mods folder like with other mods, and run Minecraft with Forge through the launcher. Although this is a simpler process and provides a more stable version, it is not always the most up-to-date as beta versions of updates are often released on Github first.

### Github
The mod is also available for download on Github, and development of the mod is committed there whenever it is worked on. If you want to play the absolute latest versions, you can follow these steps (for Windows). Note that this is a lengthier, more confusing process, the version may be more unstable.

This process requires the Java SDK, found here. After installing it, follow these steps to set it up properly:

1. Go to the Github repository link, found here. You can do one of two things here. You can click Download ZIP near the top-right corner to download the .zip directly. Alternatively, if you have Github Desktop installed, you can press the clipboard-shaped button to the left of the download button, press the plus sign at the top left corner of the Desktop program, tab to Create, and paste the repository link you copied in the empty bar (you can also choose the file path you want it to install to from here). Through this second method you can simply press "Sync" on the program whenever the repository updates to get the latest code without having to redownload, but it is entirely optional.
2. Navigate to the .zip you downloaded and extract it to somewhere on your computer using your choice of extractor program, such as WinRAR, 7zip or just Windows 10's built in .zip extraction (this step is only necessary if you have downloaded it directly from the Github website).
3. After unzipping/syncing the BL download, you'll get a folder named The-Betweenlands or The-Betweenlands-master. Shift-right click on the folder. There should be an option to open command prompt there, just click on that and then you have your file location. Then type 'gradlew build' after the line in your command prompt, press enter, and the build will begin compiling. After a certain amount of time it will be done and you can close the command prompt.  
   The universal .jar should end up in build>libs.
4. Navigate to your .minecraft directory. This can be found by typing "%AppData%" (without quotes) into the start menu. From there, click Roaming, and then .minecraft.
5. If you don't already have a mods folder under .minecraft, click new folder and name it "mods" (again, without quotes). Drop the .zip file you found into the mods folder.
6. Start the Minecraft launcher. Click the arrow to the right of the Profile bar and select the version of Forge you downloaded. Then launch the game.
7. Success!

Compatibility
---------------

As the Betweenlands is run on Minecraft Forge, it is compatible with almost any other 1.12.2 forge mod. Notable incompatible mods or types of mods are shown below:

* Shader mods: If you are using outside shader mods with the Betweenlands mod, you may experience visual glitches and issues, as the Betweenlands uses its own custom shaders which conflict with outside shaders. This includes Optifine.
* Biomes o' Plenty (or any other major biome mod, really): You may experience biome ID conflicts with the Betweenlands's biomes. If this occurs, simply change the IDs in the mod's config to unused IDs and you should be set.

Modpack Policy
----------------

Modpacks are allowed for use with the Betweenlands as long as they are non-profit. However, the mod is primarily built for vanilla, so you should not expect any balancing with mods that you use, and it may break the consistency of the game.

*(This policy is subject to change in the future. When in doubt, ask for permission)*