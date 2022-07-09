# Face Mask Detection with Faster R-CNN Network
> This is the final project of the Vision Measurement Course in SJTU.\
> This project implements Faster R-CNN to detect the face area and 
classify whether the people wear the face mask.
<!-- Live demo [_here_](https://www.example.com). -->
<!-- If you have the project hosted somewhere, include the link here. -->

## Table of Contents
* [General Info](#general-information)
* [Screenshots](#screenshots)
* [Setup](#setup)
* [Dataset](#dataset)
* [Train](#train)
* [Test](#test)
* [Contact](#contact)
<!-- * [License](#license) -->


## General Information
This project implements pretrained Faster R-CNN to detect the face area and 
classify whether the people wear the face mask.
<!-- You don't have to answer all the questions - just the ones relevant to your project. -->


## Screenshots
![Example screenshot](./img/main_img.png)



## Setup
This code has been tested on **win11**, **Python 3.6** and the following libraries：

**matplotlib==3.3.4\
numpy==1.19.2\
pandas==1.1.5\
Pillow==9.2.0\
requests==2.26.0\
scikit_learn==1.1.1\
torch==1.9.0\
torchvision==0.10.0**

Please install related libraries before running this code:

`  pip install -r requirements.txt`

## Dataset
The face mask can be download in Kaggle:

[Face Mask Detection](https://www.kaggle.com/datasets/andrewmvd/face-mask-detection?datasetId=667889&searchQuery=pytorch)



## Train
To train the model, run the following file:

`face-mask-detection-faster-r-cnn-pytorch.py`

## Test
To test the model, run the following file:

`map_test.py`


<!-- Optional -->
<!-- ## License -->
<!-- This project is open source and available under the [... License](). -->

<!-- You don't have to include all sections - just the one's relevant to your project -->
