# Spoon Anti-Warping Reborn

A continuation of [Spoon Anti-Warping](https://github.com/5axes/SpoonAntiWarping/) by [5axes](https://github.com/5axes/).


**Do you want to stop things warping while printing but need to use support?**  
We've all been there. Something needs a little help to stop it warping so you tried [Tab Anti-Warping Reborn](https://github.com/slashee-the-Cow/TabAntiWarpingReborn/) but that takes over the support settings, and your print needs support. Luckily for you...
### We've got spoons!
![A star with a spoon attached to each point](/images/spoons_header.webp)  
These give the parts of your model which are liable to wander an anchor point to help them stay in place. Cura treats the spoons as regular objects so you can use whatever support you want with it. In fact, this doesn't need to control *any* of your print settings, unlike its cousin who thinks tabs are so great.

## So how do I use it?
Glad you asked! Just select your object, then click the icon on the toolbar for the Spoon Anti-Warping Reborn tool:

It looks like this --> ![Toolbar icon for Spoon Anti-Warping Reborn](/images/toolbar_icon.webp)

That will open the settings panel, so select your object and you can just click the **Add Automatically** button and it will add them to the major corners of your model... automatically! If you need more (or you think you can do a better job than a pretty simple computer algorithm) you can just click any part of your model to add a spoon.

## What do the settings do?
They say "a picture is worth a thousand words". I think you deserve more than a thousand though. So here's a diagram and some extra words to explain it!  
![Diagram highlighting different parts of an anti-warping spoon](/images/settings_diagram.webp)
- **Spoon Diameter:** The diameter of the circular part of the spoon (highlighted in green).
- **Handle Length:** The distance from the model to the circular part of the spoon (blue arrow).
- **Handle Width:** How wide the handle is, side to side (red arrow). Wider handle gives you a better hold but is a little harder to remove after the print. Experiment to see what works best for you.
- **Number of Layers:** Add a couple of extra layers to your spoon to make sure it's grabbing more than just the base of your model. Like the handle width, higher = better hold, but harder to remove. You probably shouldn't need more than about three layers but experiment! (Maybe I'm wrong. I am sometimes.)
- **Print Order:** Print spoons first to give your model a "template" to fit into and adhere to. Print spoons last to... I'm not a spoonologist, but I'm sure there's a good reason. Or just leave it unchanged and let Cura do its thing.
- **Teardrop Shape:** Don't worry about the handle too much - just extend straight out into the circular part: ![Image of "Teardrop shape" style spoon](/images/teardrop_shape.webp)
- **Automatic Placement Density:** Adjusts the minimum gap between spoons in crowded places (like curves).

## Known Issues
- Due to a [bug in Cura](https://github.com/Ultimaker/Cura/issues/20488) it can try and place spoons in the wrong places sometimes. I've put in the best workarounds I know about at this point and it will automatically delete any spoons that would be placed off the build plate.
- Print ordering uses settings from the first extruder. It might not work properly if different extruders have different settings.
- In version 5.0 the dropdowns in the settings panel won't show their contents. This is a problem with Cura's theming. Since the active one *is* shown, you can just pick them in turn until you find the correct one.

## Version History
### 1.1.4:
- Added "Tight" option for automatic placement density. Will generate more spoons, but they're more likely to overlap.
### 1.1.3:
- Automatic spoon placement should now place spoons on the edge of the model correctly in the case of a raised edge (chamfer, fillet, bevel, etc.).
- Print ordering should no longer accidentally catch (and potentially remove) non-movement commands.
### 1.1.2:
- Spoons now have ironing disabled by default in case you are using ironing. This can be changed in the "Per Object Settings" tool by selecting a spoon.
- Automatic spoon placement now takes all non-extrusion moves into account when removing combing.
- Automatic spoon placement should have less chance of conflicting with other plugins/post-processing scripts if they insert code which doesn't follow Cura's syntax.
### 1.1.1:
- Automatic spoon placement will now follow the base of the model touching the build plate rather than the overall outline.
- If a model has multiple separate areas touching the build plate, automatic spoon placement will now run for all of them individually.
- New "Automatic Placement Density" setting allows you to increase the spacing between spoons on areas like curves to reduce chances of overlaps.
- Print order function now takes G2/G3 arc moves into account for determining position and extruder position.
- Fixed a logic bug that could cause spoons to be placed too closely if they were the first and last points on an object.
### 1.1.0:
**Print ordering!** Choose to print spoons before objects, after objects or just leave it unchanged and let Cura do the thinking. Shouldn't require changing any print settings. Intelligently handles travels to save time.
### 1.0.0: Initial release
#### What's new?
- Spoons will now automatically point at intervals of the shape's outline, not just the nearest corner.
- Input validation in the user interface now lets you know if settings are invalid and won't let you create spoons if they are.
- Build plate adhesion no longer has to be turned on for the spoons to calculate their angle.
#### What's fixed?
- Updated to support the latest versions of Cura.
- A lot of internal calculations should be more accurate now.
- Control panel user interface should now flow better and better match Cura's theme.
- Bugs have been squashed.
- Optimised the logic in many of the functions by removing unnecessary calculations and loops. Should run a little faster.
- The "remove all" function should now be less likely to remove things which aren't spoons.
#### What's different?
- Renamed "Direct Shape" to "Teardrop shape".
- New toolbar icon.
- Renamed everything internally so you can have this and another version of the Spoon Anti-Warping plugin installed side-by-side.
- Uses a built in form of notifications since using Cura's native ones can cause buggy behaviour.
#### What's gone?
- The minimum Cura version required is now 5.0 because support for Qt 5 has been dropped to make maintaining the codebase easier.
- Removed the "initial layer speed" setting from the plugin. You can still set in in Cura's print quality settings.
- Bundled post-processing scripts have been removed so I can focus on the core plugin.
- Existing translation files have been removed (since they'd be broken by all the changes). If you want to help translate it, I'd appreciate it, so get in touch!