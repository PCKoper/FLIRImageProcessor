# FLIRImageProcessor
Python Script for analysing FLIR Jpeg Images with embedded Thermal Data.

This Script contains a Class FlirImage, Create an object of this class by passing it the filename of the FLIR
image you want to process.
Other Optional parameters to pass are:
- ShowMinMaxTemperature (True/False), used to plot a min and max temperature marker in the picture.
- SaveNormalImage (True/False), When set to True, a jpg file be saved containing the normal picture that is
  embedded in the FLIR Jpeg file's exif meta data.
- SaveThermalImage (True/False), When set to True, a jpg file be saved containing the thermal picture that is
  embedded in the FLIR Jpeg file's exif meta data.
- PrintAllExifMetaData (True/False), When set to True, all extrated Exif meta data attributes are printed to
  the terminal the script is run from.

The ImageProcessor requires exiftool to be installed on the system, it uses it to extract all the relevant
information from the exif meta data of the FLIR Jpeg file. (See https://exiftool.org/ for more info.)
If exiftools is not in the standard search path, you can add it's full path in the __init__() of the class:
self.ExifToolPath="exiftool"
This script has been written and tested with Python version 3.5.2, it will not work with 2.x versions. 

In the top of the window some information is shown about the camera and it's settings used to create the
foto, as well as some information about the foto.

The camera image is shown with the colormap ranging from the minimum to the maximum temperature found in the
image thermal image data.

Below the image there are 2 slider bars, they can be used to change the minimum temperature and the maximum
temperature of the colormap used to display the image.
They can be used to saturate in the lower and / or higher temperatures, so more colors are available for a 
smaller temperature range and details become visible.

Below the Sliderbars are 3 buttons;
- The first one is Marker, once pressed, every mouse click in the image will draw a marker and the temperature 
  of that location. This will continue untill the Marker Button is pressed again.
- The second button is Select Box, once pressed a selection box can be drawn with the mouse, once a box is drawn
  the box can be used for 2 functionalities:
  1) Draw Box and calculate and show the average temperature inside the box
  2) Create a new colormap of the temperature range inside the box and draw an image overlay of the box with
     the new colormap. This is usefull to show details in an image without saturating the rest of the image.
  These two functionalities can be selected by means of pressing the appropriate key once the box is selected:
  - a or A for average temperature box
  - t or T for a new Temperature Overlay in the box.
  Selecting boxes will continue untill the Select Box Button is pressed again.
- The Third button is to save a processed image of the layers shown in the image section of the window.
