#!/usr/bin/env python
##############################################################################################################
# FlirImageProcessor.py 
# Last Update: December 25th 2020
# V0.1 : Initial Creation
##############################################################################################################
#
# This Script contains a Class FlirImage, Create an object of this class by passing it the filename of the FLIR
# image you want to process.
# Other Optional parameters to pass are:
# - ShowMinMaxTemperature (True/False), used to plot a min and max temperature marker in the picture.
# - SaveNormalImage (True/False), When set to True, a jpg file be saved containing the normal picture that is
#   embedded in the FLIR Jpeg file's exif meta data.
# - SaveThermalImage (True/False), When set to True, a jpg file be saved containing the thermal picture that is
#   embedded in the FLIR Jpeg file's exif meta data.
# - PrintAllExifMetaData (True/False), When set to True, all extrated Exif meta data attributes are printed to
#   the terminal the script is run from.
#
# The ImageProcessor requires exiftool to be installed on the system, it uses it to extract all the relevant
# information from the exif meta data of the FLIR Jpeg file. (See https://exiftool.org/ for more info.)
# If exiftools is not in the standard search path, you can add it's full path in the __init__() of the class:
# self.ExifToolPath="exiftool"
# This script has been written and tested with Python version 3.5.2, it will not work with 2.x versions. 
#
# In the top of the window some information is shown about the camera and it's settings used to create the
# foto, as well as some information about the foto.
#
# The camera image is shown with the colormap ranging from the minimum to the maximum temperature found in the
# image thermal image data.
#
# Below the image there are 2 slider bars, they can be used to change the minimum temperature and the maximum
# temperature of the colormap used to display the image.
# They can be used to saturate in the lower and / or higher temperatures, so more colors are available for a 
# smaller temperature range and details become visible.
#
# Below the Sliderbars are 3 buttons;
# - The first one is Marker, once pressed, every mouse click in the image will draw a marker and the temperature 
#   of that location. This will continue untill the Marker Button is pressed again.
# - The second button is Select Box, once pressed a selection box can be drawn with the mouse, once a box is drawn
#   the box can be used for 2 functionalities:
#   1) Draw Box and calculate and show the average temperature inside the box
#   2) Create a new colormap of the temperature range inside the box and draw an image overlay of the box with
#      the new colormap. This is usefull to show details in an image without saturating the rest of the image.
#   These two functionalities can be selected by means of pressing the appropriate key once the box is selected:
#   - a or A for average temperature box
#   - t or T for a new Temperature Overlay in the box.
#   Selecting boxes will continue untill the Select Box Button is pressed again.
# - The Third button is to save a processed image of the layers shown in the image section of the window.
#
##############################################################################################################


##############################################################################################################
# Imports
##############################################################################################################
import numpy
import subprocess
from io import BytesIO
import datetime
import json
import matplotlib.pyplot as plot
import matplotlib.patches as patches
from matplotlib import cm
from mpl_toolkits.axes_grid1.inset_locator import inset_axes
from matplotlib.widgets import RectangleSelector, Cursor, Slider, Button
from PIL import Image, ImageEnhance

##############################################################################################################
# Class Definitions
##############################################################################################################
class FLIRImage:
   def __init__(self, ImageName, ShowMinMaxTemperature=True, SaveNormalImage=True, SaveThermalImage=True, PrintAllExifMetaData=False):
      self.ImageName = ImageName
      self.ShowMinMaxTemperature = ShowMinMaxTemperature
      self.PrintAllExifMetaData = PrintAllExifMetaData
      self.ExifToolPath = "exiftool"
      self.FlirObject = self.GetFlirFileData()
      self.MinTemp=numpy.amin(self.FlirObject['ThermalData'])
      self.MaxTemp=numpy.amax(self.FlirObject['ThermalData'])
      self.ThermalMin = self.MinTemp
      self.ThermalMax = self.MaxTemp
      self.MeasurementPoints = []
      self.MeasurementBoxes = []
      self.OverlayBoxes = []
      NormalWidth=self.FlirObject['MetaData']['EmbeddedImageWidth']
      NormalHeight=self.FlirObject['MetaData']['EmbeddedImageHeight']
      self.NewThermalImage = numpy.array(Image.fromarray(self.FlirObject['ThermalData']).resize((NormalWidth, NormalHeight), Image.ANTIALIAS))
      if SaveThermalImage:
         ThermalImageToSave = self.RescaleImageColorMap(self.NewThermalImage)
         self.SaveThermalImage(ThermalImageToSave, self.ImageName.split('.')[0]+"Thermal.jpg")
      ResizeWidth=int(NormalWidth*self.FlirObject['MetaData']['Real2IR'])
      ResizeHeight=int(NormalHeight*self.FlirObject['MetaData']['Real2IR'])
      self.NewRGBImage = numpy.array(Image.fromarray(self.FlirObject['PictureData']).resize((ResizeWidth, ResizeHeight), Image.ANTIALIAS))
      if SaveNormalImage:
         self.SaveImage(self.NewRGBImage, self.ImageName.split('.')[0]+"Normal.jpg")
      # Now here we determine which part of the real image corresponds with the scaled up thermal image
      # There is no science behind this, other than noticing some values that seem to work for my Flir C5 camera. Offsets found in
      # the exif meta data do not seem to align the real image with the thermal image very nicely (X off by 10 pixels and Y off by 4 pixels)
      # so I don't even bother to use them and hardcoded a value here that works for my camera, you probably need to update these...
      CameraXshift = 178
      CameraYshift = 101
      AreaToCrop = (CameraXshift, CameraYshift, (NormalWidth+CameraXshift), (NormalHeight+CameraYshift)) 
      #Cropping the scaled rgb image
      self.NewRGBImage = numpy.array(Image.fromarray(self.NewRGBImage).crop(AreaToCrop))
      #Converting it to greyscale
      self.NewRGBImage = numpy.array(ImageEnhance.Color(Image.fromarray(self.NewRGBImage)).enhance(0.0))
      #Improving the contrast a bit so it mixes better with the thermal image
      self.NewRGBImage = numpy.array(ImageEnhance.Contrast(Image.fromarray(self.NewRGBImage)).enhance(3.0))
      self.MeasurementPointActive=False
      self.SelectionBoxHelpText="SelectionBox Active, actions for Selection Box  once drawn are:\nPress the T or t to Scale the colormap to the temperatures present in the selection Box.\nPress the A or a to Calculate the average temperature present in the selection Box."
      self.MarkerHelpText="Temperature Markers Active, Markers will appear where you click with the mouse in the foto."
      

   def GetFlirFileData(self):
      FlirDataDict=dict()

      #First Get all the Exif Meta Data from the image, binaries are not part of this.
      FlirDataDict['MetaData'] = self.GetMetaData()

      if self.PrintAllExifMetaData:
         for key,value in FlirDataDict['MetaData'].items():
            print(key.__str__()+" : "+value.__str__())

      #Now get the raw thermal camera data and convert the raw data to temperatures using the camera's calibration values from the ExifData.
      PlanckR1=FlirDataDict['MetaData']["PlanckR1"]
      PlanckR2=FlirDataDict['MetaData']["PlanckR2"]
      PlanckB=FlirDataDict['MetaData']["PlanckB"]
      PlanckF=FlirDataDict['MetaData']["PlanckF"]
      PlanckO=FlirDataDict['MetaData']["PlanckO"]
      Emissivity=FlirDataDict['MetaData']['Emissivity']
      RAT=float(FlirDataDict['MetaData']['ReflectedApparentTemperature'].split(" ")[0])
      ExifByteOrder=FlirDataDict['MetaData']['ExifByteOrder']
      FlirDataDict['ThermalData'] = self.GetThermalData(PlanckR1, PlanckR2, PlanckB, PlanckF, PlanckO, Emissivity, RAT, ExifByteOrder)

      #Finally get the Normal image data
      FlirDataDict['PictureData'] = self.GetPictureData()

      return (FlirDataDict)
      
   def GetMetaData(self):
      meta_json = subprocess.check_output([self.ExifToolPath, self.ImageName, "-j"])
      return (json.loads(meta_json.decode())[0])

   def GetThermalData(self, PlanckR1, PlanckR2, PlanckB, PlanckF, PlanckO, Emissivity, RAT, ExifByteOrder="Little-endian (Intel, II)"):
      RawData = subprocess.check_output([self.ExifToolPath, "-RawThermalImage", "-b", self.ImageName])
      ImageStream = BytesIO(RawData)
      ImageData = numpy.array(Image.open(ImageStream))
      
      #For my C5 camera the Thermal Data is a png file in little endian format which needs to be fixed first by swapping
      #the higher and the lower byte.
      if ExifByteOrder.split("-")[0] == "Little":
         ImageData = numpy.right_shift(ImageData, 8) + numpy.left_shift(numpy.bitwise_and(ImageData, 0x00FF), 8)
      
      # Convert to temperature from radiance with simplified formula, ignoring atmospheric influences
      ReflectedRadiationFactor = PlanckR1 / (PlanckR2 * (numpy.exp(PlanckB / (RAT + 273.15)) - PlanckF)) - PlanckO
      ObjectRadiation =  (ImageData - (1 - Emissivity) * ReflectedRadiationFactor) / Emissivity 
      TemperatureData = PlanckB / numpy.log(PlanckR1 / (PlanckR2 * (ObjectRadiation + PlanckO)) + PlanckF) - 273.15
      return (TemperatureData)
   
   def GetPictureData(self):
      RawData = subprocess.check_output([self.ExifToolPath, "-EmbeddedImage", "-b", self.ImageName])
      ImageStream = BytesIO(RawData)
      ImageData = numpy.array(Image.open(ImageStream))
      return (ImageData)

   def SaveThermalImage(self, ImageData, Name):
      MyImage = Image.fromarray(cm.plasma(ImageData, bytes=True))
      # convert to jpeg and enhance
      MyImage = MyImage.convert("RGB")
      MyImage = ImageEnhance.Sharpness(MyImage).enhance(3)
      MyImage.save(Name, "jpeg", quality=100)

   def SaveImage(self, ImageData, Name):
      MyImage = Image.fromarray(ImageData)          
      MyImage.save(Name, "jpeg", quality=100)
   
   def RescaleImageColorMap(self, ImageArray):
      NormalizedImage = (ImageArray - numpy.amin(ImageArray)) / (numpy.amax(ImageArray) - numpy.amin(ImageArray))
      return(NormalizedImage)

   def GetMinMaxTemperatureAndLocation(self):
      MinLocationY,MinLocationX=numpy.where(self.FlirObject['ThermalData'] == numpy.amin(self.FlirObject['ThermalData']))
      MaxLocationY,MaxLocationX=numpy.where(self.FlirObject['ThermalData'] == numpy.amax(self.FlirObject['ThermalData']))
      MinTemperature=self.FlirObject['ThermalData'][MinLocationY,MinLocationX][0]
      MaxTemperature=self.FlirObject['ThermalData'][MaxLocationY,MaxLocationX][0]
      MinLocationX=4*MinLocationX[0]
      MinLocationY=4*MinLocationY[0]
      MaxLocationX=4*MaxLocationX[0]
      MaxLocationY=4*MaxLocationY[0]
      MinLocation=(MinLocationX,MinLocationY)
      MaxLocation=(MaxLocationX,MaxLocationY)
      return (MinTemperature, MaxTemperature, MinLocation, MaxLocation)

   def SelectionBoxMouseClickCallback(self, eclick, erelease):
      #'eclick and erelease are the press and release events'
      if eclick.xdata < 640.0 and erelease.xdata<640.0 and eclick.ydata < 480.0 and erelease.ydata<480.0:
         #print(eclick)
         NewDict = dict()
         NewDict['X1'] = eclick.xdata
         NewDict['X2'] = erelease.xdata
         NewDict['Y1'] = eclick.ydata
         NewDict['Y2'] = erelease.ydata
         self.CurrentSelectionBox = NewDict
       
   def ProcessKeyPresses(self, event):
      if event.key in ['A', 'a'] and self.MyToggleSelectorRS.active:
          self.CreateAverageTemperatureBox()
      if event.key in ['T', 't'] and self.MyToggleSelectorRS.active:
          self.AddOverlayBox()
      
   def AddMeasurementPointMouseClickCallback(self, event):
      X1, Y1 = event.xdata, event.ydata
      if X1 > 1.0 and Y1 > 1.0:
         NewDict = dict()
         NewDict['X'] = X1
         NewDict['Y'] = Y1
         NewDict['HostAxes'] = event.inaxes
         AxesFound = False
         #First checking the overlays if the mouseclick was in one of the overlays, if not it must be on the main image axes.
         for overlay in self.OverlayBoxes:
            if NewDict['HostAxes'] == overlay['OverlayAxes']:
               NewTemperature=overlay['TemperatureArray'][int(Y1/4),int(X1/4)]
               AxesFound = True
         if not AxesFound:
            NewTemperature=self.FlirObject['ThermalData'][int(Y1/4),int(X1/4)]
         NewDict['Temperature'] = NewTemperature
         self.MeasurementPoints.append(NewDict)
         self.PlotMeasurementMarker(NewDict)
   
   def GetMarkerTextCoordinates(self, X,Y):
      if X > 600:
         TextX = X-43
      else:
         TextX = X+10
      if Y > 473:
         TextY = Y
      else:
         TextY = Y+3
      return(TextX,TextY)
   
   def PlotMeasurementMarker(self, Marker):
      X1 = Marker['X']
      Y1 = Marker['Y']
      Temperature = Marker['Temperature']
      AxesToUse = Marker['HostAxes']
      AxesToUse.scatter([X1-1], [Y1-1], marker='+', s=40, facecolors='white', edgecolors='white')
      AxesToUse.scatter([X1-1], [Y1-1], marker='o', s=50, facecolors='none', edgecolors='white')
      TextX, TextY = self.GetMarkerTextCoordinates(X1, Y1)
      AxesToUse.text(TextX, TextY, round(Temperature,1).__str__(), bbox=dict(facecolor='grey', alpha=0.35), fontsize=8, fontweight='bold', color='white')
      self.Figure.canvas.draw_idle()
           
   def LowerSliderUpdate(self, val):
      self.MinTemp = val
      self.ThermalMin = val
      self.PlotImages()

   def UpperSliderUpdate(self, val):
      self.MaxTemp = val
      self.ThermalMax = val
      self.PlotImages()

   def CreateFigure(self):
      widths = [1.0]
      heights = [1.2, 8, 0.25, 0.25, 0.25, 0.9]
      MySpec = dict(width_ratios=widths, height_ratios=heights)
      MySpec.update(wspace=0.1, hspace=0.1) # set the spacing between axes.
      self.Figure, self.PlotList = plot.subplots(nrows=6, ncols=1, gridspec_kw=MySpec, figsize=(10,10), frameon = False)
      self.PlotList[0].get_xaxis().set_visible(False)
      self.PlotList[0].get_yaxis().set_visible(False)
      self.PlotList[0].axis('off')
      self.colorbaraxes = inset_axes(self.PlotList[1], width="2%", height="80%", loc="center left") 
      self.PlotList[1].set_title("FLIR Image Data")
      self.PlotList[1].get_xaxis().set_visible(False)
      self.PlotList[1].get_yaxis().set_visible(False)
      self.PlotList[1].axis('off')
      self.PlotList[2].get_xaxis().set_visible(False)
      self.PlotList[2].get_yaxis().set_visible(False)
      self.PlotList[2].axis('off')
      self.PlotList[3].get_xaxis().set_visible(False)
      self.PlotList[3].get_yaxis().set_visible(False)
      self.PlotList[3].axis('off')
      self.PlotList[4].get_xaxis().set_visible(False)
      self.PlotList[4].get_yaxis().set_visible(False)
      self.PlotList[4].axis('off')
      self.PlotList[5].get_xaxis().set_visible(False)
      self.PlotList[5].get_yaxis().set_visible(False)
      self.PlotList[5].axis('off')
      self.ShowImageInfo()
      
   def ShowImageInfo(self):
      InfoString=self.FlirObject['MetaData']['Make'].__str__()+", "+self.FlirObject['MetaData']['CameraModel'].__str__()
      InfoString=InfoString+", SN:"+self.FlirObject['MetaData']['CameraSerialNumber'].__str__()+", Camera SW Version="+self.FlirObject['MetaData']['CameraSoftware'].__str__()+"\n"
      InfoString=InfoString+"Camera Temperature Range: Min="+self.FlirObject['MetaData']['CameraTemperatureRangeMin'].__str__()+", Max="+self.FlirObject['MetaData']['CameraTemperatureRangeMax'].__str__()+"\n"
      DateInfoString=self.FlirObject['MetaData']['DateTimeOriginal'].__str__()
      DateString=datetime.datetime.strptime(DateInfoString.split(" ")[0], '%Y:%m:%d').strftime('%A, %B %d in the year %Y')
      FotoCreationString=DateString+" @ "+DateInfoString.split(" ")[1]+" UTC"
      InfoString=InfoString+"Foto Creation: "+FotoCreationString+"\n\n"
      InfoString=InfoString+"Emissivity="+self.FlirObject['MetaData']['Emissivity'].__str__()+", Reflected Apparent Temperature="+self.FlirObject['MetaData']['ReflectedApparentTemperature'].__str__()+"\n"
      InfoString=InfoString+"Atmospheric Temperature="+self.FlirObject['MetaData']['AtmosphericTemperature'].__str__()+", Relative Humidity="+self.FlirObject['MetaData']['RelativeHumidity'].__str__()+"\n"
      InfoString=InfoString+"Object Distance="+self.FlirObject['MetaData']['ObjectDistance'].__str__()+", Focus Distance="+self.FlirObject['MetaData']['FocusDistance'].__str__()+", Focal Length="+self.FlirObject['MetaData']['FocalLength'].__str__()+"\n"
      self.PlotList[0].text(0.02,0.01,InfoString, fontsize=10, fontweight='bold', color='black')

   def PlotMinMaxMarkers(self):
      MinTemperature, MaxTemperature, MinLocation, MaxLocation = self.GetMinMaxTemperatureAndLocation()
      X1, Y1 = MinLocation
      X2, Y2 = MaxLocation
      self.PlotList[1].scatter([X1], [Y1], marker='v', s=25, facecolors='none', edgecolors='b')
      self.PlotList[1].scatter([X2], [Y2], marker='^', s=25, facecolors='none', edgecolors='r')
      TextX, TextY = self.GetMarkerTextCoordinates(X1, Y1)
      self.PlotList[1].text(TextX, TextY, round(MinTemperature,2).__str__(), bbox=dict(facecolor='grey', alpha=0.35), fontsize=8, fontweight='bold', color='white')
      TextX, TextY = self.GetMarkerTextCoordinates(X2, Y2)
      self.PlotList[1].text(TextX, TextY, round(MaxTemperature,2).__str__(), bbox=dict(facecolor='grey', alpha=0.35), fontsize=8, fontweight='bold', color='white')

   def PlotImages(self):
      self.PlotList[1].clear()
      self.colorbaraxes.clear()
      self.RGBRef=self.PlotList[1].imshow(self.NewRGBImage)
      self.ThermalRef=self.PlotList[1].imshow(self.NewThermalImage, vmin=self.ThermalMin, vmax=self.ThermalMax, cmap=cm.plasma, interpolation='nearest', alpha=0.8)
      self.ColorBarRef=self.Figure.colorbar(self.ThermalRef, cax=self.colorbaraxes, orientation='vertical')
      self.ColorBarRef.set_ticks([])
      self.PlotList[1].text(7, 38, round(self.MaxTemp,2).__str__(), bbox=dict(facecolor='grey', alpha=0.35), fontsize=10, fontweight='bold', color='white')
      self.PlotList[1].text(7, 448, round(self.MinTemp,2).__str__(), bbox=dict(facecolor='grey', alpha=0.35), fontsize=10, fontweight='bold', color='white')
      self.DrawTemperatureOverlays()
      if self.ShowMinMaxTemperature:
         self.PlotMinMaxMarkers()
      for Marker in self.MeasurementPoints:
         self.PlotMeasurementMarker(Marker)
      self.PlotMeasurementBoxes()
      self.Figure.canvas.draw()
   
   def ClearHelpInfoText(self):   
         self.PlotList[5].clear()
         self.PlotList[5].get_xaxis().set_visible(False)
         self.PlotList[5].get_yaxis().set_visible(False)
         self.PlotList[5].axis('off')
         self.Figure.canvas.draw()
         
   def PressMeasurementMarkerButton(self,bla):
      if self.MeasurementPointActive:
         self.MeasurementPointActive=False           
         self.Figure.canvas.mpl_disconnect(self.MeasurementPointMouseEventCallbackID)
         self.ClearHelpInfoText()
      else:
         #When box selection is active, we disabled it first so only one function can be active at the same time
         if self.MyToggleSelectorRS.active:
            self.PressSelectionBoxButton(bla)
         self.MeasurementPointActive=True
         self.MeasurementPointMouseEventCallbackID = self.Figure.canvas.mpl_connect('button_press_event', self.AddMeasurementPointMouseClickCallback)
         self.PlotList[5].text(0.01,0.07,self.MarkerHelpText)
         self.Figure.canvas.draw()

   def PressSelectionBoxButton(self,bla):
      if self.MyToggleSelectorRS.active:
         self.MyToggleSelectorRS.set_active(False)
         self.ClearHelpInfoText()
      else:
         #When marker is active, we disabled it first so only one function can be active at the same time
         if self.MeasurementPointActive:
            self.PressMeasurementMarkerButton(bla)
         self.MyToggleSelectorRS.set_active(True)
         self.PlotList[5].text(0.01,0.07,self.SelectionBoxHelpText)
         self.Figure.canvas.draw()
      
   def AddWidgets(self):
      self.MyToggleSelectorRS = RectangleSelector(self.PlotList[1], self.SelectionBoxMouseClickCallback, drawtype='box', useblit=True, rectprops=dict(facecolor="white", alpha=0.1, fill=True), button=[1, 3], minspanx=5, minspany=5, spancoords='pixels', interactive=True)
      self.MyToggleSelectorRS.set_active(False)
      plot.connect('key_press_event', self.ProcessKeyPresses)
      axcolor = 'lightgoldenrodyellow'
      TenPercentTemperatureRange=0.1*(self.MaxTemp-self.MinTemp)
      self.LowerColorBarSliderContainer = inset_axes(self.PlotList[2], width="60%", height="100%", loc="upper center") 
      self.LowerColarBarSlider = Slider(self.LowerColorBarSliderContainer, 'LowerBound', round(self.MinTemp-TenPercentTemperatureRange,1), round(self.MaxTemp,1), valinit=round(self.MinTemp,1), valstep=0.1)
      self.LowerColarBarSlider.on_changed(self.LowerSliderUpdate)
      self.UpperColorBarSliderContainer = inset_axes(self.PlotList[3], width="60%", height="100%", loc="upper center") 
      self.UpperColarBarSlider = Slider(self.UpperColorBarSliderContainer, 'UpperBound', round(self.MinTemp,1), round(self.MaxTemp+TenPercentTemperatureRange,1), valinit=round(self.MaxTemp,1), valstep=0.1)
      self.UpperColarBarSlider.on_changed(self.UpperSliderUpdate)
      self.MSButtonContainer = inset_axes(self.PlotList[4], width="25%", height="100%", loc="center left") 
      self.MeasurementMarkerButton = Button(self.MSButtonContainer, 'Marker', color='0.85', hovercolor='0.95')
      self.MeasurementMarkerButton.on_clicked(self.PressMeasurementMarkerButton)
      self.SelectionBoxButtonContainer = inset_axes(self.PlotList[4], width="25%", height="100%", loc="center") 
      self.SelectBoxButton = Button(self.SelectionBoxButtonContainer, 'SelectBox', color='0.85', hovercolor='0.95')
      self.SelectBoxButton.on_clicked(self.PressSelectionBoxButton)
      self.SaveImageButtonContainer = inset_axes(self.PlotList[4], width="25%", height="100%", loc="center right") 
      self.SaveImageButton = Button(self.SaveImageButtonContainer, 'Save Image', color='0.85', hovercolor='0.95')
      self.SaveImageButton.on_clicked(self.SaveFlattenedImage)
      
   def AddOverlayBox(self):
      OverlayDict = dict()
      InsertX=((int(self.CurrentSelectionBox['X1'])-6)/640.0)
      InsertY=1.0-((int(self.CurrentSelectionBox['Y2'])+3)/480.0)
      OverlayDict['PixelWidth']=int(self.CurrentSelectionBox['X2']-self.CurrentSelectionBox['X1'])
      OverlayDict['PixelHeight']=int(self.CurrentSelectionBox['Y2']-self.CurrentSelectionBox['Y1'])
      InsertWidth=(OverlayDict['PixelWidth'])/640.0
      InsertHeight=(OverlayDict['PixelHeight'])/480.0
      OverlayDict['OverlayAxes'] = inset_axes(self.PlotList[1], width="100%", height="100%", loc='lower left', bbox_to_anchor=(InsertX, InsertY, InsertWidth, InsertHeight), bbox_transform=self.PlotList[1].transAxes)
      OverlayDict['OverlayAxes'].get_xaxis().set_visible(False)
      OverlayDict['OverlayAxes'].get_yaxis().set_visible(False)
      OverlayDict['OverlayAxes'].axis('off')
      ColorBarHightString = int(100*(OverlayDict['PixelHeight']-38)/OverlayDict['PixelHeight']).__str__()+"%"
      ColorBarWidthString = int(1000/OverlayDict['PixelWidth']).__str__()+"%"
      OverlayDict['OverlayColorBarAxes'] = inset_axes(OverlayDict['OverlayAxes'], width=ColorBarWidthString, height=ColorBarHightString, loc="center left") 

      #First Scale Down to the original temperaturemap size
      NewX1 = int(self.CurrentSelectionBox['X1']/4)
      NewY1 = int(self.CurrentSelectionBox['Y1']/4)
      NewX2 = int(self.CurrentSelectionBox['X2']/4)
      NewY2 = int(self.CurrentSelectionBox['Y2']/4)
      OverlayDict['TemperatureArray'] = self.FlirObject['ThermalData'][NewY1-1:NewY2,NewX1-1:NewX2]
      OverlayDict['ThermalImage'] = numpy.array(Image.fromarray(OverlayDict['TemperatureArray']).resize((OverlayDict['PixelWidth'], OverlayDict['PixelHeight']), Image.ANTIALIAS))
      OverlayDict['RGBImage'] = self.NewRGBImage[int(self.CurrentSelectionBox['Y1']-1):int(self.CurrentSelectionBox['Y2']),int(self.CurrentSelectionBox['X1']-1):int(self.CurrentSelectionBox['X2'])]
      OverlayDict['ThermalMin'] = numpy.amin(OverlayDict['TemperatureArray'])
      OverlayDict['ThermalMax'] = numpy.amax(OverlayDict['TemperatureArray'])
      self.OverlayBoxes.append(OverlayDict)
      self.PlotImages()

   def DrawTemperatureOverlays(self):
      for overlayDict in self.OverlayBoxes:
         overlayDict['OverlayAxes'].clear()
         overlayDict['OverlayColorBarAxes'].clear()
         overlayDict['RGBRef']=overlayDict['OverlayAxes'].imshow(overlayDict['RGBImage'])
         overlayDict['ThermalRef']=overlayDict['OverlayAxes'].imshow(overlayDict['ThermalImage'], vmin=overlayDict['ThermalMin'], vmax=overlayDict['ThermalMax'], cmap=cm.YlOrRd, interpolation='nearest', alpha=0.75)
         overlayDict['ColorBarRef']=self.Figure.colorbar(overlayDict['ThermalRef'], cax=overlayDict['OverlayColorBarAxes'], orientation='vertical')
         overlayDict['ColorBarRef'].set_ticks([])
         overlayDict['OverlayAxes'].text(5, 12, round(overlayDict['ThermalMax'],2).__str__(), bbox=dict(facecolor='grey', alpha=0.35), fontsize=8, fontweight='bold', color='white')
         overlayDict['OverlayAxes'].text(5, overlayDict['PixelHeight']-8, round(overlayDict['ThermalMin'],2).__str__(), bbox=dict(facecolor='grey', alpha=0.35), fontsize=8, fontweight='bold', color='white')
     
   def CreateAverageTemperatureBox(self):
      self.MeasurementBoxes.append(self.CurrentSelectionBox)
      self.PlotImages()
      
   def PlotMeasurementBoxes(self):
      for box in self.MeasurementBoxes:
         #First Scale Down to the original temperaturemap size
         NewX1 = int(box['X1']/4)
         NewY1 = int(box['Y1']/4)
         NewX2 = int(box['X2']/4)
         NewY2 = int(box['Y2']/4)
         NewTemperatureArray=self.FlirObject['ThermalData'][NewY1-1:NewY2,NewX1-1:NewX2]
         TemperatureSamples=NewTemperatureArray.size
         AverageTemperature=sum(sum(NewTemperatureArray))/TemperatureSamples
         self.PlotList[1].text(((NewX1+NewX2)*2)-20, ((NewY1+NewY2)*2)+5, round(AverageTemperature,1).__str__(), fontsize=10, fontweight='bold', color='white')
         RectangleFrame=patches.Rectangle((NewX1*4,NewY1*4),(NewX2-NewX1)*4,(NewY2-NewY1)*4,linewidth=3,edgecolor='black',facecolor='white', alpha=0.15)
         self.PlotList[1].add_patch(RectangleFrame)
         self.Figure.canvas.draw_idle()

   def SaveFlattenedImage(self, bla):
      extent = self.PlotList[1].get_window_extent().transformed(self.Figure.dpi_scale_trans.inverted())
      self.Figure.savefig(self.ImageName.split('.')[0]+"Processed.png", bbox_inches=extent)

   def ShowFigure(self):
      plot.show()

##############################################################################################################
# Main Application
##############################################################################################################
MyFlirImage = FLIRImage("FLIR0356.jpg")
MyFlirImage.CreateFigure()
MyFlirImage.PlotImages()
MyFlirImage.AddWidgets()
MyFlirImage.ShowFigure()

